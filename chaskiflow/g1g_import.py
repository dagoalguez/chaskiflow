"""Importador de flujos del formato G1G (nodes con data.task_type) a definiciones ChaskiFlow.

convert(g1g) -> (definición ChaskiFlow, informe). El informe es una lista de
{"level": "info"|"warn"|"error", "node": etiqueta o "", "message": texto}.
Solo librería estándar. No ejecuta nada: únicamente traduce JSON.
"""

import re
import unicodedata

NEWS_DROP = ("headless", "stealth", "session_id", "keep_session", "seen_key", "fetch_mode",
             "link_selector", "on_error")
EXPORT_COMMON = ("data", "output_dir", "filename", "columns", "rename", "overwrite")
EXPORT_CSV = EXPORT_COMMON + ("delimiter", "encoding")
EXPORT_XLSX = EXPORT_COMMON + ("sheet_name",)
SAME_TYPES = {"news_consolidate", "news_feed_scrape", "outlook_send"}


def is_g1g(d):
    """¿Parece un flujo G1G? (nodos con data.task_type)."""
    if not isinstance(d, dict) or not isinstance(d.get("nodes"), list):
        return False
    return any(isinstance(n, dict) and isinstance(n.get("data"), dict) and "task_type" in n["data"]
               for n in d["nodes"])


def _slug(text, used):
    t = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"\W+", "_", t).strip("_") or "Paso"
    if t[0].isdigit():
        t = "P_" + t
    base, i = t[:60], 2
    t = base
    while t in used:
        t = "%s_%d" % (base, i)
        i += 1
    used.add(t)
    return t


