"""Manejadores del API REST (JSON). Se registran con @route al importar este módulo."""

import json
import re
from pathlib import Path

from . import __author__, __contributions__, __license__, __repository__, __version__
from . import auth as authmod
from . import g1g_import
from . import plugin_admin as padm
from .access import allows, workflow_level
from .engine import Engine, normalize
from .router import ApiError, route
from . import scheduler as sch
from .runs import RunError, unpack_result
from .util import now_iso

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
MAX_NODES = 500


# ======================================================================== utilidades
def public_wf(wf, level, db, with_definition=False):
    owner = db.one("SELECT username, display_name FROM users WHERE id=?", (wf["owner_id"],)) or {}
    upd = db.one("SELECT username, display_name FROM users WHERE id=?", (wf["updated_by"],)) or {}
    out = {"id": wf["id"], "name": wf["name"], "description": wf["description"],
           "owner_id": wf["owner_id"], "owner": owner.get("display_name") or owner.get("username", ""),
           "team_access": wf["team_access"], "version": wf["version"], "access": level,
           "created_at": wf["created_at"], "updated_at": wf["updated_at"],
           "updated_by": upd.get("display_name") or upd.get("username", ""),
           "deleted_at": wf["deleted_at"]}
    if with_definition:
        out["definition"] = json.loads(wf["definition"])
    return out


def get_wf(req, wf_id, need="view", deleted=False):
    wf = req.db.one("SELECT * FROM workflows WHERE id=?", (wf_id,))
    if not wf or (bool(wf["deleted_at"]) != deleted):
        raise ApiError(404, "Workflow no encontrado")
    level = workflow_level(req.db, req.user, wf)
    if level is None:
        raise ApiError(404, "Workflow no encontrado")
    if not allows(level, need):
        raise ApiError(403, "No tiene permiso para esta acción (requiere '%s')" % need)
    return wf, level


def clean_definition(d):
    if not isinstance(d, dict):
        raise ApiError(400, "La definición debe ser un objeto con 'nodes' y 'edges'")
    nodes, edges, variables = d.get("nodes", []), d.get("edges", []), d.get("variables", {})
    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(variables, dict):
        raise ApiError(400, "Definición inválida: 'nodes' y 'edges' deben ser listas y 'variables' un objeto")
    if len(nodes) > MAX_NODES:
        raise ApiError(400, "Demasiados nodos (máximo %d)" % MAX_NODES)
    out_nodes = []
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not 0 < len(n["id"]) <= 64:
            raise ApiError(400, "Cada nodo necesita un 'id' de texto (hasta 64 caracteres)")
        cfg = n.get("config", {})
        if not isinstance(cfg, dict):
            raise ApiError(400, "La configuración del nodo '%s' debe ser un objeto" % n["id"])
        node = {"id": n["id"], "label": str(n.get("label") or n["id"])[:64],
                "type": str(n.get("type") or "")[:64], "config": cfg,
                "on_error": n.get("on_error", "stop"), "enabled": bool(n.get("enabled", True))}
        if isinstance(n.get("position"), dict):
            node["position"] = {"x": n["position"].get("x", 0), "y": n["position"].get("y", 0)}
        out_nodes.append(node)
    out_edges = []
    for e in edges:
        if not isinstance(e, dict) or not isinstance(e.get("source"), str) \
                or not isinstance(e.get("target"), str):
            raise ApiError(400, "Cada conexión necesita 'source' y 'target'")
        out_edges.append({"source": e["source"], "target": e["target"]})
    return {"nodes": out_nodes, "edges": out_edges, "variables": variables}


def check_name(name, what="nombre"):
    name = (name or "").strip() if isinstance(name, str) else ""
    if not 1 <= len(name) <= 120:
        raise ApiError(400, "El %s debe tener entre 1 y 120 caracteres" % what)
    return name


def validate_definition(req, definition, owner_id):
    engine = req.app.runs.engine_for(owner_id)
    errors, warnings = engine.validate(normalize(dict(definition, name="x")))
    return {"errors": errors, "warnings": warnings, "valid": not errors}


def user_labels(db):
    return {u["id"]: (u["display_name"] or u["username"]) for u in
            db.all("SELECT id, username, display_name FROM users")}


# ======================================================================== público
@route("GET", "/api/health", "public")
def health(req):
    return {"ok": True, "version": __version__, "needs_setup": req.app.auth.count_users() == 0,
            "author": __author__, "contributions": __contributions__, "license": __license__, "repository": __repository__}


@route("POST", "/api/setup", "public")
def setup(req):
    a = req.app.auth
    if a.count_users() > 0:
        raise ApiError(409, "El sistema ya fue configurado")
    b = req.body()
    try:
        u = a.create_user(b.get("username"), b.get("password"), "admin",
                          b.get("display_name") or "")
    except ValueError as e:
        raise ApiError(400, str(e))
    req.db.audit(u, "setup", "Administrador inicial creado")
    token, user = a.login(b["username"], b["password"], req.ip, req.user_agent)
    req.set_session = token
    return {"user": a.public_user(user)}


