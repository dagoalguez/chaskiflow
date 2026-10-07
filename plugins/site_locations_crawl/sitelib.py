"""Rastreo de sitios para encontrar direcciones, sucursales, tiendas y establecimientos.
Solo librería estándar. Lo usa task.py; se puede probar suelto con probar_sitio.py."""

import gzip
import heapq
import html
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser
from urllib import robotparser

DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36 ChaskiFlow-Sucursales")

KEYWORDS = ("ubic", "sucursal", "tienda", "local", "agencia", "oficina", "direcci", "donde", "dónde", "estamos",
            "contact", "punto de venta", "puntos de venta", "sede", "mapa", "establecimiento", "cobertura",
            "encuentr", "visit", "nuestras", "red de", "centros", "cajero", "almacen", "almacén", "distribuidor",
            "locator", "store", "branch", "location", "find-us", "where")
COMMON_PATHS = ("/ubicanos", "/ubicanos/", "/sucursales", "/tiendas", "/locales", "/donde-estamos", "/contacto",
                "/agencias", "/oficinas", "/puntos-de-venta", "/nosotros/ubicanos", "/store-locator")
SKIP_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".zip", ".rar", ".doc", ".docx", ".xls",
            ".xlsx", ".ppt", ".pptx", ".mp3", ".mp4", ".avi", ".mov", ".css", ".js", ".woff", ".woff2", ".ttf", ".xml",
            ".json", ".txt", ".csv", ".exe", ".apk")
TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|_ga|ref$|sessionid|phpsessid)", re.I)
STREET = re.compile(
    r"\b(?:av\.?|avenida|jr\.?|jir[oó]n|calle|ca\.|psje\.?|pasaje|mz\.?|manzana|urb\.?|urbanizaci[oó]n|carretera|carr\.|"
    r"km\.?|alameda|malec[oó]n|prolongaci[oó]n|prol\.?|plaza|paseo|[oó]valo|centro comercial|c\.c\.|cc\.|esq\.|esquina|"
    r"cdra\.?|cuadra|sector|lote|lt\.?|street|st\.|road|rd\.|boulevard|blvd)\b", re.I)
LABEL = re.compile(r"^\s*(direcci[oó]n|ubicaci[oó]n|local|sede|oficina|agencia|tienda|sucursal|address)\s*[:\-–]", re.I)
PHONE = re.compile(r"(?:tel[eé]?f?[a-z\.]*|cel[a-z\.]*|fono|llam[ae]\w*|whatsapp|t:|ph:|phone)\s*[:\.]?\s*"
                   r"(\+?[\d(][\d\s\-\(\)\.]{5,18}\d)", re.I)
BLOCK_TAGS = {"p", "div", "li", "br", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
              "address", "ul", "ol", "table", "footer", "header", "nav", "main", "aside", "form", "dd", "dt", "option"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "template"}
MAPS = re.compile(r"(maps\.google\.|google\.[a-z.]+/maps|goo\.gl/maps|maps\.app\.goo\.gl|waze\.com|openstreetmap\.org|"
                  r"maps\.apple\.com|bing\.com/maps)", re.I)


def norm_text(s):
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c)).lower()).strip()


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


class FetchError(Exception):
    pass


