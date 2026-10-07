"""Utilidades de noticias: HTTP, feeds, fechas y EXTRACTOR de texto propio.

Solo librería estándar. El extractor reemplaza a trafilatura: construye un árbol HTML
liviano, puntúa los contenedores por la cantidad de texto en párrafos y descarta menús,
"lee también", compartir, etc. Es heurístico: valide con `probar_url.py` en sus medios.
"""

import gzip
import json
import re
import ssl
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


# ============================================================ texto
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def norm(s):
    return re.sub(r"\s+", " ", strip_accents(str(s or "")).lower()).strip()


def clean_text(t):
    if t is None:
        return ""
    t = unicodedata.normalize("NFKC", str(t))
    t = "".join(c for c in t if unicodedata.category(c) != "Cf")
    return re.sub(r"\s+", " ", t).strip()


def parse_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = re.split(r"[,;\n]", str(value))
    return [str(x).strip() for x in items if str(x).strip()]


def parse_urls(value):
    """Acepta lista o texto con URLs separadas por coma/espacio/salto y enlaces tipo [t](url)."""
    out = []
    for raw in (value if isinstance(value, (list, tuple)) else re.split(r"[\s,;]+", str(value or ""))):
        raw = str(raw).strip()
        m = re.search(r"\((https?://[^)\s]+)\)", raw)
        raw = m.group(1) if m else raw
        raw = raw.strip("<>[]()\"'")
        if raw.lower().startswith(("http://", "https://")) and raw not in out:
            out.append(raw)
    return out


def detect(text, keywords):
    """Palabras completas, sin distinguir mayúsculas ni tildes. Devuelve las que aparecen."""
    base = norm(text)
    found = []
    for kw in keywords:
        k = norm(kw)
        if k and re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", base):
            found.append(kw)
    return sorted(set(found))


def parse_date(raw):
    """ISO 8601 o RFC 2822 -> datetime UTC (o None)."""
    if not raw:
        return None
    raw = str(raw).strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    try:
        dt = parsedate_to_datetime(raw)
        if dt:
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


# ============================================================ HTTP
PROXY_MARKS = ("skyhigh", "web gateway", "mcafee web", "bluecoat", "blue coat", "zscaler", "netskope",
               "forcepoint", "fortiguard", "url categor", "categoria web", "filtro de categor",
               "pagina web bloqueada", "web page blocked", "access denied by", "webfilter",
               "politicas de seguridad de uso de internet")
_RE_CATEGORY = re.compile(r"URL\s*Categor(?:ies|ía|ia)\s*:?\s*([^\n<]{1,60})", re.I)


def proxy_block(body):
    """Si el cuerpo es la página de bloqueo del proxy institucional, devuelve la categoría ('?' si
    no se pudo leer). Si no, None. Se distingue de un 403 del medio: este lo arregla TI, no el código."""
    if not body:
        return None
    low = strip_accents(body[:4000]).lower()
    if not any(m in low for m in PROXY_MARKS):
        return None
    m = _RE_CATEGORY.search(body[:4000])
    return m.group(1).strip() if m else "?"


class FetchError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind  # SSL | PROXY_BLOCK | HTTP | RED


