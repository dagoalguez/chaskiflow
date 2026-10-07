"""Prueba opcional en navegador: logo, cerrar workflow, borrar ejecuciones, papelera definitiva, barra lateral,
hora legible en modo oscuro.  Uso: python tests/ui_cleanup_smoke.py [carpeta_capturas]  (CHROMIUM_PATH=ruta)"""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer, wait_run
from playwright.sync_api import sync_playwright
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(), "")
srv = TestServer(scheduler_enabled=False)
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
def rgb(s): return [int(x) for x in s[s.index("(") + 1:s.index(")")].split(",")[:3]]
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    c.post("/api/plugins/hello_world/enable")
    D = {"nodes": [{"id": "a", "label": "A", "type": "hello_world", "config": {}}], "edges": []}
    w1 = c.post("/api/workflows", {"name": "Uno", "definition": D})[1]["workflow"]["id"]
    w2 = c.post("/api/workflows", {"name": "Dos", "definition": D})[1]["workflow"]["id"]
    for _ in range(3):
        wait_run(c, c.post("/api/workflows/%d/run" % w1, {})[1]["run_id"])
    c.delete("/api/workflows/%d" % w2)
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1400, "height": 850}).new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base)
        pg.wait_for_selector("img.login-logo"); until(lambda: pg.eval_on_selector("img.login-logo", "i => i.complete && i.naturalWidth > 0"))
        check(True, "logo en el login")
        pg.wait_for_selector(".about-login")
        check("Diego Guevara B." in pg.inner_text(".about-login") and "Apache-2.0" in pg.inner_text(".about-login"), "créditos en el login: " + pg.inner_text(".about-login"))
        pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".wf-item")
        check(pg.eval_on_selector(".topbar img.logo", "i => i.complete && i.naturalWidth > 0"), "logo en la barra superior")
        check(pg.get_attribute("link[rel=icon]", "href") == "/static/logo.svg", "icono de la pestaña")
        secs = pg.locator(".sb-foot .sb-sec").all_inner_texts()
        check(len(secs) == 2 and pg.locator(".sb-foot .sb-link").count() == 6, "barra lateral ordenada en 2 grupos: %s" % secs)
        check("Diego Guevara B." in pg.inner_text(".about-side"), "créditos al pie de la barra lateral")
        pg.click(".about-side"); pg.wait_for_selector("text=Acerca de ChaskiFlow")
        check("Contribuciones" in pg.inner_text(".dialog") and "Claude" in pg.inner_text(".dialog"), "diálogo Acerca de con autor y contribuciones")
        pg.screenshot(path=OUT + "c0_acerca.png"); pg.click(".dialog .x")
        pg.screenshot(path=OUT + "c1_lateral.png")
        # cerrar workflow
        pg.click(".wf-item >> text=Uno"); pg.wait_for_selector(".gsvg")
        pg.click(".close-wf"); pg.wait_for_selector(".empty")
        check(pg.locator(".wf-item.active").count() == 0, "✕ cierra el workflow y vuelve a la pantalla inicial")
        # borrar ejecuciones
        pg.click(".wf-item >> text=Uno"); pg.wait_for_selector(".gsvg")
        until(lambda: pg.locator(".rp-body .hi").count() == 3)
        check(pg.locator(".gnode[class*=st-]").count() == 0, "sin ejecución abierta el grafo no tiene colores de estado")
        pg.click(".rp-body .hi >> nth=0"); pg.wait_for_selector(".rp-body .msg")
        until(lambda: pg.locator(".gnode.st-ok").count() == 1)
        check(True, "al abrir una ejecución del historial el grafo muestra sus colores (nodo ok)")
        pg.click("text=← Historial"); until(lambda: pg.locator(".gnode[class*=st-]").count() == 0)
        check(True, "al volver al historial el grafo se limpia")
        pg.locator(".rp-body .hi").first.hover(); pg.locator(".rp-body .hi .del").first.click()
        pg.click(".overlay .btn.danger"); until(lambda: pg.locator(".rp-body .hi").count() == 2)
        check(True, "borrar una ejecución del historial (3 → 2)")
        pg.click("text=Ejecuciones >> nth=0") if False else None
        pg.click(".rp-body button[title*='Limpiar']"); pg.wait_for_selector("text=Limpiar historial")
        pg.fill(".overlay input[type=number]", "1"); pg.locator(".overlay .btn.danger").last.click()
        until(lambda: pg.locator(".rp-body .hi").count() == 1)
        check(True, "limpiar historial conservando 1")
        pg.click(".rp-body .hi >> nth=0"); pg.wait_for_selector("text=Eliminar esta ejecución")
        pg.click("text=Eliminar esta ejecución"); pg.click(".overlay .btn.danger")
        until(lambda: pg.locator(".rp-body .hi").count() == 0)
        check(True, "eliminar desde el detalle de la ejecución")
        # modo oscuro + hora
        pg.evaluate("document.documentElement.setAttribute('data-theme','dark')")
        pg.click(".wf-item >> text=Uno"); pg.wait_for_selector(".gsvg")
        pg.click(".wf-bar >> text=⋯"); pg.click(".dialog >> text=Programar"); pg.wait_for_selector(".dialog >> text=Nueva programación")
        pg.wait_for_selector(".overlay input[type=time]")
        col = pg.eval_on_selector(".overlay input[type=time]", "e => [getComputedStyle(e).color, getComputedStyle(e).backgroundColor]")
        fg, bg = rgb(col[0]), rgb(col[1])
        lum = lambda x: 0.2126 * x[0] + 0.7152 * x[1] + 0.0722 * x[2]
        check(abs(lum(fg) - lum(bg)) > 100, "hora del servidor legible en oscuro: texto %s sobre fondo %s" % (col[0], col[1]))
        pg.screenshot(path=OUT + "c3_hora_oscuro.png")
        for o in pg.locator(".overlay .x").all(): o.click()
        # papelera
        pg.click(".sb-link >> text=Papelera"); pg.wait_for_selector("text=Dos")
        pg.click("button:has-text('Eliminar definitivamente')"); pg.wait_for_selector(".overlay >> nth=1")
        pg.locator(".overlay").last.locator(".btn.danger").click()
        until(lambda: pg.locator("text=La papelera está vacía").count() == 1)
        check(True, "eliminar definitivamente desde la papelera")
        pg.screenshot(path=OUT + "c4_papelera.png")
        check(c.get("/api/workflows/trash")[1]["workflows"] == [], "la API confirma papelera vacía")
finally:
    srv.stop()
print("PROBLEMAS: %s" % problems if problems else "TODO OK")
sys.exit(1 if problems else 0)
