"""Descarga del portal SMV los PDF «Estados Financieros y Dictamen» por empresa y año. Solo librería estándar."""

import os
import re
import time

from smvlib import DEFAULT_URL, Portal, PortalError, norm, safe_name


def _pick_companies(lines, companies, log):
    """lines: texto del usuario; companies: [(id, nombre)] del portal. Devuelve [(id, nombre)] sin repetir."""
    if not lines:
        return list(companies), []
    chosen, missing, seen = [], [], set()
    for ln in lines:
        key = norm(ln)
        hits = [c for c in companies if (key.isdigit() and c[0] == key) or (not key.isdigit() and key in norm(c[1]))]
        exact = [c for c in hits if norm(c[1]) == key]
        hits = exact or hits
        if not hits:
            missing.append(ln)
            continue
        if len(hits) > 1:
            log("«%s» coincide con %d empresas: %s" % (ln, len(hits), "; ".join(h[1] for h in hits[:6]) + ("…" if len(hits) > 6 else "")))
        for h in hits:
            if h[0] not in seen:
                seen.add(h[0])
                chosen.append(h)
    return chosen, missing


def run(config, ctx):
    base = (config.get("carpeta") or "").strip()
    if not base:
        raise RuntimeError("Indique la carpeta de salida")
    y0, y1 = int(config.get("anio_desde") or 2021), int(config.get("anio_hasta") or 2025)
    if y0 > y1:
        y0, y1 = y1, y0
    tipo = "C" if str(config.get("tipo") or "").lower().startswith("c") else "I"
    want = norm(config.get("documento") or "Estados Financieros y Dictamen")
    pausa = float(config.get("pausa") if config.get("pausa") is not None else 1.0)
    limit = float(config.get("max_total_seconds") or 0)
    replace = bool(config.get("reemplazar"))
    dest_root = os.path.join(base, "Descargas")
    os.makedirs(dest_root, exist_ok=True)

    portal = Portal(url=(config.get("portal_url") or "").strip() or DEFAULT_URL, timeout=int(config.get("timeout") or 60),
                    verify_ssl=bool(config.get("verify_ssl", True)), ca_bundle=config.get("ca_bundle") or "",
                    proxy=config.get("proxy") or "", user_agent=config.get("user_agent") or "",
                    retries=int(config.get("reintentos") if config.get("reintentos") is not None else 3))
    try:
        companies = portal.open()
    except PortalError as e:
        raise RuntimeError("No se pudo abrir el portal de la SMV: %s. Si hay un proxy con SSL re-firmado, use «Archivo CA» o desactive «Verificar SSL»." % e)
    ctx.log("Portal abierto: %d empresas en la lista" % len(companies))
    lines = [x.strip() for x in re.split(r"[\n;]+", config.get("empresas") or "") if x.strip()]
    chosen, missing = _pick_companies(lines, companies, ctx.log)
    if lines and not chosen:
        raise RuntimeError("Ninguna de las empresas indicadas se encontró en el portal: " + "; ".join(missing))
    for m in missing:
        ctx.log("AVISO: no se encontró en el portal: «%s»" % m)
    years = list(range(y0, y1 + 1))
    total = len(chosen) * len(years)
    ctx.log("Buscando %d empresa(s) × %d año(s) = %d consulta(s). Documento: «%s»" % (len(chosen), len(years), total, config.get("documento") or "Estados Financieros y Dictamen"))

    rows, files, archivos, sin_doc = [], [], [], []
    st = {"descargados": 0, "existentes": 0, "errores": 0, "sin_documento": 0, "pendientes": 0, "empresas": len(chosen), "no_encontradas": missing}
    t0 = time.time()
    done = 0
    stop = False
    consecutive_fail = 0

    def row(emp, y, d, estado, archivo="", nbytes=0, err=""):
        return {"empresa": emp[1], "empresa_id": emp[0], "anio": y, "documento": d.get("documento", ""), "expediente": d.get("expediente", ""),
                "fecha": d.get("fecha", ""), "url": d.get("url", ""), "archivo": archivo, "estado": estado, "bytes": nbytes, "error": err}

    for emp in chosen:
        for y in years:
            if stop or (limit and time.time() - t0 > limit):
                stop = True
                st["pendientes"] += 1
                rows.append(row(emp, y, {}, "pendiente (tiempo agotado)"))
                continue
            done += 1
            ctx.progress(done, total, "%s %d" % (emp[1][:40], y))
            try:
                found = portal.search(emp[0], emp[1], y, tipo=tipo)
                consecutive_fail = 0
            except PortalError as e:
                st["errores"] += 1
                consecutive_fail += 1
                ctx.log("ERROR buscando %s %d: %s" % (emp[1], y, e))
                rows.append(row(emp, y, {}, "error", err=str(e)))
                if consecutive_fail >= 5:
                    try:
                        portal.open()                       # sesión caída: se reabre el portal
                        consecutive_fail = 0
                    except PortalError as e2:
                        raise RuntimeError("El portal dejó de responder tras varios errores seguidos: %s" % e2)
                time.sleep(pausa)
                continue
            docs = [d for d in found if norm(d["documento"]) == want]
            if not docs:
                st["sin_documento"] += 1
                sin_doc.append({"empresa": emp[1], "anio": y})
                time.sleep(pausa)
                continue
            seen_url = set()
            for d in docs:
                if d["url"] in seen_url:
                    continue
                seen_url.add(d["url"])
                folder = os.path.join(dest_root, safe_name(emp[1]), str(y))
                os.makedirs(folder, exist_ok=True)
                exp = re.sub(r"\D", "", d["expediente"]) or "sin-expediente"
                dest = os.path.join(folder, "%d_%s_%s.pdf" % (y, safe_name(emp[1], 40).replace(" ", "_"), exp))
                if os.path.isfile(dest) and os.path.getsize(dest) > 0 and not replace:
                    st["existentes"] += 1
                    files.append(dest)
                    archivos.append({"archivo": dest, "empresa": emp[1], "anio": y, "expediente": d["expediente"]})
                    rows.append(row(emp, y, d, "ya existía", dest, os.path.getsize(dest)))
                    continue
                try:
                    n = portal.download(d["url"], dest)
                except PortalError as e:
                    st["errores"] += 1
                    ctx.log("ERROR descargando %s %d (%s): %s" % (emp[1], y, d["expediente"], e))
                    rows.append(row(emp, y, d, "error", err=str(e)))
                    continue
                st["descargados"] += 1
                files.append(dest)
                archivos.append({"archivo": dest, "empresa": emp[1], "anio": y, "expediente": d["expediente"]})
                rows.append(row(emp, y, d, "descargado", dest, n))
                ctx.log("%s %d: %s (%d KB)" % (emp[1], y, os.path.basename(dest), n // 1024))
                time.sleep(pausa)
            time.sleep(pausa)
    st["segundos"] = round(time.time() - t0, 1)
    if st["pendientes"]:
        ctx.log("AVISO: se alcanzó el tiempo máximo total; %d consulta(s) quedaron pendientes. Vuelva a ejecutar: continúa sin repetir lo descargado." % st["pendientes"])
    ctx.log("Listo: %d descargado(s), %d ya existían, %d sin ese documento, %d error(es), %d pendiente(s)" % (
        st["descargados"], st["existentes"], st["sin_documento"], st["errores"], st["pendientes"]))
    return {"rows": rows, "files": files, "archivos": archivos, "total": len(files), "stats": st, "sin_documento": sin_doc, "carpeta_descargas": dest_root}
