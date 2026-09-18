#!/bin/zsh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
PYDROP_VERSION="${PYDROP_VERSION:-0.1.2}"
DMG_PATH="$DIST_DIR/PyDrop-v${PYDROP_VERSION}-macos-arm64.dmg"
BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pydrop-build.XXXXXX")"

cleanup() {
    rm -rf "$BUILD_ROOT"
}
trap cleanup EXIT

cd "$PROJECT_DIR"

env \
    PYDROP_VERSION="$PYDROP_VERSION" \
    PYINSTALLER_CONFIG_DIR="$BUILD_ROOT/pyinstaller-config" \
    UV_CACHE_DIR="$BUILD_ROOT/uv-cache" \
    uv run --with pyinstaller pyinstaller --clean --noconfirm PyDrop.spec

APP_EXECUTABLE="$DIST_DIR/PyDrop.app/Contents/MacOS/PyDrop"
if [[ "$(lipo -archs "$APP_EXECUTABLE")" != "arm64" ]]; then
    print -u2 "错误：PyDrop.app 不是 arm64 架构。"
    exit 1
fi

DMG_SOURCE="$BUILD_ROOT/PyDrop"
mkdir -p "$DMG_SOURCE"
ditto "$DIST_DIR/PyDrop.app" "$DMG_SOURCE/PyDrop.app"
ln -s /Applications "$DMG_SOURCE/Applications"

rm -f "$DMG_PATH"
diskutil image create from \
    --format UDZO \
    "$DMG_SOURCE" \
    "$DMG_PATH"

print "已生成：$DMG_PATH"
