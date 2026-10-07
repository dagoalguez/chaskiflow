"""Servidor HTTP (solo librería estándar): API REST + archivos estáticos de la interfaz."""

import json
import socket
import sys
import threading
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import api  # noqa: F401  (registra las rutas)
from .auth import Auth
from .db import Database
from .plugin_gate import PluginGate
from .plugin_loader import PluginRegistry
from .router import ApiError, Req, find_route
from .runs import RunManager
from .scheduler import Scheduler

COOKIE = "cf_session"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
}
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
MUST_CHANGE_OK = ("/api/me", "/api/me/password", "/api/logout", "/api/health")


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.data_dir = Path(cfg["data_dir"])
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(self.data_dir / "app.db")
        self.registry = PluginRegistry(cfg["plugin_dirs"])
        self.gate = PluginGate(self.db, self.registry)
        self.seeded = 0
        if self.db.created_new:
            self.seeded = self.gate.approve_all_present()
        self.auth = Auth(self.db, session_hours=cfg["session_idle_hours"])
        self.runs = RunManager(self.db, self.gate, self.data_dir,
                               max_concurrent=cfg["max_concurrent_runs"],
                               max_parallel=cfg["max_parallel_nodes"],
                               retention_days=cfg["run_retention_days"])
        self.scheduler = Scheduler(self.db, self.runs, cfg.get("scheduler_tick_seconds", 15))
        if cfg.get("scheduler_enabled", True):
            self.scheduler.start()
        self.web_dir = Path(cfg["base_dir"]) / "web"
        self.max_body = int(float(cfg["max_body_mb"]) * 1024 * 1024)
        self._stop = threading.Event()
        threading.Thread(target=self._housekeeping, daemon=True, name="housekeeping").start()

    def _housekeeping(self):
        while not self._stop.wait(3600):
            try:
                self.auth.purge_sessions()
                self.runs.purge_old()
            except Exception:
                traceback.print_exc()

    def stop(self):
        self._stop.set()
        self.scheduler.stop()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ChaskiFlow"
    sys_version = ""
    timeout = 60
    app = None

    def log_message(self, fmt, *args):
        pass

    def finish(self):
        try:
            super().finish()
        finally:
            self.app.db.close_thread()   # cada hilo de conexión cierra su conexión SQLite al terminar

    # ------------------------------------------------------------------ envío
    def _send(self, status, body, ctype="application/json; charset=utf-8", extra=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _error(self, status, message, **extra):
        self._send(status, dict({"error": message}, **extra))

    # ------------------------------------------------------------------ verbos
    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_HEAD(self):
        self._handle("GET")

    def do_OPTIONS(self):
        self._error(405, "Método no permitido")

    # ------------------------------------------------------------------ despacho
    def _handle(self, method):
        try:
            self._dispatch(method)
        except (ConnectionError, TimeoutError):
            self.close_connection = True
        except Exception:
            traceback.print_exc(file=sys.stderr)
            try:
                self._error(500, "Error interno del servidor")
            except Exception:
                self.close_connection = True

    def _token(self):
        c = self.headers.get("Cookie")
        if c:
            try:
                sc = SimpleCookie()
                sc.load(c)
                if COOKIE in sc:
                    return sc[COOKIE].value
            except Exception:
                pass
        h = self.headers.get("Authorization", "")
        if h.lower().startswith("bearer "):
            return h[7:].strip()
        return ""

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = (self.headers.get("Host") or "").lower()
        return urlsplit(origin).netloc.lower() == host

    def _dispatch(self, method):
        app = self.app
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        query = parse_qs(parts.query)
        length = int(self.headers.get("Content-Length") or 0)
        if length > app.max_body:
            self.close_connection = True
            return self._error(413, "La petición es demasiado grande (máximo %d MB)"
                               % (app.max_body // 1048576))
        raw = self.rfile.read(length) if length else b""

        if not path.startswith("/api/"):
            if method != "GET":
                return self._error(405, "Método no permitido")
            return self._static(path)

        fn, auth, params, path_known = find_route(method, path)
        if fn is None:
            return self._error(405 if path_known else 404,
                               "Método no permitido" if path_known else "Ruta no encontrada")
        if method != "GET" and not self._origin_ok():
            return self._error(403, "Origen no permitido")

        token = self._token()
        user = app.auth.user_for_token(token) if token else None
        if auth != "public":
            if not user:
                return self._error(401, "Inicie sesión para continuar")
            if user["must_change_password"] and path not in MUST_CHANGE_OK:
                return self._error(403, "Debe cambiar su contraseña antes de continuar",
                                   code="must_change_password")
            if auth == "admin" and user["role"] != "admin":
                return self._error(403, "Solo un administrador puede hacer esto")
            if auth == "editor" and user["role"] not in ("admin", "editor"):
                return self._error(403, "Su rol no permite esta acción")

        req = Req(app, method, path, query, raw, params, user, token, self.client_address[0],
                  self.headers.get("User-Agent", ""))
        try:
            result = fn(req)
            status = 200
            if isinstance(result, tuple):
                status, result = result
        except ApiError as e:
            return self._error(e.status, e.message, **e.extra)
        extra = []
        if req.set_session:
            hours = int(app.cfg["session_idle_hours"])
            extra.append(("Set-Cookie", "%s=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=%d"
                          % (COOKIE, req.set_session, hours * 3600 * 14)))
        if req.clear_session:
            extra.append(("Set-Cookie", "%s=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0" % COOKIE))
        self._send(status, result, extra=extra)

    # ------------------------------------------------------------------ estáticos
    def _static(self, path):
        web = self.app.web_dir
        rel = "index.html" if path in ("/", "/index.html") else path[len("/static/"):] \
            if path.startswith("/static/") else None
        if rel is None:
            return self._error(404, "No encontrado")
        target = (web / rel).resolve()
        try:
            target.relative_to(web.resolve())
        except ValueError:
            return self._error(404, "No encontrado")
        ctype = CONTENT_TYPES.get(target.suffix.lower())
        if not target.is_file() or ctype is None:
            return self._error(404, "No encontrado")
        self._send(200, target.read_bytes(), ctype)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(cfg):
    app = App(cfg)
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = Server((cfg["host"], int(cfg["port"])), handler)
    return httpd, app


def lan_addresses():
    ips = set()
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            ips.add(ip)
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # UDP: no envía nada, solo elige la interfaz
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127."))
