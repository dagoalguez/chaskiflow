"""Lee una lista de enlaces desde CSV o TXT (solo librería estándar)."""

import csv
import io
import re
from pathlib import Path
from urllib.parse import urlparse

DOMAIN = re.compile(r"^(?:www\.)?[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9][a-z0-9\-]*)+(?:[/?#:].*)?$", re.I)


def _decode(raw):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _norm(value):
    """Devuelve una URL http(s) válida o None."""
    v = (value or "").strip().strip('"\'<>').strip()
    if not v or " " in v:
        return None
    if re.match(r"^https?://", v, re.I):
        pass
    elif DOMAIN.match(v):
        v = "https://" + v
    else:
        return None
    u = urlparse(v)
    if not u.netloc or "." not in u.netloc.split(":")[0]:
        return None
    return v


def _sniff(text, wanted):
    if wanted:
        return "\t" if wanted.lower() in ("\\t", "tab", "tabulador") else wanted
    first = "\n".join(text.splitlines()[:20])
    counts = {d: first.count(d) for d in (";", ",", "\t", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ";"


def run(config, ctx):
    path = Path(str(config.get("file_path") or "").strip().strip('"'))
    if not path.is_file():
        raise RuntimeError("No existe el archivo: %s" % path)
    text = _decode(path.read_bytes())
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("El archivo está vacío")
    col, ncol = (config.get("column") or "").strip(), (config.get("name_column") or "").strip()
    items, skipped, seen = [], [], set()

    def add(name, raw, where):
        url = _norm(raw)
        if not url:
            skipped.append({"linea": where, "valor": (raw or "")[:120], "motivo": "no parece un enlace"})
            return
        key = re.sub(r"^https?://(www\.)?", "", url.lower()).rstrip("/")
        if key in seen:
            skipped.append({"linea": where, "valor": url, "motivo": "duplicado"})
            return
        seen.add(key)
        host = urlparse(url).netloc.lower()
        items.append({"name": (name or "").strip() or re.sub(r"^www\.", "", host), "url": url})

    is_csv = path.suffix.lower() == ".csv" or (
        len(lines) > 1 and any(d in lines[0] for d in (";", "\t", "|")) and not _norm(lines[0]))
    if is_csv:
        delim = _sniff(text, config.get("delimiter"))
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
        rows = [r for r in rows if any(c.strip() for c in r)]
        head = [c.strip() for c in rows[0]]
        has_header = not any(_norm(c) for c in head)
        data = rows[1:] if has_header else rows
        ui = ni = None
        if col:
            lowered = [h.lower() for h in head]
            if col.lower() not in lowered:
                raise RuntimeError("No existe la columna '%s'. Columnas: %s" % (col, ", ".join(head)))
            ui = lowered.index(col.lower())
        else:
            for i in range(max(len(r) for r in rows)):
                if any(i < len(r) and _norm(r[i]) for r in data[:50]):
                    ui = i
                    break
            if ui is None:
                raise RuntimeError("No encontré una columna con enlaces o dominios. Indique 'Columna de la URL'")
        if ncol:
            lowered = [h.lower() for h in head]
            if ncol.lower() not in lowered:
                raise RuntimeError("No existe la columna de nombre '%s'. Columnas: %s" % (ncol, ", ".join(head)))
            ni = lowered.index(ncol.lower())
        for n, r in enumerate(data, start=2 if has_header else 1):
            add(r[ni] if ni is not None and ni < len(r) else "", r[ui] if ui < len(r) else "", n)
    else:
        for n, ln in enumerate(text.splitlines(), start=1):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            add("", ln.split()[0] if ln.split() and _norm(ln.split()[0]) else ln, n)
    limit = int(config.get("limit") or 0)
    if limit and len(items) > limit:
        ctx.log("Se usan los primeros %d de %d enlaces" % (limit, len(items)))
        items = items[:limit]
    if not items:
        raise RuntimeError("No se encontró ningún enlace válido en %s" % path.name)
    ctx.log("%d enlace(s) válidos, %d descartado(s)" % (len(items), len(skipped)))
    return {"items": items, "urls": [i["url"] for i in items], "total": len(items), "skipped": skipped}
