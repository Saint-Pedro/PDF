#!/usr/bin/env bash
# Starts PDF Studio locally: http://localhost:8000
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r requirements.txt
fi
PORT="${PORT:-8000}"
echo "PDF Studio → http://localhost:$PORT"
exec .venv/bin/uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "$PORT"
