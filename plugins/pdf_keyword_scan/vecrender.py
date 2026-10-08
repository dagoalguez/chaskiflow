#!/usr/bin/env python3
"""vecrender: rasterizador vectorial de paginas PDF.

Solo libreria estandar (el lector de PDF es pypdf, puro Python).
Pensado para PDFs cuyo texto esta convertido a contornos (sin capa de texto
ni imagenes): lee el flujo de contenido y pinta rellenos (f, f*, B, b), trazos
(S, B) y recortes rectangulares (W n) con cobertura de area exacta
(acumulacion con signo, estilo font-rs). Escribe PNG en escala de grises.

Uso:
  python vecrender.py archivo.pdf carpeta_salida [--dpi 200] [--pages 1-5,8]

No soporta: imagenes (Do se omite y se cuenta), sombreados, patrones,
modos de mezcla, transparencia, recortes no rectangulares, texto con fuentes.
"""
import math
import os
import struct
import sys
import time
import zlib


# ---------------------------------------------------------------- PNG
def png_bytes(w, h, pix):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += pix[y * w:(y + 1) * w]

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 6))
            + chunk(b'IEND', b''))


def write_png(path, w, h, pix):
    with open(path, 'wb') as f:
        f.write(png_bytes(w, h, pix))


# ------------------------------------------------- acumulacion de area
def _line(a, S, H, x0, y0, x1, y1):
    """Suma la contribucion de un borde con x dentro de [0, W]."""
    if y0 == y1:
        return
    if y0 < y1:
        d0 = 1.0
    else:
        d0 = -1.0
        x0, y0, x1, y1 = x1, y1, x0, y0
    if y1 <= 0 or y0 >= H:
        return
    dxdy = (x1 - x0) / (y1 - y0)
    x = x0
    if y0 < 0:
        x -= y0 * dxdy
        ys = 0
    else:
        ys = int(y0)
    ye = min(H, int(math.ceil(y1)))
    floor = math.floor
    ceil = math.ceil
    for y in range(ys, ye):
        ls = y * S
        top = y if y > y0 else y0
        bot = y + 1 if y + 1 < y1 else y1
        dy = bot - top
        xn = x + dxdy * dy
        d = dy * d0
        if x < xn:
            xa, xb = x, xn
        else:
            xa, xb = xn, x
        xaf = floor(xa)
        xai = int(xaf)
        xbc = ceil(xb)
        xbi = int(xbc)
        if xbi <= xai + 1:
            xmf = 0.5 * (x + xn) - xaf
            a[ls + xai] += d - d * xmf
            a[ls + xai + 1] += d * xmf
        else:
            s = 1.0 / (xb - xa)
            x0f = xa - xaf
            a0 = 0.5 * s * (1.0 - x0f) * (1.0 - x0f)
            x1f = xb - xbc + 1.0
            am = 0.5 * s * x1f * x1f
            a[ls + xai] += d * a0
            if xbi == xai + 2:
                a[ls + xai + 1] += d * (1.0 - a0 - am)
            else:
                a1 = s * (1.5 - x0f)
                a[ls + xai + 1] += d * (a1 - a0)
                for xi in range(xai + 2, xbi - 1):
                    a[ls + xi] += d * s
                a2 = a1 + (xbi - xai - 3) * s
                a[ls + xbi - 1] += d * (1.0 - a2 - am)
            a[ls + xbi] += d * am
        x = xn


