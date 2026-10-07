"""Programación horaria: cálculo de próxima ejecución, API, disparo, tolerancia, permisos y migración v1->v2."""

import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chaskiflow import db as dbmod  # noqa: E402
from chaskiflow import scheduler as sch  # noqa: E402
from tests.apiclient import TestServer, n, wait_run, wf_def  # noqa: E402

PASS = "clave-segura-1"
SRV = ADMIN = ANA = BETO = VERA = None


def setUpModule():
    global SRV, ADMIN, ANA, BETO, VERA
    SRV = TestServer(scheduler_enabled=False)
    ADMIN = SRV.client()
    assert ADMIN.post("/api/setup", {"username": "admin", "password": PASS})[0] == 200
    for name, role in (("ana", "editor"), ("beto", "editor"), ("vera", "viewer")):
        assert ADMIN.post("/api/users", {"username": name, "password": PASS, "role": role})[0] == 201
    ANA, BETO, VERA = SRV.client(), SRV.client(), SRV.client()
    for c, name in ((ANA, "ana"), (BETO, "beto"), (VERA, "vera")):
        assert c.post("/api/login", {"username": name, "password": PASS})[0] == 200


def tearDownModule():
    SRV.stop()


def mk_wf(client, typ="hello_world", config=None, name="wf"):
    s, d = client.post("/api/workflows", {"name": name, "definition": wf_def(n("A", typ, config or {}))})
    assert s == 201, d
    return d["workflow"]["id"]


def ts(y, mo, d, h, mi):
    return time.mktime(datetime(y, mo, d, h, mi).timetuple())


class PureTests(unittest.TestCase):
    def test_compute_next_daily(self):
        wed_8 = ts(2026, 10, 7, 8, 0)                      # miércoles
        self.assertEqual(sch.compute_next("daily", "09:00", "", None, wed_8), ts(2026, 10, 7, 9, 0))
        self.assertEqual(sch.compute_next("daily", "07:30", "", None, wed_8), ts(2026, 10, 8, 7, 30))
        self.assertEqual(sch.compute_next("daily", "08:00", "", None, wed_8), ts(2026, 10, 8, 8, 0))  # estrictamente posterior
        self.assertEqual(sch.compute_next("daily", "07:30", "5,6", None, wed_8), ts(2026, 10, 10, 7, 30))  # sábado
        self.assertEqual(sch.compute_next("daily", "07:30", "0,1,2,3,4", None, ts(2026, 10, 9, 20, 0)),    # viernes noche
                         ts(2026, 10, 12, 7, 30))                                                          # lunes
        self.assertEqual(sch.compute_next("daily", "00:05", "", None, ts(2026, 12, 31, 23, 59)), ts(2027, 1, 1, 0, 5))

    def test_compute_next_interval(self):
        self.assertEqual(sch.compute_next("interval", "", "", 30, 1000), 1000 + 1800)

    def test_clean_schedule_validation(self):
        ok = sch.clean_schedule({"kind": "daily", "time": "7:05", "days": [0, 1, 2, 3, 4]})
        self.assertEqual((ok["time"], ok["days"]), ("07:05", "0,1,2,3,4"))
        self.assertEqual(sch.clean_schedule({"kind": "daily", "time": "07:00", "days": [0, 1, 2, 3, 4, 5, 6]})["days"], "")
        for bad in ({"kind": "daily", "time": "25:00"}, {"kind": "daily", "time": "7"}, {"kind": "daily", "time": "07:00", "days": [7]},
                    {"kind": "daily", "time": "07:00", "days": ["x"]}, {"kind": "interval"}, {"kind": "interval", "every_minutes": 0},
                    {"kind": "interval", "every_minutes": 99999}, {"kind": "raro"}, {"kind": "daily", "time": "07:00", "grace_minutes": 0},
                    {"kind": "daily", "time": "07:00", "variables": [1]}):
            with self.assertRaises(sch.ScheduleError, msg=str(bad)):
                sch.clean_schedule(bad)

    def test_describe(self):
        self.assertEqual(sch.describe({"kind": "daily", "days": "", "time": "07:30", "every_minutes": None}), "Todos los días a las 07:30")
        self.assertEqual(sch.describe({"kind": "daily", "days": "5,6", "time": "10:00", "every_minutes": None}), "sáb, dom a las 10:00")
        self.assertEqual(sch.describe({"kind": "interval", "days": "", "time": "", "every_minutes": 180}), "Cada 3 h")


