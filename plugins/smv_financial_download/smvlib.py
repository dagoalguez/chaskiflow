"""Cliente del portal SMV «Información Financiera» (formulario ASP.NET WebForms). Solo librería estándar.
Lo usa task.py; se puede probar suelto con probar_smv.py."""

import gzip
import html as htmllib
import http.cookiejar
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser

DEFAULT_URL = "https://www.smv.gob.pe/simv/Frm_InformacionFinanciera?data=A70181B60967D74090DCD93C4920AA1D769614EC12"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def norm(s):
    """Minúsculas, sin tildes, espacios simples."""
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


def safe_name(s, maxlen=80):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s[:maxlen].strip(" .")) or "SinNombre"


class PortalError(Exception):
    pass


# ----------------------------------------------------------------------------------- análisis del HTML
class _Page(HTMLParser):
    """Formulario (controles como los envía un navegador), lista de empresas y tabla de resultados."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.form = None            # {"action":..., "controls":[...]}
        self._in_form = False
        self._sel = None
        self._opt = None
        self.tables = []            # [{"id":..., "rows":[{"cells":[...], "href":..., "title":...}]}]
        self.pager = []             # [(destino, "Page$N")] de todos los enlaces de paginación de la página
        self._stack = []
        self._tab = None
        self._row = None
        self._cell = None
        self._href = None
        self._title = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if tag == "form" and self.form is None:
            self.form = {"action": a.get("action", ""), "id": a.get("id", ""), "controls": []}
            self._in_form = True
        elif self._in_form and tag == "input":
            self.form["controls"].append({"kind": "input", "type": (a.get("type") or "text").lower(), "name": a.get("name", ""),
                                          "value": a.get("value", ""), "checked": "checked" in a, "disabled": "disabled" in a, "id": a.get("id", "")})
        elif self._in_form and tag == "textarea":
            self.form["controls"].append({"kind": "input", "type": "textarea", "name": a.get("name", ""), "value": "",
                                          "checked": False, "disabled": "disabled" in a, "id": a.get("id", "")})
        elif self._in_form and tag == "select":
            self._sel = {"kind": "select", "name": a.get("name", ""), "id": a.get("id", ""), "disabled": "disabled" in a, "options": []}
            self.form["controls"].append(self._sel)
        elif tag == "option" and self._sel is not None:
            self._opt = {"value": a.get("value", ""), "text": "", "selected": "selected" in a, "_has_value": "value" in a}
            self._sel["options"].append(self._opt)
        elif tag == "table":
            self._tab = {"id": a.get("id", ""), "rows": []}
            self._stack.append(self._tab)
            self.tables.append(self._tab)
        elif tag == "tr" and self._tab is not None:
            self._row = {"cells": [], "href": "", "title": ""}
            self._tab["rows"].append(self._row)
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "a":
            href = a.get("href", "")
            m = re.search(r"__doPostBack\('([^']*)','(Page\$[^']*)'\)", href)
            if m:
                self.pager.append((m.group(1), m.group(2)))
            elif self._tab is not None and self._row is not None and href and not href.lower().startswith("javascript"):
                self._row["href"] = htmllib.unescape(href)
                self._row["title"] = a.get("title", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False
        elif tag == "select":
            self._sel = None
        elif tag == "option":
            self._opt = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row["cells"].append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr":
            self._row = None
        elif tag == "table":
            if self._stack:
                self._stack.pop()
            self._tab = self._stack[-1] if self._stack else None

    def handle_data(self, d):
        if self._opt is not None:
            self._opt["text"] += d
        if self._cell is not None:
            self._cell.append(d)


def parse_page(text):
    p = _Page()
    p.feed(text)
    return p


def form_defaults(form):
    """Pares (nombre, valor) como los enviaría un navegador, sin tocar nada."""
    out = []
    for c in form["controls"]:
        if not c["name"] or c["disabled"]:
            continue
        if c["kind"] == "select":
            opts = c["options"]
            if not opts:
                continue
            chosen = [o for o in opts if o["selected"]] or opts[:1]
            for o in chosen:
                out.append((c["name"], o["value"] if o["_has_value"] else o["text"].strip()))
        else:
            t = c["type"]
            if t in ("submit", "button", "image", "reset", "file"):
                continue
            if t in ("checkbox", "radio"):
                if c["checked"]:
                    out.append((c["name"], c["value"] or "on"))
            else:
                out.append((c["name"], c["value"]))
    return out


def find_control(form, suffix):
    for c in form["controls"]:
        if c["name"].endswith(suffix):
            return c
    return None


# ----------------------------------------------------------------------------------- cliente
class Portal:
    def __init__(self, url=DEFAULT_URL, timeout=60, verify_ssl=True, ca_bundle="", proxy="", user_agent="", retries=3, log=None):
        self.url, self.timeout, self.retries = url, timeout, max(0, int(retries))
        self.log = log or (lambda *_: None)
        self.headers = {"User-Agent": user_agent or UA, "Accept-Language": "es-PE,es;q=0.9,en;q=0.5",
                        "Accept-Encoding": "gzip, deflate"}
        handlers = [urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())]
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        sctx = ssl.create_default_context(cafile=ca_bundle or None)
        if not verify_ssl:
            sctx.check_hostname = False
            sctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=sctx))
        self.opener = urllib.request.build_opener(*handlers)
        self.page = None            # última página analizada (formulario con su estado actual)
        self.companies = []         # [(id, nombre)]

    # --- HTTP
    def _request(self, url, data=None, accept="text/html,*/*", max_bytes=None, referer=None):
        last = None
        for attempt in range(self.retries + 1):
            try:
                hdr = dict(self.headers)
                hdr["Accept"] = accept
                if referer:
                    hdr["Referer"] = referer
                body = None
                if data is not None:
                    body = urllib.parse.urlencode(data, encoding="utf-8").encode("ascii")
                    hdr["Content-Type"] = "application/x-www-form-urlencoded"
                    p = urllib.parse.urlsplit(self.url)
                    hdr["Origin"] = "%s://%s" % (p.scheme, p.netloc)
                req = urllib.request.Request(url, data=body, headers=hdr)
                with self.opener.open(req, timeout=self.timeout) as r:
                    raw = r.read(max_bytes) if max_bytes else r.read()
                    enc = (r.headers.get("Content-Encoding") or "").lower()
                    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except zlib.error:
                            raw = zlib.decompress(raw, -15)
                    return raw, r.headers, r.geturl()
            except urllib.error.HTTPError as e:
                last = "HTTP %d" % e.code
                if e.code in (400, 401, 403, 404):
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last = str(getattr(e, "reason", e))
            if attempt < self.retries:
                time.sleep(min(2 * (attempt + 1), 10))
        raise PortalError("%s (%s)" % (url[:120], last))

    @staticmethod
    def _text(raw, headers):
        cs = headers.get_content_charset() if headers is not None else None
        for enc in (cs, "utf-8", "cp1252"):
            if not enc:
                continue
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", "replace")

    # --- página principal
    def open(self):
        raw, hdr, final = self._request(self.url)
        self._load(self._text(raw, hdr), final)
        form = self.page.form
        if not form:
            raise PortalError("La página del portal no tiene el formulario esperado (¿cambió el portal o hay un bloqueo del proxy?)")
        sel = find_control(form, "cboDenominacionSocial")
        if not sel:
            raise PortalError("No se encontró la lista de empresas (cboDenominacionSocial) en el portal")
        self.companies = [(o["value"], re.sub(r"\s+", " ", o["text"]).strip()) for o in sel["options"]
                          if o["value"] not in ("", "-1", "0") and o["text"].strip()]
        return self.companies

    def _load(self, text, final):
        page = parse_page(text)
        if page.form is not None:
            self.page = page
            self.action = urllib.parse.urljoin(final, page.form["action"]) if page.form["action"] else self.url
        self.last_text = text
        return page

    def _post(self, overrides, extra=None):
        form = self.page.form
        pairs = form_defaults(form)
        ov = dict(overrides)
        data, seen = [], set()
        for k, v in pairs:
            if k in ov:
                if k not in seen:
                    data.append((k, ov[k]))
                    seen.add(k)
            else:
                data.append((k, v))
        for k, v in ov.items():
            if k not in seen:
                data.append((k, v))
        for k, v in (extra or {}).items():
            data = [(a, b) for a, b in data if a != k] + [(k, v)]
        raw, hdr, final = self._request(self.action, data=data, referer=self.url)
        return self._load(self._text(raw, hdr), final)

    # --- búsqueda
    def search(self, company_id, company_name, year, tipo="I", periodo="A"):
        """Devuelve filas [{denominacion, documento, expediente, fecha, url, titulo}] de todas las páginas de resultados."""
        form = self.page.form
        names = {}
        for suf in ("cboDenominacionSocial", "TextBox1", "cboTipo", "cboPeriodo", "cboAnio", "cbBuscar"):
            c = find_control(form, suf)
            if c is None:
                raise PortalError("El formulario del portal cambió: falta el campo %s" % suf)
            names[suf] = c["name"]
        ov = {names["cboDenominacionSocial"]: str(company_id), names["TextBox1"]: company_name, names["cboTipo"]: tipo,
              names["cboPeriodo"]: periodo, names["cboAnio"]: str(year), names["cbBuscar"]: "Buscar"}
        page = self._post(ov)
        rows, seen_pages = [], {"Page$1"}
        for _ in range(30):
            tab = next((t for t in page.tables if "grdInfoFinanciera" in t["id"]), None)
            if tab is None:
                tab = next((t for t in page.tables if t["rows"] and any("documento" in norm(c) for c in t["rows"][0]["cells"])), None)
            if tab is None:
                break
            for r in tab["rows"]:
                cells = r["cells"]
                if len(cells) < 4 or norm(cells[1]) == "documento" or not r["href"]:
                    continue
                rows.append({"denominacion": cells[0], "documento": cells[1], "expediente": cells[2], "fecha": cells[3],
                             "url": urllib.parse.urljoin(self.action, r["href"]), "titulo": r["title"]})
            nxt = [(t, a) for t, a in page.pager if "grdInfoFinanciera" in t and a not in seen_pages]
            if not nxt:
                break
            target, arg = nxt[0]
            seen_pages.add(arg)
            page = self._post(ov, extra={"__EVENTTARGET": target, "__EVENTARGUMENT": arg})
            ov.pop(names["cbBuscar"], None)                   # el cambio de página no es un clic en «Buscar»
        uniq, seen = [], set()
        for r in rows:
            k = (r["expediente"], r["url"], r["documento"])
            if k not in seen:
                seen.add(k)
                uniq.append(r)
        return uniq

    # --- descarga
    def download(self, url, dest, max_bytes=200 * 1024 * 1024):
        raw, hdr, final = self._request(url, accept="application/pdf,*/*", max_bytes=max_bytes, referer=self.url)
        if raw[:5] != b"%PDF-":
            head = raw[:200].decode("utf-8", "replace").replace("\n", " ")
            raise PortalError("la respuesta no es un PDF (%s): %s" % ((hdr.get("Content-Type") or "?"), head[:120]))
        tmp = dest + ".part"
        with open(tmp, "wb") as fh:
            fh.write(raw)
        import os
        os.replace(tmp, dest)
        return len(raw)
