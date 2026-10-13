#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -e ".[dev]" -q
echo "Starting Trip Rescue AI on http://localhost:8000 ..."
exec uvicorn server.http_facade:app --reload --port 8000