def _edge(a, S, H, W, x0, y0, x1, y1):
    """Como _line, pero recorta el borde al rango horizontal [0, W]."""
    if x0 < 0 or x1 < 0 or x0 > W or x1 > W:
        if x0 <= 0 and x1 <= 0:
            _line(a, S, H, 0.0, y0, 0.0, y1)
            return
        if x0 >= W and x1 >= W:
            _line(a, S, H, float(W), y0, float(W), y1)
            return
        dx = x1 - x0
        ts = [0.0, 1.0]
        for bx in (0.0, float(W)):
            t = (bx - x0) / dx
            if 0.0 < t < 1.0:
                ts.append(t)
        ts.sort()
        for i in range(len(ts) - 1):
            ta, tb = ts[i], ts[i + 1]
            xa = x0 + dx * ta
            ya = y0 + (y1 - y0) * ta
            xb = x0 + dx * tb
            yb = y0 + (y1 - y0) * tb
            xm = 0.5 * (xa + xb)
            if xm < 0:
                xa = xb = 0.0
            elif xm > W:
                xa = xb = float(W)
            else:
                xa = min(max(xa, 0.0), float(W))
                xb = min(max(xb, 0.0), float(W))
            _line(a, S, H, xa, ya, xb, yb)
        return
    _line(a, S, H, x0, y0, x1, y1)


# ------------------------------------------------------------ pagina
class Canvas:
    def __init__(self, w_pt, h_pt, dpi):
        self.sc = dpi / 72.0
        self.W = max(1, int(round(w_pt * self.sc)))
        self.H = max(1, int(round(h_pt * self.sc)))
        self.pix = bytearray(b'\xff') * (self.W * self.H)

    def paint(self, subpaths, gray, evenodd, clip, stroke_gray=None, lw=0.0):
        """subpaths: lista de (puntos_dispositivo, cerrado)."""
        W, H = self.W, self.H
        minx = miny = 1e30
        maxx = maxy = -1e30
        for pts, _c in subpaths:
            for x, y in pts:
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
        if minx > maxx:
            return
        pad = (lw * 0.5 + 1.0) if stroke_gray is not None else 1.0
        X0 = max(0, int(math.floor(minx - pad)))
        Y0 = max(0, int(math.floor(miny - pad)))
        X1 = min(W, int(math.ceil(maxx + pad)))
        Y1 = min(H, int(math.ceil(maxy + pad)))
        cx0, cy0, cx1, cy1 = clip
        # recorte al rectangulo de clip (solo limita el pintado)
        px0 = max(X0, int(math.floor(cx0)))
        py0 = max(Y0, int(math.floor(cy0)))
        px1 = min(X1, int(math.ceil(cx1)))
        py1 = min(Y1, int(math.ceil(cy1)))
        if X1 <= X0 or Y1 <= Y0 or px1 <= px0 or py1 <= py0:
            return
        lw_ = X1 - X0
        lh_ = Y1 - Y0
        S = lw_ + 2

        acc = None
        if gray is not None:
            acc = [0.0] * (S * lh_)
            for pts, _c in subpaths:
                n = len(pts)
                if n < 2:
                    continue
                for i in range(n):
                    xa, ya = pts[i]
                    xb, yb = pts[(i + 1) % n]
                    _edge(acc, S, lh_, lw_, xa - X0, ya - Y0, xb - X0, yb - Y0)

        acc2 = None
        if stroke_gray is not None:
            acc2 = [0.0] * (S * lh_)
            hw = max(lw * 0.5, 0.35)
            for pts, closed in subpaths:
                n = len(pts)
                segs = n if closed else n - 1
                for i in range(segs):
                    xa, ya = pts[i]
                    xb, yb = pts[(i + 1) % n]
                    dx = xb - xa
                    dy = yb - ya
                    ln = math.hypot(dx, dy)
                    if ln < 1e-6:
                        continue
                    nx = -dy / ln * hw
                    ny = dx / ln * hw
                    q = ((xa + nx, ya + ny), (xb + nx, yb + ny),
                         (xb - nx, yb - ny), (xa - nx, ya - ny))
                    for k in range(4):
                        p0 = q[k]
                        p1 = q[(k + 1) & 3]
                        _edge(acc2, S, lh_, lw_, p0[0] - X0, p0[1] - Y0,
                              p1[0] - X0, p1[1] - Y0)

        pix = self.pix
        gf = gray
        gs = stroke_gray
        for row in range(py0, py1):
            base = (row - Y0) * S
            pbase = row * W
            r1 = 0.0
            r2 = 0.0
            for xi in range(lw_):
                if acc is not None:
                    r1 += acc[base + xi]
                if acc2 is not None:
                    r2 += acc2[base + xi]
                x = X0 + xi
                if x < px0 or x >= px1:
                    continue
                idx = pbase + x
                if acc is not None:
                    v = r1 if r1 >= 0 else -r1
                    if evenodd:
                        v = v % 2.0
                        if v > 1.0:
                            v = 2.0 - v
                    elif v > 1.0:
                        v = 1.0
                    if v > 0.004:
                        p = pix[idx]
                        pix[idx] = int(p + (gf - p) * v + 0.5)
                if acc2 is not None:
                    v = r2 if r2 >= 0 else -r2
                    if v > 1.0:
                        v = 1.0
                    if v > 0.004:
                        p = pix[idx]
                        pix[idx] = int(p + (gs - p) * v + 0.5)


