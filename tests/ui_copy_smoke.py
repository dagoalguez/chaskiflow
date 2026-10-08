"""Prueba opcional en navegador: clic derecho (Duplicar/Copiar/Eliminar/Pegar aquí) y Ctrl+C/V/D en el grafo.
El paso se pega SIN conexiones y sin referencias rotas.  Uso: python tests/ui_copy_smoke.py [carpeta_capturas]"""
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
def until(fn, t=10000):
    t0 = time.time()
    while time.time() - t0 < t / 1000:
        try:
            if fn(): return True
        except Exception: pass
        time.sleep(0.1)
    raise AssertionError("tiempo agotado")
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    c.post("/api/plugins/hello_world/enable")
    d1 = {"variables": {"saludo": "Hola"}, "nodes": [
        {"id": "a", "label": "Uno", "type": "hello_world", "config": {"nombre": "{{vars.saludo}}"}, "position": {"x": 40, "y": 60}},
        {"id": "b", "label": "Dos", "type": "hello_world", "config": {"nombre": "{{Uno.result.mensaje}} y {{vars.saludo}}"}, "position": {"x": 340, "y": 60}}],
        "edges": [{"source": "a", "target": "b"}]}
    w1 = c.post("/api/workflows", {"name": "Origen", "definition": d1})[1]["workflow"]["id"]
    w2 = c.post("/api/workflows", {"name": "Destino", "definition": {"nodes": [], "edges": [], "variables": {}}})[1]["workflow"]["id"]
    def wf(i): return c.get("/api/workflows/%d" % i)[1]["workflow"]["definition"]
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1400, "height": 1050}).new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".wf-item"); pg.click(".wf-item >> text=Origen"); pg.wait_for_selector(".gsvg .gnode")
        # --- clic derecho en un nodo -> Duplicar
        pg.locator(".gnode", has_text="Dos").click(button="right")
        pg.wait_for_selector("#ctxmenu")
        check(pg.locator("#ctxmenu .mi").all_inner_texts() == ["Duplicar\nCtrl+D", "Añadir paso después…", "Copiar\nCtrl+C", "Eliminar\nSupr"], "menú del nodo: %s" % pg.locator("#ctxmenu .mi").all_inner_texts())
        pg.screenshot(path=OUT + "k1_menu.png")
        pg.click("#ctxmenu .mi >> text=Duplicar")
        until(lambda: pg.locator(".gnode").count() == 3)
        check(pg.locator(".gnode.sel .glabel").text_content() == "Dos2", "el duplicado se llama Dos2 y queda seleccionado")
        check("referencia" in pg.inner_text("#toast"), "aviso de referencias vaciadas: " + pg.inner_text("#toast"))
        pg.screenshot(path=OUT + "k2_duplicado.png")
        until(lambda: len(wf(w1)["nodes"]) == 3)
        dd = wf(w1); n2 = [n for n in dd["nodes"] if n["label"] == "Dos2"][0]
        check(len(dd["edges"]) == 1, "sin conexiones nuevas (sigue 1 lazo): %s" % dd["edges"])
        check(n2["config"]["nombre"] == " y {{vars.saludo}}", "referencia a otro paso vaciada, {{vars}} conservada: %r" % n2["config"]["nombre"])
        errs = c.post("/api/workflows/%d/validate" % w1, {"definition": dd})[1]
        check(errs["errors"] == [], "el workflow valida sin errores de referencia: %s" % errs["errors"])
        # --- deshacer
        pg.click("#toast button"); until(lambda: pg.locator(".gnode").count() == 2)
        check(True, "Deshacer quita el duplicado")
        # --- Ctrl+C / Ctrl+V en otro workflow (con variable)
        pg.locator(".gnode", has_text="Uno").click(); pg.keyboard.press("Control+c")
        pg.click(".wf-item >> text=Destino"); pg.wait_for_selector(".gsvg"); time.sleep(0.4)
        pg.locator(".gsvg").click(position={"x": 400, "y": 300}); pg.keyboard.press("Control+v")
        until(lambda: pg.locator(".gnode").count() == 1)
        until(lambda: len(wf(w2)["nodes"]) == 1)
        d2 = wf(w2)
        check(d2["nodes"][0]["label"] == "Uno" and d2["edges"] == [], "pegado en otro workflow, sin lazos")
        check(d2["variables"].get("saludo") == "Hola", "la variable usada se agregó al destino: %s" % d2["variables"])
        check(c.post("/api/workflows/%d/validate" % w2, {"definition": d2})[1]["errors"] == [], "el destino valida sin errores")
        # --- Ctrl+D
        pg.locator(".gnode", has_text="Uno").click(); pg.keyboard.press("Control+d")
        until(lambda: pg.locator(".gnode").count() == 2)
        check(pg.locator(".gnode.sel .glabel").text_content() == "Uno2", "Ctrl+D duplica")
        # --- clic derecho en el fondo -> Pegar aquí
        pg.locator(".gsvg").click(button="right", position={"x": 200, "y": 380})
        pg.wait_for_selector("#ctxmenu"); pg.click("#ctxmenu .mi >> text=Pegar aquí")
        until(lambda: pg.locator(".gnode").count() == 3)
        until(lambda: len(wf(w2)["nodes"]) == 3)
        labs = sorted(n["label"] for n in wf(w2)["nodes"])
        check(labs == ["Uno", "Uno2", "Uno3"] and wf(w2)["edges"] == [], "Pegar aquí crea Uno3 sin lazos: %s" % labs)
        # --- eliminar desde el menú
        pg.locator(".gnode", has_text="Uno3").click(button="right"); pg.click("#ctxmenu .mi >> text=Eliminar")
        until(lambda: pg.locator(".gnode").count() == 2)
        check(True, "Eliminar desde el menú")
        pg.keyboard.press("Escape")
        b.close()
finally:
    srv.stop()
print("PROBLEMAS: %s" % problems if problems else "OK: todo bien"); sys.exit(1 if problems else 0)
