import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
import generate


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw.decode("utf-8"))
            question = (req.get("question") or "").strip()
            news = req.get("news") or []
            if not question:
                self._reply(400, {"ok": False, "error": "问题不能为空"})
                return
            answer = generate.ask(question, news)
            self._reply(200, {"ok": True, "answer": answer})
        except Exception as e:
            self._reply(500, {"ok": False, "error": str(e)})

    def _reply(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass
