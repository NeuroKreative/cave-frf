@echo off
REM CAVE FRF launcher (Windows). Uses the py launcher exclusively.

setlocal
cd /d "%~dp0"

REM Verify py launcher is installed and finds Python 3.10+
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo =====================================================================
    echo   Python 3 not found via the 'py' launcher
    echo =====================================================================
    echo.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo Be sure to check "Add python.exe to PATH" during install.
    echo Do NOT install from the Microsoft Store.
    echo.
    pause
    exit /b 1
)

py -3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo =====================================================================
    echo   Python is installed but too old
    echo =====================================================================
    py -3 --version
    echo Need Python 3.10 or newer. Install a newer version from python.org.
    pause
    exit /b 1
)

echo Using:
py -3 --version
echo.

REM Create venv if missing
if not exist ".venv\Scripts\python.exe" (
    echo First-time setup: creating virtual environment in .venv\
    py -3 -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
)

REM Install dependencies if needed
.venv\Scripts\python.exe -c "import streamlit, numpy, pandas, matplotlib" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies, please wait ^(about 1 minute^)...
    .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Dependency install failed.
        echo Check your internet connection. If the problem persists, delete the
        echo .venv folder and run this script again.
        pause
        exit /b 1
    )
    echo Dependencies installed.
)

echo.
echo =====================================================================
echo   Launching CAVE FRF UI
echo =====================================================================
echo If the browser doesn't open automatically, visit:
echo     http://localhost:8501
echo.
echo To stop: close the browser tab and close this window.
echo.

.venv\Scripts\python.exe -m streamlit run app.py
pause
