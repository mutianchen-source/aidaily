import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
import generate


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = generate.run()
            if not data:
                self._reply(500, {"ok": False, "error": "没有抓到任何素材"})
                return
            self._reply(200, {"ok": True, "data": data})
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
