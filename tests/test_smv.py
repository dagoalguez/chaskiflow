"""SMV: descarga de «Estados Financieros y Dictamen» (portal simulado) y búsqueda de palabras en PDF
(texto del PDF y páginas escaneadas leídas por un servidor de visión simulado)."""

import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chaskiflow.engine import Engine  # noqa: E402
from chaskiflow.plugin_loader import PluginRegistry  # noqa: E402
from tests.fakellm import FakeLLM  # noqa: E402
from tests.helpers import PLUGINS  # noqa: E402
from tests.pdfmaker import make_pdf  # noqa: E402
from tests.smvsite import PortalSite  # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.engine = Engine(PluginRegistry([PLUGINS]), workdir_root=cls.tmp / "runs")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def out(self):
        return str(Path(tempfile.mkdtemp(dir=self.tmp)))

    def run_node(self, typ, config, secrets=None):
        eng = Engine(PluginRegistry([PLUGINS]), workdir_root=self.tmp / "runs", secrets=(lambda n: (secrets or {}).get(n)))
        return eng.run({"name": "t", "nodes": [{"id": "A", "label": "A", "type": typ, "config": config}], "edges": []}).nodes["A"]


class Download(Base):
    def dl(self, site, **kw):
        cfg = {"carpeta": self.out(), "portal_url": site.url, "pausa": 0, "reintentos": 1, "timeout": 10}
        cfg.update(kw)
        r = self.run_node("smv_financial_download", cfg)
        self.assertEqual(r["status"], "ok", r["error"])
        return cfg["carpeta"], r["result"]

    def test_downloads_only_the_wanted_document_by_company_and_year(self):
        with PortalSite() as s:
            folder, res = self.dl(s, empresas="ALFA", anio_desde=2021, anio_hasta=2022)
            posts = s.posts
        ok = [r for r in res["rows"] if r["estado"] == "descargado"]
        self.assertEqual(sorted((r["anio"], r["expediente"]) for r in ok), [(2021, "20211019"), (2022, "20221018"), (2022, "20221019")])
        self.assertTrue(all(r["documento"] == "Estados Financieros y Dictamen" for r in ok))   # sin XBRL, cartas ni «Estados Financieros»
        self.assertEqual(posts, 3)                                                              # 2 búsquedas (una por año) + la página 2 de los resultados de 2022
        f = Path(res["files"][0])
        self.assertEqual(f.parent, Path(folder) / "Descargas" / "ALFA ENERGIA S.A.A" / "2021")   # Windows no admite punto final en carpetas
        self.assertTrue(f.read_bytes().startswith(b"%PDF-"))
        self.assertEqual(res["total"], 3)
        self.assertEqual(res["stats"]["descargados"], 3)

    def test_second_run_does_not_download_again_and_replace_forces_it(self):
        with PortalSite() as s:
            cfg = dict(empresas="BETA", anio_desde=2021, anio_hasta=2022)
            folder, res = self.dl(s, **cfg)
            n1 = len([h for h in s.hits if "documento.aspx" in h])
            _, res2 = self.dl(s, carpeta=folder, **cfg)
            n2 = len([h for h in s.hits if "documento.aspx" in h])
            _, res3 = self.dl(s, carpeta=folder, reemplazar=True, **cfg)
            n3 = len([h for h in s.hits if "documento.aspx" in h])
        self.assertEqual((n1, n2, n3), (2, 2, 4))
        self.assertEqual({r["estado"] for r in res2["rows"]}, {"ya existía"})
        self.assertEqual(res2["total"], 2)                                    # los existentes también se entregan al escaneo
        self.assertEqual(res3["stats"]["descargados"], 2)

    def test_company_matching_by_name_number_and_missing(self):
        with PortalSite() as s:
            _, res = self.dl(s, empresas="falabella\n106\nNO EXISTE\nSIN DATOS", anio_desde=2022, anio_hasta=2022)
        names = {r["empresa"] for r in res["rows"]}
        self.assertIn("ACTIVO INMOBILIARIO PERUANO S.A.A. (ANTES FALABELLA PERU S.A.A.)", names)   # «falabella» coincide con 2 empresas
        self.assertIn("FALABELLA TIENDAS S.A.", names)
        self.assertEqual(res["stats"]["empresas"], 3)                                               # 103, 104 y 106
        self.assertEqual(res["stats"]["no_encontradas"], ["NO EXISTE"])
        self.assertEqual([x["empresa"] for x in res["sin_documento"]], ["SIN DATOS S.A."])

    def test_no_matching_company_is_a_clear_error(self):
        with PortalSite() as s:
            r = self.run_node("smv_financial_download", {"carpeta": self.out(), "portal_url": s.url, "empresas": "ZZZ"})
        self.assertEqual(r["status"], "error")
        self.assertIn("Ninguna de las empresas", r["error"])

    def test_results_in_several_pages_are_all_read(self):
        with PortalSite() as s:
            _, res = self.dl(s, empresas="PAGINADA", anio_desde=2022, anio_hasta=2022)
        self.assertEqual(sorted(r["expediente"] for r in res["rows"] if r["estado"] == "descargado"), ["202210551", "202210554"])   # uno por página

    def test_consolidated_type(self):
        with PortalSite() as s:
            _, res = self.dl(s, empresas="ALFA", anio_desde=2022, anio_hasta=2022, tipo="Consolidada")
        self.assertEqual(res["total"], 1)

    def test_retries_and_one_failing_file_does_not_stop_the_rest(self):
        with PortalSite() as s:
            s.fail_download_once.add(s.guid("101", 2021))                  # falla una vez y luego responde
            s.bad_download.add(s.guid("102", 2021))                        # el portal devuelve HTML en vez de PDF
            folder, res = self.dl(s, empresas="ALFA\nBETA", anio_desde=2021, anio_hasta=2021, reintentos=2)
            # cada empresa solo existe en la tabla si se pidió bien: los GUID se crean al consultar
        by = {r["empresa"]: r for r in res["rows"]}
        self.assertEqual(by["ALFA ENERGIA S.A.A."]["estado"], "descargado")        # reintentó y funcionó
        self.assertEqual(by["BETA MINERA S.A."]["estado"], "error")
        self.assertIn("no es un PDF", by["BETA MINERA S.A."]["error"])
        self.assertEqual(res["stats"]["errores"], 1)
        self.assertFalse(list(Path(folder).rglob("*.part")))                        # sin archivos a medias

    def test_total_time_limit_ends_cleanly_and_resumes(self):
        with PortalSite() as s:
            folder, res = self.dl(s, empresas="ALFA", anio_desde=2021, anio_hasta=2025, pausa=1, max_total_seconds=1)
            self.assertTrue(res["stats"]["pendientes"] > 0, res["stats"])
            self.assertTrue(res["total"] >= 1)
            _, res2 = self.dl(s, carpeta=folder, empresas="ALFA", anio_desde=2021, anio_hasta=2025)
        self.assertEqual(res2["stats"]["pendientes"], 0)
        self.assertEqual(res2["total"], 6)                                          # 2021, 2022 (×2), 2023, 2024, 2025

    def test_unreachable_portal_has_a_clear_message(self):
        r = self.run_node("smv_financial_download", {"carpeta": self.out(), "portal_url": "http://127.0.0.1:1/x", "reintentos": 0, "timeout": 5})
        self.assertEqual(r["status"], "error")
        self.assertIn("No se pudo abrir el portal", r["error"])


