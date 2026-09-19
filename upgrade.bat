@echo off
REM ============================================================
REM  Upgrade an existing v1.0 installation to v1.1 (English output
REM  intentionally: this script is meant to be run by an AI agent).
REM  Usage:  upgrade.bat "<old installation folder>"
REM  Keeps:  backend\data (database + uploads) and tools\python312
REM  Updates: all program files, then auto-migrates the database.
REM ============================================================
set "NEW=%~dp0"
set "OLD=%~1"

if "%OLD%"=="" (
    echo [ERROR] Usage: upgrade.bat "old_installation_folder"
    exit /b 1
)
if not exist "%OLD%\backend\app\main.py" (
    echo [ERROR] "%OLD%" does not look like an installation folder ^(backend\app\main.py not found^)
    exit /b 1
)
if not exist "%OLD%\tools\python312\python.exe" (
    echo [ERROR] "%OLD%\tools\python312\python.exe" not found - this is not a v1.0 installation
    exit /b 1
)

echo ============================================
echo  Upgrade to v1.1
echo  NEW source: %NEW%
echo  OLD target: %OLD%
echo ============================================

echo [1/5] Stopping running service...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*app_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo [2/5] Backing up old database...
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
robocopy "%OLD%\backend\data" "%OLD%\backup_%TS%" /E /NFL /NDL /NJH /NJS >nul
if exist "%OLD%\backup_%TS%" (echo     backup saved to backup_%TS%) else (echo     [WARN] no data folder to back up)

echo [3/5] Copying new program files ^(keeps backend\data and tools\python312^)...
robocopy "%NEW%" "%OLD%" /E /NFL /NDL /NJH /NJS /XD "%NEW%tools\python312" "%NEW%backend\data" __pycache__ /XF shortcuts.txt server.log *.pyc >nul
if errorlevel 8 (
    echo [ERROR] file copy failed
    exit /b 1
)

echo [4/5] Running database migration...
"%OLD%\tools\python312\python.exe" "%OLD%\scripts\migrate_v1_1.py"
if errorlevel 1 (
    echo [ERROR] migration failed. Database backup is in %OLD%\backup_%TS%
    exit /b 1
)

echo [5/5] Starting service...
start "" "%OLD%\tools\python312\pythonw.exe" "%OLD%\app_server.py"
set /a tries=0
:waitloop
timeout /t 2 /nobreak >nul
curl -s -o nul http://127.0.0.1:8000/api/health
if not errorlevel 1 goto ready
set /a tries+=1
if %tries% geq 15 goto fail
goto waitloop

:ready
echo.
echo [OK] UPGRADE COMPLETE. Service is running at http://127.0.0.1:8000
echo     Verify: curl http://127.0.0.1:8000/api/companies  should list companies
echo     Rollback if needed: backup folder %OLD%\backup_%TS%
exit /b 0

:fail
echo [ERROR] service did not start. Check %OLD%\backend\data\server.log
exit /b 1
