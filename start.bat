@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo               Starting Text Compare Tool
echo ========================================================
echo.

:: Get Local IP Address
set "IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set "IP=%%a"
    :: Remove leading spaces
    for /f "tokens=* delims= " %%b in ("!IP!") do set "IP=%%b"
)

echo Access URLs:
echo   - Local:    http://localhost:5000
if defined IP (
    echo   - Network:  http://!IP!:5000
) else (
    echo   - Network:  (IP detection failed, please check ipconfig)
)
echo.
echo ========================================================
echo.

:: Check if virtual environment exists and activate it
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: Run the application
python app.py

pause