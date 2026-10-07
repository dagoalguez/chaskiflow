"""Importador G1G -> ChaskiFlow: traducción de nodos, etiquetas, exportación doble y API."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chaskiflow import g1g_import as g  # noqa: E402
from chaskiflow.engine import Engine  # noqa: E402
from chaskiflow.plugin_loader import PluginRegistry  # noqa: E402
from tests.apiclient import TestServer  # noqa: E402

ENGINE = Engine(PluginRegistry([Path(__file__).resolve().parent.parent / "plugins"]))

FIX = Path(__file__).resolve().parent / "fixtures" / "g1g_noticias.json"


def load():
    return json.loads(FIX.read_text(encoding="utf-8"))


class Convert(unittest.TestCase):
    def setUp(self):
        self.d, self.rep = g.convert(load())
        self.by = {n["label"]: n for n in self.d["nodes"]}

    def test_detect(self):
        self.assertTrue(g.is_g1g(load()))
        self.assertFalse(g.is_g1g({"nodes": [{"id": "a", "type": "x"}], "edges": []}))
        self.assertFalse(g.is_g1g([]))

    def test_label_and_refs(self):
        self.assertIn("El_Comercio", self.by)
        self.assertIn("{{El_Comercio.result.count}}", self.by["Correo"]["config"]["body"])

    def test_news_fields(self):
        c = self.by["RPP"]["config"]
        for k in ("headless", "stealth", "session_id", "keep_session", "seen_key", "fetch_mode", "on_error"):
            self.assertNotIn(k, c)
        self.assertEqual(self.by["RPP"]["on_error"], "continue")
        self.assertEqual(self.by["El_Comercio"]["on_error"], "stop")
        self.assertTrue(any("fetch_mode" in r["message"] for r in self.rep if r["level"] == "warn"))
        self.assertTrue(any("link_selector" in r["message"] for r in self.rep if r["level"] == "warn"))

    def test_export_both(self):
        self.assertEqual(self.by["Exportar"]["type"], "export_csv")
        self.assertEqual(self.by["Exportar_xlsx"]["type"], "export_xlsx")
        self.assertEqual(self.by["Exportar_xlsx"]["config"]["sheet_name"], "Noticias")
        self.assertNotIn("wat", self.by["Exportar"]["config"])
        self.assertEqual(self.by["Correo"]["config"]["attachments"],
                         ["{{Exportar.result.file_paths}}", "{{Exportar_xlsx.result.file_paths}}"])

    def test_outlook(self):
        c = self.by["Correo"]["config"]
        self.assertIs(c["body_is_html"], True)
        self.assertEqual(c["mode"], "display")
        self.assertNotIn("send_mode", c)

    def test_edges_and_warnings(self):
        pairs = {(e["source"], e["target"]) for e in self.d["edges"]}
        self.assertIn(("node_3", "node_4"), pairs)
        self.assertIn(("node_3", "node_4_xlsx"), pairs)
        self.assertIn(("node_4_xlsx", "node_5"), pairs)
        self.assertFalse(any(t == "node_99" for _, t in pairs))
        msgs = " ".join(r["message"] for r in self.rep)
        self.assertIn("inexistente", msgs)
        self.assertIn("foreach", msgs)
        self.assertIn("desconocido", msgs)

    def test_valid_dag(self):
        d = json.loads(json.dumps(self.d))
        d["nodes"] = [n for n in d["nodes"] if n["label"] != "Raro"]
        errors, _ = ENGINE.validate(d)
        self.assertEqual(errors, [])


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = TestServer(scheduler_enabled=False)
        cls.c = cls.srv.client()
        assert cls.c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})[0] == 200

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()

    def test_import_endpoint(self):
        s, d = self.c.post("/api/workflows/import", {"name": "Desde G1G", "definition": load()})
        self.assertEqual(s, 201, d)
        self.assertIn("import_report", d)
        self.assertEqual(d["workflow"]["definition"]["nodes"][0]["label"], "RPP")

    def test_native_import_has_no_report(self):
        s, d = self.c.post("/api/workflows/import", {"name": "Nativo", "definition": {
            "nodes": [{"id": "a", "label": "A", "type": "hello_world", "config": {}}], "edges": []}})
        self.assertEqual(s, 201, d)
        self.assertNotIn("import_report", d)


if __name__ == "__main__":
    unittest.main()
