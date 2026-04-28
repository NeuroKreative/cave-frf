#!/usr/bin/env bash
# CAVE FRF launcher (macOS / Linux).

set -e
cd "$(dirname "$0")"

VENV_DIR=".venv"

# Find a usable Python 3.10+
find_python() {
    for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            ver=$("$candidate" -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>/dev/null) || continue
            major=$(echo "$ver" | awk '{print $1}')
            minor=$(echo "$ver" | awk '{print $2}')
            if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python) || {
    cat <<EOF

═══════════════════════════════════════════════════════════════════
  Python 3.10+ not found
═══════════════════════════════════════════════════════════════════

Install from:
  • Mac:    https://www.anaconda.com/download
            (or 'brew install python@3.12')
  • Linux:  use your package manager:
              sudo apt install python3.12 python3.12-venv  (Debian/Ubuntu)
              sudo dnf install python3.12                  (Fedora)
EOF
    exit 1
}
echo "Using: $($PYTHON --version)"

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    echo "First-time setup: creating virtual environment in $VENV_DIR/"
    "$PYTHON" -m venv "$VENV_DIR" || {
        echo "Could not create venv. On Debian/Ubuntu try: sudo apt install python3-venv"
        exit 1
    }
fi

VENV_PY="$VENV_DIR/bin/python"

# Install deps if needed
if ! "$VENV_PY" -c "import streamlit, numpy, pandas, matplotlib" 2>/dev/null; then
    echo "Installing dependencies (~1 minute)..."
    "$VENV_PY" -m pip install --quiet --upgrade pip
    "$VENV_PY" -m pip install --quiet -r requirements.txt
    echo "Dependencies installed."
fi

# Suppress Streamlit's first-run email prompt
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
    mkdir -p "$HOME/.streamlit"
    cat > "$HOME/.streamlit/credentials.toml" <<'TOML'
[general]
email = ""
TOML
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Launching CAVE FRF UI"
echo "═══════════════════════════════════════════════════════════════════"
echo "If the browser doesn't open automatically: http://localhost:8501"
echo "To stop: close the browser tab and Ctrl+C in this terminal."
echo ""

exec "$VENV_PY" -m streamlit run app.py
