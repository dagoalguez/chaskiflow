"""Prueba opcional del importador G1G en navegador real (requiere `pip install playwright`).
Uso:  python tests/ui_import_smoke.py [carpeta_de_capturas]   (CHROMIUM_PATH=ruta si hace falta)"""
import os, sys, tempfile
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
    txt = (ROOT / "tests" / "fixtures" / "g1g_noticias.json").read_text(encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1400, "height": 850}).new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector("text=Importar"); pg.click(".sb-head >> text=Importar") if pg.locator(".sb-head >> text=Importar").count() else pg.click("text=Importar >> nth=0")
        pg.wait_for_selector(".dialog textarea"); pg.fill(".dialog textarea", txt)
        pg.click(".dialog .df >> text=Importar")
        pg.wait_for_selector(".imp-report")
        rt = pg.inner_text(".imp-report")
        check("El_Comercio" in rt and "foreach" in rt, "informe visible: " + rt.replace("\n", " | ")[:140])
        pg.screenshot(path=OUT + "imp1_report.png")
        pg.click(".dialog .df >> text=Cerrar")
        pg.wait_for_selector(".wf-bar")
        check(pg.locator(".card[data-node]").count() >= 6, "workflow abierto con pasos")
        b.close()
finally:
    srv.stop()
print("PROBLEMAS:", problems)