class ApiTests(unittest.TestCase):
    def test_create_list_update_delete(self):
        wid = mk_wf(ANA)
        s, d = ANA.post("/api/workflows/%d/schedules" % wid, {"name": "Diario", "kind": "daily", "time": "07:30", "days": [0, 1, 2, 3, 4]})
        self.assertEqual(s, 201, d)
        sc = d["schedule"]
        self.assertEqual((sc["description"], sc["enabled"], sc["created_by"]), ("Lun–Vie a las 07:30", True, "ana"))
        self.assertTrue(sc["next_run"])
        sid = sc["id"]
        s, d = ANA.get("/api/workflows/%d/schedules" % wid)
        self.assertEqual([x["id"] for x in d["schedules"]], [sid])
        s, d = ANA.put("/api/schedules/%d" % sid, {"enabled": False})
        self.assertEqual((s, d["schedule"]["enabled"], d["schedule"]["next_run"]), (200, False, None))
        s, d = ANA.put("/api/schedules/%d" % sid, {"enabled": True, "time": "09:15"})
        self.assertEqual((s, d["schedule"]["time"]), (200, "09:15"))
        self.assertTrue(d["schedule"]["next_run"])
        self.assertEqual(ANA.put("/api/schedules/%d" % sid, {"time": "99:99"})[0], 400)
        self.assertIn(sid, [x["id"] for x in ANA.get("/api/schedules")[1]["schedules"]])
        self.assertEqual(ANA.delete("/api/schedules/%d" % sid)[0], 200)
        self.assertEqual(ANA.delete("/api/schedules/%d" % sid)[0], 404)

    def test_validation_errors(self):
        wid = mk_wf(ANA)
        for body in ({"kind": "daily", "time": "xx"}, {"kind": "interval", "every_minutes": "abc"}, {"kind": "otro"}):
            self.assertEqual(ANA.post("/api/workflows/%d/schedules" % wid, body)[0], 400, body)

    def test_permissions(self):
        wid = mk_wf(ANA)
        body = {"kind": "interval", "every_minutes": 60}
        self.assertEqual(BETO.post("/api/workflows/%d/schedules" % wid, body)[0], 404)        # no ve el workflow
        self.assertEqual(VERA.post("/api/workflows/%d/schedules" % wid, body)[0], 403)        # viewer
        ANA.put("/api/workflows/%d/shares" % wid, {"shares": [{"user_id": _uid("beto"), "permission": "view"}]})
        self.assertEqual(BETO.post("/api/workflows/%d/schedules" % wid, body)[0], 403)        # solo ver
        ANA.put("/api/workflows/%d/shares" % wid, {"shares": [{"user_id": _uid("beto"), "permission": "run"}]})
        s, d = BETO.post("/api/workflows/%d/schedules" % wid, body)
        self.assertEqual(s, 201)
        sid = d["schedule"]["id"]
        self.assertEqual(ANA.put("/api/schedules/%d" % sid, {"enabled": False})[0], 200)       # dueño edita
        ANA.put("/api/workflows/%d/shares" % wid, {"shares": []})
        self.assertEqual(BETO.delete("/api/schedules/%d" % sid)[0], 404)                       # ya no lo ve
        self.assertEqual(ADMIN.delete("/api/schedules/%d" % sid)[0], 200)


def _uid(name):
    return next(u["id"] for u in ADMIN.get("/api/users/directory")[1]["users"] if u["username"] == name)


def force_due(sid, seconds_ago=5):
    SRV.app.db.run("UPDATE schedules SET next_run=? WHERE id=?", (int(time.time()) - seconds_ago, sid))


