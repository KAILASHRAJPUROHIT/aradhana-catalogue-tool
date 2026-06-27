@echo off
title Aradhana Catalogue Watcher
echo =============================================
echo  ARADHANA CATALOGUE WATCHER
echo  Drop photos here: JewelleryCatalogTool\drop\
echo  1st photo = jewellery  |  2nd photo = tag
echo  Processed tiles appear in: output_aradhana\
echo =============================================
echo.

REM Start Ollama if not running
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if errorlevel 1 (
    echo Starting Ollama...
    start /B "" ollama serve
    timeout /t 5 /nobreak >NUL
)

echo Watcher running... Press Ctrl+C to stop.
echo.
"C:\Users\kaila\AppData\Local\Programs\Python\Python311\python.exe" watcher.py
pause
