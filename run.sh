#!/usr/bin/env bash
# CAVE FRF launcher (macOS / Linux).
#
# Behavior:
#   1. Checks Python 3.10+ is installed.
#   2. Creates a project-local virtual environment (.venv/) if missing,
#      so we don't pollute the system Python.
#   3. Installs/updates dependencies inside the venv.
#   4. Launches the Streamlit UI.
#
# Re-running this script just launches the app; install only happens once.

set -e
cd "$(dirname "$0")"

VENV_DIR=".venv"
MIN_PY_MAJOR=3
MIN_PY_MINOR=10

print_box() {
    local msg="$1"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "  $msg"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
}

# -- Step 1: find a usable Python --
find_python() {
    for candidate in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            ver=$("$candidate" -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>/dev/null) || continue
            major=$(echo "$ver" | awk '{print $1}')
            minor=$(echo "$ver" | awk '{print $2}')
            if [ "$major" -gt "$MIN_PY_MAJOR" ] || \
               { [ "$major" -eq "$MIN_PY_MAJOR" ] && [ "$minor" -ge "$MIN_PY_MINOR" ]; }; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python) || {
    print_box "Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ not found"
    cat <<EOF
This pipeline needs Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR} or newer.

Easiest install:
  • Mac:    https://www.anaconda.com/download
            (or 'brew install python@3.12' if you use Homebrew)
  • Linux:  use your package manager, e.g.:
              sudo apt install python3.12 python3.12-venv  (Debian/Ubuntu)
              sudo dnf install python3.12                  (Fedora)

After installing, close this terminal, open a new one, and run ./run.sh
again. If you still see this message, Python is installed but not on your
PATH — see INSTALL.md for troubleshooting.
EOF
    exit 1
}
echo "✓ Using $PYTHON ($($PYTHON --version 2>&1))"

# -- Step 2: create / use project-local venv --
if [ ! -d "$VENV_DIR" ]; then
    echo "→ First-time setup: creating virtual environment in $VENV_DIR/"
    if ! "$PYTHON" -m venv "$VENV_DIR" 2>/tmp/cave_venv_err; then
        print_box "Could not create virtual environment"
        cat /tmp/cave_venv_err
        echo ""
        echo "On Debian/Ubuntu, you may need: sudo apt install python3-venv"
        exit 1
    fi
fi

# Activate venv-local Python
VENV_PY="$VENV_DIR/bin/python"
[ -x "$VENV_PY" ] || { echo "✗ venv broken at $VENV_DIR/ — delete it and re-run."; exit 1; }

# -- Step 3: install / update deps if needed --
if ! "$VENV_PY" -c "import streamlit, numpy, pandas, matplotlib" 2>/dev/null; then
    echo "→ Installing dependencies (one-time, takes ~1 minute)..."
    if ! "$VENV_PY" -m pip install --quiet --upgrade pip; then
        echo "✗ pip upgrade failed — check your internet connection."
        exit 1
    fi
    if ! "$VENV_PY" -m pip install --quiet -r requirements.txt; then
        print_box "Dependency install failed"
        echo "Check your internet connection and try again."
        echo "If the problem persists, try deleting .venv/ and re-running."
        exit 1
    fi
    echo "✓ Dependencies installed"
fi

# -- Step 4: launch --
print_box "Launching CAVE FRF UI in your browser"
echo "If the browser doesn't open automatically, go to: http://localhost:8501"
echo "To stop the app, close the browser tab and press Ctrl+C in this terminal."
echo ""

exec "$VENV_PY" -m streamlit run app.py
