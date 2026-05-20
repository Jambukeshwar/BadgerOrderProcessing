"""
Badger ICCID Pipeline — Web UI
Usage: uvicorn web_app:app --reload --port 8001
"""
import json
import os
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv('.env.local')

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import automation.progress as progress
from automation.state_db import (
    init_db, get_conn, insert_file, update_file_status,
    bulk_insert_iccids, bulk_update_iccid_statuses
)
from automation.scheduler import get_run_at_utc

app = FastAPI(title='Badger Automation')
templates = Jinja2Templates(directory=str(ROOT / 'templates'))

INPUT_CSV        = ROOT / 'data' / 'input_iccid.csv'
LIVE_LOG_FILE    = ROOT / 'log' / 'badger_live.log'
AUTOMATION_CFG   = ROOT / 'automation_config.json'

_running   = False
_run_lock  = threading.Lock()

init_db()

def _warmup_sf():
    try:
        from automation.sf_validator import _get_sf
        _get_sf()
        print('[Badger] Salesforce connection warmed up.')
    except Exception as e:
        print(f'[Badger] SF warmup failed (will retry on first run): {e}')

threading.Thread(target=_warmup_sf, daemon=True).start()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if AUTOMATION_CFG.exists():
        with open(AUTOMATION_CFG, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_config(config: dict):
    with open(AUTOMATION_CFG, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def _count_iccids(csv_path: Path) -> list[str]:
    import pandas as pd
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path, dtype=str)
    col = df.columns[0]
    return df[col].dropna().str.strip().tolist()


class _LogTee:
    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file
        self.encoding = 'utf-8'

    def write(self, data):
        if isinstance(data, str):
            try: self.original.write(data); self.original.flush()
            except Exception: pass
            try: self.log_file.write(data); self.log_file.flush()
            except Exception: pass
        return len(data) if data else 0

    def flush(self):
        try: self.original.flush()
        except Exception: pass
        try: self.log_file.flush()
        except Exception: pass

    def isatty(self): return False


# ── Pipeline runner ────────────────────────────────────────────────────────────

def _run_pipeline(source: str, filename: str, file_id: int = 0):
    """Runs in a background thread. Writes progress + live log throughout."""
    global _running

    LIVE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_file   = open(LIVE_LOG_FILE, 'w', encoding='utf-8', buffering=1)
    old_stdout = sys.stdout
    sys.stdout = _LogTee(old_stdout, log_file)

    started_at   = datetime.now()
    total_iccids = 0
    active_count = 0
    retry_count  = 0
    perm_failed  = 0
    config       = _load_config()

    try:
        import subprocess
        import pandas as pd
        from automation.sf_validator import check_orders_created, check_duplicate_orders
        from automation.retry_handler import handle_retries

        # Clear stale reports from previous run
        for _report in ('order_report.csv', 'duplicate_orders_report.csv'):
            _p = ROOT / 'log' / _report
            if _p.exists():
                _p.unlink()

        # ── Step 0: count ICCIDs ────────────────────────────────────────────
        iccids = _count_iccids(INPUT_CSV)
        total_iccids = len(iccids)
        progress.write('csv_ready', 5,
                       detail=f'{total_iccids:,} ICCIDs ready',
                       source=source, filename=filename, total_iccids=total_iccids,
                       started_at=started_at.isoformat())
        print(f'[Badger] {total_iccids:,} ICCIDs loaded from {filename}')

        if file_id and iccids:
            bulk_insert_iccids(file_id, iccids)

        skipped_count = 0

        # ── Step 0.5: pre-check — skip ICCIDs already Active in SF Asset ───────
        from automation.sf_validator import get_already_ordered_iccids
        progress.write('csv_ready', 10,
                       detail='Checking Salesforce Asset for already-provisioned ICCIDs...',
                       source=source, filename=filename, total_iccids=total_iccids,
                       started_at=started_at.isoformat())
        already_ordered = get_already_ordered_iccids(iccids)
        if already_ordered:
            new_iccids = [i for i in iccids if i not in already_ordered]
            skipped_count = len(iccids) - len(new_iccids)
            if skipped_count:
                print(f'[Badger] Skipping {skipped_count:,} ICCID(s) already Active in Salesforce Asset — no duplicate orders')
                pd.DataFrame({'ICCID': new_iccids}).to_csv(INPUT_CSV, index=False)
                iccids       = new_iccids
                total_iccids = len(iccids)

        if not iccids:
            progress.finish('completed',
                            detail=f'All {skipped_count:,} ICCID(s) already Active in Salesforce Asset — nothing to do',
                            source=source, filename=filename,
                            total_iccids=skipped_count, active_count=skipped_count,
                            retry_count=0, perm_failed=0,
                            has_report=False,
                            started_at=started_at.isoformat())
            print('[Badger] All ICCIDs already Active in Salesforce Asset — pipeline skipped')
            return

        # ── Step 1: generatecsv.py ──────────────────────────────────────────
        progress.write('generating', 20,
                       detail=f'Generating order CSV for {total_iccids:,} ICCIDs...',
                       source=source, filename=filename, total_iccids=total_iccids)
        r = subprocess.run(
            [sys.executable, 'generatecsv.py'],
            cwd=str(ROOT / 'data'),
            capture_output=True, text=True
        )
        if r.stdout: print(r.stdout.strip())
        if r.stderr: print(r.stderr.strip())
        if r.returncode != 0:
            raise RuntimeError(f'generatecsv.py exited {r.returncode}')
        print('[Badger] generatecsv.py OK')

        # ── Step 2: Badger.py (processCSV + Bulk upsert + PrepRetry) ───────
        progress.write('uploading', 50,
                       detail='Uploading to Salesforce via Bulk API...',
                       source=source, filename=filename, total_iccids=total_iccids)
        r = subprocess.run(
            [sys.executable, 'Badger.py'],
            cwd=str(ROOT),
            capture_output=True, text=True
        )
        if r.stdout: print(r.stdout.strip())
        if r.stderr: print(r.stderr.strip())
        if r.returncode != 0:
            raise RuntimeError(f'Badger.py exited {r.returncode}')
        print('[Badger] Badger.py OK')

        # ── Step 3: check if orders were created ────────────────────────────
        progress.write('validating', 75,
                       detail='Checking Salesforce — did orders get created?',
                       source=source, filename=filename, total_iccids=total_iccids)
        diff          = check_orders_created(file_id, iccids)
        active_count  = len(diff['created']) + skipped_count
        retry_count   = len(diff['needs_retry'])
        print(f'[Badger] Orders: {len(diff["created"]):,} new / {skipped_count:,} existing / {retry_count:,} missing')

        # ── Duplicate order detection ────────────────────────────────────────
        df_dupes = check_duplicate_orders()
        dupe_count = df_dupes['ICCID'].nunique() if not df_dupes.empty else 0

        # ── Step 4: retry missing orders ────────────────────────────────────
        if diff['needs_retry']:
            progress.write('retrying', 88,
                           detail=f'Re-running pipeline for {retry_count:,} missing orders...',
                           source=source, filename=filename, total_iccids=total_iccids,
                           active_count=active_count, retry_count=retry_count)
            handle_retries(file_id, diff['needs_retry'], config)

            perm_log = ROOT / 'log' / 'permanently_failed.csv'
            if perm_log.exists():
                perm_failed = len(pd.read_csv(perm_log))

        elapsed = int((datetime.now() - started_at).total_seconds())
        detail_msg = f'{active_count:,} orders created · {retry_count:,} retried · {perm_failed:,} perm-failed'
        if dupe_count:
            detail_msg += f' · ⚠ {dupe_count:,} duplicate order(s) — see log/duplicate_orders_report.csv'
        progress.finish('completed',
                        detail=detail_msg,
                        source=source, filename=filename,
                        total_iccids=total_iccids, active_count=active_count,
                        retry_count=retry_count, perm_failed_count=perm_failed,
                        duplicate_count=dupe_count,
                        elapsed_seconds=elapsed)
        print(f'[Badger] Pipeline complete in {elapsed}s')

        if file_id:
            update_file_status(file_id, 'completed')

    except Exception as e:
        import traceback
        traceback.print_exc()
        elapsed = int((datetime.now() - started_at).total_seconds())
        progress.finish('failed', detail=str(e),
                        source=source, filename=filename,
                        total_iccids=total_iccids, elapsed_seconds=elapsed)
        if file_id:
            update_file_status(file_id, 'failed')

    finally:
        log_file.close()
        sys.stdout = old_stdout
        with _run_lock:
            _running = False


def _start_thread(target, args=()):
    global _running
    with _run_lock:
        _running = True
    t = threading.Thread(target=target, args=args, daemon=True)
    t.start()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    config = _load_config()
    return templates.TemplateResponse(request, 'index.html', {
        'jira_ticket_id': config.get('jira_ticket_id', ''),
        'jira_base_url':  os.environ.get('JIRA_BASE_URL', 'https://prodapt.atlassian.net'),
    })


@app.post('/api/run/csv')
async def run_csv(file: UploadFile = File(...)):
    if _running:
        return JSONResponse({'status': 'already_running'}, status_code=409)

    import pandas as pd
    import io

    filename = file.filename or 'input_iccid.txt'
    raw = await file.read()

    # Parse TXT — one ICCID per line, strip whitespace, drop blanks
    try:
        lines = raw.decode('utf-8', errors='replace').splitlines()
        iccid_list = [l.strip() for l in lines if l.strip()]
        df = pd.DataFrame({'ICCID': iccid_list})
    except Exception as e:
        return JSONResponse({'error': f'Could not parse file: {e}'}, status_code=400)

    if df.empty:
        return JSONResponse({'error': 'No ICCID values found in the uploaded file.'}, status_code=400)

    INPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(INPUT_CSV, index=False)

    progress.clear()
    if LIVE_LOG_FILE.exists():
        LIVE_LOG_FILE.unlink()

    _start_thread(_run_pipeline, ('csv_upload', filename, 0))
    return {'status': 'started', 'source': 'csv_upload', 'filename': filename}


@app.post('/api/run/jira')
async def run_jira(request: Request):
    if _running:
        return JSONResponse({'status': 'already_running'}, status_code=409)

    body      = await request.json()
    ticket_id = body.get('ticket_id', '').strip()
    if not ticket_id:
        return JSONResponse({'error': 'ticket_id is required'}, status_code=400)

    config = _load_config()
    config['jira_ticket_id'] = ticket_id
    _save_config(config)

    progress.clear()
    if LIVE_LOG_FILE.exists():
        LIVE_LOG_FILE.unlink()

    def _jira_thread():
        global _running
        try:
            progress.write('csv_ready', 3,
                           detail=f'Fetching CSV from Jira ticket {ticket_id}...',
                           source='jira', filename='')

            from automation.jira_monitor import check_for_new_file
            attachment, filename = check_for_new_file(config)
            if not attachment:
                progress.finish('failed', detail='No new CSV attachment found on Jira ticket.')
                return

            run_at  = get_run_at_utc(config)
            file_id = insert_file(str(attachment['id']), filename, run_at)
            update_file_status(file_id, 'processing')
            _run_pipeline('jira', filename, file_id)
        except Exception as e:
            progress.finish('failed', detail=str(e))
        finally:
            with _run_lock:
                _running = False

    _start_thread(_jira_thread)
    return {'status': 'started', 'source': 'jira', 'ticket_id': ticket_id}


@app.get('/api/status')
async def get_status():
    return {'running': _running}


@app.get('/api/progress')
async def get_progress():
    prog_file = ROOT / 'log' / 'badger_progress.json'
    if not prog_file.exists():
        return {'available': False, 'running': _running}
    try:
        data = json.loads(prog_file.read_text(encoding='utf-8'))
        data['available'] = True
        data['running']   = _running
        return data
    except Exception:
        return {'available': False, 'running': _running}


@app.get('/api/download/order-report')
async def download_order_report():
    report = ROOT / 'log' / 'order_report.csv'
    if not report.exists():
        return JSONResponse({'error': 'No order report available yet. Run the pipeline first.'}, status_code=404)
    return FileResponse(str(report), media_type='text/csv', filename='order_report.csv')


@app.get('/api/report/exists')
async def report_exists():
    return {'exists': (ROOT / 'log' / 'order_report.csv').exists()}


@app.get('/api/live-log')
async def get_live_log():
    if not LIVE_LOG_FILE.exists():
        return {'content': '', 'running': _running}
    try:
        content = LIVE_LOG_FILE.read_text(encoding='utf-8', errors='replace')
        return {'content': content, 'running': _running}
    except Exception:
        return {'content': '', 'running': _running}


@app.get('/api/history')
async def get_history():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM processed_files ORDER BY created_at DESC LIMIT 30"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()




@app.get('/api/sf/status')
async def sf_status():
    try:
        from automation.sf_validator import _get_sf
        sf = _get_sf()
        return {'connected': True, 'username': os.environ.get('SF_USERNAME', ''), 'instance_url': sf.sf_instance}
    except Exception as e:
        return {'connected': False, 'error': str(e)}


@app.get('/api/config')
async def get_config():
    config = _load_config()
    return {
        'jira_ticket_id':              config.get('jira_ticket_id', ''),
        'processing_window_start_ist': config.get('processing_window_start_ist', '07:00'),
        'processing_window_end_ist':   config.get('processing_window_end_ist', '17:00'),
        'max_retry_attempts':          config.get('max_retry_attempts', 3),
    }


@app.post('/api/config')
async def save_config_route(request: Request):
    body   = await request.json()
    config = _load_config()
    for key in ('jira_ticket_id', 'processing_window_start_ist',
                'processing_window_end_ist', 'max_retry_attempts'):
        if key in body:
            config[key] = body[key]
    _save_config(config)
    return {'status': 'saved'}
