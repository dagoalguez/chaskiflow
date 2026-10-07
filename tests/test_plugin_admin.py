"""Editar, renombrar, cambiar id y eliminar plugins desde el API (solo administrador)."""

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.apiclient import TestServer, wait_run  # noqa: E402
from tests.helpers import PLUGINS  # noqa: E402

PASS = "clave-segura-1"


class PluginAdmin(unittest.TestCase):
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
        self.pid = "mi_plugin"
        dst = self.srv.extra_plugins / self.pid
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(PLUGINS / "_plantilla"), str(dst))
        self.admin.post("/api/plugins/reload")
        self.admin.post("/api/plugins/%s/enable" % self.pid)

    def tearDown(self):
        for d in list(self.srv.extra_plugins.iterdir()):
            if d.is_dir():
                shutil.rmtree(str(d), ignore_errors=True)
        self.admin.post("/api/plugins/reload")

    def status(self, pid):
        s, d = self.admin.get("/api/plugins")
        return {p["id"]: p for p in d["plugins"]}.get(pid)

    def wf(self, pid):
        s, d = self.admin.post("/api/workflows", {"name": "usa " + pid, "definition": {
            "nodes": [{"id": "a", "label": "A", "type": pid, "config": {"texto": "x", "veces": 2}}], "edges": []}})
        self.assertEqual(s, 201, d)
        return d["workflow"]["id"]

    def test_only_admin(self):
        for call in (lambda: self.ana.get("/api/plugins/%s/files" % self.pid),
                     lambda: self.ana.put("/api/plugins/%s/file" % self.pid, {"name": "task.py", "content": "x"}),
                     lambda: self.ana.post("/api/plugins/%s/rename" % self.pid, {"name": "Z"}),
                     lambda: self.ana.delete("/api/plugins/%s" % self.pid)):
            self.assertEqual(call()[0], 403)

    def test_list_and_read(self):
        s, d = self.admin.get("/api/plugins/%s/files" % self.pid)
        self.assertEqual(s, 200)
        self.assertEqual({f["name"] for f in d["files"]}, {"plugin.json", "task.py"})
        s, d = self.admin.get("/api/plugins/%s/file?name=task.py" % self.pid)
        self.assertIn("def run(config, ctx)", d["content"])
        self.assertEqual(self.admin.get("/api/plugins/%s/file?name=..%%2Fx.py" % self.pid)[0], 400)
        self.assertEqual(self.admin.get("/api/plugins/%s/file?name=nada.py" % self.pid)[0], 404)

    def test_edit_code_stays_enabled_and_runs_new_code(self):
        code = ('def run(config, ctx):\n    return {"rows": [], "total": 42}\n')
        s, d = self.admin.put("/api/plugins/%s/file" % self.pid, {"name": "task.py", "content": code})
        self.assertEqual(s, 200, d)
        self.assertEqual(self.status(self.pid)["status"], "enabled")      # reaprobado por el admin que editó
        wid = self.wf(self.pid)
        s, d = self.admin.post("/api/workflows/%d/run" % wid, {})
        self.assertIn(s, (200, 201, 202), d)
        run, _ = wait_run(self.admin, d["run_id"])
        self.assertEqual(run["status"], "ok", run)
        s, nd = self.admin.get("/api/runs/%s/nodes/a" % d["run_id"])
        self.assertEqual(s, 200, nd)
        self.assertEqual(nd["node"]["result"]["total"], 42)

    def test_invalid_edits_are_rejected_and_file_untouched(self):
        orig = (self.srv.extra_plugins / self.pid / "task.py").read_text(encoding="utf-8")
        s, d = self.admin.put("/api/plugins/%s/file" % self.pid, {"name": "task.py", "content": "def run(:\n"})
        self.assertEqual(s, 400)
        self.assertIn("no compila", d["error"] if "error" in d else str(d))
        self.assertEqual((self.srv.extra_plugins / self.pid / "task.py").read_text(encoding="utf-8"), orig)
        s, d = self.admin.put("/api/plugins/%s/file" % self.pid, {"name": "plugin.json", "content": "{no json"})
        self.assertEqual(s, 400)
        s, d = self.admin.put("/api/plugins/%s/file" % self.pid, {"name": "run.exe", "content": "x"})
        self.assertEqual(s, 400)
        s, d = self.admin.put("/api/plugins/%s/file" % self.pid, {"name": "plugin.json",
                              "content": '{"id":"otro","name":"x","version":"1.0.0"}'})
        self.assertEqual(s, 400)                                           # el id no se cambia aquí
        self.assertEqual(self.status(self.pid)["status"], "enabled")

    def test_new_helper_file(self):
        s, d = self.admin.put("/api/plugins/%s/file" % self.pid, {"name": "ayuda.py", "content": "X = 1\n"})
        self.assertEqual(s, 200, d)
        self.assertTrue((self.srv.extra_plugins / self.pid / "ayuda.py").is_file())

    def test_rename_display_name(self):
        s, d = self.admin.post("/api/plugins/%s/rename" % self.pid, {"name": "Mi nombre nuevo"})
        self.assertEqual(s, 200, d)
        p = self.status(self.pid)
        self.assertEqual(p["name"], "Mi nombre nuevo")
        self.assertEqual(p["status"], "enabled")

    def test_change_id_migrates_workflows(self):
        wid = self.wf(self.pid)
        s, d = self.admin.post("/api/plugins/%s/rename" % self.pid, {"id": "tarea_nueva"})
        self.assertEqual(s, 200, d)
        self.assertEqual(d["migrated_workflows"], 1)
        self.assertIsNone(self.status(self.pid))
        self.assertEqual(self.status("tarea_nueva")["status"], "enabled")
        self.assertTrue((self.srv.extra_plugins / "tarea_nueva").is_dir())
        s, d = self.admin.get("/api/workflows/%d" % wid)
        self.assertEqual(d["workflow"]["definition"]["nodes"][0]["type"], "tarea_nueva")
        s, d = self.admin.post("/api/plugins/%s/rename" % "tarea_nueva", {"id": "hello_world"})
        self.assertEqual(s, 409)
        s, d = self.admin.post("/api/plugins/%s/rename" % "tarea_nueva", {"id": "Mal Id"})
        self.assertEqual(s, 400)

    def test_delete_moves_to_trash(self):
        wid = self.wf(self.pid)
        s, d = self.admin.get("/api/plugins/%s/files" % self.pid)
        self.assertEqual(d["used_by"], ["usa " + self.pid])
        s, d = self.admin.delete("/api/plugins/%s" % self.pid)
        self.assertEqual(s, 200, d)
        self.assertEqual(d["used_by"], ["usa " + self.pid])
        self.assertIsNone(self.status(self.pid))
        self.assertFalse((self.srv.extra_plugins / self.pid).exists())
        trash = list((self.srv.extra_plugins / "_eliminados").iterdir())
        self.assertEqual(len(trash), 1)
        self.assertTrue((trash[0] / "plugin.json").is_file())             # recuperable a mano
        self.assertEqual(self.admin.delete("/api/plugins/%s" % self.pid)[0], 404)
        s, d = self.admin.post("/api/workflows/%d/validate" % wid, {})
        self.assertFalse(d["valid"])                                       # el workflow avisa que falta la tarea

    def test_audit_trail(self):
        self.admin.post("/api/plugins/%s/rename" % self.pid, {"name": "N"})
        self.admin.delete("/api/plugins/%s" % self.pid)
        s, d = self.admin.get("/api/audit?limit=50")
        actions = {a["action"] for a in d["audit"]}
        self.assertTrue({"plugin.edit", "plugin.rename", "plugin.delete"} <= actions)

    def test_disabled_by_config(self):
        self.srv.app.cfg["allow_plugin_edit"] = False
        try:
            self.assertEqual(self.admin.post("/api/plugins/%s/rename" % self.pid, {"name": "Z"})[0], 403)
            self.assertEqual(self.admin.delete("/api/plugins/%s" % self.pid)[0], 403)
        finally:
            self.srv.app.cfg["allow_plugin_edit"] = True


if __name__ == "__main__":
    unittest.main()
