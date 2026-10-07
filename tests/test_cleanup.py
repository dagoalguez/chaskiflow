"""Borrar ejecuciones, limpiar historial, eliminar definitivamente y vaciar papelera."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.apiclient import TestServer, wait_run  # noqa: E402

PASS = "clave-segura-1"
DEF = {"nodes": [{"id": "a", "label": "A", "type": "_plantilla_none", "config": {}}], "edges": []}


class Cleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = TestServer()
        cls.admin = cls.srv.client()
        assert cls.admin.post("/api/setup", {"username": "admin", "password": PASS})[0] == 200
        for u in ("ana", "beto"):
            assert cls.admin.post("/api/users", {"username": u, "password": PASS, "role": "editor"})[0] == 201
        cls.ana = cls.srv.client(); cls.ana.post("/api/login", {"username": "ana", "password": PASS})
        cls.beto = cls.srv.client(); cls.beto.post("/api/login", {"username": "beto", "password": PASS})
        cls.admin.post("/api/plugins/hello_world/enable")
        cls.admin.post("/api/plugins/slow/enable")

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()

    def mk(self, client, name="wf", ptype="hello_world", cfg=None):
        st, d = client.post("/api/workflows", {"name": name, "definition": {
            "nodes": [{"id": "a", "label": "A", "type": ptype, "config": cfg or {"nombre": "x", "filas": 1}}], "edges": []}})
        self.assertEqual(st, 201, d)
        return d["workflow"]["id"]

    def do_run(self, client, wid):
        st, d = client.post("/api/workflows/%d/run" % wid, {})
        self.assertEqual(st, 202, d)
        wait_run(client, d["run_id"])
        return d["run_id"]

    def test_delete_one_run_and_permissions(self):
        wid = self.mk(self.ana)
        r1, r2 = self.do_run(self.ana, wid), self.do_run(self.ana, wid)
        self.assertEqual(self.beto.delete("/api/runs/%s" % r1)[0], 404)       # no lo ve
        st, d = self.ana.delete("/api/runs/%s" % r1)
        self.assertEqual(st, 200, d)
        self.assertEqual(self.ana.get("/api/runs/%s" % r1)[0], 404)
        self.assertEqual(self.ana.get("/api/runs/%s" % r2)[0], 200)
        ids = [r["id"] for r in self.ana.get("/api/workflows/%d/runs" % wid)[1]["runs"]]
        self.assertEqual(ids, [r2])
        self.assertEqual(self.ana.delete("/api/runs/nope")[0], 404)

    def test_clear_history_keep(self):
        wid = self.mk(self.ana)
        ids = [self.do_run(self.ana, wid) for _ in range(4)]
        st, d = self.ana.post("/api/workflows/%d/runs/clear" % wid, {"keep": 1})
        self.assertEqual((st, d["deleted"]), (200, 3))
        left = self.ana.get("/api/workflows/%d/runs" % wid)[1]["runs"]
        self.assertEqual(len(left), 1)
        st, d = self.ana.post("/api/workflows/%d/runs/clear" % wid, {})
        self.assertEqual(d["deleted"], 1)
        self.assertEqual(self.beto.post("/api/workflows/%d/runs/clear" % wid, {})[0], 404)

    def test_purge_from_trash(self):
        wid = self.mk(self.ana, "borrame")
        rid = self.do_run(self.ana, wid)
        self.assertEqual(self.ana.delete("/api/workflows/%d/purge" % wid)[0], 404)   # aún no está en la papelera
        self.assertEqual(self.ana.delete("/api/workflows/%d" % wid)[0], 200)
        self.assertEqual(self.beto.delete("/api/workflows/%d/purge" % wid)[0], 404)
        st, d = self.ana.delete("/api/workflows/%d/purge" % wid)
        self.assertEqual(st, 200, d)
        self.assertEqual([w for w in self.ana.get("/api/workflows/trash")[1]["workflows"] if w["id"] == wid], [])
        self.assertEqual(self.ana.get("/api/runs/%s" % rid)[0], 404)
        self.assertEqual(self.ana.post("/api/workflows/%d/restore" % wid, {})[0], 404)
        self.assertEqual(self.srv_db_count("SELECT COUNT(*) FROM runs WHERE workflow_id=%d" % wid), 0)

    def srv_db_count(self, sql):
        import sqlite3
        con = sqlite3.connect(str(sorted((self.srv.tmp / "data").rglob("*.db"))[0]))
        try:
            return con.execute(sql).fetchone()[0]
        finally:
            con.close()

    def test_empty_trash_only_mine(self):
        a1, a2, b1 = self.mk(self.ana, "a1"), self.mk(self.ana, "a2"), self.mk(self.beto, "b1")
        for c, w in ((self.ana, a1), (self.ana, a2), (self.beto, b1)):
            self.assertEqual(c.delete("/api/workflows/%d" % w)[0], 200)
        st, d = self.ana.post("/api/workflows/trash/empty", {})
        self.assertEqual((st, d["purged"]), (200, 2), d)
        self.assertEqual([w["id"] for w in self.beto.get("/api/workflows/trash")[1]["workflows"]], [b1])
        st, d = self.admin.post("/api/workflows/trash/empty", {})
        self.assertEqual(d["purged"], 1)

    def test_health_reports_credits(self):
        st, d = self.srv.client().get("/api/health")
        self.assertEqual(st, 200)
        self.assertEqual((d["author"], d["contributions"], d["license"]), ("Diego Guevara B.", "Claude", "Apache-2.0"))

    def test_no_delete_running(self):
        import time
        wid = self.mk(self.ana, "lento", "slow", {"seconds": 6})
        st, d = self.ana.post("/api/workflows/%d/run" % wid, {})
        self.assertEqual(st, 202, d)
        rid = d["run_id"]
        time.sleep(0.5)
        self.assertEqual(self.ana.delete("/api/runs/%s" % rid)[0], 409)
        self.assertEqual(self.ana.post("/api/workflows/%d/runs/clear" % wid, {})[1]["deleted"], 0)
        self.assertEqual(self.ana.post("/api/runs/%s/cancel" % rid, {})[0], 200)
        wait_run(self.ana, rid)
        self.assertEqual(self.ana.delete("/api/runs/%s" % rid)[0], 200)


if __name__ == "__main__":
    unittest.main()
