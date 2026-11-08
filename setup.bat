@echo off
REM setup.bat - PeechaVisit one-time setup (run once, and again after each update)
cd /d "%~dp0"

set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY (py -3 --version >nul 2>&1 && set "PY=py -3")
if not defined PY (
    echo [ERROR] Python is not installed.
    echo Install Python 3.12 from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during install. Then run setup.bat again.
    pause
    exit /b 1
)
echo Python found:
%PY% --version

if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv ...
    %PY% -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Could not create .venv
    pause
    exit /b 1
)

echo Installing packages - this needs internet and takes a few minutes ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package install failed. Check the internet connection and run setup.bat again.
    pause
    exit /b 1
)

echo.
echo ===============================================
echo   Setup finished. Now double-click start.bat
echo ===============================================
pause
