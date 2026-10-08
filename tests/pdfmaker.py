"""Genera PDF de prueba solo con la librería estándar: con texto, escaneados (imagen gris Flate o JPEG) y mixtos."""

import base64
import zlib

# JPEG mínimo válido de 8x8 (gris), para probar la ruta DCTDecode
JPEG_8X8 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/"
    "yQALCAAIAAgBAREA/8wABgAQEAX/2gAIAQEAAD8A0s8g/9k=")


def _pdf(objects):
    out = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offs = []
    for i, body in enumerate(objects, 1):
        offs.append(sum(len(x) for x in out))
        out.append(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = sum(len(x) for x in out)
    out.append(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for o in offs:
        out.append(b"%010d 00000 n \n" % o)
    out.append(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return b"".join(out)


def _esc(line):
    b = line.encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _text_stream(lines):
    ops = [b"BT /F1 11 Tf 14 TL 50 780 Td"]
    for ln in lines:
        ops.append(b"(" + _esc(ln) + b") Tj T*")
    ops.append(b"ET")
    return b"\n".join(ops)


def make_pdf(pages, compress=True):
    """pages: lista de páginas; cada una es:
         ("texto", [líneas])                    página con texto
         ("gris", valor_0_255)                  página escaneada: imagen gris 256x256 con ese valor (Flate)
         ("jpeg",)                              página escaneada: imagen JPEG
         ("jbig2",)                             página escaneada con un formato que no se puede leer
         ("vector", n)                          texto convertido a contornos: SIN capa de texto ni imágenes, n rellenos
         ("vector_logo", n)                     igual, pero con un logo JPEG grande (como los informes de auditoría)
    """
    objs = [None, None]          # 1 = catálogo, 2 = páginas (se rellenan al final)
    kids = []

    def add(body):
        objs.append(body)
        return len(objs)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for pg in pages:
        kind = pg[0]
        res = b"/Font << /F1 %d 0 R >>" % font
        if kind == "texto":
            data = _text_stream(pg[1])
            if compress:
                data, flt = zlib.compress(data), b" /Filter /FlateDecode"
            else:
                flt = b""
            cs = add(b"<< /Length %d%s >>\nstream\n" % (len(data), flt) + data + b"\nendstream")
        elif kind in ("vector", "vector_logo"):
            # n cuadros negros de 5x8 pt en filas: hacen de «letras» dibujadas como trazos rellenos
            n = pg[1]
            ops = []
            for k in range(n):
                x, y = 60 + (k % 40) * 12, 780 - (k // 40) * 20
                ops.append(b"0 0 0 rg %d %d 5 8 re\nf" % (x, y))
            content = b"\n".join(ops)
            if kind == "vector_logo":
                img = add(b"<< /Type /XObject /Subtype /Image /Width 400 /Height 400 /ColorSpace /DeviceGray /BitsPerComponent 8 "
                          b"/Filter /DCTDecode /Length %d >>\nstream\n" % len(JPEG_8X8) + JPEG_8X8 + b"\nendstream")
                res += b" /XObject << /Im1 %d 0 R >>" % img
                content = b"q 100 0 0 40 50 790 cm /Im1 Do Q\n" + content
            cs = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        else:
            if kind == "gris":
                raw = bytes([pg[1]]) * (256 * 256)
                data = zlib.compress(raw)
                img = add(b"<< /Type /XObject /Subtype /Image /Width 256 /Height 256 /ColorSpace /DeviceGray /BitsPerComponent 8 "
                          b"/Filter /FlateDecode /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
            elif kind == "jpeg":
                # el JPEG de prueba es de 8x8; se declara 400x400 solo para pasar el filtro de tamaño mínimo
                img = add(b"<< /Type /XObject /Subtype /Image /Width 400 /Height 400 /ColorSpace /DeviceGray /BitsPerComponent 8 "
                          b"/Filter /DCTDecode /Length %d >>\nstream\n" % len(JPEG_8X8) + JPEG_8X8 + b"\nendstream")
            else:
                data = b"\x00" * 64
                img = add(b"<< /Type /XObject /Subtype /Image /Width 400 /Height 400 /ColorSpace /DeviceGray /BitsPerComponent 1 "
                          b"/Filter /JBIG2Decode /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
            res += b" /XObject << /Im1 %d 0 R >>" % img
            content = b"q 500 0 0 700 50 50 cm /Im1 Do Q"
            cs = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        page = add(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << %s >> /Contents %d 0 R >>" % (res, cs))
        kids.append(page)
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    return _pdf(objs)
