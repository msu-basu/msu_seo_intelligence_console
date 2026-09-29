@echo off
REM =============================================================================
REM MSU Analytics Daily Ingestion - Windows Task Scheduler Runner
REM =============================================================================

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "LOGS_DIR=%PROJECT_ROOT%\logs"

if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

echo [%date% %time%] Starting MSU Analytics ingestion job... >> "%LOGS_DIR%\cron_ingestion.log"

cd /d "%PROJECT_ROOT%"

REM Execute python runner using project virtual environment
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\venv\Scripts\python.exe" "%PROJECT_ROOT%\scripts\run_ingestion.py" >> "%LOGS_DIR%\cron_ingestion.log" 2>&1
) else (
    python "%PROJECT_ROOT%\scripts\run_ingestion.py" >> "%LOGS_DIR%\cron_ingestion.log" 2>&1
)

set EXIT_CODE=%errorlevel%
echo [%date% %time%] Ingestion job finished with Exit Code: %EXIT_CODE% >> "%LOGS_DIR%\cron_ingestion.log"
exit /b %EXIT_CODE%
