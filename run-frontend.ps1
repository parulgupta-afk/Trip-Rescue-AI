# Trip Rescue AI – start frontend (Windows PowerShell)
Set-Location $PSScriptRoot\simulator
if (-not (Test-Path node_modules)) {
    npm install
}
Write-Host "Starting simulator on http://localhost:5173 ..." -ForegroundColor Cyan
npm run dev
