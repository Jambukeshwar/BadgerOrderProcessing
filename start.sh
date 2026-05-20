#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
mkdir -p log
nohup uvicorn web_app:app --host 0.0.0.0 --port 8001 > log/app.log 2>&1 &
echo "Badger started on port 8001 — tail -f log/app.log"
