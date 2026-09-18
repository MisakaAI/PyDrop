# PyDrop

PyDrop is a lightweight LAN file-transfer tool for computers and phones.  
It starts a local web server, displays the access URL as a QR code,  
and lets you upload or download files from any browser on the same network.

[简体中文](README.zh-CN.md)

## Features

- QR code access with a simple Tkinter desktop GUI
- Copy the access URL and refresh the address and QR code after switching networks
- Upload files from a phone or another computer
- Browse and download files from the shared directory
- Open the shared directory from the desktop app
- Choose or change the shared directory from the desktop app
- Works across Windows, macOS, Linux, Android, and iOS browsers
- Uses `segno` to generate QR codes

## Requirements

- Python 3.13 or newer
- Tkinter
- [uv](https://docs.astral.sh/uv/) (optional, for dependency management)

Tkinter is included with most Python installations.  
On Debian/Ubuntu, install it with:

```bash
sudo apt install python3-tk
```

## Run from source

Create the project environment and install the locked dependencies:

```bash
uv sync
```

Start PyDrop:

```bash
uv run python main.py
```

Without uv, install `segno` into the active Python environment and run  
`python main.py` directly.

Connect the phone and computer to the same Wi-Fi network,  
then scan the QR code shown in the PyDrop window.  
You can also open the displayed URL manually.

The default port is `12450`.  
The default shared directory is the current user's `Downloads` folder (`~/Downloads`).  
You can choose a different existing directory with the **Choose shared directory**  
button in the desktop app.

## Build release executables

The build scripts prefer the project's `.venv` when it exists and otherwise use  
the system Python. They do not invoke uv or require a PyInstaller spec file.  
Before building, each script checks for PyInstaller, `segno`, and Pillow and  
prints a suitable `python -m pip install ...` command if anything is missing.  
The macOS script also checks for `dmgbuild`.

uv users can install the locked runtime, development, and build dependencies with:

```bash
uv sync --group build
```

Users without uv can install the build dependencies into their virtual environment  
or system Python directly:

```bash
python -m pip install pyinstaller segno pillow
```

Add `dmgbuild` to that command when building the macOS disk image.

Run the script for the target operating system:

| Platform | Command | Example release asset |
| --- | --- | --- |
| Linux | `./build_linux.sh` | `dist/PyDrop-v0.1.0-linux-x86_64` |
| Windows (cmd) | `build_windows.bat` | `dist\PyDrop-v0.1.0-windows-x86_64.exe` |
| macOS | `./build_macos_dmg.sh` | `dist/PyDrop-v0.1.0-macos-arm64.dmg` |

The version comes from `pyproject.toml`. Set `PYDROP_VERSION` before running a  
script to override it for a particular release. The architecture suffix is detected  
from the build machine. PyInstaller does not cross-compile, so build each asset on  
its target operating system and upload the files from `dist` to the corresponding GitHub Release.

## Notes

- Both devices must be on the same LAN, and the computer firewall must allow TCP port `12450` on the private/local network.
- PyDrop is intended for trusted local networks. It has no login or encryption layer.
- To change the port, edit `PORT` in `main.py` before running or building the application.

## Development

Format and lint the project with Ruff:

```bash
uv run ruff format .
uv run ruff check .
```

## Project layout

```text
.
├── main.py                 # Application and web server
├── favicon.ico             # Application icon
├── build_linux.sh          # Linux release build
├── build_macos_dmg.sh      # macOS DMG release build
├── build_windows.bat       # Windows release build
├── README.md
├── README.zh-CN.md
└── LICENSE                 # WTFPL v2
```

## License and copyright

Except for `favicon.ico`, the source code and other project contents are released under the [Do What The Fuck You Want To Public License v2 (WTFPL)](https://www.wtfpl.net/). See [LICENSE](LICENSE).

The copyright of `favicon.ico` belongs to [Bison仓鼠](https://space.bilibili.com/136107).  
The icon is not covered by the WTFPL.  
If there is any infringement, please submit an [issue](https://github.com/MisakaAI/PyDrop/issues),  
and we will delete it immediately upon seeing it.
