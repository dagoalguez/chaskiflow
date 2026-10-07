"""Noticias: leer un medio (solo librería estándar)."""

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from newslib import (FetchError, Fetcher, clean_text, detect, extract_article, norm, parse_date, parse_feed,
                     parse_list, parse_urls)


def _seen_path(d, key):
    safe = re.sub(r"[^\w.-]+", "_", key)[:80] or "medio"
    return os.path.join(d, safe + ".txt")


def _load_seen(d, key):
    try:
        with open(_seen_path(d, key), encoding="utf-8") as f:
            return {l.strip() for l in f if l.strip()}
    except OSError:
        return set()


def _save_seen(d, key, urls):
    os.makedirs(d, exist_ok=True)
    old = _load_seen(d, key)
    allu = sorted(old | set(urls))[-20000:]
    with open(_seen_path(d, key), "w", encoding="utf-8") as f:
        f.write("\n".join(allu))


def run(config, ctx):
    medio = (config.get("medio") or "").strip()
    feeds = parse_urls(config.get("feed_urls"))
    if not medio:
        raise RuntimeError("Falta el nombre del medio")
    if not feeds:
        raise RuntimeError("Falta al menos una URL de feed válida (http:// o https://)")
    ftype = config.get("feed_type") or "auto"
    include = [norm(x) for x in parse_list(config.get("include_paths"))]
    exclude = [norm(x) for x in parse_list(config.get("exclude_paths"))]
    url_regex = (config.get("url_regex") or "").strip()
    hours = float(config.get("hours_back") if config.get("hours_back") is not None else 24)
    max_articles = int(config.get("max_articles") or 60)
    exc_kws = parse_list(config.get("exclude_keywords"))
    exc_scope = config.get("exclude_scope") or "titulo"
    rel_kws = parse_list(config.get("relevance_keywords"))
    only_rel = bool(config.get("only_relevant"))
    min_chars = int(config.get("min_chars") or 0)
    max_chars = int(config.get("max_chars") or 20000)
    workers = max(1, min(16, int(config.get("workers") or 8)))
    skip_seen = bool(config.get("skip_seen"))
    seen_dir = (config.get("seen_dir") or "").strip() or os.path.join(os.path.expanduser("~"), ".chaskiflow", "news_seen")
    if url_regex:
        try:
            re.compile(url_regex)
        except re.error as e:
            raise RuntimeError("Regex de URL inválida: %s" % e)

    fetcher = Fetcher(timeout=int(config.get("timeout") or 30), user_agent=config.get("user_agent") or None,
                      verify_ssl=config.get("verify_ssl") is not False, ca_bundle=config.get("ca_bundle") or "",
                      proxy=config.get("proxy") or "")
    ctx.log("[%s] %d feed(s), últimas %s h" % (medio, len(feeds), hours or "∞"))

    # ---- 1. feeds
    raw, failed, last_kind = [], [], ""
    for furl in feeds:
        try:
            text = fetcher.get(furl)
            found = parse_feed(text, ftype, furl, fetch=fetcher.get, url_pattern=url_regex)
            raw.extend(found)
            ctx.log("  %4d items · %s" % (len(found), furl))
        except FetchError as e:
            last_kind = e.kind
            failed.append("%s (%s)" % (furl, e))
            ctx.log("  falló %s: %s" % (furl, e), "warn")
        except ValueError as e:
            last_kind = "FORMATO"
            failed.append("%s (%s)" % (furl, e))
            ctx.log("  falló %s: %s" % (furl, e), "warn")
    if not raw and failed:
        hints = {
            "PROXY_BLOCK": "El proxy institucional bloquea este dominio: pida a TI que lo habilite (ningún cambio en ChaskiFlow lo arregla).",
            "SSL": "Certificado rechazado: configure 'Certificado CA (.pem)' o desmarque 'Verificar SSL' en este nodo.",
            "HTTP": "El sitio rechazó la petición (403/404). Revise la URL; si es 403 puede bloquear clientes automáticos.",
            "RED": "Sin conexión. Revise la red, el proxy y la URL.",
            "FORMATO": "La URL no devuelve un feed XML. Pruebe feed_type = html_index.",
        }
        raise RuntimeError("[%s] Ningún feed respondió. %s Detalle: %s"
                           % (medio, hints.get(last_kind, ""), "; ".join(failed[:4])))

    # ---- 2. filtros previos a descargar
    limit = (datetime.now(timezone.utc) - timedelta(hours=hours)) if hours else None
    seen_cache = _load_seen(seen_dir, medio) if skip_seen else set()
    d = {"fuera_de_ventana": 0, "otra_seccion": 0, "duplicadas": 0, "excluidas_titulo": 0,
         "cuerpo_vacio": 0, "cuerpo_corto": 0, "excluidas_contenido": 0, "no_relevantes": 0, "errores": 0}
    run_seen, cands = set(), []
    for it in raw:
        url = (it.get("url") or "").strip()
        if not url or url in run_seen or (skip_seen and url in seen_cache):
            d["duplicadas"] += 1
            continue
        un = norm(url)
        if (include and not any(p in un for p in include)) or (exclude and any(p in un for p in exclude)) \
                or (url_regex and not re.search(url_regex, url, re.I)):
            d["otra_seccion"] += 1
            continue
        dt = parse_date(it.get("fecha_raw"))
        if limit and dt and dt < limit:
            d["fuera_de_ventana"] += 1
            continue
        run_seen.add(url)
        path = [s for s in urlparse(url).path.split("/") if s]
        cands.append({"medio": medio, "titulo": clean_text(it.get("titulo")),
                      "fecha_iso": dt.isoformat() if dt else "",
                      "fecha": dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "",
                      "url": url, "seccion": path[0] if path else ""})
    if exc_kws and exc_scope == "titulo":
        keep = [c for c in cands if not detect(c["titulo"] + " " + c["url"].replace("-", " ").replace("/", " "), exc_kws)]
        d["excluidas_titulo"] = len(cands) - len(keep)
        cands = keep
    cands = cands[:max_articles]
    ctx.log("%d notas a descargar (feed=%d)" % (len(cands), len(raw)))

    # ---- 3. descargar y extraer en paralelo
    def work(item):
        item = dict(item)
        try:
            html = fetcher.get(item["url"])
        except FetchError as e:
            item["_err"] = (e.kind, str(e))
            return item
        art = extract_article(html)
        item["contenido"] = clean_text(art["texto"])[:max_chars]
        item["_estrategia"] = art["estrategia"]
        if not item.get("fecha_iso") and art["fecha"]:
            dt = parse_date(art["fecha"])
            if dt:
                item["fecha_iso"] = dt.isoformat()
                item["fecha"] = dt.astimezone().strftime("%Y-%m-%d %H:%M")
        if len(item.get("titulo") or "") < 25 and art["titulo"]:
            item["titulo"] = art["titulo"]
        return item

    done, rows, strat, errs = 0, [], {}, {}
    if cands:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(work, c) for c in cands]):
                done += 1
                if done % 10 == 0 or done == len(cands):
                    ctx.progress(done, len(cands), "descargando notas")
                try:
                    rows.append(fut.result())
                except Exception as e:
                    d["errores"] += 1
                    ctx.log("error extrayendo una nota: %s" % e, "warn")

    # ---- 4. post-filtros y relevancia
    final = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in rows:
        if "_err" in r:
            d["errores"] += 1
            errs[r["_err"][0]] = errs.get(r["_err"][0], 0) + 1
            r.pop("_err")
            continue
        est = r.pop("_estrategia", "?")
        strat[est] = strat.get(est, 0) + 1
        body = r.get("contenido") or ""
        if len(body) < max(min_chars, 1):
            d["cuerpo_vacio" if not body else "cuerpo_corto"] += 1
            continue
        if limit and r.get("fecha_iso"):
            dt = parse_date(r["fecha_iso"])
            if dt and dt < limit:
                d["fuera_de_ventana"] += 1
                continue
        if exc_kws and exc_scope == "titulo_contenido" and detect(r["titulo"] + " " + body, exc_kws):
            d["excluidas_contenido"] += 1
            continue
        words = detect(r["titulo"] + " " + body, rel_kws)
        r["ind_relevante"] = 1 if words else 0
        r["palabras_detectadas"] = ", ".join(words)
        r["fecha_extraccion"] = now
        if only_rel and not words:
            d["no_relevantes"] += 1
            continue
        final.append(r)
    final.sort(key=lambda x: x.get("fecha_iso") or "", reverse=True)
    if skip_seen:
        try:
            _save_seen(seen_dir, medio, [r["url"] for r in final])
        except OSError as e:
            ctx.log("no se pudo guardar la lista de vistas: %s" % e, "warn")

    if strat:
        ctx.log("extracción: " + ", ".join("%s=%d" % kv for kv in sorted(strat.items(), key=lambda kv: -kv[1])))
    if errs:
        ctx.log("descargas fallidas: " + ", ".join("%s=%d" % kv for kv in errs.items()), "warn")
    if rows and d["cuerpo_vacio"] >= 0.8 * len(rows):
        ctx.log("Casi ninguna nota tuvo texto: el sitio puede cargar el cuerpo con JavaScript o el proxy devolvió "
                "una página de bloqueo. Pruebe con plugins/news_feed_scrape/probar_url.py <url-de-una-nota>.", "warn")
    rel = sum(r["ind_relevante"] for r in final)
    ctx.log("[%s] %d notas, %d relevantes" % (medio, len(final), rel))
    return {"_kind": "news_rows", "medio": medio, "rows": final, "total_feed": len(raw),
            "total_articulos": len(final), "relevantes": rel, "feeds_fallidos": failed, "descartes": d}
