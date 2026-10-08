#!/usr/bin/env python3

import html
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from urllib.parse import parse_qs, quote, unquote, urlsplit

import segno

HOST = "0.0.0.0"
PORT = 12450

# 这个目录内的文件会显示在手机网页上，并可直接下载。
# Path.home() 会在 Windows 上返回当前用户目录，并使用平台原生路径格式。
SHARED_DIR = Path.home() / "Downloads"
SHARED_DIR.mkdir(parents=True, exist_ok=True)
MAX_SIZE = 2 * 1024 * 1024 * 1024  # 2 GiB
MAX_TEXT_LENGTH = 50_000  # 单条文本的最大字符数
MAX_TEXT_BODY = 256 * 1024  # 文本请求体的最大字节数

PAGE_HEAD = """<!doctype html>
<html lang="zh-CN">

<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#f3f7fa">
  <title>PyDrop - 局域网互传</title>
  <style>
    :root {
      color-scheme: light;
      --text: #1e3445;
      --muted: #617582;
      --accent: #087e8b;
      --accent-dark: #05626d;
      --border: #e1eaf0;
      --page: #f3f7fa;
      --chat: #edf3f7;
    }

    * { box-sizing: border-box; }

    html, body { height: 100%; }

    body {
      margin: 0;
      background: var(--page);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
        "PingFang SC", "Microsoft YaHei", sans-serif;
      font-size: 15px;
      line-height: 1.6;
      -webkit-tap-highlight-color: transparent;
      -webkit-text-size-adjust: 100%;
    }

    .app {
      display: flex;
      flex-direction: column;
      width: 100%;
      height: 100vh;
      height: 100dvh;
      max-height: 100vh;
      max-height: 100dvh;
      margin: 0 auto;
      background: var(--chat);
    }

    @media (min-width: 720px) {
      body { padding: 24px 20px; }
      .app {
        width: min(100%, 660px);
        height: calc(100vh - 48px);
        height: calc(100dvh - 48px);
        max-height: calc(100vh - 48px);
        max-height: calc(100dvh - 48px);
        border: 1px solid var(--border);
        border-radius: 24px;
        box-shadow: 0 18px 50px #25465b14;
        overflow: hidden;
      }
    }

    .topbar {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
      padding: 11px 14px;
      padding-top: calc(11px + env(safe-area-inset-top, 0));
      background: #fff;
      border-bottom: 1px solid var(--border);
    }

    .brand { display: flex; align-items: center; gap: 10px; min-width: 0; }

    .brand-icon {
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      flex-shrink: 0;
      border-radius: 11px;
      background: var(--accent);
      color: #fff;
      box-shadow: 0 5px 12px #087e8b20;
    }

    .icon {
      width: 20px;
      height: 20px;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
      flex-shrink: 0;
    }

    .brand-name { display: block; font-size: 16px; font-weight: 750; letter-spacing: -0.2px; }
    .brand-sub { display: block; color: var(--muted); font-size: 11px; line-height: 1.4; }

    .topbar-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }

    button { font: inherit; cursor: pointer; }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 34px;
      padding: 6px 12px;
      border: 1px solid #d4e7eb;
      border-radius: 999px;
      background: #eff7f9;
      color: var(--accent-dark);
      font-size: 12.5px;
      font-weight: 650;
      text-decoration: none;
      white-space: nowrap;
      transition: background-color 160ms ease;
      touch-action: manipulation;
    }

    .chip .icon { width: 16px; height: 16px; }

    .chat {
      flex: 1;
      overflow-y: auto;
      padding: 16px 14px 8px;
      -webkit-overflow-scrolling: touch;
      overscroll-behavior: contain;
    }

    .messages {
      display: flex;
      flex-direction: column;
      gap: 14px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .messages:empty::before {
      content: "还没有消息。在下方输入文字，或点击回形针按钮发送文件。";
      display: block;
      margin: 26px auto 0;
      max-width: 230px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }

    .message {
      display: flex;
      flex-direction: column;
      max-width: 85%;
      animation: bubble-in 240ms ease-out;
    }

    .message.in { align-self: flex-start; align-items: flex-start; }
    .message.out { align-self: flex-end; align-items: flex-end; }

    .message-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 4px 5px;
      color: var(--muted);
      font-size: 11px;
    }

    .message.out .message-meta { flex-direction: row-reverse; }

    .bubble {
      padding: 10px 13px;
      border-radius: 16px;
      font-size: 14.5px;
      line-height: 1.65;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      -webkit-user-select: text;
      user-select: text;
      -webkit-touch-callout: default;
    }

    .message.in .bubble {
      background: #fff;
      border: 1px solid var(--border);
      border-top-left-radius: 5px;
      box-shadow: 0 2px 10px #25465b0a;
    }

    .message.out .bubble {
      background: var(--accent);
      color: #fff;
      border-top-right-radius: 5px;
      box-shadow: 0 4px 12px #087e8b24;
    }

    .copy-button {
      padding: 2px 9px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: #fff;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.6;
    }

    .file-card {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 210px;
      max-width: 100%;
      padding: 12px 14px;
      border-radius: 16px;
      color: inherit;
      text-decoration: none;
      transition: background-color 160ms ease;
    }

    .message.in .file-card {
      background: #fff;
      border: 1px solid var(--border);
      border-top-left-radius: 5px;
      box-shadow: 0 2px 10px #25465b0a;
    }

    .message.out .file-card {
      background: var(--accent);
      border-top-right-radius: 5px;
      box-shadow: 0 4px 12px #087e8b24;
    }

    .file-icon {
      display: grid;
      place-items: center;
      width: 38px;
      height: 38px;
      flex-shrink: 0;
      border-radius: 11px;
    }

    .message.in .file-icon { background: #e4f2f5; color: var(--accent); }
    .message.out .file-icon { background: #ffffff2e; color: #fff; }

    .file-info { min-width: 0; }
    .file-name { display: block; font-size: 13.5px; font-weight: 650; line-height: 1.45; overflow-wrap: anywhere; }
    .file-size { display: block; margin-top: 2px; font-size: 11.5px; opacity: .8; }

    .message.out .file-card,
    .message.out .file-card .file-name,
    .message.out .file-card .file-size { color: #fff; }

    .composer-wrap {
      flex-shrink: 0;
      background: #fff;
      border-top: 1px solid var(--border);
      padding-bottom: env(safe-area-inset-bottom, 0);
    }

    .composer-status {
      margin: 0;
      padding: 0 16px;
      color: var(--accent-dark);
      font-size: 12px;
    }

    .composer-status:not(:empty) { padding-top: 8px; }
    .composer-status.is-error { color: #b3261e; }

    .progress { height: 3px; background: #e6eef1; overflow: hidden; }
    .progress[hidden] { display: none; }

    .progress-bar {
      display: block;
      width: 0;
      height: 100%;
      background: var(--accent);
      transition: width 140ms linear;
    }

    .composer { display: flex; align-items: flex-end; gap: 8px; padding: 10px 14px; }

    .composer textarea {
      flex: 1;
      min-width: 0;
      min-height: 44px;
      max-height: 132px;
      padding: 11px 13px;
      border: 1px solid var(--border);
      border-radius: 15px;
      background: #f7fafc;
      color: var(--text);
      font: inherit;
      font-size: 14.5px;
      line-height: 1.5;
      resize: none;
    }

    .composer textarea::placeholder { color: #9aabb7; }
    .composer textarea:focus { outline: none; border-color: #9fd4dc; background: #fff; }

    .composer-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 44px;
      flex-shrink: 0;
      padding: 0 18px;
      border: 0;
      border-radius: 15px;
      background: var(--accent);
      color: #fff;
      font-size: 14px;
      font-weight: 650;
      box-shadow: 0 4px 10px #087e8b18;
      touch-action: manipulation;
    }

    .composer-button:disabled { opacity: .55; box-shadow: none; cursor: default; }

    .icon-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 44px;
      height: 44px;
      flex-shrink: 0;
      border: 1px solid #d4e7eb;
      border-radius: 15px;
      background: #eff7f9;
      color: var(--accent-dark);
      touch-action: manipulation;
    }

    .icon-button[disabled] { opacity: .55; cursor: default; }

    :where(a, button, textarea):focus-visible { outline: 3px solid #168998; outline-offset: 2px; }

    @keyframes bubble-in {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (hover: hover) {
      .chip:hover { background: #deeff3; }
      .composer-button:hover { background: var(--accent-dark); }
      .icon-button:hover { background: #deeff3; }
      .copy-button:hover { background: #eff7f9; color: var(--accent-dark); }
      .message.in .file-card:hover { background: #f7fbfc; }
      .message.out .file-card:hover { background: var(--accent-dark); }
    }

    .chip:active { background: #d1e7ec; }
    .composer-button:active { background: #044f58; }
    .icon-button:active { background: #d1e7ec; }

    @media (max-width: 480px) {
      /* 16px 可避免 iOS Safari 聚焦输入框时自动放大页面 */
      .composer textarea { font-size: 16px; }
      .bubble { font-size: 15px; }
      .message { max-width: 88%; }
    }

    @media (prefers-reduced-motion: reduce) {
      .message { animation: none; }
      .chip, .composer-button, .icon-button, .file-card, .progress-bar { transition: none; }
    }
  </style>
</head>

<body>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <span class="brand-icon" aria-hidden="true">
          <svg class="icon" viewBox="0 0 24 24">
            <path d="M7 16V4m-4 4 4-4 4 4M17 8v12m-4-4 4 4 4-4" />
          </svg>
        </span>
        <span>
          <span class="brand-name">PyDrop</span>
          <span class="brand-sub">与电脑局域网互传</span>
        </span>
      </div>
      <div class="topbar-actions">
        <a class="chip" href="/files">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 7h5l2 2h11v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" />
          </svg>
          共享文件
        </a>
        <button type="button" class="chip" id="chat-clear">清空</button>
      </div>
    </header>
    <div class="chat" id="chat">
      <ol class="messages" id="messages" aria-live="polite">__MESSAGES__</ol>
    </div>
    <div class="composer-wrap">
      <p class="composer-status" id="composer-status" role="status"></p>
      <div class="progress" id="progress" hidden><span class="progress-bar" id="progress-bar"></span></div>
      <form class="composer" id="composer" method="post" enctype="multipart/form-data" action="/">
        <button type="button" class="icon-button" id="pick-file" title="选择文件并发送到电脑"
          aria-label="选择文件并发送到电脑">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M21.4 11.05 12.6 19.85a5 5 0 0 1-7.07-7.07l8.49-8.49a3.5 3.5 0 0 1 4.95 4.95l-8.49 8.49a2 2 0 0 1-2.83-2.83l7.78-7.78" />
          </svg>
        </button>
        <input type="file" id="file-input" name="file" multiple hidden>
        <textarea id="text-input" name="text" rows="1" maxlength="50000"
          placeholder="输入文本…" aria-label="要发送到电脑的文本"></textarea>
        <button type="submit" class="composer-button" id="send-button">发送</button>
      </form>
    </div>
  </div>
  <script>
    const messagesEl = document.getElementById("messages");
    const chatEl = document.getElementById("chat");
    const composer = document.getElementById("composer");
    const textInput = document.getElementById("text-input");
    const sendButton = document.getElementById("send-button");
    const pickFileButton = document.getElementById("pick-file");
    const fileInput = document.getElementById("file-input");
    const statusEl = document.getElementById("composer-status");
    const progressEl = document.getElementById("progress");
    const progressBar = document.getElementById("progress-bar");

    const FILE_ICON =
      '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">' +
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6" /></svg>';

    let lastId = Number("__LAST_ID__") || 0;
    let chatVersion = Number("__CHAT_VERSION__") || 1;
    const renderedIds = new Set();
    let statusTimer = null;

    function setStatus(message, isError = false) {
      window.clearTimeout(statusTimer);
      statusEl.textContent = message || "";
      statusEl.classList.toggle("is-error", Boolean(isError));
      if (message) {
        statusTimer = window.setTimeout(() => {
          statusEl.textContent = "";
          statusEl.classList.remove("is-error");
        }, 4000);
      }
    }

    function formatSize(size) {
      const units = ["B", "KB", "MB", "GB"];
      let value = Number(size) || 0;
      let unit = units[0];
      for (const candidate of units) {
        unit = candidate;
        if (value < 1024 || candidate === "GB") break;
        value /= 1024;
      }
      return `${value.toFixed(unit === "B" ? 0 : 1)} ${unit}`;
    }

    function clockText(seconds) {
      const date = new Date((Number(seconds) || 0) * 1000);
      if (Number.isNaN(date.getTime())) return "";
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    function scrollToEnd(force) {
      const distance = chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight;
      if (force || distance < 120) chatEl.scrollTop = chatEl.scrollHeight;
    }

    function messageElement(message) {
      const outgoing = message.sender === "phone";
      const item = document.createElement("li");
      item.className = "message " + (outgoing ? "out" : "in");
      item.dataset.id = message.id;

      const meta = document.createElement("p");
      meta.className = "message-meta";
      const who = document.createElement("span");
      who.textContent = `${outgoing ? "本机" : "电脑"} · ${clockText(message.time)}`;
      meta.append(who);

      if (message.kind === "file") {
        const card = document.createElement("a");
        card.className = "file-card";
        card.href = message.url;
        card.setAttribute("download", "");
        const icon = document.createElement("span");
        icon.className = "file-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.innerHTML = FILE_ICON;
        const info = document.createElement("span");
        info.className = "file-info";
        const name = document.createElement("span");
        name.className = "file-name";
        name.textContent = message.name;
        const size = document.createElement("span");
        size.className = "file-size";
        size.textContent = `${formatSize(message.size)} · 点击下载`;
        info.append(name, size);
        card.append(icon, info);
        item.append(meta, card);
        return item;
      }

      const copyButton = document.createElement("button");
      copyButton.type = "button";
      copyButton.className = "copy-button";
      copyButton.textContent = "复制";
      meta.append(copyButton);

      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = message.text;
      item.append(meta, bubble);
      return item;
    }

    function appendMessage(message) {
      if (!message || renderedIds.has(message.id)) return;
      renderedIds.add(message.id);
      if (message.id > lastId) lastId = message.id;
      messagesEl.append(messageElement(message));
    }

    function resetMessages(version) {
      renderedIds.clear();
      lastId = 0;
      chatVersion = version;
      messagesEl.textContent = "";
    }

    async function copyText(text, element) {
      if (navigator.clipboard && window.isSecureContext) {
        try {
          await navigator.clipboard.writeText(text);
          return true;
        } catch (error) {
          // 继续尝试下方的兼容方案
        }
      }
      // 局域网 HTTP 页面没有剪贴板 API，改用选区加 execCommand。
      try {
        const range = document.createRange();
        range.selectNodeContents(element);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        if (document.execCommand("copy")) {
          selection.removeAllRanges();
          return true;
        }
      } catch (error) {
        // 保留选中状态，提示用户手动复制
      }
      return false;
    }

    messagesEl.addEventListener("click", async (event) => {
      const button = event.target.closest(".copy-button");
      if (!button) return;
      const message = button.closest(".message");
      const bubble = message ? message.querySelector(".bubble") : null;
      if (!bubble) return;
      const copied = await copyText(bubble.textContent, bubble);
      button.textContent = copied ? "已复制" : "长按复制";
      window.setTimeout(() => {
        button.textContent = "复制";
      }, 1800);
    });

    function resizeInput() {
      textInput.style.height = "auto";
      textInput.style.height = `${Math.min(textInput.scrollHeight, 132)}px`;
    }

    textInput.addEventListener("input", resizeInput);
    textInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        if (composer.requestSubmit) {
          composer.requestSubmit();
        } else {
          composer.dispatchEvent(new Event("submit", { cancelable: true }));
        }
      }
    });

    composer.addEventListener("submit", async (event) => {
      event.preventDefault();
      const value = textInput.value;
      if (!value.trim()) {
        setStatus("请输入要发送的文本。", true);
        textInput.focus();
        return;
      }
      sendButton.disabled = true;
      try {
        const response = await fetch("/text", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ text: value }),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "发送失败，请稍后重试。");
        }
        textInput.value = "";
        resizeInput();
        appendMessage(result.message);
        scrollToEnd(true);
        setStatus("已发送到电脑。");
      } catch (error) {
        setStatus(error.message || "发送失败，请稍后重试。", true);
      } finally {
        sendButton.disabled = false;
        textInput.focus();
      }
    });

    function showProgress(percent, message) {
      progressEl.hidden = false;
      progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
      setStatus(message);
    }

    function hideProgress() {
      progressEl.hidden = true;
      progressBar.style.width = "0%";
    }

    function uploadFiles(files) {
      const form = new FormData();
      files.forEach((file) => form.append("file", file, file.name));
      const request = new XMLHttpRequest();
      request.open("POST", "/");
      request.setRequestHeader("Accept", "application/json");
      request.upload.addEventListener("progress", (event) => {
        if (!event.lengthComputable) return;
        showProgress((event.loaded / event.total) * 100, `正在上传 ${files.length} 个文件…`);
      });
      request.addEventListener("load", () => {
        hideProgress();
        let result = {};
        try {
          result = JSON.parse(request.responseText);
        } catch (error) {
          result = {};
        }
        if (request.status !== 200 || !result.ok) {
          setStatus(result.error || "上传失败，请稍后重试。", true);
          return;
        }
        (result.messages || []).forEach(appendMessage);
        scrollToEnd(true);
        setStatus(`已发送 ${files.length} 个文件到电脑。`);
      });
      request.addEventListener("error", () => {
        hideProgress();
        setStatus("上传失败，请检查网络后重试。", true);
      });
      request.addEventListener("abort", () => {
        hideProgress();
        setStatus("已取消上传。", true);
      });
      showProgress(0, `准备上传 ${files.length} 个文件…`);
      request.send(form);
    }

    pickFileButton.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", () => {
      const files = Array.from(fileInput.files || []);
      fileInput.value = "";
      if (files.length) uploadFiles(files);
    });

    document.getElementById("chat-clear").addEventListener("click", async () => {
      if (!window.confirm("清空当前会话的聊天记录？清空后无法恢复。")) return;
      try {
        const response = await fetch("/chat/clear", {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "清空失败，请稍后重试。");
        }
        const version = Number(result.version);
        if (Number.isFinite(version)) resetMessages(version);
        setStatus("聊天记录已清空。");
      } catch (error) {
        setStatus(error.message || "清空失败，请稍后重试。", true);
      }
    });

    async function pollMessages() {
      try {
        const response = await fetch(
          `/chat/messages?since=${lastId}&version=${chatVersion}`,
          { cache: "no-store" }
        );
        if (!response.ok) return;
        const result = await response.json();
        const version = Number(result.version);
        if (Number.isFinite(version) && version !== chatVersion) {
          resetMessages(version);
        }
        const messages = result.messages || [];
        if (!messages.length) return;
        messages.forEach(appendMessage);
        scrollToEnd();
      } catch (error) {
        // 网络短暂中断时保持界面不变，下一轮会自动重试
      }
    }

    resizeInput();
    chatEl.scrollTop = chatEl.scrollHeight;
    pollMessages();
    window.setInterval(pollMessages, 2000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) pollMessages();
    });
  </script>
</body>

</html>"""


