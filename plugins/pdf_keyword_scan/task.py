"""Busca palabras (p. ej. fusión, escisión, reorganización societaria) en PDF y organiza en carpetas los que las
contienen. Texto del PDF primero; solo las páginas sin texto (escaneadas) se leen con un modelo local con visión.
Solo librería estándar + pypdf incluido."""

import base64
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import time
import unicodedata
import urllib.error
import urllib.request
from urllib.parse import urlparse

import pdftext

DEFAULT_KEYWORDS = "fusión\nescisión\nreorganización societaria"
SYSTEM = "Eres un lector de documentos escaneados. Respondes únicamente con JSON válido, sin explicaciones."


# ----------------------------------------------------------------------------------- texto y palabras
def fold(s):
    """Minúsculas y sin tildes, un carácter por carácter (los índices se conservan)."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower() for c in s)


def prep(text):
    t = (text or "").replace("\xad", "")
    return re.sub(r"-[ \t]*\r?\n[ \t]*", "", t)         # palabras partidas con guion al final de línea


def term_regex(term):
    words = [w for w in re.split(r"\s+", fold(term).strip()) if w]
    if not words:
        return None
    body = r"\s+".join(re.escape(w) + r"(?:es|s)?" for w in words)
    return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])")


def find_terms(text, terms):
    """{término: [fragmentos]} para los que aparecen en el texto."""
    out = {}
    t = prep(text)
    f = fold(t)
    for term, rx in terms:
        ms = list(rx.finditer(f))
        if ms:
            frag = []
            for m in ms[:2]:
                a, b = max(0, m.start() - 90), min(len(t), m.end() + 90)
                frag.append(re.sub(r"\s+", " ", t[a:b]).strip())
            out[term] = (len(ms), frag)
    return out


# ----------------------------------------------------------------------------------- modelo con visión
def _is_local(host):
    host = (host or "").strip("[]").lower()
    if host in ("localhost", "") or host.endswith((".local", ".lan", ".internal", ".intranet", ".home")):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            return True
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except OSError:
            return False
    return ip.is_private or ip.is_loopback or ip.is_link_local



def _norm_base(base):
    """http://host:1234 -> http://host:1234/v1 (la API OpenAI-compatible vive en /v1)."""
    base = base.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[:-len("/chat/completions")]
    p = urlparse(base)
    if p.path in ("", "/"):
        base += "/v1"
    return base


