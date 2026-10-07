"""Crear plugins pegando lo que devuelve una IA («=== archivo ===» o JSON)."""

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chaskiflow import plugin_admin as padm  # noqa: E402
from tests.apiclient import TestServer, wait_run  # noqa: E402

PASS = "clave-segura-1"
MANI = '{"id": "ia_saludo", "name": "Saludo IA", "version": "1.0.0", "kind": "python", "entry": "task.py", ' \
       '"fields": [{"key": "nombre", "label": "Nombre", "type": "string", "default": "mundo"}], ' \
       '"outputs": [{"key": "texto", "type": "string"}]}'
CODE = "def run(config, ctx):\n    return {'texto': 'Hola ' + str(config['nombre'])}\n"
BUNDLE = "```\n=== plugin.json ===\n%s\n=== task.py ===\n%s=== README.md ===\nSaluda.\n```\n" % (MANI, CODE)


class ParseBundle(unittest.TestCase):
    def test_blocks_and_fences(self):
        f = padm.parse_bundle(BUNDLE)
        self.assertEqual(sorted(f), ["README.md", "plugin.json", "task.py"])
        self.assertIn("def run", f["task.py"])
        self.assertNotIn("```", f["task.py"])

    def test_json_forms(self):
        import json
        self.assertEqual(sorted(padm.parse_bundle(json.dumps({"files": {"plugin.json": MANI, "task.py": CODE}}))),
                         ["plugin.json", "task.py"])
        self.assertEqual(list(padm.parse_bundle(MANI)), ["plugin.json"])

    def test_garbage(self):
        for bad in ("", "hola mundo"):
            with self.assertRaises(padm.PluginAdminError):
                padm.parse_bundle(bad)


class ImportApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = TestServer()
        cls.admin = cls.srv.client()
        assert cls.admin.post("/api/setup", {"username": "admin", "password": PASS})[0] == 200
        assert cls.admin.post("/api/users", {"username": "ana", "password": PASS, "role": "editor"})[0] == 201
        cls.ana = cls.srv.client()
        assert cls.ana.post("/api/login", {"username": "ana", "password": PASS})[0] == 200

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()

    def setUp(self):
        d = self.srv.extra_plugins / "ia_saludo"
        if d.exists():
            shutil.rmtree(str(d))
        self.admin.post("/api/plugins/reload")

    def test_prompt(self):
        st, d = self.admin.get("/api/plugins/prompt")
        self.assertEqual(st, 200)
        self.assertIn("plugin.json", d["prompt"])
        self.assertIn("=== task.py ===", d["prompt"])
        self.assertEqual(self.ana.get("/api/plugins/prompt")[0], 403)

    def test_import_pending_then_approve_and_run(self):
        st, d = self.admin.post("/api/plugins/import", {"text": BUNDLE})
        self.assertEqual(st, 200, d)
        p = [x for x in d["plugins"] if x["id"] == "ia_saludo"][0]
        self.assertNotEqual(p["status"], "enabled")          # el admin debe aprobar
        self.assertEqual(self.admin.post("/api/plugins/ia_saludo/enable")[0], 200)
        wf = {"name": "t", "nodes": [{"id": "n1", "label": "S", "type": "ia_saludo", "config": {"nombre": "Ana"}}], "edges": []}
        st, w = self.admin.post("/api/workflows", {"name": "t", "definition": wf})
        self.assertEqual(st, 201, w)
        st, r = self.admin.post("/api/workflows/%d/run" % w["workflow"]["id"], {})
        self.assertEqual(st, 202, r)
        run, _ = wait_run(self.admin, r["run_id"])
        self.assertEqual(run["status"], "ok", run)
        node = self.admin.get("/api/runs/%s/nodes/n1" % r["run_id"])[1]["node"]
        self.assertEqual(node["result"]["texto"], "Hola Ana")

    def test_duplicate_and_overwrite(self):
        self.assertEqual(self.admin.post("/api/plugins/import", {"text": BUNDLE})[0], 200)
        st, d = self.admin.post("/api/plugins/import", {"text": BUNDLE})
        self.assertEqual(st, 409)
        st, d = self.admin.post("/api/plugins/import", {"text": BUNDLE, "overwrite": True})
        self.assertEqual(st, 200, d)

    def test_rejects_bad_code_imports_and_names(self):
        def attempt(files):
            return self.admin.post("/api/plugins/import", {"files": files})
        self.assertEqual(attempt({"plugin.json": MANI, "task.py": "def run(config, ctx)\n    pass\n"})[0], 400)
        st, d = attempt({"plugin.json": MANI, "task.py": "import requests\ndef run(config, ctx):\n    return {}\n"})
        self.assertEqual(st, 400)
        self.assertIn("librería estándar", d.get("error", "") + str(d))
        self.assertEqual(attempt({"plugin.json": MANI})[0], 400)                       # falta task.py
        self.assertEqual(attempt({"plugin.json": MANI, "task.py": CODE, "x.exe": "a"})[0], 400)
        self.assertEqual(attempt({"plugin.json": MANI, "task.py": CODE, "../x.py": "a"})[0], 400)
        self.assertEqual(attempt({"plugin.json": MANI.replace("ia_saludo", "Mal Id"), "task.py": CODE})[0], 400)
        self.assertEqual(attempt({"task.py": CODE})[0], 400)
        self.assertFalse((self.srv.extra_plugins / "ia_saludo").exists())

    def test_permissions_and_switch(self):
        self.assertEqual(self.ana.post("/api/plugins/import", {"text": BUNDLE})[0], 403)
        self.assertEqual(self.srv.client().post("/api/plugins/import", {"text": BUNDLE})[0], 401)


if __name__ == "__main__":
    unittest.main()
