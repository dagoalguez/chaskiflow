"""Diagnóstico: prueba el extractor sobre una URL real (úselo en la PC de la oficina).

    python plugins\\news_feed_scrape\\probar_url.py https://rpp.pe/...nota
    python plugins\\news_feed_scrape\\probar_url.py https://rpp.pe/sitemap/news --feed
Opciones:  --ca ruta.pem   --sin-ssl   --proxy http://host:puerto
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from newslib import FetchError, Fetcher, extract_article, parse_feed  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--feed", action="store_true", help="la URL es un feed/portada: lista lo que encuentra")
    ap.add_argument("--ca", default="")
    ap.add_argument("--sin-ssl", action="store_true")
    ap.add_argument("--proxy", default="")
    a = ap.parse_args()
    f = Fetcher(verify_ssl=not a.sin_ssl, ca_bundle=a.ca, proxy=a.proxy, retries=0)
    try:
        text = f.get(a.url)
    except FetchError as e:
        print("ERROR (%s): %s" % (e.kind, e))
        return 1
    print("Descargado: %d caracteres" % len(text))
    if a.feed:
        items = parse_feed(text, "auto", a.url, fetch=f.get)
        print("Items: %d" % len(items))
        for it in items[:15]:
            print("  %s | %s | %s" % (it["fecha_raw"][:25], it["titulo"][:60], it["url"]))
        return 0
    r = extract_article(text)
    print("Estrategia: %s | Título: %s | Fecha: %s | Texto: %d caracteres" %
          (r["estrategia"], r["titulo"], r["fecha"], len(r["texto"])))
    print("-" * 60)
    print(r["texto"][:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
