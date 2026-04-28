@echo off
REM CAVE FRF launcher (Windows).
REM
REM Behavior:
REM   1. Checks Python 3.10+ is installed.
REM   2. Creates a project-local virtual environment (.venv\) if missing.
REM   3. Installs/updates dependencies inside the venv.
REM   4. Launches the Streamlit UI.

setlocal
cd /d "%~dp0"

set VENV_DIR=.venv

REM -- Step 1: find a usable Python --
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo =====================================================================
    echo   Python not found
    echo =====================================================================
    echo.
    echo This pipeline needs Python 3.10 or newer.
    echo.
    echo Install from:  https://www.python.org/downloads/
    echo During install, MAKE SURE to check "Add Python to PATH".
    echo.
    echo Or install Anaconda:  https://www.anaconda.com/download
    echo.
    echo After installing, close this window, open a new one, and run
    echo run.bat again.
    echo.
    pause
    exit /b 1
)

REM Verify version is at least 3.10
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo =====================================================================
    echo   Python is too old
    echo =====================================================================
    echo.
    python --version
    echo.
    echo This pipeline needs Python 3.10 or newer.
    echo Please install a newer version from python.org and try again.
    echo.
    pause
    exit /b 1
)
for /f %%v in ('python --version 2^>^&1') do echo Using %%v %%w

REM -- Step 2: create venv if missing --
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo First-time setup: creating virtual environment in %VENV_DIR%\
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        echo If on Windows Store Python, try installing python.org Python instead.
        pause
        exit /b 1
    )
)

set VENV_PY=%VENV_DIR%\Scripts\python.exe

REM -- Step 3: install deps if needed --
"%VENV_PY%" -c "import streamlit, numpy, pandas, matplotlib" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies, please wait ^(takes ~1 minute^)...
    "%VENV_PY%" -m pip install --quiet --upgrade pip
    "%VENV_PY%" -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Dependency install failed.
        echo Check your internet connection. If problem persists, delete the
        echo %VENV_DIR%\ folder and run this script again.
        pause
        exit /b 1
    )
    echo Dependencies installed.
)

REM -- Step 4: launch --
echo.
echo =====================================================================
echo   Launching CAVE FRF UI
echo =====================================================================
echo If the browser doesn't open automatically, visit:
echo     http://localhost:8501
echo.
echo To stop: close the browser tab and close this window.
echo.

"%VENV_PY%" -m streamlit run app.py
pause
