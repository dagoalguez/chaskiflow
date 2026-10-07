"""Exportar XLSX (solo librería estándar)."""

import json
import re
from datetime import datetime
from pathlib import Path

from xlsx_writer import write_xlsx

_BAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _split_columns(text):
    return [c.strip() for c in re.split(r"[,\n]", text or "") if c.strip()]


def _value(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def _unique(path):
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name("%s_%d%s" % (path.stem, i, path.suffix))
        if not cand.exists():
            return cand
        i += 1


def _safe_replace(tmp, path, ctx):
    """Mueve tmp sobre path. En Windows falla (WinError 5/32) si el destino está abierto, p. ej. en Excel,
    o lo bloquea un antivirus un instante: se reintenta y, si sigue bloqueado, se guarda con otro nombre."""
    import time
    last = None
    for _ in range(6):
        try:
            tmp.replace(path)
            return path
        except PermissionError as e:
            last = e
            time.sleep(0.4)
    i = 1
    while True:
        alt = path.with_name("%s_%d%s" % (path.stem, i, path.suffix))
        if not alt.exists():
            break
        i += 1
    try:
        tmp.replace(alt)
    except PermissionError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise RuntimeError("No se pudo escribir '%s': %s. Cierre el archivo si lo tiene abierto (¿Excel?) "
                           "o revise los permisos de la carpeta." % (path, last))
    ctx.log("AVISO: '%s' está abierto o bloqueado (¿Excel?); se guardó como '%s'." % (path.name, alt.name))
    return alt


def run(config, ctx):
    data = config.get("data")
    if not isinstance(data, list):
        raise RuntimeError("'Datos' debe ser una lista de filas (recibido: %s)"
                           % type(data).__name__)
    if any(not isinstance(r, dict) for r in data):
        raise RuntimeError("Todas las filas deben ser objetos (diccionarios)")

    columns = _split_columns(config.get("columns"))
    if not columns:
        for r in data:
            for k in r:
                if k not in columns:
                    columns.append(k)
    rename = config.get("rename") or {}
    header = [rename.get(c, c) for c in columns]
    rows = [[_value(r.get(c)) for c in columns] for r in data]

    name = datetime.now().strftime(config.get("filename") or "export_%Y-%m-%d")
    name = _BAD_NAME.sub("_", name).strip() or "export"
    if not name.lower().endswith(".xlsx"):
        name += ".xlsx"
    out_dir = Path(str(config["output_dir"])).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    if not config.get("overwrite", True):
        path = _unique(path)

    tmp = path.with_name(path.name + ".tmp")
    write_xlsx(str(tmp), header or ["(vacío)"], rows, config.get("sheet_name") or "Datos",
               int(config.get("max_cell_chars") or 32767))
    path = _safe_replace(tmp, path, ctx)
    ctx.log("XLSX escrito: %s (%d filas)" % (path, len(rows)))
    return {"file_path": str(path), "file_paths": [str(path)], "filename": path.name,
            "rows": len(rows), "columns": columns}
