#!/bin/sh
# Install from the source checkout (alternative to double-clicking dist/cam4linux.pyz)
cd "$(dirname "$0")" && exec python3 -m cam4linux --install
