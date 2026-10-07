"""Sucursales desde una lista de enlaces: lista, rastreo, IA local (servidor falso) y exportación."""

import csv
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chaskiflow.engine import Engine  # noqa: E402
from chaskiflow.plugin_loader import PluginRegistry  # noqa: E402
from tests.fakellm import FakeLLM  # noqa: E402
from tests.helpers import PLUGINS  # noqa: E402
from tests.locsite import Site  # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.engine = Engine(PluginRegistry([PLUGINS]), workdir_root=cls.tmp / "runs")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_node(self, typ, config, secrets=None):
        eng = Engine(PluginRegistry([PLUGINS]), workdir_root=self.tmp / "runs",
                     secrets=(lambda n: (secrets or {}).get(n)))
        return eng.run({"name": "t", "nodes": [{"id": "A", "label": "A", "type": typ, "config": config}], "edges": []}).nodes["A"]


class UrlList(Base):
    def w(self, name, text, enc="utf-8"):
        p = self.tmp / name
        p.write_bytes(text.encode(enc))
        return str(p)

    def test_csv_semicolon_header_and_names(self):
        f = self.w("a.csv", "Empresa;Web;Notas\nFerretería Ñandú;ferreteria.pe;x\nBanco;https://www.banco.pe/;y\nRepetido;FERRETERIA.pe/;z\nMalo;no es link;w\n", "cp1252")
        r = self.run_node("url_list_read", {"file_path": f, "name_column": "Empresa"})
        self.assertEqual(r["status"], "ok", r["error"])
        res = r["result"]
        self.assertEqual(res["urls"], ["https://ferreteria.pe", "https://www.banco.pe/"])
        self.assertEqual(res["items"][0]["name"], "Ferretería Ñandú")
        self.assertEqual(sorted(s["motivo"] for s in res["skipped"]), ["duplicado", "no parece un enlace"])

    def test_txt_and_limit(self):
        f = self.w("a.txt", "# comentario\nhttps://a.pe\n\nb.pe   algo\nhttps://c.pe/x\n")
        res = self.run_node("url_list_read", {"file_path": f, "limit": 2})["result"]
        self.assertEqual(res["urls"], ["https://a.pe", "https://b.pe"])

    def test_errors(self):
        self.assertIn("No existe el archivo", self.run_node("url_list_read", {"file_path": str(self.tmp / "no.csv")})["error"])
        f = self.w("b.csv", "a;b\n1;2\n")
        self.assertIn("No encontré una columna", self.run_node("url_list_read", {"file_path": f})["error"])
        f = self.w("c.csv", "x;y\nhttps://a.pe;1\n")
        self.assertIn("No existe la columna 'zzz'", self.run_node("url_list_read", {"file_path": f, "column": "zzz"})["error"])


class Crawl(Base):
    def crawl(self, base, **kw):
        cfg = {"sites": [{"name": "Andina", "url": base + "/"}], "delay": 0, "workers": 1}
        cfg.update(kw)
        r = self.run_node("site_locations_crawl", cfg)
        self.assertEqual(r["status"], "ok", r["error"])
        return r["result"]

    def test_finds_every_way_of_publishing_branches(self):
        with Site() as s:
            res = self.crawl(s.base)
            hits = s.hits
        by = {x["metodo"] for x in res["rows"]}
        self.assertTrue({"address", "jsonld", "json", "texto"} <= by, by)
        dirs = " | ".join(x["direccion"] for x in res["rows"])
        for esperado in ("Av. Larco 1234", "Av. Primavera 890", "Calle Mercaderes 345", "Jr. Constitución 456", "Av. España 777", "Av. Grau 100"):
            self.assertIn(esperado, dirs)
        self.assertEqual(res["total"], 6)
        arequipa = [x for x in res["rows"] if "Mercaderes" in x["direccion"]][0]
        self.assertAlmostEqual(arequipa["lat"], -16.3989)                     # mapa incrustado asociado al texto
        self.assertAlmostEqual(arequipa["lng"], -71.5375)
        miraf = [x for x in res["rows"] if "Larco" in x["direccion"]][0]
        self.assertIn("445-1234", miraf["telefono"])
        self.assertFalse(any(h.startswith("/privado") for h in hits), "robots.txt debe respetarse")
        self.assertFalse(any("externo" in h for h in hits))
        self.assertNotIn("/catalogo.pdf", hits)
        self.assertEqual(res["sin_resultados"], [])
        self.assertTrue(res["sites"][0]["paginas"] >= 6)

    def test_without_robots_option_and_page_limit(self):
        with Site() as s:
            res = self.crawl(s.base, respect_robots=False)
            self.assertTrue(any(h.startswith("/privado") for h in s.hits))
        with Site() as s:
            res = self.crawl(s.base, max_pages=2)
        self.assertEqual(res["sites"][0]["paginas"], 2)

    def test_blocks_for_llm_when_only_plain_text(self):
        with Site() as s:
            res = self.crawl(s.base, max_pages=3, max_depth=1)   # solo portada, ubícanos y una tienda
        # con 'max_pages' bajo hay pocos datos estructurados y se entregan textos para el modelo
        self.assertTrue(res["bloques"], res["sites"])
        self.assertIn("pagina_url", res["bloques"][0])

    def test_unreachable_site_does_not_stop_the_rest(self):
        with Site() as s:
            r = self.run_node("site_locations_crawl", {"sites": ["http://127.0.0.1:1/", s.base + "/"], "delay": 0, "workers": 2, "timeout": 3})
        self.assertEqual(r["status"], "ok", r["error"])
        res = r["result"]
        self.assertEqual(len(res["sites"]), 2)
        self.assertEqual(res["sin_resultados"], ["127.0.0.1:1"])
        self.assertTrue(res["total"] >= 6)

    def test_no_sites_is_clear_error(self):
        self.assertIn("No hay sitios", self.run_node("site_locations_crawl", {"sites": []})["error"])


