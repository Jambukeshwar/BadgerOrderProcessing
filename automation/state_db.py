import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'badger.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attachment_id TEXT UNIQUE,
                filename TEXT,
                downloaded_at TEXT,
                status TEXT,
                run_at TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS iccid_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                iccid TEXT,
                status TEXT,
                attempt_count INTEGER DEFAULT 0,
                sf_order_id TEXT,
                error TEXT,
                last_updated TEXT,
                FOREIGN KEY (file_id) REFERENCES processed_files(id)
            );
        """)
    conn.close()


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def insert_file(attachment_id: str, filename: str, run_at: str) -> int:
    conn = get_conn()
    with conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO processed_files
               (attachment_id, filename, downloaded_at, status, run_at, created_at)
               VALUES (?, ?, ?, 'queued', ?, ?)""",
            (attachment_id, filename, now_utc(), run_at, now_utc())
        )
        file_id = cur.lastrowid
    conn.close()
    return file_id


def update_file_status(file_id: int, status: str):
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE processed_files SET status=? WHERE id=?",
            (status, file_id)
        )
    conn.close()


def get_due_files():
    conn = get_conn()
    now = now_utc()
    rows = conn.execute(
        "SELECT * FROM processed_files WHERE status='queued' AND run_at <= ?",
        (now,)
    ).fetchall()
    conn.close()
    return rows


def file_already_processed(attachment_id: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM processed_files WHERE attachment_id=?",
        (attachment_id,)
    ).fetchone()
    conn.close()
    return row is not None


def bulk_insert_iccids(file_id: int, iccids: list[str]):
    conn = get_conn()
    ts = now_utc()
    with conn:
        conn.executemany(
            """INSERT OR IGNORE INTO iccid_status
               (file_id, iccid, status, attempt_count, last_updated)
               VALUES (?, ?, 'pending', 0, ?)""",
            [(file_id, iccid, ts) for iccid in iccids]
        )
    conn.close()


def get_iccids_by_status(file_id: int, status: str) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT iccid FROM iccid_status WHERE file_id=? AND status=?",
        (file_id, status)
    ).fetchall()
    conn.close()
    return [r['iccid'] for r in rows]


def update_iccid_status(file_id: int, iccid: str, status: str,
                        sf_order_id: str = None, error: str = None):
    conn = get_conn()
    with conn:
        conn.execute(
            """UPDATE iccid_status
               SET status=?, sf_order_id=COALESCE(?, sf_order_id),
                   error=COALESCE(?, error), last_updated=?
               WHERE file_id=? AND iccid=?""",
            (status, sf_order_id, error, now_utc(), file_id, iccid)
        )
    conn.close()


def increment_attempt(file_id: int, iccid: str):
    conn = get_conn()
    with conn:
        conn.execute(
            """UPDATE iccid_status
               SET attempt_count = attempt_count + 1, last_updated=?
               WHERE file_id=? AND iccid=?""",
            (now_utc(), file_id, iccid)
        )
    conn.close()


def get_iccid_attempt_count(file_id: int, iccid: str) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT attempt_count FROM iccid_status WHERE file_id=? AND iccid=?",
        (file_id, iccid)
    ).fetchone()
    conn.close()
    return row['attempt_count'] if row else 0


def get_all_created_iccids() -> set:
    """Return every ICCID this app has ever successfully created an order for."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT iccid FROM iccid_status WHERE status = 'created'"
    ).fetchall()
    conn.close()
    return {r['iccid'] for r in rows}


def bulk_update_iccid_statuses(file_id: int, iccid_status_map: dict[str, str]):
    """iccid_status_map: {iccid: new_status}"""
    conn = get_conn()
    ts = now_utc()
    with conn:
        conn.executemany(
            "UPDATE iccid_status SET status=?, last_updated=? WHERE file_id=? AND iccid=?",
            [(status, ts, file_id, iccid) for iccid, status in iccid_status_map.items()]
        )
    conn.close()
