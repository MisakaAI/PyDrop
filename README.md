# PyDrop

PyDrop is a lightweight LAN file-transfer tool for computers and phones. It starts a local web server, displays the access URL as a QR code, and lets you upload or download files from any browser on the same network.

[简体中文](README.zh-CN.md)

## Features

- QR code access with a simple Tkinter desktop GUI
- Upload files from a phone or another computer
- Browse and download files from the shared directory
- Open the shared directory from the desktop app
- Choose or change the shared directory from the desktop app
- Works across Windows, macOS, Linux, Android, and iOS browsers
- Uses `segno` to generate QR codes

## Requirements

- Python 3.8 or newer
- Tkinter
- `segno`

Tkinter is included with most Python installations. On Debian/Ubuntu, install it with:

```bash
sudo apt install python3-tk
```

## Run from source

Install the dependency:

```bash
python -m pip install segno
```

Start PyDrop:

```bash
python ser.py
```

Connect the phone and computer to the same Wi-Fi network, then scan the QR code shown in the PyDrop window. You can also open the displayed URL manually.

The default port is `12450`. The default shared directory is `shared` next to the script. You can choose a different existing directory with the **Choose shared directory** button in the desktop app.

## Build a single executable

Install PyInstaller:

```bash
python -m pip install pyinstaller
```

On Windows:

```bash
pyinstaller --onefile --windowed --name PyDrop --icon=favicon.ico --add-data "favicon.ico;." ser.py
```

On Linux or macOS:

```bash
pyinstaller --onefile --windowed --name PyDrop --icon=favicon.ico --add-data "favicon.ico:." ser.py
```

The executable is created in the `dist` directory. Build the application separately on each target operating system.

PyDrop keeps the default `shared` directory next to the executable when running as a PyInstaller single-file application.

## Notes

- Both devices must be on the same LAN, and the computer firewall must allow TCP port `12450` on the private/local network.
- PyDrop is intended for trusted local networks. It has no login or encryption layer.
- To change the port, edit `PORT` in `ser.py` before running or building the application.

## Project layout

```text
.
├── ser.py          # Application and web server
├── favicon.ico     # Application icon
├── shared/         # Default shared files
├── README.md
├── README.zh-CN.md
└── LICENSE         # WTFPL v2
```

## License and copyright

Except for `favicon.ico`, the source code and other project contents are released under the [Do What The Fuck You Want To Public License v2 (WTFPL)](https://www.wtfpl.net/). See [LICENSE](LICENSE).

The copyright of `favicon.ico` belongs to [Bison仓鼠](https://space.bilibili.com/136107). The icon is not covered by the WTFPL. If there is any infringement, please contact the copyright holder for removal.
