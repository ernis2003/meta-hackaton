@echo off
echo Starting a frontend
cd /d "%~dp0..\frontend"
node -e "fetch('http://localhost:5173/src/App.tsx',{signal:AbortSignal.timeout(1500)}).then(async r=>process.exit(r.ok&&(await r.text()).includes('NetworkSubjects')?0:1)).catch(()=>process.exit(1))"
if not errorlevel 1 (
    echo Existing JA4 forensics frontend is ready at http://localhost:5173
    exit /b 0
)
call npm run dev -- --host localhost --port 5173 --strictPort
