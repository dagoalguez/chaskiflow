"""Noticias: consolidar y detectar recurrencia (TF-IDF + coseno, solo librería estándar)."""

import math
import re
import unicodedata

TOKEN = re.compile(r"[a-z0-9ñ]{4,}")
STOP = {"para", "como", "pero", "este", "esta", "esto", "esos", "esas", "entre", "sobre", "desde", "hasta",
        "cuando", "donde", "porque", "aunque", "tambien", "segun", "todos", "todas", "otro", "otra", "otros",
        "otras", "ante", "cada", "ellos", "ellas", "hacia", "mientras", "durante", "mismo", "misma", "sido",
        "seran", "sera", "fueron", "haber", "hacer", "hace", "dijo", "senalo", "indico", "tras", "ademas",
        "luego", "ahora", "solo", "muy", "mas", "anos", "dias", "lima", "peru"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def tokens(text):
    return [t for t in TOKEN.findall(norm(text)) if t not in STOP]


def similar_pairs(texts, threshold):
    """Pares (i, j, similitud) con TF-IDF + coseno. Índice invertido: no compara todo contra todo."""
    n = len(texts)
    docs = [tokens(t) for t in texts]
    df = {}
    for d in docs:
        for term in set(d):
            df[term] = df.get(term, 0) + 1
    vecs = []
    for d in docs:
        tf = {}
        for term in d:
            tf[term] = tf.get(term, 0.0) + 1.0
        vec = {term: (1.0 + math.log(f)) * (math.log((1 + n) / (1 + df[term])) + 1.0) for term, f in tf.items()}
        norm_ = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vecs.append({t: v / norm_ for t, v in vec.items()})
    inv = {}
    cap = max(3, int(n * 0.25))
    for i, vec in enumerate(vecs):
        for term in vec:
            if df[term] <= cap:
                inv.setdefault(term, []).append(i)
    cand = {}
    for ids in inv.values():
        if len(ids) < 2 or len(ids) > 60:
            continue
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                cand[(ids[a], ids[b])] = cand.get((ids[a], ids[b]), 0) + 1
    pairs = []
    for (i, j), shared in cand.items():
        if shared < 2:
            continue
        vi, vj = vecs[i], vecs[j]
        if len(vj) < len(vi):
            vi, vj = vj, vi
        sim = sum(w * vj.get(t, 0.0) for t, w in vi.items())
        if sim >= threshold:
            pairs.append((i, j, round(sim, 4)))
    return pairs


def _collect(config, ctx):
    rows, medios_con_datos = [], set()

    def absorb(obj):
        if isinstance(obj, list):
            for x in obj:
                if isinstance(x, dict) and "url" in x and "titulo" in x:
                    rows.append(x)
                elif isinstance(x, (list, dict)):
                    absorb(x)
        elif isinstance(obj, dict) and isinstance(obj.get("rows"), list):
            absorb(obj["rows"])

    src = config.get("sources")
    if src:
        absorb(src if isinstance(src, list) else [src])
        if rows:
            ctx.log("%d filas desde la fuente explícita" % len(rows))
            return rows
    for label, res in (ctx.inputs or {}).items():
        if isinstance(res, dict) and res.get("_kind") == "news_rows":
            fl = res.get("rows") or []
            rows.extend(fl)
            ctx.log("%4d filas de '%s' (%s)" % (len(fl), label, res.get("medio", "")))
    return rows


def run(config, ctx):
    threshold = float(config.get("umbral") or 0.40)
    n_chars = int(config.get("chars_similitud") or 1200)
    cross = config.get("cross_medio") is not False
    only_rel = bool(config.get("only_relevant"))
    order = config.get("orden") or "relevancia"
    max_rows = int(config.get("max_rows") or 0)
    expected = [m.strip() for m in re.split(r"[,;\n]", config.get("medios_esperados") or "") if m.strip()]

    rows = _collect(config, ctx)
    if not rows:
        raise RuntimeError("No llegaron noticias. Este nodo debe ir DESPUÉS de los nodos 'Noticias: leer medio' "
                           "(casilla 'Depende de') y alguno debe haber terminado bien.")
    uniq = {}
    for r in rows:
        url = (r.get("url") or "").strip().split("#")[0].rstrip("/")
        if url and url not in uniq:
            uniq[url] = dict(r)
    data = list(uniq.values())
    ctx.log("%d filas -> %d únicas por URL" % (len(rows), len(data)))
    if only_rel:
        data = [d for d in data if d.get("ind_relevante")]
    for d in data:
        d.setdefault("ind_relevante", 0)
        d.setdefault("palabras_detectadas", "")
        d.update({"recurrencia": "No", "nro_medios": 1, "medios": d.get("medio", ""), "id_recurrencia": ""})

    n_groups = 0
    if len(data) > 1:
        texts = [(d.get("titulo") or "") + " " + (d.get("contenido") or "")[:n_chars] for d in data]
        pairs = similar_pairs(texts, threshold)
        if cross:
            pairs = [(i, j, s) for i, j, s in pairs if data[i].get("medio") != data[j].get("medio")]
        parent = list(range(len(data)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i, j, _ in pairs:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
        groups = {}
        for i in range(len(data)):
            groups.setdefault(find(i), []).append(i)
        for _, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(members) < 2:
                continue
            medios = sorted({data[i].get("medio", "") for i in members})
            if cross and len(medios) < 2:
                continue
            n_groups += 1
            for i in members:
                data[i].update({"recurrencia": "Sí", "id_recurrencia": "REC_%04d" % n_groups,
                                "nro_medios": len(medios), "medios": ", ".join(medios)})
        ctx.log("%d grupos de recurrencia (umbral %s, %d pares)" % (n_groups, threshold, len(pairs)))

    if order == "fecha":
        data.sort(key=lambda d: d.get("fecha_iso") or "", reverse=True)
    elif order == "medio":
        data.sort(key=lambda d: (d.get("medio") or "", d.get("fecha_iso") or ""))
    else:  # relevancia; a igual relevancia y medios, lo más reciente primero
        data.sort(key=lambda d: d.get("fecha_iso") or "", reverse=True)
        data.sort(key=lambda d: (-int(d.get("ind_relevante") or 0), -int(d.get("nro_medios") or 1)))
    if max_rows:
        data = data[:max_rows]

    per = {}
    for d in data:
        s = per.setdefault(d.get("medio", "?"), {"total": 0, "relevantes": 0})
        s["total"] += 1
        s["relevantes"] += int(d.get("ind_relevante") or 0)
    rel = sum(int(d.get("ind_relevante") or 0) for d in data)
    rec = sum(1 for d in data if d["recurrencia"] == "Sí")
    missing = [m for m in expected if m not in per]
    lines = ["  - %s: %d noticias (%d relevantes)" % (m, v["total"], v["relevantes"]) for m, v in sorted(per.items())]
    md = ("Total de noticias: %d\nRelevantes (palabras clave): %d\nEn más de un medio (recurrencia): %d en %d grupos\n\n"
          "Por medio:\n%s" % (len(data), rel, rec, n_groups, "\n".join(lines)))
    if missing:
        md += "\n\nMedios sin noticias en esta corrida: " + ", ".join(missing)
    return {"_kind": "news_consolidated", "rows": data, "total": len(data), "relevantes": rel, "recurrentes": rec,
            "grupos_recurrencia": n_groups, "medios_sin_datos": missing,
            "resumen": {"por_medio": per, "total": len(data), "relevantes": rel, "recurrentes": rec},
            "resumen_md": md}

