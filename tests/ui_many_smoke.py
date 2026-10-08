"""Muchos workflows: buscador en la barra ancha; en la reducida solo recientes + selector con búsqueda."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer
from playwright.sync_api import sync_playwright
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(), "")
srv = TestServer(plugin_dirs=[str(ROOT / "plugins")])
problems = []
def check(c, m):
    print(("OK   " if c else "FAIL ") + m)
    if not c: problems.append(m)
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    for i in range(12):
        c.post("/api/workflows", {"name": "Noticias %02d" % i if i < 11 else "Sucursales", "definition": {"nodes": [], "edges": []}})
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1300, "height": 800}).new_page()
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".wf-item")
        check(pg.locator(".wf-item:visible").count() == 12, "barra ancha: 12 workflows")
        check(pg.locator(".sidebar .sb-find:visible").count() == 0 and pg.locator(".sidebar .sb-imp:visible").count() == 1, "barra ancha: sin botón 🔍 (hay cuadro de búsqueda) y con Importar")
        pg.screenshot(path=OUT + "m0_ancha.png")
        pg.fill(".sb-search input", "sucurs")
        check(pg.locator(".wf-item:visible").count() == 1, "el buscador filtra la lista")
        pg.fill(".sb-search input", "zzz"); check("Ningún workflow" in pg.inner_text(".sidebar .list"), "mensaje si nada coincide")
        pg.fill(".sb-search input", "")
        for n in ("Noticias 00", "Noticias 01", "Noticias 02", "Noticias 03", "Noticias 04", "Noticias 05", "Sucursales"):
            pg.locator(".wf-item", has_text=n).first.click(); pg.wait_for_selector(".wf-bar .title"); pg.wait_for_timeout(120)
        pg.click(".topbar .panel-toggle"); pg.wait_for_timeout(200)
        n_rail = pg.locator(".sidebar .wf-item:visible").count()
        check(n_rail == 5, "barra reducida: solo los 5 recientes (%d de 12)" % n_rail)
        check(pg.locator(".sidebar .sb-find:visible").count() == 1 and pg.locator(".sidebar .sb-search:visible").count() == 0, "reducida: botón de búsqueda en vez del cuadro")
        pg.screenshot(path=OUT + "m1_reducida.png")
        pg.click(".sidebar .sb-find"); pg.wait_for_selector(".picker input")
        check(pg.locator(".picker .pk-item").count() == 12, "el selector lista los 12")
        pg.fill(".picker input", "noticias 09"); check(pg.locator(".picker .pk-item").count() == 1, "el selector filtra")
        pg.keyboard.press("Enter"); import time
        for _ in range(60):
            if pg.input_value(".wf-bar .title") == "Noticias 09": break
            time.sleep(0.1)
        else: raise AssertionError("no abrió Noticias 09")
        check(True, "Enter abre el workflow elegido")
        check(pg.locator(".sidebar .wf-item.active:visible").count() == 1, "el abierto aparece en la columna aunque no fuera reciente")
        b.close()
finally:
    srv.stop()
print("PROBLEMAS: %s" % problems if problems else "OK: todo bien"); sys.exit(1 if problems else 0)
