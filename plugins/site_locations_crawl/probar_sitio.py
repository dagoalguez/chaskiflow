#!/usr/bin/env python3
"""Prueba el rastreo de UN sitio desde la consola, sin ChaskiFlow:
    python plugins\\site_locations_crawl\\probar_sitio.py https://www.ejemplo.pe [--paginas 30] [--sin-ssl]
Imprime los candidatos de dirección y los textos de las páginas de ubicación."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sitelib import Fetcher, KEYWORDS, crawl_site  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("url")
ap.add_argument("--paginas", type=int, default=30)
ap.add_argument("--profundidad", type=int, default=3)
ap.add_argument("--sin-ssl", action="store_true", help="no verificar certificados")
ap.add_argument("--proxy", default="")
a = ap.parse_args()
f = Fetcher(verify_ssl=not a.sin_ssl, proxy=a.proxy)
r = crawl_site(a.url, a.url, {"max_pages": a.paginas, "max_depth": a.profundidad, "keywords": KEYWORDS},
               f, progress=lambda n, u: print("  [%d] %s" % (n, u), file=sys.stderr))
print(json.dumps({k: v for k, v in r.items()}, ensure_ascii=False, indent=2))
