"""Administración de plugins desde la interfaz: editar archivos, renombrar, cambiar id y eliminar.

Solo la usan rutas de administrador. Todo cambio se valida en una copia temporal ANTES de tocar el
plugin real (manifiesto válido, código que compila). Eliminar mueve la carpeta a «_eliminados/» (el
cargador ignora las carpetas que empiezan con «_»), de modo que se puede recuperar a mano.
"""

import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from .plugin_loader import ID_RE, MANIFEST, load_plugin
from .util import now_iso

TEXT_EXT = {".py", ".json", ".md", ".txt", ".js", ".css", ".html", ".csv"}
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,63}$")
MAX_FILE = 512 * 1024
TRASH = "_eliminados"


class PluginAdminError(Exception):
    def __init__(self, message, status=400, errors=None):
        super().__init__(message)
        self.status = status
        self.errors = errors or []


def _plugin(registry, pid):
    p = registry.get(pid)
    if p is None:
        for bad in registry.problems:
            if bad.id == pid:
                return bad
        raise PluginAdminError("Plugin inexistente", 404)
    return p


def _check_name(name):
    if not isinstance(name, str) or not NAME_RE.match(name) or name.startswith("."):
        raise PluginAdminError("Nombre de archivo inválido (letras, números, _ . -; sin carpetas)")
    if Path(name).suffix.lower() not in TEXT_EXT:
        raise PluginAdminError("Solo se permiten archivos de texto: %s" % " ".join(sorted(TEXT_EXT)))
    return name


def list_files(p):
    out = []
    for f in sorted(p.path.iterdir()):
        if f.is_file() and f.suffix.lower() in TEXT_EXT and not f.name.startswith("."):
            out.append({"name": f.name, "size": f.stat().st_size})
    return out


def read_file(p, name):
    f = p.path / _check_name(name)
    if not f.is_file():
        raise PluginAdminError("Archivo inexistente", 404)
    if f.stat().st_size > MAX_FILE:
        raise PluginAdminError("Archivo demasiado grande para editarlo aquí")
    try:
        return f.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise PluginAdminError("El archivo no es texto UTF-8")


