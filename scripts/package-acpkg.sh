#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
VERSION=$(python3 -c "import json; print(json.load(open('$ROOT_DIR/manifest.json'))['version'])")
PKG_NAME="qgis-mcp-${VERSION}-windows-x64.acpkg"

echo "=== Packaging AiConnect QGIS Connector (.acpkg) ==="
mkdir -p "$DIST_DIR"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

# Core files
for f in manifest.json marketplace.json TUTORIAL.md LICENSE; do
    [ -f "$ROOT_DIR/$f" ] && cp "$ROOT_DIR/$f" "$STAGE_DIR/"
done

# Server code (qgis_mcp package)
mkdir -p "$STAGE_DIR/qgis_mcp"
cp -r "$ROOT_DIR/qgis_mcp/"* "$STAGE_DIR/qgis_mcp/"
find "$STAGE_DIR/qgis_mcp" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Plugin code
if [ -d "$ROOT_DIR/qgis_mcp_plugin" ]; then
    mkdir -p "$STAGE_DIR/qgis_mcp_plugin"
    cp -r "$ROOT_DIR/qgis_mcp_plugin/"* "$STAGE_DIR/qgis_mcp_plugin/"
    find "$STAGE_DIR/qgis_mcp_plugin" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
fi

# Assets
if [ -d "$ROOT_DIR/assets" ]; then
    mkdir -p "$STAGE_DIR/assets"
    cp -r "$ROOT_DIR/assets/"* "$STAGE_DIR/assets/" || true
fi

# Create .acpkg (ZIP archive, no pyc files)
(cd "$STAGE_DIR" && find . -name "*.pyc" -delete && zip -r "$DIST_DIR/$PKG_NAME" .)

echo "Package created at: $DIST_DIR/$PKG_NAME"
ls -lh "$DIST_DIR/$PKG_NAME"
