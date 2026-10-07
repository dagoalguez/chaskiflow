"""Exportar CSV (solo librería estándar)."""

import csv
import json
import re
from datetime import datetime
from pathlib import Path

_BAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _split_columns(text):
    return [c.strip() for c in re.split(r"[,\n]", text or "") if c.strip()]


def _cell(value, max_chars, escape_formulas):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        if max_chars and len(value) > max_chars:
            value = value[:max_chars]
        if escape_formulas and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
            value = "'" + value
        return value
    return value


def unique_path(path):
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name("%s_%d%s" % (path.stem, i, path.suffix))
        if not cand.exists():
            return cand
        i += 1


def run(config, ctx):
    data = config.get("data")
    if not isinstance(data, list):
        raise RuntimeError("'Datos' debe ser una lista de filas (recibido: %s)"
                           % type(data).__name__)
    rows = [r for r in data if isinstance(r, dict)]
    if len(rows) != len(data):
        raise RuntimeError("Todas las filas deben ser objetos (diccionarios)")

    columns = _split_columns(config.get("columns"))
    if not columns:
        for r in rows:
            for k in r:
                if k not in columns:
                    columns.append(k)
    rename = config.get("rename") or {}
    header = [rename.get(c, c) for c in columns]

    name = datetime.now().strftime(config.get("filename") or "export_%Y-%m-%d")
    name = _BAD_NAME.sub("_", name).strip() or "export"
    if not name.lower().endswith(".csv"):
        name += ".csv"
    out_dir = Path(str(config["output_dir"])).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    if not config.get("overwrite", True):
        path = unique_path(path)

    max_chars = int(config.get("max_cell_chars") or 0)
    esc = bool(config.get("escape_formulas", True))
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding=config.get("encoding") or "utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=(config.get("delimiter") or ";")[:1])
        w.writerow(header)
        for r in rows:
            w.writerow([_cell(r.get(c), max_chars, esc) for c in columns])
    tmp.replace(path)
    ctx.log("CSV escrito: %s (%d filas)" % (path, len(rows)))
    return {"file_path": str(path), "file_paths": [str(path)], "filename": path.name,
            "rows": len(rows), "columns": columns}
