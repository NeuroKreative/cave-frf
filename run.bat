@echo off
REM CAVE FRF launcher (Windows).
REM
REM Detection strategy:
REM   1. Try the 'py' Python Launcher (shipped with python.org installers,
REM      not affected by the Microsoft Store alias quirk).
REM   2. Fall back to plain 'python', verifying it's a real install rather
REM      than the Microsoft Store placeholder.
REM   3. Tell the user clearly what's wrong, including the MS Store gotcha.

setlocal enabledelayedexpansion
cd /d "%~dp0"

set VENV_DIR=.venv
set PYTHON_CMD=

REM === Try 'py -3' first (the official Windows Python Launcher) ===
py -3 -c "print(1)" >nul 2>&1
if !errorlevel! equ 0 (
    REM py works — check it's 3.10+
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 99)" >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=py -3
        goto :found
    )
    REM py works but version is too old
    set OLD_VERSION_FOUND=1
)

REM === Try 'python' ===
REM We can't trust 'where python' on Windows — the Microsoft Store stub
REM exists at a fake path that makes 'where' succeed but the command
REM doesn't actually run Python. Test by running real Python code.
set PY_TEST=
for /f "delims=" %%i in ('python -c "print(42)" 2^>nul') do set PY_TEST=%%i
if "!PY_TEST!"=="42" (
    REM Real Python — check version
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 99)" >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=python
        goto :found
    )
    set OLD_VERSION_FOUND=1
)

REM === Nothing worked ===
if defined OLD_VERSION_FOUND goto :too_old
goto :no_python


:no_python
echo.
echo =====================================================================
echo   Python 3.10+ is not installed
echo =====================================================================
echo.
echo If you just saw a message like:
echo     "Python was not found; run without arguments to install from the
echo      Microsoft Store"
echo that is the Windows PLACEHOLDER, not real Python. It is a common
echo source of confusion on fresh Windows installs.
echo.
echo Fix:
echo.
echo   1. Open https://www.python.org/downloads/ in a browser
echo      (do NOT use the Microsoft Store version)
echo.
echo   2. Click the big yellow "Download Python 3.x.x" button.
echo.
echo   3. Run the installer.
echo      *** IMPORTANT: at the BOTTOM of the first install screen, CHECK
echo          the box "Add python.exe to PATH" ***
echo      Without this checkbox, the launcher cannot find Python.
echo.
echo   4. Click "Install Now" and wait for it to finish.
echo.
echo   5. CLOSE this window.
echo      Open a NEW PowerShell or Command Prompt.
echo      Run run.bat again.
echo.
echo If you have already installed Python and still see this error, see
echo INSTALL.md for troubleshooting (most likely the "Add to PATH" box was
echo missed during install).
echo.
pause
exit /b 1


:too_old
echo.
echo =====================================================================
echo   Python is installed but version is too old
echo =====================================================================
echo.
py -3 --version 2>nul
python --version 2>nul
echo.
echo This pipeline needs Python 3.10 or newer.
echo.
echo Install a newer version from https://www.python.org/downloads/
echo Make sure to check "Add python.exe to PATH" during install.
echo.
pause
exit /b 1


:found
echo Using:
%PYTHON_CMD% --version
echo.

REM === Step 2: create venv if missing ===
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo First-time setup: creating virtual environment in %VENV_DIR%\
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo.
        echo ERROR: Could not create virtual environment.
        echo If you installed Python from the Microsoft Store, that's the
        echo problem -- uninstall it and install from python.org instead.
        pause
        exit /b 1
    )
)

set VENV_PY=%VENV_DIR%\Scripts\python.exe

REM === Step 3: install deps if needed ===
"%VENV_PY%" -c "import streamlit, numpy, pandas, matplotlib" >nul 2>&1
if !errorlevel! neq 0 (
    echo Installing dependencies, please wait ^(takes ~1 minute^)...
    "%VENV_PY%" -m pip install --quiet --upgrade pip
    "%VENV_PY%" -m pip install --quiet -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo ERROR: Dependency install failed.
        echo Check your internet connection. If problem persists, delete the
        echo %VENV_DIR%\ folder and run this script again.
        pause
        exit /b 1
    )
    echo Dependencies installed.
)

REM === Step 4: launch ===
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
