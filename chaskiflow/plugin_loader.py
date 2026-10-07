"""Descubrimiento y validación de plugins.

Un plugin es una carpeta con plugin.json (y task.py si kind = "python").
Un plugin inválido NUNCA tumba el sistema: se lista con sus errores y no se puede usar.
"""

import hashlib
import importlib.util
import json
import re
from pathlib import Path

from .schema import validate_fields

MANIFEST = "plugin.json"
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.\-]+)?$")
KINDS = ("python", "http")


class Plugin:
    def __init__(self, path):
        self.path = Path(path)
        self.manifest = {}
        self.errors = []
        self.hash = ""

    # --- atajos del manifiesto -------------------------------------------------
    @property
    def id(self):
        return self.manifest.get("id") or self.path.name

    @property
    def kind(self):
        return self.manifest.get("kind", "python")

    @property
    def fields(self):
        return self.manifest.get("fields") or []

    @property
    def outputs(self):
        return self.manifest.get("outputs") or []

    @property
    def secrets(self):
        return self.manifest.get("secrets") or []

    @property
    def wants_inputs(self):
        return bool(self.manifest.get("inputs"))

    @property
    def timeout(self):
        return float(self.manifest.get("timeout") or 300)

    @property
    def ok(self):
        return not self.errors

    def catalog_entry(self):
        m = self.manifest
        return {
            "id": self.id,
            "name": m.get("name", self.id),
            "version": m.get("version", ""),
            "author": m.get("author", ""),
            "description": m.get("description", ""),
            "icon": m.get("icon", "🧩"),
            "category": m.get("category", "General"),
            "kind": self.kind,
            "fields": self.fields,
            "outputs": self.outputs,
            "secrets": self.secrets,
            "inputs": self.wants_inputs,
            "timeout": self.timeout,
            "hash": self.hash,
            "ok": self.ok,
            "errors": list(self.errors),
            "path": str(self.path),
        }


def compute_hash(path):
    """SHA-256 del contenido del plugin (rutas ordenadas). Cambia si se edita cualquier archivo."""
    h = hashlib.sha256()
    root = Path(path)
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = f.relative_to(root).as_posix()
        if "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        h.update(rel.encode("utf-8") + b"\0")
        h.update(f.read_bytes() + b"\0")
    return h.hexdigest()


def _check_manifest(p):
    m = p.manifest
    if not isinstance(m, dict):
        p.errors.append("plugin.json debe ser un objeto JSON")
        return
    pid = m.get("id")
    if not isinstance(pid, str) or not ID_RE.match(pid):
        p.errors.append("'id' inválido: use minúsculas, números y _ (ej. 'enviar_correo')")
    if not m.get("name"):
        p.errors.append("falta 'name'")
    if not isinstance(m.get("version"), str) or not VERSION_RE.match(m.get("version", "")):
        p.errors.append("'version' debe ser tipo 1.0.0")
    kind = m.get("kind", "python")
    if kind not in KINDS:
        p.errors.append("'kind' debe ser uno de: %s" % ", ".join(KINDS))
    p.errors.extend(validate_fields(m.get("fields", [])))
    outs = m.get("outputs", [])
    if not isinstance(outs, list) or any(not isinstance(o, dict) or "key" not in o for o in outs):
        p.errors.append("'outputs' debe ser una lista de objetos con 'key'")
    secrets = m.get("secrets", [])
    if not isinstance(secrets, list) or any(not isinstance(s, str) or not s.isidentifier()
                                            for s in secrets):
        p.errors.append("'secrets' debe ser una lista de nombres (letras, números, _)")
    t = m.get("timeout", 300)
    if not isinstance(t, (int, float)) or isinstance(t, bool) or not 0 < t <= 86400:
        p.errors.append("'timeout' debe estar entre 1 y 86400 segundos")
    if kind == "python":
        entry = m.get("entry", "task.py")
        if not isinstance(entry, str) or "/" in entry or "\\" in entry or ".." in entry:
            p.errors.append("'entry' debe ser un archivo dentro de la carpeta del plugin")
        elif not (p.path / entry).is_file():
            p.errors.append("no existe el archivo '%s'" % entry)
    elif kind == "http":
        h = m.get("http")
        if not isinstance(h, dict) or not h.get("url"):
            p.errors.append("kind 'http' necesita un bloque 'http' con 'url'")
    req = m.get("requires", [])
    if not isinstance(req, list) or any(not isinstance(r, str) for r in req):
        p.errors.append("'requires' debe ser una lista de nombres de módulos Python")
    else:
        for mod in req:
            try:
                found = importlib.util.find_spec(mod) is not None
            except (ImportError, ValueError):
                found = False
            if not found:
                p.errors.append("falta el módulo Python '%s' (instálalo con: pip install %s)"
                                % (mod, mod))


def load_plugin(path):
    """Carga un plugin desde su carpeta. Nunca lanza excepciones."""
    p = Plugin(path)
    mf = p.path / MANIFEST
    try:
        p.hash = compute_hash(p.path)
    except Exception as e:  # pragma: no cover
        p.errors.append("no se pudo leer la carpeta: %s" % e)
        return p
    if not mf.is_file():
        p.errors.append("falta %s" % MANIFEST)
        return p
    try:
        p.manifest = json.loads(mf.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        p.errors.append("%s ilegible: %s" % (MANIFEST, e))
        return p
    _check_manifest(p)
    return p


class PluginRegistry:
    """Conjunto de plugins descubiertos en una o más carpetas."""

    def __init__(self, dirs):
        self.dirs = [Path(d) for d in ([dirs] if isinstance(dirs, (str, Path)) else dirs)]
        self.plugins = {}   # id -> Plugin (válidos)
        self.problems = []  # Plugin con errores (incluye ids duplicados)
        self.reload()

    def reload(self):
        plugins, problems = {}, []
        for d in self.dirs:
            if not d.is_dir():
                continue
            for sub in sorted(d.iterdir()):
                if not sub.is_dir() or sub.name.startswith(("_", ".")):
                    continue
                p = load_plugin(sub)
                if p.ok and p.id in plugins:
                    p.errors.append("id duplicado '%s' (ya existe en %s)"
                                    % (p.id, plugins[p.id].path))
                if p.ok:
                    plugins[p.id] = p
                else:
                    problems.append(p)
        self.plugins, self.problems = plugins, problems
        return self

    def get(self, plugin_id):
        return self.plugins.get(plugin_id)

    def catalog(self):
        entries = [p.catalog_entry() for p in self.plugins.values()]
        entries += [p.catalog_entry() for p in self.problems]
        return entries