class Fetcher:
    def __init__(self, timeout=25, user_agent=None, verify_ssl=True, ca_bundle="", proxy="", retries=1,
                 max_bytes=3 * 1024 * 1024):
        self.timeout, self.retries, self.max_bytes = timeout, retries, max_bytes
        self.headers = {"User-Agent": user_agent or DEFAULT_UA, "Accept-Language": "es-PE,es;q=0.9,en;q=0.5",
                        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                        "Accept-Encoding": "gzip, deflate"}
        handlers = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        ctx = ssl.create_default_context(cafile=ca_bundle or None)
        if not verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
        self.opener = urllib.request.build_opener(*handlers)

    def get(self, url):
        """Devuelve (texto, url_final, content_type)."""
        last = None
        for _ in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with self.opener.open(req, timeout=self.timeout) as r:
                    data = r.read(self.max_bytes + 1)[:self.max_bytes]
                    ctype = (r.headers.get("Content-Type") or "").lower()
                    enc = (r.headers.get("Content-Encoding") or "").lower()
                    if enc == "gzip" or data[:2] == b"\x1f\x8b":
                        data = gzip.decompress(data)
                    elif enc == "deflate":
                        try:
                            data = zlib.decompress(data)
                        except zlib.error:
                            data = zlib.decompress(data, -15)
                    m = re.search(r"charset=([\w-]+)", ctype) or re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', data[:4000], re.I)
                    cs = (m.group(1).decode("ascii", "ignore") if m and isinstance(m.group(1), bytes) else (m.group(1) if m else "utf-8"))
                    try:
                        text = data.decode(cs, errors="replace")
                    except LookupError:
                        text = data.decode("utf-8", errors="replace")
                    return text, r.geturl(), ctype
            except urllib.error.HTTPError as e:
                last = FetchError("HTTP %d" % e.code)
                if e.code in (401, 403, 404, 410):
                    break
            except ssl.SSLError as e:
                raise FetchError("certificado rechazado (%s): use 'ca_bundle' o desmarque 'Verificar SSL'" % e)
            except urllib.error.URLError as e:
                if isinstance(e.reason, ssl.SSLError) or "CERTIFICATE" in str(e.reason).upper():
                    raise FetchError("certificado rechazado (%s): use 'ca_bundle' o desmarque 'Verificar SSL'" % e.reason)
                last = FetchError("sin conexión (%s)" % e.reason)
            except Exception as e:  # timeout, reset…
                last = FetchError("falló (%s)" % e)
            time.sleep(0.5)
        raise last or FetchError("falló")


