# PyDrop

PyDrop 是一个轻量的局域网文件互传工具，适用于电脑和手机之间传输文件。程序启动本地网页服务，并在 Tkinter 窗口中显示访问地址和二维码，手机浏览器扫码后即可上传或下载文件。

[English](README.md)

## 功能

- 使用 Tkinter 图形界面显示二维码
- 一键复制访问地址，网络切换后可重新检测地址并更新二维码
- 手机或其他电脑通过网页上传文件
- 浏览并下载共享目录中的文件
- 一键使用系统文件管理器打开共享目录
- 在 GUI 中选择或修改共享目录
- 支持 Windows、macOS、Linux，以及 Android / iOS 手机浏览器
- 使用 `segno` 生成二维码

## 运行环境

- Python 3.13 或更高版本
- [uv](https://docs.astral.sh/uv/)
- Tkinter

大多数 Python 安装包已包含 Tkinter。Debian / Ubuntu 可执行：

```bash
sudo apt install python3-tk
```

## 从源码运行

创建项目虚拟环境并安装锁定的依赖：

```bash
uv sync
```

启动程序：

```bash
uv run python main.py
```

让手机和电脑连接同一个 Wi-Fi，然后使用手机扫描 PyDrop 窗口中的二维码，也可以手动打开窗口中显示的地址。

默认端口为 `12450`，共享目录是当前用户的下载文件夹（`~/Downloads`）。手动放入该目录的文件也会显示在网页中，也可以通过 GUI 中的“选择共享目录”按钮切换到其他已有目录。

## 使用 PyInstaller 打包成单文件

在项目环境中运行 PyInstaller，确保它能够访问 PyDrop 的依赖（包括 `segno`）。
`--with pyinstaller` 会将 PyInstaller 临时安装到项目环境之上，不会将其添加为项目依赖：

```bash
uv run --with pyinstaller pyinstaller --version
```

Windows：

```bash
uv run --with pyinstaller pyinstaller --onefile --windowed --name PyDrop --icon=favicon.ico --add-data "favicon.ico;." main.py
```

Linux / macOS：

```bash
uv run --with pyinstaller pyinstaller --onefile --windowed --name PyDrop --icon=favicon.ico --add-data "favicon.ico:." main.py
```

生成的可执行文件位于 `dist` 目录。需要在目标操作系统上分别打包，不能跨操作系统直接打包。

## 注意事项

- 手机和电脑必须连接同一个局域网。
- Windows 防火墙提示时，需要允许 PyDrop 在专用网络中通信。
- PyDrop 默认监听 TCP `12450` 端口。
- 本程序没有登录和加密功能，请只在可信任的局域网中使用。
- 如需修改端口，运行或打包前修改 `main.py` 中的 `PORT`。

## 开发

使用 Ruff 格式化并检查代码：

```bash
uv run ruff format .
uv run ruff check .
```

## 项目结构

```text
.
├── main.py         # 主程序和网页服务器
├── favicon.ico     # 软件图标
├── README.md       # English documentation
├── README.zh-CN.md # 中文文档
└── LICENSE         # WTFPL v2
```

## 许可证与版权

除 `favicon.ico` 外，本项目的源代码及其他项目内容使用 [WTFPL v2（Do What The Fuck You Want To Public License）](https://www.wtfpl.net/) 发布，详见 [LICENSE](LICENSE)。

软件图标 `favicon.ico` 的版权归 [Bison仓鼠](https://space.bilibili.com/136107) 所有，不属于 WTFPL 授权范围。如有侵权，请联系版权方删除（侵删）。
