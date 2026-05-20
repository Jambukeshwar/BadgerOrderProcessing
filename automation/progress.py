import json
from datetime import datetime
from pathlib import Path

PROGRESS_FILE = Path('log') / 'badger_progress.json'

STEPS = [
    'csv_ready',    # 0
    'generating',   # 1
    'uploading',    # 2
    'validating',   # 3
    'retrying',     # 4
    'completed',    # 5
]

STEP_LABELS = {
    'csv_ready':  'CSV loaded — preparing data',
    'generating': 'Generating order CSV',
    'uploading':  'Uploading to Salesforce (Bulk API)',
    'validating': 'Validating provisioning status',
    'retrying':   'Retrying failed ICCIDs',
    'completed':  'Pipeline complete',
    'failed':     'Pipeline failed',
}


def _load_started_at() -> str:
    """Read started_at from the existing progress file so it survives across writes."""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding='utf-8')).get('started_at', '')
        except Exception:
            pass
    return ''


def write(step: str, percent: int, detail: str = '', **kwargs):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'step': step,
        'step_index': STEPS.index(step) if step in STEPS else -1,
        'label': STEP_LABELS.get(step, step),
        'detail': detail,
        'percent': percent,
        'status': 'running',
        'ts': datetime.now().isoformat(),
    }
    if 'started_at' not in kwargs:
        prev = _load_started_at()
        if prev:
            data['started_at'] = prev
    data.update(kwargs)
    PROGRESS_FILE.write_text(json.dumps(data), encoding='utf-8')


def finish(status: str, detail: str = '', **kwargs):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'step': status,
        'step_index': 5 if status == 'completed' else -1,
        'label': STEP_LABELS.get(status, status),
        'detail': detail,
        'percent': 100 if status == 'completed' else 0,
        'status': status,
        'ts': datetime.now().isoformat(),
    }
    if 'started_at' not in kwargs:
        prev = _load_started_at()
        if prev:
            data['started_at'] = prev
    data.update(kwargs)
    PROGRESS_FILE.write_text(json.dumps(data), encoding='utf-8')


def clear():
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
