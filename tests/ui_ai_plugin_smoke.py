"""Prueba opcional en navegador: Plugins -> «Crear con IA» (prompt + importar).
Uso:  python tests/ui_ai_plugin_smoke.py [carpeta_de_capturas]   (CHROMIUM_PATH=ruta si hace falta)"""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer
from tests.test_plugin_import import BUNDLE
from playwright.sync_api import sync_playwright
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(), "")
srv = TestServer()
problems = []
def check(c, m):
    print(("OK   " if c else "FAIL ") + m)
    if not c: problems.append(m)
def until(fn, t=8000):
    t0 = time.time()
    while time.time() - t0 < t / 1000:
        try:
            if fn(): return True
        except Exception: pass
        time.sleep(0.1)
    raise AssertionError("tiempo agotado")
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1400, "height": 850}).new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text and "400" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".topbar"); pg.click("text=Plugins"); pg.wait_for_selector(".dialog table")
        pg.click("text=Crear con IA"); pg.wait_for_selector("text=Crear un plugin con IA")
        ov = pg.locator(".overlay").last
        until(lambda: "plugin.json" in ov.locator("textarea").first.input_value())
        check(True, "el prompt se carga en el diálogo")
        ov.locator("button", has_text="Instalar plugin").click()
        until(lambda: ov.locator(".help").last.inner_text().strip() not in ("", "…"))
        check("nada que importar" in ov.inner_text().lower() or "no hay nada" in ov.inner_text().lower(), "pegar vacío da un error claro")
        ov.locator("textarea").nth(1).fill("=== plugin.json ===\n{\"id\":\"x_y\"}\n=== task.py ===\ndef run(config, ctx)\n  pass\n")
        ov.locator("button", has_text="Instalar plugin").click()
        until(lambda: "compila" in ov.inner_text())
        check(True, "código con error de sintaxis se rechaza con mensaje")
        ov.locator("textarea").nth(1).fill(BUNDLE)
        ov.locator("button", has_text="Instalar plugin").click()
        until(lambda: pg.locator(".dialog tr", has_text="ia_saludo").count() > 0)
        row = pg.locator(".dialog tr", has_text="ia_saludo")
        check("Pendiente" in row.inner_text() or "pendiente" in row.inner_text().lower(), "el plugin importado queda pendiente: " + row.inner_text().replace("\n", " ")[:80])
        pg.screenshot(path=OUT + "ai1.png")
finally:
    srv.stop()
print("PROBLEMAS: %s" % problems if problems else "TODO OK")
sys.exit(1 if problems else 0)
