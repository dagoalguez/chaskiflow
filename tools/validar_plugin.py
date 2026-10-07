#!/usr/bin/env python3
"""Valida una carpeta de plugin antes de entregarla al administrador.

    python tools/validar_plugin.py plugins/mi_plugin
    python tools/validar_plugin.py plugins/mi_plugin --probar     (ejecuta run() con los valores por defecto)

Revisa: manifiesto, campos, que task.py compile y tenga run(config, ctx), que todos los archivos
sean texto, y que solo importe librería estándar. Código de salida 0 = sin errores.
"""

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chaskiflow.plugin_loader import load_plugin  # noqa: E402

TEXT_EXT = {".py", ".json", ".md", ".txt", ".js", ".css", ".html", ".csv", ".yml", ".yaml"}


def stdlib_names():
    names = getattr(sys, "stdlib_module_names", None)
    return set(names) if names else None


def check(path, probar=False, config=None):
    """Devuelve (errores, avisos)."""
    path = Path(path).resolve()
    errors, warns = [], []
    if not path.is_dir():
        return ["no es una carpeta: %s" % path], warns
    p = load_plugin(path)
    errors.extend(p.errors)
    for f in sorted(x for x in path.rglob("*") if x.is_file()):
        rel = f.relative_to(path).as_posix()
        if "__pycache__" in rel:
            continue
        if f.suffix.lower() not in TEXT_EXT:
            errors.append("archivo no permitido (solo texto): %s" % rel)
            continue
        try:
            f.read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError:
            errors.append("%s no es UTF-8" % rel)
    m = p.manifest if isinstance(p.manifest, dict) else {}
    if m.get("kind", "python") == "python":
        entry = path / m.get("entry", "task.py")
        if entry.is_file():
            try:
                tree = ast.parse(entry.read_text(encoding="utf-8-sig"), filename=str(entry))
            except SyntaxError as e:
                errors.append("%s no compila: línea %s: %s" % (entry.name, e.lineno, e.msg))
                tree = None
            if tree is not None:
                fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run"]
                if not fn:
                    errors.append("%s no define run(config, ctx)" % entry.name)
                elif len(fn[0].args.args) < 2:
                    errors.append("run() debe recibir (config, ctx)")
                std, local = stdlib_names(), {x.stem for x in path.glob("*.py")}
                for n in ast.walk(tree):
                    mods = []
                    if isinstance(n, ast.Import):
                        mods = [a.name.split(".")[0] for a in n.names]
                    elif isinstance(n, ast.ImportFrom) and not n.level and n.module:
                        mods = [n.module.split(".")[0]]
                    for mod in mods:
                        if std is not None and mod not in std and mod not in local:
                            (warns if mod in (m.get("requires") or []) else errors).append(
                                "importa '%s', que no es de la librería estándar (en el entorno "
                                "institucional pip no funciona)%s" % (
                                    mod, "; declarado en 'requires'" if mod in (m.get("requires") or [])
                                    else ""))
    if not m.get("description"):
        warns.append("falta 'description'")
    if not m.get("outputs"):
        warns.append("sin 'outputs': los demás pasos no sabrán qué campos pueden usar")
    if (path / "plugin.json").is_file() and not errors and probar:
        for msg in _probar(path, p, config or {}):
            (warns if msg.startswith("no se pudo probar") else errors).append(msg)
    return errors, warns


def _probar(path, p, config):
    from chaskiflow.engine import Engine, WorkflowError
    from chaskiflow.plugin_loader import PluginRegistry
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        reg = PluginRegistry([])
        reg.plugins = {p.id: p}
        eng = Engine(reg, workdir_root=tmp)
        try:
            res = eng.run({"name": "prueba", "nodes": [{"id": "A", "label": "A", "type": p.id,
                                                        "config": config}], "edges": []})
        except WorkflowError as e:
            return ["no se pudo probar: %s (pase valores con --config '{\"campo\": \"valor\"}')" % e]
        node = res.nodes["A"]
        if node["status"] != "ok":
            return ["la ejecución de prueba falló: %s" % (node.get("error") or node["status"])]
        try:
            json.dumps(node["result"])
        except TypeError as e:
            return ["el resultado no es JSON: %s" % e]
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(description="Valida un plugin de ChaskiFlow")
    ap.add_argument("carpeta")
    ap.add_argument("--probar", action="store_true", help="ejecuta el plugin con valores por defecto")
    ap.add_argument("--config", default="{}", help="JSON con valores de campos para --probar")
    a = ap.parse_args(argv)
    errors, warns = check(a.carpeta, a.probar, json.loads(a.config))
    for w in warns:
        print("AVISO: %s" % w)
    for e in errors:
        print("ERROR: %s" % e)
    print("%s: %d error(es), %d aviso(s)" % (Path(a.carpeta).name, len(errors), len(warns)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