# ------------------------------------------------------------------ análisis del HTML
class Page(HTMLParser):
    """Una sola pasada: enlaces, texto por líneas con su encabezado, <address>, mapas, scripts, opciones."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.links, self.options, self.maps, self.scripts, self.ldjson = "", [], [], [], [], []
        self.lines, self.addresses, self.dataset = [], [], []     # lines: (encabezado, texto)
        self.h1 = ""
        self._buf, self._heading, self._skip, self._script, self._ld = [], "", 0, None, False
        self._a, self._atext, self._in_title, self._in_h, self._htext = None, [], False, 0, []
        self._in_addr, self._addr_buf, self._sel_id = 0, [], ""

    def _flush(self):
        t = clean(" ".join(self._buf))
        self._buf = []
        if t:
            self.lines.append((self._heading, t))

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in SKIP_TAGS:
            if tag == "script":
                self._script = []
                self._ld = "ld+json" in a.get("type", "")
                src = a.get("src")
                if src:
                    self.scripts.append(("src", src))
            self._skip += 1
            return
        if tag in BLOCK_TAGS:
            self._flush()
        if tag == "title":
            self._in_title = True
        if re.fullmatch(r"h[1-4]", tag):
            self._in_h, self._htext = int(tag[1]), []
        if tag == "address":
            self._in_addr += 1
            self._addr_buf = [] if self._in_addr == 1 else self._addr_buf
        if tag == "a" and a.get("href") is not None:
            self._a, self._atext = a["href"], [a.get("title", "") or a.get("aria-label", "")]
            if MAPS.search(a["href"]):
                self.maps.append({"url": a["href"], "texto": ""})
        if tag == "iframe" and a.get("src") and MAPS.search(a["src"]):
            self.maps.append({"url": a["src"], "texto": a.get("title", "")})
        if tag == "iframe" and a.get("data-src") and MAPS.search(a["data-src"]):
            self.maps.append({"url": a["data-src"], "texto": a.get("title", "")})
        if tag == "select":
            self._sel_id = a.get("id") or a.get("name") or "select"
        if tag == "option":
            self._opt = a.get("value", "")
        lat = a.get("data-lat") or a.get("data-latitude") or a.get("data-latitud")
        lng = a.get("data-lng") or a.get("data-lon") or a.get("data-longitude") or a.get("data-long") or a.get("data-longitud")
        if lat and lng:
            self.dataset.append({"lat": lat, "lng": lng, "nombre": a.get("data-name") or a.get("data-title") or a.get("title") or a.get("aria-label") or "",
                                 "direccion": a.get("data-address") or a.get("data-direccion") or ""})

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            if tag == "script" and self._script is not None:
                txt = "".join(self._script)
                (self.ldjson if self._ld else self.scripts).append(txt if self._ld else ("inline", txt))
            self._script, self._ld = None, False
            self._skip = max(0, self._skip - 1)
            return
        if tag in BLOCK_TAGS:
            self._flush()
        if tag == "title":
            self._in_title = False
        if re.fullmatch(r"h[1-4]", tag) and self._in_h:
            self._heading = clean(" ".join(self._htext))
            if self._in_h == 1 and not self.h1:
                self.h1 = self._heading
            self._in_h = 0
        if tag == "address" and self._in_addr:
            self._in_addr -= 1
            if not self._in_addr:
                t = clean(" ".join(self._addr_buf))
                if t:
                    self.addresses.append((self._heading, t))
        if tag == "a" and self._a is not None:
            txt = clean(" ".join(self._atext))
            self.links.append((self._a, txt))
            if self.maps and self.maps[-1]["url"] == self._a and not self.maps[-1]["texto"]:
                self.maps[-1]["texto"] = txt
            self._a = None
        if tag == "select":
            self._sel_id = ""

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)
            return
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._in_h:
            self._htext.append(data)
        if self._in_addr:
            self._addr_buf.append(data)
        if self._a is not None:
            self._atext.append(data)
        self._buf.append(data)
        if self._sel_id and data.strip():
            self.options.append((getattr(self, "_opt", ""), clean(data), self._sel_id))

    def close(self):
        super().close()
        self._flush()


def parse_html(text):
    p = Page()
    try:
        p.feed(text)
        p.close()
    except Exception:
        pass
    p.title = clean(p.title)
    return p


# ------------------------------------------------------------------ candidatos
def maps_info(url):
    """(lat, lng, texto_consulta) desde un enlace de Google Maps/Waze/OSM."""
    u = urllib.parse.unquote(html.unescape(url))
    lat = lng = None
    m = (re.search(r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)", u) or re.search(r"@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)", u)
         or re.search(r"[?&](?:ll|mlat)=(-?\d{1,3}\.\d+)[,&](?:mlon=)?(-?\d{1,3}\.\d+)", u))
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))
    else:
        m = re.search(r"!2d(-?\d{1,3}\.\d+)!3d(-?\d{1,3}\.\d+)", u)       # embed: !2d = longitud, !3d = latitud
        if m:
            lng, lat = float(m.group(1)), float(m.group(2))
    q = ""
    m = re.search(r"[?&](?:q|query|daddr|destination)=([^&]+)", u)
    if m:
        q = m.group(1).replace("+", " ").strip()
        mm = re.fullmatch(r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", q)
        if mm:
            lat, lng, q = float(mm.group(1)), float(mm.group(2)), ""
    else:
        m = re.search(r"/maps/place/([^/@?]+)", u)
        if m:
            q = m.group(1).replace("+", " ").strip()
    return lat, lng, q


def _num(v):
    try:
        f = float(str(v).replace(",", "."))
        return f if -180 <= f <= 180 else None
    except (TypeError, ValueError):
        return None


def _addr_from_obj(o):
    if isinstance(o, str):
        return clean(o)
    if isinstance(o, dict):
        parts = [o.get(k) for k in ("streetAddress", "street", "address", "address1", "direccion", "dirección", "calle",
                                    "address2", "addressLocality", "distrito", "city", "ciudad", "addressRegion", "region",
                                    "departamento", "state", "postalCode", "addressCountry")]
        seen, out = set(), []
        for p in parts:
            p = clean(p.get("name") if isinstance(p, dict) else str(p)) if p else ""
            if p and p.lower() not in seen:
                seen.add(p.lower())
                out.append(p)
        return ", ".join(out)
    return ""


ADDR_KEYS = {"address", "direccion", "dirección", "address1", "street", "streetaddress", "calle", "addr", "domicilio", "ubicacion", "ubicación"}
NAME_KEYS = ("name", "nombre", "title", "titulo", "store", "tienda", "local", "sucursal", "agencia", "label")
PHONE_KEYS = ("telephone", "phone", "telefono", "teléfono", "tel", "celular", "fono")


def walk_json(obj, out, depth=0):
    """Busca, a cualquier profundidad, objetos que parezcan un local (tienen dirección)."""
    if depth > 8 or len(out) > 3000:
        return
    if isinstance(obj, list):
        for x in obj[:3000]:
            walk_json(x, out, depth + 1)
    elif isinstance(obj, dict):
        low = {str(k).lower(): v for k, v in obj.items()}
        akey = next((k for k in low if k in ADDR_KEYS), None)
        typ = str(low.get("@type", ""))
        if akey and (isinstance(low[akey], (str, dict)) and low[akey]) or typ == "PostalAddress":
            src = low[akey] if akey and not typ == "PostalAddress" else obj
            direccion = _addr_from_obj(src)
            if direccion and len(direccion) > 5 and typ != "PostalAddress":
                geo = low.get("geo") if isinstance(low.get("geo"), dict) else {}
                lat = _num(geo.get("latitude") or low.get("lat") or low.get("latitude") or low.get("latitud"))
                lng = _num(geo.get("longitude") or low.get("lng") or low.get("lon") or low.get("long") or low.get("longitude") or low.get("longitud"))
                out.append({"nombre": clean(str(next((low[k] for k in NAME_KEYS if isinstance(low.get(k), (str, int)) and low.get(k)), ""))),
                            "direccion": direccion, "telefono": clean(str(next((low[k] for k in PHONE_KEYS if low.get(k)), ""))),
                            "lat": lat, "lng": lng, "horario": clean(str(low.get("openinghours") or low.get("horario") or ""))[:120]})
        for v in obj.values():
            if isinstance(v, (list, dict)):
                walk_json(v, out, depth + 1)


def json_in_script(text, limit=250):
    """Intenta decodificar los literales JSON que aparecen tras '=', ':' o '(' en un script."""
    out, dec, tries = [], json.JSONDecoder(), 0
    for m in re.finditer(r"[=:(,]\s*([\[{])", text):
        if tries >= limit:
            break
        tries += 1
        i = m.start(1)
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            continue
        if end - i > 40:
            walk_json(obj, out)
    return out


def script_endpoints(text):
    found = []
    for m in re.finditer(r"""["']((?:https?:)?//[^"'\s]+|/[^"'\s]*)["']""", text):
        u = m.group(1)
        if re.search(r"(\.json\b|wp-json|/api/|stores?\b|locat|sucursal|tienda|locales|agencias)", u, re.I) and not u.lower().endswith(SKIP_EXT[:-5] + (".css",)):
            found.append(u)
    return found[:20]