def write_pdfs(folder):
    """Carpeta Descargas/Empresa/Año/*.pdf con los distintos casos."""
    cases = {
        ("ALFA", "2021"): [("texto", ["Estados financieros", "Sin hechos relevantes."])],
        ("ALFA", "2022"): [("texto", ["Nota 1", "Se aprobó la FUSIÓN por absorción con Beta.", "Nota 2"])],
        ("ALFA", "2023"): [("texto", ["Nota 5", "Proceso de reorgani-", "zación   societaria en curso."])],
        ("ALFA", "2024"): [("gris", 200)],                                    # escaneado: la IA ve «fusión»
        ("ALFA", "2025"): [("texto", ["Portada del informe anual", "Auditores independientes y asociados"]), ("gris", 90)],             # mixto, sin hallazgo
        ("BETA", "2021"): [("texto", ["Notas", "Las escisiones y fusiones fueron aprobadas."])],
        ("BETA", "2022"): [("jpeg",)],                                        # escaneado JPEG: reorganización societaria
        ("BETA", "2023"): [("jbig2",)],                                       # no legible
        ("BETA", "2024"): [("texto", ["Hechos posteriores", "Ninguno. La confusión no cuenta."])],      # «confusión» NO es «fusión»
    }
    for (emp, year), pages in cases.items():
        d = Path(folder) / "Descargas" / emp / year
        d.mkdir(parents=True, exist_ok=True)
        (d / ("%s_%s.pdf" % (year, emp))).write_bytes(make_pdf(pages))
    (Path(folder) / "Descargas" / "BETA" / "2025").mkdir(parents=True)
    (Path(folder) / "Descargas" / "BETA" / "2025" / "2025_BETA.pdf").write_bytes(b"esto no es un pdf")


