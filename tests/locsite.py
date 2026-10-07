"""Sitio de prueba con las formas habituales de publicar sucursales."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = """<html><head><title>Ferretería Andina</title></head><body>
<nav><a href="/productos">Productos</a><a href="/ubicanos">Ubícanos</a><a href="/blog">Blog</a></nav>
<h1>Ferretería Andina</h1><p>Todo para tu obra.</p>
<footer><a href="/privado/intranet">Intranet</a><a href="https://externo.example.com/ubicanos">Externo</a>
<a href="/catalogo.pdf">Catálogo</a><a href="/blog/pagina/2">Más</a></footer></body></html>"""

UBICANOS = """<html><head><title>Ubícanos - Ferretería Andina</title></head><body>
<h1>Nuestras tiendas</h1>
<select id="distrito"><option value="">Elige distrito</option>
<option value="/tiendas/miraflores">Miraflores</option><option value="/tiendas/surco">Santiago de Surco</option>
<option value="/tiendas/arequipa">Arequipa</option></select>
<p>Encuentra la tienda más cercana.</p></body></html>"""

MIRAFLORES = """<html><head><title>Tienda Miraflores</title></head><body><h1>Tienda Miraflores</h1>
<address>Av. Larco 1234, Miraflores, Lima. Tel: (01) 445-1234</address>
<p>Horario: Lun a Sáb 9am - 7pm</p></body></html>"""

SURCO = """<html><head><title>Tienda Surco</title>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"HardwareStore","name":"Ferretería Andina Surco",
"telephone":"+51 1 555 0101","address":{"@type":"PostalAddress","streetAddress":"Av. Primavera 890","addressLocality":"Santiago de Surco",
"addressRegion":"Lima","addressCountry":"PE"},"geo":{"@type":"GeoCoordinates","latitude":-12.1,"longitude":-77.0}}</script>
</head><body><h1>Tienda Surco</h1></body></html>"""

AREQUIPA = """<html><head><title>Tienda Arequipa</title></head><body><h1>Tienda Arequipa</h1>
<p>Calle Mercaderes 345, Cercado, Arequipa</p>
<iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3!2d-71.5375!3d-16.3989!2m3!1f0"></iframe></body></html>"""

LOCALES = """<html><head><title>Locales</title></head><body><h1>Puntos de venta</h1><div id="map"></div>
<script>var tiendas = [{"nombre":"Andina Callao","direccion":"Jr. Constitución 456, Callao","lat":-12.05,"lng":-77.12,"telefono":"01 429 0000"},
{"nombre":"Andina Trujillo","direccion":"Av. España 777, Trujillo","lat":-8.11,"lng":-79.03}];
fetch("/api/stores.json").then(function(r){return r.json();});</script></body></html>"""

STORES_JSON = json.dumps({"stores": [{"title": "Andina Piura", "address": "Av. Grau 100", "city": "Piura", "latitude": "-5.19", "longitude": "-80.63"}]})

BLOG2 = '<html><head><title>Blog 2</title></head><body><a href="/blog/pagina/3">3</a><a href="/blog/pagina/2">2</a></body></html>'


class Site:
    def __init__(self, ubicanos_extra=""):
        S = self
        S.hits = []
        S.extra = ubicanos_extra

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def send(self, code, body, ctype="text/html; charset=utf-8"):
                b = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                p = self.path.split("?")[0]
                S.hits.append(p)
                pages = {"/": HOME, "/ubicanos": UBICANOS.replace("<p>Encuentra", S.extra + "<p>Encuentra") if S.extra else UBICANOS,
                         "/tiendas/miraflores": MIRAFLORES, "/tiendas/surco": SURCO, "/tiendas/arequipa": AREQUIPA,
                         "/productos": '<html><title>Productos</title><body><a href="/locales">Locales</a></body></html>',
                         "/locales": LOCALES}
                if p == "/robots.txt":
                    return self.send(200, "User-agent: *\nDisallow: /privado/\nSitemap: %s/sitemap.xml\n" % S.base, "text/plain")
                if p == "/sitemap.xml":
                    return self.send(200, '<urlset><url><loc>%s/tiendas/miraflores</loc></url><url><loc>%s/blog/pagina/2</loc></url></urlset>' % (S.base, S.base), "application/xml")
                if p == "/api/stores.json":
                    return self.send(200, STORES_JSON, "application/json")
                if p.startswith("/blog/pagina/"):
                    return self.send(200, BLOG2)
                if p == "/blog":
                    return self.send(200, '<html><title>Blog</title><body><a href="/blog/pagina/2">2</a></body></html>')
                if p.startswith("/privado"):
                    return self.send(200, "<html><body>Av. Secreta 1, Lima</body></html>")
                if p in pages:
                    return self.send(200, pages[p])
                self.send(404, "no")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