FILES_PAGE = """<!doctype html>
<html lang="zh-CN">

<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f3f7fa">
  <title>共享文件 - PyDrop</title>
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

    main { width: min(100% - 32px, 640px); margin: 0 auto; padding: 24px 0 40px; }

    .brand { display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 750; }

    .brand-icon {
      display: grid;
      place-items: center;
      width: 36px;
      height: 36px;
      border-radius: 12px;
      background: var(--accent);
      color: #fff;
      box-shadow: 0 5px 12px #087e8b20;
    }

    .icon {
      width: 20px;
      height: 20px;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .back {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 36px;
      margin: 18px 0;
      padding: 6px 14px;
      border: 1px solid #d4e7eb;
      border-radius: 999px;
      background: #eff7f9;
      color: var(--accent-dark);
      font-size: 13px;
      font-weight: 650;
      text-decoration: none;
    }

    .card {
      padding: 22px;
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: 0 8px 30px #25465b06;
    }

    .section-heading { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }

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

    h1 { margin: 0; font-size: 17px; font-weight: 650; }
    .section-description { margin: 2px 0 0; color: var(--muted); font-size: 12px; }

    ul { padding: 0; margin: 0; list-style: none; }

    li {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px 0;
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

    .download {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 72px;
      min-height: 40px;
      padding: 8px 16px;
      border: 1px solid #d4e7eb;
      border-radius: 11px;
      background: #eff7f9;
      color: var(--accent-dark);
      font-size: 14px;
      font-weight: 600;
      text-decoration: none;
      white-space: nowrap;
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

    @media (hover: hover) {
      .back:hover { background: #deeff3; }
      .download:hover { background: #deeff3; }
      .file-name:hover { color: var(--accent); text-decoration: underline; }
    }

    @media (max-width: 480px) {
      main { width: calc(100% - 24px); }
      .card { padding: 18px 14px; }
      li { gap: 12px; }
      .download { min-width: 64px; padding-inline: 12px; }
    }
  </style>
</head>

<body>
  <main>
    <header class="brand">
      <span class="brand-icon" aria-hidden="true">
        <svg class="icon" viewBox="0 0 24 24">
          <path d="M7 16V4m-4 4 4-4 4 4M17 8v12m-4-4 4 4 4-4" />
        </svg>
      </span>
      PyDrop
    </header>
    <a class="back" href="/">
      <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="m15 18-6-6 6-6" />
      </svg>
      返回聊天
    </a>
    <section class="card">
      <div class="section-heading">
        <span class="section-number" aria-hidden="true">__COUNT__</span>
        <div>
          <h1>共享文件</h1>
          <p class="section-description">电脑共享目录中的文件，点击文件名或下载按钮保存到此设备</p>
        </div>
      </div>
      __FILES__
    </section>
  </main>
</body>

</html>"""

