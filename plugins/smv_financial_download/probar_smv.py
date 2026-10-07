#!/usr/bin/env python3
"""Prueba el portal SMV desde la consola, sin ChaskiFlow:
    python plugins\\smv_financial_download\\probar_smv.py ALICORP 2022 [--descargar carpeta] [--sin-ssl] [--proxy http://...]
Lista los documentos de esa empresa y año (y baja el que corresponda si se indica --descargar)."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smvlib import Portal, norm, safe_name  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("empresa", help="parte del nombre")
ap.add_argument("anio", type=int)
ap.add_argument("--consolidada", action="store_true")
ap.add_argument("--descargar", default="", help="carpeta donde guardar «Estados Financieros y Dictamen»")
ap.add_argument("--sin-ssl", action="store_true")
ap.add_argument("--proxy", default="")
a = ap.parse_args()
p = Portal(verify_ssl=not a.sin_ssl, proxy=a.proxy)
cs = p.open()
print("%d empresas en el portal" % len(cs))
hits = [c for c in cs if norm(a.empresa) in norm(c[1])]
for c in hits:
    print("-", c[0], c[1])
if not hits:
    sys.exit("Ninguna empresa coincide")
c = hits[0]
print("\nBuscando:", c[1], a.anio)
for d in p.search(c[0], c[1], a.anio, tipo="C" if a.consolidada else "I"):
    print("  %-40s %-12s %s  %s" % (d["documento"][:40], d["expediente"], d["fecha"], d["url"]))
    if a.descargar and norm(d["documento"]) == norm("Estados Financieros y Dictamen"):
        os.makedirs(a.descargar, exist_ok=True)
        dest = os.path.join(a.descargar, "%s_%d_%s.pdf" % (safe_name(c[1], 30).replace(" ", "_"), a.anio, d["expediente"]))
        print("   -> %d bytes en %s" % (p.download(d["url"], dest), dest))
