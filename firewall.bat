@echo off
REM firewall.bat - opens PeechaVisit ports in Windows Firewall
REM Right-click this file and choose "Run as administrator"
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Right-click firewall.bat and choose "Run as administrator".
    pause
    exit /b 1
)
for %%P in (5000 8000 8501 8502) do (
    netsh advfirewall firewall delete rule name="PeechaVisit %%P" >nul 2>&1
    netsh advfirewall firewall add rule name="PeechaVisit %%P" dir=in action=allow protocol=TCP localport=%%P
)
echo.
echo Ports 5000, 8000, 8501, 8502 are open.
pause
