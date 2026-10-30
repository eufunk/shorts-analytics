@echo off
rem Startet das Shorts-Analytics Control Panel und oeffnet es im Browser.
rem Laeuft der Server bereits, wird nur der Browser geoeffnet.
rem Der Server laeuft in einem minimierten Fenster - Fenster schliessen beendet ihn.
setlocal
set PORT=8502
set URL=http://localhost:%PORT%
cd /d "%~dp0"

"%SystemRoot%\System32\curl.exe" -s -f -o nul %URL%/_stcore/health && goto open

if not exist ".venv\Scripts\python.exe" (
    echo Die virtuelle Umgebung .venv wurde nicht gefunden. Siehe README, Abschnitt "Setup".
    pause
    exit /b 1
)

echo Shorts Analytics wird gestartet ...
start "Shorts Analytics Server - Fenster schliessen beendet den Server" /min ".venv\Scripts\python.exe" -m streamlit run dashboard\app.py --server.port %PORT% --server.headless true --browser.gatherUsageStats false

for /l %%i in (1,1,60) do (
    "%SystemRoot%\System32\timeout.exe" /t 1 /nobreak >nul
    "%SystemRoot%\System32\curl.exe" -s -f -o nul %URL%/_stcore/health && goto open
)
echo Der Server war nach 60 Sekunden nicht erreichbar. Details im minimierten Server-Fenster.
pause
exit /b 1

:open
start "" "%URL%"
endlocal
