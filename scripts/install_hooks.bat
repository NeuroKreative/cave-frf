@echo off
REM Installs the pre-commit hook so git refuses to commit subject data files.
REM Run once, after cloning the repo:
REM    scripts\install_hooks.bat

cd /d "%~dp0\.."

if not exist .git (
    echo ERROR: Not in a git repository. Run this from the cave-frf folder
    echo        after you've run 'git init' or 'git clone'.
    pause
    exit /b 1
)

git config core.hooksPath .githooks

echo Pre-commit hook installed.
echo Git will refuse commits containing subject data files.
echo To bypass in an emergency: git commit --no-verify
pause
