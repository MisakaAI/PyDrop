#!/usr/bin/env python3

import html
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import segno
import tkinter as tk
from tkinter import filedialog, messagebox

HOST = "0.0.0.0"
PORT = 12450


def application_dir():
    """获取程序所在目录，兼容源码运行和 PyInstaller 单文件运行。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# 这个目录内的文件会显示在手机网页上，并可直接下载。
# 默认使用程序目录下的 shared 文件夹。
SHARED_DIR = application_dir() / "shared"
SHARED_DIR.mkdir(parents=True, exist_ok=True)
MAX_SIZE = 2 * 1024 * 1024 * 1024  # 2 GiB

PAGE_HEAD = """<!doctype html>
<html lang="zh-CN">

<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PyDrop - 局域网文件互传</title>
  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: #f4f5f7;
      color: #222;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    main {
      width: min(100% - 28px, 640px);
      margin: 0 auto;
      padding: 24px 0 36px;
    }

    h1 {
      margin: 0;
      font-size: 22px;
    }

    h2 {
      margin: 0 0 14px;
      font-size: 18px;
    }

    .subtitle {
      margin: 7px 0 0;
      color: #666;
      font-size: 14px;
    }

    .card {
      margin-top: 16px;
      padding: 18px;
      background: #fff;
      border: 1px solid #e2e4e8;
      border-radius: 10px;
    }

    input[type="file"] {
      display: block;
      width: 100%;
      padding: 9px;
      border: 1px solid #d5d8dd;
      border-radius: 6px;
      background: #fff;
      font-size: 14px;
    }

    button,
    .download {
      display: inline-block;
      min-width: 84px;
      text-align: center;
      min-height: 42px;
      border: 0;
      border-radius: 6px;
      background: #1769aa;
      color: #fff;
      font-size: 15px;
      text-decoration: none;
      cursor: pointer;
    }

    button {
      width: 100%;
      margin-top: 10px;
    }

    .download {
      padding: 11px 14px;
      white-space: nowrap;
    }

    button:active,
    .download:active {
      background: #125589;
    }

    ul {
      padding: 0;
      margin: 0;
      list-style: none;
    }

    li {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 0;
      border-top: 1px solid #eceef1;
    }

    li:first-child {
      border-top: 0;
      padding-top: 0;
    }

    li:last-child {
      padding-bottom: 0;
    }

    .file-info {
      min-width: 0;
      flex: 1;
    }

    .file-name {
      display: block;
      color: #1769aa;
      overflow-wrap: anywhere;
      text-decoration: none;
    }

    .file-size {
      display: block;
      margin-top: 4px;
      color: #777;
      font-size: 12px;
    }

    .empty {
      margin: 0;
      color: #777;
    }

    @media (min-width: 480px) {
      form {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      button {
        width: auto;
        margin-top: 0;
        padding: 0 20px;
      }
    }
  </style>
</head>

<body>
  <main>
    <h1>PyDrop · 局域网文件互传</h1>
    <p class="subtitle">上传文件，或点击下面的文件下载到手机</p>
    <section class="card">
      <h2>上传文件</h2>
      <form method="post" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <button type="submit">上传</button>
      </form>
    </section>
    <section class="card">
      <h2>共享文件</h2>
      {files}
    </section>
  </main>
</body>

</html>"""


def local_ip():
    """获取本机用于局域网通信的 IPv4 地址。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "<电脑局域网IP>"
    finally:
        sock.close()


def resource_path(name):
    """获取源码运行或 PyInstaller 打包后的资源路径。"""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    base_dir = Path(bundle_dir) if bundle_dir else Path(__file__).resolve().parent
    return base_dir / name


def open_shared_dir():
    """使用当前平台的文件管理器打开共享目录。"""
    path = str(SHARED_DIR)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        opener = shutil.which("xdg-open")
        if not opener:
            raise RuntimeError("找不到 xdg-open，无法打开文件管理器")
        subprocess.Popen([opener, path])


class App:
    QR_SIZE = 320

    def __init__(self):
        self.server = None
        self.server_thread = None
        self.root = tk.Tk()
        self.root.title("PyDrop - 局域网文件互传")
        self.root.resizable(False, False)
        self.root.configure(bg="#f4f5f7")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.set_window_icon()

        self.url = f"http://{local_ip()}:{PORT}"
        self.start_server()
        self.build_ui()

    def set_window_icon(self):
        """使用项目中的 favicon.ico 设置窗口图标。"""
        icon_path = resource_path("favicon.ico")
        if not icon_path.is_file():
            return

        # Windows 对 ICO 支持最好；其他平台不支持时保持默认 Tk 图标。
        try:
            self.root.iconbitmap(default=str(icon_path))
        except tk.TclError:
            try:
                self.icon_image = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, self.icon_image)
            except tk.TclError:
                pass

    def start_server(self):
        try:
            self.server = ThreadingHTTPServer((HOST, PORT), Handler)
            self.server.daemon_threads = True
        except OSError as exc:
            messagebox.showerror(
                "启动失败",
                f"无法监听端口 {PORT}。\n可能是端口已被占用，或被防火墙限制。\n\n{exc}",
                parent=self.root,
            )
            self.root.destroy()
            raise SystemExit(1) from exc

        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            name="file-transfer-server",
            daemon=True,
        )
        self.server_thread.start()

    def build_ui(self):
        colors = {
            "background": "#f4f5f7",
            "card": "#ffffff",
            "text": "#222222",
            "muted": "#666666",
            "primary": "#1769aa",
            "primary_active": "#125589",
            "border": "#e2e4e8",
        }

        content = tk.Frame(self.root, bg=colors["background"], padx=24, pady=22)
        content.pack()

        tk.Label(
            content,
            text="PyDrop · 局域网文件互传",
            bg=colors["background"],
            fg=colors["text"],
            font=("TkDefaultFont", 17, "bold"),
        ).pack()
        tk.Label(
            content,
            text="手机连接同一 Wi-Fi 后，扫描二维码或打开下面的地址",
            bg=colors["background"],
            fg=colors["muted"],
            font=("TkDefaultFont", 10),
        ).pack(pady=(6, 16))

        card = tk.Frame(
            content,
            bg=colors["card"],
            highlightbackground=colors["border"],
            highlightthickness=1,
            padx=18,
            pady=18,
        )
        card.pack()

        tk.Label(
            card,
            text="扫码访问",
            bg=colors["card"],
            fg=colors["text"],
            font=("TkDefaultFont", 12, "bold"),
        ).pack()
        tk.Label(
            card,
            text="用手机相机扫描二维码即可打开文件页面",
            bg=colors["card"],
            fg=colors["muted"],
            font=("TkDefaultFont", 9),
        ).pack(pady=(4, 10))

        url_label = tk.Label(
            card,
            text=self.url,
            bg=colors["card"],
            fg=colors["primary"],
            cursor="hand2",
            font=("TkDefaultFont", 10, "underline"),
        )
        url_label.pack(pady=(0, 10))
        url_label.bind("<Button-1>", lambda _event: self.copy_url())

        self.qr_canvas = tk.Canvas(
            card,
            width=self.QR_SIZE,
            height=self.QR_SIZE,
            bg="white",
            highlightthickness=1,
            highlightbackground=colors["border"],
        )
        self.qr_canvas.pack()
        self.draw_qr(self.url)

        button = tk.Button(
            card,
            text="打开共享文件夹",
            command=self.open_folder,
            bg=colors["primary"],
            fg="white",
            activebackground=colors["primary_active"],
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=18,
            pady=8,
            font=("TkDefaultFont", 10),
        )
        button.pack(pady=(16, 8))

        tk.Button(
            card,
            text="选择共享目录",
            command=self.choose_folder,
            bg=colors["card"],
            fg=colors["primary"],
            activebackground="#edf5fb",
            activeforeground=colors["primary_active"],
            relief="solid",
            borderwidth=1,
            cursor="hand2",
            padx=18,
            pady=6,
            font=("TkDefaultFont", 10),
        ).pack(pady=(0, 10))

        self.shared_dir_label = tk.Label(
            card,
            text=f"共享目录：{SHARED_DIR}",
            bg=colors["card"],
            fg=colors["muted"],
            font=("TkDefaultFont", 9),
            wraplength=400,
        )
        self.shared_dir_label.pack()

    def choose_folder(self):
        """选择并立即切换当前运行实例使用的共享目录。"""
        global SHARED_DIR

        selected = filedialog.askdirectory(
            parent=self.root,
            initialdir=str(SHARED_DIR),
            title="选择共享目录",
            mustexist=True,
        )
        if not selected:
            return

        SHARED_DIR = Path(selected).resolve()
        self.shared_dir_label.config(text=f"共享目录：{SHARED_DIR}")

    def draw_qr(self, value):
        """用 segno 生成二维码，并直接绘制到 Tk Canvas。"""
        qr = segno.make(value, error="m")
        matrix = qr.matrix
        border = 4
        module_count = len(matrix) + border * 2
        scale = max(1, self.QR_SIZE // module_count)
        actual_size = module_count * scale
        offset = (self.QR_SIZE - actual_size) // 2

        self.qr_canvas.delete("all")
        self.qr_canvas.create_rectangle(
            0, 0, self.QR_SIZE, self.QR_SIZE, fill="white", outline=""
        )
        for row, values in enumerate(matrix):
            for column, dark in enumerate(values):
                if dark:
                    x0 = offset + (column + border) * scale
                    y0 = offset + (row + border) * scale
                    self.qr_canvas.create_rectangle(
                        x0,
                        y0,
                        x0 + scale,
                        y0 + scale,
                        fill="black",
                        outline="",
                    )

    def copy_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.url)
        self.root.update()  # 让剪贴板内容在窗口关闭后仍可用

    def open_folder(self):
        try:
            open_shared_dir()
        except (OSError, RuntimeError) as exc:
            messagebox.showerror("无法打开目录", str(exc), parent=self.root)

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.root.destroy()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path == "/":
            files = []
            for item in sorted(SHARED_DIR.iterdir(), key=lambda p: p.name.lower()):
                if item.is_file():
                    name = html.escape(item.name)
                    href = html.escape("/files/" + quote(item.name), quote=True)
                    size = self.format_size(item.stat().st_size)
                    files.append(
                        f'<li><div class="file-info">'
                        f'<a class="file-name" href="{href}">{name}</a>'
                        f'<small class="file-size">{size}</small></div>'
                        f'<a class="download" href="{href}" download>下载</a></li>'
                    )
            file_list = (
                "<ul>" + "".join(files) + "</ul>"
                if files
                else '<p class="empty">共享目录为空。</p>'
            )
            self.reply(200, PAGE_HEAD.replace("{files}", file_list))
            return

        if not request_path.startswith("/files/"):
            self.send_error(404)
            return

        # 只允许访问共享目录的直接子文件，避免 ../ 路径穿越。
        requested_name = unquote(request_path[len("/files/") :])
        if not requested_name or "/" in requested_name or "\\" in requested_name:
            self.send_error(404)
            return
        target = SHARED_DIR / requested_name
        if not target.is_file() or target.parent != SHARED_DIR:
            self.send_error(404)
            return

        try:
            size = target.stat().st_size
            content_type = (
                mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            )
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            safe_download_name = (
                target.name.replace('"', "'").replace("\r", "").replace("\n", "")
            )
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{safe_download_name}"',
            )
            self.end_headers()
            with target.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    @staticmethod
    def format_size(size):
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
            size /= 1024

    def do_POST(self):
        if self.path != "/":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return

        if length <= 0:
            self.send_error(400, "没有收到文件")
            return
        if length > MAX_SIZE:
            self.send_error(413, "文件不能超过 2 GiB")
            return

        body = self.rfile.read(length)
        raw = (
            b"Content-Type: "
            + self.headers.get("Content-Type", "").encode()
            + b"\r\nMIME-Version: 1.0\r\n\r\n"
            + body
        )
        message = BytesParser(policy=default).parsebytes(raw)

        for part in message.iter_attachments():
            filename = part.get_filename()
            if not filename:
                continue

            # 浏览器可能提交 Unix 或 Windows 风格的路径。
            filename = os.path.basename(filename.replace("\\", "/"))
            if not filename:
                filename = "uploaded_file"
            stem = Path(filename).stem or "uploaded_file"
            suffix = Path(filename).suffix
            target = SHARED_DIR / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
            target.write_bytes(part.get_payload(decode=True) or b"")

            message_text = html.escape(f"上传成功！\n保存到：{target}")
            self.reply(
                200,
                "<meta name='viewport' content='width=device-width'>"
                f"<pre>{message_text}</pre><p><a href='/'>返回文件列表</a></p>",
            )
            return

        self.send_error(400, "没有找到上传文件")


if __name__ == "__main__":
    App().root.mainloop()
