"""Cliente HTTP mínimo (urllib) y servidor de pruebas para la batería del API."""

import http.client
import json
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from chaskiflow.config import load_config
from chaskiflow.server import create_server
from tests.helpers import FIXTURES, PLUGINS, ROOT


class Client:
    def __init__(self, base):
        self.base = base
        self.cookie = None

    def call(self, method, path, body=None, headers=None, raw_body=None):
        h = {"Content-Type": "application/json"}
        if self.cookie:
            h["Cookie"] = self.cookie
        h.update(headers or {})
        data = raw_body if raw_body is not None else (
            json.dumps(body).encode("utf-8") if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            r = urllib.request.urlopen(req, timeout=60)
            status, payload, hdrs = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            status, payload, hdrs = e.code, e.read(), e.headers
        sc = hdrs.get("Set-Cookie")
        if sc:
            first = sc.split(";")[0]
            self.cookie = None if first.endswith("=") else first
        try:
            data = json.loads(payload.decode("utf-8")) if payload else {}
        except ValueError:
            data = payload
        self.last_headers = hdrs
        return status, data

    def get(self, p, **kw):
        return self.call("GET", p, **kw)

    def post(self, p, body=None, **kw):
        return self.call("POST", p, body if body is not None else {}, **kw)

    def put(self, p, body=None, **kw):
        return self.call("PUT", p, body if body is not None else {}, **kw)

    def delete(self, p, **kw):
        return self.call("DELETE", p, **kw)


class TestServer:
    """Servidor real en un puerto libre, con base de datos y carpeta de plugins temporales."""

    def __init__(self, plugin_dirs=None, **cfg_over):
        self.tmp = Path(tempfile.mkdtemp())
        self.extra_plugins = self.tmp / "extra_plugins"
        self.extra_plugins.mkdir()
        cfg = load_config(ROOT, path=self.tmp / "none.json", create=False)
        cfg.update({"host": "127.0.0.1", "port": 0, "data_dir": str(self.tmp / "data"),
                    "plugin_dirs": plugin_dirs or [str(PLUGINS), str(FIXTURES), str(self.extra_plugins)]})
        cfg.update(cfg_over)
        self.cfg = cfg
        self.httpd, self.app = create_server(cfg)
        self.port = self.httpd.server_address[1]
        self.base = "http://127.0.0.1:%d" % self.port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def client(self):
        return Client(self.base)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.app.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


def wf_def(*nodes, edges=(), variables=None):
    return {"nodes": list(nodes), "edges": [{"source": a, "target": b} for a, b in edges],
            "variables": variables or {}}


def n(nid, typ, config=None, **kw):
    d = {"id": nid, "label": nid, "type": typ, "config": config or {}}
    d.update(kw)
    return d


def wait_run(client, run_id, timeout=30):
    """Espera a que termine la ejecución (por el API de eventos) y devuelve su detalle."""
    t0 = time.time()
    after = 0
    events = []
    while time.time() - t0 < timeout:
        s, d = client.get("/api/runs/%s/events?after=%d" % (run_id, after))
        assert s == 200, d
        events += d["events"]
        after = d["seq"]
        if d["done"]:
            break
        time.sleep(0.15)
    else:
        raise AssertionError("la ejecución no terminó en %s s" % timeout)
    s, detail = client.get("/api/runs/%s" % run_id)
    assert s == 200, detail
    return detail["run"], events


def raw_request(port, method, path, headers=None, body=None):
    """Petición sin normalizar la ruta (para probar path traversal)."""
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    data = r.read()
    out = (r.status, dict(r.getheaders()), data)
    c.close()
    return out