# ------------------------------------------------- interprete de contenido
def _mul(m, c):
    return (m[0] * c[0] + m[1] * c[2],
            m[0] * c[1] + m[1] * c[3],
            m[2] * c[0] + m[3] * c[2],
            m[2] * c[1] + m[3] * c[3],
            m[4] * c[0] + m[5] * c[2] + c[4],
            m[4] * c[1] + m[5] * c[3] + c[5])


def _gray_rgb(r, g, b):
    return 255.0 * (0.299 * r + 0.587 * g + 0.114 * b)


class RenderTimeout(Exception):
    pass


def render_stream(canvas, content, base_ctm, stats, deadline=None):
    """Interpreta un flujo de contenido (str latin1) sobre el canvas."""
    ctm = base_ctm
    fill = 0.0
    strokec = 0.0
    lwu = 1.0
    clip = (0.0, 0.0, float(canvas.W), float(canvas.H))
    stack = []
    subs = []          # subtrazados ya cerrados/abiertos
    cur = None         # puntos del subtrazado actual
    cur_closed = False
    startpt = None
    lastpt = None
    pend_clip = False
    ops = []
    sc = canvas.sc

    def tr(x, y):
        c = ctm
        return (c[0] * x + c[2] * y + c[4], c[1] * x + c[3] * y + c[5])

    def flush_cur():
        nonlocal cur, cur_closed
        if cur is not None and len(cur) > 0:
            subs.append((cur, cur_closed))
        cur = None
        cur_closed = False

    def finish_path():
        nonlocal subs, cur, startpt, lastpt, pend_clip, clip
        flush_cur()
        if pend_clip:
            xs = [p[0] for s, _ in subs for p in s]
            ys = [p[1] for s, _ in subs for p in s]
            if xs:
                clip = (max(clip[0], min(xs)), max(clip[1], min(ys)),
                        min(clip[2], max(xs)), min(clip[3], max(ys)))
            pend_clip = False
        subs = []
        cur = None
        startpt = lastpt = None

    npaint = 0
    for tok in content.split():
        c0 = tok[0]
        if c0 in '0123456789.-+/' :
            ops.append(tok)
            continue
        op = tok
        try:
            if op == 'm':
                flush_cur()
                p = tr(float(ops[-2]), float(ops[-1]))
                cur = [p]
                startpt = lastpt = p
            elif op == 'l':
                p = tr(float(ops[-2]), float(ops[-1]))
                if cur is None:
                    cur = [p]
                    startpt = p
                else:
                    cur.append(p)
                lastpt = p
            elif op == 'c' or op == 'v' or op == 'y':
                if op == 'c':
                    p1 = tr(float(ops[-6]), float(ops[-5]))
                    p2 = tr(float(ops[-4]), float(ops[-3]))
                    p3 = tr(float(ops[-2]), float(ops[-1]))
                elif op == 'v':
                    p1 = lastpt
                    p2 = tr(float(ops[-4]), float(ops[-3]))
                    p3 = tr(float(ops[-2]), float(ops[-1]))
                else:
                    p1 = tr(float(ops[-4]), float(ops[-3]))
                    p3 = tr(float(ops[-2]), float(ops[-1]))
                    p2 = p3
                p0 = lastpt
                if cur is None:
                    cur = [p3]
                    startpt = p3
                else:
                    L = (math.hypot(p1[0] - p0[0], p1[1] - p0[1])
                         + math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                         + math.hypot(p3[0] - p2[0], p3[1] - p2[1]))
                    n = int(L / 2.0) + 2
                    if n > 24:
                        n = 24
                    x0, y0 = p0
                    for i in range(1, n):
                        t = i / n
                        u = 1.0 - t
                        a_ = u * u * u
                        b_ = 3 * u * u * t
                        c_ = 3 * u * t * t
                        d_ = t * t * t
                        cur.append((a_ * x0 + b_ * p1[0] + c_ * p2[0] + d_ * p3[0],
                                    a_ * y0 + b_ * p1[1] + c_ * p2[1] + d_ * p3[1]))
                    cur.append(p3)
                lastpt = p3
            elif op == 'h':
                if cur is not None:
                    cur_closed = True
                    flush_cur()
                    # un nuevo 'l' sin 'm' parte del punto inicial
                    cur = None
                    lastpt = startpt
            elif op == 're':
                x, y, w, h = (float(v) for v in ops[-4:])
                flush_cur()
                subs.append(([tr(x, y), tr(x + w, y), tr(x + w, y + h),
                              tr(x, y + h)], True))
                startpt = lastpt = tr(x, y)
            elif op in ('f', 'F', 'f*', 'B', 'B*', 'b', 'b*', 'S', 's'):
                if op in ('b', 'b*', 's') and cur is not None:
                    cur_closed = True
                flush_cur()
                eo = op.endswith('*')
                do_fill = op in ('f', 'F', 'f*', 'B', 'B*', 'b', 'b*')
                do_stroke = op in ('B', 'B*', 'b', 'b*', 'S', 's')
                npaint += 1
                if deadline and (npaint & 511) == 0 and time.time() > deadline:
                    raise RenderTimeout('tiempo agotado al dibujar la pagina')
                if subs:
                    lwd = lwu * math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]))
                    canvas.paint(subs, fill if do_fill else None, eo, clip,
                                 strokec if do_stroke else None, lwd)
                    stats['paths'] = stats.get('paths', 0) + 1
                pend = pend_clip
                finish_path()
            elif op == 'n':
                finish_path()
            elif op == 'W' or op == 'W*':
                pend_clip = True
                ops = []
                continue
            elif op == 'q':
                stack.append((ctm, fill, strokec, lwu, clip))
            elif op == 'Q':
                if stack:
                    ctm, fill, strokec, lwu, clip = stack.pop()
            elif op == 'cm':
                m = tuple(float(v) for v in ops[-6:])
                ctm = _mul(m, ctm)
            elif op == 'rg':
                fill = _gray_rgb(*(float(v) for v in ops[-3:]))
            elif op == 'RG':
                strokec = _gray_rgb(*(float(v) for v in ops[-3:]))
            elif op == 'g':
                fill = 255.0 * float(ops[-1])
            elif op == 'G':
                strokec = 255.0 * float(ops[-1])
            elif op == 'k':
                c_, m_, y_, k_ = (float(v) for v in ops[-4:])
                fill = 255.0 * (1 - c_) * (1 - k_) * 0.3 + 255.0 * (1 - k_) * 0.7 * (1 - (c_ + m_ + y_) / 3)
            elif op == 'K':
                c_, m_, y_, k_ = (float(v) for v in ops[-4:])
                strokec = 255.0 * (1 - k_) * (1 - (c_ + m_ + y_) / 3)
            elif op == 'w':
                lwu = float(ops[-1])
            elif op == 'Do':
                stats['images_skipped'] = stats.get('images_skipped', 0) + 1
            elif op in ('J', 'j', 'M', 'd', 'i', 'ri', 'gs', 'cs', 'CS',
                        'sc', 'scn', 'SC', 'SCN'):
                if op in ('cs', 'CS', 'sc', 'scn', 'SC', 'SCN', 'gs'):
                    stats['ignored_' + op] = stats.get('ignored_' + op, 0) + 1
            elif op in ('BT', 'ET', 'Tj', 'TJ', 'Tf', 'Td', 'Tm', 'T*', 'Tc',
                        'Tw', 'Tz', 'TL', 'Tr', 'Ts', 'TD', "'", '"'):
                stats['text_ops'] = stats.get('text_ops', 0) + 1
            else:
                stats['unknown_' + op] = stats.get('unknown_' + op, 0) + 1
        except (ValueError, IndexError, TypeError) as e:
            stats['errors'] = stats.get('errors', 0) + 1
        ops = []


