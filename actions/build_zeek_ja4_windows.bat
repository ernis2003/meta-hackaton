@echo off
setlocal
cd /d "%~dp0.."
docker build --tag forensics-zeek-ja4:local --file backend\zeek\Dockerfile backend\zeek
if errorlevel 1 exit /b 1
echo Configure backend/.env: ZEEK_DOCKER_IMAGE=forensics-zeek-ja4:local and ZEEK_SCRIPTS=ja4
