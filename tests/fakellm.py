"""Servidor falso compatible con OpenAI (como quipullm) para probar el plugin de IA local."""

import base64
import json
import re
import struct
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeLLM:
    def __init__(self, key=None, mode="ok"):
        S = self
        S.key, S.mode, S.calls, S.auth, S.users = key, mode, 0, [], []

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def send(self, code, obj):
                b = (obj if isinstance(obj, str) else json.dumps(obj)).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path == "/v1/models":
                    return self.send(200, {"data": [{"id": "qwen-fake-7b"}]})
                self.send(404, {"error": "no"})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
                S.auth.append(self.headers.get("Authorization"))
                if S.key and self.headers.get("Authorization") != "Bearer " + S.key:
                    return self.send(401, {"error": "clave incorrecta"})
                S.calls += 1
                user = body["messages"][-1]["content"]
                if isinstance(user, list):                     # petición con imagen (modelo de visión)
                    return self.vision(user)
                S.users.append(user)
                S.model_seen = body.get("model")
                if '"estado"' in user:                          # «Probar conexión»
                    return self.reply('{"estado": "ok"}')
                if S.mode == "http500":
                    return self.send(500, {"error": "boom"})
                if S.mode == "prose_first" and "RESPONDE SOLO" not in user:
                    return self.reply("Claro, con gusto. Aquí tienes el análisis.")
                if S.mode == "garbage":
                    return self.reply("no sé")
                if "Fragmentos:" in user:
                    frags = json.loads(user.split("Fragmentos:\n", 1)[1].split("\n\nDevuelve", 1)[0])
                    out = []
                    for f in frags:
                        t = f["texto"]
                        o = {"id": f["id"], "es_local": "ANUNCIO" not in t}
                        m = re.search(r"((?:Av|Jr|Calle)\.?\s[^,|]+?\d+)(?:,\s*([^,.|]+))?", t)
                        o.update(nombre=t.split("|")[0].strip()[:40], direccion=m.group(1) if m else "", distrito=(m.group(2) or "") if m else "",
                                 ciudad="Lima" if "Lima" in t else "", departamento="", telefono="", horario="")
                        if "INVENTADA" in t:
                            o["direccion"] = "Av. Los Delfines 999, Marte"
                        out.append(o)
                    return self.reply(S.wrap(json.dumps(out, ensure_ascii=False)))
                text = user.split('"""', 1)[1].rsplit('"""', 1)[0]
                out = []
                for m in re.finditer(r"((?:Av|Jr|Calle)\.?\s[A-Za-zÁÉÍÓÚáéíóúñ ]+\d+),\s*([A-Za-zÁÉÍÓÚáéíóúñ ]+)", text):
                    out.append({"nombre": "Sede", "direccion": m.group(1), "distrito": m.group(2).strip(), "ciudad": "", "departamento": "", "telefono": "", "horario": ""})
                self.reply(S.wrap(json.dumps(out, ensure_ascii=False)))

            def vision(self, parts):
                S.vision_calls = getattr(S, "vision_calls", 0) + 1
                text = next(p["text"] for p in parts if p.get("type") == "text")
                uri = next(p["image_url"]["url"] for p in parts if p.get("type") == "image_url")
                mime, b64 = uri[5:].split(";base64,", 1)
                data = base64.b64decode(b64)
                S.images = getattr(S, "images", []) + [mime]
                if S.mode == "novision":
                    return self.send(400, {"error": {"message": "Model 'x' has no vision in this version: there is no mmproj file in its folder.", "type": "vision_not_supported"}})
                if S.mode == "http500":
                    return self.send(500, {"error": "boom"})
                if '"color"' in text:                           # «Probar conexión»: cuadro rojo
                    return self.reply('{"color": "%s"}' % ("negro" if S.mode == "blind" else "rojo"))
                if S.mode == "garbage":
                    return self.reply("no sé")
                if mime == "image/jpeg":
                    words = ["reorganización societaria"]
                else:                                           # PNG gris: el valor del primer píxel decide
                    raw = b""
                    i = 8
                    while i < len(data):
                        ln = struct.unpack(">I", data[i:i + 4])[0]
                        if data[i + 4:i + 8] == b"IDAT":
                            raw += data[i + 8:i + 8 + ln]
                        i += 12 + ln
                    v = zlib.decompress(raw)[1]
                    words = {200: ["fusión"], 150: ["escisión", "Fusión"]}.get(v, [])
                words = [w for w in words if w in text or w.lower() in text]
                self.reply(S.wrap(json.dumps({"encontradas": words, "contexto": "…aprobó la %s…" % words[0] if words else ""}, ensure_ascii=False)))

            def reply(self, content):
                self.send(200, {"choices": [{"message": {"role": "assistant", "content": content}}], "usage": {}})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = "http://127.0.0.1:%d/v1" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def wrap(self, js):
        if self.mode == "think_fence":
            return "<think>Voy a analizar los fragmentos...</think>\n```json\n%s\n```" % js
        return js

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
