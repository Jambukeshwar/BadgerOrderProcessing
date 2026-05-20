"""
Entry point for the automation cron job.
Run every minute via cron:
  * * * * * /path/to/.env/bin/python /path/to/llab2bengine/automation/orchestrator.py >> /path/to/log/automation.log 2>&1
"""
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure llab2bengine/ is on the path so all existing utils imports work
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
load_dotenv('.env.local')

from utils.logger import Logger
from automation.state_db import init_db, insert_file, get_due_files, update_file_status
from automation.scheduler import get_run_at_utc
from automation.jira_monitor import check_for_new_file
from automation.pipeline_runner import run_full_pipeline
from automation.sf_validator import validate_and_diff, get_order_status_for_iccids
from automation.retry_handler import handle_retries

logger = Logger().get_logger()

LOCK_FILE = ROOT / 'badger_pipeline.lock'
CONFIG_FILE = ROOT / 'automation_config.json'


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _read_input_iccids() -> list[str]:
    csv_path = ROOT / 'data' / 'input_iccid.csv'
    if not csv_path.exists():
        return []
    import pandas as pd
    df = pd.read_csv(csv_path, dtype=str)
    col = df.columns[0]
    return df[col].dropna().str.strip().tolist()


def main():
    # ── Lock check ─────────────────────────────────────────────────────────
    if LOCK_FILE.exists():
        logger.info('Lock file exists — another run is in progress. Skipping.')
        return

    try:
        LOCK_FILE.touch()
        init_db()
        config = _load_config()

        # ── 1. Check Jira for new CSV attachment ───────────────────────────
        attachment, filename = check_for_new_file(config)
        if attachment:
            run_at = get_run_at_utc(config)
            file_id = insert_file(str(attachment['id']), filename, run_at)
            logger.info(f"Queued file '{filename}' (id={file_id}) to run at {run_at}")

        # ── 2. Run any due jobs ─────────────────────────────────────────────
        due_files = get_due_files()
        if not due_files:
            logger.info('No jobs due. Exiting.')
            return

        for file_row in due_files:
            file_id   = file_row['id']
            file_name = file_row['filename']
            logger.info(f"Processing file '{file_name}' (id={file_id})")
            update_file_status(file_id, 'processing')

            try:
                # ── 3. Run the pipeline ─────────────────────────────────────
                run_full_pipeline()

                # ── 4. Validate against Salesforce ──────────────────────────
                input_iccids = _read_input_iccids()
                diff = validate_and_diff(file_id, input_iccids)

                if diff['needs_retry']:
                    logger.info(f"{len(diff['needs_retry'])} ICCIDs need retry.")
                    df_orders = get_order_status_for_iccids(diff['needs_retry'])
                    handle_retries(file_id, diff['needs_retry'], df_orders, config)

                update_file_status(file_id, 'completed')
                logger.info(f"File '{file_name}' completed.")

            except Exception as e:
                logger.exception(f"Pipeline error for file '{file_name}': {e}")
                update_file_status(file_id, 'failed')

    finally:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()


if __name__ == '__main__':
    main()
