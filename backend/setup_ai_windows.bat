@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-ai\Scripts\python.exe" py -3.12 -m venv .venv-ai
if errorlevel 1 exit /b 1
".venv-ai\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
".venv-ai\Scripts\python.exe" -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 exit /b 1
".venv-ai\Scripts\python.exe" -m pip install -r requirements-ai.txt
if errorlevel 1 exit /b 1
".venv-ai\Scripts\python.exe" -m src.ai.training.preflight
