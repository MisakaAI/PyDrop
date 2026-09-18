@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "PROJECT_DIR=%CD%"
set "DIST_DIR=%PROJECT_DIR%\dist"
set "BUILD_DIR=%PROJECT_DIR%\build\windows"

if exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"
    set "PYTHON_OPTION="
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
        set "PYTHON_OPTION="
    ) else (
        where py >nul 2>&1
        if errorlevel 1 (
            echo Error: Python was not found. Install Python 3.13 or newer first. 1>&2
            exit /b 1
        )
        set "PYTHON_EXE=py"
        set "PYTHON_OPTION=-3"
    )
)

set "MISSING_PACKAGES="
"!PYTHON_EXE!" !PYTHON_OPTION! -c "import PyInstaller" >nul 2>&1 || set "MISSING_PACKAGES=!MISSING_PACKAGES! pyinstaller"
"!PYTHON_EXE!" !PYTHON_OPTION! -c "import segno" >nul 2>&1 || set "MISSING_PACKAGES=!MISSING_PACKAGES! segno"
"!PYTHON_EXE!" !PYTHON_OPTION! -c "import PIL" >nul 2>&1 || set "MISSING_PACKAGES=!MISSING_PACKAGES! pillow"

if defined MISSING_PACKAGES (
    echo Error: the selected Python environment is missing build dependencies:!MISSING_PACKAGES! 1>&2
    echo Install them with: 1>&2
    echo   "!PYTHON_EXE!" !PYTHON_OPTION! -m pip install!MISSING_PACKAGES! 1>&2
    exit /b 1
)

if not defined PYDROP_VERSION (
    for /f "tokens=3" %%V in ('findstr /B /C:"version = " pyproject.toml') do set "PYDROP_VERSION=%%~V"
)
if not defined PYDROP_VERSION (
    echo Error: unable to read the project version from pyproject.toml. 1>&2
    exit /b 1
)

set "NATIVE_ARCH=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "NATIVE_ARCH=%PROCESSOR_ARCHITEW6432%"

if /I "!NATIVE_ARCH!"=="AMD64" (
    set "RELEASE_ARCH=x86_64"
) else if /I "!NATIVE_ARCH!"=="ARM64" (
    set "RELEASE_ARCH=arm64"
) else if /I "!NATIVE_ARCH!"=="x86" (
    set "RELEASE_ARCH=x86"
) else (
    set "RELEASE_ARCH=!NATIVE_ARCH!"
)

set "ARTIFACT_NAME=PyDrop-v!PYDROP_VERSION!-windows-!RELEASE_ARCH!"

if not exist "!DIST_DIR!" mkdir "!DIST_DIR!"
if not exist "!BUILD_DIR!" mkdir "!BUILD_DIR!"
set "PYINSTALLER_CONFIG_DIR=!BUILD_DIR!\pyinstaller-config"

"!PYTHON_EXE!" !PYTHON_OPTION! -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "!ARTIFACT_NAME!" ^
    --icon "!PROJECT_DIR!\favicon.ico" ^
    --add-data "!PROJECT_DIR!\favicon.ico;." ^
    --distpath "!DIST_DIR!" ^
    --workpath "!BUILD_DIR!\work" ^
    --specpath "!BUILD_DIR!" ^
    "!PROJECT_DIR!\main.py"

if errorlevel 1 exit /b !ERRORLEVEL!

echo Built: !DIST_DIR!\!ARTIFACT_NAME!.exe
exit /b 0
