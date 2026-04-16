@echo off
REM ============================================================================
REM  BULK SETUP: Create MT5 instances for all users from database
REM ============================================================================
REM  This script provisions MT5 portable instances for multiple users.
REM  
REM  USAGE:
REM    setup_all_users_mt5.bat <source_mt5_folder>
REM
REM  EXAMPLE:
REM    setup_all_users_mt5.bat "C:\trading-bot\MT5_Template"
REM
REM  NOTE: Edit the USER_IDS list below with your actual user IDs (first 8 chars)
REM ============================================================================

setlocal enabledelayedexpansion

set SOURCE_MT5=%~1
set MT5_INSTANCES_DIR=C:\trading-bot\MT5_Instances

if "%SOURCE_MT5%"=="" (
    echo ERROR: Please provide source MT5 template folder
    echo USAGE: setup_all_users_mt5.bat "C:\trading-bot\MT5_Template"
    exit /b 1
)

if not exist "%SOURCE_MT5%\terminal64.exe" (
    echo ERROR: terminal64.exe not found in %SOURCE_MT5%
    exit /b 1
)

REM ============================================================================
REM  EDIT THIS LIST WITH YOUR USER IDs (first 8 characters of each user's UUID)
REM  Get these from your Supabase dashboard -> profiles table
REM ============================================================================
set USER_IDS=5e6b929b user2_id user3_id

echo ============================================
echo  Bulk MT5 Instance Setup
echo  Source template: %SOURCE_MT5%
echo  Target base: %MT5_INSTANCES_DIR%
echo ============================================
echo.

mkdir "%MT5_INSTANCES_DIR%" 2>nul

for %%U in (%USER_IDS%) do (
    set TARGET=%MT5_INSTANCES_DIR%\%%U
    
    if exist "!TARGET!\terminal64.exe" (
        echo [SKIP] %%U - already exists
    ) else (
        echo [SETUP] %%U - copying MT5 files...
        mkdir "!TARGET!" 2>nul
        xcopy "%SOURCE_MT5%\*" "!TARGET!\" /E /H /Y /Q >nul
        
        if !ERRORLEVEL! EQU 0 (
            echo [OK] %%U - MT5 instance created
        ) else (
            echo [FAIL] %%U - copy failed!
        )
    )
)

echo.
echo ============================================
echo  Setup complete! Listing instances:
echo ============================================
dir /b "%MT5_INSTANCES_DIR%"

endlocal
