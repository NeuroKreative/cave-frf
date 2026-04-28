"""
PyInstaller entry point for the standalone bundle.

This wraps `streamlit run app.py` so it works inside a frozen executable,
where streamlit's normal CLI assumptions about __file__ paths don't hold.
"""
import os
import sys
from pathlib import Path

# When frozen, sys._MEIPASS is the bundle root; otherwise use the source dir.
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent.parent

APP_PATH = BUNDLE_DIR / 'app.py'

if not APP_PATH.exists():
    print(f"FATAL: app.py not found at {APP_PATH}")
    print("This bundle is broken. Falling back to the Python install path.")
    sys.exit(1)

# Make sure imports work
sys.path.insert(0, str(BUNDLE_DIR))

# Hand off to streamlit's CLI runner
from streamlit.web import cli as stcli
sys.argv = [
    'streamlit', 'run', str(APP_PATH),
    '--global.developmentMode=false',
    '--server.headless=false',
    '--browser.gatherUsageStats=false',
]
sys.exit(stcli.main())
