"""Estructura direcciones con un LLM local compatible con OpenAI (p. ej. quipullm). Solo librería estándar."""

import ipaddress
import json
import re
import socket
import time
import unicodedata
import urllib.error
import urllib.request
from urllib.parse import urlparse

SYSTEM = (
    "Eres un extractor de datos de ubicaciones de empresas en Perú y Latinoamérica. Recibes fragmentos de texto "
    "tomados de sitios web. Un LOCAL es un lugar físico de la empresa: sucursal, tienda, agencia, oficina, sede, "
    "establecimiento o punto de venta, con una dirección. Reglas: (1) No inventes: si un dato no está en el texto, "
    "déjalo vacío (\"\"). (2) Copia la dirección tal como aparece, sin traducirla. (3) distrito, ciudad y departamento "
    "solo si el texto los menciona. (4) Si el fragmento no es la dirección de un local (menú, anuncio, dirección web, "
    "texto legal), marca es_local=false. Responde ÚNICAMENTE con JSON válido, sin explicaciones ni markdown.")

FIELDS = ("nombre", "direccion", "distrito", "ciudad", "departamento", "telefono", "horario")
OUT_COLS = ("sitio", "sitio_url", "pagina_url", "nombre", "direccion", "distrito", "ciudad", "departamento",
            "telefono", "horario", "lat", "lng", "fuente", "verificada", "metodo")


def _is_local(host):
    host = (host or "").strip("[]").lower()
    if host in ("localhost", "") or host.endswith((".local", ".lan", ".internal", ".intranet", ".home")):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            return True                                  # nombre de equipo de la red (sin dominio)
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except OSError:
            return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


