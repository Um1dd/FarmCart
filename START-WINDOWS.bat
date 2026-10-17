@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 scripts\run_local.py
) else (
    python scripts\run_local.py
)
if errorlevel 1 (
    echo.
    echo Install Python 3.12 or newer from python.org and enable Add Python to PATH.
    echo If the port is occupied, run: python scripts\run_local.py --port 8002
)
pause
