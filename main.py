#!/usr/bin/env python3

import html
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import tkinter as tk
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from urllib.parse import quote, unquote, urlsplit

import segno

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
  <meta name="theme-color" content="#f3f7fa">
  <title>PyDrop - 局域网文件互传</title>
  <style>
    :root {
      color-scheme: light;
      --text: #1e3445;
      --muted: #617582;
      --accent: #087e8b;
      --accent-dark: #05626d;
      --border: #e1eaf0;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(ellipse at 0% 0%, #deeff4 0, transparent 55%),
        radial-gradient(ellipse at 100% 30%, #e8edf9 0, transparent 50%),
        #f3f7fa;
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
        "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.6;
      -webkit-tap-highlight-color: transparent;
    }

    main {
      width: min(100% - 40px, 760px);
      margin: 0 auto;
      padding: 36px 0 28px;
    }

    .brand, .brand-name, .section-heading {
      display: flex;
      align-items: center;
    }

    .brand { justify-content: space-between; gap: 16px; }
    .brand-name { gap: 10px; font-size: 21px; font-weight: 750; }

    .brand-icon {
      display: grid;
      place-items: center;
      width: 40px;
      height: 40px;
      border-radius: 13px;
      background: var(--accent);
      color: #fff;
      box-shadow: 0 5px 12px #087e8b20;
    }

    .icon {
      width: 22px;
      height: 22px;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
      flex-shrink: 0;
    }

    .network-badge {
      padding: 5px 11px;
      border: 1px solid #cce3e7;
      border-radius: 999px;
      color: var(--accent-dark);
      background: #edf8fa;
      font-size: 12px;
      white-space: nowrap;
    }

    .intro { padding: 34px 0 24px; }

    h1 {
      margin: 0;
      font-size: clamp(27px, 5vw, 36px);
      line-height: 1.35;
      letter-spacing: -0.8px;
    }

    .subtitle { margin: 12px 0 0; color: var(--muted); font-size: 14px; }

    .card {
      margin-bottom: 20px;
      padding: 26px;
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: 0 8px 30px #25465b06;
    }

    .section-heading { gap: 12px; margin-bottom: 20px; }

    .section-number {
      display: grid;
      place-items: center;
      width: 36px;
      height: 36px;
      flex-shrink: 0;
      border-radius: 11px;
      background: #edf6f8;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }

    h2 { margin: 0; font-size: 17px; font-weight: 650; }
    .section-description { margin: 2px 0 0; color: var(--muted); font-size: 12px; }

    .upload-area {
      padding: 24px;
      border: 1px dashed #b7d5dd;
      border-radius: 16px;
      background: #f7fbfc;
      text-align: center;
    }

    .upload-icon {
      display: grid;
      place-items: center;
      width: 48px;
      height: 48px;
      margin: 0 auto 12px;
      border-radius: 15px;
      background: #e4f2f5;
      color: var(--accent);
    }

    .upload-label { display: block; font-size: 15px; font-weight: 600; }
    .upload-hint { margin: 4px 0 18px; color: var(--muted); font-size: 12px; }

    input[type="file"] {
      display: block;
      width: 100%;
      min-width: 0;
      padding: 6px;
      border: 1px solid var(--border);
      border-radius: 11px;
      background: #fff;
      color: var(--muted);
      font: inherit;
      font-size: 13px;
      text-align: left;
    }

    input[type="file"]::file-selector-button {
      margin-right: 12px;
      padding: 9px 14px;
      border: 0;
      border-radius: 7px;
      background: #eaf3f6;
      color: var(--accent-dark);
      font: inherit;
      font-weight: 600;
      cursor: pointer;
    }

    button, .download {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 44px;
      border: 1px solid transparent;
      border-radius: 11px;
      font: inherit;
      font-size: 14px;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      transition: background-color 160ms ease, box-shadow 160ms ease;
      touch-action: manipulation;
    }

    button {
      width: 100%;
      margin-top: 16px;
      padding: 12px 20px;
      background: var(--accent);
      color: #fff;
      box-shadow: 0 4px 10px #087e8b18;
    }

    .download {
      flex-shrink: 0;
      min-width: 72px;
      padding: 8px 16px;
      border-color: #d4e7eb;
      background: #eff7f9;
      color: var(--accent-dark);
      white-space: nowrap;
    }

    :where(a, button, input):focus-visible {
      outline: 3px solid #168998;
      outline-offset: 4px;
    }

    @media (hover: hover) {
      button:hover { background: var(--accent-dark); box-shadow: 0 6px 16px #087e8b26; }
      .download:hover { background: #deeff3; }
      .file-name:hover { color: var(--accent); text-decoration: underline; }
      input[type="file"]::file-selector-button:hover { background: #deeff3; }
    }

    button:active { background: #044f58; }
    .download:active { background: #d1e7ec; }

    ul { padding: 0; margin: 0; list-style: none; }

    li {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 18px 0;
      border-top: 1px solid #edf1f4;
    }

    li:first-child { border-top: 0; padding-top: 0; }
    li:last-child { padding-bottom: 0; }
    .file-info { min-width: 0; flex: 1; }

    .file-name {
      display: block;
      color: var(--text);
      font-size: 14px;
      font-weight: 550;
      overflow-wrap: anywhere;
      text-decoration: none;
    }

    .file-size {
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }

    .empty {
      margin: 0;
      padding: 32px 16px;
      border: 1px dashed var(--border);
      border-radius: 14px;
      background: #f8fafc;
      color: var(--muted);
      font-size: 14px;
      text-align: center;
    }

    footer { padding: 4px 12px; color: var(--muted); font-size: 12px; text-align: center; }

    @media (max-width: 480px) {
      main { width: calc(100% - 28px); padding-top: 22px; }
      .intro { padding: 28px 2px 22px; }
      .card { padding: 20px 16px; border-radius: 18px; }
      .upload-area { padding: 20px 14px; }
      li { gap: 12px; }
      .download { min-width: 64px; padding-inline: 12px; }
    }

    @media (prefers-reduced-motion: reduce) {
      button, .download { transition: none; }
    }
  </style>
</head>

<body>
  <main>
    <header class="brand">
      <div class="brand-name">
        <span class="brand-icon" aria-hidden="true">
          <svg class="icon" viewBox="0 0 24 24">
            <path d="M7 16V4m-4 4 4-4 4 4M17 8v12m-4-4 4 4 4-4" />
          </svg>
        </span>
        PyDrop
      </div>
      <span class="network-badge">局域网文件互传</span>
    </header>
    <div class="intro">
      <h1>文件互传，轻松一点。</h1>
      <p class="subtitle">让文件在手机与电脑之间，自由来往。</p>
    </div>
    <section class="card" aria-labelledby="upload-heading">
      <div class="section-heading">
        <span class="section-number" aria-hidden="true">01</span>
        <div>
          <h2 id="upload-heading">上传文件</h2>
          <p class="section-description">将此设备的文件发送到电脑</p>
        </div>
      </div>
      <form method="post" enctype="multipart/form-data">
        <div class="upload-area">
          <span class="upload-icon" aria-hidden="true">
            <svg class="icon" viewBox="0 0 24 24">
              <path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5" />
            </svg>
          </span>
          <label class="upload-label" for="upload-file">选择一个要分享的文件</label>
          <p class="upload-hint" id="upload-hint">照片、视频、文档，随心传递</p>
          <input id="upload-file" type="file" name="file" aria-describedby="upload-hint" required>
        </div>
        <button type="submit">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 19V5m-5 5 5-5 5 5" />
          </svg>
          上传到电脑
        </button>
      </form>
    </section>
    <section class="card" aria-labelledby="files-heading">
      <div class="section-heading">
        <span class="section-number" aria-hidden="true">02</span>
        <div>
          <h2 id="files-heading">共享文件</h2>
          <p class="section-description">点击文件名或下载按钮，保存到此设备</p>
        </div>
      </div>
      {files}
    </section>
    <footer>连接同一局域网，即可上传与下载</footer>
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
        return None
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
    QR_SIZE = 256

    def __init__(self):
        self.server = None
        self.server_thread = None
        self.feedback_job = None
        self.root = tk.Tk()
        self.root.title("PyDrop - 局域网文件互传")
        self.root.configure(bg="#f3f6fa")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.set_window_icon()

        self.start_server()
        self.build_ui()
        self.refresh_address()
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_reqwidth(), self.root.winfo_reqheight())

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
        self.colors = colors = {
            "background": "#f3f6fa",
            "card": "#ffffff",
            "text": "#18283b",
            "muted": "#596b80",
            "primary": "#2563eb",
            "primary_active": "#1d4ed8",
            "border": "#dce4ef",
        }
        family = tkfont.nametofont("TkDefaultFont").actual("family")
        self.body_font = (family, 10)
        self.small_font = (family, 9)
        heading_font = (family, 11, "bold")
        self.status = tk.StringVar(self.root)
        self.address = tk.StringVar(self.root)
        self.folder_path = tk.StringVar(self.root, value=str(SHARED_DIR))

        content = tk.Frame(self.root, bg=colors["background"], padx=24, pady=24)
        content.pack(fill="both", expand=True)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(1, weight=1)

        header = tk.Frame(content, bg=colors["background"])
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        header.columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="PyDrop",
            bg=colors["background"],
            fg=colors["text"],
            font=(family, 24, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.connection_label = tk.Label(
            header,
            padx=12,
            pady=6,
            font=self.small_font,
        )
        self.connection_label.grid(row=0, column=1, sticky="e")
        tk.Label(
            header,
            text="局域网文件互传 · 手机与电脑连接同一 Wi-Fi 即可使用",
            bg=colors["background"],
            fg=colors["muted"],
            font=self.body_font,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        qr_card = tk.Frame(
            content,
            bg=colors["card"],
            highlightbackground=colors["border"],
            highlightthickness=1,
            padx=16,
            pady=16,
        )
        qr_card.grid(row=1, column=0, sticky="ns", padx=(0, 20))

        tk.Label(
            qr_card,
            text="扫码连接",
            bg=colors["card"],
            fg=colors["text"],
            font=heading_font,
        ).pack()

        self.qr_canvas = tk.Canvas(
            qr_card,
            width=self.QR_SIZE,
            height=self.QR_SIZE,
            bg="white",
            highlightthickness=0,
        )
        self.qr_canvas.pack(expand=True, pady=8)
        tk.Label(
            qr_card,
            text="使用手机相机扫描\n在浏览器中上传或下载文件",
            bg=colors["card"],
            fg=colors["muted"],
            font=self.small_font,
            justify="center",
        ).pack()

        details = tk.Frame(content, bg=colors["background"])
        details.grid(row=1, column=1, sticky="nsew")
        details.columnconfigure(0, weight=1)

        tk.Label(
            details,
            text="浏览器访问地址",
            bg=colors["background"],
            fg=colors["text"],
            font=heading_font,
        ).grid(row=0, column=0, sticky="w", pady=(2, 10))
        self.address_entry = self.readonly_entry(details, self.address)
        self.address_entry.grid(row=1, column=0, sticky="ew", ipady=8)
        address_actions = tk.Frame(details, bg=colors["background"])
        address_actions.grid(row=2, column=0, sticky="w", pady=(10, 24))
        self.copy_button = self.action_button(
            address_actions, "复制地址", self.copy_url, primary=True
        )
        self.copy_button.pack(side="left", padx=(0, 8))
        self.action_button(address_actions, "重新检测", self.refresh_address).pack(
            side="left"
        )

        tk.Frame(details, bg=colors["border"], height=1).grid(
            row=3, column=0, sticky="ew", pady=(0, 20)
        )
        tk.Label(
            details,
            text="共享文件夹",
            bg=colors["background"],
            fg=colors["text"],
            font=heading_font,
        ).grid(row=4, column=0, sticky="w", pady=(0, 10))
        self.folder_entry = self.readonly_entry(details, self.folder_path)
        self.folder_entry.grid(row=5, column=0, sticky="ew", ipady=8)
        self.folder_entry.xview_moveto(1)
        tk.Label(
            details,
            text="放入文件即可共享，手机上传也会保存到此处。",
            bg=colors["background"],
            fg=colors["muted"],
            font=self.small_font,
            wraplength=300,
            justify="left",
        ).grid(row=6, column=0, sticky="w", pady=(8, 12))
        folder_actions = tk.Frame(details, bg=colors["background"])
        folder_actions.grid(row=7, column=0, sticky="w")
        self.action_button(folder_actions, "打开文件夹", self.open_folder).pack(
            side="left", padx=(0, 8)
        )
        self.action_button(folder_actions, "选择共享目录", self.choose_folder).pack(
            side="left"
        )
        tk.Label(
            content,
            textvariable=self.status,
            bg=colors["background"],
            fg=colors["muted"],
            font=self.small_font,
            anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 0))

    def readonly_entry(self, parent, variable):
        """允许选择、复制和水平滚动，避免长地址或路径撑大窗口。"""
        return tk.Entry(
            parent,
            textvariable=variable,
            state="readonly",
            width=32,
            font=self.body_font,
            fg=self.colors["text"],
            readonlybackground=self.colors["card"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["primary"],
            selectbackground=self.colors["primary"],
            selectforeground="white",
        )

    def action_button(self, parent, text, command, primary=False):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=self.colors["primary"] if primary else self.colors["card"],
            fg="white" if primary else self.colors["primary"],
            activebackground=self.colors["primary_active"] if primary else "#e6edfa",
            activeforeground="white" if primary else self.colors["primary_active"],
            disabledforeground=self.colors["muted"],
            relief="flat",
            borderwidth=0,
            highlightthickness=2,
            highlightbackground=self.colors["background"],
            highlightcolor=self.colors["primary"],
            cursor="hand2",
            padx=12,
            pady=8,
            font=self.body_font,
            takefocus=True,
        )
        button.bind("<Return>", lambda _event: button.invoke())
        return button

    def refresh_address(self):
        ip = local_ip()
        self.url = f"http://{ip}:{PORT}" if ip else ""
        self.address.set(self.url or "未检测到局域网地址")
        self.copy_button.config(state="normal" if ip else "disabled")
        self.connection_label.config(
            text="● 服务已启动" if ip else "● 请检查网络",
            fg="#166534" if ip else "#92400e",
            bg="#e6f4eb" if ip else "#fff1d6",
        )
        if ip:
            self.draw_qr(self.url)
        else:
            self.qr_canvas.delete("all")
            self.qr_canvas.create_text(
                self.QR_SIZE // 2,
                self.QR_SIZE // 2,
                text="连接 Wi-Fi 或网线后\n点击「重新检测」生成二维码",
                fill=self.colors["muted"],
                font=self.body_font,
                width=self.QR_SIZE - 24,
                justify="center",
            )
        self.show_status()

    def show_status(self, message=None):
        if self.feedback_job is not None:
            self.root.after_cancel(self.feedback_job)
            self.feedback_job = None
        self.status.set(
            message
            or (
                "手机与电脑需在同一局域网；请仅在可信任的网络中共享。"
                if self.url
                else "未获取到访问地址，请检查网络连接后重新检测。"
            )
        )
        if message:
            self.feedback_job = self.root.after(4000, self.show_status)

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
        self.folder_path.set(str(SHARED_DIR))
        self.folder_entry.xview_moveto(1)
        self.show_status("共享目录已切换，刷新手机页面即可查看。")

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
        if not self.url:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.url)
        except tk.TclError:
            self.show_status("复制失败，请选中访问地址后手动复制。")
        else:
            self.show_status("地址已复制，可粘贴到同一局域网设备的浏览器中。")

    def open_folder(self):
        try:
            open_shared_dir()
        except (OSError, RuntimeError) as exc:
            messagebox.showerror("无法打开目录", str(exc), parent=self.root)

    def close(self):
        if self.feedback_job is not None:
            self.root.after_cancel(self.feedback_job)
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.root.destroy()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Keep requests working when a windowed build has no stderr stream."""
        if sys.stderr is not None:
            super().log_message(format, *args)

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
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"download\"; filename*=UTF-8''{quote(target.name)}",
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
