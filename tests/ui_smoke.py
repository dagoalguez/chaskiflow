import sys
"""Prueba opcional de la interfaz en un navegador real (requiere `pip install playwright` y Chromium).
No forma parte de run_all.py (la batería principal es solo librería estándar).
Uso:  python tests/ui_smoke.py [carpeta_de_capturas]"""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer
from playwright.sync_api import sync_playwright
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(), "")
srv = TestServer(plugin_dirs=[str(ROOT / "plugins")])
errors = []
def check(c, m):
    print(("OK   " if c else "FAIL ") + m)
    if not c: errors.append(m)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        ctx = b.new_context(locale="es-PE", viewport={"width": 1366, "height": 800}); pg = ctx.new_page()
        pg.on("console", lambda m: errors.append("console: " + m.text) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.wait_for_selector("#lg-user")
        pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.fill("#lg-dn", "Admin")
        pg.click("button[type=submit]"); pg.wait_for_selector(".sidebar")
        pg.click("text=+ Nuevo"); pg.fill(".dialog input", "Mi prueba"); pg.keyboard.press("Enter")
        pg.wait_for_selector(".wf-bar")
        for plug in ("hello_world", "export_csv"):
            pg.select_option(".gtools select", plug); pg.wait_for_timeout(250)
        pg.wait_for_selector(".inspector .card[data-node]")
        card = pg.locator(".inspector .card[data-node]")
        card.locator(".deps label.chk", has_text="Holamundo").locator("input").check()
        pg.wait_for_timeout(200)
        check(pg.locator(".gedge-hit").count() == 1, "dependencia creada desde el inspector")
        # Datos del csv: referencia con chip
        ta = card.locator("textarea").first
        ta.click()
        card.locator("summary", has_text="Insertar referencia").click()
        card.locator(".chip", has_text="{{Holamundo.result.rows}}").click()
        check("{{Holamundo.result.rows}}" in ta.input_value(), "chip inserta referencia")
        card.locator("input[data-ref]").nth(0).fill("%s/ui_out" % srv.tmp)  # output_dir (primer input de texto)
        pg.wait_for_timeout(1700)
        check(pg.inner_text("#savestate") == "Guardado", "autoguardado")
        pg.click("text=Validar"); pg.wait_for_selector(".problems")
        print("validar:", pg.inner_text(".problems").replace("\n", " | "))
        pg.click("#runbtn")
        pg.wait_for_selector(".dk-step.ok >> nth=1", timeout=20000)
        pg.wait_for_timeout(1200)
        pg.screenshot(path=OUT + "04_run.png")
        check(pg.locator(".dk-step.ok").count() == 2, "2 pasos OK en vivo")
        check(pg.locator("#stopbtn.hidden").count() == 1, "botón parar oculto al terminar")
        pg.locator(".dk-step.ok").nth(0).click(); pg.click(".dk-detail >> text=Ver resultado")
        pg.wait_for_selector("pre.json"); pg.wait_for_timeout(400)
        check("rows" in pg.inner_text("pre.json"), "resultado del nodo visible")
        pg.screenshot(path=OUT + "05_result.png"); pg.click(".dialog .x")
        # historial
        pg.click(".tab >> text=Ejecuciones"); pg.wait_for_selector(".rl-row"); pg.wait_for_selector(".runright .gnode.st-ok")
        pg.screenshot(path=OUT + "06_history.png")
        # tema oscuro
        pg.click(".topbar button >> text=⚙"); pg.select_option(".dialog select >> nth=1", "dark"); pg.click(".dialog .x")
        pg.click(".tab >> text=Editor"); pg.wait_for_timeout(300)
        pg.screenshot(path=OUT + "07_dark.png")
        # admin
        pg.click("text=Plugins"); pg.wait_for_selector(".dialog table"); pg.screenshot(path=OUT + "08_plugins.png"); pg.click(".dialog .x")
        pg.click("text=Usuarios"); pg.wait_for_selector(".dialog table")
        pg.fill(".dialog input[placeholder=Usuario]", "ana"); pg.fill(".dialog input[type=password]", "clave-segura-1")
        pg.click(".dialog >> text=Crear"); pg.wait_for_selector("td:has-text('ana')")
        pg.screenshot(path=OUT + "09_users.png"); pg.click(".dialog .x")
        pg.click("text=Auditoría"); pg.wait_for_selector(".dialog table"); check("run.start" in pg.inner_text(".dialog"), "auditoría muestra run.start"); pg.click(".dialog .x")
        # compartir
        pg.click(".wf-bar >> text=⋯"); pg.click(".dialog >> text=Compartir"); pg.wait_for_selector(".dialog select")
        pg.select_option(".dialog select >> nth=0", "view"); pg.click(".dialog >> text=Guardar"); pg.wait_for_timeout(300)
        # conflicto: otra persona edita por API
        import json, urllib.request
        c = srv.client(); c.post("/api/login", {"username": "admin", "password": "clave-segura-1"})
        wf = c.get("/api/workflows")[1]["workflows"][0]
        c.put("/api/workflows/%d" % wf["id"], {"description": "externo", "version": wf["version"]})
        pg.locator(".inspector .card[data-node]").locator("input[data-ref]").first.fill("Otro")
        pg.wait_for_selector(".banner.err", timeout=8000); check(True, "conflicto 409 muestra aviso")
        pg.screenshot(path=OUT + "10_conflict.png")
        pg.click(".banner >> text=Recargar"); pg.wait_for_selector(".wf-bar")
        # borrar y deshacer
        pg.hover(".wf-item"); pg.click(".wf-item .acts button >> nth=1")
        pg.wait_for_selector(".toast"); pg.wait_for_timeout(500); check(pg.locator(".wf-item").count() == 0, "workflow a la papelera")
        pg.click(".toast >> text=Deshacer"); pg.wait_for_selector(".wf-item"); check(True, "deshacer restaura")
        # ana (editor) entra: solo ve compartido
        b.close()
finally:
    srv.stop()
print("PROBLEMAS:", errors)
