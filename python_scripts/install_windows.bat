@echo off
REM Windows Bot Manager Installation Script
REM Run this as Administrator

echo ========================================
echo Trading Bot Manager - Windows Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo ✓ Python detected
python --version
echo.

REM Create bot directory
set BOT_DIR=C:\trading-bot
if not exist "%BOT_DIR%" (
    echo Creating directory: %BOT_DIR%
    mkdir "%BOT_DIR%"
)

REM Copy files
echo Copying bot files...
copy /Y bot_wrapper.py "%BOT_DIR%\" >nul
copy /Y hybrid_trading_bot.py "%BOT_DIR%\" >nul
copy /Y bot_manager_http_windows.py "%BOT_DIR%\bot_manager_http.py" >nul
copy /Y requirements.txt "%BOT_DIR%\" >nul

REM Create virtual environment
echo Creating virtual environment...
cd /d "%BOT_DIR%"
python -m venv venv

REM Activate virtual environment and install dependencies
echo Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install flask gunicorn psutil
pip install waitress

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Bot directory: %BOT_DIR%
echo.
echo Next steps:
echo 1. Set environment variable BOT_MANAGER_SECRET
echo 2. Run: run_bot_manager.bat
echo.
pause
