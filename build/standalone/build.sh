#!/usr/bin/env bash
# Convenience wrapper around the PyInstaller build.
# See build/standalone/README.md for the full story.

set -e
cd "$(dirname "$0")/../.."

echo "→ Building standalone CAVE FRF executable..."
echo "  This will take 5-15 minutes."
echo "  Output: dist/CAVE_FRF/"
echo ""

if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "→ PyInstaller not installed. Installing..."
    pip install pyinstaller
fi

rm -rf dist build/work

pyinstaller build/standalone/cave_frf.spec \
    --noconfirm \
    --workpath build/work \
    --distpath dist

echo ""
echo "✓ Build complete."
echo "  Test with: ./dist/CAVE_FRF/CAVE_FRF"
echo ""
echo "  To distribute: zip the entire dist/CAVE_FRF/ folder."
