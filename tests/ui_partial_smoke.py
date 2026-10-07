"""Prueba opcional en navegador: ejecutar un paso, hasta un paso o desde un paso desde el grafo.
Uso:  python tests/ui_partial_smoke.py [carpeta_de_capturas]   (CHROMIUM_PATH=ruta si hace falta)"""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer
from playwright.sync_api import sync_playwright
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(), "")
srv = TestServer()
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
        time.sleep(0.15)
    raise AssertionError("tiempo agotado")
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    d = {"nodes": [
        {"id": "a", "label": "A", "type": "hello_world", "config": {"filas": 2}, "position": {"x": 40, "y": 60}},
        {"id": "b", "label": "B", "type": "hello_world", "config": {"nombre": "{{A.result.mensaje}}"}, "position": {"x": 340, "y": 60}},
        {"id": "c", "label": "C", "type": "hello_world", "config": {"nombre": "{{B.result.mensaje}}"}, "position": {"x": 640, "y": 60}}],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]}
    wid = c.post("/api/workflows", {"name": "Parcial", "definition": d})[1]["workflow"]["id"]
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1500, "height": 850}).new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text and "409" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".wf-item"); pg.click(".wf-item"); pg.wait_for_selector(".gnode")
        check(pg.locator(".gplay").count() == 0, "sin nodo seleccionado no hay botones de ejecución parcial")
        nodes = pg.locator(".gnode")
        nodes.nth(1).click(); pg.wait_for_selector(".gplay")
        pg.click(".gplay >> text=Este paso")           # B sin ejecución previa de A -> explica
        pg.wait_for_selector(".toast"); check("necesita el resultado de: A" in pg.inner_text(".toast"), "mensaje claro si falta el resultado previo: " + pg.inner_text(".toast")[:90])
        pg.click(".gplay >> text=Hasta aquí")           # A y B
        until(lambda: pg.locator(".rp-body .msg.ok").count() >= 2)
        check(pg.locator(".rp-body .msg.ok").count() == 2 and "Ejecución parcial" in pg.inner_text(".rp-body"), "«Hasta aquí» ejecuta A y B")
        until(lambda: pg.locator("#stopbtn.hidden").count() == 1)
        pg.locator(".gnode").nth(2).click(); pg.wait_for_selector(".gplay")
        pg.click(".gplay >> text=Este paso")            # C reutiliza B
        until(lambda: "Reutiliza el resultado de B" in pg.inner_text(".rp-body"))
        until(lambda: pg.locator(".rp-body .msg.ok").count() >= 1)
        check(True, "«Este paso» reutiliza el resultado anterior")
        pg.screenshot(path=OUT + "pp1.png")
        until(lambda: pg.locator("#stopbtn.hidden").count() == 1)
        runs = c.get("/api/workflows/%d/runs" % wid)[1]["runs"]
        check(len(runs) == 2, "2 ejecuciones registradas (la 409 no crea ejecución): %d" % len(runs))
        b.close()
finally:
    srv.stop()
print("PROBLEMAS:", problems)