class LLM:
    def __init__(self, base, model, key, timeout):
        self.base, self.model, self.key, self.timeout = base.rstrip("/"), model, key, timeout
        # los servidores locales no deben pasar por el proxy institucional
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _req(self, path, payload=None):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method="POST" if data else "GET")
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            body = e.read(500).decode("utf-8", "replace")
            if e.code in (401, 403):
                raise RuntimeError("El servidor rechazó la clave (HTTP %d). Escriba en el campo «Clave» el nombre de la clave guardada en 🔑 Claves, o revise que sea la correcta" % e.code)
            raise RuntimeError("HTTP %d del servidor de IA: %s" % (e.code, body[:200]))
        except urllib.error.URLError as e:
            raise RuntimeError("No se pudo conectar con el servidor de IA %s (%s). ¿Está encendido y es la IP/puerto correctos?" % (self.base, e.reason))
        except (TimeoutError, socket.timeout):
            raise RuntimeError("El servidor de IA no respondió en %d s" % self.timeout)

    def pick_model(self):
        if self.model:
            return
        try:
            d = self._req("/models")
            ids = [m.get("id") for m in (d.get("data") or []) if m.get("id")]
        except RuntimeError:
            ids = []
        self.model = ids[0] if ids else "local-model"

    def chat(self, system, user, max_tokens):
        payload = {"model": self.model, "temperature": 0, "max_tokens": max_tokens, "stream": False,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        for attempt in range(4):
            try:
                d = self._req("/chat/completions", payload)
                break
            except RuntimeError as e:
                if "HTTP 429" in str(e) and attempt < 3:       # cola llena (max_cola de quipullm)
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
        msg = ((d.get("choices") or [{}])[0].get("message") or {})
        return msg.get("content") or ""


def parse_json(text):
    """Extrae el primer JSON (lista u objeto) de la respuesta, tolerando <think>, ``` y comas finales."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I)
    t = re.sub(r"```(?:json)?", "", t)
    dec = json.JSONDecoder()
    for m in re.finditer(r"[\[{]", t):
        for cand in (t[m.start():], re.sub(r",\s*([}\]])", r"\1", t[m.start():])):
            try:
                obj, _ = dec.raw_decode(cand)
                return obj
            except ValueError:
                continue
    raise ValueError("la respuesta no contiene JSON")


def _tokens(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return set(re.findall(r"[a-z0-9]{3,}", s))


def verified(direccion, source):
    """True si casi todas las palabras de la dirección aparecen en el texto original (control anti-invención)."""
    a = _tokens(direccion)
    return not a or len(a & _tokens(source)) / float(len(a)) >= 0.7


def _clean_obj(o):
    out = {}
    for k in FIELDS:
        v = o.get(k) if isinstance(o, dict) else ""
        out[k] = re.sub(r"\s+", " ", str(v)).strip() if v not in (None, False) else ""
    return out



def _norm_base(base):
    """http://host:1234 -> http://host:1234/v1 (la API OpenAI-compatible vive en /v1)."""
    base = base.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[:-len("/chat/completions")]
    p = urlparse(base)
    if p.path in ("", "/"):
        base += "/v1"
    return base


def _is_true(v):
    return v is True or str(v).strip().lower() in ("true", "si", "sí", "1", "yes")


def probar_conexion(config, ctx, base):
    """Botón «Probar conexión»: comprueba servidor, clave y modelo con una consulta mínima."""
    t0 = time.time()
    clave = (config.get("clave") or "").strip()
    key = (ctx.secrets.get(clave) or "") if clave else ""
    llm = LLM(_norm_base(base), (config.get("model") or "").strip(), key, int(config.get("timeout") or 600))
    ctx.log("Servidor: %s" % llm.base)
    ctx.log("Clave: " + ("enviada («%s»)" % clave if key else "ninguna"))
    try:
        ids = [m.get("id") for m in (llm._req("/models").get("data") or []) if m.get("id")]
    except RuntimeError as e:
        if "HTTP 404" in str(e):
            ids = []
        else:
            raise
    ctx.log("Conexión correcta. Modelos que informa el servidor: %s" % (", ".join(ids[:10]) if ids else "(no los lista)"))
    llm.pick_model()
    if (config.get("model") or "").strip() and ids and llm.model not in ids:
        raise RuntimeError("El servidor responde, pero no tiene el modelo «%s». Disponibles: %s" % (llm.model, ", ".join(ids[:10])))
    t1 = time.time()
    ans = llm.chat("Responde únicamente con JSON válido.", 'Responde SOLO con este JSON: {"estado": "ok"}', 40)
    seg = round(time.time() - t1, 1)
    ok = "ok" in (ans or "").lower()
    ctx.log("Respuesta del modelo (%s s): %s" % (seg, re.sub(r"\s+", " ", ans or "")[:120]))
    return {"ok": ok, "servidor": llm.base, "modelo": llm.model, "modelos_disponibles": ids[:20], "clave_enviada": bool(key),
            "respuesta_modelo": (ans or "")[:200], "segundos": round(time.time() - t0, 1),
            "mensaje": "Conexión correcta y el modelo responde" if ok else "Conecta, pero la respuesta del modelo no fue la esperada"}


def run(config, ctx):
    base = (config.get("base_url") or "").strip()
    if not re.match(r"^https?://", base):
        raise RuntimeError("La URL del servidor debe empezar con http:// o https:// (ej. http://192.168.1.50:1234/v1)")
    base = _norm_base(base)
    host = urlparse(base).hostname or ""
    if not config.get("allow_remote") and not _is_local(host):
        raise RuntimeError("«%s» no es un equipo de la red local. Por seguridad los datos solo se envían a servidores locales; "
                           "si de verdad lo desea, active «Permitir servidores fuera de la red local»" % host)
    if config.get("modo_prueba"):
        return probar_conexion(config, ctx, base)
    rows = [r for r in (config.get("rows") or []) if isinstance(r, dict)]
    bloques = [b for b in (config.get("bloques") or []) if isinstance(b, dict)]
    max_items = int(config.get("max_items") or 400)
    if len(rows) > max_items:
        ctx.log("AVISO: %d candidatos; se envían los primeros %d al modelo (resto se conserva sin IA)" % (len(rows), max_items))
    clave = (config.get("clave") or "").strip()
    key = (ctx.secrets.get(clave) or "") if clave else ""
    llm = LLM(base, (config.get("model") or "").strip(), key, int(config.get("timeout") or 600))
    llm.pick_model()
    extra = (config.get("system_prompt") or "").strip()
    system = SYSTEM + ((" " + extra) if extra else "")
    mt = int(config.get("max_tokens") or 1200)
    fallback = bool(config.get("fallback"))
    stats = {"modelo": llm.model, "consultas": 0, "fallos": 0, "descartados": 0, "sin_verificar": 0, "segundos": 0}
    t0 = time.time()
    out = []

    def base_row(src):
        d = {k: src.get(k, "") for k in OUT_COLS}
        d["lat"], d["lng"] = src.get("lat"), src.get("lng")
        return d

    def heuristic(r):
        d = base_row(r)
        d.update(nombre=r.get("nombre", ""), direccion=r.get("direccion", ""), fuente="rastreo", verificada="sí")
        return d

    bs = int(config.get("batch_size") or 6)
    todo = rows[:max_items]
    rest = rows[max_items:]
    out.extend(heuristic(r) for r in rest)
    batches = []
    for i in range(0, len(todo), bs):
        batches.append(("rows", todo[i:i + bs]))
    for b in bloques:
        batches.append(("bloque", [b]))
    total = max(1, len(batches))
    ctx.log("Modelo '%s' en %s: %d consulta(s) (%d candidatos, %d texto(s) de página)" % (llm.model, base, len(batches), len(todo), len(bloques)))
    limit = float(config.get("max_total_seconds") or 0)
    cortado = 0
    for n, (kind, items) in enumerate(batches, start=1):
        ctx.progress(n, total, "IA %d/%d" % (n, total))
        if limit and time.time() - t0 > limit:       # tiempo total agotado: no se consulta más al modelo
            cortado += 1
            if kind == "rows" and fallback:
                out.extend(heuristic(r) for r in items)
            continue
        try:
            if kind == "rows":
                frag = [{"id": j, "texto": (r.get("contexto") or "%s %s" % (r.get("nombre", ""), r.get("direccion", "")))[:400]} for j, r in enumerate(items)]
                user = ("Sitio: %s\nFragmentos:\n%s\n\nDevuelve un arreglo JSON con un objeto por fragmento, con las claves: "
                        "id, es_local (true/false), nombre, direccion, distrito, ciudad, departamento, telefono, horario."
                        % (items[0].get("sitio", ""), json.dumps(frag, ensure_ascii=False)))
            else:
                b = items[0]
                user = ("Sitio: %s\nPágina: %s\nTexto de la página:\n\"\"\"\n%s\n\"\"\"\n\nExtrae TODOS los locales físicos que aparezcan. "
                        "Devuelve un arreglo JSON de objetos con las claves: nombre, direccion, distrito, ciudad, departamento, "
                        "telefono, horario. Si no hay ninguno, devuelve []." % (b.get("sitio", ""), b.get("pagina_url", ""), b.get("texto", "")))
            stats["consultas"] += 1
            try:
                data = parse_json(llm.chat(system, user, mt))
            except ValueError:
                data = parse_json(llm.chat(system, user + "\n\nRESPONDE SOLO CON EL JSON.", mt))     # un reintento
            if isinstance(data, dict):
                data = data.get("locales") or data.get("resultados") or data.get("items") or [data]
            if not isinstance(data, list):
                raise ValueError("el JSON no es una lista")
            if kind == "rows":
                byid = {}
                for o in data:
                    try:
                        byid[int(o.get("id"))] = o
                    except (TypeError, ValueError, AttributeError):
                        continue
                for j, r in enumerate(items):
                    o = byid.get(j)
                    if o is None:
                        out.append(heuristic(r)) if fallback else None
                        stats["fallos"] += 1
                        continue
                    if not _is_true(o.get("es_local", True)):
                        stats["descartados"] += 1
                        continue
                    f = _clean_obj(o)
                    d = base_row(r)
                    src = r.get("contexto") or r.get("direccion", "")
                    d.update(f, fuente="ia", verificada="sí" if verified(f["direccion"], src) else "no")
                    d["nombre"] = f["nombre"] or r.get("nombre", "")
                    d["direccion"] = f["direccion"] or r.get("direccion", "")
                    d["telefono"] = f["telefono"] or r.get("telefono", "")
                    if d["verificada"] == "no":
                        stats["sin_verificar"] += 1
                    out.append(d)
            else:
                b = items[0]
                for o in data:
                    if not isinstance(o, dict):
                        continue
                    f = _clean_obj(o)
                    if not f["direccion"]:
                        continue
                    d = {k: "" for k in OUT_COLS}
                    d.update(f, sitio=b.get("sitio", ""), sitio_url=b.get("sitio_url", ""), pagina_url=b.get("pagina_url", ""),
                             fuente="ia", metodo="texto_pagina", verificada="sí" if verified(f["direccion"], b.get("texto", "")) else "no")
                    d["lat"] = d["lng"] = None
                    if d["verificada"] == "no":
                        stats["sin_verificar"] += 1
                    out.append(d)
        except RuntimeError as e:
            # servidor caído, clave mala o timeout: no tiene sentido seguir consultando
            stats["fallos"] += 1
            if not fallback:
                raise
            ctx.log("AVISO: %s. Se conservan los datos del rastreo sin estructurar." % e)
            for r in items if kind == "rows" else []:
                out.append(heuristic(r))
            for k2, it2 in batches[n:]:
                if k2 == "rows":
                    out.extend(heuristic(r) for r in it2)
            break
        except ValueError as e:
            stats["fallos"] += 1
            ctx.log("AVISO: respuesta no válida del modelo en la consulta %d (%s)" % (n, e))
            if kind == "rows" and fallback:
                out.extend(heuristic(r) for r in items)
    # quitar duplicados (mismo sitio y misma dirección)
    final, seen = [], set()
    for d in out:
        key = (d.get("sitio"), re.sub(r"[^a-z0-9]+", "", (d.get("direccion") or "").lower())[:80] or id(d))
        if key in seen:
            continue
        seen.add(key)
        final.append({k: d.get(k, "") if k not in ("lat", "lng") else d.get(k) for k in OUT_COLS})
    stats["segundos"] = round(time.time() - t0, 1)
    stats["sin_consultar_por_tiempo"] = cortado
    if cortado:
        ctx.log("AVISO: se alcanzó el tiempo máximo total; %d consulta(s) no se enviaron al modelo (se conservó el dato del rastreo)." % cortado)
    ctx.log("Listo: %d local(es); descartados %d; no verificados %d; fallos %d; %.0f s" % (
        len(final), stats["descartados"], stats["sin_verificar"], stats["fallos"], stats["segundos"]))
    return {"rows": final, "total": len(final), "stats": stats}
