import os
import requests
import shutil
from pathlib import Path
from dotenv import load_dotenv
from utils.logger import Logger
from automation.state_db import file_already_processed

load_dotenv('.env.local')
logger = Logger().get_logger()

INPUT_CSV = Path('data') / 'input_iccid.csv'


def _auth() -> tuple[str, str]:
    email = os.environ['JIRA_EMAIL']
    token = os.environ['JIRA_API_TOKEN']
    return (email, token)


def _base_url() -> str:
    return os.environ['JIRA_BASE_URL'].rstrip('/')


def fetch_new_attachment(ticket_id: str) -> dict | None:
    """
    Check the Jira ticket for a CSV attachment not yet in processed_files.
    Returns attachment metadata dict or None if nothing new.
    """
    url = f"{_base_url()}/rest/api/2/issue/{ticket_id}"
    resp = requests.get(url, auth=_auth(), timeout=30)
    resp.raise_for_status()

    attachments = resp.json().get('fields', {}).get('attachment', [])
    csv_attachments = [
        a for a in attachments
        if a.get('filename', '').upper().endswith('.CSV')
    ]

    if not csv_attachments:
        logger.info(f'No CSV attachments found on {ticket_id}')
        return None

    # Most recent attachment first
    csv_attachments.sort(key=lambda a: a.get('created', ''), reverse=True)

    for attachment in csv_attachments:
        att_id = str(attachment['id'])
        if not file_already_processed(att_id):
            logger.info(f"New attachment found: {attachment['filename']} (id={att_id})")
            return attachment

    logger.info('All CSV attachments already processed.')
    return None


def download_attachment(attachment: dict) -> str:
    """Download the attachment content to input_iccid.csv. Returns the filename."""
    content_url = attachment['content']
    filename = attachment['filename']

    resp = requests.get(content_url, auth=_auth(), timeout=60, stream=True)
    resp.raise_for_status()

    INPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(INPUT_CSV, 'wb') as f:
        shutil.copyfileobj(resp.raw, f)

    logger.info(f"Downloaded '{filename}' → {INPUT_CSV}")
    return filename


def check_for_new_file(config: dict) -> tuple[dict | None, str | None]:
    """
    High-level entry point called by orchestrator.
    Returns (attachment_metadata, filename) or (None, None).
    """
    ticket_id = config.get('jira_ticket_id') or os.environ.get('JIRA_TICKET_ID', '')
    if not ticket_id:
        logger.warning('JIRA_TICKET_ID not configured — skipping Jira check.')
        return None, None

    try:
        attachment = fetch_new_attachment(ticket_id)
        if attachment is None:
            return None, None
        filename = download_attachment(attachment)
        return attachment, filename
    except Exception as e:
        logger.error(f'Jira monitor error: {e}')
        return None, None
