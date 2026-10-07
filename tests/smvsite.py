"""Portal de prueba que imita «Información Financiera» de la SMV: formulario ASP.NET con __VIEWSTATE y sesión por cookie,
lista de empresas, tabla de resultados (con paginación en una empresa) y descarga de PDF."""

import re
import threading
import urllib.parse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.pdfmaker import make_pdf

COMPANIES = [("101", "ALFA ENERGIA S.A.A."), ("102", "BETA MINERA S.A."), ("103", "ACTIVO INMOBILIARIO PERUANO S.A.A. (ANTES FALABELLA PERU S.A.A.)"),
             ("104", "FALABELLA TIENDAS S.A."), ("105", "PAGINADA CORP S.A."), ("106", "SIN DATOS S.A.")]
PAGE_SIZE = 3

T = lambda *l: ("texto", list(l))      # noqa: E731
# (empresa, año, tipo) -> páginas del PDF «Estados Financieros y Dictamen»
DOCS = {
    ("101", 2021, "I"): [T("Estados financieros 2021", "Sin hechos relevantes de este tipo.")],
    ("101", 2022, "I"): [T("Nota 1", "Con fecha 30 de junio se aprobó la fusión por absorción con Beta.", "Nota 2 normal.")],
    ("101", 2023, "I"): [T("Nota 5", "Proceso de reorgani-", "zación societaria en curso.")],
    ("101", 2024, "I"): [("gris", 200)],                       # escaneado: la IA debe ver «fusión»
    ("101", 2025, "I"): [T("Portada"), ("gris", 90)],            # mixto: página escaneada sin hallazgo
    ("102", 2021, "I"): [T("Estados 2021", "La Escisión de la unidad minera fue aprobada.")],
    ("102", 2022, "I"): [("jpeg",)],                            # escaneado JPEG: la IA ve «reorganización societaria»
    ("102", 2023, "I"): [("jbig2",)],                           # no legible
    ("102", 2024, "I"): [T("Hechos posteriores", "Ninguno.")],
    ("103", 2022, "I"): [T("Notas", "FUSIONES y adquisiciones menores.")],
    ("104", 2022, "I"): [T("Notas", "Nada especial.")],
    ("105", 2021, "I"): [T("Paginada", "Texto normal 2021")],
    ("101", 2022, "C"): [T("Consolidado 2022", "fusión consolidada")],
}


def _guid(emp, year, kind, n=0):
    return "{%08X-0000-CD19-B5D2-%012X}" % (int(emp) * 1000 + year, hash((kind, n)) & 0xFFFFFFFFFFFF if False else (ord(kind[0]) * 1000 + n))