FILE_ICON_HTML = (
    '<span class="file-icon" aria-hidden="true">'
    '<svg class="icon" viewBox="0 0 24 24">'
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6" />'
    "</svg></span>"
)


def format_size(size):
    """把字节数格式化成便于阅读的字符串。"""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024


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


def open_local_path(path):
    """使用当前平台的默认程序打开文件或目录。"""
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        opener = shutil.which("xdg-open")
        if not opener:
            raise RuntimeError("找不到 xdg-open，无法打开文件")
        subprocess.Popen([opener, path])


def open_shared_dir():
    """使用当前平台的文件管理器打开共享目录。"""
    open_local_path(SHARED_DIR)


def place_shared_file(source):
    """把本机文件放进共享目录，返回共享目录中的目标路径。

    同名且大小相同的文件视为同一个文件，不会重复复制；同名但内容长度不同
    时另存为带随机后缀的文件名，避免覆盖共享目录中的已有文件。
    """
    source = Path(source)
    target = SHARED_DIR / source.name
    if target.exists():
        try:
            if source.resolve() == target.resolve():
                return target
            if target.stat().st_size == source.stat().st_size:
                return target
        except OSError:
            pass
        target = SHARED_DIR / f"{source.stem}_{uuid.uuid4().hex[:8]}{source.suffix}"
    shutil.copy2(source, target)
    return target


