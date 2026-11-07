import io
import json
import re
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import main


class RequestSocket:
    def __init__(self, request):
        self.request = io.BytesIO(request)
        self.response = bytearray()

    def makefile(self, *_args):
        return self.request

    def sendall(self, data):
        self.response.extend(data)


class ChatSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        for name, value in (
            ("DEVICE_SESSIONS", main.DeviceSessions()),
            ("CHAT_LOG", main.ChatLog()),
            ("SHARED_DIR", Path(self.directory.name)),
        ):
            patcher = patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def request(self, method, path, body=b"", cookie=None, content_type=None):
        headers = {"Host": "localhost", "Accept": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        if content_type:
            headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(body))
        head = f"{method} {path} HTTP/1.0\r\n"
        head += "".join(f"{key}: {value}\r\n" for key, value in headers.items())
        connection = RequestSocket(head.encode() + b"\r\n" + body)
        with patch.object(main.Handler, "log_message"):
            main.Handler(connection, ("127.0.0.1", 12345), None)
        head, response_body = bytes(connection.response).split(b"\r\n\r\n", 1)
        self.assertIn(b" 200 ", head.split(b"\r\n")[0])
        response_headers = dict(
            line.decode().split(": ", 1) for line in head.split(b"\r\n")[1:]
        )
        return response_headers, response_body

    def send_text(self, cookie, text="原始内容\n  缩进"):
        _, body = self.request(
            "POST",
            "/text",
            json.dumps({"text": text}).encode(),
            cookie,
            "application/json",
        )
        return json.loads(body)["message"]

    def test_browser_session_refresh_clear_and_new_session(self):
        headers, _ = self.request("GET", "/")
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertNotIn("Max-Age", headers["Set-Cookie"])
        self.assertNotIn("Expires", headers["Set-Cookie"])
        first = self.send_text(cookie)
        self.assertRegex(first["device_code"], r"^[A-Z0-9]{5}$")
        self.assertRegex(first["device_code"], r"[A-Z]")
        self.assertRegex(first["device_code"], r"[0-9]")
        self.assertEqual(first["text"], "原始内容\n  缩进")
        self.request("GET", "/", cookie=cookie)
        self.request("POST", "/chat/clear", cookie=cookie)
        self.assertEqual(first["device_code"], self.send_text(cookie)["device_code"])
        headers, _ = self.request("GET", "/")
        other_cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertNotEqual(
            first["device_code"], self.send_text(other_cookie)["device_code"]
        )

    def test_multipart_file_and_text_share_device_code(self):
        headers, _ = self.request("GET", "/")
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        code = self.send_text(cookie)["device_code"]
        body = (
            b'--boundary\r\nContent-Disposition: form-data; name="text"\r\n\r\n'
            b'hello\r\n--boundary\r\nContent-Disposition: form-data; name="files"; '
            b'filename="sample.txt"\r\nContent-Type: text/plain\r\n\r\n'
            b"file contents\r\n--boundary--\r\n"
        )
        _, response = self.request(
            "POST", "/", body, cookie, "multipart/form-data; boundary=boundary"
        )
        messages = json.loads(response)["messages"]
        self.assertEqual([m["kind"] for m in messages], ["text", "file"])
        self.assertTrue(all(m["device_code"] == code for m in messages))
        files = list(Path(self.directory.name).iterdir())
        self.assertEqual(files[0].read_bytes(), b"file contents")

    def test_concurrent_sessions_and_server_restart(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            sessions = list(executor.map(main.DEVICE_SESSIONS.resolve, [None] * 200))
        self.assertEqual(len({code for _, code, _ in sessions}), 200)
        token, code, _ = sessions[0]
        self.assertEqual(main.DEVICE_SESSIONS.resolve(token), (token, code, False))
        self.assertTrue(main.DeviceSessions().resolve(token)[2])

    def test_web_page_identifies_each_sender_and_preserves_bubbles(self):
        headers, _ = self.request("GET", "/")
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        own = self.send_text(cookie)
        headers, _ = self.request("GET", "/")
        other_cookie = headers["Set-Cookie"].split(";", 1)[0]
        other = self.send_text(other_cookie)
        computer = main.CHAT_LOG.add_text("computer", "电脑内容")
        _, body = self.request("GET", "/", cookie=cookie)
        page = body.decode()
        self.assertIn(f'const deviceCode = "{own["device_code"]}";', page)
        self.assertNotIn("__DEVICE_CODE__", page)
        for message, name, side in (
            (own, "本机", "out"),
            (other, f"设备 ({other['device_code']})", "in"),
            (computer, "电脑", "in"),
        ):
            stamp = time.strftime("%H:%M:%S", time.localtime(message["time"]))
            self.assertIn(
                f'<li class="message {side}" data-id="{message["id"]}">'
                f'<p class="message-meta"><span>{name} {stamp}</span>',
                page,
            )
            self.assertIn(f'<div class="bubble">{message["text"]}</div>', page)

    def test_desktop_transcript_preserves_text_and_second_precision(self):
        app = main.App.__new__(main.App)
        app.chat_box = MagicMock()
        app.chat_message_tags = {}
        app.chat_file_tags = {}
        text = "首行\n  保留缩进\n末行"
        local = main.CHAT_LOG.add_text("computer", text)
        remote = main.CHAT_LOG.add_text("phone", text, device_code="ABC01")
        for message in (local, remote):
            app.insert_chat_message(message)
        inserted = "".join(call.args[1] for call in app.chat_box.insert.call_args_list)
        stamp = time.strftime("%H:%M:%S", time.localtime(local["time"]))
        self.assertTrue(inserted.startswith(f"本机 {stamp}\n{text}\n\n"))
        self.assertRegex(inserted, re.escape("设备 (ABC01)") + r" \d{2}:\d{2}:\d{2}\n")
        self.assertTrue(inserted.endswith(text + "\n\n"))


if __name__ == "__main__":
    unittest.main()
