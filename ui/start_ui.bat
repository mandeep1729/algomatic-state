@echo off
echo ========================================
echo   Regime State Visualization UI
echo ========================================
echo.

REM Check if Python virtual environment exists
if exist "..\\.venv\\Scripts\\activate.bat" (
    call ..\\.venv\\Scripts\\activate.bat
) else (
    echo Warning: Virtual environment not found at ..\.venv
    echo Make sure you have activated your Python environment.
    echo.
)

REM Start backend in a new window
echo Starting backend server...
start "Backend Server" cmd /k "cd /d %~dp0.. && python -m ui.run_backend"

REM Wait for backend to start
echo Waiting for backend to initialize...
timeout /t 3 /nobreak > nul

REM Start frontend
echo Starting frontend...
cd frontend
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)
echo.
echo Frontend will be available at: http://localhost:5173
echo.
call npm run dev