def message_html(message):
    """把一条聊天记录渲染成网页中的气泡（网页端就是手机端）。"""
    outgoing = message["sender"] == "phone"
    side = "out" if outgoing else "in"
    clock = time.strftime("%H:%M", time.localtime(message.get("time") or time.time()))
    who = "本机" if outgoing else "电脑"
    meta = f"<span>{who} · {clock}</span>"
    if message["kind"] == "file":
        href = html.escape("/files/" + quote(message["name"]), quote=True)
        body = (
            f'<a class="file-card" href="{href}" download>'
            f"{FILE_ICON_HTML}"
            '<span class="file-info">'
            f'<span class="file-name">{html.escape(message["name"])}</span>'
            f'<span class="file-size">{format_size(message["size"])} · 点击下载</span>'
            "</span></a>"
        )
    else:
        meta += '<button type="button" class="copy-button">复制</button>'
        body = f'<div class="bubble">{html.escape(message["text"])}</div>'
    return (
        f'<li class="message {side}" data-id="{message["id"]}">'
        f'<p class="message-meta">{meta}</p>{body}</li>'
    )


def public_message(message):
    """网页接口返回的消息结构，去掉本机文件路径。"""
    payload = {key: value for key, value in message.items() if key != "path"}
    if message["kind"] == "file":
        payload["url"] = "/files/" + quote(message["name"])
    return payload


class ChatLog:
    """会话级聊天记录。

    文本和文件消息都只保存在内存中：不写入磁盘、不保留历史记录，程序退出后
    即消失。共享目录里的文件会作为电脑发出的消息出现在聊天窗口中，方便手机
    直接下载；这类消息只回填最近修改的一部分，其余文件仍可在共享文件页面下载。
    """

    MAX_MESSAGES = 400  # 防止长时间运行后内存无限增长
    BACKFILL_LIMIT = 40  # 共享目录回填进聊天窗口的最大文件数
    SENDERS = ("phone", "computer")

    def __init__(self):
        self._lock = threading.Lock()
        self._messages = []
        self._next_id = 1
        self._version = 1
        self._shared_dir = None
        self._known_files = set()

    # ---- 写入（调用 _append 前必须持有锁）----
    def _append(self, message):
        message["id"] = self._next_id
        message["time"] = time.time()
        self._next_id += 1
        self._messages.append(message)
        overflow = len(self._messages) - self.MAX_MESSAGES
        if overflow > 0:
            del self._messages[:overflow]
        return dict(message)

    def add_text(self, sender, text):
        """记录一条文本消息并返回副本；内容不合法时抛出异常。"""
        if sender not in self.SENDERS:
            raise ValueError("未知的发送方")
        if not isinstance(text, str):
            raise TypeError("文本内容格式不正确")
        if not text.strip():
            raise ValueError("文本内容不能为空")
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(f"文本不能超过 {MAX_TEXT_LENGTH} 个字符")
        with self._lock:
            return self._append(
                {"kind": "text", "sender": sender, "source": "chat", "text": text}
            )

    def add_file(self, sender, name, size, path=None, source="chat"):
        """记录一条文件消息；文件本体已经保存在共享目录中。"""
        if sender not in self.SENDERS:
            raise ValueError("未知的发送方")
        if not name:
            raise ValueError("文件名不能为空")
        with self._lock:
            self._known_files.add(name)
            return self._append(
                {
                    "kind": "file",
                    "sender": sender,
                    "source": source,
                    "name": name,
                    "size": int(size),
                    "path": str(path) if path else str(SHARED_DIR / name),
                }
            )

    def clear(self):
        """清空当前会话的聊天记录，只影响内存。"""
        with self._lock:
            self._messages.clear()
            self._version += 1
            return self._version

    # ---- 读取 ----
    def version(self):
        with self._lock:
            return self._version

    def snapshot(self, since=0, sources=None):
        """返回 (版本号, 消息副本列表)，供本机 GUI 使用。"""
        with self._lock:
            messages = [
                dict(message)
                for message in self._messages
                if message["id"] > since
                and (sources is None or message["source"] in sources)
            ]
            return self._version, messages

    # ---- 共享目录 ----
    def sync_shared_files(self, directory):
        """把共享目录中的文件同步成电脑发出的消息，返回新增数量。"""
        directory = Path(directory)
        entries = self._scan_shared_dir(directory)
        if entries is None:
            return 0

        with self._lock:
            first_scan = self._shared_dir != directory
            if first_scan:
                self._shared_dir = directory
                self._known_files = set()
                self._messages = [
                    message
                    for message in self._messages
                    if message["source"] != "shared"
                ]
                self._version += 1

            existing = {name for name, _size, _time, _path in entries}
            self._known_files &= existing
            # 文件被移出共享目录后，对应的气泡也一起消失
            self._messages = [
                message
                for message in self._messages
                if message["source"] != "shared" or message.get("name") in existing
            ]

            if first_scan and len(entries) > self.BACKFILL_LIMIT:
                backfill_from = len(entries) - self.BACKFILL_LIMIT
            else:
                backfill_from = 0

            added = 0
            for index, (name, size, _time, path) in enumerate(entries):
                if name in self._known_files:
                    continue
                # 已记录过的文件名不再重复回填，避免每次扫描都产生新气泡
                self._known_files.add(name)
                if index < backfill_from:
                    # 首次扫描只回填最近修改的一部分，其余文件仍可在共享文件页面下载
                    continue
                self._append(
                    {
                        "kind": "file",
                        "sender": "computer",
                        "source": "shared",
                        "name": name,
                        "size": size,
                        "path": str(path),
                    }
                )
                added += 1
            return added

    @staticmethod
    def _scan_shared_dir(directory):
        """按修改时间从早到晚列出共享目录中的文件。"""
        entries = []
        try:
            with os.scandir(directory) as scanner:
                for entry in scanner:
                    if entry.name.startswith("."):
                        continue
                    try:
                        if not entry.is_file():
                            continue
                        stat = entry.stat()
                    except OSError:
                        continue
                    entries.append(
                        (entry.name, stat.st_size, stat.st_mtime, Path(entry.path))
                    )
        except OSError:
            return None
        entries.sort(key=lambda item: item[2])
        return entries


