"""Utilidades de prueba: servidor HTTP local y rutas."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
FIXTURES = TESTS / "fixtures" / "plugins"
FIXTURES_DUP = TESTS / "fixtures" / "plugins_dup"
PLUGINS = ROOT / "plugins"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except ConnectionError:
            pass  # el cliente se fue (prueba de timeout); en Windows es ConnectionAbortedError

    def do_GET(self):
        if self.path.startswith("/json"):
            self._send(200, json.dumps({"a": 1, "texto": "ñandú"}))
        elif self.path.startswith("/text"):
            self._send(200, "hola texto", "text/plain; charset=utf-8")
        elif self.path.startswith("/status/404"):
            self._send(404, "no existe")
        elif self.path.startswith("/slow"):
            time.sleep(3)
            self._send(200, "{}")
        elif self.path.startswith("/ua"):
            self._send(200, json.dumps({"ua": self.headers.get("User-Agent")}))
        elif self.path.startswith("/query"):
            self._send(200, json.dumps({"path": self.path}))
        else:
            self._send(404, "?")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            body = raw.decode("utf-8", errors="replace")
        self._send(200, json.dumps({
            "received": body, "auth": self.headers.get("Authorization"),
            "ctype": self.headers.get("Content-Type")}))


class LocalServer:
    def __enter__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
