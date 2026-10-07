#!/usr/bin/env python3
"""Ejecuta un workflow JSON desde la línea de comandos (sin servidor).

  python run_workflow.py examples/hola_reporte.json
  python run_workflow.py flujo.json --var carpeta=D:/salida
  python run_workflow.py --list-plugins
  python run_workflow.py flujo.json --validate
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from chaskiflow.engine import Engine, WorkflowError  # noqa: E402
from chaskiflow.plugin_loader import PluginRegistry  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ejecuta un workflow de ChaskiFlow")
    ap.add_argument("workflow", nargs="?", help="archivo .json del workflow")
    ap.add_argument("--plugins", action="append", help="carpeta de plugins (repetible)")
    ap.add_argument("--var", action="append", default=[], help="variable clave=valor")
    ap.add_argument("--workdir", default=str(ROOT / "runs"), help="carpeta de trabajo")
    ap.add_argument("--validate", action="store_true", help="solo validar")
    ap.add_argument("--list-plugins", action="store_true")
    ap.add_argument("--json", action="store_true", help="imprimir el resultado completo en JSON")
    args = ap.parse_args(argv)

    registry = PluginRegistry(args.plugins or [ROOT / "plugins"])
    if args.list_plugins:
        for e in registry.catalog():
            mark = "OK " if e["ok"] else "ERR"
            print("[%s] %-18s v%-7s %s" % (mark, e["id"], e["version"], e["name"]))
            for err in e["errors"]:
                print("       - %s" % err)
        return 0
    if not args.workflow:
        ap.error("indique el archivo del workflow (o use --list-plugins)")

    wf = json.loads(Path(args.workflow).read_text(encoding="utf-8-sig"))
    variables = {}
    for kv in args.var:
        k, _, v = kv.partition("=")
        variables[k] = v
    engine = Engine(registry, workdir_root=args.workdir)
    errors, warnings = engine.validate(wf)
    for w in warnings:
        print("AVISO:", w)
    if errors:
        print("El workflow no es válido:")
        for e in errors:
            print("  -", e)
        return 2
    if args.validate:
        print("Workflow válido.")
        return 0

    def show(ev):
        t = ev["type"]
        if t == "node_start":
            print("▶ %s" % ev["label"])
        elif t == "node_end":
            extra = (" — %s" % (ev.get("error") or ev.get("reason"))) if ev["status"] != "ok" else ""
            print("  %s %s (%.1f s)%s" % ("✔" if ev["status"] == "ok" else "✖", ev["status"],
                                           ev.get("duration") or 0, extra))
        elif t == "log":
            print("    · %s" % ev.get("message"))
        elif t == "run_end":
            print("Resultado: %s en %.1f s" % (ev["status"], ev["duration"]))

    try:
        res = engine.run(wf, on_event=show, variables=variables)
    except WorkflowError as e:
        print("Error:", e)
        return 2
    if args.json:
        print(json.dumps(res.to_dict(full=False), ensure_ascii=False, indent=2, default=str))
    return 0 if res.status in ("ok", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