def _validate_copy(p, name, content, expected_id):
    """Aplica el cambio en una copia temporal y devuelve la lista de errores (vacía = válido)."""
    errors = []
    if "\x00" in content:
        return ["el contenido tiene caracteres nulos"]
    if len(content.encode("utf-8")) > MAX_FILE:
        return ["archivo demasiado grande (máx. %d KB)" % (MAX_FILE // 1024)]
    if name.endswith(".py"):
        try:
            compile(content, name, "exec")
        except SyntaxError as e:
            return ["%s no compila: línea %s: %s" % (name, e.lineno, e.msg)]
    if name == MANIFEST:
        try:
            m = json.loads(content)
        except ValueError as e:
            return ["plugin.json no es JSON válido: %s" % e]
        if not isinstance(m, dict) or m.get("id") != expected_id:
            return ["el 'id' no se cambia aquí: use «Renombrar → ID» para migrar también los workflows"]
    tmp = Path(tempfile.mkdtemp(prefix="cf_plug_"))
    try:
        dst = tmp / p.path.name
        shutil.copytree(str(p.path), str(dst), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (dst / name).write_text(content, encoding="utf-8")
        chk = load_plugin(dst)
        errors.extend(chk.errors)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return errors


def write_file(registry, gate, pid, name, content, user):
    """Guarda un archivo del plugin (nuevo o existente). Devuelve el estado final."""
    p = _plugin(registry, pid)
    name = _check_name(name)
    content = content.replace("\r\n", "\n")
    errors = _validate_copy(p, name, content, p.id)
    if errors:
        raise PluginAdminError("No se guardó: " + "; ".join(errors), errors=errors)
    was_enabled = gate.status_of(p) == "enabled" if p.ok else False
    target = p.path / name
    tmp = target.with_name(target.name + ".tmp_edit")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(target))
    registry.reload()
    if was_enabled and registry.get(pid) is not None:
        gate.enable(pid, user)          # el administrador que edita es quien aprueba el nuevo contenido
    gate.db.audit(user, "plugin.edit", "%s/%s" % (pid, name))


def _migrate_workflows(db, old, new):
    n = 0
    for wf in db.all("SELECT id, definition, version FROM workflows"):
        try:
            d = json.loads(wf["definition"])
        except ValueError:
            continue
        changed = False
        for node in d.get("nodes", []) if isinstance(d, dict) else []:
            if isinstance(node, dict) and node.get("type") == old:
                node["type"] = new
                changed = True
        if changed:
            db.run("UPDATE workflows SET definition=?, version=version+1, updated_at=? WHERE id=?",
                   (json.dumps(d, ensure_ascii=False), now_iso(), wf["id"]))
            n += 1
    return n


def usage(db, pid):
    names = []
    for wf in db.all("SELECT name, definition FROM workflows WHERE deleted_at IS NULL"):
        try:
            d = json.loads(wf["definition"])
        except ValueError:
            continue
        if any(isinstance(n, dict) and n.get("type") == pid for n in (d.get("nodes") or [])):
            names.append(wf["name"])
    return names


def rename(registry, gate, pid, user, name=None, new_id=None):
    """Cambia el nombre visible y/o el id. El id nuevo mueve la carpeta y migra los workflows."""
    p = _plugin(registry, pid)
    if not p.ok:
        raise PluginAdminError("Corrija primero los errores del plugin")
    db = gate.db
    migrated = 0
    if name is not None:
        name = str(name).strip()
        if not name or len(name) > 80:
            raise PluginAdminError("El nombre debe tener entre 1 y 80 caracteres")
        m = dict(p.manifest)
        m["name"] = name
        write_file(registry, gate, pid, MANIFEST, json.dumps(m, ensure_ascii=False, indent=2) + "\n", user)
        p = _plugin(registry, pid)
    if new_id and new_id != pid:
        if not ID_RE.match(new_id):
            raise PluginAdminError("ID inválido: minúsculas, números y _ (ej. 'enviar_correo')")
        if registry.get(new_id) is not None or any(b.id == new_id for b in registry.problems):
            raise PluginAdminError("Ya existe un plugin con el id '%s'" % new_id, 409)
        dest = p.path.parent / new_id
        if dest.exists():
            raise PluginAdminError("Ya existe la carpeta '%s'" % new_id, 409)
        was_enabled = gate.status_of(p) == "enabled"
        m = dict(p.manifest)
        m["id"] = new_id
        tmp = p.path.with_name(p.path.name + ".tmp_edit.json")
        tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(p.path / MANIFEST))
        os.rename(str(p.path), str(dest))
        migrated = _migrate_workflows(db, pid, new_id)
        db.run("DELETE FROM plugin_state WHERE plugin_id=?", (pid,))
        registry.reload()
        if was_enabled and registry.get(new_id) is not None:
            gate.enable(new_id, user)
        db.audit(user, "plugin.rename", "%s -> %s (%d workflows)" % (pid, new_id, migrated))
    elif name is not None:
        db.audit(user, "plugin.rename", "%s nombre='%s'" % (pid, name))
    return migrated


def delete(registry, gate, pid, user):
    """Mueve el plugin a «_eliminados/». Devuelve la ruta nueva y los workflows que lo usaban."""
    p = _plugin(registry, pid)
    used = usage(gate.db, pid)
    trash = p.path.parent / TRASH
    trash.mkdir(exist_ok=True)
    dest = trash / ("%s_%s" % (p.path.name, time.strftime("%Y%m%d-%H%M%S")))
    shutil.move(str(p.path), str(dest))
    gate.db.run("DELETE FROM plugin_state WHERE plugin_id=?", (pid,))
    registry.reload()
    gate.db.audit(user, "plugin.delete", "%s -> %s (usado en %d workflows)" % (pid, dest.name, len(used)))
    return {"moved_to": str(dest), "used_by": used}