class Llm(Base):
    ROWS = [
        {"sitio": "A", "sitio_url": "http://a", "pagina_url": "http://a/t", "metodo": "texto", "nombre": "Tienda Miraflores",
         "direccion": "Av. Larco 1234, Miraflores, Lima", "telefono": "", "lat": None, "lng": None,
         "contexto": "Tienda Miraflores | Av. Larco 1234, Miraflores, Lima"},
        {"sitio": "A", "sitio_url": "http://a", "pagina_url": "http://a/t", "metodo": "texto", "nombre": "",
         "direccion": "Av. Publicidad 55", "telefono": "", "lat": None, "lng": None, "contexto": "ANUNCIO Av. Publicidad 55 ofertas"},
        {"sitio": "A", "sitio_url": "http://a", "pagina_url": "http://a/t", "metodo": "texto", "nombre": "",
         "direccion": "Jr. Real 10", "telefono": "", "lat": -12.0, "lng": -77.0, "contexto": "Sede INVENTADA | Jr. Real 10, Lima"},
    ]

    def ia(self, srv, rows=None, bloques=None, secrets=None, **kw):
        cfg = {"base_url": srv.base, "rows": self.ROWS if rows is None else rows, "bloques": bloques or [], "batch_size": 2}
        cfg.update(kw)
        return self.run_node("llm_structure_addresses", cfg, secrets)

    def test_structures_discards_and_verifies(self):
        with FakeLLM() as srv:
            r = self.ia(srv)
            self.assertEqual(srv.model_seen, "qwen-fake-7b")             # tomó el primer modelo de /v1/models
        self.assertEqual(r["status"], "ok", r["error"])
        res = r["result"]
        by = {x["direccion"]: x for x in res["rows"]}
        self.assertEqual(res["total"], 2)                                  # el ANUNCIO se descartó
        self.assertEqual(res["stats"]["descartados"], 1)
        larco = by["Av. Larco 1234"]
        self.assertEqual((larco["distrito"], larco["ciudad"], larco["fuente"], larco["verificada"]), ("Miraflores", "Lima", "ia", "sí"))
        inv = by["Av. Los Delfines 999, Marte"]
        self.assertEqual(inv["verificada"], "no")                          # el modelo inventó una dirección que no está en el texto
        self.assertEqual(res["stats"]["sin_verificar"], 1)

    def test_blocks_become_rows(self):
        bl = [{"sitio": "B", "sitio_url": "http://b", "pagina_url": "http://b/c", "texto": "Contáctanos\nSede central: Av. Javier Prado Este 4200, Santiago de Surco\nHorario 9 a 6"}]
        with FakeLLM() as srv:
            res = self.ia(srv, rows=[], bloques=bl)["result"]
        self.assertEqual(len(res["rows"]), 1)
        x = res["rows"][0]
        self.assertEqual((x["sitio"], x["direccion"], x["distrito"], x["metodo"], x["verificada"]),
                         ("B", "Av. Javier Prado Este 4200", "Santiago de Surco", "texto_pagina", "sí"))

    def test_key_is_sent_and_wrong_key_falls_back(self):
        with FakeLLM(key="secreta") as srv:
            ok = self.ia(srv, secrets={"quipullm_key": "secreta"})
            self.assertEqual(ok["status"], "ok", ok["error"])
            self.assertEqual(set(srv.auth), {"Bearer secreta"})
            bad = self.ia(srv, secrets={"quipullm_key": "otra"})
            self.assertEqual(bad["status"], "ok")
            self.assertEqual(bad["result"]["total"], 3)                     # conserva los 3 del rastreo
            self.assertTrue(all(x["fuente"] == "rastreo" for x in bad["result"]["rows"]))
            strict = self.ia(srv, secrets={"quipullm_key": "otra"}, fallback=False)
            self.assertEqual(strict["status"], "error")
            self.assertIn("rechazó la clave", strict["error"])

    def test_server_down_falls_back(self):
        r = self.run_node("llm_structure_addresses", {"base_url": "http://127.0.0.1:1/v1", "model": "x", "rows": self.ROWS, "timeout": 10})
        self.assertEqual(r["status"], "ok", r["error"])
        self.assertEqual(r["result"]["total"], 3)
        self.assertEqual(r["result"]["stats"]["fallos"], 1)

    def test_tolerates_think_fences_and_prose_first(self):
        for mode in ("think_fence", "prose_first"):
            with FakeLLM(mode=mode) as srv:
                res = self.ia(srv)["result"]
            self.assertEqual(res["total"], 2, mode)
            self.assertEqual(res["stats"]["fallos"], 0, mode)
            self.assertTrue(all(x["fuente"] == "ia" for x in res["rows"]), mode)

    def test_garbage_answer_falls_back_without_failing(self):
        with FakeLLM(mode="garbage") as srv:
            r = self.ia(srv)
        self.assertEqual(r["status"], "ok", r["error"])
        self.assertEqual(r["result"]["total"], 3)
        self.assertTrue(r["result"]["stats"]["fallos"] >= 1)

    def test_only_local_servers_by_default(self):
        r = self.run_node("llm_structure_addresses", {"base_url": "http://8.8.8.8:1234/v1", "rows": self.ROWS})
        self.assertEqual(r["status"], "error")
        self.assertIn("no es un equipo de la red local", r["error"])
        r = self.run_node("llm_structure_addresses", {"base_url": "ftp://x", "rows": self.ROWS})
        self.assertIn("http://", r["error"])

    def test_private_hosts_recognised(self):
        sys.path.insert(0, str(PLUGINS / "llm_structure_addresses"))
        import importlib
        mod = importlib.import_module("task")
        for h in ("localhost", "127.0.0.1", "192.168.1.50", "10.0.0.7", "172.16.5.5", "servidor-llm", "pc01.local"):
            self.assertTrue(mod._is_local(h), h)
        self.assertFalse(mod._is_local("8.8.8.8"))
        self.assertFalse(mod._is_local("93.184.216.34"))
        sys.path.remove(str(PLUGINS / "llm_structure_addresses"))
        sys.modules.pop("task", None)


