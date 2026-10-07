"""Batería del API REST: autenticación, roles, plugins, workflows, ejecuciones, secretos, auditoría."""

import json
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chaskiflow import db as dbmod  # noqa: E402
from chaskiflow.auth import hash_password, verify_password  # noqa: E402
from chaskiflow.runs import RunManager  # noqa: E402
from tests.apiclient import TestServer, n, raw_request, wait_run, wf_def  # noqa: E402
from tests.helpers import FIXTURES  # noqa: E402

SRV = None
ADMIN = ANA = BETO = VERA = None
PASS = "clave-segura-1"


def setUpModule():
    global SRV, ADMIN, ANA, BETO, VERA
    SRV = TestServer()
    ADMIN = SRV.client()
    s, d = ADMIN.post("/api/setup", {"username": "admin", "password": PASS, "display_name": "Admin"})
    assert s == 200, d
    for name, role in (("ana", "editor"), ("beto", "editor"), ("vera", "viewer")):
        s, d = ADMIN.post("/api/users", {"username": name, "password": PASS, "role": role,
                                         "display_name": name.capitalize()})
        assert s == 201, d
    ANA, BETO, VERA = SRV.client(), SRV.client(), SRV.client()
    for c, name in ((ANA, "ana"), (BETO, "beto"), (VERA, "vera")):
        s, d = c.post("/api/login", {"username": name, "password": PASS})
        assert s == 200, d


def tearDownModule():
    SRV.stop()


def mk_wf(client, name, *nodes, edges=(), **kw):
    s, d = client.post("/api/workflows", {"name": name, "definition": wf_def(*nodes, edges=edges, **kw)})
    assert s == 201, d
    return d["workflow"]["id"]


def run_and_wait(client, wid, body=None, timeout=30):
    s, d = client.post("/api/workflows/%d/run" % wid, body or {})
    assert s == 202, d
    return wait_run(client, d["run_id"], timeout)


