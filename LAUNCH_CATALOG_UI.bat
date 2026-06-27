@echo off
REM ====== Auto Catalogue Tool — Aradhana Jewellers ======
cd /d "%~dp0"

REM Kill ALL python processes running app.py (clean slate)
echo Stopping any running server...
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq app.py" >nul 2>&1
for /f "tokens=2" %%P in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2^>nul') do (
    wmic process where "ProcessId=%%~P AND CommandLine like '%%app.py%%'" delete >nul 2>&1
)
timeout /t 3 >nul

REM Clear Python cache
if exist __pycache__ rmdir /s /q __pycache__ >nul 2>&1

REM Start Chrome with remote debugging if not already running
netstat -ano | findstr ":9222" | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    echo Starting Chrome...
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
        --remote-debugging-port=9222 ^
        --user-data-dir="C:\Users\kaila\AppData\Local\AutoCatalogueChrome" ^
        --no-first-run --no-default-browser-check
    timeout /t 5 >nul
)

REM Start server hidden — writes PORT to port.txt so we know where to open
echo Starting server...
powershell -WindowStyle Hidden -Command "Start-Process 'C:\Users\kaila\AppData\Local\Programs\Python\Python311\python.exe' -ArgumentList 'app.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"

REM Wait for Flask to bind
timeout /t 6 >nul

REM Read port from port.txt and open browser
set PORT=7654
if exist port.txt set /p PORT=<port.txt
start http://127.0.0.1:%PORT%
echo.
echo Tool open at http://127.0.0.1:%PORT%
echo.
