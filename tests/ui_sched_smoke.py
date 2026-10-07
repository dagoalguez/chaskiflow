"""Prueba opcional del diálogo de programación en un navegador real (requiere `pip install playwright`).
Uso:  python tests/ui_sched_smoke.py [carpeta_de_capturas]   (CHROMIUM_PATH=ruta si hace falta)"""
import os, sys, json, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer
from playwright.sync_api import sync_playwright
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(), "")
srv = TestServer(plugin_dirs=[str(ROOT / "plugins")], scheduler_enabled=False)
problems = []
def check(c, m):
    print(("OK   " if c else "FAIL ") + m)
    if not c: problems.append(m)
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    d = json.load(open(str(ROOT / "examples" / "hola_reporte.json")))
    wid = c.post("/api/workflows/import", {"name": d["name"], "definition": d})[1]["workflow"]["id"]
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1400, "height": 850}).new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".wf-item"); pg.click(".wf-item"); pg.wait_for_selector(".wf-bar")
        pg.click(".wf-bar >> text=⋯"); pg.click(".dialog >> text=Programar"); pg.wait_for_selector(".dialog >> text=Nueva programación")
        pg.fill(".dialog input[placeholder=Nombre]", "Reporte diario"); pg.fill(".dialog input[type=time]", "07:45")
        pg.locator('.dialog label.chk:has-text("Sáb") input').uncheck(); pg.locator('.dialog label.chk:has-text("Dom") input').uncheck()
        pg.click(".dialog >> text=Crear"); pg.wait_for_selector(".dialog table")
        txt = pg.inner_text(".dialog table")
        check("Lun–Vie a las 07:45" in txt, "programación creada y descrita: " + txt.replace("\n", " | ")[:120])
        pg.screenshot(path=OUT + "s1_dialog.png")
        s = c.get("/api/workflows/%d/schedules" % wid)[1]["schedules"][0]
        check(s["days"] == [0, 1, 2, 3, 4] and s["time"] == "07:45", "datos guardados en servidor")
        pg.locator(".dialog table input[type=checkbox]").uncheck(); pg.wait_for_timeout(500)
        check(c.get("/api/workflows/%d/schedules" % wid)[1]["schedules"][0]["enabled"] is False, "desactivada desde la UI")
        pg.click(".dialog .x")
        pg.click(".sb-foot >> text=Programaciones"); pg.wait_for_selector(".dialog table"); check("Hola reporte" in pg.inner_text(".dialog"), "vista global muestra el workflow")
        pg.click(".dialog .x")
        b.close()
finally:
    srv.stop()
print("PROBLEMAS:", problems)
