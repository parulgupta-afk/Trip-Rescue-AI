@echo off
cd /d "%~dp0simulator"
if not exist node_modules (
    npm install
)
echo Starting simulator on http://localhost:5173 ...
npm run dev