CHAT_LOG = ChatLog()


class FileTransferServer(ThreadingHTTPServer):
    """忽略客户端中途断开连接产生的噪声异常。

    浏览器常会在正式请求前建立预连接，用户取消上传或关闭页面时也会直接
    重置连接。这类 ConnectionError 不影响服务端，不应打印完整 traceback。
    """

    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


class App:
    QR_SIZE = 256
    SEND_PLACEHOLDER = "输入要发送到手机的文本，Ctrl+Enter 发送"
    CHAT_POLL_MS = 700
    SHARED_SYNC_SECONDS = 5.0

    def __init__(self):
        self.server = None
        self.server_thread = None
        self.feedback_job = None
        self.chat_poll_job = None
        self.chat_version = 1
        self.last_message_id = 0
        self.last_shared_sync = 0.0
        self.root = tk.Tk()
        self.root.title("PyDrop - 局域网文件互传")
        self.root.configure(bg="#f3f6fa")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.set_window_icon()

        self.start_server()
        self.build_ui()
        self.refresh_address()
        self.start_chat_polling()
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
            self.server = FileTransferServer((HOST, PORT), Handler)
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
            "chat": "#f7f9fc",
            "bubble_in": "#e9eff8",
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
        content.columnconfigure(2, weight=1)
        content.rowconfigure(1, weight=1)

        header = tk.Frame(content, bg=colors["background"])
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 20))
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
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

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
            text="使用手机相机扫描\n在浏览器中互传文件与文本",
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
            wraplength=280,
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

        chat_card = tk.Frame(
            content,
            bg=colors["card"],
            highlightbackground=colors["border"],
            highlightthickness=1,
            padx=16,
            pady=16,
        )
        chat_card.grid(row=1, column=2, sticky="nsew", padx=(20, 0))
        chat_card.columnconfigure(0, weight=1)
        chat_card.rowconfigure(2, weight=1)

        chat_head = tk.Frame(chat_card, bg=colors["card"])
        chat_head.grid(row=0, column=0, sticky="ew")
        chat_head.columnconfigure(0, weight=1)
        tk.Label(
            chat_head,
            text="聊天窗口",
            bg=colors["card"],
            fg=colors["text"],
            font=heading_font,
        ).grid(row=0, column=0, sticky="w")
        self.action_button(chat_head, "清空记录", self.clear_chat).grid(
            row=0, column=1, sticky="e"
        )
        tk.Label(
            chat_card,
            text="聊天记录只保存在内存里，关闭程序后即消失。",
            bg=colors["card"],
            fg=colors["muted"],
            font=self.small_font,
            wraplength=310,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        # 边框画在外层 Frame 上：聊天框本身不画焦点框，选中文字时也不会出现描边
        chat_area = tk.Frame(
            chat_card,
            bg=colors["chat"],
            highlightthickness=1,
            highlightbackground=colors["border"],
        )
        chat_area.grid(row=2, column=0, sticky="nsew")
        chat_area.columnconfigure(0, weight=1)
        chat_area.rowconfigure(0, weight=1)

        self.chat_box = tk.Text(
            chat_area,
            height=14,
            width=34,
            wrap="word",
            state="disabled",
            cursor="arrow",
            font=self.body_font,
            fg=colors["text"],
            bg=colors["chat"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            selectborderwidth=0,
            selectbackground="#bfdbfe",
            selectforeground=colors["text"],
            padx=8,
            pady=8,
        )
        self.chat_box.grid(row=0, column=0, sticky="nsew")
        chat_scroll = tk.Scrollbar(
            chat_area,
            command=self.chat_box.yview,
            orient="vertical",
            width=10,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            troughcolor=colors["chat"],
            bg=colors["border"],
            activebackground="#b8c6da",
        )
        chat_scroll.grid(row=0, column=1, sticky="ns", padx=(2, 0))
        self.chat_box.configure(yscrollcommand=chat_scroll.set)
        self.configure_chat_tags()
        # 每条消息单独记录，右键菜单可以只复制光标下的那一条
        self.chat_file_tags = {}
        self.chat_message_tags = {}
        self.attach_chat_menu()
        self.chat_box.bind("<Button-1>", self.on_chat_click)
        self.chat_box.bind("<Motion>", self.on_chat_motion)
        self.chat_box.bind("<Leave>", self.on_chat_leave)

        self.text_input = self.text_box(chat_card, height=3)
        self.text_input.grid(row=3, column=0, sticky="ew", pady=(12, 8))
        self.text_input.bind("<Control-Return>", self.send_text_shortcut)
        self.text_input.bind("<Command-Return>", self.send_text_shortcut)
        self.text_input.bind("<FocusIn>", self.on_input_focus_in)
        self.text_input.bind("<FocusOut>", self.on_input_focus_out)
        self.input_placeholder = False
        self.show_input_placeholder()

        input_actions = tk.Frame(chat_card, bg=colors["card"])
        input_actions.grid(row=4, column=0, sticky="ew")
        input_actions.columnconfigure(0, weight=1)
        self.action_button(
            input_actions, "选择文件并发送", self.send_file_to_phone
        ).grid(row=0, column=0, sticky="w")
        self.action_button(
            input_actions, "发送文本", self.send_text_to_phone, primary=True
        ).grid(row=0, column=1, sticky="e")

        tk.Label(
            content,
            textvariable=self.status,
            bg=colors["background"],
            fg=colors["muted"],
            font=self.small_font,
            anchor="w",
        ).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(18, 0))

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
        # Aqua 会用原生灰色按钮外观覆盖自定义背景色，白色文字在 macOS
        # 上对比度不足；改用品牌蓝，其他平台仍保持白字蓝底。
        primary_foreground = (
            self.colors["primary"] if sys.platform == "darwin" else "white"
        )
        primary_active_foreground = (
            self.colors["primary_active"] if sys.platform == "darwin" else "white"
        )
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=self.colors["primary"] if primary else self.colors["card"],
            fg=primary_foreground if primary else self.colors["primary"],
            activebackground=self.colors["primary_active"] if primary else "#e6edfa",
            activeforeground=(
                primary_active_foreground if primary else self.colors["primary_active"]
            ),
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

    def text_box(self, parent, height):
        """创建可以选中、复制和粘贴的多行输入框。"""
        box = tk.Text(
            parent,
            height=height,
            width=28,
            wrap="word",
            font=self.body_font,
            fg=self.colors["text"],
            bg=self.colors["card"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["primary"],
            selectbackground=self.colors["primary"],
            selectforeground="white",
            insertbackground=self.colors["text"],
            padx=10,
            pady=8,
            spacing1=2,
            spacing3=2,
            undo=True,
        )
        self.attach_text_menu(box)
        return box

    def attach_text_menu(self, box):
        """为输入框补上右键菜单和显式复制/粘贴快捷键。"""
        menu = tk.Menu(box, tearoff=False)
        menu.add_command(label="剪切", command=lambda: box.event_generate("<<Cut>>"))
        menu.add_command(label="复制", command=lambda: self.copy_widget_selection(box))
        menu.add_command(label="粘贴", command=lambda: box.event_generate("<<Paste>>"))
        menu.add_command(label="全选", command=lambda: self.select_all_text(box))
        menu.add_separator()
        menu.add_command(label="清空输入", command=self.clear_text_input)
        for sequence in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            box.bind(sequence, lambda event, m=menu: self.popup_text_menu(event, m))
        box.bind("<Control-c>", lambda _event: self.copy_widget_selection(box))
        box.bind("<Command-c>", lambda _event: self.copy_widget_selection(box))

    def popup_text_menu(self, event, menu):
        try:
            event.widget.focus_set()
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    @staticmethod
    def select_all_text(box):
        box.tag_add("sel", "1.0", "end-1c")
        box.mark_set("insert", "1.0")
        box.focus_set()

    @staticmethod
    def selected_text(box):
        """返回文本框中的选中内容，没有选中时返回空字符串。"""
        try:
            return box.get("sel.first", "sel.last")
        except tk.TclError:
            return ""

    def copy_widget_selection(self, box):
        """复制选中内容；没有选中时复制整个文本框。"""
        text = self.selected_text(box) or self.widget_text(box)
        if text:
            self.write_clipboard(text)
        return "break"

    def widget_text(self, box):
        """文本框的真实内容，忽略输入框中的占位提示。"""
        if box is getattr(self, "text_input", None):
            return self.input_value()
        return box.get("1.0", "end-1c")

    def write_clipboard(self, text):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            self.show_status("复制失败，请选中文本后手动复制。")
            return False
        return True

    # ---- 聊天窗口 ----
    def configure_chat_tags(self):
        """用文本标签模拟聊天气泡：左侧是收到的，右侧是发出的。"""
        colors = self.colors
        box = self.chat_box
        # 选中文字只改背景色，不画任何描边
        box.tag_configure("sel", borderwidth=0, relief="flat")
        box.tag_configure(
            "placeholder",
            foreground=colors["muted"],
            font=self.small_font,
            justify="left",
            spacing1=8,
            lmargin1=4,
            lmargin2=4,
        )
        box.tag_configure(
            "in_meta",
            foreground=colors["muted"],
            font=self.small_font,
            justify="left",
            spacing1=6,
        )
        box.tag_configure(
            "out_meta",
            foreground=colors["muted"],
            font=self.small_font,
            justify="right",
            spacing1=6,
        )
        box.tag_configure(
            "in",
            background=colors["bubble_in"],
            foreground=colors["text"],
            font=self.body_font,
            justify="left",
            spacing1=4,
            spacing3=4,
        )
        box.tag_configure(
            "out",
            background=colors["primary"],
            foreground="#ffffff",
            font=self.body_font,
            justify="right",
            spacing1=4,
            spacing3=4,
        )
        box.tag_configure(
            "in_file",
            background=colors["bubble_in"],
            foreground=colors["primary"],
            font=self.body_font,
            justify="left",
            underline=True,
            spacing1=4,
            spacing3=4,
        )
        box.tag_configure(
            "out_file",
            background=colors["primary"],
            foreground="#ffffff",
            font=self.body_font,
            justify="right",
            underline=True,
            spacing1=4,
            spacing3=4,
        )

    def start_chat_polling(self):
        """首次绘制聊天窗口，并开始轮询手机发来的消息。"""
        self.sync_shared_files(force=True)
        self.chat_version = CHAT_LOG.version()
        self.render_chat()
        _version, messages = CHAT_LOG.snapshot()
        self.last_message_id = max((m["id"] for m in messages), default=0)
        self.chat_poll_job = self.root.after(self.CHAT_POLL_MS, self.poll_chat)

    def sync_shared_files(self, force=False):
        """把共享目录中的新文件同步进聊天记录，避免频繁扫描目录。"""
        now = time.monotonic()
        if not force and now - self.last_shared_sync < self.SHARED_SYNC_SECONDS:
            return
        self.last_shared_sync = now
        CHAT_LOG.sync_shared_files(SHARED_DIR)

    def poll_chat(self):
        """轮询聊天记录：只要最新消息，不保留历史。"""
        self.sync_shared_files()
        version, messages = CHAT_LOG.snapshot(since=self.last_message_id)
        for message in messages:
            self.last_message_id = max(self.last_message_id, message["id"])
        if version != self.chat_version:
            # 记录被清空或切换了共享目录，整体重绘
            self.chat_version = version
            self.render_chat()
        elif messages:
            self.append_chat_messages(messages)
            incoming = [m for m in messages if m["sender"] == "phone"]
            if incoming:
                self.announce(incoming[-1])
        self.chat_poll_job = self.root.after(self.CHAT_POLL_MS, self.poll_chat)

    def announce(self, message):
        if message["kind"] == "file":
            self.show_status(f"收到手机发来的文件：{message['name']}")
        else:
            self.show_status(
                f"收到手机发来的文本（{len(message['text'])} 字），可选中复制。"
            )

    def render_chat(self):
        """整体重绘聊天窗口；仅在清空记录或切换共享目录后调用。"""
        box = self.chat_box
        _version, messages = CHAT_LOG.snapshot(sources=("chat",))
        self.chat_file_tags.clear()
        self.chat_message_tags.clear()
        box.configure(state="normal")
        box.delete("1.0", "end")
        if messages:
            for message in messages:
                self.insert_chat_message(message)
        else:
            box.insert(
                "end",
                "还没有消息。\n在下方输入文字后点击「发送文本」，或点击「选择文件并发送」。",
                ("placeholder",),
            )
        box.configure(state="disabled")
        box.see("end")

    def append_chat_messages(self, messages):
        """在末尾追加新消息；只增加内容，不打断用户正在进行的选中操作。"""
        visible = [message for message in messages if message["source"] == "chat"]
        if not visible:
            return
        box = self.chat_box
        at_bottom = box.yview()[1] >= 0.98
        box.configure(state="normal")
        if box.tag_ranges("placeholder"):
            box.delete("1.0", "end")
        for message in visible:
            self.insert_chat_message(message)
        box.configure(state="disabled")
        if at_bottom:
            box.see("end")

    def insert_chat_message(self, message):
        """把一条消息写进只读文本框；文字可以直接选中、复制。"""
        box = self.chat_box
        outgoing = message["sender"] == "computer"
        side = "out" if outgoing else "in"
        # 每条消息一个专属标签，右键时可以定位到具体是哪一条
        tag = f"msg_{message['id']}"
        self.chat_message_tags[tag] = message
        stamp = time.strftime(
            "%H:%M", time.localtime(message.get("time") or time.time())
        )
        who = "电脑" if outgoing else "手机"
        box.insert("end", f"{who} · {stamp}\n", (f"{side}_meta", tag))
        if message["kind"] == "file":
            size = format_size(message.get("size", 0))
            file_tag = f"file_{message['id']}"
            # 首尾空格充当气泡内边距，让文字不贴着背景边缘
            box.insert(
                "end",
                f"  [文件] {message['name']}（{size}）点击打开  \n",
                (f"{side}_file", tag, file_tag),
            )
            path = message.get("path")
            if path:
                self.chat_file_tags[file_tag] = path
        else:
            box.insert("end", self.pad_bubble(message["text"]) + "\n", (side, tag))
        box.insert("end", "\n", (tag,))

    def file_path_at(self, x, y):
        """返回指定位置的文件路径；不在文件气泡上时返回 None。"""
        try:
            names = self.chat_box.tag_names(self.chat_box.index(f"@{x},{y}"))
        except tk.TclError:
            return None
        for name in names:
            if name in self.chat_file_tags:
                return self.chat_file_tags[name]
        return None

    def message_at(self, x, y):
        """返回指定位置的消息；不在任何消息上时返回 None。"""
        try:
            names = self.chat_box.tag_names(self.chat_box.index(f"@{x},{y}"))
        except tk.TclError:
            return None
        for name in names:
            if name in self.chat_message_tags:
                return self.chat_message_tags[name]
        return None

    def attach_chat_menu(self):
        """聊天窗口专用的右键菜单：可以单独复制光标下的那一条消息。"""
        # 每次都复用同一个菜单对象，只重建菜单项，避免反复创建 Tk 菜单
        self.chat_menu = tk.Menu(self.chat_box, tearoff=False)
        for sequence in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            self.chat_box.bind(sequence, self.popup_chat_menu)
        self.chat_box.bind(
            "<Control-c>", lambda _event: self.copy_widget_selection(self.chat_box)
        )
        self.chat_box.bind(
            "<Command-c>", lambda _event: self.copy_widget_selection(self.chat_box)
        )

    def popup_chat_menu(self, event):
        menu = self.chat_menu
        menu.delete(0, "end")
        message = self.message_at(event.x, event.y)
        if message is not None:
            if message["kind"] == "file":
                menu.add_command(
                    label="复制文件名",
                    command=lambda item=message: self.copy_chat_message(item),
                )
                menu.add_command(
                    label="复制文件路径",
                    command=lambda item=message: self.copy_chat_message(
                        item, path=True
                    ),
                )
            else:
                menu.add_command(
                    label="复制这条消息",
                    command=lambda item=message: self.copy_chat_message(item),
                )
            menu.add_separator()
        if self.selected_text(self.chat_box):
            menu.add_command(
                label="复制选中内容",
                command=lambda: self.copy_widget_selection(self.chat_box),
            )
        menu.add_command(
            label="全选", command=lambda: self.select_all_text(self.chat_box)
        )
        try:
            self.chat_box.focus_set()
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def copy_chat_message(self, message, path=False):
        """复制一整条消息，不包含时间戳和气泡里的额外空格。"""
        if path:
            text = message.get("path") or ""
        elif message["kind"] == "file":
            text = message["name"]
        else:
            text = message["text"]
        if not text:
            return
        if self.write_clipboard(text):
            preview = " ".join(text.split())
            if len(preview) > 16:
                preview = preview[:16] + "…"
            self.show_status(f"已复制：{preview}")

    def on_chat_click(self, event):
        path = self.file_path_at(event.x, event.y)
        if path:
            self.open_path(path)
            return "break"
        return None

    def on_chat_motion(self, event):
        cursor = "hand2" if self.file_path_at(event.x, event.y) else "arrow"
        if self.chat_box.cget("cursor") != cursor:
            self.chat_box.configure(cursor=cursor)

    def on_chat_leave(self, _event=None):
        self.chat_box.configure(cursor="arrow")

    @staticmethod
    def pad_bubble(text):
        """给气泡文字加上左右内边距。"""
        return "  " + text.replace("\n", "  \n  ") + "  "

    def clear_chat(self):
        """清空当前会话的聊天记录（不影响磁盘上的文件）。"""
        self.chat_version = CHAT_LOG.clear()
        self.render_chat()
        self.show_status("已清空当前会话的聊天记录，手机页面会同步清空。")

    # ---- 输入框 ----
    def show_input_placeholder(self):
        """空输入框显示浅色提示，与网页端 placeholder 保持一致。"""
        self.text_input.delete("1.0", "end")
        self.text_input.insert("1.0", self.SEND_PLACEHOLDER)
        self.text_input.tag_add("placeholder", "1.0", "end")
        self.text_input.tag_config("placeholder", foreground=self.colors["muted"])
        self.text_input.edit_reset()
        self.input_placeholder = True

    def on_input_focus_in(self, _event=None):
        if self.input_placeholder:
            self.text_input.delete("1.0", "end")
            self.text_input.edit_reset()
            self.input_placeholder = False

    def on_input_focus_out(self, _event=None):
        if not self.text_input.get("1.0", "end-1c").strip():
            self.show_input_placeholder()

    def input_value(self):
        """返回输入框中的真实文本，忽略占位提示。"""
        if self.input_placeholder:
            return ""
        return self.text_input.get("1.0", "end-1c")

    def send_text_shortcut(self, _event=None):
        self.send_text_to_phone()
        return "break"

    def send_text_to_phone(self):
        text = self.input_value()
        if not text.strip():
            self.show_status("请先输入要发送到手机的文本。")
            self.text_input.focus_set()
            return
        try:
            CHAT_LOG.add_text("computer", text)
        except (TypeError, ValueError) as exc:
            self.show_status(str(exc))
            return
        self.clear_text_input()
        self.show_status("文本已发送，手机页面会自动显示。")

    def clear_text_input(self):
        self.text_input.delete("1.0", "end")
        self.text_input.edit_reset()
        self.input_placeholder = False
        self.text_input.focus_set()

    # ---- 文件 ----
    def send_file_to_phone(self):
        """把本机文件放进共享目录，并在聊天窗口中显示为发出的消息。"""
        selected = filedialog.askopenfilenames(
            parent=self.root,
            title="选择要发送到手机的文件",
        )
        if not selected:
            return

        sent = 0
        failures = []
        for raw in selected:
            source = Path(raw)
            try:
                target = place_shared_file(source)
                stat = target.stat()
            except OSError as exc:
                failures.append(f"{source.name}：{exc}")
                continue
            CHAT_LOG.add_file("computer", target.name, stat.st_size, target)
            sent += 1

        if failures:
            messagebox.showerror(
                "部分文件发送失败", "\n".join(failures), parent=self.root
            )
        if sent:
            self.show_status(f"已发送 {sent} 个文件，手机页面可下载。")

    def open_path(self, path):
        try:
            open_local_path(path)
        except (OSError, RuntimeError) as exc:
            messagebox.showerror("无法打开文件", str(exc), parent=self.root)

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
        self.sync_shared_files(force=True)
        self.show_status("共享目录已切换，手机页面会自动更新。")

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
        if self.write_clipboard(self.url):
            self.show_status("地址已复制，可粘贴到同一局域网设备的浏览器中。")

    def open_folder(self):
        try:
            open_shared_dir()
        except (OSError, RuntimeError) as exc:
            messagebox.showerror("无法打开目录", str(exc), parent=self.root)

    def close(self):
        for job in (self.feedback_job, self.chat_poll_job):
            if job is not None:
                self.root.after_cancel(job)
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.root.destroy()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Keep requests working when a windowed build has no stderr stream."""
        if sys.stderr is not None:
            super().log_message(format, *args)

    def reply(
        self, status, body, content_type="text/html; charset=utf-8", headers=None
    ):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def reply_json(self, status, payload):
        # 聊天状态需要实时刷新，禁止浏览器或代理缓存。
        self.reply(
            status,
            json.dumps(payload, ensure_ascii=False),
            "application/json; charset=utf-8",
            {"Cache-Control": "no-store"},
        )

    def reply_error(self, status, message):
        """以 UTF-8 返回错误说明。

        BaseHTTPRequestHandler.send_error 会把消息按 latin-1 编码，中文会直接
        抛出 UnicodeEncodeError 并中断响应，因此这里自己构造响应体。
        """
        self.reply(status, message, "text/plain; charset=utf-8")

    def wants_json(self):
        return "application/json" in self.headers.get("Accept", "")

    # ---- 页面 ----
    def render_chat_page(self):
        """聊天窗口页面：先渲染会话中的消息，之后由前端轮询增量更新。"""
        CHAT_LOG.sync_shared_files(SHARED_DIR)
        version, messages = CHAT_LOG.snapshot()
        last_id = messages[-1]["id"] if messages else 0
        # 先替换标量占位符，最后插入消息，避免消息内容意外命中占位符
        page = PAGE_HEAD.replace("__CHAT_VERSION__", str(version))
        page = page.replace("__LAST_ID__", str(last_id))
        return page.replace(
            "__MESSAGES__", "".join(message_html(message) for message in messages)
        )

    def render_files_page(self):
        """共享目录的完整列表；聊天窗口只回填最近的一部分文件。"""
        files = []
        try:
            items = sorted(SHARED_DIR.iterdir(), key=lambda path: path.name.lower())
        except OSError:
            items = []
        for item in items:
            if item.name.startswith("."):
                continue
            try:
                if not item.is_file():
                    continue
                size = item.stat().st_size
            except OSError:
                continue
            name = html.escape(item.name)
            href = html.escape("/files/" + quote(item.name), quote=True)
            files.append(
                f'<li><div class="file-info">'
                f'<a class="file-name" href="{href}">{name}</a>'
                f'<small class="file-size">{format_size(size)}</small></div>'
                f'<a class="download" href="{href}" download>下载</a></li>'
            )
        listing = (
            "<ul>" + "".join(files) + "</ul>"
            if files
            else '<p class="empty">共享目录为空。</p>'
        )
        page = FILES_PAGE.replace("__COUNT__", str(len(files)))
        return page.replace("__FILES__", listing)

    # ---- GET ----
    def do_GET(self):
        parts = urlsplit(self.path)
        request_path = parts.path
        if request_path == "/chat/messages":
            self.handle_chat_state(parts.query)
            return

        if request_path == "/":
            self.reply(200, self.render_chat_page())
            return

        if request_path == "/files":
            self.reply(200, self.render_files_page())
            return

        if not request_path.startswith("/files/"):
            self.send_error(404)
            return

        self.serve_shared_file(request_path[len("/files/") :])

    def handle_chat_state(self, query):
        """返回聊天记录的增量内容；版本变化时返回全部内容。"""
        params = parse_qs(query)
        try:
            since = int(params.get("since", ["0"])[0])
        except ValueError:
            since = 0
        version = CHAT_LOG.version()
        if params.get("version", [None])[0] != str(version):
            # 记录被清空，或共享目录发生了变化，客户端需要整体重绘
            since = 0
        version, messages = CHAT_LOG.snapshot(since=since)
        self.reply_json(
            200,
            {
                "ok": True,
                "version": version,
                "messages": [public_message(message) for message in messages],
            },
        )

    def serve_shared_file(self, encoded_name):
        """只允许访问共享目录的直接子文件，避免 ../ 路径穿越。"""
        requested_name = unquote(encoded_name)
        if not requested_name or "/" in requested_name or "\\" in requested_name:
            self.send_error(404)
            return
        target = SHARED_DIR / requested_name
        try:
            allowed = target.is_file() and target.parent == SHARED_DIR
        except OSError:
            allowed = False
        if not allowed:
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
        except OSError:
            self.send_error(404)

    # ---- POST ----
    def do_POST(self):
        request_path = urlsplit(self.path).path
        if request_path == "/text":
            self.handle_text_post()
            return
        if request_path == "/chat/clear":
            self.handle_chat_clear()
            return
        if request_path != "/":
            self.send_error(404)
            return
        self.handle_upload_post()

    def handle_text_post(self):
        """接收手机发送的文本，作为一条消息加入当前会话。"""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.reply_json(400, {"ok": False, "error": "请求长度无效"})
            return

        if length <= 0:
            self.reply_json(400, {"ok": False, "error": "没有收到文本内容"})
            return
        if length > MAX_TEXT_BODY:
            self.reply_json(413, {"ok": False, "error": "文本内容过大"})
            return

        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.reply_json(400, {"ok": False, "error": "无法解析文本内容"})
            return

        text = payload.get("text", "") if isinstance(payload, dict) else ""
        try:
            message = CHAT_LOG.add_text("phone", text)
        except (TypeError, ValueError) as exc:
            self.reply_json(400, {"ok": False, "error": str(exc)})
            return

        self.reply_json(200, {"ok": True, "message": public_message(message)})

    def handle_chat_clear(self):
        """清空当前会话的聊天记录；只影响内存，不动磁盘文件。"""
        version = CHAT_LOG.clear()
        if self.wants_json():
            self.reply_json(200, {"ok": True, "version": version})
            return
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_upload_post(self):
        """处理网页表单：既接收文件，也接收没有脚本时提交的文本。"""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.reply_error(400, "请求长度无效")
            return

        if length <= 0:
            self.reply_error(400, "没有收到内容")
            return
        if length > MAX_SIZE:
            self.reply_error(413, "上传内容总大小不能超过 2 GiB")
            return

        body = self.rfile.read(length)
        raw = (
            b"Content-Type: "
            + self.headers.get("Content-Type", "").encode()
            + b"\r\nMIME-Version: 1.0\r\n\r\n"
            + body
        )
        message = BytesParser(policy=default).parsebytes(raw)

        created = []
        errors = []
        for part in message.iter_parts():
            filename = part.get_filename()
            if filename:
                try:
                    created.append(self.save_uploaded_file(part, filename))
                except OSError as exc:
                    errors.append(f"{filename}：{exc}")
                continue

            if part.get_param("name", header="content-disposition") != "text":
                continue
            text = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
            if not text.strip():
                continue
            try:
                created.append(CHAT_LOG.add_text("phone", text))
            except (TypeError, ValueError) as exc:
                errors.append(str(exc))

        if self.wants_json():
            if not created and errors:
                self.reply_json(400, {"ok": False, "error": "；".join(errors)})
                return
            self.reply_json(
                200,
                {
                    "ok": True,
                    "messages": [public_message(item) for item in created],
                    "errors": errors,
                },
            )
            return

        if not created:
            self.reply_error(400, "没有收到可保存的内容")
            return

        # 没有脚本时提交表单，回到聊天页面即可看到新消息
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def save_uploaded_file(self, part, filename):
        """保存上传的文件到共享目录，并记录一条聊天消息。"""
        # 浏览器可能提交 Unix 或 Windows 风格的路径。
        filename = os.path.basename(filename.replace("\\", "/"))
        if not filename:
            filename = "uploaded_file"
        stem = Path(filename).stem or "uploaded_file"
        suffix = Path(filename).suffix
        target = SHARED_DIR / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
        target.write_bytes(part.get_payload(decode=True) or b"")
        return CHAT_LOG.add_file("phone", target.name, target.stat().st_size, target)


if __name__ == "__main__":
    App().root.mainloop()