@route("POST", "/api/login", "public")
def login(req):
    b = req.body()
    try:
        token, user = req.app.auth.login(b.get("username"), b.get("password"), req.ip,
                                         req.user_agent)
    except authmod.AuthError as e:
        req.db.audit(b.get("username") or "?", "login.fail", req.ip)
        raise ApiError(e.status, str(e))
    req.db.audit(user, "login", req.ip)
    req.set_session = token
    return {"user": req.app.auth.public_user(user)}


@route("POST", "/api/logout", "public")
def logout(req):
    req.app.auth.logout(req.token)
    req.clear_session = True
    return {"ok": True}


# ======================================================================== cuenta
@route("GET", "/api/me")
def me(req):
    return {"user": req.app.auth.public_user(req.user)}


@route("POST", "/api/me/password")
def my_password(req):
    b = req.body()
    if not authmod.verify_password(b.get("current") or "", req.user["password_hash"]):
        raise ApiError(400, "La contraseña actual no es correcta")
    try:
        req.app.auth.set_password(req.user["id"], b.get("new"), by=req.user)
    except ValueError as e:
        raise ApiError(400, str(e))
    req.db.audit(req.user, "password.change", "")
    token, _ = req.app.auth.login(req.user["username"], b["new"], req.ip, req.user_agent)
    req.set_session = token
    return {"ok": True}


# ======================================================================== usuarios
@route("GET", "/api/users/directory")
def users_directory(req):
    rows = req.db.all("SELECT id, username, display_name, role FROM users WHERE active=1 "
                      "ORDER BY display_name COLLATE NOCASE")
    return {"users": rows}


@route("GET", "/api/users", "admin")
def users_list(req):
    rows = req.db.all("SELECT * FROM users ORDER BY username COLLATE NOCASE")
    return {"users": [req.app.auth.public_user(u) for u in rows]}


@route("POST", "/api/users", "admin")
def users_create(req):
    b = req.body()
    try:
        u = req.app.auth.create_user(b.get("username"), b.get("password"), b.get("role", "editor"),
                                     b.get("display_name") or "", by=req.user,
                                     must_change=bool(b.get("must_change_password")))
    except ValueError as e:
        raise ApiError(400, str(e))
    req.db.audit(req.user, "user.create", "%s (%s)" % (u["username"], u["role"]))
    return 201, {"user": req.app.auth.public_user(u)}


def _active_admins(db, excluding=None):
    q = "SELECT count(*) AS n FROM users WHERE role='admin' AND active=1"
    if excluding:
        return db.one(q + " AND id<>?", (excluding,))["n"]
    return db.one(q)["n"]


@route("PUT", "/api/users/(?P<id>\\d+)", "admin")
def users_update(req):
    uid = req.pid()
    u = req.db.one("SELECT * FROM users WHERE id=?", (uid,))
    if not u:
        raise ApiError(404, "Usuario no encontrado")
    b = req.body()
    role = b.get("role", u["role"])
    active = 1 if b.get("active", bool(u["active"])) else 0
    if role not in authmod.ROLES:
        raise ApiError(400, "Rol inválido")
    if u["role"] == "admin" and u["active"] and (role != "admin" or not active) \
            and _active_admins(req.db, excluding=uid) == 0:
        raise ApiError(409, "Debe quedar al menos un administrador activo")
    name = str(b.get("display_name", u["display_name"]))[:80]
    req.db.run("UPDATE users SET role=?, active=?, display_name=?, updated_at=?, updated_by=? "
               "WHERE id=?", (role, active, name, now_iso(), req.user["id"], uid))
    if b.get("password"):
        try:
            req.app.auth.set_password(uid, b["password"], by=req.user,
                                      must_change=bool(b.get("must_change_password", True)))
        except ValueError as e:
            raise ApiError(400, str(e))
    if not active:
        req.db.run("DELETE FROM sessions WHERE user_id=?", (uid,))
    req.db.audit(req.user, "user.update", "%s role=%s active=%s" % (u["username"], role, active))
    return {"user": req.app.auth.public_user(req.db.one("SELECT * FROM users WHERE id=?", (uid,)))}


# ======================================================================== plugins
@route("GET", "/api/plugins")
def plugins_list(req):
    return {"plugins": req.app.gate.catalog(admin=req.user["role"] == "admin")}


@route("POST", "/api/plugins/reload", "admin")
def plugins_reload(req):
    req.app.registry.reload()
    req.db.audit(req.user, "plugins.reload", "")
    return {"plugins": req.app.gate.catalog(admin=True)}


@route("POST", "/api/plugins/(?P<pid>[a-z][a-z0-9_]*)/(?P<action>enable|disable)", "admin")
def plugin_toggle(req):
    pid = req.params["pid"]
    try:
        if req.params["action"] == "enable":
            req.app.gate.enable(pid, req.user)
        else:
            req.app.gate.disable(pid, req.user)
    except ValueError as e:
        raise ApiError(404, str(e))
    return {"plugins": req.app.gate.catalog(admin=True)}


