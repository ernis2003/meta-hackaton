@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-ai\Scripts\python.exe" (
  echo Run setup_ai_windows.bat first.
  exit /b 1
)
call ".venv-ai\Scripts\activate.bat"
python -m src.ai.training.run_pipeline %*
exit /b %errorlevel%
