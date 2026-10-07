"""Ejecución parcial desde el grafo: solo un paso, hasta un paso o desde un paso, reutilizando resultados previos."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.apiclient import TestServer, wait_run  # noqa: E402

PASS = "clave-segura-1"
DEF = {"nodes": [
    {"id": "a", "label": "A", "type": "hello_world", "config": {"nombre": "mundo", "filas": 2}},
    {"id": "b", "label": "B", "type": "hello_world", "config": {"nombre": "{{A.result.mensaje}}", "filas": 1}},
    {"id": "c", "label": "C", "type": "hello_world", "config": {"nombre": "{{B.result.mensaje}}", "filas": 1}},
    {"id": "d", "label": "D", "type": "hello_world", "config": {"nombre": "libre", "filas": 1}},
], "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]}


class Partial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = TestServer(scheduler_enabled=False)
        cls.c = cls.srv.client()
        assert cls.c.post("/api/setup", {"username": "admin", "password": PASS})[0] == 200
        assert cls.c.post("/api/users", {"username": "vera", "password": PASS, "role": "viewer"})[0] == 201
        cls.vera = cls.srv.client()
        cls.vera.post("/api/login", {"username": "vera", "password": PASS})

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()

    def wf(self):
        s, d = self.c.post("/api/workflows", {"name": "parcial", "definition": DEF})
        self.assertEqual(s, 201, d)
        return d["workflow"]["id"]

    def run_it(self, wid, **body):
        s, d = self.c.post("/api/workflows/%d/run" % wid, body)
        if s != 202:
            return s, d, None
        run, _ = wait_run(self.c, d["run_id"])
        return s, d, run

    def node(self, run_id, nid):
        return self.c.get("/api/runs/%s/nodes/%s" % (run_id, nid))[1]["node"]

    def test_only_without_previous_run_explains(self):
        wid = self.wf()
        s, d, _ = self.run_it(wid, only=["b"])
        self.assertEqual(s, 409)
        self.assertIn("necesita el resultado de: A", d["error"])

    def test_only_one_step_reuses_previous_results(self):
        wid = self.wf()
        s, d, full = self.run_it(wid)
        self.assertEqual(full["status"], "ok")
        s, d, run = self.run_it(wid, only=["b"])
        self.assertEqual(s, 202, d)
        self.assertEqual([r["node"] for r in d["reused"]], ["A"])
        self.assertEqual(run["status"], "ok", run)
        b = self.node(d["run_id"], "b")
        self.assertEqual(b["config"]["nombre"], "Hola, mundo")            # resolvió {{A...}} con el resultado previo
        a = self.node(d["run_id"], "a")
        self.assertEqual(a["status"], "ok")
        self.assertEqual(a["reason"], "resultado reutilizado")
        c = self.node(d["run_id"], "c")
        self.assertEqual(c["reason"], "resultado reutilizado")            # no se pidió: no se vuelve a ejecutar

    def test_from_step_runs_it_and_descendants_only(self):
        wid = self.wf()
        self.run_it(wid)
        s, d, run = self.run_it(wid, only=["b", "c"])
        self.assertEqual(s, 202, d)
        self.assertEqual([r["node"] for r in d["reused"]], ["A"])
        self.assertEqual(self.node(d["run_id"], "c")["status"], "ok")
        self.assertEqual(self.node(d["run_id"], "d")["reason"], "resultado reutilizado")  # D no se pidió

    def test_until_step_needs_no_previous_run(self):
        wid = self.wf()
        s, d, run = self.run_it(wid, only=["a", "b"])
        self.assertEqual(s, 202, d)
        self.assertEqual(d["reused"], [])
        self.assertEqual(run["status"], "ok")

    def test_independent_step_needs_nothing(self):
        wid = self.wf()
        s, d, run = self.run_it(wid, only=["d"])
        self.assertEqual(s, 202, d)
        self.assertEqual(run["status"], "ok")

    def test_results_carry_forward_between_partial_runs(self):
        wid = self.wf()
        self.run_it(wid)
        self.run_it(wid, only=["b"])
        s, d, run = self.run_it(wid, only=["c"])                           # B viene de la ejecución parcial anterior
        self.assertEqual(s, 202, d)
        self.assertEqual(self.node(d["run_id"], "c")["config"]["nombre"], "Hola, Hola, mundo")

    def test_invalid_only(self):
        wid = self.wf()
        self.assertEqual(self.c.post("/api/workflows/%d/run" % wid, {"only": ["zzz"]})[0], 400)
        self.assertEqual(self.c.post("/api/workflows/%d/run" % wid, {"only": []})[0], 400)
        self.assertEqual(self.c.post("/api/workflows/%d/run" % wid, {"only": "a"})[0], 400)

    def test_viewer_cannot_run(self):
        wid = self.wf()
        self.assertEqual(self.c.put("/api/workflows/%d/shares" % wid, {"team_access": "view", "shares": []})[0], 200)
        self.assertEqual(self.vera.post("/api/workflows/%d/run" % wid, {"only": ["d"]})[0], 403)


if __name__ == "__main__":
    unittest.main()