@route("POST", "/api/plugins/(?P<pid>[a-z][a-z0-9_]*)/test", "editor")
def plugin_test(req):
    """Botón «Probar conexión»: ejecuta el plugin UNA vez con modo_prueba=true (solo si su plugin.json trae «test»)."""
    pid = req.params["pid"]
    plugin = req.app.registry.get(pid) if hasattr(req.app.registry, "get") else None
    if plugin is None or not getattr(plugin, "manifest", None) or not plugin.manifest.get("test"):
        raise ApiError(404, "Este plugin no tiene prueba de conexión")
    b = req.body()
    given = b.get("config") if isinstance(b.get("config"), dict) else {}
    variables = b.get("variables") if isinstance(b.get("variables"), dict) else {}
    cfg = {}
    for fld in plugin.fields:
        k = fld["key"]
        v = given.get(k)
        if v in (None, ""):
            continue
        if isinstance(v, str) and any(root != "vars" for root in re.findall(r"\{\{\s*([A-Za-z0-9_\u00C0-\u024F ]+?)\s*[.}]", v)):
            continue                                    # referencia a otro paso: no existe en una prueba aislada
        cfg[k] = v
    for fld in plugin.fields:                           # campos obligatorios que no importan para la prueba
        k = fld["key"]
        if fld.get("required") and k not in cfg:
            cfg[k] = {"number": 0, "boolean": False, "json": {}, "any": []}.get(fld.get("type", "string"), "-")
    cfg["modo_prueba"] = True
    wf = {"name": "Prueba de conexión", "variables": variables,
          "nodes": [{"id": "prueba", "label": "Prueba", "type": pid, "config": cfg}], "edges": []}
    engine = req.app.runs.engine_for(req.user["id"])
    errors, _ = engine.validate(normalize(dict(wf)))
    if errors:
        return {"ok": False, "error": "; ".join(errors), "logs": [], "result": None}
    try:
        res = engine.run(wf)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "logs": [], "result": None}
    rec = res.nodes["prueba"]
    result = rec.get("result") if isinstance(rec.get("result"), dict) else None
    logs = [str(x.get("message", "")) for x in (rec.get("logs") or []) if isinstance(x, dict) and x.get("message")]
    ok = rec["status"] == "ok" and (result is None or result.get("ok") is not False)
    return {"ok": ok, "error": rec.get("error") or "", "logs": logs, "result": result,
            "message": (result or {}).get("mensaje") or ("Prueba correcta" if ok else "")}


def _padm(req, fn, *a, **kw):
    if not req.app.cfg.get("allow_plugin_edit", True):
        raise ApiError(403, "La edición de plugins desde la web está desactivada (allow_plugin_edit en config.json)")
    try:
        return fn(req.app.registry, req.app.gate, *a, **kw)
    except padm.PluginAdminError as e:
        raise ApiError(e.status, str(e), errors=e.errors)


@route("GET", "/api/plugins/prompt", "admin")
def plugin_prompt(req):
    f = Path(__file__).resolve().parent.parent / "docs" / "PROMPT_CREAR_PLUGIN.txt"
    if not f.is_file():
        raise ApiError(404, "No se encontró docs/PROMPT_CREAR_PLUGIN.txt")
    return {"prompt": f.read_text(encoding="utf-8-sig")}


@route("POST", "/api/plugins/import", "admin")
def plugin_import(req):
    b = req.body()
    try:
        files = b["files"] if isinstance(b.get("files"), dict) else padm.parse_bundle(b.get("text"))
    except padm.PluginAdminError as e:
        raise ApiError(e.status, str(e))
    pid = _padm(req, padm.create, files, req.user, overwrite=bool(b.get("overwrite")))
    return {"id": pid, "plugins": req.app.gate.catalog(admin=True)}


@route("GET", "/api/plugins/(?P<pid>[a-z][a-z0-9_]*)/files", "admin")
def plugin_files(req):
    try:
        p = padm._plugin(req.app.registry, req.params["pid"])
    except padm.PluginAdminError as e:
        raise ApiError(e.status, str(e))
    return {"files": padm.list_files(p), "used_by": padm.usage(req.db, p.id)}


@route("GET", "/api/plugins/(?P<pid>[a-z][a-z0-9_]*)/file", "admin")
def plugin_file_get(req):
    try:
        p = padm._plugin(req.app.registry, req.params["pid"])
        return {"name": req.qstr("name"), "content": padm.read_file(p, req.qstr("name"))}
    except padm.PluginAdminError as e:
        raise ApiError(e.status, str(e))


@route("PUT", "/api/plugins/(?P<pid>[a-z][a-z0-9_]*)/file", "admin")
def plugin_file_put(req):
    b = req.body()
    if not isinstance(b.get("content"), str):
        raise ApiError(400, "Falta 'content'")
    _padm(req, padm.write_file, req.params["pid"], b.get("name"), b["content"], req.user)
    return {"plugins": req.app.gate.catalog(admin=True)}


@route("POST", "/api/plugins/(?P<pid>[a-z][a-z0-9_]*)/rename", "admin")
def plugin_rename(req):
    b = req.body()
    migrated = _padm(req, padm.rename, req.params["pid"], req.user, name=b.get("name"), new_id=b.get("id"))
    return {"plugins": req.app.gate.catalog(admin=True), "migrated_workflows": migrated}


@route("DELETE", "/api/plugins/(?P<pid>[a-z][a-z0-9_]*)", "admin")
def plugin_delete(req):
    res = _padm(req, padm.delete, req.params["pid"], req.user)
    return dict(res, plugins=req.app.gate.catalog(admin=True))


