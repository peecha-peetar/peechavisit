@echo off
REM start.bat - PeechaVisit: starts API, web app, dashboard and admin panel
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup.bat first.
    pause
    exit /b 1
)

start "PeechaVisit API - port 5000" cmd /k .venv\Scripts\python.exe app.py
start "PeechaVisit Web App - port 8000" cmd /k .venv\Scripts\python.exe run_client.py
start "PeechaVisit Dashboard - port 8501" cmd /k .venv\Scripts\python.exe -m streamlit run dashboard.py --server.port 8501
start "PeechaVisit Admin - port 8502" cmd /k .venv\Scripts\python.exe -m streamlit run admin.py --server.port 8502

echo.
echo ===============================================
echo   4 windows were opened. Do NOT close them.
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