# =============================================================================== autenticación
class AuthTests(unittest.TestCase):
    def test_health_and_setup_state(self):
        s, d = SRV.client().get("/api/health")
        self.assertEqual(s, 200)
        self.assertFalse(d["needs_setup"])
        s, d = SRV.client().post("/api/setup", {"username": "otro", "password": "12345678"})
        self.assertEqual(s, 409)

    def test_setup_on_empty_system(self):
        t = TestServer()
        try:
            c = t.client()
            self.assertTrue(c.get("/api/health")[1]["needs_setup"])
            s, d = c.post("/api/setup", {"username": "ab", "password": "12345678"})
            self.assertEqual(s, 400)  # usuario demasiado corto
            s, d = c.post("/api/setup", {"username": "jefe", "password": "corta"})
            self.assertEqual(s, 400)  # contraseña corta
            s, d = c.post("/api/setup", {"username": "jefe", "password": "12345678"})
            self.assertEqual(s, 200)
            self.assertEqual(d["user"]["role"], "admin")
            self.assertEqual(c.get("/api/me")[0], 200)  # queda con sesión iniciada
            self.assertFalse(t.client().get("/api/health")[1]["needs_setup"])
        finally:
            t.stop()

    def test_requires_login(self):
        c = SRV.client()
        for p in ("/api/me", "/api/workflows", "/api/plugins", "/api/secrets", "/api/runs"):
            self.assertEqual(c.get(p)[0], 401, p)

    def test_wrong_password_is_generic(self):
        c = SRV.client()
        s1, d1 = c.post("/api/login", {"username": "admin", "password": "mala"})
        s2, d2 = c.post("/api/login", {"username": "no_existe", "password": "mala"})
        self.assertEqual((s1, s2), (401, 401))
        self.assertEqual(d1["error"], d2["error"])

    def test_login_throttle(self):
        c = SRV.client()
        for _ in range(5):
            self.assertEqual(c.post("/api/login", {"username": "victima", "password": "x"})[0], 401)
        s, d = c.post("/api/login", {"username": "victima", "password": "x"})
        self.assertEqual(s, 429)
        self.assertIn("Espere", d["error"])

    def test_logout_and_bearer(self):
        c = SRV.client()
        c.post("/api/login", {"username": "ana", "password": PASS})
        token = c.cookie.split("=", 1)[1]
        other = SRV.client()
        self.assertEqual(other.get("/api/me", headers={"Authorization": "Bearer " + token})[0], 200)
        c.post("/api/logout")
        self.assertIsNone(c.cookie)
        self.assertEqual(other.get("/api/me", headers={"Authorization": "Bearer " + token})[0], 401)

    def test_cookie_flags(self):
        c = SRV.client()
        c.call("POST", "/api/login", {"username": "ana", "password": PASS})
        sc = c.last_headers.get("Set-Cookie")
        self.assertIn("HttpOnly", sc)
        self.assertIn("SameSite=Strict", sc)

    def test_passwords_and_tokens_are_not_stored_in_clear(self):
        row = SRV.app.db.one("SELECT password_hash FROM users WHERE username='ana'")
        self.assertTrue(row["password_hash"].startswith("pbkdf2_sha256$"))
        self.assertNotIn(PASS, row["password_hash"])
        self.assertTrue(verify_password(PASS, row["password_hash"]))
        self.assertFalse(verify_password("otra", row["password_hash"]))
        c = SRV.client()
        c.post("/api/login", {"username": "ana", "password": PASS})
        token = c.cookie.split("=", 1)[1]
        hashes = [r["token_hash"] for r in SRV.app.db.all("SELECT token_hash FROM sessions")]
        self.assertNotIn(token, hashes)
        self.assertEqual(len(hashes[0]), 64)

    def test_idle_session_expires(self):
        c = SRV.client()
        ADMIN.post("/api/users", {"username": "ociosa", "password": PASS})
        c.post("/api/login", {"username": "ociosa", "password": PASS})
        self.assertEqual(c.get("/api/me")[0], 200)
        SRV.app.db.run("UPDATE sessions SET last_seen=last_seen-999999 WHERE user_id="
                       "(SELECT id FROM users WHERE username='ociosa')")
        self.assertEqual(c.get("/api/me")[0], 401)

    def test_change_password(self):
        s, d = ADMIN.post("/api/users", {"username": "temporal", "password": PASS})
        c = SRV.client()
        c.post("/api/login", {"username": "temporal", "password": PASS})
        c2 = SRV.client()
        c2.post("/api/login", {"username": "temporal", "password": PASS})
        self.assertEqual(c.post("/api/me/password", {"current": "mal", "new": "nueva-clave-9"})[0], 400)
        self.assertEqual(c.post("/api/me/password", {"current": PASS, "new": "corta"})[0], 400)
        self.assertEqual(c.post("/api/me/password", {"current": PASS, "new": "nueva-clave-9"})[0], 200)
        self.assertEqual(c.get("/api/me")[0], 200)       # la sesión actual sigue
        self.assertEqual(c2.get("/api/me")[0], 401)      # las otras se cierran
        self.assertEqual(SRV.client().post("/api/login", {"username": "temporal", "password": PASS})[0], 401)
        self.assertEqual(SRV.client().post("/api/login", {"username": "temporal", "password": "nueva-clave-9"})[0], 200)

    def test_must_change_password_flow(self):
        ADMIN.post("/api/users", {"username": "nuevo1", "password": "inicial-123", "must_change_password": True})
        c = SRV.client()
        s, d = c.post("/api/login", {"username": "nuevo1", "password": "inicial-123"})
        self.assertEqual(s, 200)
        self.assertTrue(d["user"]["must_change_password"])
        s, d = c.get("/api/workflows")
        self.assertEqual(s, 403)
        self.assertEqual(d["code"], "must_change_password")
        self.assertEqual(c.post("/api/me/password", {"current": "inicial-123", "new": "definitiva-77"})[0], 200)
        self.assertEqual(c.get("/api/workflows")[0], 200)

    def test_csrf_origin_check(self):
        s, d = ANA.post("/api/workflows", {"name": "x"}, headers={"Origin": "http://evil.example"})
        self.assertEqual(s, 403)
        host = SRV.base.split("//")[1]
        s, d = ANA.post("/api/workflows", {"name": "ok-origin"}, headers={"Origin": "http://" + host})
        self.assertEqual(s, 201)
        # GET no se bloquea por Origin (no cambia nada)
        self.assertEqual(ANA.get("/api/me", headers={"Origin": "http://evil.example"})[0], 200)

    def test_bad_requests(self):
        self.assertEqual(ANA.post("/api/workflows", raw_body=b"{no es json")[0], 400)
        self.assertEqual(ANA.post("/api/workflows", raw_body=b"[1,2]")[0], 400)
        self.assertEqual(ANA.get("/api/no_existe")[0], 404)
        self.assertEqual(ANA.call("DELETE", "/api/me")[0], 405)

    def test_body_limit(self):
        old = SRV.app.max_body
        SRV.app.max_body = 500
        try:
            s, d = ANA.post("/api/workflows", {"name": "x" * 1000})
            self.assertEqual(s, 413)
        finally:
            SRV.app.max_body = old
        self.assertEqual(ANA.get("/api/me")[0], 200)  # el servidor sigue sano

    def test_security_headers(self):
        ANA.get("/api/me")
        h = ANA.last_headers
        self.assertIn("default-src 'self'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertEqual(h["Cache-Control"], "no-store")


# =============================================================================== usuarios y roles
class UserTests(unittest.TestCase):
    def test_only_admin_manages_users(self):
        self.assertEqual(ADMIN.get("/api/users")[0], 200)
        self.assertEqual(ANA.get("/api/users")[0], 403)
        self.assertEqual(ANA.post("/api/users", {"username": "zzz1", "password": PASS})[0], 403)
        self.assertEqual(VERA.get("/api/audit")[0], 403)

    def test_directory_for_everyone(self):
        s, d = ANA.get("/api/users/directory")
        self.assertEqual(s, 200)
        names = {u["username"] for u in d["users"]}
        self.assertTrue({"admin", "ana", "beto", "vera"} <= names)
        self.assertNotIn("password_hash", json.dumps(d))

    def test_duplicate_and_invalid_users(self):
        self.assertEqual(ADMIN.post("/api/users", {"username": "ANA", "password": PASS})[0], 400)  # sin distinguir mayúsculas
        self.assertEqual(ADMIN.post("/api/users", {"username": "a b", "password": PASS})[0], 400)
        self.assertEqual(ADMIN.post("/api/users", {"username": "zeta1", "password": PASS, "role": "dios"})[0], 400)

    def test_cannot_remove_last_admin(self):
        uid = ADMIN.get("/api/me")[1]["user"]["id"]
        self.assertEqual(ADMIN.put("/api/users/%d" % uid, {"role": "editor"})[0], 409)
        self.assertEqual(ADMIN.put("/api/users/%d" % uid, {"active": False})[0], 409)

    def test_deactivate_user_kills_sessions(self):
        s, d = ADMIN.post("/api/users", {"username": "baja1", "password": PASS})
        uid = d["user"]["id"]
        c = SRV.client()
        c.post("/api/login", {"username": "baja1", "password": PASS})
        self.assertEqual(c.get("/api/me")[0], 200)
        self.assertEqual(ADMIN.put("/api/users/%d" % uid, {"active": False})[0], 200)
        self.assertEqual(c.get("/api/me")[0], 401)
        self.assertEqual(SRV.client().post("/api/login", {"username": "baja1", "password": PASS})[0], 401)
        self.assertEqual(ADMIN.put("/api/users/%d" % uid, {"active": True})[0], 200)
        self.assertEqual(SRV.client().post("/api/login", {"username": "baja1", "password": PASS})[0], 200)

    def test_admin_resets_password_forces_change(self):
        s, d = ADMIN.post("/api/users", {"username": "reset1", "password": PASS})
        uid = d["user"]["id"]
        ADMIN.put("/api/users/%d" % uid, {"password": "provisional-1"})
        c = SRV.client()
        s, d = c.post("/api/login", {"username": "reset1", "password": "provisional-1"})
        self.assertTrue(d["user"]["must_change_password"])

    def test_viewer_cannot_create_but_editor_can(self):
        self.assertEqual(VERA.post("/api/workflows", {"name": "no"})[0], 403)
        self.assertEqual(ANA.post("/api/workflows", {"name": "si"})[0], 201)


# =============================================================================== plugins
class PluginTests(unittest.TestCase):
    def test_catalog_admin_vs_editor(self):
        s, d = ADMIN.get("/api/plugins")
        by = {p["id"]: p for p in d["plugins"]}
        self.assertEqual(by["export_csv"]["status"], "enabled")
        self.assertIn("hash", by["export_csv"])
        self.assertTrue(any(p["status"] == "invalid" and p["errors"] for p in d["plugins"]))  # 'roto', etc.
        s, d = ANA.get("/api/plugins")
        ids = {p["id"] for p in d["plugins"]}
        self.assertIn("export_csv", ids)
        for p in d["plugins"]:
            self.assertEqual(p["status"], "enabled")
            self.assertNotIn("hash", p)
            self.assertNotIn("path", p)

    def test_new_plugin_needs_admin_approval(self):
        src = SRV.extra_plugins / "aprobar_me"
        src.mkdir(exist_ok=True)
        (src / "plugin.json").write_text(json.dumps({"id": "aprobar_me", "name": "Aprobar", "version": "1.0.0",
                                                     "fields": [{"key": "v", "type": "any"}]}))
        (src / "task.py").write_text("def run(config, ctx):\n    return {'v': config.get('v')}\n")
        self.assertEqual(ANA.post("/api/plugins/reload")[0], 403)
        s, d = ADMIN.post("/api/plugins/reload")
        st = {p["id"]: p["status"] for p in d["plugins"]}
        self.assertEqual(st["aprobar_me"], "pending")
        self.assertNotIn("aprobar_me", {p["id"] for p in ANA.get("/api/plugins")[1]["plugins"]})
        wid = mk_wf(ANA, "usa pendiente", n("A", "aprobar_me", {"v": 1}))
        s, d = ANA.post("/api/workflows/%d/run" % wid)
        self.assertEqual(s, 422)
        self.assertIn("pendiente de aprobación", d["error"])
        self.assertEqual(ANA.post("/api/plugins/aprobar_me/enable")[0], 403)
        self.assertEqual(ADMIN.post("/api/plugins/aprobar_me/enable")[0], 200)
        run, _ = run_and_wait(ANA, wid)
        self.assertEqual(run["status"], "ok")
        # el código cambia -> bloqueado hasta nueva aprobación
        (src / "task.py").write_text("def run(config, ctx):\n    return {'v': 'cambiado'}\n")
        ADMIN.post("/api/plugins/reload")
        st = {p["id"]: p["status"] for p in ADMIN.get("/api/plugins")[1]["plugins"]}
        self.assertEqual(st["aprobar_me"], "changed")
        s, d = ANA.post("/api/workflows/%d/run" % wid)
        self.assertEqual(s, 422)
        self.assertIn("cambió desde que fue aprobada", d["error"])
        ADMIN.post("/api/plugins/aprobar_me/enable")
        self.assertEqual(run_and_wait(ANA, wid)[0]["status"], "ok")
        # deshabilitar
        ADMIN.post("/api/plugins/aprobar_me/disable")
        s, d = ANA.post("/api/workflows/%d/run" % wid)
        self.assertEqual(s, 422)
        self.assertIn("deshabilitada", d["error"])

    def test_enable_unknown_plugin(self):
        self.assertEqual(ADMIN.post("/api/plugins/no_existe/enable")[0], 404)

    def test_first_run_seeds_but_later_plugins_are_pending(self):
        t = TestServer()
        try:
            c = t.client()
            c.post("/api/setup", {"username": "jefe", "password": PASS})
            self.assertTrue(all(p["status"] == "enabled" for p in c.get("/api/plugins")[1]["plugins"]
                                if p["status"] != "invalid"))
        finally:
            t.stop()


# =============================================================================== workflows
class WorkflowTests(unittest.TestCase):
    def test_crud_and_versions(self):
        wid = mk_wf(ANA, "crud", n("A", "ok_echo", {"value": 1}))
        s, d = ANA.get("/api/workflows/%d" % wid)
        self.assertEqual((s, d["workflow"]["version"], d["workflow"]["access"]), (200, 1, "edit"))
        self.assertEqual(d["workflow"]["definition"]["nodes"][0]["id"], "A")
        s, d = ANA.put("/api/workflows/%d" % wid, {"name": "crud2", "version": 1})
        self.assertEqual((s, d["workflow"]["version"]), (200, 2))
        s, d = ANA.put("/api/workflows/%d" % wid, {"name": "x"})
        self.assertEqual(s, 400)  # falta version
        s, d = ANA.get("/api/workflows")
        self.assertIn("crud2", [w["name"] for w in d["workflows"]])

    def test_conflict_on_stale_version(self):
        wid = mk_wf(ANA, "conflicto", n("A", "ok_echo"))
        ANA.post("/api/workflows/%d/duplicate" % wid)  # no afecta
        ADMIN.put("/api/workflows/%d" % wid, {"description": "cambio admin", "version": 1})
        s, d = ANA.put("/api/workflows/%d" % wid, {"description": "mi cambio", "version": 1})
        self.assertEqual(s, 409)
        self.assertEqual(d["current_version"], 2)
        self.assertIn("Admin", d["error"])

    def test_parallel_updates_only_one_wins(self):
        wid = mk_wf(ANA, "carrera", n("A", "ok_echo"))
        results = []

        def go(i):
            c = SRV.client()
            c.post("/api/login", {"username": "ana", "password": PASS})
            results.append(c.put("/api/workflows/%d" % wid, {"description": "v%d" % i, "version": 1})[0])

        ths = [threading.Thread(target=go, args=(i,)) for i in range(8)]
        [t.start() for t in ths]
        [t.join() for t in ths]
        self.assertEqual(sorted(results), [200] + [409] * 7)

    def test_invalid_definitions_rejected(self):
        for bad in ({"nodes": "x"}, {"nodes": [{"label": "sin id"}]}, {"nodes": [], "edges": [{"source": "a"}]},
                    {"nodes": [{"id": "a", "config": "no objeto"}]}, {"variables": []}):
            s, d = ANA.post("/api/workflows", {"name": "mala", "definition": bad})
            self.assertEqual(s, 400, bad)
        self.assertEqual(ANA.post("/api/workflows", {"name": "", "definition": {}})[0], 400)
        many = {"nodes": [{"id": "n%d" % i, "type": "x"} for i in range(501)]}
        self.assertEqual(ANA.post("/api/workflows", {"name": "grande", "definition": many})[0], 400)

    def test_soft_delete_trash_restore(self):
        wid = mk_wf(ANA, "borrame", n("A", "ok_echo"))
        s, d = ANA.delete("/api/workflows/%d" % wid)
        self.assertEqual(s, 200)
        self.assertIn("/restore", d["undo"])
        self.assertNotIn(wid, [w["id"] for w in ANA.get("/api/workflows")[1]["workflows"]])
        self.assertEqual(ANA.get("/api/workflows/%d" % wid)[0], 404)
        self.assertIn(wid, [w["id"] for w in ANA.get("/api/workflows/trash")[1]["workflows"]])
        self.assertNotIn(wid, [w["id"] for w in BETO.get("/api/workflows/trash")[1]["workflows"]])
        self.assertEqual(BETO.post("/api/workflows/%d/restore" % wid)[0], 404)
        self.assertEqual(ANA.post("/api/workflows/%d/restore" % wid)[0], 200)
        self.assertEqual(ANA.get("/api/workflows/%d" % wid)[0], 200)
        self.assertTrue(SRV.app.db.one("SELECT 1 FROM workflows WHERE id=?", (wid,)))  # nunca se borra de verdad

    def test_permission_matrix(self):
        wid = mk_wf(ANA, "permisos", n("A", "ok_echo", {"value": 7}))
        base = "/api/workflows/%d" % wid
        self.assertEqual(BETO.get(base)[0], 404)  # ni siquiera sabe que existe
        self.assertNotIn(wid, [w["id"] for w in BETO.get("/api/workflows")[1]["workflows"]])
        beto_id = next(u["id"] for u in ANA.get("/api/users/directory")[1]["users"] if u["username"] == "beto")
        vera_id = next(u["id"] for u in ANA.get("/api/users/directory")[1]["users"] if u["username"] == "vera")

        def share(perm, uid=beto_id, team="none"):
            return ANA.put(base + "/shares", {"team_access": team, "shares": [{"user_id": uid, "permission": perm}]})

        self.assertEqual(share("view")[0], 200)
        self.assertEqual(BETO.get(base)[1]["workflow"]["access"], "view")
        self.assertEqual(BETO.put(base, {"name": "x", "version": 1})[0], 403)
        self.assertEqual(BETO.post(base + "/run")[0], 403)
        self.assertEqual(BETO.get(base + "/runs")[0], 200)

        self.assertEqual(share("run")[0], 200)
        run, _ = run_and_wait(BETO, wid)
        self.assertEqual(run["status"], "ok")
        self.assertEqual(BETO.put(base, {"name": "x", "version": 1})[0], 403)

        self.assertEqual(share("edit")[0], 200)
        self.assertEqual(BETO.put(base, {"description": "beto edita", "version": 1})[0], 200)
        self.assertEqual(BETO.delete(base)[0], 403)                    # borrar: solo dueño/admin
        self.assertEqual(BETO.put(base + "/shares", {"shares": []})[0], 403)
        self.assertNotIn("shares", BETO.get(base)[1]["workflow"])      # no ve la lista de compartidos

        # el rol viewer nunca pasa de 'view'
        self.assertEqual(share("edit", uid=vera_id)[0], 200)
        self.assertEqual(VERA.get(base)[1]["workflow"]["access"], "view")
        self.assertEqual(VERA.post(base + "/run")[0], 403)

        # acceso del equipo
        self.assertEqual(ANA.put(base + "/shares", {"team_access": "view", "shares": []})[0], 200)
        self.assertEqual(BETO.get(base)[1]["workflow"]["access"], "view")
        self.assertEqual(ANA.put(base + "/shares", {"team_access": "none", "shares": []})[0], 200)
        self.assertEqual(BETO.get(base)[0], 404)

        # el administrador lo ve y lo edita todo
        self.assertEqual(ADMIN.get(base)[1]["workflow"]["access"], "edit")

    def test_shares_validation(self):
        wid = mk_wf(ANA, "shares", n("A", "ok_echo"))
        base = "/api/workflows/%d/shares" % wid
        self.assertEqual(ANA.put(base, {"shares": [{"user_id": 9999, "permission": "view"}]})[0], 400)
        self.assertEqual(ANA.put(base, {"shares": [{"user_id": 1, "permission": "dueño"}]})[0], 400)
        self.assertEqual(ANA.put(base, {"team_access": "todo"})[0], 400)

    def test_duplicate_and_export_import(self):
        wid = mk_wf(ANA, "original", n("A", "ok_echo", {"value": 5}))
        s, d = BETO.post("/api/workflows/%d/duplicate" % wid)
        self.assertEqual(s, 404)  # sin acceso
        s, d = ANA.post("/api/workflows/%d/duplicate" % wid)
        self.assertEqual(s, 201)
        self.assertEqual(d["workflow"]["name"], "original (copia)")
        s, exported = ANA.get("/api/workflows/%d/export" % wid)
        self.assertEqual(exported["format"], "chaskiflow-workflow/1")
        s, d = BETO.post("/api/workflows/import", {"name": "importado", "definition": exported})
        self.assertEqual(s, 201)
        self.assertEqual(d["workflow"]["owner"], "Beto")
        self.assertEqual(d["workflow"]["definition"]["nodes"][0]["config"], {"value": 5})

    def test_validate_endpoint(self):
        wid = mk_wf(ANA, "valida", n("A", "ok_echo"))
        base = "/api/workflows/%d/validate" % wid
        s, d = ANA.post(base)
        self.assertEqual((s, d["valid"]), (200, True))
        bad = wf_def(n("A", "ok_echo"), n("B", "ok_echo"), edges=[("A", "B"), ("B", "A")])
        s, d = ANA.post(base, {"definition": bad})
        self.assertFalse(d["valid"])
        self.assertTrue(any("ciclo" in e for e in d["errors"]))
        bad = wf_def(n("A", "no_existe"))
        self.assertIn("no está instalada", ANA.post(base, {"definition": bad})[1]["errors"][0])

    def test_list_includes_last_run(self):
        wid = mk_wf(ANA, "con corrida", n("A", "ok_echo"))
        run_and_wait(ANA, wid)
        w = next(x for x in ANA.get("/api/workflows")[1]["workflows"] if x["id"] == wid)
        self.assertEqual(w["last_run"]["status"], "ok")


# =============================================================================== ejecuciones
class RunTests(unittest.TestCase):
    def test_lifecycle_events_and_persistence(self):
        wid = mk_wf(ANA, "ciclo", n("A", "hello_world", {"filas": 4}),
                    n("B", "ok_echo", {"value": "{{A.result.rows}}"}), edges=[("A", "B")])
        run, events = run_and_wait(ANA, wid)
        self.assertEqual(run["status"], "ok")
        types = [e["type"] for e in events]
        self.assertEqual(types[0], "queued")
        self.assertIn("run_start", types)
        self.assertEqual(types[-1], "run_final")
        seqs = [e["seq"] for e in events]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual({x["node_id"]: x["status"] for x in run["nodes"]}, {"A": "ok", "B": "ok"})
        s, d = ANA.get("/api/runs/%s/nodes/B" % run["id"])
        self.assertEqual(len(d["node"]["result"]["echo"]), 4)       # tipo nativo, no texto
        self.assertTrue(any(l["message"].startswith("Generando") for l in
                            ANA.get("/api/runs/%s/nodes/A" % run["id"])[1]["node"]["logs"]))
        s, d = ANA.get("/api/workflows/%d/runs" % wid)
        self.assertEqual(d["runs"][0]["id"], run["id"])
        self.assertEqual(d["runs"][0]["started_by_name"], "Ana")

    def test_events_after_cursor(self):
        wid = mk_wf(ANA, "cursor", n("A", "ok_echo"))
        run, events = run_and_wait(ANA, wid)
        last = events[-1]["seq"]
        s, d = ANA.get("/api/runs/%s/events?after=%d" % (run["id"], last))
        self.assertEqual(d["events"], [])
        self.assertTrue(d["done"])
        s, d = ANA.get("/api/runs/%s/events?after=2" % run["id"])
        self.assertTrue(all(e["seq"] > 2 for e in d["events"]))

    def test_invalid_workflow_cannot_start(self):
        wid = mk_wf(ANA, "invalido", n("A", "ok_echo", {"value": "{{Fantasma.result.x}}"}))
        s, d = ANA.post("/api/workflows/%d/run" % wid)
        self.assertEqual(s, 422)
        self.assertIn("Fantasma", d["error"])

    def test_error_and_partial_statuses(self):
        wid = mk_wf(ANA, "falla", n("A", "fail"), n("B", "ok_echo"), edges=[("A", "B")])
        run, _ = run_and_wait(ANA, wid)
        self.assertEqual(run["status"], "error")
        st = {x["node_id"]: x for x in run["nodes"]}
        self.assertIn("falló a propósito", st["A"]["error"])
        self.assertEqual(st["B"]["status"], "skipped")
        wid = mk_wf(ANA, "parcial", n("A", "fail", on_error="continue"), n("B", "ok_echo"), edges=[("A", "B")])
        self.assertEqual(run_and_wait(ANA, wid)[0]["status"], "partial")

    def test_one_run_at_a_time_per_workflow_and_cancel(self):
        wid = mk_wf(ANA, "lento", n("A", "slow", {"seconds": 20}), n("B", "ok_echo"), edges=[("A", "B")])
        s, d = ANA.post("/api/workflows/%d/run" % wid)
        self.assertEqual(s, 202)
        rid = d["run_id"]
        time.sleep(0.5)
        s, d2 = ANA.post("/api/workflows/%d/run" % wid)
        self.assertEqual(s, 409)
        self.assertEqual(VERA.post("/api/runs/%s/cancel" % rid)[0], 404)  # sin acceso
        t0 = time.time()
        self.assertEqual(ANA.post("/api/runs/%s/cancel" % rid)[0], 200)
        run, _ = wait_run(ANA, rid)
        self.assertLess(time.time() - t0, 8)
        self.assertEqual(run["status"], "cancelled")
        self.assertEqual(ANA.post("/api/runs/%s/cancel" % rid)[0], 409)  # ya terminó
        self.assertEqual(run_and_wait(ANA, mk_wf(ANA, "otro", n("A", "ok_echo")))[0]["status"], "ok")
        s, d = ANA.post("/api/workflows/%d/run" % wid)                    # se puede volver a ejecutar
        self.assertEqual(s, 202)
        ANA.post("/api/runs/%s/cancel" % d["run_id"])
        wait_run(ANA, d["run_id"])

    def test_variables_and_rerun_single_node(self):
        wid = mk_wf(ANA, "vars", n("A", "ok_echo", {"value": "hola {{vars.quien}}"}),
                    n("B", "ok_echo", {"value": "{{A.result.echo}}!"}), edges=[("A", "B")],
                    variables={"quien": "mundo"})
        run1, _ = run_and_wait(ANA, wid, {"variables": {"quien": "equipo"}})
        res = {x["node_id"]: ANA.get("/api/runs/%s/nodes/%s" % (run1["id"], x["node_id"]))[1]["node"] for x in run1["nodes"]}
        self.assertEqual(res["B"]["result"]["echo"], "hola equipo!")
        run2, _ = run_and_wait(ANA, wid, {"only": ["B"], "from_run": run1["id"], "variables": {"quien": "equipo"}})
        st = {x["node_id"]: x["status"] for x in run2["nodes"]}
        self.assertEqual(st, {"A": "ok", "B": "ok"})
        a1 = res["A"]["result"]["pid"]
        a2 = ANA.get("/api/runs/%s/nodes/A" % run2["id"])[1]["node"]["result"]["pid"]
        self.assertEqual(a1, a2)  # A no se volvió a ejecutar

    def test_big_result_roundtrip_compressed(self):
        wid = mk_wf(ANA, "grande", n("A", "big"))
        run, _ = run_and_wait(ANA, wid)
        size = SRV.app.db.one("SELECT length(result) AS l, result_size AS s FROM run_nodes WHERE run_id=? "
                              "AND node_id='A'", (run["id"],))
        self.assertLess(size["l"], size["s"] / 100)  # 5 MB de 'x' comprimen muchísimo
        s, d = ANA.get("/api/runs/%s/nodes/A" % run["id"])
        self.assertEqual(len(d["node"]["result"]["blob"]), 5000000)
        self.assertNotIn("result", ANA.get("/api/runs/%s" % run["id"])[1]["run"]["nodes"][0])  # el listado no los trae

    def test_run_visibility(self):
        wid = mk_wf(ANA, "privada", n("A", "ok_echo"))
        run, _ = run_and_wait(ANA, wid)
        self.assertEqual(BETO.get("/api/runs/%s" % run["id"])[0], 404)
        self.assertNotIn(run["id"], [r["id"] for r in BETO.get("/api/runs")[1]["runs"]])
        self.assertIn(run["id"], [r["id"] for r in ANA.get("/api/runs")[1]["runs"]])
        self.assertIn(run["id"], [r["id"] for r in ADMIN.get("/api/runs?limit=100")[1]["runs"]])

    def test_interrupted_runs_are_marked_on_restart(self):
        db = SRV.app.db
        db.run("INSERT INTO runs(id, workflow_id, workflow_name, status, started) VALUES('zombie-1',1,'x','running','2026-01-01')")
        RunManager(db, SRV.app.gate, SRV.app.data_dir)
        r = db.one("SELECT status, error FROM runs WHERE id='zombie-1'")
        self.assertEqual(r["status"], "error")
        self.assertIn("reinició", r["error"])

    def test_retention_purge(self):
        db = SRV.app.db
        db.run("INSERT INTO runs(id, workflow_id, workflow_name, status, started) VALUES('vieja-1',1,'x','ok','2000-01-01T00:00:00')")
        db.run("INSERT INTO run_nodes(run_id, node_id, status) VALUES('vieja-1','A','ok')")
        self.assertGreaterEqual(SRV.app.runs.purge_old(), 1)
        self.assertIsNone(db.one("SELECT 1 FROM runs WHERE id='vieja-1'"))
        self.assertIsNone(db.one("SELECT 1 FROM run_nodes WHERE run_id='vieja-1'"))  # en cascada

    def test_temp_dirs_cleaned(self):
        wid = mk_wf(ANA, "limpieza", n("A", "ok_echo"))
        run, _ = run_and_wait(ANA, wid)
        time.sleep(0.3)
        self.assertFalse((SRV.app.runs.tmp_root / run["id"]).exists())


# =============================================================================== secretos
class SecretTests(unittest.TestCase):
    def test_secret_flow_and_masking(self):
        wid = mk_wf(ANA, "secreto", n("A", "secret_reader"))
        run, _ = run_and_wait(ANA, wid)
        self.assertEqual(run["status"], "error")
        self.assertIn("Falta el secreto 'api_token'", run["nodes"][0]["error"])
        self.assertEqual(ANA.put("/api/secrets/api_token", {"value": "valor-privado-ana", "scope": "global"})[0], 403)
        self.assertEqual(ADMIN.put("/api/secrets/api_token", {"value": "global-123456", "scope": "global"})[0], 200)
        run, _ = run_and_wait(ANA, wid)
        node = ANA.get("/api/runs/%s/nodes/A" % run["id"])[1]["node"]
        self.assertEqual(node["result"]["len"], len("global-123456"))
        self.assertEqual(ANA.put("/api/secrets/api_token", {"value": "valor-privado-ana"})[0], 200)
        run, _ = run_and_wait(ANA, wid)
        node = ANA.get("/api/runs/%s/nodes/A" % run["id"])[1]["node"]
        self.assertEqual(node["result"]["len"], len("valor-privado-ana"))   # el personal gana al global
        logs = json.dumps(node["logs"])
        self.assertNotIn("valor-privado-ana", logs)
        self.assertIn("***", logs)
        # un workflow compartido usa los secretos del DUEÑO, no los de quien ejecuta
        beto_id = next(u["id"] for u in ANA.get("/api/users/directory")[1]["users"] if u["username"] == "beto")
        ANA.put("/api/workflows/%d/shares" % wid, {"shares": [{"user_id": beto_id, "permission": "run"}]})
        BETO.put("/api/secrets/api_token", {"value": "beto-otro-valor-largo"})
        run, _ = run_and_wait(BETO, wid)
        self.assertEqual(BETO.get("/api/runs/%s/nodes/A" % run["id"])[1]["node"]["result"]["len"], len("valor-privado-ana"))

    def test_secret_values_never_leave_the_api(self):
        ANA.put("/api/secrets/otro_secreto", {"value": "SUPER-SECRETO-XYZ"})
        s, d = ANA.get("/api/secrets")
        self.assertIn("otro_secreto", [x["name"] for x in d["secrets"]])
        blob = json.dumps(d) + json.dumps(ADMIN.get("/api/audit")[1]) + json.dumps(ADMIN.get("/api/secrets")[1])
        self.assertNotIn("SUPER-SECRETO-XYZ", blob)
        self.assertIn("secret.set", blob)  # sí queda registrado QUE se cambió

    def test_secret_validation_and_isolation(self):
        self.assertEqual(ANA.put("/api/secrets/nombre%20malo", {"value": "x"})[0], 400)
        self.assertEqual(ANA.put("/api/secrets/ok_nombre", {"value": ""})[0], 400)
        self.assertEqual(VERA.put("/api/secrets/vera_s", {"value": "x1234567"})[0], 403)
        ANA.put("/api/secrets/solo_ana", {"value": "abcdef123"})
        self.assertNotIn("solo_ana", [x["name"] for x in BETO.get("/api/secrets")[1]["secrets"]])
        self.assertEqual(BETO.delete("/api/secrets/solo_ana")[0], 404)
        self.assertEqual(ANA.delete("/api/secrets/solo_ana")[0], 200)
        self.assertEqual(ANA.delete("/api/secrets/solo_ana")[0], 404)


# =============================================================================== auditoría, estáticos, BD
class AuditAndStaticTests(unittest.TestCase):
    def test_audit_records_actions(self):
        SRV.client().post("/api/login", {"username": "ana", "password": "incorrecta-1"})
        ws = ANA.post("/api/workflows", {"name": "para auditoría", "definition": wf_def(n("A", "hello_world"))})[1]["workflow"]
        ANA.post("/api/workflows/%d/run" % ws["id"])
        s, d = ADMIN.get("/api/audit?limit=500")
        actions = {a["action"] for a in d["audit"]}
        for expected in ("setup", "login", "login.fail", "user.create", "workflow.create", "run.start",
                         "plugin.enable"):
            self.assertIn(expected, actions)
        self.assertEqual(ANA.get("/api/audit")[0], 403)

    def test_static_files_and_traversal(self):
        s, h, body = raw_request(SRV.port, "GET", "/")
        self.assertEqual(s, 200)
        self.assertIn("text/html", h["Content-Type"])
        for bad in ("/static/../chaskiflow/db.py", "/static/..%2fchaskiflow%2fdb.py", "/static/%2e%2e/config.py",
                    "/static//etc/passwd", "/static/nada.exe"):
            self.assertEqual(raw_request(SRV.port, "GET", bad)[0], 404, bad)
        self.assertEqual(raw_request(SRV.port, "POST", "/")[0], 405)

    def test_parallel_requests(self):
        results = []

        def go():
            c = SRV.client()
            c.post("/api/login", {"username": "ana", "password": PASS})
            for _ in range(5):
                results.append(c.get("/api/workflows")[0])

        ths = [threading.Thread(target=go) for _ in range(12)]
        [t.start() for t in ths]
        [t.join() for t in ths]
        self.assertEqual(set(results), {200})
        self.assertEqual(len(results), 60)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_old_schema_is_migrated_without_losing_data(self):
        p = self.tmp / "app.db"
        c = sqlite3.connect(str(p))
        c.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL DEFAULT '', password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'editor',
              active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, created_by INTEGER, updated_at TEXT,
              updated_by INTEGER, last_login TEXT);
            INSERT INTO users(username, password_hash, role, created_at) VALUES('viejo', 'x', 'admin', '2026-01-01');
            CREATE TABLE workflows(id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
              definition TEXT NOT NULL, owner_id INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL, created_by INTEGER, updated_at TEXT NOT NULL, updated_by INTEGER);
            INSERT INTO workflows(name, definition, owner_id, created_at, updated_at) VALUES('mi flujo', '{}', 1, 'a', 'b');
        """)
        c.commit()
        c.close()
        d = dbmod.Database(p)
        self.assertFalse(d.created_new)
        self.assertIsNotNone(d.backup_path)
        self.assertTrue(d.backup_path.exists())
        self.assertIn("must_change_password", dbmod.table_columns(d.conn(), "users"))   # columna agregada
        self.assertIn("team_access", dbmod.table_columns(d.conn(), "workflows"))
        self.assertIn("deleted_at", dbmod.table_columns(d.conn(), "workflows"))
        self.assertEqual(d.one("SELECT username FROM users")["username"], "viejo")      # datos intactos
        self.assertEqual(d.one("SELECT name, team_access FROM workflows")["team_access"], "none")
        self.assertEqual(d.one("PRAGMA user_version")["user_version"], dbmod.SCHEMA_VERSION)
        for t in ("sessions", "runs", "run_nodes", "secrets", "plugin_state", "audit", "settings"):
            self.assertIsNotNone(d.one("SELECT name FROM sqlite_master WHERE name=?", (t,)), t)

    def test_migrate_is_idempotent_and_no_backup_for_new_db(self):
        d = dbmod.Database(self.tmp / "nueva.db")
        self.assertTrue(d.created_new)
        self.assertIsNone(d.backup_path)
        d2 = dbmod.Database(self.tmp / "nueva.db")
        self.assertIsNone(d2.backup_path)  # ya está al día: no hay copia
        self.assertEqual(dbmod.migrate(d2.conn()), dbmod.SCHEMA_VERSION)

    def test_ensure_column(self):
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE t(a)")
        self.assertTrue(dbmod.ensure_column(c, "t", "b", "TEXT DEFAULT 'x'"))
        self.assertFalse(dbmod.ensure_column(c, "t", "b", "TEXT"))
        self.assertEqual(dbmod.table_columns(c, "t"), ["a", "b"])

    def test_password_hash_format(self):
        h = hash_password("abc12345")
        algo, iters, salt, dk = h.split("$")
        self.assertEqual((algo, int(iters) >= 310000), ("pbkdf2_sha256", True))
        self.assertNotEqual(h, hash_password("abc12345"))  # sal distinta cada vez


if __name__ == "__main__":
    unittest.main()
