"""Rastrea una lista de sitios y devuelve candidatos de dirección (sin IA)."""

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from sitelib import Fetcher, KEYWORDS, crawl_site


def _sites(value):
    out = []
    if isinstance(value, str):
        value = [x for x in re.split(r"[\n;]+", value) if x.strip()]
    for v in value or []:
        if isinstance(v, dict):
            u, n = v.get("url") or v.get("link") or v.get("enlace") or "", v.get("name") or v.get("nombre") or ""
        else:
            u, n = str(v).strip(), ""
        if not u:
            continue
        if not re.match(r"^https?://", u, re.I):
            u = "https://" + u
        host = urlparse(u).netloc.lower()
        out.append({"name": n or re.sub(r"^www\.", "", host), "url": u})
    return out


def run(config, ctx):
    sites = _sites(config.get("sites"))
    if not sites:
        raise RuntimeError("No hay sitios para rastrear: conecte «Lista de enlaces» o escriba una URL por línea")
    kws = [k.strip() for k in re.split(r"[\n,]+", config.get("keywords") or "") if k.strip()] or list(KEYWORDS)
    opts = {"max_pages": config.get("max_pages") or 40, "max_depth": config.get("max_depth") if config.get("max_depth") is not None else 3,
            "delay": config.get("delay") if config.get("delay") is not None else 0.4, "max_seconds": config.get("max_seconds") or 240,
            "keywords": kws, "subdomains": bool(config.get("subdomains")), "robots": bool(config.get("respect_robots")),
            "probe_paths": bool(config.get("probe_paths")), "bloque_chars": config.get("text_block_chars") or 3500}
    fetcher = Fetcher(timeout=config.get("timeout") or 25, user_agent=config.get("user_agent") or None,
                      verify_ssl=bool(config.get("verify_ssl")), ca_bundle=config.get("ca_bundle") or "",
                      proxy=config.get("proxy") or "")
    done, lock = [0], threading.Lock()
    total = len(sites)
    ctx.log("Rastreando %d sitio(s): hasta %d página(s) cada uno, profundidad %d" % (total, opts["max_pages"], opts["max_depth"]))

    def one(s):
        try:
            res = crawl_site(s["name"], s["url"], opts, fetcher)
        except Exception as e:  # un sitio con problemas no detiene al resto
            res = {"sitio": s["name"], "sitio_url": s["url"], "paginas": 0, "paginas_ubicacion": [], "errores": [str(e)],
                   "bloqueadas_robots": 0, "rows": [], "bloques": [], "cortado": "", "segundos": 0}
        with lock:
            done[0] += 1
            ctx.progress(done[0], total, s["name"])
            ctx.log("%s: %d página(s), %d candidato(s)%s%s" % (
                s["name"], res["paginas"], len(res["rows"]), " · cortado por " + res["cortado"] if res.get("cortado") else "",
                " · ERROR: " + res["errores"][0] if res["errores"] and not res["paginas"] else ""))
        return res

    with ThreadPoolExecutor(max_workers=int(config.get("workers") or 3)) as ex:
        results = list(ex.map(one, sites))
    rows, bloques, summary, empty = [], [], [], []
    for r in results:
        rows.extend(r["rows"])
        bloques.extend(r["bloques"])
        summary.append({"sitio": r["sitio"], "url": r["sitio_url"], "paginas": r["paginas"], "candidatos": len(r["rows"]),
                        "paginas_ubicacion": r["paginas_ubicacion"][:10], "errores": r["errores"][:3],
                        "bloqueadas_por_robots": r["bloqueadas_robots"], "cortado": r.get("cortado", ""), "segundos": r.get("segundos", 0)})
        if not r["rows"]:
            empty.append(r["sitio"])
    ctx.log("Total: %d candidato(s) en %d sitio(s); sin resultados: %d" % (len(rows), total, len(empty)))
    return {"rows": rows, "bloques": bloques, "sites": summary, "total": len(rows), "sin_resultados": empty}