class Fetcher:
    def __init__(self, timeout=30, user_agent=None, verify_ssl=True, ca_bundle="", proxy="",
                 headers=None, retries=2, max_bytes=8 * 1024 * 1024):
        self.timeout, self.retries, self.max_bytes = timeout, retries, max_bytes
        self.headers = {"User-Agent": user_agent or DEFAULT_UA, "Accept-Language": "es-PE,es;q=0.9,en;q=0.5",
                        "Accept": "text/html,application/xhtml+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
                        "Accept-Encoding": "gzip, deflate"}
        self.headers.update(headers or {})
        handlers = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        # sin 'proxy' explícito urllib usa el proxy del sistema (en Windows, el del registro/IE)
        ctx = ssl.create_default_context(cafile=ca_bundle or None)
        if not verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
        self.opener = urllib.request.build_opener(*handlers)

    @staticmethod
    def _decode(data, content_type, head):
        m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
        enc = m.group(1) if m else None
        if not enc:
            m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', head[:4000], re.I) or \
                re.search(rb'^<\?xml[^>]+encoding=["\']([\w-]+)', head[:200], re.I)
            enc = m.group(1).decode("ascii", "ignore") if m else "utf-8"
        try:
            return data.decode(enc, errors="replace")
        except LookupError:
            return data.decode("utf-8", errors="replace")

    def get(self, url):
        last = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with self.opener.open(req, timeout=self.timeout) as r:
                    data = r.read(self.max_bytes + 1)[:self.max_bytes]
                    enc = (r.headers.get("Content-Encoding") or "").lower()
                    if enc == "gzip" or data[:2] == b"\x1f\x8b":
                        data = gzip.decompress(data)
                    elif enc == "deflate":
                        try:
                            data = zlib.decompress(data)
                        except zlib.error:
                            data = zlib.decompress(data, -15)
                    text = self._decode(data, r.headers.get("Content-Type"), data)
                blk = proxy_block(text)
                if blk is not None:
                    raise FetchError("PROXY_BLOCK", "bloqueado por el proxy institucional (categoría: %s)" % blk)
                return text
            except FetchError:
                raise
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read(6000).decode("utf-8", "replace")
                except Exception:
                    pass
                blk = proxy_block(body)
                if blk is not None:
                    raise FetchError("PROXY_BLOCK", "bloqueado por el proxy institucional (categoría: %s)" % blk)
                last = FetchError("HTTP", "HTTP %d en %s" % (e.code, url))
                if e.code in (401, 403, 404, 410):
                    break
            except ssl.SSLError as e:
                raise FetchError("SSL", "certificado rechazado (%s). Use 'ca_bundle' con la CA de su "
                                        "institución o desmarque 'Verificar SSL'" % e)
            except urllib.error.URLError as e:
                if isinstance(e.reason, ssl.SSLError) or "CERTIFICATE" in str(e.reason).upper():
                    raise FetchError("SSL", "certificado rechazado (%s). Use 'ca_bundle' con la CA de su "
                                            "institución o desmarque 'Verificar SSL'" % e.reason)
                last = FetchError("RED", "sin conexión a %s (%s)" % (url, e.reason))
            except Exception as e:  # timeout, reset...
                last = FetchError("RED", "falló %s (%s)" % (url, e))
        raise last


# ============================================================ feeds
def _local(tag):
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _child_text(el, *names):
    for ch in el.iter():
        if _local(ch.tag) in names and ch.text and ch.text.strip():
            return ch.text.strip()
    return ""


def parse_feed(text, feed_type="auto", origin="", fetch=None, depth=0, link_selector=None, url_pattern=""):
    """Devuelve items {titulo, fecha_raw, url}. fetch(url)->texto para seguir sitemap index."""
    stripped = text.lstrip()
    is_html = stripped[:15].lower().startswith(("<!doctype html", "<html")) or "<html" in stripped[:1500].lower()
    if feed_type == "html_index" or (feed_type == "auto" and is_html):
        return parse_html_index(text, origin, url_pattern)
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        # a veces hay basura antes del XML o entidades raras
        i = text.find("<")
        try:
            root = ET.fromstring(re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", text[i:]).encode("utf-8"))
        except ET.ParseError as e:
            raise ValueError("el feed no es XML válido (%s)" % e)
    kind = _local(root.tag)
    items = []
    if kind == "sitemapindex" or feed_type == "sitemap_index":
        if depth >= 1 or fetch is None:
            return items
        kids = [c.text.strip() for c in root.iter() if _local(c.tag) == "loc" and c.text][:10]
        for k in kids:
            try:
                items.extend(parse_feed(fetch(k), "auto", k, fetch, depth + 1))
            except (FetchError, ValueError):
                continue
        return items
    if kind in ("rss", "rdf") or feed_type == "rss" or root.find(".//channel") is not None:
        for it in root.iter():
            if _local(it.tag) in ("item", "entry"):
                link = _child_text(it, "link", "guid")
                if not link:
                    for ch in it:
                        if _local(ch.tag) == "link" and ch.get("href"):
                            link = ch.get("href")
                if link:
                    items.append({"titulo": _child_text(it, "title"),
                                  "fecha_raw": _child_text(it, "pubdate", "date", "published", "updated"),
                                  "url": link.strip()})
        return items
    for u in root.iter():
        if _local(u.tag) == "url":
            loc = _child_text(u, "loc")
            if loc:
                items.append({"titulo": _child_text(u, "title"),
                              "fecha_raw": _child_text(u, "publication_date", "lastmod"), "url": loc})
    return items


_INFRA = ("/cdn-cgi/", "/wp-json/", "/wp-admin/", "/wp-content/", "/feed/", "/tag/", "/tags/", "/autor/",
          "/author/", "/buscar/", "/search/", "/suscripcion", "/suscribete", "/newsletter", "/login",
          "/registro", "/terminos", "/privacidad", "/contacto", "/publicidad", "/pag/", "/page/", "/rss",
          "/amp/", "/static/", "/assets/")


def parse_html_index(html, origin, url_pattern=""):
    """Links que parecen artículos en una portada de sección (para medios sin sitemap ni RSS)."""
    host = urllib.parse.urlparse(origin).netloc.lower()
    items, seen = [], set()
    for href, title in extract_links(html):
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urllib.parse.urljoin(origin, href).split("#")[0].rstrip("/")
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https") or p.netloc.lower() != host or url in seen:
            continue
        if any(x in p.path.lower() for x in _INFRA):
            continue
        segs = [s for s in p.path.split("/") if s]
        if url_pattern:
            if not re.search(url_pattern, url, re.I):
                continue
        elif len(segs) < 2 or "-" not in segs[-1] or len(segs[-1]) < 15:
            continue
        seen.add(url)
        items.append({"titulo": title, "fecha_raw": "", "url": url})
    return items


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self._href, self._buf = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            d = dict(attrs)
            self._href, self._buf = d.get("href"), [d.get("title") or ""]

    def handle_data(self, data):
        if self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            txt = clean_text(" ".join(self._buf[1:])) or clean_text(self._buf[0])
            self.links.append((self._href.strip(), txt))
            self._href = None


def extract_links(html):
    p = _LinkParser()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.links


# ============================================================ extractor de artículos
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source",
        "track", "wbr"}
SKIP = {"script", "style", "noscript", "iframe", "svg", "template", "head", "nav", "footer", "aside",
        "form", "button", "select", "figure", "figcaption", "picture", "video", "audio", "canvas", "dialog"}
BLOCK_CLOSE_P = {"p", "div", "section", "article", "ul", "ol", "li", "h1", "h2", "h3", "h4", "table", "blockquote"}
_BOILER_ATTR = re.compile(
    r"(comment|share|social|related|relacionad|newsletter|promo|banner|advert|publicidad|sidebar|menu|"
    r"breadcrumb|\btags?\b|paywall|subscri|suscri|widget|recomend|more-?news|taboola|outbrain|"
    r"author-?bio|footer|cookie|popup|modal|signup|follow|whatsapp|telegram)", re.I)
_BOILER_TEXT = re.compile(
    r"^(lee tambien|lea tambien|te puede interesar|mira tambien|puede interesarte|mas informacion|"
    r"suscribete|suscribase|siguenos|sigue a|compartir|comparte|publicidad|advertisement|"
    r"recibe las noticias|unete a|descarga la app|lo mas leido|tambien lee|no te pierdas|"
    r"foto:|imagen:|video:|fuente:|click aqui|haz clic|escucha|ver mas|lee mas)\b", re.I)


class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "text")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent, self.text = tag, attrs or {}, [], parent, ""


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root
        self.skip_depth = 0
        self.skip_tag = None
        self.title = ""
        self._in_title = False
        self.metas = []
        self.jsonld = []
        self._in_jsonld = False
        self._jbuf = []

    def handle_starttag(self, tag, attrs):
        d = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            self.metas.append(d)
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "script" and "ld+json" in d.get("type", "").lower():
            self._in_jsonld, self._jbuf = True, []
        if self.skip_depth:
            if tag == self.skip_tag:
                self.skip_depth += 1
            return
        if tag in SKIP:
            if tag not in VOID:
                self.skip_depth, self.skip_tag = 1, tag
            return
        if tag in VOID:
            return
        if tag in ("p", "li") and self.cur.tag == tag:
            self.cur = self.cur.parent or self.root
        elif tag in BLOCK_CLOSE_P and self.cur.tag == "p":
            self.cur = self.cur.parent or self.root
        n = Node(tag, d, self.cur)
        self.cur.children.append(n)
        self.cur = n

    def handle_startendtag(self, tag, attrs):
        if tag == "meta":
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            return
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._jbuf))
            self._in_jsonld = False
        if self.skip_depth:
            if tag == self.skip_tag:
                self.skip_depth -= 1
            return
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n is not self.root:
            self.cur = n.parent or self.root

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_jsonld:
            self._jbuf.append(data)
        elif not self.skip_depth and data.strip():
            t = Node("#text", parent=self.cur)
            t.text = data
            self.cur.children.append(t)


