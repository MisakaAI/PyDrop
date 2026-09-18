# PyDrop

PyDrop 是一个轻量的局域网文件互传工具，适用于电脑和手机之间传输文件。  
程序启动本地网页服务，并在 Tkinter 窗口中显示访问地址和二维码，手机浏览器扫码后即可上传或下载文件。

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
- Tkinter
- [uv](https://docs.astral.sh/uv/)（可选，用于依赖管理）

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

不使用 uv 时，在当前 Python 环境中安装 `segno`，再直接运行 `python main.py` 即可。

让手机和电脑连接同一个 Wi-Fi，然后使用手机扫描 PyDrop 窗口中的二维码，也可以手动打开窗口中显示的地址。

默认端口为 `12450`，共享目录是当前用户的下载文件夹（`~/Downloads`）。  
手动放入该目录的文件也会显示在网页中，也可以通过 GUI 中的“选择共享目录”按钮切换到其他已有目录。

## 构建 Release 可执行文件

构建脚本会优先使用项目中的 `.venv`，不存在时再使用系统 Python，脚本本身不会调用  
uv，也不依赖 PyInstaller spec 文件。构建开始前会检查 PyInstaller、`segno` 和  
Pillow；如果缺少依赖，脚本会输出可直接使用的 `python -m pip install ...` 命令。  
macOS 脚本还会检查 `dmgbuild`。

使用 uv 时，可安装锁定的运行、开发和构建依赖：

```bash
uv sync --group build
```

没有 uv 时，可直接在虚拟环境或系统 Python 中安装构建依赖：

```bash
python -m pip install pyinstaller segno pillow
```

构建 macOS 磁盘映像时，还需在上述命令中加入 `dmgbuild`。

请在目标系统上运行对应脚本：

| 平台 | 命令 | Release 产物示例 |
| --- | --- | --- |
| Linux | `./build_linux.sh` | `dist/PyDrop-v0.1.0-linux-x86_64` |
| Windows（cmd） | `build_windows.bat` | `dist\PyDrop-v0.1.0-windows-x86_64.exe` |
| macOS | `./build_macos_dmg.sh` | `dist/PyDrop-v0.1.0-macos-arm64.dmg` |

版本号默认读取自 `pyproject.toml`，也可以在运行脚本前设置 `PYDROP_VERSION` 来覆盖。  
架构后缀根据构建电脑自动识别。PyInstaller 不能跨系统编译，因此需要分别在各目标系统上  
构建，再把 `dist` 中的对应文件上传到 GitHub Release。

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
├── main.py                 # 主程序和网页服务器
├── favicon.ico             # 软件图标
├── build_linux.sh          # Linux Release 构建脚本
├── build_macos_dmg.sh      # macOS DMG Release 构建脚本
├── build_windows.bat       # Windows Release 构建脚本
├── README.md               # English documentation
├── README.zh-CN.md         # 中文文档
└── LICENSE                 # WTFPL v2
```

## 许可证与版权

除 `favicon.ico` 外，本项目的源代码及其他项目内容使用 [WTFPL v2（Do What The Fuck You Want To Public License）](https://www.wtfpl.net/) 发布，详见 [LICENSE](LICENSE)。

软件图标 `favicon.ico` 的版权归 [Bison仓鼠](https://space.bilibili.com/136107) 所有，不属于 WTFPL 授权范围。  
若存在侵权行为，请提交 [issue](https://github.com/MisakaAI/PyDrop/issues)，我将在看到后立即删除。
