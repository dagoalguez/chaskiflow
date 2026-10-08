"""Prueba opcional en navegador: campo «Clave» (lista de claves guardadas) y botón «Probar conexión» del Escaneo.
Uso: python tests/ui_conn_smoke.py [carpeta_capturas]"""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer
from tests.fakellm import FakeLLM
from playwright.sync_api import sync_playwright
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
srv = TestServer(scheduler_enabled=False)
problems = []
def check(c, m):
    print(("OK   " if c else "FAIL ") + m)
    if not c: problems.append(m)
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    c.post("/api/plugins/pdf_keyword_scan/enable")
    c.put("/api/secrets/ia_oficina", {"value": "k123", "scope": "me"})
    with FakeLLM(key="k123") as llm:
        d = {"variables": {"ia_url": llm.base, "carpeta": "x"}, "nodes": [
            {"id": "a", "label": "Escaneo", "type": "pdf_keyword_scan", "config": {"output_dir": "{{vars.carpeta}}", "base_url": "{{vars.ia_url}}"}, "position": {"x": 40, "y": 60}}], "edges": []}
        c.post("/api/workflows", {"name": "Conn", "definition": d})
        with sync_playwright() as p:
            b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
            pg = b.new_context(locale="es-PE", viewport={"width": 1400, "height": 900}).new_page()
            pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
            pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
            pg.wait_for_selector(".wf-item"); pg.click(".wf-item >> text=Conn"); pg.wait_for_selector(".gsvg .gnode")
            pg.click(".gsvg .gnode"); pg.wait_for_selector("text=Clave")
            check(pg.locator("datalist option[value=ia_oficina]").count() == 1, "la lista de claves ofrece «ia_oficina»")
            check("Secreto" not in pg.content(), "ya no aparece la palabra «Secreto»")
            check(pg.locator("text=Probar conexión con la IA").count() == 1, "hay botón de probar conexión")
            pg.click("text=Probar conexión con la IA")
            pg.wait_for_selector(".testout.bad")
            check("rechazó la clave" in pg.locator(".testout").inner_text(), "sin clave: dice que el servidor rechazó la clave")
            pg.fill("input[list^=sec-]", "ia_oficina")
            pg.click("text=Probar conexión con la IA")
            pg.wait_for_selector(".testout.ok", timeout=20000)
            txt = pg.locator(".testout").inner_text()
            check("ve imágenes" in txt and "enviada" in txt, "con clave: conexión correcta y el modelo ve imágenes")
            pg.screenshot(path=os.path.join(OUT, "conexion.png"))
            b.close()
finally:
    srv.close() if hasattr(srv, "close") else None
print("\nRESULTADO:", "OK" if not problems else "FALLAS: %s" % problems)
sys.exit(1 if problems else 0)