def _text(node):
    if node.tag == "#text":
        return node.text
    return " ".join(_text(c) for c in node.children)


def _link_text(node, inside=False):
    if node.tag == "#text":
        return len(node.text.strip()) if inside else 0
    inside = inside or node.tag == "a"
    return sum(_link_text(c, inside) for c in node.children)


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


def _attr_blob(n):
    return " ".join((n.attrs.get("class", ""), n.attrs.get("id", ""), n.attrs.get("role", "")))


def _boiler_ancestor(n, stop):
    while n is not None and n is not stop:
        if n.tag in ("div", "section", "ul", "ol", "p", "span") and _BOILER_ATTR.search(_attr_blob(n)):
            return True
        n = n.parent
    return False


def _paragraphs(container, min_len=40):
    out = []
    for p in _walk(container):
        if p.tag not in ("p", "li", "h2", "h3", "blockquote", "div") :
            continue
        if p.tag == "div" and any(c.tag != "#text" and c.tag not in ("a", "b", "i", "strong", "em", "span", "br")
                                   for c in p.children):
            continue
        txt = clean_text(_text(p))
        if p.tag in ("li", "h2", "h3"):
            if p.tag == "li" and (len(txt) < 80 or p.parent is None or p.parent.tag not in ("ul", "ol")):
                continue
            if p.tag in ("h2", "h3") and not (20 <= len(txt) <= 160):
                continue
        elif len(txt) < min_len:
            continue
        if p.tag == "div" and len(txt) < 60:
            continue
        if _link_text(p) > 0.5 * max(len(txt), 1):
            continue
        if _BOILER_TEXT.match(norm(txt)):
            continue
        if _boiler_ancestor(p, container):
            continue
        out.append(txt)
    # quitar repetidos consecutivos
    res = []
    for t in out:
        if not res or res[-1] != t:
            res.append(t)
    return res


