@echo off
REM start.bat - PeechaVisit: starts API, web app, dashboard and admin panel
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup.bat first.
    pause
    exit /b 1
)

REM the installed version (Windows service) already runs everything - two copies would fight over the ports
sc query PeechaVisit 2>nul | find "RUNNING" >nul
if not errorlevel 1 (
    echo [!] The installed PeechaVisit service is running on this computer.
    echo     start.bat is not needed. Use the desktop shortcuts, or stop the service first:
    echo     "C:\Program Files\PeechaVisit\PeechaVisitService.exe" stop
    pause
    exit /b 1
)

REM close windows left from a previous start, so old code never keeps running
taskkill /FI "WINDOWTITLE eq PeechaVisit*" /T /F >nul 2>&1
timeout /t 2 >nul

REM one window runs everything (API, web app, dashboard, admin panel); a crashed part restarts,
REM and changing database/network settings in the admin panel restarts all parts automatically
start "PeechaVisit Server - do not close" cmd /k .venv\Scripts\python.exe peecha_server.py

echo.
echo ===============================================
echo   The "PeechaVisit Server" window was opened. Do NOT close it.
echo.
echo   Dashboard : http://localhost:8501
echo   Admin     : http://localhost:8502
echo   API test  : http://localhost:5000
echo.
echo   IP of this computer - type it in the Android app:
ipconfig | findstr /c:"IPv4"
echo ===============================================
timeout /t 8 >nul
start "" http://localhost:8502
start "" http://localhost:8501
pause