class Scan(Base):
    def scan(self, folder, llm=None, **kw):
        cfg = {"folder": str(Path(folder) / "Descargas"), "output_dir": folder}
        if llm is not None:
            cfg.update(base_url=llm.base, model="lfm2.5-vl-1.6b")
        cfg.update(kw)
        r = self.run_node("pdf_keyword_scan", cfg)
        self.assertEqual(r["status"], "ok", r["error"])
        return r["result"]

    def setUp(self):
        self.folder = self.out()
        write_pdfs(self.folder)

    def by(self, res):
        return {(r["empresa"], r["anio"]): r for r in res["rows"]}

    def test_text_search_ignores_case_accents_hyphens_plurals_and_false_friends(self):
        res = self.scan(self.folder)                                            # sin IA
        b = self.by(res)
        self.assertEqual(b[("ALFA", "2021")]["identificado"], "no")
        self.assertEqual(b[("ALFA", "2022")]["identificado"], "sí")             # «FUSIÓN» en mayúsculas
        self.assertEqual(b[("ALFA", "2023")]["identificado"], "sí")             # «reorgani-\nzación   societaria»
        self.assertIn("reorganización societaria", b[("ALFA", "2023")]["palabras"])
        self.assertEqual(b[("BETA", "2021")]["identificado"], "sí")             # plurales «escisiones» y «fusiones»
        self.assertIn("escisión", b[("BETA", "2021")]["palabras"])
        self.assertIn("fusión", b[("BETA", "2021")]["palabras"])
        self.assertEqual(b[("BETA", "2024")]["identificado"], "no")             # «confusión» no coincide
        self.assertEqual(b[("ALFA", "2022")]["paginas_hallazgo"], "1")
        self.assertIn("FUSIÓN por absorción", b[("ALFA", "2022")]["contexto"])
        self.assertEqual(b[("ALFA", "2022")]["deteccion"], "texto")
        self.assertEqual(b[("ALFA", "2022")]["metodo"], "texto")

    def test_url_without_v1_is_completed(self):
        with FakeLLM() as llm:
            llm.base = llm.base[:-len("/v1")]                                    # http://host:puerto (como lo escribió el usuario)
            res = self.scan(self.folder, llm)
            calls = llm.vision_calls
        self.assertEqual(calls, 2)
        self.assertEqual(self.by(res)[("ALFA", "2024")]["deteccion"], "IA")

    def test_scanned_pages_are_read_by_the_vision_model_only_when_there_is_no_text(self):
        with FakeLLM() as llm:
            res = self.scan(self.folder, llm)
            calls = llm.vision_calls
            mimes = sorted(set(llm.images))
        b = self.by(res)
        self.assertEqual(b[("ALFA", "2024")]["identificado"], "sí")
        self.assertEqual(b[("ALFA", "2024")]["deteccion"], "IA")
        self.assertEqual(b[("ALFA", "2024")]["metodo"], "ia")
        self.assertEqual(b[("BETA", "2022")]["identificado"], "sí")             # JPEG
        self.assertIn("reorganización societaria", b[("BETA", "2022")]["palabras"])
        self.assertEqual(b[("ALFA", "2025")]["identificado"], "no")             # PDF con texto (y una página escaneada): se busca solo en el texto
        self.assertEqual(b[("ALFA", "2025")]["metodo"], "texto")                # tiene texto en alguna página: el PDF NO usa IA
        self.assertEqual(b[("ALFA", "2025")]["paginas_leidas_ia"], 0)
        self.assertEqual(calls, 2)                                              # solo PDF sin ningún texto (ALFA 2024, BETA 2022)
        self.assertEqual(mimes, ["image/jpeg", "image/png"])

    def test_unreadable_pdfs_go_to_manual_review_and_broken_ones_are_reported(self):
        with FakeLLM() as llm:
            res = self.scan(self.folder, llm)
        b = self.by(res)
        self.assertEqual(b[("BETA", "2023")]["identificado"], "no")
        self.assertIn("JBIG2", b[("BETA", "2023")]["nota"])
        self.assertTrue((Path(self.folder) / "REVISAR_MANUAL" / "BETA" / "2023" / "2023_BETA.pdf").is_file())
        self.assertEqual(b[("BETA", "2025")]["metodo"], "error")
        self.assertIn("PDF", b[("BETA", "2025")]["nota"])
        self.assertEqual(res["stats"]["errores"], 1)
        self.assertEqual(res["stats"]["no_leidos"], 1)

    def test_identified_are_copied_into_company_and_year_folders(self):
        with FakeLLM() as llm:
            res = self.scan(self.folder, llm)
        ident = Path(self.folder) / "IDENTIFICADOS"
        got = sorted(str(p.relative_to(ident)).replace("\\", "/") for p in ident.rglob("*.pdf"))
        self.assertEqual(got, ["ALFA/2022/2022_ALFA.pdf", "ALFA/2023/2023_ALFA.pdf", "ALFA/2024/2024_ALFA.pdf",
                               "BETA/2021/2021_BETA.pdf", "BETA/2022/2022_BETA.pdf"])
        self.assertTrue((Path(self.folder) / "Descargas" / "ALFA" / "2022" / "2022_ALFA.pdf").is_file())   # copia: el original se queda
        self.assertEqual(len(res["identificados"]), 5)
        self.assertEqual(res["stats"]["con_hallazgo"], 5)

    def test_move_instead_of_copy(self):
        self.scan(self.folder, mover=True)
        self.assertFalse((Path(self.folder) / "Descargas" / "ALFA" / "2022" / "2022_ALFA.pdf").exists())
        self.assertTrue((Path(self.folder) / "IDENTIFICADOS" / "ALFA" / "2022" / "2022_ALFA.pdf").is_file())

    def test_without_ai_scanned_pdfs_are_flagged_not_silently_skipped(self):
        res = self.scan(self.folder)
        b = self.by(res)
        self.assertEqual(b[("ALFA", "2024")]["identificado"], "no")
        self.assertEqual(b[("ALFA", "2024")]["paginas_sin_leer"], 1)
        self.assertTrue((Path(self.folder) / "REVISAR_MANUAL" / "ALFA" / "2024").is_dir())
        self.assertTrue(res["stats"]["no_leidos"] >= 3)

    def test_second_run_reuses_results_and_does_not_ask_the_model_again(self):
        with FakeLLM() as llm:
            self.scan(self.folder, llm)
            n = llm.vision_calls
            res = self.scan(self.folder, llm)
            self.assertEqual(llm.vision_calls, n)
            res3 = self.scan(self.folder, llm, reprocesar=True)
            self.assertTrue(llm.vision_calls > n)
        self.assertEqual(res["stats"]["reutilizados"], 9)                       # todos menos el PDF dañado
        self.assertEqual(res["stats"]["con_hallazgo"], 5)
        self.assertEqual(res3["stats"]["reutilizados"], 0)

    def test_changing_keywords_invalidates_the_cache(self):
        self.scan(self.folder)
        res = self.scan(self.folder, keywords="absorción")
        self.assertEqual(res["stats"]["reutilizados"], 0)
        self.assertEqual(self.by(res)[("ALFA", "2022")]["identificado"], "sí")

    def test_total_time_limit_leaves_pending_without_failing(self):
        res = self.scan(self.folder, max_total_seconds=0.000001)
        self.assertEqual(res["stats"]["pendientes"], 10)
        self.assertEqual({r["metodo"] for r in res["rows"]}, {"pendiente"})
        res2 = self.scan(self.folder)
        self.assertEqual(res2["stats"]["pendientes"], 0)

    def test_model_errors_do_not_break_the_scan(self):
        with FakeLLM(mode="garbage") as llm:
            res = self.scan(self.folder, llm)
        b = self.by(res)
        self.assertEqual(b[("ALFA", "2024")]["identificado"], "no")
        self.assertIn("la IA no respondió bien", b[("ALFA", "2024")]["nota"])
        self.assertEqual(b[("ALFA", "2022")]["identificado"], "sí")             # el texto sigue funcionando

    def test_clean_text_is_saved_and_split_in_columns(self):
        res = self.scan(self.folder, texto_columnas=3, texto_max_celda=1000)
        r = self.by(res)[("ALFA", "2023")]
        self.assertTrue(r["texto_1"].startswith("[p. 1]"))
        self.assertIn("reorganización societaria", r["texto_1"])                # sin guion ni salto de línea
        self.assertNotIn("\n", r["texto_1"])
        self.assertEqual(r["texto_completo"], "sí")
        full = Path(r["texto_archivo"]).read_text(encoding="utf-8")
        self.assertIn("reorganización societaria", full)
        self.assertNotIn("texto_1", self.by(res)[("ALFA", "2024")])             # escaneado sin IA: no hay texto
        res2 = self.scan(self.folder)                                            # reutiliza el caché y conserva las columnas
        self.assertIn("reorganización societaria", self.by(res2)[("ALFA", "2023")]["texto_1"])

    def test_text_columns_can_be_turned_off(self):
        res = self.scan(self.folder, guardar_texto=False)
        self.assertNotIn("texto_archivo", self.by(res)[("ALFA", "2023")])
        self.assertFalse((Path(self.folder) / "TEXTOS").exists())

    def test_chunking_cuts_at_spaces_and_reports_truncation(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("kw_task", PLUGINS / "pdf_keyword_scan" / "task.py")
        sys.path.insert(0, str(PLUGINS / "pdf_keyword_scan"))
        try:
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        finally:
            sys.path.pop(0)
        parts, ok = m.trozos("palabra " * 300, 2, 1000)
        self.assertEqual(len(parts), 2)
        self.assertTrue(all(len(p) <= 1000 and p.endswith("palabra") for p in parts))
        self.assertFalse(ok)
        self.assertTrue(m.trozos("hola mundo", 5, 1000)[1])

    def test_dead_ai_server_does_not_abort_text_pdfs(self):
        with FakeLLM(mode="http500") as llm:
            res = self.scan(self.folder, llm)
            res2 = self.scan(self.folder)
        b = self.by(res)
        self.assertEqual(b[("ALFA", "2022")]["identificado"], "sí")             # PDF con texto: procesado igual
        self.assertEqual(b[("BETA", "2021")]["identificado"], "sí")
        self.assertGreaterEqual(res["stats"]["no_leidos"], 1)

    def test_only_local_ai_servers_by_default(self):
        r = self.run_node("pdf_keyword_scan", {"folder": self.folder, "output_dir": self.folder, "base_url": "http://93.184.216.34:1234/v1"})
        self.assertEqual(r["status"], "error")
        self.assertIn("red local", r["error"])

    def test_no_pdfs_is_a_clear_error(self):
        r = self.run_node("pdf_keyword_scan", {"folder": self.out(), "output_dir": self.out()})
        self.assertIn("No hay PDF", r["error"])

    def test_example_is_valid_and_runs_end_to_end(self):
        ex = json.loads((PLUGINS.parent / "examples" / "smv_fusiones_escisiones.json").read_text(encoding="utf-8"))
        errors, _ = self.engine.validate(ex)
        self.assertEqual(errors, [])
        out = self.out()
        with PortalSite() as s, FakeLLM() as llm:
            ex["variables"].update(carpeta=out, empresas="ALFA\nBETA", anio_desde=2021, anio_hasta=2024, ia_url=llm.base)
            for n in ex["nodes"]:
                if n["type"] == "smv_financial_download":
                    n["config"].update(portal_url=s.url, pausa=0, reintentos=1, timeout=10)
            res = self.engine.run(ex)
        self.assertEqual(res.status, "ok", {k: v["error"] for k, v in res.nodes.items() if v["error"]})
        csvs = sorted(Path(out).glob("fusiones_20*.csv"))
        self.assertEqual(len(csvs), 1)
        with open(csvs[0], encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f, delimiter=";"))
        self.assertEqual(rows[0][:4], ["Empresa", "Año", "Archivo", "Identificado"])
        data = {(r[0], r[1]): r for r in rows[1:]}
        self.assertEqual(len(rows) - 1, 9)                                      # ALFA 2021, 2022 (×2 expedientes), 2023, 2024 y BETA 2021–2024
        self.assertEqual(data[("ALFA ENERGIA S.A.A.", "2024")][3], "sí")        # escaneado, leído por la IA
        self.assertEqual(data[("BETA MINERA S.A.", "2022")][3], "sí")
        self.assertTrue((Path(out) / "IDENTIFICADOS" / "ALFA ENERGIA S.A.A" / "2022").is_dir())
        self.assertEqual(len(list(Path(out).glob("fusiones_20*.xlsx"))), 1)
        self.assertEqual(len(list(Path(out).glob("descargas_20*.csv"))), 1)


if __name__ == "__main__":
    unittest.main()
