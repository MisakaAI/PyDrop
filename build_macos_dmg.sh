#!/bin/zsh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pydrop-build.XXXXXX")"

cleanup() {
    rm -rf "$BUILD_ROOT"
}
trap cleanup EXIT

cd "$PROJECT_DIR"

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON="$(command -v python)"
else
    print -u2 "错误：未找到 Python，请先安装 Python 3.13 或更高版本。"
    exit 1
fi

missing_packages=()
for dependency in \
    "PyInstaller:pyinstaller" \
    "segno:segno" \
    "PIL:pillow" \
    "dmgbuild:dmgbuild"
do
    module="${dependency%%:*}"
    package="${dependency#*:}"
    if ! "$PYTHON" -c "import $module" >/dev/null 2>&1; then
        missing_packages+=("$package")
    fi
done

if (( ${#missing_packages[@]} > 0 )); then
    print -nu2 "错误：当前 Python 环境缺少构建依赖："
    print -u2 "${(j: :)missing_packages}"
    print -u2 "请安装："
    print -nu2 "  ${(q)PYTHON} -m pip install "
    print -u2 "${(j: :)missing_packages}"
    exit 1
fi

if [[ -z "${PYDROP_VERSION:-}" ]]; then
    PYDROP_VERSION="$("$PYTHON" -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
fi

case "$(uname -m)" in
    arm64|aarch64) RELEASE_ARCH="arm64" ;;
    x86_64|amd64) RELEASE_ARCH="x86_64" ;;
    *) RELEASE_ARCH="$(uname -m)" ;;
esac

DMG_PATH="$DIST_DIR/PyDrop-v${PYDROP_VERSION}-macos-${RELEASE_ARCH}.dmg"

env \
    PYINSTALLER_CONFIG_DIR="$BUILD_ROOT/pyinstaller-config" \
    "$PYTHON" -m PyInstaller \
        --clean \
        --noconfirm \
        --onefile \
        --windowed \
        --name "PyDrop" \
        --icon "$PROJECT_DIR/favicon.ico" \
        --add-data "$PROJECT_DIR/favicon.ico:." \
        --osx-bundle-identifier "cn.misaka.pydrop" \
        --target-architecture "$RELEASE_ARCH" \
        --distpath "$DIST_DIR" \
        --workpath "$BUILD_ROOT/pyinstaller-work" \
        --specpath "$BUILD_ROOT" \
        "$PROJECT_DIR/main.py"

APP_EXECUTABLE="$DIST_DIR/PyDrop.app/Contents/MacOS/PyDrop"
if [[ " $(lipo -archs "$APP_EXECUTABLE") " != *" $RELEASE_ARCH "* ]]; then
    print -u2 "错误：PyDrop.app 不是 $RELEASE_ARCH 架构。"
    exit 1
fi

rm -f "$DMG_PATH"
"$PYTHON" - \
        "$DIST_DIR/PyDrop.app" \
        "$DMG_PATH" <<'PYTHON'
import sys

from dmgbuild import build_dmg

app_path, dmg_path = sys.argv[1:]
build_dmg(
    filename=dmg_path,
    volume_name="PyDrop",
    settings={
        "files": [app_path],
        "symlinks": {"Applications": "/Applications"},
        "window_rect": ((100, 100), (600, 400)),
        "default_view": "icon-view",
        "show_toolbar": False,
        "show_status_bar": False,
        "show_pathbar": False,
        "show_sidebar": False,
        "arrange_by": None,
        "icon_size": 96,
        "text_size": 14,
        "icon_locations": {
            "PyDrop.app": (160, 190),
            "Applications": (440, 190),
        },
        "format": "UDZO",
        "compression_level": 9,
    },
)
PYTHON

print "已生成：$DMG_PATH"
