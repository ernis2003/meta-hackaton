@echo off
echo Starting backend
cd /d "%~dp0..\backend"
".venv\Scripts\python.exe" ..\actions\ensure_zeek_service.py
if errorlevel 1 (
    pause
    exit /b 1
)
".venv\Scripts\python.exe" ..\actions\ensure_model_service.py
if errorlevel 1 (
    echo Model service startup failed. See backend\src\ai\results\model_service.log.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8001
