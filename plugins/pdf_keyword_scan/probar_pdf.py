"""Diagnóstico de un PDF: por página, cuánto texto trae, cuántos rellenos vectoriales (texto en contornos) y qué imagen tiene
(y, si es JBIG2, qué tipos de segmento).
Uso:  python plugins\\pdf_keyword_scan\\probar_pdf.py archivo.pdf [maxpaginas]
Solo lee el archivo; no envía nada a ningún lado."""

import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdftext  # noqa: E402

SEG = {0: "diccionario de símbolos", 4: "texto (intermedio)", 6: "región de texto", 7: "región de texto (final)",
       16: "diccionario de patrones", 20: "halftone", 22: "halftone", 23: "halftone (final)",
       36: "región genérica (intermedia)", 38: "región genérica", 39: "región genérica (final)",
       40: "refinamiento", 42: "refinamiento", 43: "refinamiento (final)", 48: "info de página", 49: "fin de página",
       50: "fin de franja", 51: "fin de archivo", 52: "perfiles", 53: "tabla", 62: "extensión"}


def jbig2_segments(data):
    """Tipos de segmento de un flujo JBIG2 incrustado en PDF (sin cabecera de archivo)."""
    out, p = [], 0
    try:
        while p + 11 <= len(data):
            num = struct.unpack(">I", data[p:p + 4])[0]
            flags = data[p + 4]
            typ = flags & 0x3F
            big_page = bool(flags & 0x40)
            p += 5
            c = data[p] >> 5
            if c == 7:
                cnt = struct.unpack(">I", data[p:p + 4])[0] & 0x1FFFFFFF
                p += 4 + (cnt + 8) // 8
            else:
                cnt = c
                p += 1
            ref = 1 if num <= 256 else (2 if num <= 65536 else 4)
            p += cnt * ref
            p += 4 if big_page else 1
            ln = struct.unpack(">I", data[p:p + 4])[0]
            p += 4
            out.append((typ, ln))
            if ln == 0xFFFFFFFF:
                break
            p += ln
    except (struct.error, IndexError):
        out.append((-1, 0))
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    rd = pdftext.open_pdf(argv[1])
    pages = rd.pages
    lim = int(argv[2]) if len(argv) > 2 else 8
    print("%s: %d página(s), %d KB" % (os.path.basename(argv[1]), len(pages), os.path.getsize(argv[1]) // 1024))
    con = 0
    for i, pg in enumerate(pages):
        t = re.sub(r"\s+", "", pdftext.page_text(pg))
        con += len(t) >= 25
        if i >= lim:
            continue
        imgs = []
        try:
            for o in pdftext._images(pg.get("/Resources")):
                fl = ",".join(x.lstrip("/") for x in pdftext._filters(o)) or "sin filtro"
                d = "%sx%s %s" % (o.get("/Width"), o.get("/Height"), fl)
                if "JBIG2" in fl:
                    try:
                        raw = o._data if hasattr(o, "_data") else b""
                        segs = jbig2_segments(raw)
                        d += " segmentos: " + ", ".join(sorted({SEG.get(t_, "tipo %d" % t_) for t_, _ in segs}))
                    except Exception as e:  # noqa: BLE001
                        d += " (no se pudo leer los segmentos: %s)" % e
                imgs.append(d)
        except Exception as e:  # noqa: BLE001
            imgs.append("error leyendo imágenes: %s" % e)
        try:
            nv = pdftext.vector_fills(pg)
        except Exception:  # noqa: BLE001
            nv = 0
        marca = " → VECTORIAL (se dibuja y va a la IA)" if (nv >= 30 and len(t) < 25) else ""
        print("  p. %d: %d caracteres de texto · %d rellenos vectoriales%s · imágenes: %s" % (
            i + 1, len(t), nv, marca, "; ".join(imgs) or "ninguna"))
    print("Páginas con texto (≥25 caracteres): %d de %d → %s" % (con, len(pages), "PDF de TEXTO (no usa IA salvo páginas dibujadas)" if con else "PDF SIN TEXTO (iría a la IA)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
