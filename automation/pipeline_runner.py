import subprocess
import sys
import os
from pathlib import Path
from utils.logger import Logger

logger = Logger().get_logger()

ROOT = Path(__file__).parent.parent  # llab2bengine/


def _run(cmd: list[str], cwd: Path = ROOT):
    logger.info(f'Running: {" ".join(cmd)}')
    result = subprocess.run(
        cmd, cwd=str(cwd),
        capture_output=True, text=True
    )
    if result.stdout:
        logger.info(result.stdout.strip())
    if result.stderr:
        logger.warning(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(
            f'Command failed (exit {result.returncode}): {" ".join(cmd)}\n{result.stderr}'
        )


def run_full_pipeline():
    """Run generatecsv.py → Badger.py (which calls processCSV.py + PrepRetry.py)."""
    logger.info('--- Pipeline start ---')

    # Step 1: generate LBPR CSV from input_iccid.csv
    _run([sys.executable, 'generatecsv.py'], cwd=ROOT / 'data')

    # Step 2: main pipeline (processCSV → SF bulk upsert → PrepRetry)
    _run([sys.executable, 'Badger.py'], cwd=ROOT)

    logger.info('--- Pipeline complete ---')


def run_retry_pipeline(failed_iccids: list[str]):
    """Write failed ICCIDs to input_iccid.csv and re-run the full pipeline."""
    input_csv = ROOT / 'data' / 'input_iccid.csv'
    logger.info(f'Writing {len(failed_iccids)} failed ICCIDs to {input_csv} for retry.')

    with open(input_csv, 'w', encoding='utf-8') as f:
        f.write('ICCID\n')
        for iccid in failed_iccids:
            f.write(f'{iccid}\n')

    run_full_pipeline()
