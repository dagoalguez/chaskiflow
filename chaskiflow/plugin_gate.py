"""Aprobación de plugins por el administrador.

Un plugin encontrado en disco NO se puede usar hasta que un administrador lo habilita.
Al habilitarlo se guarda su hash SHA-256; si el código cambia después, vuelve a quedar
bloqueado ("changed") hasta que se apruebe de nuevo. Los plugins presentes cuando se crea
la base de datos por primera vez se aprueban solos (son los que vienen en la instalación).
"""

from .util import now_iso


class PluginGate:
    def __init__(self, db, registry):
        self.db = db
        self.registry = registry

    # ----- estado ----------------------------------------------------------------
    def _states(self):
        return {r["plugin_id"]: r for r in self.db.all("SELECT * FROM plugin_state")}

    def status_of(self, plugin, states=None):
        if not plugin.ok:
            return "invalid"
        st = (states if states is not None else self._states()).get(plugin.id)
        if not st or not st["enabled"]:
            return "pending" if not st else "disabled"
        return "enabled" if st["approved_hash"] == plugin.hash else "changed"

    def get(self, plugin_id):
        """Plugin utilizable (válido, habilitado y con el hash aprobado) o None."""
        p = self.registry.get(plugin_id)
        if p is not None and self.status_of(p) == "enabled":
            return p
        return None

    def why_unavailable(self, plugin_id):
        p = self.registry.get(plugin_id)
        if p is None:
            bad = [x for x in self.registry.problems if x.id == plugin_id]
            if bad:
                return "la tarea '%s' está inválida: %s" % (plugin_id, "; ".join(bad[0].errors))
            return "la tarea '%s' no está instalada" % plugin_id
        s = self.status_of(p)
        if s == "pending":
            return "la tarea '%s' está pendiente de aprobación por un administrador" % plugin_id
        if s == "disabled":
            return "la tarea '%s' está deshabilitada" % plugin_id
        if s == "changed":
            return ("la tarea '%s' cambió desde que fue aprobada; un administrador debe "
                    "revisarla y habilitarla de nuevo" % plugin_id)
        return "la tarea '%s' no está disponible" % plugin_id

    # ----- catálogo --------------------------------------------------------------
    def catalog(self, admin=False):
        states = self._states()
        out = []
        for entry in self.registry.catalog():
            p = self.registry.get(entry["id"]) if entry["ok"] else None
            status = self.status_of(p, states) if p else "invalid"
            if not admin and status != "enabled":
                continue
            e = dict(entry, status=status)
            if admin:
                st = states.get(entry["id"]) or {}
                e["approved_hash"] = st.get("approved_hash")
            else:
                for k in ("path", "hash", "errors"):
                    e.pop(k, None)
            out.append(e)
        out.sort(key=lambda e: (e["category"], e["name"].lower()))
        return out

    # ----- acciones del administrador -----------------------------------------------
    def enable(self, plugin_id, user):
        p = self.registry.get(plugin_id)
        if p is None:
            raise ValueError("Plugin inexistente o inválido")
        self.db.run(
            "INSERT INTO plugin_state(plugin_id, enabled, approved_hash, updated_at, updated_by) "
            "VALUES(?,1,?,?,?) ON CONFLICT(plugin_id) DO UPDATE SET enabled=1, "
            "approved_hash=excluded.approved_hash, updated_at=excluded.updated_at, "
            "updated_by=excluded.updated_by",
            (plugin_id, p.hash, now_iso(), user["id"] if user else None))
        self.db.audit(user or "sistema", "plugin.enable", "%s %s" % (plugin_id, p.hash[:12]))

    def disable(self, plugin_id, user):
        self.db.run(
            "INSERT INTO plugin_state(plugin_id, enabled, updated_at, updated_by) VALUES(?,0,?,?) "
            "ON CONFLICT(plugin_id) DO UPDATE SET enabled=0, updated_at=excluded.updated_at, "
            "updated_by=excluded.updated_by",
            (plugin_id, now_iso(), user["id"] if user else None))
        self.db.audit(user or "sistema", "plugin.disable", plugin_id)

    def approve_all_present(self):
        n = 0
        for p in list(self.registry.plugins.values()):
            self.enable(p.id, None)
            n += 1
        return n
