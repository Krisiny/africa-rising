@echo off
rem Double-click to start Africa Rising.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 main.py %*
) else (
    python main.py %*
)
if errorlevel 1 (
    echo.
    echo The game could not start. Did you install it? Run this once:
    echo     python -m pip install -r requirements.txt
    pause
)
