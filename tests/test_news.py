"""Pruebas del paquete de noticias: extractor, feeds, scraping, recurrencia y Outlook (modo prueba)."""

import json
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugins" / "news_feed_scrape"))

import newslib  # noqa: E402
from chaskiflow.engine import Engine  # noqa: E402
from chaskiflow.plugin_loader import PluginRegistry  # noqa: E402
from tests.helpers import PLUGINS  # noqa: E402

LAV = ("La Fiscalía informó que tres personas fueron detenidas durante un operativo contra una red de lavado "
       "de activos que operaba en Lima y Callao, según el comunicado oficial difundido por el Ministerio Público. ",
       "Los implicados habrían movido más de diez millones de soles a través de empresas fachada, de acuerdo con la "
       "investigación preliminar, que continúa en curso bajo reserva de la Fiscalía especializada. ",
       "Las autoridades no descartan más detenciones en los próximos días, mientras se analizan los documentos "
       "incautados durante los allanamientos realizados en distintos distritos de la capital. ")
CLIMA = ("El Senamhi pronosticó lluvias de ligera intensidad en la sierra central durante el fin de semana, con "
         "temperaturas mínimas que descenderán hasta los cero grados en las zonas altas del país. ",
         "Los agricultores deberán tomar precauciones para proteger los cultivos de papa y quinua, advirtió el "
         "ministerio, que recomendó revisar los boletines meteorológicos de manera frecuente. ")


def now_iso(hours_ago=1):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def page(paras, layout="hint", title="Titular", extra=""):
    ps = "".join("<p>%s</p>" % p for p in paras)
    body = {
        "hint": '<div class="story"><div class="article-body">%s</div></div>' % ps,
        "article": "<article>%s</article>" % ps,
        "dense": '<div id="x"><div class="c">%s</div></div>' % ps,
        "jsonld": "<div>sin parrafos</div><script type=\"application/ld+json\">%s</script>"
                  % json.dumps({"@type": "NewsArticle", "articleBody": " ".join(paras)}),
    }[layout]
    return ('<html><head><title>%s | Medio</title><meta property="og:title" content="%s">'
            '<meta property="article:published_time" content="%s"></head><body><nav><a href="/">Inicio</a></nav>%s'
            '<div class="related-posts"><p>Nota relacionada enlazada que debe descartarse del cuerpo principal del texto.</p></div>'
            '<footer><p>Todos los derechos reservados por la empresa propietaria de este sitio web.</p></footer>'
            '</body></html>' % (title, title, now_iso(), body + extra))