class PortalSite:
    def __init__(self):
        S = self
        S.hits, S.posts, S.fail_download_once, S.dl_failed = [], 0, set(), set()
        S.bad_download = set()
        S.sessions = {}
        S.require_session = True
        S.pdfs = {}                   # guid -> bytes

        def rows_for(emp, year, tipo):
            name = dict(COMPANIES)[emp]
            r = []
            if (emp, year, tipo) in DOCS or emp == "105":
                r.append(("Archivo Estructurado XBRL de Información Financiera", "%d%03d1" % (year, int(emp)), "31/03/%d 07:09:14 p.m." % (year + 1),
                          "/ConsultasP8/documento.aspx?vidDoc=" + urllib.parse.quote(_guid(emp, year, "X"))))
                r.append(("Estados Financieros", "%d%03d2" % (year, int(emp)), "31/03/%d 07:09:14 p.m." % (year + 1),
                          "/simv/Frm_DetalleInfoFinanciera.aspx?data=ABC%s" % emp))
            if emp == "105" and tipo == "I":
                for i in range(5):                                  # 5 filas: obliga a paginar (3 por página)
                    g = _guid(emp, year, "E", i)
                    pages = [T("Paginada %d #%d" % (year, i), "Texto normal")]
                    if year == 2022 and i == 4:
                        pages = [T("Paginada", "se acordó la escisión parcial")]    # el hallazgo está en la última página
                    S.pdfs[g] = make_pdf(pages)
                    r.append(("Estados Financieros y Dictamen" if i in (1, 4) else "Carta informando presentación de la información",
                              "%d%03d%d" % (year, 105, 50 + i), "05/03/%d 12:01:50 p.m." % (year + 1),
                              "/ConsultasP8/documento.aspx?vidDoc=" + urllib.parse.quote(g)))
            elif (emp, year, tipo) in DOCS:
                g = _guid(emp, year, "E")
                S.pdfs[g] = make_pdf(DOCS[(emp, year, tipo)])
                r.append(("Estados Financieros y Dictamen", "%d%03d9" % (year, int(emp)), "05/03/%d 12:01:50 p.m." % (year + 1),
                          "/ConsultasP8/documento.aspx?vidDoc=" + urllib.parse.quote(g)))
                if (emp, year) == ("101", 2022) and tipo == "I":
                    g2 = _guid(emp, year, "R")
                    S.pdfs[g2] = make_pdf([T("Re-presentación", "Texto corregido, sin hallazgos.")])
                    r.append(("Estados Financieros y Dictamen", "%d%03d8" % (year, int(emp)), "20/05/%d 09:00:00 a.m." % (year + 1),
                              "/ConsultasP8/documento.aspx?vidDoc=" + urllib.parse.quote(g2)))      # re-presentación: otro documento
            return name, r

        def page_html(sid, state, results=None, pager_page=1):
            S.state_n = getattr(S, "state_n", 0) + 1
            hidden = ('<div class="aspNetHidden"><input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="VS|%s|%d">'
                      '<input type="hidden" name="__VIEWSTATEGENERATOR" value="GEN123">'
                      '<input type="hidden" name="__EVENTVALIDATION" value="EV|%s"></div>' % (sid, S.state_n, sid))
            opts = '<option value="-1">Ingrese nombre de la empresa</option>' + "".join(
                '<option %svalue="%s">%s</option>' % ('selected="selected" ' if state.get("emp") == c else "", c, escape(n)) for c, n in COMPANIES)
            years = '<option value="-1">TODOS</option>' + "".join('<option value="%d">%d</option>' % (y, y) for y in range(2026, 1998, -1))
            table = ""
            if results is not None:
                allr = results
                chunk = allr[(pager_page - 1) * PAGE_SIZE:pager_page * PAGE_SIZE] if len(allr) > PAGE_SIZE else allr
                body = "".join('<tr class="item-grid"><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td style="width:30px;"><a id="MainContent_grdInfoFinanciera_HyperLink1_%d" '
                               'title="Descargar Documento" href="%s" target="_blank"><img src="/x.png"></a></td></tr>' % (
                                   escape(state["name"]), escape(d), e, f, i, h) for i, (d, e, f, h) in enumerate(chunk))
                pager = ""
                if len(allr) > PAGE_SIZE:
                    npages = (len(allr) + PAGE_SIZE - 1) // PAGE_SIZE
                    links = "".join('<td><a href="javascript:__doPostBack(&#39;ctl00$MainContent$grdInfoFinanciera&#39;,&#39;Page$%d&#39;)">%d</a></td>' % (n, n)
                                    if n != pager_page else "<td><span>%d</span></td>" % n for n in range(1, npages + 1))
                    pager = '<tr class="pager"><td colspan="5"><table><tbody><tr>%s</tr></tbody></table></td></tr>' % links
                table = ('<table class="CentrarDiv" id="MainContent_grdInfoFinanciera"><tbody><tr><th>Denominación Social</th><th>Documento</th>'
                         '<th>N° Expediente</th><th>Fecha de Presentación</th><th></th></tr>%s%s</tbody></table>' % (body, pager))
                if not allr:
                    table = '<div>No se encontraron registros</div>'
            return ('<html><body><form method="post" action="./Frm_InformacionFinanciera?data=ABC" id="frmMain">%s'
                    '<input name="ctl00$txtSearch" type="text" id="txtSearch"><input type="image" name="ctl00$ibtnB" id="ibtnB" src="/b.png">'
                    '<input type="radio" name="ctl00$rbNuevo" value="rbEmpresa" checked="checked"><input type="radio" name="ctl00$rbNuevo" value="rbPortal">'
                    '<input id="MainContent_cbxRetiradas" type="checkbox" name="ctl00$MainContent$cbxRetiradas">'
                    '<input name="ctl00$MainContent$TextBox1" type="text" value="%s" id="MainContent_TextBox1">'
                    '<select name="ctl00$MainContent$cboDenominacionSocial" id="MainContent_cboDenominacionSocial">%s</select>'
                    '<input type="radio" name="ctl00$MainContent$cboTipo" value="I" checked="checked"><input type="radio" name="ctl00$MainContent$cboTipo" value="C">'
                    '<input type="radio" name="ctl00$MainContent$cboPeriodo" value="T"><input type="radio" name="ctl00$MainContent$cboPeriodo" value="A" checked="checked">'
                    '<select name="ctl00$MainContent$cboAnio" id="MainContent_cboAnio">%s</select>'
                    '<select name="ctl00$MainContent$cboTrimestre" disabled="disabled"><option value="-1">TODOS</option><option value="1" selected="selected">TRIMESTRE I</option></select>'
                    '<input type="submit" name="ctl00$MainContent$cbBuscar" value="Buscar" id="MainContent_cbBuscar">%s</form></body></html>'
                    % (hidden, escape(state.get("name", "")), opts, years, table))

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def out(self, code, body, ctype="text/html; charset=utf-8", extra=None):
                b = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(b)

            def sid(self):
                m = re.search(r"ASP.NET_SessionId=(\w+)", self.headers.get("Cookie") or "")
                return m.group(1) if m else None

            def do_GET(self):
                S.hits.append(self.path)
                u = urllib.parse.urlsplit(self.path)
                if u.path.endswith("Frm_InformacionFinanciera"):
                    sid = "S%d" % (len(S.sessions) + 1)
                    S.sessions[sid] = {}
                    return self.out(200, page_html(sid, {}), extra={"Set-Cookie": "ASP.NET_SessionId=%s; path=/; HttpOnly" % sid})
                if u.path.endswith("documento.aspx"):
                    g = urllib.parse.parse_qs(u.query).get("vidDoc", [""])[0]
                    if g in S.bad_download:
                        return self.out(200, "<html>Sesión expirada</html>")
                    if g in S.fail_download_once and g not in S.dl_failed:
                        S.dl_failed.add(g)
                        return self.out(500, "boom")
                    if g in S.pdfs:
                        return self.out(200, S.pdfs[g], "application/pdf")
                    return self.out(404, "no existe")
                self.out(404, "no")

            def do_POST(self):
                S.posts += 1
                n = int(self.headers.get("Content-Length") or 0)
                f = {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"), keep_blank_values=True).items()}
                sid = self.sid()
                vs = f.get("__VIEWSTATE", "")
                if S.require_session and (sid not in S.sessions or not vs.startswith("VS|%s|" % sid) or f.get("__EVENTVALIDATION") != "EV|%s" % sid):
                    return self.out(500, "Validation of viewstate MAC failed")
                if "ctl00$MainContent$cboTrimestre" in f:
                    return self.out(500, "el trimestre deshabilitado no debe enviarse")
                sess = S.sessions[sid]
                emp = f.get("ctl00$MainContent$cboDenominacionSocial")
                if f.get("__EVENTTARGET", "").endswith("grdInfoFinanciera"):
                    page = int(f["__EVENTARGUMENT"].split("$")[1])
                    return self.out(200, page_html(sid, sess["state"], sess["results"], page))
                if emp not in dict(COMPANIES) or "ctl00$MainContent$cbBuscar" not in f:
                    return self.out(200, page_html(sid, {}))
                year, tipo = int(f["ctl00$MainContent$cboAnio"]), f["ctl00$MainContent$cboTipo"]
                if f.get("ctl00$MainContent$cboPeriodo") != "A":
                    return self.out(200, page_html(sid, {"emp": emp, "name": dict(COMPANIES)[emp]}, []))
                name, r = rows_for(emp, year, tipo)
                state = {"emp": emp, "name": name}
                sess["state"], sess["results"] = state, r
                self.out(200, page_html(sid, state, r, 1))

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.url = self.base + "/simv/Frm_InformacionFinanciera?data=ABC"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def guid(self, emp, year, kind="E", n=0):
        return _guid(emp, year, kind, n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
