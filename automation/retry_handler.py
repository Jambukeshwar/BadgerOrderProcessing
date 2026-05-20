import pandas as pd
from pathlib import Path
from utils.logger import Logger
from automation.state_db import (
    get_iccid_attempt_count, increment_attempt, update_iccid_status,
    bulk_update_iccid_statuses
)
from automation.pipeline_runner import run_retry_pipeline

logger = Logger().get_logger()

MAX_RETRIES = 3
PERM_FAILED_LOG = Path('log') / 'permanently_failed.csv'


def handle_retries(file_id: int, failed_iccids: list[str], config: dict):
    """
    Re-run the full pipeline (generatecsv → Badger.py) for ICCIDs that have
    no order in Salesforce. Permanently fails any ICCID that has exhausted
    max_retry_attempts.
    """
    if not failed_iccids:
        logger.info('No failed ICCIDs to retry.')
        return

    max_attempts = config.get('max_retry_attempts', MAX_RETRIES)
    needs_pipeline: list[str] = []
    perm_failed: list[dict] = []

    for iccid in failed_iccids:
        attempt = get_iccid_attempt_count(file_id, iccid)

        if attempt >= max_attempts:
            logger.warning(f'ICCID {iccid} permanently failed after {attempt} attempts.')
            update_iccid_status(file_id, iccid, 'permanently_failed')
            perm_failed.append({'iccid': iccid, 'attempts': attempt})
        else:
            increment_attempt(file_id, iccid)
            logger.info(f'Retrying ICCID {iccid} (attempt {attempt + 1})')
            needs_pipeline.append(iccid)

    if perm_failed:
        PERM_FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(perm_failed).to_csv(PERM_FAILED_LOG, index=False)
        logger.warning(f'{len(perm_failed)} permanently failed → {PERM_FAILED_LOG}')

    if needs_pipeline:
        logger.info(f'Re-running pipeline for {len(needs_pipeline)} ICCIDs...')
        try:
            run_retry_pipeline(needs_pipeline)
        except Exception as e:
            logger.error(f'Retry pipeline failed: {e}')
            bulk_update_iccid_statuses(
                file_id,
                {iccid: 'failed' for iccid in needs_pipeline}
            )
