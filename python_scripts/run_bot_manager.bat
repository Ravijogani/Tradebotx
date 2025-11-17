@echo off
REM Run Bot Manager on Windows - FINAL

set BOT_DIR=C:\trading-bot
set PORT=8080

echo ========================================
echo Starting Trading Bot Manager
echo ========================================
echo Port: %PORT%
echo Directory: %BOT_DIR%
echo.

cd /d "%BOT_DIR%"
call venv\Scripts\activate.bat

echo Installing/checking required libraries...
pip install waitress flask psutil

echo Starting server...
echo Press Ctrl+C to stop
echo.

REM This will now use the BOT_MANAGER_SECRET from the Windows environment
REM (the one you set with 'setx')
python -m waitress --host=0.0.0.0 --port=%PORT% bot_manager_http_windows:app

pause