def phone_near(*texts):
    for t in texts:
        m = PHONE.search(t or "")
        if m:
            return clean(m.group(1))
    return ""


def text_candidates(page):
    """Líneas del texto visible que parecen una dirección, con su encabezado y teléfono cercano."""
    out, lines = [], page.lines
    for i, (head, line) in enumerate(lines):
        if not (12 <= len(line) <= 260):
            continue
        digit = re.search(r"\d", line)
        if not ((STREET.search(line) and (digit or "," in line)) or (LABEL.match(line) and (digit or STREET.search(line)))):
            continue
        ctx_after = " ".join(t for _, t in lines[i + 1:i + 3])[:200]
        direccion = LABEL.sub("", line).strip(" :-–") if LABEL.match(line) else line
        nombre = head
        if LABEL.match(line) and i > 0 and lines[i - 1][1] and len(lines[i - 1][1]) < 80 and not LABEL.match(lines[i - 1][1]):
            nombre = nombre or lines[i - 1][1]
        out.append({"metodo": "texto", "nombre": nombre, "direccion": direccion, "telefono": phone_near(line, ctx_after),
                    "contexto": clean((head + " | " if head else "") + line + " " + ctx_after)[:320]})
    return out


def page_candidates(page, page_url):
    """Todos los candidatos de una página: JSON-LD, JSON incrustado, <address>, atributos data-, texto y mapas."""
    cands = []
    for raw in page.ldjson:
        try:
            data = json.loads(raw.strip())
        except ValueError:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw.strip()))
            except ValueError:
                continue
        found = []
        walk_json(data, found)
        for f in found:
            f.update(metodo="jsonld", contexto=clean("%s | %s" % (f["nombre"], f["direccion"]))[:320])
            cands.append(f)
    for kind, txt in [s for s in page.scripts if s[0] == "inline"]:
        if re.search(r"(lat|direcc|address|calle|sucursal|tienda)", txt, re.I):
            for f in json_in_script(txt):
                f.update(metodo="json", contexto=clean("%s | %s" % (f["nombre"], f["direccion"]))[:320])
                cands.append(f)
    for head, t in page.addresses:
        cands.append({"metodo": "address", "nombre": head, "direccion": t, "telefono": phone_near(t),
                      "contexto": clean((head + " | " if head else "") + t)[:320]})
    for d in page.dataset:
        lat, lng = _num(d["lat"]), _num(d["lng"])
        if lat is not None and lng is not None:
            cands.append({"metodo": "data", "nombre": clean(d["nombre"]), "direccion": clean(d["direccion"]), "lat": lat, "lng": lng,
                          "contexto": clean("%s %s" % (d["nombre"], d["direccion"]))[:320]})
    texts = text_candidates(page)
    maps = [(maps_info(m["url"]), m["texto"]) for m in page.maps]
    maps = [x for x in maps if x[0][0] is not None or x[0][2]]
    if texts and maps and len(texts) == len(maps):                   # un mapa por local, en el mismo orden
        for t, ((lat, lng, q), _) in zip(texts, maps):
            t["lat"], t["lng"] = lat, lng
    elif len(texts) == 1 and len(maps) >= 1:
        texts[0]["lat"], texts[0]["lng"] = maps[0][0][0], maps[0][0][1]
    cands.extend(texts)
    if not texts and not cands:
        for (lat, lng, q), label in maps:
            cands.append({"metodo": "mapa", "nombre": clean(label), "direccion": clean(q), "lat": lat, "lng": lng,
                          "contexto": clean("%s %s" % (label, q))[:320]})
    elif maps and not texts:
        for (lat, lng, q), label in maps:
            if q and not any(c.get("direccion") for c in cands):
                cands.append({"metodo": "mapa", "nombre": clean(label), "direccion": clean(q), "lat": lat, "lng": lng,
                              "contexto": clean("%s %s" % (label, q))[:320]})
    return cands