# ======================================================================== workflows
@route("GET", "/api/workflows")
def wf_list(req):
    out = []
    for wf in req.db.all("SELECT * FROM workflows WHERE deleted_at IS NULL ORDER BY updated_at DESC"):
        level = workflow_level(req.db, req.user, wf)
        if level is None:
            continue
        item = public_wf(wf, level, req.db)
        last = req.db.one("SELECT id, status, started, duration FROM runs WHERE workflow_id=? "
                          "ORDER BY started DESC LIMIT 1", (wf["id"],))
        item["last_run"] = last
        out.append(item)
    return {"workflows": out}


@route("GET", "/api/workflows/trash")
def wf_trash(req):
    out = []
    for wf in req.db.all("SELECT * FROM workflows WHERE deleted_at IS NOT NULL "
                         "ORDER BY deleted_at DESC LIMIT 100"):
        if req.user["role"] == "admin" or wf["owner_id"] == req.user["id"]:
            out.append(public_wf(wf, "edit", req.db))
    return {"workflows": out}


@route("POST", "/api/workflows", "editor")
def wf_create(req):
    b = req.body()
    name = check_name(b.get("name"))
    definition = clean_definition(b.get("definition", {}))
    now = now_iso()
    cur = req.db.run(
        "INSERT INTO workflows(name, description, definition, owner_id, version, created_at, "
        "created_by, updated_at, updated_by) VALUES(?,?,?,?,?,?,?,?,?)",
        (name, str(b.get("description") or "")[:2000], json.dumps(definition, ensure_ascii=False),
         req.user["id"], 1, now, req.user["id"], now, req.user["id"]))
    req.db.audit(req.user, "workflow.create", "%s #%d" % (name, cur.lastrowid))
    wf = req.db.one("SELECT * FROM workflows WHERE id=?", (cur.lastrowid,))
    return 201, {"workflow": public_wf(wf, "edit", req.db, True)}


@route("POST", "/api/workflows/import", "editor")
def wf_import(req):
    b = req.body()
    d = b.get("definition")
    name = check_name(b.get("name") or (d if isinstance(d, dict) else {}).get("name") or "Importado")
    report = None
    if g1g_import.is_g1g(d):
        d, report = g1g_import.convert(d)
    status, out = wf_create_from(req, name, d)
    if report is not None:
        out["import_report"] = report
        req.db.audit(req.user, "workflow.import_g1g", "%s (%d avisos)" % (
            name, len([r for r in report if r["level"] != "info"])))
    return status, out


def wf_create_from(req, name, definition, description=""):
    definition = clean_definition(definition)
    now = now_iso()
    cur = req.db.run(
        "INSERT INTO workflows(name, description, definition, owner_id, version, created_at, "
        "created_by, updated_at, updated_by) VALUES(?,?,?,?,?,?,?,?,?)",
        (name, description, json.dumps(definition, ensure_ascii=False), req.user["id"], 1, now,
         req.user["id"], now, req.user["id"]))
    req.db.audit(req.user, "workflow.create", "%s #%d" % (name, cur.lastrowid))
    wf = req.db.one("SELECT * FROM workflows WHERE id=?", (cur.lastrowid,))
    return 201, {"workflow": public_wf(wf, "edit", req.db, True)}


@route("GET", "/api/workflows/(?P<id>\\d+)")
def wf_get(req):
    wf, level = get_wf(req, req.pid())
    out = public_wf(wf, level, req.db, True)
    if level == "edit" and (req.user["role"] == "admin" or wf["owner_id"] == req.user["id"]):
        out["shares"] = req.db.all("SELECT user_id, permission FROM workflow_shares WHERE workflow_id=?",
                                   (wf["id"],))
    return {"workflow": out}


@route("PUT", "/api/workflows/(?P<id>\\d+)", "editor")
def wf_update(req):
    wf, level = get_wf(req, req.pid(), "edit")
    b = req.body()
    sets, params = [], []
    if "definition" in b:
        sets.append("definition=?")
        params.append(json.dumps(clean_definition(b["definition"]), ensure_ascii=False))
    if "name" in b:
        sets.append("name=?")
        params.append(check_name(b["name"]))
    if "description" in b:
        sets.append("description=?")
        params.append(str(b["description"] or "")[:2000])
    if not sets:
        raise ApiError(400, "No hay nada que actualizar")
    base = b.get("version")
    if base is None or not isinstance(base, int):
        raise ApiError(400, "Falta 'version' (la versión que usted tenía abierta)")
    sets += ["version=version+1", "updated_at=?", "updated_by=?"]
    params += [now_iso(), req.user["id"]]
    cur = req.db.run("UPDATE workflows SET %s WHERE id=? AND version=? AND deleted_at IS NULL"
                     % ", ".join(sets), params + [wf["id"], base])
    if cur.rowcount == 0:
        now = req.db.one("SELECT version, updated_at, updated_by FROM workflows WHERE id=?", (wf["id"],))
        who = user_labels(req.db).get(now["updated_by"], "otra persona")
        raise ApiError(409, "%s modificó este workflow mientras usted lo editaba. Recargue para ver "
                            "la versión más reciente." % who,
                       current_version=now["version"], updated_at=now["updated_at"], updated_by=who)
    fresh = req.db.one("SELECT * FROM workflows WHERE id=?", (wf["id"],))
    return {"workflow": public_wf(fresh, level, req.db, False)}


