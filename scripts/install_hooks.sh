#!/usr/bin/env bash
# Installs the pre-commit hook so git refuses to commit subject data files.
# Run once, after cloning the repo:
#   bash scripts/install_hooks.sh

set -e
cd "$(dirname "$0")/.."

if [ ! -d .git ]; then
    echo "✗ Not in a git repository. Run this from the cave-frf folder after"
    echo "  you've run 'git init' or 'git clone'."
    exit 1
fi

git config core.hooksPath .githooks
chmod +x .githooks/pre-commit

echo "✓ Pre-commit hook installed."
echo "  Git will now refuse commits that contain subject data files."
echo "  To bypass in an emergency: git commit --no-verify"