class TickTests(unittest.TestCase):
    def new_schedule(self, client, wid, **kw):
        body = {"kind": "interval", "every_minutes": 60}
        body.update(kw)
        s, d = client.post("/api/workflows/%d/schedules" % wid, body)
        self.assertEqual(s, 201, d)
        return d["schedule"]["id"]

    def test_fires_run_with_schedule_trigger_and_advances(self):
        wid = mk_wf(ANA)
        sid = self.new_schedule(ANA, wid, every_minutes=30)
        now = int(time.time())
        self.assertEqual(SRV.app.scheduler.tick(now), [] if _next(sid) > now else None)  # aún no toca
        force_due(sid)
        fired = SRV.app.scheduler.tick()
        self.assertIn((sid, "iniciada"), fired)
        row = SRV.app.db.one("SELECT * FROM schedules WHERE id=?", (sid,))
        self.assertEqual(row["last_status"], "iniciada")
        self.assertGreater(row["next_run"], time.time() + 25 * 60)          # reprogramada
        run, _ = wait_run(ANA, row["last_run_id"])
        self.assertEqual(run["status"], "ok")
        self.assertEqual(run["trigger"], "schedule")
        self.assertEqual(run["started_by"], _uid("ana"))
        self.assertEqual(SRV.app.scheduler.tick(), [])                      # no se repite
        d = ANA.get("/api/workflows/%d/schedules" % wid)[1]["schedules"][0]
        self.assertEqual((d["last_status"], d["last_run_status"]), ("iniciada", "ok"))

    def test_disabled_does_not_fire(self):
        wid = mk_wf(ANA)
        sid = self.new_schedule(ANA, wid)
        ANA.put("/api/schedules/%d" % sid, {"enabled": False})
        SRV.app.db.run("UPDATE schedules SET next_run=? WHERE id=?", (int(time.time()) - 5, sid))
        self.assertNotIn(sid, [f[0] for f in SRV.app.scheduler.tick()])

    def test_missed_beyond_grace_is_skipped(self):
        wid = mk_wf(ANA)
        sid = self.new_schedule(ANA, wid, grace_minutes=60)
        force_due(sid, seconds_ago=3 * 3600)
        self.assertIn((sid, "omitida"), SRV.app.scheduler.tick())
        row = SRV.app.db.one("SELECT * FROM schedules WHERE id=?", (sid,))
        self.assertIn("no estaba disponible", row["last_message"])
        self.assertIsNone(row["last_run_id"])
        self.assertEqual(ANA.get("/api/workflows/%d/runs" % wid)[1]["runs"], [])
        self.assertGreater(row["next_run"], time.time())

    def test_within_grace_still_runs(self):
        wid = mk_wf(ANA)
        sid = self.new_schedule(ANA, wid, grace_minutes=120)
        force_due(sid, seconds_ago=30 * 60)
        self.assertIn((sid, "iniciada"), SRV.app.scheduler.tick())

    def test_skips_when_already_running(self):
        wid = mk_wf(ANA, "slow", {"seconds": 3})
        s, d = ANA.post("/api/workflows/%d/run" % wid)
        self.assertEqual(s, 202)
        sid = self.new_schedule(ANA, wid)
        force_due(sid)
        self.assertIn((sid, "omitida"), SRV.app.scheduler.tick())
        self.assertIn("ya se está ejecutando", SRV.app.db.one("SELECT last_message FROM schedules WHERE id=?", (sid,))["last_message"])
        wait_run(ANA, d["run_id"])

    def test_invalid_workflow_is_reported_not_crashing(self):
        wid = mk_wf(ANA, "no_existe_este_plugin")
        sid = self.new_schedule(ANA, wid)
        force_due(sid)
        self.assertIn((sid, "omitida"), SRV.app.scheduler.tick())
        self.assertIn("no es válido", SRV.app.db.one("SELECT last_message FROM schedules WHERE id=?", (sid,))["last_message"])

    def test_user_deactivated_or_permission_lost(self):
        wid = mk_wf(ANA)
        ANA.put("/api/workflows/%d/shares" % wid, {"shares": [{"user_id": _uid("beto"), "permission": "run"}]})
        sid = self.new_schedule(BETO, wid)
        ANA.put("/api/workflows/%d/shares" % wid, {"shares": []})
        force_due(sid)
        self.assertIn((sid, "error"), SRV.app.scheduler.tick())
        self.assertIn("permiso", SRV.app.db.one("SELECT last_message FROM schedules WHERE id=?", (sid,))["last_message"])
        # usuario inactivo
        u = ADMIN.post("/api/users", {"username": "temporal9", "password": PASS, "role": "editor"})[1]["user"]
        tmp = SRV.client()
        tmp.post("/api/login", {"username": "temporal9", "password": PASS})
        w2 = mk_wf(tmp)
        s2 = self.new_schedule(tmp, w2)
        ADMIN.put("/api/users/%d" % u["id"], {"active": False})
        force_due(s2)
        self.assertIn((s2, "error"), SRV.app.scheduler.tick())

    def test_deleted_workflow_disables_schedule(self):
        wid = mk_wf(ANA)
        sid = self.new_schedule(ANA, wid)
        ANA.delete("/api/workflows/%d" % wid)
        force_due(sid)
        self.assertIn((sid, "error"), SRV.app.scheduler.tick())
        row = SRV.app.db.one("SELECT enabled FROM schedules WHERE id=?", (sid,))
        self.assertEqual(row["enabled"], 0)

    def test_audit_has_schedule_events(self):
        wid = mk_wf(ANA)
        sid = self.new_schedule(ANA, wid)
        force_due(sid)
        SRV.app.scheduler.tick()
        actions = {a["action"] for a in ADMIN.get("/api/audit?limit=1000")[1]["audit"]}
        self.assertTrue({"schedule.create", "schedule.iniciada"} <= actions, actions)