class Vision:
    def __init__(self, base, model, key, timeout):
        self.base, self.model, self.key, self.timeout = base.rstrip("/"), model, key, timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # servidor local: sin proxy

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
            body = e.read(300).decode("utf-8", "replace")
            if e.code in (401, 403):
                raise RuntimeError("El servidor de IA rechazó la clave (HTTP %d). Revise el secreto quipullm_key" % e.code)
            raise RuntimeError("HTTP %d del servidor de IA: %s" % (e.code, body[:160]))
        except urllib.error.URLError as e:
            raise RuntimeError("No se pudo conectar con el servidor de IA %s (%s)" % (self.base, e.reason))
        except (TimeoutError, socket.timeout):
            raise RuntimeError("El servidor de IA no respondió en %d s" % self.timeout)

    def pick_model(self):
        if self.model:
            return
        try:
            ids = [m.get("id") for m in (self._req("/models").get("data") or []) if m.get("id")]
        except RuntimeError:
            ids = []
        self.model = ids[0] if ids else "local-model"

    def ask(self, prompt, mime, data, max_tokens=150):
        uri = "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))
        payload = {"model": self.model, "temperature": 0, "max_tokens": max_tokens, "stream": False,
                   "messages": [{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": uri}}]}]}
        for attempt in range(4):
            try:
                d = self._req("/chat/completions", payload)
                break
            except RuntimeError as e:
                if "HTTP 429" in str(e) and attempt < 3:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
        return ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def parse_json(text):
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I)
    t = re.sub(r"```(?:json)?", "", t)
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", t):
        for cand in (t[m.start():], re.sub(r",\s*([}\]])", r"\1", t[m.start():])):
            try:
                obj, _ = dec.raw_decode(cand)
                return obj
            except ValueError:
                continue
    raise ValueError("la respuesta no contiene JSON")


def vision_terms(vis, terms_txt, mime, data):
    """Pregunta al modelo qué palabras de la lista se ven en la imagen. Devuelve ({término: contexto}, respuesta)."""
    prompt = ("Esta imagen es una página escaneada de un documento. Palabras a buscar: %s.\n"
              "Lee la página y responde SOLO con JSON: {\"encontradas\": [palabras de la lista que SÍ aparecen escritas en la página, "
              "copiadas tal como están en la lista], \"contexto\": \"la frase corta donde aparece la primera\"}. "
              "Si ninguna aparece, {\"encontradas\": [], \"contexto\": \"\"}. No adivines." % ", ".join('"%s"' % t for t in terms_txt))
    raw = vis.ask(prompt, mime, data)
    try:
        o = parse_json(raw)
    except ValueError:
        o = parse_json(vis.ask(prompt + " RESPONDE SOLO CON EL JSON.", mime, data))
    keys = {fold(t).strip(): t for t in terms_txt}
    found = {}
    enc = o.get("encontradas") if isinstance(o, dict) else []
    for w in enc if isinstance(enc, list) else []:
        k = keys.get(fold(str(w)).strip())
        if k:
            found[k] = str(o.get("contexto") or "")[:240]
    return found


# ----------------------------------------------------------------------------------- utilidades
def _safe(s, n=80):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:n].strip(" .") or "SinNombre"


def _collect(files, folder):
    """Lista de {path, empresa, anio} desde 'files' (rutas o filas) y/o desde una carpeta."""
    items, seen = [], set()

    def add(path, empresa="", anio=""):
        path = os.path.abspath(str(path))
        if path in seen or not path.lower().endswith(".pdf"):
            return
        seen.add(path)
        parts = path.replace("\\", "/").split("/")
        if not anio and len(parts) >= 2 and re.fullmatch(r"(19|20)\d\d", parts[-2]):
            anio = parts[-2]
        if not empresa:
            empresa = parts[-3] if anio and len(parts) >= 3 else (parts[-2] if len(parts) >= 2 else "")
        items.append({"path": path, "empresa": str(empresa), "anio": str(anio)})

    src = files
    if isinstance(src, str):
        src = [x.strip() for x in re.split(r"[\n;]+", src) if x.strip()]
    for f in src or []:
        if isinstance(f, dict):
            p = f.get("archivo") or f.get("path") or f.get("ruta")
            if p:
                add(p, f.get("empresa", ""), f.get("anio", ""))
        elif f:
            add(f)
    if folder:
        for root, _, names in os.walk(folder):
            for n in sorted(names):
                add(os.path.join(root, n))
    return items


def _cfg_hash(cfg):
    return hashlib.sha1(json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp, path)


def _place(src, dest_dir, move):
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(src))
    if os.path.abspath(dest) == os.path.abspath(src):
        return dest
    if move:
        if os.path.exists(dest):
            os.remove(dest)
        shutil.move(src, dest)
    else:
        shutil.copy2(src, dest)
    return dest


# ----------------------------------------------------------------------------------- análisis de un PDF
def scan_pdf(item, terms, terms_txt, vis, opt, ctx, deadline):
    res = {"paginas": 0, "con_texto": 0, "sin_texto": 0, "leidas_ia": 0, "no_leidas": 0, "hits": {}, "paginas_hallazgo": [],
           "notas": [], "error": ""}
    try:
        rd = pdftext.open_pdf(item["path"])
    except pdftext.PdfError as e:
        res["error"] = str(e)
        return res
    pages = rd.pages
    res["paginas"] = len(pages)
    t0 = time.time()
    ia_used = 0
    ia_fail = 0
    for i in range(len(pages)):
        if time.time() - t0 > opt["max_pdf_seconds"]:
            res["notas"].append("cortado a las %d páginas por tiempo" % i)
            res["no_leidas"] += len(pages) - i
            break
        page = pages[i]
        text = pdftext.page_text(page)
        if len(re.sub(r"\s+", "", text)) >= opt["min_chars"]:
            res["con_texto"] += 1
            for term, (n, frag) in find_terms(text, terms).items():
                h = res["hits"].setdefault(term, {"n": 0, "paginas": [], "contexto": [], "fuente": "texto"})
                h["n"] += n
                h["paginas"].append(i + 1)
                if len(h["contexto"]) < 2:
                    h["contexto"].extend(frag[:1])
            continue
        try:
            scanned = pdftext.has_image(page)
        except Exception:
            scanned = True
        if not scanned:                              # página en blanco o solo con dibujos: no hay nada que leer
            res["vacias"] = res.get("vacias", 0) + 1
            continue
        res["sin_texto"] += 1
        if vis is None:
            res["no_leidas"] += 1
            continue
        if ia_used >= opt["ia_max_paginas"] or (deadline and time.time() > deadline):
            res["no_leidas"] += 1
            continue
        try:
            mime, data = pdftext.page_image(page)
        except ValueError as e:
            res["no_leidas"] += 1
            if str(e) not in res["notas"] and len(res["notas"]) < 4:
                res["notas"].append("p. %d: %s" % (i + 1, e))
            continue
        except Exception as e:
            res["no_leidas"] += 1
            continue
        if len(data) > 18 * 1024 * 1024:
            res["no_leidas"] += 1
            res["notas"].append("p. %d: imagen demasiado grande para el modelo" % (i + 1))
            continue
        try:
            found = vision_terms(vis, terms_txt, mime, data)
            ia_used += 1
            res["leidas_ia"] += 1
        except (RuntimeError, ValueError) as e:
            ia_fail += 1
            res["no_leidas"] += 1
            if len(res["notas"]) < 4:
                res["notas"].append("p. %d: la IA no respondió bien (%s)" % (i + 1, str(e)[:80]))
            if ia_fail >= 3 and not res["leidas_ia"]:
                raise RuntimeError("El servidor de IA falla de forma repetida: %s" % e)
            continue
        for term, ctxt in found.items():
            h = res["hits"].setdefault(term, {"n": 0, "paginas": [], "contexto": [], "fuente": "IA"})
            if h["fuente"] == "texto":
                h["fuente"] = "texto+IA"
            h["n"] += 1
            h["paginas"].append(i + 1)
            if ctxt and len(h["contexto"]) < 2:
                h["contexto"].append(ctxt)
    return res


