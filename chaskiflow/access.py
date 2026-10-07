"""Permisos sobre workflows.

Niveles (de menor a mayor): view < run < edit.
  * admin: edit sobre todo.   * dueño: edit.
  * Otros: el mayor entre team_access del workflow y su permiso personal en workflow_shares.
  * El rol 'viewer' nunca pasa de 'view', aunque le compartan con 'edit'.
"""

LEVELS = {"view": 1, "run": 2, "edit": 3}


def best(a, b):
    return a if LEVELS.get(a, 0) >= LEVELS.get(b, 0) else b


def workflow_level(db, user, wf):
    """Devuelve 'edit' | 'run' | 'view' | None para este usuario sobre este workflow."""
    if user["role"] == "admin" or wf["owner_id"] == user["id"]:
        return "edit" if user["role"] != "viewer" else "view"
    level = wf.get("team_access") if wf.get("team_access") in LEVELS else None
    share = db.one("SELECT permission FROM workflow_shares WHERE workflow_id=? AND user_id=?",
                   (wf["id"], user["id"]))
    if share:
        level = best(level, share["permission"]) if level else share["permission"]
    if level and user["role"] == "viewer":
        level = "view"
    return level


def allows(level, needed):
    return LEVELS.get(level, 0) >= LEVELS[needed]
