#!/bin/bash
# Build Meowdoku.app and a zip of it for sharing. See README, "Sharing as a Mac app".
#
# Run from anywhere, after: python -m pip install -e ".[build]"
# The app runs on Macs with the same chip type as the Mac that built it;
# an Intel build also runs on Apple-chip Macs through Rosetta.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
ARCH="$(uname -m)"

"$PYTHON" packaging/make_icon.py "$ROOT/build/Meowdoku.icns"

"$PYTHON" -m PyInstaller \
    --noconfirm --clean --windowed \
    --name Meowdoku \
    --icon "$ROOT/build/Meowdoku.icns" \
    --osx-bundle-identifier local.meowdoku.app \
    --paths "$ROOT/src" \
    --specpath "$ROOT/build" \
    --workpath "$ROOT/build/pyinstaller" \
    --distpath "$ROOT/dist" \
    packaging/app.py

# The zip unpacks to a "Meowdoku" folder holding the app and short instructions.
SHARE="$ROOT/build/share/Meowdoku"
rm -rf "$ROOT/build/share"
mkdir -p "$SHARE"
ditto dist/Meowdoku.app "$SHARE/Meowdoku.app"
cp "packaging/How to open Meowdoku.txt" "$SHARE/"

ZIP="dist/Meowdoku-mac-$ARCH.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$SHARE" "$ZIP"
echo "Built dist/Meowdoku.app and $ZIP"
