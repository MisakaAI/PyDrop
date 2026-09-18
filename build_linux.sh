#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build/linux"

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON="$(command -v python)"
else
    printf 'Error: Python was not found. Install Python 3.13 or newer first.\n' >&2
    exit 1
fi

missing_packages=()
for dependency in \
    "PyInstaller:pyinstaller" \
    "segno:segno" \
    "PIL:pillow"
do
    module="${dependency%%:*}"
    package="${dependency#*:}"
    if ! "$PYTHON" -c "import $module" >/dev/null 2>&1; then
        missing_packages+=("$package")
    fi
done

if (( ${#missing_packages[@]} > 0 )); then
    printf 'Error: the selected Python environment is missing build dependencies:' >&2
    printf ' %s' "${missing_packages[@]}" >&2
    printf '\nInstall them with:\n  %q -m pip install' "$PYTHON" >&2
    printf ' %s' "${missing_packages[@]}" >&2
    printf '\n' >&2
    exit 1
fi

if [[ -z "${PYDROP_VERSION:-}" ]]; then
    PYDROP_VERSION="$("$PYTHON" -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
fi

case "$(uname -m)" in
    x86_64|amd64) RELEASE_ARCH="x86_64" ;;
    aarch64|arm64) RELEASE_ARCH="arm64" ;;
    i386|i486|i586|i686) RELEASE_ARCH="x86" ;;
    *) RELEASE_ARCH="$(uname -m)" ;;
esac

ARTIFACT_NAME="PyDrop-v${PYDROP_VERSION}-linux-${RELEASE_ARCH}"

cd "$PROJECT_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

PYINSTALLER_CONFIG_DIR="$BUILD_DIR/pyinstaller-config" \
    "$PYTHON" -m PyInstaller \
    --clean \
    --noconfirm \
    --onefile \
    --windowed \
    --name "$ARTIFACT_NAME" \
    --icon "$PROJECT_DIR/favicon.ico" \
    --add-data "$PROJECT_DIR/favicon.ico:." \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR/work" \
    --specpath "$BUILD_DIR" \
    "$PROJECT_DIR/main.py"

printf 'Built: %s/%s\n' "$DIST_DIR" "$ARTIFACT_NAME"