def _owner_only(req, wf):
    if req.user["role"] != "admin" and wf["owner_id"] != req.user["id"]:
        raise ApiError(403, "Solo el dueño o un administrador puede hacer esto")


@route("DELETE", "/api/workflows/(?P<id>\\d+)", "editor")
def wf_delete(req):
    wf, _ = get_wf(req, req.pid(), "edit")
    _owner_only(req, wf)
    req.db.run("UPDATE workflows SET deleted_at=?, deleted_by=? WHERE id=?",
               (now_iso(), req.user["id"], wf["id"]))
    req.db.audit(req.user, "workflow.delete", "%s #%d" % (wf["name"], wf["id"]))
    return {"ok": True, "undo": "/api/workflows/%d/restore" % wf["id"]}


@route("POST", "/api/workflows/(?P<id>\\d+)/restore", "editor")
def wf_restore(req):
    wf, _ = get_wf(req, req.pid(), "view", deleted=True)
    _owner_only(req, wf)
    req.db.run("UPDATE workflows SET deleted_at=NULL, deleted_by=NULL, updated_at=?, updated_by=? "
               "WHERE id=?", (now_iso(), req.user["id"], wf["id"]))
    req.db.audit(req.user, "workflow.restore", "%s #%d" % (wf["name"], wf["id"]))
    fresh = req.db.one("SELECT * FROM workflows WHERE id=?", (wf["id"],))
    return {"workflow": public_wf(fresh, "edit", req.db)}


ACTIVE = ("queued", "running")


def _purge_workflow(req, wf):
    """Borra para siempre un workflow de la papelera con sus programaciones, accesos y ejecuciones."""
    busy = req.db.one("SELECT COUNT(*) AS n FROM runs WHERE workflow_id=? AND status IN ('queued','running')",
                      (wf["id"],))
    if busy and busy["n"]:
        raise ApiError(409, "Tiene una ejecución en curso; espere a que termine")
    n = req.db.one("SELECT COUNT(*) AS n FROM runs WHERE workflow_id=?", (wf["id"],))["n"]
    req.db.run("DELETE FROM runs WHERE workflow_id=?", (wf["id"],))           # run_nodes cae en cascada
    req.db.run("DELETE FROM schedules WHERE workflow_id=?", (wf["id"],))
    req.db.run("DELETE FROM workflow_shares WHERE workflow_id=?", (wf["id"],))
    req.db.run("DELETE FROM workflows WHERE id=?", (wf["id"],))
    req.db.audit(req.user, "workflow.purge", "%s #%d (%d ejecución(es))" % (wf["name"], wf["id"], n))


@route("DELETE", "/api/workflows/(?P<id>\\d+)/purge", "editor")
def wf_purge(req):
    wf, _ = get_wf(req, req.pid(), "view", deleted=True)
    _owner_only(req, wf)
    _purge_workflow(req, wf)
    return {"ok": True}


@route("POST", "/api/workflows/trash/empty", "editor")
def wf_trash_empty(req):
    done = skipped = 0
    for wf in req.db.all("SELECT * FROM workflows WHERE deleted_at IS NOT NULL"):
        if req.user["role"] != "admin" and wf["owner_id"] != req.user["id"]:
            continue
        try:
            _purge_workflow(req, wf)
            done += 1
        except ApiError:
            skipped += 1
    return {"purged": done, "skipped": skipped}


@route("POST", "/api/workflows/(?P<id>\\d+)/duplicate", "editor")
def wf_duplicate(req):
    wf, _ = get_wf(req, req.pid(), "view")
    return wf_create_from(req, (wf["name"] + " (copia)")[:120], json.loads(wf["definition"]),
                          wf["description"])


@route("GET", "/api/workflows/(?P<id>\\d+)/export")
def wf_export(req):
    wf, _ = get_wf(req, req.pid(), "view")
    d = json.loads(wf["definition"])
    d["name"] = wf["name"]
    d["description"] = wf["description"]
    d["format"] = "chaskiflow-workflow/1"
    return d


@route("PUT", "/api/workflows/(?P<id>\\d+)/shares", "editor")
def wf_shares(req):
    wf, _ = get_wf(req, req.pid(), "edit")
    _owner_only(req, wf)
    b = req.body()
    team = b.get("team_access", wf["team_access"])
    if team not in ("none", "view", "run", "edit"):
        raise ApiError(400, "team_access inválido")
    shares = b.get("shares", [])
    if not isinstance(shares, list):
        raise ApiError(400, "'shares' debe ser una lista")
    clean = []
    for s in shares:
        if not isinstance(s, dict) or s.get("permission") not in ("view", "run", "edit") \
                or not isinstance(s.get("user_id"), int):
            raise ApiError(400, "Cada elemento necesita user_id y permission (view|run|edit)")
        if s["user_id"] == wf["owner_id"]:
            continue
        if not req.db.one("SELECT 1 FROM users WHERE id=? AND active=1", (s["user_id"],)):
            raise ApiError(400, "Usuario %s no existe o está inactivo" % s["user_id"])
        clean.append((wf["id"], s["user_id"], s["permission"]))
    with req.db.tx() as c:
        c.execute("DELETE FROM workflow_shares WHERE workflow_id=?", (wf["id"],))
        c.executemany("INSERT INTO workflow_shares(workflow_id, user_id, permission) VALUES(?,?,?)",
                      clean)
        c.execute("UPDATE workflows SET team_access=? WHERE id=?", (team, wf["id"]))
    req.db.audit(req.user, "workflow.share", "#%d team=%s n=%d" % (wf["id"], team, len(clean)))
    return {"team_access": team, "shares": [{"user_id": u, "permission": p} for _, u, p in clean]}