class NewsServer:
    """Medios falsos: sitemap de noticias (A), RSS (B), portada HTML (C), bloqueo de proxy (D), 403 (E)."""

    def __init__(self):
        S = self
        self.hits = []
        self.arts = {
            "/a/politica/lavado-activos-red-detenidos-lima": (page(LAV, "hint", "Caen tres por lavado de activos en Lima")),
            "/a/economia/senamhi-lluvias-sierra-central-fin-de-semana": (page(CLIMA, "article", "Lluvias en la sierra central")),
            "/a/espectaculos/horoscopo-de-hoy-todos-los-signos-del-zodiaco": (page(CLIMA, "hint", "Horóscopo de hoy")),
            "/a/politica/nota-demasiado-corta-sin-texto-suficiente": ("<html><body><p>Muy corta.</p></body></html>"),
            "/b/nota/red-de-lavado-de-activos-tres-detenidos-callao": (page(LAV, "dense", "Tres detenidos por red de lavado")),
            "/c/politica/investigan-lavado-de-activos-red-fachada-lima": (page(LAV, "jsonld", "Investigan red de lavado")),
        }

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def send(self, code, body, ctype="text/html; charset=utf-8"):
                b = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                S.hits.append(self.path)
                base = S.base
                p = self.path
                if p == "/a/sitemap.xml":
                    items = "".join(
                        "<url><loc>%s%s</loc><news:news><news:publication_date>%s</news:publication_date>"
                        "<news:title>%s</news:title></news:news></url>" % (base, k, d, t) for k, d, t in [
                            ("/a/politica/lavado-activos-red-detenidos-lima", now_iso(2), "Caen tres por lavado de activos en Lima"),
                            ("/a/economia/senamhi-lluvias-sierra-central-fin-de-semana", now_iso(3), "Lluvias en la sierra central"),
                            ("/a/espectaculos/horoscopo-de-hoy-todos-los-signos-del-zodiaco", now_iso(1), "Horóscopo de hoy"),
                            ("/a/politica/nota-demasiado-corta-sin-texto-suficiente", now_iso(1), "Nota corta del día de hoy en el medio"),
                            ("/a/politica/nota-vieja-de-hace-una-semana-en-el-sitio", now_iso(24 * 7), "Vieja"),
                        ])
                    return self.send(200, '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                                          'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">%s</urlset>' % items, "application/xml")
                if p == "/a/index.xml":
                    return self.send(200, '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>%s/a/sitemap.xml</loc></sitemap></sitemapindex>' % base, "application/xml")
                if p == "/b/rss.xml":
                    d = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S +0000")
                    return self.send(200, '<?xml version="1.0"?><rss version="2.0"><channel><title>B</title><item><title>Tres detenidos por red de lavado</title>'
                                          '<link>%s/b/nota/red-de-lavado-de-activos-tres-detenidos-callao</link><pubDate>%s</pubDate></item></channel></rss>' % (base, d), "application/rss+xml")
                if p == "/c/politica/":
                    return self.send(200, '<html><body><a href="/c/politica/investigan-lavado-de-activos-red-fachada-lima">Investigan red de lavado de activos</a>'
                                          '<a href="/c/politica/">Politica</a><a href="/tag/algo-largo-de-prueba-para-slug">tag</a><a href="https://otro.com/x/y-zzzzzzzzzzzzzzzzzz">ext</a>'
                                          '<a href="/cdn-cgi/l/email-protection">x</a></body></html>')
                if p == "/d/feed.xml":
                    return self.send(403, "<html><body>Web Page Blocked - Skyhigh Web Gateway. URL Categories: Gambling</body></html>")
                if p == "/e/feed.xml":
                    return self.send(403, "Forbidden")
                if p == "/f/feed.xml":
                    return self.send(200, "<rss><channel><item>roto")
                if p in S.arts:
                    return self.send(200, S.arts[p])
                self.send(404, "no")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class ExtractorTests(unittest.TestCase):
    def test_layouts(self):
        for layout, strat in (("hint", "pista_de_cuerpo"), ("article", "article"), ("dense", "contenedor_denso"),
                              ("jsonld", "json_ld")):
            r = newslib.extract_article(page(LAV, layout, "Caen tres por lavado de activos en Lima"))
            self.assertEqual(r["estrategia"], strat, layout)
            self.assertIn("empresas fachada", r["texto"], layout)
            self.assertNotIn("relacionada enlazada", r["texto"], layout)
            self.assertNotIn("derechos reservados", r["texto"], layout)
            self.assertEqual(r["titulo"], "Caen tres por lavado de activos en Lima")
            self.assertTrue(newslib.parse_date(r["fecha"]))

    def test_boilerplate_and_links_removed(self):
        extra = '<div class="x"><p><a href="/1">Lee también: algo que enlaza a otra nota muy interesante</a></p></div>'
        r = newslib.extract_article(page(LAV, "hint", extra=extra))
        self.assertNotIn("Lee también", r["texto"])

    def test_garbage_html_does_not_crash(self):
        for h in ("", "<<<>>>", "<p>sin cerrar <div><p>otro", "<html><body><script>x", "\x00\x01"):
            r = newslib.extract_article(h)
            self.assertIn("texto", r)

    def test_entities_and_accents(self):
        r = newslib.extract_article("<article><p>" + ("La investigación &amp; los señores de la comisión analizaron el caso. " * 6) + "</p></article>")
        self.assertIn("investigación & los señores", r["texto"])

    def test_detect_keywords_ignores_accents_and_case(self):
        self.assertEqual(newslib.detect("Caso de LAVADO de Activos y corrupción", ["lavado de activos", "corrupcion", "tributo"]),
                         ["corrupcion", "lavado de activos"])
        self.assertEqual(newslib.detect("contrabandista", ["contrabando"]), [])  # palabra completa

    def test_parse_urls_and_dates(self):
        self.assertEqual(newslib.parse_urls("[a](https://x.pe/a), https://y.pe/b\nhttps://x.pe/a nada"),
                         ["https://x.pe/a", "https://y.pe/b"])
        for raw in ("2026-10-07T08:00:00-05:00", "Wed, 07 Oct 2026 08:00:00 -0500", "2026-10-07", "2026-10-07T13:00:00Z"):
            self.assertIsNotNone(newslib.parse_date(raw), raw)
        self.assertIsNone(newslib.parse_date("ayer"))


class FeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = NewsServer()
        cls.f = newslib.Fetcher(timeout=10, retries=0)

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def items(self, path, ftype="auto"):
        u = self.srv.base + path
        return newslib.parse_feed(self.f.get(u), ftype, u, fetch=self.f.get)

    def test_news_sitemap(self):
        it = self.items("/a/sitemap.xml")
        self.assertEqual(len(it), 5)
        self.assertTrue(it[0]["titulo"].startswith("Caen tres"))
        self.assertTrue(it[0]["fecha_raw"])

    def test_sitemap_index_follows_children(self):
        self.assertEqual(len(self.items("/a/index.xml")), 5)

    def test_rss(self):
        it = self.items("/b/rss.xml")
        self.assertEqual(len(it), 1)
        self.assertIsNotNone(newslib.parse_date(it[0]["fecha_raw"]))

    def test_html_index_only_article_links(self):
        it = self.items("/c/politica/")
        self.assertEqual([i["url"].rsplit("/", 1)[-1] for i in it], ["investigan-lavado-de-activos-red-fachada-lima"])

    def test_proxy_block_is_detected(self):
        with self.assertRaises(newslib.FetchError) as cm:
            self.f.get(self.srv.base + "/d/feed.xml")
        self.assertEqual(cm.exception.kind, "PROXY_BLOCK")
        self.assertIn("Gambling", str(cm.exception))

    def test_plain_403_is_http_error(self):
        with self.assertRaises(newslib.FetchError) as cm:
            self.f.get(self.srv.base + "/e/feed.xml")
        self.assertEqual(cm.exception.kind, "HTTP")

    def test_broken_xml(self):
        with self.assertRaises(ValueError):
            self.items("/f/feed.xml")

    def test_connection_refused(self):
        with self.assertRaises(newslib.FetchError) as cm:
            newslib.Fetcher(timeout=2, retries=0).get("http://127.0.0.1:1/x")
        self.assertEqual(cm.exception.kind, "RED")


class PluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = NewsServer()
        cls.tmp = Path(tempfile.mkdtemp())
        cls.engine = Engine(PluginRegistry([PLUGINS]), workdir_root=cls.tmp / "runs")

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def scrape(self, **cfg):
        base = {"medio": "A", "feed_urls": self.srv.base + "/a/sitemap.xml", "workers": 4, "timeout": 10,
                "include_paths": "", "relevance_keywords": "lavado de activos, corrupcion, contrabando, evasion"}
        base.update(cfg)
        w = {"name": "t", "nodes": [{"id": "A", "label": "A", "type": "news_feed_scrape", "config": base}], "edges": []}
        return self.engine.run(w).nodes["A"]

    def test_scrape_sitemap_filters(self):
        r = self.scrape()
        self.assertEqual(r["status"], "ok", r["error"])
        res = r["result"]
        urls = [x["url"].rsplit("/", 1)[-1] for x in res["rows"]]
        self.assertEqual(sorted(urls), ["lavado-activos-red-detenidos-lima", "senamhi-lluvias-sierra-central-fin-de-semana"])
        d = res["descartes"]
        self.assertEqual((d["fuera_de_ventana"], d["excluidas_titulo"], d["cuerpo_corto"] + d["cuerpo_vacio"]), (1, 1, 1))
        lav = next(x for x in res["rows"] if "lavado" in x["url"])
        self.assertEqual(lav["ind_relevante"], 1)
        self.assertEqual(lav["palabras_detectadas"], "lavado de activos")
        self.assertEqual(lav["medio"], "A")
        self.assertTrue(lav["fecha"] and lav["contenido"] and lav["fecha_extraccion"])
        self.assertEqual(lav["seccion"], "a")
        clima = next(x for x in res["rows"] if "senamhi" in x["url"])
        self.assertEqual(clima["ind_relevante"], 0)
        self.assertEqual(res["_kind"], "news_rows")

    def test_only_relevant_and_include_paths(self):
        res = self.scrape(only_relevant=True)["result"]
        self.assertEqual(len(res["rows"]), 1)
        res = self.scrape(include_paths="/economia/")["result"]
        self.assertEqual([x["seccion"] for x in res["rows"]], ["a"])
        self.assertEqual(len(res["rows"]), 1)
        self.assertGreaterEqual(res["descartes"]["otra_seccion"], 3)

    def test_hours_back_zero_means_no_limit(self):
        res = self.scrape(hours_back=0, exclude_keywords="")["result"]
        # sin ventana ni exclusiones entra la nota vieja (cuyo cuerpo no existe en el servidor -> error)
        self.assertGreaterEqual(res["descartes"]["errores"], 1)
        self.assertEqual(res["descartes"]["fuera_de_ventana"], 0)

    def test_rss_and_html_index_and_index(self):
        self.assertEqual(len(self.scrape(medio="B", feed_urls=self.srv.base + "/b/rss.xml")["result"]["rows"]), 1)
        r = self.scrape(medio="C", feed_urls=self.srv.base + "/c/politica/", feed_type="html_index")["result"]
        self.assertEqual(len(r["rows"]), 1)
        self.assertTrue(r["rows"][0]["fecha_iso"], "la fecha se saca del artículo cuando el índice no la trae")
        self.assertEqual(len(self.scrape(feed_urls=self.srv.base + "/a/index.xml")["result"]["rows"]), 2)

    def test_proxy_block_gives_actionable_error(self):
        r = self.scrape(feed_urls=self.srv.base + "/d/feed.xml")
        self.assertEqual(r["status"], "error")
        self.assertIn("proxy institucional", r["error"])
        self.assertIn("TI", r["error"])

    def test_bad_config(self):
        self.assertEqual(self.scrape(feed_urls="no es url")["status"], "error")
        self.assertIn("regex", self.scrape(url_regex="([")["error"].lower())

    def test_skip_seen(self):
        d = str(self.tmp / "vistas")
        a = self.scrape(skip_seen=True, seen_dir=d)["result"]
        b = self.scrape(skip_seen=True, seen_dir=d)["result"]
        self.assertEqual((len(a["rows"]), len(b["rows"])), (2, 0))

    def test_full_pipeline_recurrence_and_exports(self):
        out = str(self.tmp / "salida")
        nodes = [
            {"id": "n1", "label": "A", "type": "news_feed_scrape", "config": {"relevance_keywords": "lavado de activos, corrupcion, contrabando, evasion", "medio": "A", "feed_urls": self.srv.base + "/a/sitemap.xml", "timeout": 10}},
            {"id": "n2", "label": "B", "type": "news_feed_scrape", "config": {"relevance_keywords": "lavado de activos, corrupcion, contrabando, evasion", "medio": "B", "feed_urls": self.srv.base + "/b/rss.xml", "timeout": 10}},
            {"id": "n3", "label": "C", "type": "news_feed_scrape", "config": {"relevance_keywords": "lavado de activos, corrupcion, contrabando, evasion", "medio": "C", "feed_urls": self.srv.base + "/c/politica/", "feed_type": "html_index", "timeout": 10}},
            {"id": "n4", "label": "Roto", "type": "news_feed_scrape", "on_error": "continue",
             "config": {"medio": "Roto", "feed_urls": self.srv.base + "/d/feed.xml", "timeout": 10}},
            {"id": "n5", "label": "Consolidar", "type": "news_consolidate",
             "config": {"medios_esperados": "A, B, C, Roto"}},
            {"id": "n6", "label": "Csv", "type": "export_csv",
             "config": {"data": "{{Consolidar.result.rows}}", "output_dir": out, "filename": "noticias",
                        "columns": "medio,titulo,recurrencia,nro_medios,medios,ind_relevante"}},
            {"id": "n8", "label": "Excel", "type": "export_xlsx",
             "config": {"data": "{{Consolidar.result.rows}}", "output_dir": out, "filename": "noticias"}},
            {"id": "n7", "label": "Correo", "type": "outlook_send",
             "config": {"to": "equipo@ejemplo.org; otra@ejemplo.org", "subject": "Noticias %Y",
                        "body": "{{Consolidar.result.resumen_md}}",
                        "attachments": "{{Csv.result.file_paths}}\n{{Excel.result.file_paths}}",
                        "dry_run": True}},
        ]
        edges = [{"source": s, "target": "n5"} for s in ("n1", "n2", "n3", "n4")] + \
                [{"source": "n5", "target": "n6"}, {"source": "n6", "target": "n7"}, {"source": "n5", "target": "n7"},
                 {"source": "n5", "target": "n8"}, {"source": "n8", "target": "n7"}]
        res = self.engine.run({"name": "noticias", "nodes": nodes, "edges": edges})
        self.assertEqual(res.status, "partial", {k: v["error"] for k, v in res.nodes.items() if v["error"]})
        self.assertEqual(res.nodes["Roto"]["status"] if "Roto" in res.nodes else res.nodes["n4"]["status"], "error")
        c = res.nodes["n5"]["result"]
        self.assertEqual(c["total"], 4)                      # A: 2, B: 1, C: 1
        rec = [r for r in c["rows"] if r["recurrencia"] == "Sí"]
        self.assertEqual(len(rec), 3)
        self.assertEqual({r["medios"] for r in rec}, {"A, B, C"})
        self.assertEqual({r["nro_medios"] for r in rec}, {3})
        self.assertEqual(c["grupos_recurrencia"], 1)
        self.assertEqual(c["rows"][0]["ind_relevante"], 1)  # relevantes primero
        self.assertEqual(c["medios_sin_datos"], ["Roto"])
        self.assertIn("Medios sin noticias", c["resumen_md"])
        mail = res.nodes["n7"]["result"]
        self.assertTrue(mail["dry_run"] and not mail["sent"])
        self.assertEqual(len(mail["attachments"]), 2)          # CSV y XLSX juntos
        self.assertEqual(sorted(Path(a).suffix for a in mail["attachments"]), [".csv", ".xlsx"])
        self.assertTrue(all(Path(a).is_file() for a in mail["attachments"]))
        csv_path = [a for a in mail["attachments"] if a.endswith(".csv")][0]
        text = Path(csv_path).read_text(encoding="utf-8-sig")
        self.assertIn("Caen tres por lavado", text)

    def test_example_workflow_is_valid(self):
        import json
        ex = json.loads((PLUGINS.parent / "examples" / "noticias_diario.json").read_text(encoding="utf-8"))
        errors, _ = self.engine.validate(ex)
        self.assertEqual(errors, [])
        mail = [n for n in ex["nodes"] if n["type"] == "outlook_send"][0]
        self.assertIn("Csv.result", mail["config"]["attachments"])
        self.assertIn("Excel.result", mail["config"]["attachments"])

    def test_example_export_headers_exact(self):
        """El CSV y el XLSX del ejemplo salen con los encabezados y el orden exactos del archivo original."""
        import csv, json, re, zipfile
        expected = ["Medio", "Fecha publicación", "Título", "URL", "Sección", "Relevante", "Palabras detectadas",
                    "Recurrencia", "N° medios", "Medios", "ID recurrencia", "Contenido"]
        ex = json.loads((PLUGINS.parent / "examples" / "noticias_diario.json").read_text(encoding="utf-8"))
        row = {k: "x" for k in ("medio", "fecha", "titulo", "url", "seccion", "ind_relevante", "palabras_detectadas",
                                "recurrencia", "nro_medios", "medios", "id_recurrencia", "contenido", "extra")}
        out = str(self.tmp / "hdr")
        nodes = []
        for n in ex["nodes"]:
            if n["type"] in ("export_csv", "export_xlsx"):
                c = dict(n["config"], data=[row], output_dir=out, filename="h_" + n["type"])
                nodes.append({"id": n["id"], "label": n["label"], "type": n["type"], "config": c})
        res = self.engine.run({"name": "h", "nodes": nodes, "edges": []})
        self.assertEqual(res.status, "ok", {k: v["error"] for k, v in res.nodes.items() if v["error"]})
        csv_path = [Path(v["result"]["file_path"]) for v in res.nodes.values() if v["result"]["file_path"].endswith(".csv")][0]
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            self.assertEqual(next(csv.reader(f, delimiter=";")), expected)
        x_path = [v["result"]["file_path"] for v in res.nodes.values() if v["result"]["file_path"].endswith(".xlsx")][0]
        xml = zipfile.ZipFile(x_path).read("xl/worksheets/sheet1.xml").decode("utf-8")
        first = xml.split("</row>")[0]
        self.assertEqual([t for t in re.findall(r"<t[^>]*>([^<]*)</t>", first)], expected)

    def test_consolidate_without_inputs_fails_clearly(self):
        w = {"name": "t", "nodes": [{"id": "A", "label": "A", "type": "news_consolidate", "config": {}}], "edges": []}
        r = self.engine.run(w).nodes["A"]
        self.assertEqual(r["status"], "error")
        self.assertIn("DESPUÉS", r["error"])

    def test_consolidate_same_medio_not_recurrent_when_cross(self):
        rows = [{"medio": "A", "titulo": "Lavado de activos red Lima", "url": "http://x/1", "contenido": " ".join(LAV)},
                {"medio": "A", "titulo": "Lavado de activos red Lima otra vez", "url": "http://x/2", "contenido": " ".join(LAV)},
                {"medio": "B", "titulo": "Lluvias", "url": "http://x/3", "contenido": " ".join(CLIMA)}]
        w = {"name": "t", "nodes": [{"id": "A", "label": "A", "type": "news_consolidate", "config": {"sources": rows}}], "edges": []}
        res = self.engine.run(w).nodes["A"]["result"]
        self.assertEqual(res["recurrentes"], 0)
        w["nodes"][0]["config"]["cross_medio"] = False
        res = self.engine.run(w).nodes["A"]["result"]
        self.assertEqual(res["recurrentes"], 2)

    def test_outlook_validation(self):
        def go(**cfg):
            base = {"to": "a@b.pe", "subject": "s", "body": "hola", "dry_run": True}
            base.update(cfg)
            return self.engine.run({"name": "t", "nodes": [{"id": "A", "label": "A", "type": "outlook_send", "config": base}], "edges": []}).nodes["A"]
        self.assertEqual(go()["status"], "ok")
        self.assertIn("inválido", go(to="no-es-correo")["error"])
        self.assertIn("adjunto", go(attachments="/no/existe.xlsx")["error"])
        self.assertEqual(go(body="   ")["status"], "error")
        if sys.platform != "win32":
            self.assertIn("Windows", go(dry_run=False)["error"])


if __name__ == "__main__":
    unittest.main()
