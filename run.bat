@echo off
REM Starts PDF Studio locally: http://localhost:8000
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
if "%PORT%"=="" set PORT=8000
echo PDF Studio -^> http://localhost:%PORT%
start "" http://localhost:%PORT%
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port %PORT%