@route("POST", "/api/workflows/(?P<id>\\d+)/validate")
def wf_validate(req):
    wf, _ = get_wf(req, req.pid(), "view")
    b = req.body()
    definition = clean_definition(b["definition"]) if "definition" in b else json.loads(wf["definition"])
    return validate_definition(req, definition, wf["owner_id"])


@route("POST", "/api/workflows/(?P<id>\\d+)/run")
def wf_run(req):
    wf, _ = get_wf(req, req.pid(), "run")
    b = req.body()
    variables = b.get("variables") or {}
    if not isinstance(variables, dict):
        raise ApiError(400, "'variables' debe ser un objeto")
    only = b.get("only")
    if only is not None and (not isinstance(only, list) or not all(isinstance(x, str) for x in only)):
        raise ApiError(400, "'only' debe ser una lista de ids de nodo")
    try:
        run_id, reused = req.app.runs.start_ex(wf, req.user, variables,
                                               only=set(only) if only is not None else None,
                                               seed_run=b.get("from_run"))
    except RunError as e:
        raise ApiError(e.status, str(e))
    req.db.audit(req.user, "run.start", "%s #%d %s%s" % (wf["name"], wf["id"], run_id,
                                                         " (parcial: %d paso(s))" % len(only) if only else ""))
    return 202, {"run_id": run_id, "reused": reused}


@route("GET", "/api/workflows/(?P<id>\\d+)/runs")
def wf_runs(req):
    wf, _ = get_wf(req, req.pid(), "view")
    rows = req.db.all("SELECT id, status, started, finished, duration, trigger, started_by, error "
                      "FROM runs WHERE workflow_id=? ORDER BY started DESC LIMIT ?",
                      (wf["id"], req.qint("limit", 30, 1, 200)))
    names = user_labels(req.db)
    for r in rows:
        r["started_by_name"] = names.get(r["started_by"], "")
    return {"runs": rows}


# ======================================================================== ejecuciones
def get_run(req, run_id, need="view"):
    r = req.db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not r:
        raise ApiError(404, "Ejecución no encontrada")
    wf = req.db.one("SELECT * FROM workflows WHERE id=?", (r["workflow_id"],))
    level = workflow_level(req.db, req.user, wf) if wf else (
        "view" if req.user["role"] == "admin" or r["started_by"] == req.user["id"] else None)
    if level is None:
        raise ApiError(404, "Ejecución no encontrada")
    if not allows(level, need):
        raise ApiError(403, "No tiene permiso para esta acción")
    return r


@route("GET", "/api/runs")
def runs_recent(req):
    rows = req.db.all("SELECT id, workflow_id, workflow_name, status, started, duration, started_by "
                      "FROM runs ORDER BY started DESC LIMIT 300")
    names, out, cache = user_labels(req.db), [], {}
    for r in rows:
        wid = r["workflow_id"]
        if wid not in cache:
            wf = req.db.one("SELECT * FROM workflows WHERE id=?", (wid,))
            cache[wid] = workflow_level(req.db, req.user, wf) if wf else (
                "view" if req.user["role"] == "admin" else None)
        if cache[wid]:
            r["started_by_name"] = names.get(r["started_by"], "")
            out.append(r)
        if len(out) >= req.qint("limit", 30, 1, 100):
            break
    return {"runs": out}


@route("GET", "/api/runs/(?P<rid>[0-9A-Za-z-]+)")
def run_get(req):
    get_run(req, req.params["rid"])
    return {"run": req.app.runs.run_detail(req.params["rid"])}


@route("GET", "/api/runs/(?P<rid>[0-9A-Za-z-]+)/events")
def run_events(req):
    get_run(req, req.params["rid"])
    return req.app.runs.events(req.params["rid"], req.qint("after", 0, 0, 10 ** 9))


@route("GET", "/api/runs/(?P<rid>[0-9A-Za-z-]+)/nodes/(?P<nid>[^/]+)")
def run_node(req):
    get_run(req, req.params["rid"])
    n = req.db.one("SELECT * FROM run_nodes WHERE run_id=? AND node_id=?",
                   (req.params["rid"], req.params["nid"]))
    if not n:
        raise ApiError(404, "Nodo no encontrado en esa ejecución")
    n["config"] = json.loads(n["config"]) if n["config"] else None
    n["logs"] = json.loads(n["logs"]) if n["logs"] else []
    n["result"] = unpack_result(n.pop("result"))
    return {"node": n}


@route("POST", "/api/runs/(?P<rid>[0-9A-Za-z-]+)/cancel")
def run_cancel(req):
    r = get_run(req, req.params["rid"], "run")
    try:
        req.app.runs.cancel(r["id"])
    except RunError as e:
        raise ApiError(e.status, str(e))
    req.db.audit(req.user, "run.cancel", r["id"])
    return {"ok": True}