def run(config, ctx):
    out_dir = (config.get("output_dir") or "").strip()
    if not out_dir:
        raise RuntimeError("Indique la carpeta de salida")
    items = _collect(config.get("files"), (config.get("folder") or "").strip())
    if not items:
        raise RuntimeError("No hay PDF para revisar: conecte «Archivos» (p. ej. {{Descarga.result.archivos}}) o indique una carpeta")
    terms_txt = [x.strip() for x in re.split(r"[\n;,]+", config.get("keywords") or DEFAULT_KEYWORDS) if x.strip()]
    terms = [(t, term_regex(t)) for t in terms_txt]
    terms = [(t, rx) for t, rx in terms if rx is not None]
    if not terms:
        raise RuntimeError("Indique al menos una palabra a buscar")
    limit = float(config.get("max_total_seconds") or 0)
    t0 = time.time()
    deadline = t0 + limit if limit else 0
    move = bool(config.get("mover"))
    split_unread = config.get("separar_no_leidos") is not False
    os.makedirs(out_dir, exist_ok=True)

    vis = None
    use_ai = bool(config.get("usar_ia", True))
    if use_ai:
        base = (config.get("base_url") or "").strip()
        if base:
            if not re.match(r"^https?://", base):
                raise RuntimeError("La URL del servidor de IA debe empezar con http:// o https://")
            if not config.get("allow_remote") and not _is_local(urlparse(base).hostname):
                raise RuntimeError("«%s» no es un equipo de la red local. Por seguridad las páginas solo se envían a servidores locales" % urlparse(base).hostname)
            base = _norm_base(base)
            vis = Vision(base, (config.get("model") or "").strip(), ctx.secrets.get("quipullm_key") or "", int(config.get("ia_timeout") or 300))
            vis.pick_model()
            ctx.log("IA para páginas sin texto: %s en %s" % (vis.model, base))
        else:
            ctx.log("AVISO: sin URL del servidor de IA; las páginas sin texto (escaneadas) NO se podrán leer")
    opt = {"min_chars": int(config.get("min_chars") or 25), "ia_max_paginas": int(config.get("ia_max_paginas") or 60),
           "max_pdf_seconds": float(config.get("max_pdf_seconds") or 600)}
    cfg = {"t": [t for t, _ in terms], "ia": bool(vis), "m": vis.model if vis else "", "min": opt["min_chars"], "iamax": opt["ia_max_paginas"]}
    cfgh = _cfg_hash(cfg)
    cache_path = os.path.join(out_dir, "_cache_escaneo.json")
    cache = {}
    if os.path.isfile(cache_path) and not config.get("reprocesar"):
        try:
            cache = json.load(open(cache_path, encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
    ctx.log("Revisando %d PDF buscando: %s" % (len(items), ", ".join(t for t, _ in terms)))

    rows, pend = [], 0
    stats = {"pdf": len(items), "con_hallazgo": 0, "sin_hallazgo": 0, "no_leidos": 0, "con_ia": 0, "errores": 0, "pendientes": 0, "reutilizados": 0}
    for n, it in enumerate(items, 1):
        ctx.progress(n, len(items), os.path.basename(it["path"]))
        key = it["path"]
        try:
            st = os.stat(it["path"])
            sig = [st.st_size, int(st.st_mtime), cfgh]
        except OSError as e:
            rows.append({"empresa": it["empresa"], "anio": it["anio"], "archivo": os.path.basename(it["path"]), "ruta": it["path"],
                         "identificado": "", "metodo": "error", "nota": "no se pudo abrir: %s" % e})
            stats["errores"] += 1
            continue
        res = None
        if key in cache and cache[key].get("sig") == sig:
            res = dict(cache[key]["res"], _reutilizado=True)
            stats["reutilizados"] += 1
        else:
            if deadline and time.time() > deadline:
                pend += 1
                rows.append({"empresa": it["empresa"], "anio": it["anio"], "archivo": os.path.basename(it["path"]), "ruta": it["path"],
                             "identificado": "", "metodo": "pendiente", "nota": "tiempo máximo total agotado; vuelva a ejecutar"})
                continue
            res = scan_pdf(it, terms, [t for t, _ in terms], vis, opt, ctx, deadline)
            if not res["error"]:
                cache[key] = {"sig": sig, "res": res}
                _atomic_json(cache_path, cache)
        hits = res["hits"]
        if not res["error"] and not res.get("_reutilizado"):
            ctx.log("%s %s: %d pág. · %d con texto · %d sin texto (%d leídas con IA)%s → %s" % (
                it["empresa"], it["anio"], res["paginas"], res["con_texto"], res["sin_texto"], res["leidas_ia"],
                " · %d sin leer" % res["no_leidas"] if res["no_leidas"] else "", ", ".join(hits) if hits else "sin hallazgo"))
        palabras = "; ".join("%s (%d)" % (t, h["n"]) for t, h in hits.items())
        pgs = sorted({p for h in hits.values() for p in h["paginas"]})
        fuentes = sorted({h["fuente"] for h in hits.values()})
        if res["error"]:
            metodo, ident = "error", ""
            stats["errores"] += 1
        else:
            metodo = "texto" if not res["sin_texto"] else ("ia" if res["con_texto"] == 0 and res["leidas_ia"] else
                                                          ("mixto" if res["leidas_ia"] else ("sin texto" if res["con_texto"] == 0 else "texto")))
            ident = "sí" if hits else "no"
        no_leido = (not res["error"]) and res["no_leidas"] > 0 and not hits
        copiado = ""
        if hits:
            stats["con_hallazgo"] += 1
            copiado = _place(it["path"], os.path.join(out_dir, "IDENTIFICADOS", _safe(it["empresa"]), _safe(it["anio"], 10)), move)
        elif no_leido and split_unread:
            copiado = _place(it["path"], os.path.join(out_dir, "REVISAR_MANUAL", _safe(it["empresa"]), _safe(it["anio"], 10)), move)
        if not hits and not res["error"]:
            stats["sin_hallazgo"] += 1
        if no_leido:
            stats["no_leidos"] += 1
        if res.get("leidas_ia"):
            stats["con_ia"] += 1
        nota = "; ".join(res["notas"])
        if res["no_leidas"] and hits:
            nota = ("%d página(s) sin leer. " % res["no_leidas"]) + nota
        rows.append({"empresa": it["empresa"], "anio": it["anio"], "archivo": os.path.basename(it["path"]), "ruta": it["path"],
                     "identificado": ident, "palabras": palabras, "paginas_hallazgo": ", ".join(str(p) for p in pgs[:40]),
                     "deteccion": "+".join(fuentes), "contexto": " | ".join(c for h in hits.values() for c in h["contexto"][:1])[:600],
                     "paginas": res["paginas"], "paginas_con_texto": res["con_texto"], "paginas_sin_texto": res["sin_texto"],
                     "paginas_leidas_ia": res["leidas_ia"], "paginas_sin_leer": res["no_leidas"], "metodo": metodo,
                     "copiado_a": copiado, "nota": (res["error"] or nota)})
    stats["pendientes"] = pend
    stats["segundos"] = round(time.time() - t0, 1)
    if pend:
        ctx.log("AVISO: se alcanzó el tiempo máximo total; %d PDF quedaron pendientes. Vuelva a ejecutar: no repite los ya revisados." % pend)
    if stats["no_leidos"]:
        ctx.log("AVISO: %d PDF tienen páginas que no se pudieron leer y no mostraron hallazgos%s." % (
            stats["no_leidos"], " (copiados a REVISAR_MANUAL)" if split_unread else ""))
    ctx.log("Listo: %d con hallazgo, %d sin hallazgo, %d no leídos del todo, %d con error" % (
        stats["con_hallazgo"], stats["sin_hallazgo"], stats["no_leidos"], stats["errores"]))
    ident_rows = [r for r in rows if r.get("identificado") == "sí"]
    return {"rows": rows, "identificados": ident_rows, "total": len(rows), "stats": stats,
            "carpeta_identificados": os.path.join(out_dir, "IDENTIFICADOS")}
