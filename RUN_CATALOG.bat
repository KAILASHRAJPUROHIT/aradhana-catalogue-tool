@echo off
REM ====== Aradhana Catalogue Tool - double-click to run ======
cd /d "%~dp0"

echo Checking Ollama (AI brain)...
ollama ps >nul 2>&1
if errorlevel 1 (
  echo   Ollama not running - starting it...
  start "" ollama serve
  timeout /t 4 >nul
)

echo.
echo ============================================
echo   ARADHANA CATALOGUE ENGINE
echo   input\  -^>  output_aradhana\
echo ============================================
echo.

"C:\Users\kaila\AppData\Local\Programs\Python\Python311\python.exe" aradhana_engine.py

echo.
echo Done. Opening the output folder...
start "" "%~dp0output_aradhana"
pause