def _next(sid):
    return SRV.app.db.one("SELECT next_run FROM schedules WHERE id=?", (sid,))["next_run"]


class ThreadTests(unittest.TestCase):
    def test_background_thread_fires_by_itself(self):
        srv = TestServer(scheduler_enabled=True, scheduler_tick_seconds=1)
        try:
            c = srv.client()
            c.post("/api/setup", {"username": "admin", "password": PASS})
            wid = c.post("/api/workflows", {"name": "x", "definition": wf_def(n("A", "hello_world"))})[1]["workflow"]["id"]
            sid = c.post("/api/workflows/%d/schedules" % wid, {"kind": "interval", "every_minutes": 60})[1]["schedule"]["id"]
            srv.app.db.run("UPDATE schedules SET next_run=? WHERE id=?", (int(time.time()) + 1, sid))
            deadline = time.time() + 10
            while time.time() < deadline:
                runs = c.get("/api/workflows/%d/runs" % wid)[1]["runs"]
                if runs:
                    break
                time.sleep(0.3)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["trigger"], "schedule")
        finally:
            srv.stop()


class MigrationTests(unittest.TestCase):
    def test_v1_database_gets_schedules_without_losing_data(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            p = tmp / "app.db"
            c = sqlite3.connect(str(p))
            dbmod._m1(c)
            c.execute("PRAGMA user_version = 1")
            c.execute("INSERT INTO users(username, password_hash, role, created_at) VALUES('viejo','x','admin','2026-01-01')")
            c.commit()
            c.close()
            d = dbmod.Database(p)
            self.assertIsNotNone(d.backup_path)
            self.assertTrue(d.backup_path.exists())
            self.assertEqual(d.one("SELECT username FROM users")["username"], "viejo")
            self.assertEqual(d.one("PRAGMA user_version")["user_version"], 2)
            self.assertIn("next_run", dbmod.table_columns(d.conn(), "schedules"))
            d2 = dbmod.Database(p)           # idempotente: sin nueva copia
            self.assertIsNone(d2.backup_path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
