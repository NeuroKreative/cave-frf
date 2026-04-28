# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for CAVE FRF standalone bundle.

Build with:
    cd cave-frf
    pyinstaller build/standalone/cave_frf.spec --noconfirm

Output appears in dist/CAVE_FRF/.

EXPERIMENTAL — the supported install path is the Python+launcher route
described in README.md. Streamlit + PyInstaller is fragile.
"""
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_all, collect_data_files, collect_submodules
)

# Project root, relative to this spec file
PROJECT_ROOT = Path(SPECPATH).parent.parent

# Collect all of Streamlit's runtime files (templates, static assets, etc.)
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all('streamlit')
altair_datas, altair_binaries, altair_hiddenimports = collect_all('altair')

# Bundle the source files of our package and the app
extra_datas = [
    (str(PROJECT_ROOT / 'app.py'), '.'),
    (str(PROJECT_ROOT / 'cave_frf'), 'cave_frf'),
    (str(PROJECT_ROOT / 'Updated-_CAVE_Adult_Stimulus_Factor_Trial.txt'), '.'),
]

hiddenimports = list(set(
    streamlit_hiddenimports + altair_hiddenimports + [
        'cave_frf',
        'cave_frf.analysis',
        'cave_frf.plots',
        'pkg_resources.py2_warn',
    ] + collect_submodules('cave_frf')
))

a = Analysis(
    [str(PROJECT_ROOT / 'build' / 'standalone' / 'launcher_main.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=streamlit_binaries + altair_binaries,
    datas=streamlit_datas + altair_datas + extra_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CAVE_FRF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CAVE_FRF',
)