def _json_ld_body(tree):
    for raw in tree.jsonld:
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                if isinstance(x.get("articleBody"), str) and len(x["articleBody"]) > 200:
                    return x["articleBody"]
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
    return ""


_BODY_HINT = re.compile(r"(articlebody|article-body|story-contents|story-body|entry-content|post-content|"
                        r"nota-contenido|contenido-nota|article__body|article-content|body-content|"
                        r"cuerpo|content-body|field--name-body|detail-body|news-body)", re.I)


def extract_article(html):
    """Devuelve dict(texto, estrategia, titulo, fecha). Estrategias en orden de fiabilidad."""
    tb = _TreeBuilder()
    try:
        tb.feed(html or "")
        tb.close()
    except Exception:
        pass
    meta = {}
    for m in tb.metas:
        key = (m.get("property") or m.get("name") or m.get("itemprop") or "").lower()
        if key and m.get("content") and key not in meta:
            meta[key] = m["content"]
    titulo = clean_text(meta.get("og:title") or tb.title)
    titulo = re.split(r"\s[|\-–—]\s", titulo)[0].strip() if len(titulo) > 40 else titulo
    fecha = ""
    for k in ("article:published_time", "datepublished", "publishdate", "pubdate", "date", "dc.date.issued",
              "sailthru.date", "og:published_time"):
        if k in meta and parse_date(meta[k]):
            fecha = meta[k]
            break
    if not fecha:
        for rx in (re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.I),
                   re.compile(r'<time[^>]+datetime\s*=\s*["\']([^"\']+)["\']', re.I)):
            m = rx.search((html or "")[:60000])
            if m and parse_date(m.group(1)):
                fecha = m.group(1)
                break

    def result(text, strat):
        return {"texto": "\n".join(text) if isinstance(text, list) else text, "estrategia": strat,
                "titulo": titulo, "fecha": fecha}

    root = tb.root
    # 1. contenedores con pista explícita de cuerpo de nota
    best, best_len = None, 0
    for n in _walk(root):
        if n.tag in ("div", "section", "article", "main") and (
                n.attrs.get("itemprop", "").lower() == "articlebody" or _BODY_HINT.search(_attr_blob(n))):
            ps = _paragraphs(n)
            L = sum(len(p) for p in ps)
            if L > best_len:
                best, best_len = ps, L
    if best_len > 250:
        return result(best, "pista_de_cuerpo")
    # 2. <article> / <main>
    for tag in ("article", "main"):
        cands = [n for n in _walk(root) if n.tag == tag]
        bestp, bl = None, 0
        for n in cands:
            ps = _paragraphs(n)
            L = sum(len(p) for p in ps)
            if L > bl:
                bestp, bl = ps, L
        if bl > 250:
            return result(bestp, tag)
    # 3. contenedor más denso (puntaje por párrafos hijos, readability simplificado)
    scores = {}
    for p in _walk(root):
        if p.tag != "p":
            continue
        txt = clean_text(_text(p))
        if len(txt) < 60 or _link_text(p) > 0.5 * len(txt) or _BOILER_TEXT.match(norm(txt)):
            continue
        sc = 1 + min(len(txt) // 100, 3) + txt.count(",")
        par = p.parent
        if par is not None:
            scores[id(par)] = (par, scores.get(id(par), (par, 0))[1] + sc)
            gp = par.parent
            if gp is not None:
                scores[id(gp)] = (gp, scores.get(id(gp), (gp, 0))[1] + sc / 2.0)
    if scores:
        node = max(scores.values(), key=lambda v: v[1])[0]
        ps = _paragraphs(node)
        if sum(len(p) for p in ps) > 250:
            return result(ps, "contenedor_denso")
    # 4. JSON-LD
    body = _json_ld_body(tb)
    if body:
        return result(clean_text(body), "json_ld")
    # 5. todos los párrafos
    ps = _paragraphs(root, min_len=30)
    if ps:
        return result(ps, "todos_los_p")
    return result("", "vacio")