def render_page(page, dpi=200, max_pixels=12000000, max_seconds=0):
    """Devuelve (ancho, alto, bytearray gris, stats) de un objeto pagina de pypdf.
    Respeta /Rotate; baja los dpi si la pagina excede max_pixels."""
    mb = page.mediabox
    llx, lly, urx, ury = (float(mb.left), float(mb.bottom),
                          float(mb.right), float(mb.top))
    w_pt, h_pt = urx - llx, ury - lly
    if w_pt <= 0 or h_pt <= 0:
        raise ValueError('MediaBox invalida')
    scale = dpi / 72.0
    if w_pt * h_pt * scale * scale > max_pixels:
        scale = math.sqrt(max_pixels / (w_pt * h_pt))
        dpi = scale * 72.0
    try:
        rot = int(page.rotation) % 360
    except Exception:
        rot = int(page.get('/Rotate', 0) or 0) % 360
    cv = Canvas(w_pt, h_pt, dpi)
    sc = cv.sc
    base = (sc, 0.0, 0.0, -sc, -llx * sc, ury * sc)
    W0, H0 = cv.W, cv.H
    if rot in (90, 180, 270):
        if rot == 90:
            R = (0.0, 1.0, -1.0, 0.0, float(H0), 0.0)
            nw, nh = H0, W0
        elif rot == 180:
            R = (-1.0, 0.0, 0.0, -1.0, float(W0), float(H0))
            nw, nh = W0, H0
        else:
            R = (0.0, -1.0, 1.0, 0.0, 0.0, float(W0))
            nw, nh = H0, W0
        base = _mul(base, R)
        cv.W, cv.H = nw, nh
        cv.pix = bytearray(b'\xff') * (nw * nh)
    stats = {}
    data = page.get_contents()
    content = data.get_data().decode('latin1') if data is not None else ''
    deadline = (time.time() + max_seconds) if max_seconds else None
    render_stream(cv, content, base, stats, deadline)
    return cv.W, cv.H, cv.pix, stats


def _parse_pages(spec, n):
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(','):
        if '-' in part:
            a, b = part.split('-')
            out += list(range(int(a) - 1, min(int(b), n)))
        else:
            out.append(int(part) - 1)
    return [i for i in out if 0 <= i < n]


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('salida')
    ap.add_argument('--dpi', type=int, default=200)
    ap.add_argument('--pages', default='')
    a = ap.parse_args(argv)
    import pypdf
    reader = pypdf.PdfReader(a.pdf)
    os.makedirs(a.salida, exist_ok=True)
    idxs = _parse_pages(a.pages, len(reader.pages))
    total = 0.0
    for i in idxs:
        t0 = time.time()
        w, h, pix, st = render_page(reader.pages[i], a.dpi)
        t1 = time.time()
        out = os.path.join(a.salida, 'p%03d.png' % (i + 1))
        write_png(out, w, h, pix)
        dt = t1 - t0
        total += dt
        print('pagina %d: %dx%d  render %.1fs  png %.1fs  %s' % (
            i + 1, w, h, dt, time.time() - t1, st), flush=True)
    print('total render %.1fs, %d paginas' % (total, len(idxs)))


if __name__ == '__main__':
    main(sys.argv[1:])
