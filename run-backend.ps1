# Trip Rescue AI – start backend (Windows PowerShell)
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]" -q
Write-Host "Starting Trip Rescue AI on http://localhost:8000 ..." -ForegroundColor Cyan
uvicorn server.http_facade:app --reload --port 8000
