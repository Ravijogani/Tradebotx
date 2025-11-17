@echo off
REM Diagnostic script to check Windows bot manager setup
REM Run this to verify your configuration

echo ========================================
echo Trading Bot Manager - Setup Diagnostics
echo ========================================
echo.

echo [1/8] Checking Python installation...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found!
    goto :error
)
echo OK: Python found
echo.

echo [2/8] Checking working directory...
cd
if not exist "bot_manager_http_windows.py" (
    echo ERROR: bot_manager_http_windows.py not found in current directory!
    echo Please run this script from C:\trading-bot
    goto :error
)
echo OK: In correct directory
echo.

echo [3/8] Checking required files...
if not exist "bot_wrapper.py" echo MISSING: bot_wrapper.py
if not exist "hybrid_trading_bot_multiuser.py" echo MISSING: hybrid_trading_bot_multiuser.py
if not exist "requirements.txt" echo MISSING: requirements.txt
if not exist "run_bot_manager.bat" echo MISSING: run_bot_manager.bat

if exist "bot_manager_http_windows.py" if exist "bot_wrapper.py" if exist "hybrid_trading_bot_multiuser.py" (
    echo OK: All required Python files present
) else (
    echo ERROR: Some required files are missing!
    goto :error
)
echo.

echo [4/8] Checking virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo WARNING: Virtual environment not found
    echo Run: python -m venv venv
) else (
    echo OK: Virtual environment found
)
echo.

echo [5/8] Checking BOT_MANAGER_SECRET...
if "%BOT_MANAGER_SECRET%"=="" (
    echo ERROR: BOT_MANAGER_SECRET not set!
    echo Run: setx BOT_MANAGER_SECRET "your-secret-here"
    echo Then close and reopen Command Prompt
    goto :error
) else (
    echo OK: BOT_MANAGER_SECRET is set
    echo    Length: 
    echo %BOT_MANAGER_SECRET%| find /c /v "" 
    echo    First 4 chars: %BOT_MANAGER_SECRET:~0,4%...
    echo    Last 4 chars: ...%BOT_MANAGER_SECRET:~-4%
)
echo.

echo [6/8] Checking Windows Firewall...
powershell -Command "Get-NetFirewallRule -DisplayName 'Bot Manager HTTP' -ErrorAction SilentlyContinue"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Firewall rule not found
    echo Run as Administrator: 
    echo    New-NetFirewallRule -DisplayName "Bot Manager HTTP" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
) else (
    echo OK: Firewall rule exists
)
echo.

echo [7/8] Checking if port 8080 is in use...
netstat -an | findstr :8080
if %ERRORLEVEL% EQU 0 (
    echo OK: Port 8080 is listening
) else (
    echo INFO: Port 8080 is not in use (bot manager not running)
)
echo.

echo [8/8] Testing local connectivity...
curl http://localhost:8080/health
if %ERRORLEVEL% NEQ 0 (
    echo INFO: Bot manager not responding (may not be running)
) else (
    echo OK: Bot manager is responding
)
echo.

echo ========================================
echo Diagnostics Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Fix any ERRORS shown above
echo 2. Address any WARNINGS
echo 3. Start bot manager with: run_bot_manager.bat
echo 4. Test remote access from dashboard
echo.
pause
goto :end

:error
echo.
echo ========================================
echo Setup has errors - please fix them first
echo ========================================
pause
exit /b 1

:end
exit /b 0
