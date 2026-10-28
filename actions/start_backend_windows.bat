@echo off
echo Starting backend
cd ./backend
uvicorn main:app --reload
echo Backend started successfully!