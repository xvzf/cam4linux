#!/bin/sh
# Builds dist/cam4linux.pyz - a single executable file. Double-click it in the
# file manager: it installs itself for the current user (asks once for the admin
# password to set up device access) and starts the app.
set -e
cd "$(dirname "$0")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -r cam4linux "$STAGE/"
find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
cp packaging/bundle_main.py "$STAGE/__main__.py"
mkdir -p dist
python3 -m zipapp "$STAGE" -o dist/cam4linux.pyz -p "/usr/bin/env python3" -c
chmod +x dist/cam4linux.pyz
echo "dist/cam4linux.pyz ($(du -h dist/cam4linux.pyz | cut -f1))"