def _walk(value, fn):
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [_walk(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _walk(v, fn) for k, v in value.items()}
    return value


def _rename_refs(cfg, mapping):
    """Reescribe {{Vieja.…}} -> {{Nueva.…}} en todas las cadenas."""
    changed = {k: v for k, v in mapping.items() if k != v}
    if not changed:
        return cfg
    pat = re.compile(r"\{\{\s*(%s)(?=[.\s}|])" % "|".join(
        re.escape(k) for k in sorted(changed, key=len, reverse=True)))
    return _walk(cfg, lambda s: pat.sub(lambda m: "{{" + changed[m.group(1)], s))


def convert(g1g):
    report = []

    def rep(level, node, msg):
        report.append({"level": level, "node": node, "message": msg})

    nodes_in = [n for n in g1g.get("nodes", []) if isinstance(n, dict)]
    used, ren, info = set(), {}, []
    for n in nodes_in:
        data = n.get("data") if isinstance(n.get("data"), dict) else {}
        old = str(data.get("label") or n.get("id") or "Paso")
        new = _slug(old, used)
        ren[old] = new
        if new != old:
            rep("info", new, "Etiqueta '%s' renombrada a '%s' (solo letras, números y _)." % (old, new))
        info.append((n, data, new))

    out_nodes, xlsx_twin = [], {}
    for n, data, label in info:
        nid = str(n.get("id") or label)[:64]
        typ = str(data.get("task_type") or "")
        cfg = dict(data.get("config") or {})
        on_error = "continue" if str(cfg.pop("on_error", "")).lower() in ("continue", "skip", "ignore") \
            else "stop"
        if n.get("foreachParent") or n.get("parent") or n.get("children"):
            rep("warn", label, "Usa bucles/agrupación (foreach); ChaskiFlow aún no los soporta: el nodo se "
                "importó suelto, revise el flujo.")
        node = {"id": nid, "label": label, "on_error": on_error, "config": {}}
        pos = n.get("position")
        if isinstance(pos, dict):
            node["position"] = {"x": pos.get("x", 0), "y": pos.get("y", 0)}
        if typ == "news_feed_scrape":
            if str(cfg.get("fetch_mode", "requests")).lower() not in ("requests", "http", ""):
                rep("warn", label, "fetch_mode '%s': ChaskiFlow solo descarga por HTTP simple (sin navegador); "
                    "si el medio exige JavaScript fallará." % cfg.get("fetch_mode"))
            if cfg.get("link_selector"):
                rep("warn", label, "link_selector no se importa; use 'url_regex' o 'include_paths' para "
                    "filtrar enlaces.")
            dropped = [k for k in NEWS_DROP if k in cfg and k not in ("fetch_mode", "link_selector")]
            if dropped:
                rep("info", label, "Campos sin equivalente, omitidos: %s." % ", ".join(dropped))
            node["type"] = typ
            node["config"] = {k: v for k, v in cfg.items() if k not in NEWS_DROP}
        elif typ == "data_export":
            fmt = str(cfg.get("format") or "csv").lower()
            if fmt not in ("csv", "xlsx", "both"):
                rep("warn", label, "Formato '%s' desconocido; se usó csv." % fmt)
                fmt = "csv"
            allowed_c = {k: v for k, v in cfg.items() if k in EXPORT_CSV}
            allowed_x = {k: v for k, v in cfg.items() if k in EXPORT_XLSX}
            lost = [k for k in cfg if k not in EXPORT_CSV and k not in EXPORT_XLSX and k != "format"]
            if lost:
                rep("info", label, "Campos omitidos: %s." % ", ".join(lost))
            if fmt == "xlsx":
                node["type"], node["config"] = "export_xlsx", allowed_x
            else:
                node["type"], node["config"] = "export_csv", allowed_c
            if fmt == "both":
                twin_label = _slug(label + "_xlsx", used)
                twin = {"id": (nid + "_xlsx")[:64], "label": twin_label, "type": "export_xlsx",
                        "on_error": on_error, "config": allowed_x}
                if "position" in node:
                    twin["position"] = {"x": node["position"]["x"], "y": node["position"]["y"] + 90}
                xlsx_twin[nid] = twin
                rep("info", label, "Formato 'both' dividido en dos pasos: '%s' (CSV) y '%s' (XLSX)." %
                    (label, twin_label))
            else:
                rep("info", label, "Tipo 'data_export' traducido a %s." % node["type"])
        elif typ == "outlook_send":
            c = dict(cfg)
            if "body_format" in c:
                c["body_is_html"] = str(c.pop("body_format")).lower() == "html"
            if "send_mode" in c:
                c["mode"] = c.pop("send_mode")
            node["type"], node["config"] = typ, c
        elif typ in SAME_TYPES:
            node["type"], node["config"] = typ, cfg
        else:
            node["type"], node["config"] = typ, cfg
            rep("warn", label, "Tipo de tarea '%s' desconocido en ChaskiFlow; se conservó tal cual. Instale un "
                "plugin con ese id o cámbielo." % typ)
        out_nodes.append(node)

    for node in out_nodes:
        node["config"] = _rename_refs(node["config"], ren)
    # adjuntos que apuntaban a un export 'both' pasan a listar CSV y XLSX
    id_to_label = {n["id"]: n["label"] for n in out_nodes}
    for csv_id, twin in xlsx_twin.items():
        lab, tl = id_to_label[csv_id], twin["label"]
        ref = re.compile(r"^\s*\{\{\s*%s\.result\.\w+\s*\}\}\s*$" % re.escape(lab))
        for node in out_nodes:
            att = node["config"].get("attachments")
            if node["type"] == "outlook_send" and isinstance(att, str) and ref.match(att):
                node["config"]["attachments"] = ["{{%s.result.file_paths}}" % lab,
                                                 "{{%s.result.file_paths}}" % tl]
                rep("info", node["label"], "Adjuntos ahora incluyen CSV y XLSX (%s, %s)." % (lab, tl))
        out_nodes.append(twin)

    ids = {n["id"] for n in out_nodes}
    edges, seen = [], set()

    def add(a, b):
        if (a, b) not in seen:
            seen.add((a, b))
            edges.append({"source": a, "target": b})

    for e in g1g.get("edges", []):
        if not isinstance(e, dict):
            continue
        s, t = str(e.get("source", ""))[:64], str(e.get("target", ""))[:64]
        if s not in ids or t not in ids:
            rep("warn", "", "Conexión %s → %s ignorada (nodo inexistente)." % (s, t))
            continue
        add(s, t)
        if s in xlsx_twin or t in xlsx_twin:   # el gemelo XLSX hereda entradas y salidas
            add(xlsx_twin[s]["id"] if s in xlsx_twin else s, xlsx_twin[t]["id"] if t in xlsx_twin else t)
    definition = {"nodes": out_nodes, "edges": edges,
                  "variables": g1g["variables"] if isinstance(g1g.get("variables"), dict) else {}}
    rep("info", "", "Importados %d paso(s) y %d conexión(es)." % (len(out_nodes), len(edges)))
    return definition, report
