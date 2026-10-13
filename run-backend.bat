@echo off
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -e ".[dev]" -q
echo Starting Trip Rescue AI backend on http://localhost:8000 ...
uvicorn server.http_facade:app --reload --port 8000
