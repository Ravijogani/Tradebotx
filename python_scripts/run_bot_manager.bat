@echo off
REM Run Bot Manager on Windows

set BOT_DIR=C:\trading-bot
set PORT=8080

REM Check if BOT_MANAGER_SECRET is set
if "%BOT_MANAGER_SECRET%"=="" (
    echo WARNING: BOT_MANAGER_SECRET environment variable not set!
    echo Please set it before running:
    echo   setx BOT_MANAGER_SECRET "your-secret-here"
    echo.
    echo For now, using default (INSECURE - change this!)
    set BOT_MANAGER_SECRET=change-this-secret-now
)

echo ========================================
echo Starting Trading Bot Manager
echo ========================================
echo Port: %PORT%
echo Directory: %BOT_DIR%
echo.

cd /d "%BOT_DIR%"
call venv\Scripts\activate.bat

echo Starting server...
echo Press Ctrl+C to stop
echo.

REM Use waitress for production-ready WSGI server on Windows
python -m waitress --host=0.0.0.0 --port=%PORT% bot_manager_http:app

REM Alternative: Use Flask development server
REM python bot_manager_http.py

pause
