"""Prueba opcional en navegador: al cambiar de workflow mientras otro corre, la ejecución sigue y al volver
la pantalla se reconecta al avance en vivo; la barra lateral marca el que está corriendo.
Uso: python tests/ui_reconnect_smoke.py [carpeta_capturas]  (CHROMIUM_PATH=ruta)"""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer
from playwright.sync_api import sync_playwright
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(), "")
srv = TestServer(scheduler_enabled=False)
problems = []
def check(c, m):
    print(("OK   " if c else "FAIL ") + m)
    if not c: problems.append(m)
def until(fn, t=15000):
    t0 = time.time()
    while time.time() - t0 < t / 1000:
        try:
            if fn(): return True
        except Exception: pass
        time.sleep(0.1)
    raise AssertionError("tiempo agotado")
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    c.post("/api/plugins/slow/enable"); c.post("/api/plugins/hello_world/enable")
    lento = {"nodes": [{"id": "a", "label": "Lento", "type": "slow", "config": {"seconds": 6}}], "edges": []}
    rapido = {"nodes": [{"id": "a", "label": "A", "type": "hello_world", "config": {}}], "edges": []}
    w1 = c.post("/api/workflows", {"name": "Lento", "definition": lento})[1]["workflow"]["id"]
    w2 = c.post("/api/workflows", {"name": "Rapido", "definition": rapido})[1]["workflow"]["id"]
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1400, "height": 850}).new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".wf-item")
        pg.click(".wf-item >> text=Lento"); pg.wait_for_selector(".gsvg")
        pg.click("#runbtn")
        until(lambda: pg.locator(".wf-item:has-text('Lento') .dot.running, .wf-item:has-text('Lento') .dot.queued").count() == 1)
        check(True, "la barra lateral marca «Lento» como en curso")
        pg.click(".wf-item >> text=Rapido"); pg.wait_for_selector(".gsvg")
        check(pg.locator("#runbtn").is_enabled(), "en otro workflow el botón Ejecutar sigue habilitado")
        pg.click("#runbtn"); until(lambda: pg.locator(".rp-body .hi").count() >= 1)
        check(True, "se puede ejecutar el segundo workflow mientras el primero corre")
        pg.click(".wf-item >> text=Lento"); pg.wait_for_selector(".gsvg")
        until(lambda: pg.locator(".gnode.st-running").count() == 1)
        check(True, "al volver, el grafo muestra el nodo en ejecución (reconectado)")
        check(not pg.locator("#stopbtn").is_hidden(), "el botón Detener aparece al volver")
        pg.screenshot(path=OUT + "r1_reconectado.png")
        until(lambda: pg.locator(".gnode.st-ok").count() == 1, 20000)
        check(True, "la ejecución termina y el grafo queda en verde")
        until(lambda: pg.locator(".wf-item:has-text('Lento') .dot.ok").count() == 1)
        check(True, "la barra lateral pasa a verde al terminar")
        b.close()
finally:
    srv.stop()
print("PROBLEMAS: %s" % problems if problems else "OK: todo bien"); sys.exit(1 if problems else 0)
