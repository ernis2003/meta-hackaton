@echo off
echo Starting backend
cd /d "%~dp0..\backend"
".venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8001
