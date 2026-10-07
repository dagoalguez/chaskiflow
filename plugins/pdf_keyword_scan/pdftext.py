"""Lectura de PDF sin instalar nada: texto por página y, para páginas escaneadas, la imagen (JPEG o PNG) que se
envía al modelo con visión. Usa pypdf (pura Python, licencia BSD) incluido en la carpeta pypdf/."""

import logging
import struct
import sys
import typing
import zlib
from pathlib import Path

if sys.version_info < (3, 11):               # pypdf pide typing_extensions en Python < 3.11
    try:
        import typing_extensions  # noqa: F401
    except ImportError:
        import types
        _te = types.ModuleType("typing_extensions")
        for _n in ("Self", "TypeAlias", "TypeGuard"):
            setattr(_te, _n, getattr(typing, _n, typing.Any))
        sys.modules["typing_extensions"] = _te

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pypdf import PdfReader  # noqa: E402

logging.getLogger("pypdf").setLevel(logging.CRITICAL)


class PdfError(Exception):
    pass


def open_pdf(path):
    try:
        r = PdfReader(str(path), strict=False)
        if r.is_encrypted:
            try:
                ok = r.decrypt("")
            except Exception as e:           # sin biblioteca de cifrado (AES) o clave distinta
                raise PdfError("PDF cifrado que no se puede abrir sin clave (%s)" % str(e)[:80])
            if not ok:
                raise PdfError("PDF protegido con clave")
        len(r.pages)
        return r
    except PdfError:
        raise
    except Exception as e:
        raise PdfError("PDF dañado o ilegible: %s" % str(e)[:120])


def page_text(page):
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


# ----------------------------------------------------------------------------------- imágenes de páginas escaneadas
def _filters(obj):
    f = obj.get("/Filter")
    if f is None:
        return []
    f = f.get_object() if hasattr(f, "get_object") else f
    if isinstance(f, (list, tuple)):
        return [str(x.get_object() if hasattr(x, "get_object") else x) for x in f]
    return [str(f)]


def _images(res, depth=0):
    if res is None or depth > 2:
        return
    res = res.get_object()
    xo = res.get("/XObject")
    if xo is None:
        return
    xo = xo.get_object()
    for k in list(xo.keys()):
        try:
            o = xo[k].get_object()
        except Exception:
            continue
        st = o.get("/Subtype")
        if st == "/Image":
            yield o
        elif st == "/Form":
            for x in _images(o.get("/Resources"), depth + 1):
                yield x


def _png(width, height, bpc, color_type, rows, plte=None):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + r for r in rows)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bpc, color_type, 0, 0, 0))
    if plte:
        out += chunk(b"PLTE", plte)
    return out + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def _colorspace(obj):
    cs = obj.get("/ColorSpace")
    cs = cs.get_object() if hasattr(cs, "get_object") else cs
    if isinstance(cs, (list, tuple)) and cs:
        name = str(cs[0].get_object() if hasattr(cs[0], "get_object") else cs[0])
        if name == "/ICCBased":
            icc = cs[1].get_object()
            n = int(icc.get("/N", 3))
            return "/DeviceGray" if n == 1 else ("/DeviceRGB" if n == 3 else "/DeviceCMYK"), None
        if name == "/Indexed":
            base = cs[1].get_object() if hasattr(cs[1], "get_object") else cs[1]
            base_name = str(base[0].get_object() if isinstance(base, (list, tuple)) else base)
            hival = int(cs[2])
            lookup = cs[3].get_object() if hasattr(cs[3], "get_object") else cs[3]
            data = lookup.get_data() if hasattr(lookup, "get_data") else (lookup if isinstance(lookup, bytes) else str(lookup).encode("latin-1"))
            return "/Indexed", (base_name, hival, data)
        return name, None
    return (str(cs) if cs is not None else "/DeviceGray"), None


def image_to_upload(obj):
    """Devuelve (mime, bytes) listo para enviar al modelo, o lanza ValueError con el motivo."""
    filters = _filters(obj)
    w, h = int(obj.get("/Width", 0)), int(obj.get("/Height", 0))
    if not (w and h):
        raise ValueError("imagen sin tamaño")
    if filters and filters[-1] == "/DCTDecode":
        data = obj.get_data()
        if data[:2] != b"\xff\xd8":
            raise ValueError("JPEG ilegible")
        return "image/jpeg", data
    unsupported = [f for f in filters if f not in ("/FlateDecode", "/Fl", "/LZWDecode", "/LZW", "/ASCII85Decode", "/A85",
                                                    "/ASCIIHexDecode", "/AHx", "/RunLengthDecode", "/RL")]
    if unsupported:
        raise ValueError("formato de imagen %s no soportado (no se puede leer sin instalar programas)" % unsupported[0].lstrip("/"))
    bpc = int(obj.get("/BitsPerComponent", 8)) if not obj.get("/ImageMask") else 1
    cs, extra = ("/DeviceGray", None) if obj.get("/ImageMask") else _colorspace(obj)
    data = obj.get_data()
    if cs in ("/DeviceGray", "/CalGray", "/G"):
        ncomp, ctype = 1, 0
    elif cs in ("/DeviceRGB", "/CalRGB", "/RGB"):
        ncomp, ctype = 3, 2
    elif cs == "/Indexed":
        ncomp, ctype = 1, 3
    else:
        raise ValueError("espacio de color %s no soportado" % cs)
    if bpc not in (1, 2, 4, 8) or (ctype == 2 and bpc != 8):
        raise ValueError("profundidad de %d bits no soportada" % bpc)
    stride = (w * ncomp * bpc + 7) // 8
    if len(data) < stride * h:
        raise ValueError("datos de imagen incompletos")
    dec = obj.get("/Decode")
    invert = bool(dec) and [float(x) for x in dec][:2] == [1.0, 0.0] and ctype == 0
    rows = []
    for y in range(h):
        r = data[y * stride:(y + 1) * stride]
        if invert:
            r = bytes(b ^ 0xFF for b in r)
        rows.append(r)
    plte = None
    if ctype == 3:
        base, hival, lut = extra
        n = hival + 1
        if base in ("/DeviceRGB", "/CalRGB", "/RGB"):
            plte = bytes(lut[:3 * n])
        elif base in ("/DeviceGray", "/CalGray", "/G"):
            plte = b"".join(bytes([v, v, v]) for v in lut[:n])
        else:
            raise ValueError("paleta de color no soportada")
    return "image/png", _png(w, h, bpc, ctype, rows, plte)


class NoImage(ValueError):
    pass


def has_image(page, min_side=200):
    """True si la página trae alguna imagen grande (sin decodificarla): indica una página escaneada."""
    for o in _images(page.get("/Resources")):
        try:
            if min(int(o.get("/Width", 0)), int(o.get("/Height", 0))) >= min_side:
                return True
        except Exception:
            continue
    return False


def page_image(page, min_side=200):
    """Imagen más grande de la página como (mime, bytes). Lanza ValueError si no hay o no se puede usar."""
    best = None
    for o in _images(page.get("/Resources")):
        try:
            w, h = int(o.get("/Width", 0)), int(o.get("/Height", 0))
        except Exception:
            continue
        if min(w, h) < min_side:
            continue
        if best is None or w * h > best[0]:
            best = (w * h, o)
    if best is None:
        raise NoImage("la página no tiene una imagen que leer")
    return image_to_upload(best[1])
