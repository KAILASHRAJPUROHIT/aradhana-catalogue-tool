@echo off
REM ====== Auto Catalogue Tool — Aradhana Jewellers ======
cd /d "%~dp0"

REM Kill any running server
echo Stopping any running server...
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq app.py" >nul 2>&1
for /f "tokens=2" %%P in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2^>nul') do (
    wmic process where "ProcessId=%%~P AND CommandLine like '%%app.py%%'" delete >nul 2>&1
)
timeout /t 3 >nul

REM Clear Python cache
if exist __pycache__ rmdir /s /q __pycache__ >nul 2>&1

REM ── Create dedicated virtual desktop for catalogue Chromes ──────────────────
echo Setting up catalogue virtual desktop...
"C:\Users\kaila\AppData\Local\Programs\Python\Python311\python.exe" -c "import vdesk; vdesk.setup_catalogue_desktop(); print('Desktop ready')" 2>nul

REM ── ChatGPT Chrome (port 9222) — opens directly on chatgpt.com ──────────────
netstat -ano | findstr ":9222" | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    echo Starting ChatGPT Chrome (off-screen)...
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
        --remote-debugging-port=9222 ^
        --user-data-dir="C:\Users\kaila\AppData\Local\AutoCatalogueChrome" ^
        --no-first-run --no-default-browser-check ^
        --window-position=-32000,-32000 --window-size=1280,900 ^
        --homepage=https://chatgpt.com ^
        https://chatgpt.com
    timeout /t 4 >nul
) else (
    echo ChatGPT Chrome already running on 9222
)

REM ── Gemini Chrome (port 9223) — opens directly on gemini.google.com ─────────
netstat -ano | findstr ":9223" | findstr LISTENING >nul 2>&1
if errorlevel 1 (
    echo Starting Gemini Chrome (off-screen)...
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
        --remote-debugging-port=9223 ^
        --user-data-dir="C:\Users\kaila\AppData\Local\GeminiCatalogChrome" ^
        --no-first-run --no-default-browser-check ^
        --window-position=-32000,-32000 --window-size=1280,900 ^
        --homepage=https://gemini.google.com/app ^
        https://gemini.google.com/app
    timeout /t 4 >nul
) else (
    echo Gemini Chrome already running on 9223
)

REM ── Start Flask server ───────────────────────────────────────────────────────
echo Starting server...
powershell -WindowStyle Hidden -Command "Start-Process 'C:\Users\kaila\AppData\Local\Programs\Python\Python311\python.exe' -ArgumentList 'app.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"

timeout /t 6 >nul

REM Read port and open tool UI
set PORT=7654
if exist port.txt set /p PORT=<port.txt
start http://127.0.0.1:%PORT%
echo.
echo Tool open at http://127.0.0.1:%PORT%
echo ChatGPT Chrome: port 9222
echo Gemini Chrome:  port 9223
echo.
