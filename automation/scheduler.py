from datetime import datetime, time, timedelta, timezone
import pytz

IST = pytz.timezone('Asia/Kolkata')

WINDOW_START = time(7, 0)   # 07:00 IST
WINDOW_END   = time(17, 0)  # 17:00 IST


def get_run_at_utc(config: dict) -> str:
    """Return ISO UTC timestamp for when the job should be executed."""
    start_str = config.get('processing_window_start_ist', '07:00')
    end_str   = config.get('processing_window_end_ist',   '17:00')
    w_start = time(*map(int, start_str.split(':')))
    w_end   = time(*map(int, end_str.split(':')))

    now_ist = datetime.now(IST)
    current_time = now_ist.time()

    if current_time < w_start:
        # Before window — run today at window start
        run_ist = now_ist.replace(
            hour=w_start.hour, minute=w_start.minute, second=0, microsecond=0
        )
    elif current_time <= w_end:
        # Inside window — run immediately
        run_ist = now_ist.replace(second=0, microsecond=0)
    else:
        # After window — run tomorrow at window start
        tomorrow = now_ist + timedelta(days=1)
        run_ist = tomorrow.replace(
            hour=w_start.hour, minute=w_start.minute, second=0, microsecond=0
        )

    return run_ist.astimezone(timezone.utc).isoformat()


def is_within_window(config: dict) -> bool:
    start_str = config.get('processing_window_start_ist', '07:00')
    end_str   = config.get('processing_window_end_ist',   '17:00')
    w_start = time(*map(int, start_str.split(':')))
    w_end   = time(*map(int, end_str.split(':')))
    now_ist = datetime.now(IST)
    return w_start <= now_ist.time() <= w_end
