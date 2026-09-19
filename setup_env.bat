@echo off
REM ============================================================
REM  ???????????????? start.bat / install_autostart.bat ?????
REM  ???????????? %PYTHON%????? exit /b 1
REM ============================================================
set "SCRIPT_DIR=%~dp0"
set "PYTHON=%SCRIPT_DIR%tools\python312\python.exe"

if not exist "%PYTHON%" (
    where python >nul 2>nul && set "PYTHON=python"
)
if "%PYTHON%"=="python" (
    echo [!] ¦Ä??? Python??????????????§Á?? Python 3.12???11MB????????¦²?...
    mkdir "%SCRIPT_DIR%tools" 2>nul
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile '%SCRIPT_DIR%tools\python-embed.zip'"
    if not exist "%SCRIPT_DIR%tools\python-embed.zip" (
        echo [!] ?????????????????????????????? Python 3.10+??
        exit /b 1
    )
    mkdir "%SCRIPT_DIR%tools\python312" 2>nul
    tar -xf "%SCRIPT_DIR%tools\python-embed.zip" -C "%SCRIPT_DIR%tools\python312"
    del "%SCRIPT_DIR%tools\python-embed.zip" >nul 2>nul
    powershell -NoProfile -Command "(Get-Content '%SCRIPT_DIR%tools\python312\python312._pth') -replace '#import site','import site' | Set-Content '%SCRIPT_DIR%tools\python312\python312._pth'"
    curl -sS -L -o "%SCRIPT_DIR%tools\get-pip.py" "https://bootstrap.pypa.io/get-pip.py"
    "%PYTHON%" "%SCRIPT_DIR%tools\get-pip.py" --no-warn-script-location -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
)

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo [!] Python ??????????????? Python 3.10+ ???????
    exit /b 1
)

"%PYTHON%" -c "import fastapi, uvicorn, sqlalchemy, openpyxl, fitz, docx, reportlab, matplotlib, httpx, multipart" >nul 2>nul
if errorlevel 1 (
    echo [>] ??????§µ??????????????2-5???????????????...
    "%PYTHON%" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-warn-script-location -r "%SCRIPT_DIR%backend\requirements.txt" --quiet
    if errorlevel 1 (
        echo [!] ?????????????????????????
        exit /b 1
    )
)
exit /b 0