class Pipeline(Base):
    def test_example_is_valid_and_runs_end_to_end(self):
        ex = json.loads((PLUGINS.parent / "examples" / "sucursales_desde_enlaces.json").read_text(encoding="utf-8"))
        errors, _ = self.engine.validate(ex)
        self.assertEqual(errors, [])
        enlaces = self.tmp / "enlaces.csv"
        out = self.tmp / "salida"
        with Site() as s, FakeLLM() as llm:
            enlaces.write_text("nombre;url\nFerretería Andina;%s/\n" % s.base, encoding="utf-8")
            ex["variables"].update(archivo_enlaces=str(enlaces), ia_url=llm.base, carpeta=str(out))
            for n in ex["nodes"]:
                if n["type"] == "site_locations_crawl":
                    n["config"]["delay"] = 0
            res = self.engine.run(ex)
        self.assertEqual(res.status, "ok", {k: v["error"] for k, v in res.nodes.items() if v["error"]})
        csvs = sorted(out.glob("sucursales_20*.csv"))
        self.assertEqual(len(csvs), 1)
        with open(csvs[0], encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f, delimiter=";"))
        self.assertEqual(rows[0][:5], ["Sitio", "Local", "Dirección", "Distrito", "Ciudad"])
        self.assertEqual(len(rows) - 1, 6)
        self.assertTrue(any("Av. Larco 1234" in r[2] for r in rows[1:]))
        self.assertEqual(len(list(out.glob("sucursales_20*.xlsx"))), 1)
        self.assertEqual(len(list(out.glob("sucursales_resumen_*.csv"))), 1)


if __name__ == "__main__":
    unittest.main()