# ------------------------------------------------------------------ rastreo
def canon(url):
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True) if not TRACKING.match(k)])
    path = re.sub(r"/{2,}", "/", u.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urllib.parse.urlunsplit((u.scheme.lower(), u.netloc.lower(), path, q, ""))


def host_key(host):
    return re.sub(r"^www\.", "", (host or "").lower().split(":")[0])


def link_score(text, url, keywords):
    t, p = norm_text(text), urllib.parse.unquote(urllib.parse.urlsplit(url).path + " " + urllib.parse.urlsplit(url).query).lower()
    s = 0
    for k in keywords:
        kn = norm_text(k)
        if kn and kn in t:
            s += 10
        if kn and kn.replace(" ", "-") in p.replace("_", "-") or (kn and kn in norm_text(p)):
            s += 6
    return min(s, 40)


class SiteResult(dict):
    pass


def crawl_site(name, start_url, opts, fetcher, log=lambda m: None, progress=lambda n, m: None, stop=lambda: False):
    """Rastrea UN sitio. opts: max_pages, max_depth, delay, max_seconds, keywords, subdomains, robots, probe_paths, bloque_chars."""
    t0 = time.time()
    start = canon(start_url)
    base = host_key(urllib.parse.urlsplit(start).netloc)
    kws = list(opts.get("keywords") or KEYWORDS)
    max_pages, max_depth = int(opts.get("max_pages", 40)), int(opts.get("max_depth", 3))
    delay, max_seconds = float(opts.get("delay", 0.4)), float(opts.get("max_seconds", 240))
    result = SiteResult(sitio=name, sitio_url=start_url, paginas=0, paginas_ubicacion=[], errores=[], bloqueadas_robots=0,
                        rows=[], bloques=[], cortado="")

    def allowed_host(h):
        hk = host_key(h)
        return hk == base or (opts.get("subdomains", True) and hk.endswith("." + base))

    rp = None
    sitemaps = []
    if opts.get("robots", True):
        try:
            rtxt, _, _ = fetcher.get(urllib.parse.urljoin(start, "/robots.txt"))
            rp = robotparser.RobotFileParser()
            rp.parse(rtxt.splitlines())
            sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rtxt)
        except Exception:
            rp = None
    heap, queued, order = [], set(), [0]

    def push(url, score, depth, via=""):
        c = canon(url)
        sp = urllib.parse.urlsplit(c)
        if sp.scheme not in ("http", "https") or not allowed_host(sp.netloc) or c in queued:
            return False
        if sp.path.lower().endswith(SKIP_EXT):
            return False
        queued.add(c)
        order[0] += 1
        heapq.heappush(heap, (-score, depth, order[0], c))
        return True

    push(start, 100, 0)
    # sitemaps: URLs con palabras de ubicación entran con prioridad; el resto con prioridad baja
    try:
        cands = sitemaps[:3] or [urllib.parse.urljoin(start, "/sitemap.xml")]
        seen_sm, locs = set(), []
        while cands and len(seen_sm) < 6:
            sm = cands.pop(0)
            if sm in seen_sm:
                continue
            seen_sm.add(sm)
            try:
                xml, _, _ = fetcher.get(sm)
            except Exception:
                continue
            found = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
            if "<sitemapindex" in xml:
                cands.extend(found[:5])
            else:
                locs.extend(found[:5000])
        for u in locs:
            sc = link_score("", u, kws)
            if sc > 0:
                push(u, 30 + sc, 1, "sitemap")
        for u in locs[:max_pages * 2]:
            push(u, 1, 1, "sitemap")
    except Exception:
        pass

    visited, probed, fetched_json = set(), False, set()
    best_pages = []                                   # (puntaje, url, page) de las páginas de ubicación
    rows = {}

    def add_rows(cands, url, loc_page):
        for c in cands:
            addr = clean(c.get("direccion"))
            key = norm_text(addr)[:90] or ("%.5f,%.5f" % (c["lat"], c["lng"]) if c.get("lat") is not None and c.get("lng") is not None else "")
            if not key or (len(norm_text(addr)) < 8 and c.get("lat") is None):
                continue
            row = {"sitio": name, "sitio_url": start_url, "pagina_url": url, "metodo": c["metodo"], "nombre": clean(c.get("nombre"))[:150],
                   "direccion": addr[:300], "telefono": clean(c.get("telefono"))[:60],
                   "lat": c.get("lat"), "lng": c.get("lng"), "horario": c.get("horario", ""), "contexto": c.get("contexto", "")[:320],
                   "pagina_ubicacion": loc_page}
            old = rows.get(key)
            if old is None:
                rows[key] = row
            else:
                for k in ("nombre", "telefono", "lat", "lng", "horario"):
                    if not old.get(k) and row.get(k):
                        old[k] = row[k]
                if loc_page and not old["pagina_ubicacion"]:
                    old["pagina_ubicacion"], old["pagina_url"] = True, url

    while heap and result["paginas"] < max_pages and not stop():
        if time.time() - t0 > max_seconds:
            result["cortado"] = "tiempo (%d s)" % max_seconds
            break
        negsc, depth, _, url = heapq.heappop(heap)
        if url in visited:
            continue
        visited.add(url)
        if rp is not None and not rp.can_fetch(fetcher.headers["User-Agent"], url) and not rp.can_fetch("*", url):
            result["bloqueadas_robots"] += 1
            continue
        if result["paginas"]:
            time.sleep(delay)
        try:
            text, final, ctype = fetcher.get(url)
        except Exception as e:
            if len(result["errores"]) < 8 and (url == start or "404" not in str(e)):
                result["errores"].append("%s: %s" % (url, e))
            if url == start and not any(True for _ in heap):
                break
            continue
        if not allowed_host(urllib.parse.urlsplit(final).netloc):
            continue
        if "html" not in ctype and "xml" not in ctype and not text.lstrip().startswith("<"):
            continue
        result["paginas"] += 1
        progress(result["paginas"], url)
        page = parse_html(text)
        cands = page_candidates(page, final)
        title_score = link_score(page.title + " " + page.h1, final, kws)
        loc_page = bool(cands) or title_score >= 10
        if loc_page:
            result["paginas_ubicacion"].append(final)
            best_pages.append((len(cands) * 5 + title_score, final, page))
        add_rows(cands, final, loc_page and bool(cands))
        # puntos finales JSON que alimentan un buscador de tiendas (solo si la página es de ubicación)
        if loc_page and len(fetched_json) < 6:
            for kind, txt in [s for s in page.scripts if s[0] == "inline"]:
                for u in script_endpoints(txt):
                    full = urllib.parse.urljoin(final, u)
                    if full in fetched_json or not allowed_host(urllib.parse.urlsplit(full).netloc) or len(fetched_json) >= 6:
                        continue
                    fetched_json.add(full)
                    try:
                        jt, _, jc = fetcher.get(full)
                        found = []
                        walk_json(json.loads(jt), found)
                        for f in found:
                            f.update(metodo="json", contexto=clean("%s | %s" % (f["nombre"], f["direccion"]))[:320])
                        add_rows(found, full, True)
                    except Exception:
                        pass
        if depth >= max_depth:
            continue
        got_loc_link = False
        for href, txt in page.links:
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "#", "whatsapp:", "sms:")):
                continue
            full = urllib.parse.urljoin(final, href.strip())
            sc = link_score(txt, full, kws)
            if loc_page:
                sp_cur, sp_new = urllib.parse.urlsplit(final), urllib.parse.urlsplit(full)
                if sp_new.netloc == sp_cur.netloc and sp_new.path.startswith(sp_cur.path.rstrip("/") + "/") and sp_new.path != sp_cur.path:
                    sc += 8                                          # hijo de la página de ubicación: un distrito/una tienda
                if re.fullmatch(r"\d{1,3}|siguiente|next|›|»|>", norm_text(txt) or txt.strip()) or "page=" in full or "pagina=" in full:
                    sc += 6
            if sc >= 6:
                got_loc_link = True
            push(full, sc + 2 if sc else 2, depth + 1)
        if loc_page:
            for val, otxt, sid in page.options:
                if val and (val.startswith("/") or val.startswith("http")) and not val.startswith("//"):
                    push(urllib.parse.urljoin(final, val), 14, depth + 1)
        if depth == 0 and not got_loc_link and opts.get("probe_paths", True) and not probed:
            probed = True
            for p in COMMON_PATHS:
                push(urllib.parse.urljoin(final, p), 9, 1)
    # bloques de texto para el LLM: páginas de ubicación con pocos candidatos estructurados
    structured = [r for r in rows.values() if r["metodo"] in ("jsonld", "json", "address", "data")]
    if len(structured) < 2:
        for sc, url, page in sorted(best_pages, key=lambda x: -x[0])[:2]:
            lines, seen = [], set()
            for head, t in page.lines:
                if len(t) > 2 and t not in seen:
                    seen.add(t)
                    lines.append(t)
            opts_txt = ", ".join(sorted({o[1] for o in page.options if o[1]}))[:600]
            body = "\n".join(lines)[:int(opts.get("bloque_chars", 3500))]
            if opts_txt:
                body += "\nOpciones del selector: " + opts_txt
            if body.strip():
                result["bloques"].append({"sitio": name, "sitio_url": start_url, "pagina_url": url, "texto": body})
    result["rows"] = list(rows.values())
    result["segundos"] = round(time.time() - t0, 1)
    return result
