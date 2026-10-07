"""Plugins declarativos (kind = "http"): una petición HTTP descrita solo con JSON.

Ejemplo de bloque "http" en plugin.json:
  {
    "method": "POST",
    "url": "https://api.ejemplo.com/v1/mensajes",
    "headers": {"Authorization": "Bearer {{secret.token}}"},
    "json": {"to": "{{config.telefono}}", "text": "{{config.mensaje}}"},
    "response_map": {"id": "json.id"}
  }
Dentro del bloque se puede usar {{config.campo}} y {{secret.nombre}}.
Claves: method, url, query, headers, json, body, timeout, verify_ssl, ca_bundle, proxy,
user_agent, max_mb, fail_on_http_error, success_status, response_map.
"""

import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from .templating import TemplateError, lookup_path, resolve


def _build_opener(url, verify_ssl, ca_bundle, proxy, log):
    handlers = []
    if url.lower().startswith("https"):
        if verify_ssl is False:
            log("Verificación SSL desactivada para esta petición", "warn")
            ctx = ssl._create_unverified_context()
        else:
            ctx = ssl.create_default_context(cafile=ca_bundle or None)
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def http_call(spec, log=lambda *a, **k: None):
    """Ejecuta la petición ya resuelta (sin plantillas). Devuelve el diccionario de resultado."""
    method = str(spec.get("method") or "GET").upper()
    url = spec.get("url")
    if not url:
        raise RuntimeError("Falta la URL")
    if not str(url).lower().startswith(("http://", "https://")):
        raise RuntimeError("La URL debe empezar con http:// o https:// (recibido: %s)" % url)
    query = spec.get("query")
    if query:
        if not isinstance(query, dict):
            raise RuntimeError("'query' debe ser un objeto")
        qs = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None},
                                    doseq=True)
        url += ("&" if "?" in url else "?") + qs
    headers = spec.get("headers") or {}
    if not isinstance(headers, dict):
        raise RuntimeError("'headers' debe ser un objeto JSON")
    headers = {str(k): str(v) for k, v in headers.items() if v is not None}
    data = None
    if spec.get("json") is not None:
        data = json.dumps(spec["json"], ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif spec.get("body") not in (None, ""):
        body = spec["body"]
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        else:
            data = str(body).encode("utf-8")
    if not any(k.lower() == "user-agent" for k in headers):
        headers["User-Agent"] = spec.get("user_agent") or "Mozilla/5.0 (ChaskiFlow)"
    timeout = float(spec.get("timeout") or 30)
    max_bytes = int(float(spec.get("max_mb") or 20) * 1024 * 1024)

    opener = _build_opener(url, spec.get("verify_ssl"), spec.get("ca_bundle"),
                           spec.get("proxy"), log)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.monotonic()
    try:
        try:
            resp = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            resp = e
        status = resp.status if hasattr(resp, "status") else resp.code
        raw = resp.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise RuntimeError("La respuesta supera el límite de %s MB" % (max_bytes // 1048576))
        charset = resp.headers.get_content_charset() or "utf-8"
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        hint = ""
        if isinstance(reason, ssl.SSLError):
            hint = (" — Si un proxy institucional rompe SSL, indique 'ca_bundle' "
                    "o desactive 'verify_ssl'.")
        raise RuntimeError("No se pudo conectar a %s: %s%s"
                           % (urllib.parse.urlparse(url).netloc, reason, hint))
    except (socket.timeout, TimeoutError):
        raise RuntimeError("Tiempo de espera agotado (%g s) en %s"
                           % (timeout, urllib.parse.urlparse(url).netloc))

    try:
        text = raw.decode(charset, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
    parsed = None
    ctype = resp_headers.get("content-type", "")
    stripped = text.lstrip()
    if "json" in ctype or stripped[:1] in ("{", "["):
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
    ok_codes = spec.get("success_status")
    ok = (status in ok_codes) if ok_codes else 200 <= status < 300
    if not ok and spec.get("fail_on_http_error", True):
        raise RuntimeError("HTTP %s: %s" % (status, text[:300].strip()))
    return {
        "status": status,
        "ok": ok,
        "headers": resp_headers,
        "text": text,
        "json": parsed,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }


def run_http(spec, config, secrets, log=lambda *a, **k: None):
    """Resuelve plantillas del bloque 'http' y ejecuta la petición."""
    scope = {"config": config, "secret": secrets}
    response_map = spec.get("response_map") or {}
    plain = {k: v for k, v in spec.items() if k not in ("response_map",)}
    try:
        resolved = resolve(plain, scope)
    except TemplateError as e:
        raise RuntimeError("%s. Si es un secreto, configúrelo en Secretos." % e)
    result = http_call(resolved, log)
    for name, path in response_map.items():
        try:
            result[name] = lookup_path(result, path)
        except TemplateError:
            result[name] = None
    return result