def _delete_run_rows(req, rid):
    req.db.run("DELETE FROM runs WHERE id=?", (rid,))
    req.app.runs.forget(rid)


@route("DELETE", "/api/runs/(?P<rid>[0-9A-Za-z-]+)", "editor")
def run_delete(req):
    r = get_run(req, req.params["rid"], "edit")
    if r["status"] in ACTIVE:
        raise ApiError(409, "La ejecución sigue en curso: deténgala primero")
    _delete_run_rows(req, r["id"])
    req.db.audit(req.user, "run.delete", "%s (%s)" % (r["id"], r["workflow_name"] or ""))
    return {"ok": True}


@route("POST", "/api/workflows/(?P<id>\\d+)/runs/clear", "editor")
def wf_runs_clear(req):
    wf, _ = get_wf(req, req.pid(), "edit")
    keep = max(0, min(int(req.body().get("keep") or 0), 1000))
    rows = req.db.all("SELECT id FROM runs WHERE workflow_id=? AND status NOT IN ('queued','running') "
                      "ORDER BY started DESC", (wf["id"],))
    ids = [r["id"] for r in rows[keep:]]
    for rid in ids:
        _delete_run_rows(req, rid)
    req.db.audit(req.user, "runs.clear", "%s #%d (%d ejecución(es), se conservan %d)" % (wf["name"], wf["id"], len(ids), keep))
    return {"deleted": len(ids)}


# ======================================================================== claves (secretos)
@route("GET", "/api/secrets")
def secrets_list(req):
    rows = req.db.all("SELECT name, owner_id, updated_at, created_at FROM secrets "
                      "WHERE owner_id=? OR owner_id IS NULL ORDER BY name", (req.user["id"],))
    return {"secrets": [{"name": r["name"], "scope": "global" if r["owner_id"] is None else "me",
                         "updated_at": r["updated_at"] or r["created_at"]} for r in rows]}


@route("PUT", "/api/secrets/(?P<name>[^/]+)", "editor")
def secrets_put(req):
    name = req.params["name"]
    if not NAME_RE.match(name):
        raise ApiError(400, "Nombre inválido (letras, números y _)")
    b = req.body()
    value = b.get("value")
    if not isinstance(value, str) or value == "" or len(value) > 10000:
        raise ApiError(400, "Falta el valor de la clave")
    scope = b.get("scope", "me")
    if scope not in ("me", "global"):
        raise ApiError(400, "scope debe ser 'me' o 'global'")
    if scope == "global" and req.user["role"] != "admin":
        raise ApiError(403, "Solo un administrador puede definir claves globales")
    owner = req.user["id"] if scope == "me" else None
    now = now_iso()
    existing = req.db.one("SELECT id FROM secrets WHERE COALESCE(owner_id,0)=COALESCE(?,0) AND name=?",
                          (owner, name))
    if existing:
        req.db.run("UPDATE secrets SET value=?, updated_at=?, updated_by=? WHERE id=?",
                   (value, now, req.user["id"], existing["id"]))
    else:
        req.db.run("INSERT INTO secrets(owner_id, name, value, created_at, created_by) "
                   "VALUES(?,?,?,?,?)", (owner, name, value, now, req.user["id"]))
    req.db.audit(req.user, "secret.set", "%s (%s)" % (name, scope))  # nunca se registra el valor
    return {"ok": True}


@route("DELETE", "/api/secrets/(?P<name>[^/]+)", "editor")
def secrets_delete(req):
    scope = req.qstr("scope", "me")
    if scope == "global" and req.user["role"] != "admin":
        raise ApiError(403, "Solo un administrador puede borrar claves globales")
    owner = req.user["id"] if scope == "me" else None
    cur = req.db.run("DELETE FROM secrets WHERE COALESCE(owner_id,0)=COALESCE(?,0) AND name=?",
                     (owner, req.params["name"]))
    if cur.rowcount == 0:
        raise ApiError(404, "Clave no encontrada")
    req.db.audit(req.user, "secret.delete", "%s (%s)" % (req.params["name"], scope))
    return {"ok": True}


# ======================================================================== auditoría
@route("GET", "/api/audit", "admin")
def audit_list(req):
    return {"audit": req.db.all("SELECT * FROM audit ORDER BY id DESC LIMIT ?",
                                (req.qint("limit", 200, 1, 1000),))}


# ======================================================================== programación horaria
def _sched_public(s, db, names=None):
    last = db.one("SELECT status, finished, duration FROM runs WHERE id=?", (s["last_run_id"],)) if s["last_run_id"] else None
    from datetime import datetime
    return {"id": s["id"], "workflow_id": s["workflow_id"], "name": s["name"], "kind": s["kind"], "time": s["time"],
            "days": [int(d) for d in s["days"].split(",") if d != ""], "every_minutes": s["every_minutes"],
            "enabled": bool(s["enabled"]), "variables": json.loads(s["variables"] or "{}"),
            "grace_minutes": s["grace_minutes"], "description": sch.describe(s),
            "next_run": datetime.fromtimestamp(s["next_run"]).isoformat(timespec="minutes") if s["next_run"] else None,
            "last_fire": datetime.fromtimestamp(s["last_fire"]).isoformat(timespec="seconds") if s["last_fire"] else None,
            "last_status": s["last_status"], "last_message": s["last_message"], "last_run_id": s["last_run_id"],
            "last_run_status": last["status"] if last else None,
            "created_by": (names or {}).get(s["created_by"], "")}


