@echo off
REM ============================================================================
REM  SETUP MT5 INSTANCE FOR A NEW USER - TradeBotX
REM ============================================================================
REM  This script creates a portable MT5 installation for a new user.
REM  
REM  USAGE:
REM    setup_mt5_instance.bat <user_id_short> <source_mt5_folder>
REM
REM  EXAMPLE:
REM    setup_mt5_instance.bat 5e6b929b "C:\trading-bot\MT5_Template"
REM
REM  PREREQUISITES:
REM    1. You need ONE working MT5 installation as a "template"
REM       - Install MT5 normally once
REM       - This becomes your template for copying
REM    2. The template should have the broker's server list already configured
REM
REM  WHAT THIS DOES:
REM    1. Creates C:\trading-bot\MT5_Instances\<user_id_short>\
REM    2. Copies the MT5 template into it (portable copy)
REM    3. The bot manager will then use this instance for that user
REM ============================================================================

setlocal enabledelayedexpansion

set USER_ID=%~1
set SOURCE_MT5=%~2
set MT5_INSTANCES_DIR=C:\trading-bot\MT5_Instances

if "%USER_ID%"=="" (
    echo ERROR: Please provide user_id_short as first argument
    echo USAGE: setup_mt5_instance.bat ^<user_id_short^> ^<source_mt5_folder^>
    echo EXAMPLE: setup_mt5_instance.bat 5e6b929b "C:\trading-bot\MT5_Template"
    exit /b 1
)

if "%SOURCE_MT5%"=="" (
    echo ERROR: Please provide source MT5 folder as second argument
    echo This should be your MT5 template installation folder
    exit /b 1
)

if not exist "%SOURCE_MT5%\terminal64.exe" (
    echo ERROR: terminal64.exe not found in %SOURCE_MT5%
    echo Make sure you point to a valid MT5 installation folder
    exit /b 1
)

set TARGET_DIR=%MT5_INSTANCES_DIR%\%USER_ID%

echo ============================================
echo Setting up MT5 instance for user: %USER_ID%
echo Source: %SOURCE_MT5%
echo Target: %TARGET_DIR%
echo ============================================

if exist "%TARGET_DIR%\terminal64.exe" (
    echo WARNING: MT5 instance already exists for user %USER_ID%
    echo Skipping copy. Delete the folder first if you want to recreate.
    exit /b 0
)

echo Creating directory...
mkdir "%TARGET_DIR%" 2>nul

echo Copying MT5 files (this may take a minute)...
xcopy "%SOURCE_MT5%\*" "%TARGET_DIR%\" /E /H /Y /Q

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to copy MT5 files
    exit /b 1
)

echo.
echo ✅ MT5 instance created successfully!
echo    Path: %TARGET_DIR%\terminal64.exe
echo.
echo NEXT STEPS:
echo    1. The bot manager will automatically use this instance
echo    2. When the user starts a bot, MT5 will launch from this folder
echo    3. Each instance logs in independently - no conflicts!
echo.

endlocal
