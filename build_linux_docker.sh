#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_IMAGE="python:3.14-slim-bookworm"
APT_MIRROR="https://mirrors.cernet.edu.cn/debian/"
APT_SECURITY_MIRROR="https://mirrors.cernet.edu.cn/debian-security/"
PYPI_MIRROR="https://mirrors.cernet.edu.cn/pypi/web/simple"

if ! command -v docker >/dev/null 2>&1; then
    printf 'Error: Docker was not found. Install and start Docker first.\n' >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    printf 'Error: Docker is not running or is not accessible.\n' >&2
    exit 1
fi

docker run \
    --rm \
    --pull=always \
    --env DEBIAN_FRONTEND=noninteractive \
    --env HOST_UID="$(id -u)" \
    --env HOST_GID="$(id -g)" \
    --env PYDROP_VERSION="${PYDROP_VERSION:-}" \
    --env APT_MIRROR="$APT_MIRROR" \
    --env APT_SECURITY_MIRROR="$APT_SECURITY_MIRROR" \
    --env PYPI_MIRROR="$PYPI_MIRROR" \
    --volume "$PROJECT_DIR:/workspace" \
    --workdir /workspace \
    "$PYTHON_IMAGE" \
    bash -euo pipefail -c '
        # The minimal image may not contain TLS root certificates yet.
        # Bootstrap that package from the image default sources before enabling
        # the requested HTTPS mirror.
        if [[ ! -s /etc/ssl/certs/ca-certificates.crt ]]; then
            apt-get update
            apt-get install --yes --no-install-recommends ca-certificates
        fi

        if [[ -f /etc/apt/sources.list.d/debian.sources ]]; then
            mv /etc/apt/sources.list.d/debian.sources \
                /etc/apt/sources.list.d/debian.sources.disabled
        fi
        printf "%s\n" \
            "deb ${APT_MIRROR} bookworm main contrib non-free non-free-firmware" \
            "deb ${APT_MIRROR} bookworm-updates main contrib non-free non-free-firmware" \
            "deb ${APT_MIRROR} bookworm-backports main contrib non-free non-free-firmware" \
            "deb ${APT_SECURITY_MIRROR} bookworm-security main contrib non-free non-free-firmware" \
            > /etc/apt/sources.list

        apt-get update
        apt-get upgrade --yes
        apt-get install --yes --no-install-recommends \
            binutils

        python -m pip install \
            --index-url "$PYPI_MIRROR" \
            --upgrade pip
        python -m pip install \
            --index-url "$PYPI_MIRROR" \
            --upgrade \
            pillow \
            pyinstaller \
            segno

        if [[ -z "$PYDROP_VERSION" ]]; then
            PYDROP_VERSION="$(
                sed -n '\''/^\[project\]/,/^\[/s/^version = "\([^"]*\)"/\1/p'\'' \
                    pyproject.toml | head -n 1
            )"
        fi

        if [[ -z "$PYDROP_VERSION" ]]; then
            printf "Error: unable to read the project version.\n" >&2
            exit 1
        fi

        case "$(uname -m)" in
            x86_64|amd64) RELEASE_ARCH="x86_64" ;;
            aarch64|arm64) RELEASE_ARCH="arm64" ;;
            i386|i486|i586|i686) RELEASE_ARCH="x86" ;;
            *) RELEASE_ARCH="$(uname -m)" ;;
        esac

        ARTIFACT_NAME="PyDrop-v${PYDROP_VERSION}-linux-${RELEASE_ARCH}"
        DIST_DIR="/workspace/dist"
        BUILD_DIR="/workspace/build/linux"

        restore_ownership() {
            chown -R "${HOST_UID}:${HOST_GID}" "$DIST_DIR" "$BUILD_DIR" \
                2>/dev/null || true
        }
        trap restore_ownership EXIT

        mkdir -p "$DIST_DIR" "$BUILD_DIR"
        PYINSTALLER_CONFIG_DIR="$BUILD_DIR/pyinstaller-config" \
            python -m PyInstaller \
            --clean \
            --noconfirm \
            --onefile \
            --windowed \
            --name "$ARTIFACT_NAME" \
            --icon /workspace/favicon.ico \
            --add-data /workspace/favicon.ico:. \
            --distpath "$DIST_DIR" \
            --workpath "$BUILD_DIR/work" \
            --specpath "$BUILD_DIR" \
            /workspace/main.py

        printf "Built: %s/%s\n" "$DIST_DIR" "$ARTIFACT_NAME"
    '