def _get_schedule(req, sid):
    s = req.db.one("SELECT * FROM schedules WHERE id=?", (sid,))
    if not s:
        raise ApiError(404, "Programación no encontrada")
    wf = req.db.one("SELECT * FROM workflows WHERE id=? AND deleted_at IS NULL", (s["workflow_id"],))
    level = workflow_level(req.db, req.user, wf) if wf else None
    if level is None:
        raise ApiError(404, "Programación no encontrada")
    mine = s["created_by"] == req.user["id"] or req.user["role"] == "admin" or level == "edit"
    if not mine or req.user["role"] == "viewer":
        raise ApiError(403, "Solo quien la creó, el dueño del workflow o un administrador puede modificarla")
    return s, wf


@route("GET", "/api/schedules")
def schedules_all(req):
    out, names, cache = [], user_labels(req.db), {}
    for s in req.db.all("SELECT * FROM schedules ORDER BY next_run IS NULL, next_run"):
        wid = s["workflow_id"]
        if wid not in cache:
            wf = req.db.one("SELECT * FROM workflows WHERE id=? AND deleted_at IS NULL", (wid,))
            cache[wid] = (wf, workflow_level(req.db, req.user, wf) if wf else None)
        wf, level = cache[wid]
        if level:
            d = _sched_public(s, req.db, names)
            d["workflow_name"] = wf["name"]
            out.append(d)
    return {"schedules": out}


@route("GET", "/api/workflows/(?P<id>\\d+)/schedules")
def wf_schedules(req):
    wf, _ = get_wf(req, req.pid(), "view")
    names = user_labels(req.db)
    return {"schedules": [_sched_public(s, req.db, names) for s in
                          req.db.all("SELECT * FROM schedules WHERE workflow_id=? ORDER BY id", (wf["id"],))]}


@route("POST", "/api/workflows/(?P<id>\\d+)/schedules", "editor")
def wf_schedule_create(req):
    wf, _ = get_wf(req, req.pid(), "run")
    b = req.body()
    name = str(b.get("name") or "").strip()[:80] or "Programación"
    try:
        f = sch.clean_schedule(b)
        nxt = sch.compute_next(f["kind"], f["time"], f["days"], f["every_minutes"], __import__("time").time())
    except sch.ScheduleError as e:
        raise ApiError(400, str(e))
    enabled = 1 if b.get("enabled", True) else 0
    cur = req.db.run(
        "INSERT INTO schedules(workflow_id, name, kind, time, days, every_minutes, enabled, variables, grace_minutes, "
        "next_run, created_by, created_at, updated_by, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (wf["id"], name, f["kind"], f["time"], f["days"], f["every_minutes"], enabled, f["variables"],
         f["grace_minutes"], nxt if enabled else None, req.user["id"], now_iso(), req.user["id"], now_iso()))
    req.db.audit(req.user, "schedule.create", "%s en %s #%d" % (name, wf["name"], wf["id"]))
    s = req.db.one("SELECT * FROM schedules WHERE id=?", (cur.lastrowid,))
    return 201, {"schedule": _sched_public(s, req.db, user_labels(req.db))}


@route("PUT", "/api/schedules/(?P<id>\\d+)", "editor")
def schedule_update(req):
    s, wf = _get_schedule(req, req.pid())
    b = req.body()
    merged = {"kind": s["kind"], "time": s["time"], "days": s["days"], "every_minutes": s["every_minutes"],
              "grace_minutes": s["grace_minutes"], "variables": json.loads(s["variables"] or "{}")}
    merged.update({k: v for k, v in b.items() if k in merged})
    try:
        f = sch.clean_schedule(merged)
        enabled = 1 if b.get("enabled", bool(s["enabled"])) else 0
        nxt = sch.compute_next(f["kind"], f["time"], f["days"], f["every_minutes"], __import__("time").time()) if enabled else None
    except sch.ScheduleError as e:
        raise ApiError(400, str(e))
    name = str(b.get("name", s["name"]) or "").strip()[:80] or "Programación"
    req.db.run("UPDATE schedules SET name=?, kind=?, time=?, days=?, every_minutes=?, enabled=?, variables=?, "
               "grace_minutes=?, next_run=?, updated_by=?, updated_at=? WHERE id=?",
               (name, f["kind"], f["time"], f["days"], f["every_minutes"], enabled, f["variables"], f["grace_minutes"],
                nxt, req.user["id"], now_iso(), s["id"]))
    req.db.audit(req.user, "schedule.update", "%s #%d enabled=%d" % (name, s["id"], enabled))
    s = req.db.one("SELECT * FROM schedules WHERE id=?", (s["id"],))
    return {"schedule": _sched_public(s, req.db, user_labels(req.db))}


@route("DELETE", "/api/schedules/(?P<id>\\d+)", "editor")
def schedule_delete(req):
    s, wf = _get_schedule(req, req.pid())
    req.db.run("DELETE FROM schedules WHERE id=?", (s["id"],))
    req.db.audit(req.user, "schedule.delete", "%s #%d" % (s["name"], s["id"]))
    return {"ok": True}
