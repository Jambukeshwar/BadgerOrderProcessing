# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Automates bulk Salesforce order creation from ICCID (SIM card identifier) CSV files. Supports two ingestion modes: manual CSV upload via web UI, and automated polling of Jira ticket attachments. Tracks per-ICCID state in SQLite and retries failed orders up to a configurable limit.

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Start the web server (port 8001)
uvicorn web_app:app --host 0.0.0.0 --port 8001

# Background with logging
nohup uvicorn web_app:app --host 0.0.0.0 --port 8001 > log/app.log 2>&1 &

# Stop
pkill -f "uvicorn web_app:app"
```

## Running Tests

```bash
python -m pytest tests/
# or individual test files:
python -m pytest tests/test_processing.py
python -m pytest tests/test_ordermanagement.py
python -m pytest tests/test_orchesmanagement.py
```

No pytest config exists; tests are present but not integrated into CI.

## Configuration

| File | Purpose |
|------|---------|
| `.env.local` | Secrets: SF credentials, Jira API token, AWS keys, SMTP config |
| `automation_config.json` | Runtime: `jira_ticket_id`, `processing_window` (IST 7–17h), `max_retry_attempts` |
| `config.json` | Legacy: S3 paths, SF environment, AWS settings |
| `rulesmappings/mappings.json` | Field mapping rules by entity for the rules engine |

## Architecture

### Entry Point & Request Flow

`web_app.py` is the FastAPI server. Two pipeline triggers:
- `POST /api/run/csv` — user uploads a CSV with an `ICCID` column
- `POST /api/run/jira` — fetches CSV attachment from configured Jira ticket

Both call `_run_pipeline()` which runs in a **daemon thread** so the HTTP response returns immediately. Progress is written to `badger_progress.json` throughout for live UI polling.

### Pipeline Steps (inside `_run_pipeline`)

1. Count ICCIDs; check Salesforce Assets for already-active orders (skip duplicates)
2. `data/generatecsv.py` → `data/LBPR00015_4500006921.csv` (expands each ICCID into 2 product lines with BATCH_NAME/PO_NUMBER sequencing)
3. `Badger.py` orchestrator (runs as **subprocess**):
   - `processCSV.py` — reformats CSV for SF Bulk API
   - SF Bulk API upsert via `utils/sfmanagement.py`
   - `PrepRetry.py` — filters "Fatally Failed" records for retry list
4. `automation/sf_validator.py` — SOQL queries verify created orders (chunks at 800 IDs to stay under SF 20k-char limit)
5. `automation/retry_handler.py` — re-runs failed ICCIDs; marks permanently failed after `max_retry_attempts`
6. Write output CSVs; persist state to SQLite

### Module Map

| Module | Role |
|--------|------|
| `web_app.py` | HTTP layer, SF CLI auth, background thread management |
| `Badger.py` | Subprocess orchestrator for the legacy pipeline |
| `processCSV.py` | Transforms ICCID CSV into SF Bulk API format |
| `PrepRetry.py` | Extracts fatally-failed records for retry |
| `data/generatecsv.py` | ICCID → order CSV (2 products per ICCID) |
| `automation/orchestrator.py` | Background pipeline orchestration |
| `automation/progress.py` | Writes `badger_progress.json` (steps: csv_ready → generating → uploading → validating → retrying → completed) |
| `automation/state_db.py` | SQLite: `processed_files` and `iccid_status` tables |
| `automation/sf_validator.py` | SOQL order verification, duplicate detection |
| `automation/retry_handler.py` | Retry counting and permanent-failure promotion |
| `automation/jira_monitor.py` | Polls Jira API for CSV attachments |
| `automation/scheduler.py` | UTC time-window gating for processing |
| `utils/processing.py` | Core ETL: S3 read → rules transform → SF upsert |
| `utils/sfmanagement.py` | SF Bulk API wrapper |
| `utils/rulesmanagement.py` | Field transformation rules engine |
| `utils/handlermanagement.py` | Factory for migration vs. processing flows |
| `schemas/` | Pydantic models for config, orders, payloads, process logs |
| `templates/index.html` | Tailwind dashboard (upload, status, history, settings tabs) |

### State Persistence

SQLite (managed by `automation/state_db.py`) tracks two tables:
- `processed_files` — history of each uploaded/fetched file
- `iccid_status` — per-ICCID lifecycle: `pending → failed → permanently_failed`

### SF CLI Integration

`web_app.py` uses `sf org display` and `sf org login` (Salesforce CLI) for authentication rather than username+password in code. Ensure `sf` CLI is installed and authenticated before starting the server.

## Output Files

| File | Content |
|------|---------|
| `order_report.csv` | All processing results |
| `duplicate_orders_report.csv` | ICCIDs skipped as already-active |
| `permanently_failed.csv` | ICCIDs that exceeded max retry attempts |
| `log/app.log` | Uvicorn stdout |
| `log/badger_live.log` | Pipeline subprocess stdout/stderr |
| `log/trackFile_log.txt` | Application-level logging |

## Deployment (Linux/Ubuntu)

See `SETUP.md` and `deploy.sh`. The app registers as a `badger` systemd service with auto-restart. `deploy.sh` handles venv creation, dependency install, and service registration.

The `Procfile` entry (`web: uvicorn main:app`) is outdated — the actual entry point is `web_app.py`, not `main.py`.
