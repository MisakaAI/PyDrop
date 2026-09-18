# PyDrop

PyDrop is a lightweight LAN file-transfer tool for computers and phones. It starts a local web server, displays the access URL as a QR code, and lets you upload or download files from any browser on the same network.

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
- [uv](https://docs.astral.sh/uv/)
- Tkinter

Tkinter is included with most Python installations. On Debian/Ubuntu, install it with:

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

Connect the phone and computer to the same Wi-Fi network, then scan the QR code shown in the PyDrop window. You can also open the displayed URL manually.

The default port is `12450`. The default shared directory is `shared` next to the script. You can choose a different existing directory with the **Choose shared directory** button in the desktop app.

## Build a single executable

Run PyInstaller in the project environment so it can access PyDrop's dependencies,
including `segno`. The `--with pyinstaller` option installs PyInstaller temporarily on
top of the project environment without adding it to the project dependencies:

```bash
uv run --with pyinstaller pyinstaller --version
```

On Windows:

```bash
uv run --with pyinstaller pyinstaller --onefile --windowed --name PyDrop --icon=favicon.ico --add-data "favicon.ico;." main.py
```

On Linux or macOS:

```bash
uv run --with pyinstaller pyinstaller --onefile --windowed --name PyDrop --icon=favicon.ico --add-data "favicon.ico:." main.py
```

The executable is created in the `dist` directory. Build the application separately on each target operating system.

PyDrop keeps the default `shared` directory next to the executable when running as a PyInstaller single-file application.

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
├── main.py         # Application and web server
├── favicon.ico     # Application icon
├── shared/         # Default shared files
├── README.md
├── README.zh-CN.md
└── LICENSE         # WTFPL v2
```

## License and copyright

Except for `favicon.ico`, the source code and other project contents are released under the [Do What The Fuck You Want To Public License v2 (WTFPL)](https://www.wtfpl.net/). See [LICENSE](LICENSE).

The copyright of `favicon.ico` belongs to [Bison仓鼠](https://space.bilibili.com/136107). The icon is not covered by the WTFPL. If there is any infringement, please contact the copyright holder for removal.
