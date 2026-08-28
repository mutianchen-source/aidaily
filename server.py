#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 资讯日报 · 本地服务

功能：
  1. 托管网页（index.html 及 data/ 静态资源）；
  2. 提供 /api/refresh 接口：点击「立即更新」时，实时抓取最新新闻
     并交给 DeepSeek 整理，返回最新数据。

启动：
  python3 server.py
然后浏览器打开 http://localhost:8000
"""

import json
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import generate

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = 8000

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/refresh":
            self.handle_refresh()
        else:
            self.handle_static()

    def do_POST(self):
        if self.path.split("?")[0] == "/api/chat":
            self.handle_chat()
        else:
            self._send(404, "Not Found", "text/plain; charset=utf-8")

    def handle_refresh(self):
        try:
            data = generate.run()
            if not data:
                self._send(500, json.dumps({"ok": False, "error": "没有抓到任何素材"}, ensure_ascii=False))
                return
            generate.write_outputs(data)
            self._send(200, json.dumps({"ok": True, "data": data}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

    def handle_chat(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw.decode("utf-8"))
            question = (req.get("question") or "").strip()
            news = req.get("news") or []
            if not question:
                self._send(400, json.dumps({"ok": False, "error": "问题不能为空"}, ensure_ascii=False))
                return
            answer = generate.ask(question, news)
            self._send(200, json.dumps({"ok": True, "answer": answer}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

    def handle_static(self):
        path = self.path.split("?")[0]
        if path == "/":
            path = "/index.html"
        rel = path.lstrip("/")
        # 只允许 index.html 和 data/ 目录下的文件，防止泄露 config.json、脚本等
        if rel != "index.html" and not rel.startswith("data/"):
            self._send(404, "Not Found", "text/plain; charset=utf-8")
            return
        filepath = os.path.normpath(os.path.join(BASE, rel))
        if not filepath.startswith(BASE) or not os.path.isfile(filepath):
            self._send(404, "Not Found", "text/plain; charset=utf-8")
            return
        ext = os.path.splitext(filepath)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        with open(filepath, "rb") as f:
            content = f.read()
        # 数据文件禁止缓存，避免「日期更新了内容没更新」
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        if ext in (".json", ".js", ".html"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print("AI 资讯日报已启动： http://localhost:{}".format(PORT))
    print("按 Ctrl+C 停止。")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
