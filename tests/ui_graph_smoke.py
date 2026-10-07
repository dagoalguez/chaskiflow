"""Prueba opcional del editor visual en un navegador real (requiere `pip install playwright`).
Uso:  python tests/ui_graph_smoke.py [carpeta_de_capturas]   (CHROMIUM_PATH=ruta si hace falta)"""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import json
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
    d = json.load(open(str(ROOT / "examples" / "noticias_diario.json")))
    wid = c.post("/api/workflows/import", {"name": d["name"], "definition": d})[1]["workflow"]["id"]
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        pg = b.new_context(locale="es-PE", viewport={"width": 1500, "height": 850}).new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".wf-item"); pg.click(".wf-item")
        pg.click(".tab >> text=Grafo"); pg.wait_for_selector(".gnode")
        pg.wait_for_timeout(500)
        check(pg.locator(".gnode").count() == 10, "10 nodos dibujados")
        check(pg.locator(".gedge").count() == 10 + 0 or pg.locator(".gedge").count() >= 10, "aristas dibujadas: %d" % pg.locator(".gedge").count())
        pg.screenshot(path=OUT + "g1_layout.png")
        # seleccionar nodo
        pg.locator(".gnode").nth(6).locator(".gbox").click()
        pg.wait_for_selector(".inspector .card"); pg.wait_for_timeout(300)
        pg.screenshot(path=OUT + "g2_select.png")
        # mover nodo
        box = pg.locator(".gnode").nth(0).locator(".gbox").bounding_box()
        pg.mouse.move(box["x"] + 60, box["y"] + 20); pg.mouse.down(); pg.mouse.move(box["x"] + 60, box["y"] - 110, steps=5); pg.mouse.up()
        pg.wait_for_timeout(1800)
        s, w = c.get("/api/workflows/%d" % wid)
        n1 = next(n for n in w["workflow"]["definition"]["nodes"] if n["id"] == "n1")
        check(n1["position"]["y"] != 40, "posición guardada tras mover: %s" % n1["position"])
        # conectar n1 -> n8 (CSV) arrastrando puerto
        out_port = pg.locator(".gnode").nth(0).locator(".gport.out").bounding_box()
        tgt = pg.locator(".gnode").nth(7).locator(".gbox").bounding_box()
        pg.mouse.move(out_port["x"] + out_port["width"] / 2, out_port["y"] + out_port["height"] / 2); pg.mouse.down()
        pg.mouse.move(tgt["x"] + 40, tgt["y"] + 20, steps=8); pg.mouse.up()
        pg.wait_for_timeout(1900)
        pg.wait_for_timeout(2500); print("savestate:", pg.inner_text("#savestate")); print("ui edges:", pg.locator(".gedge-hit").count(), "toast:", pg.locator(".toast").count(), "out_port", out_port, "tgt", tgt)
        w = c.get("/api/workflows/%d" % wid)[1]["workflow"]["definition"]
        print(len(w["edges"]), [e for e in w["edges"] if e["target"] in ("n8","n9")]); check({"source": "n1", "target": "n8"} in w["edges"], "arista n1->n8 creada")
        # ciclo rechazado: n8 -> n1
        out_port = pg.locator(".gnode").nth(7).locator(".gport.out").bounding_box()
        tgt = pg.locator(".gnode").nth(0).locator(".gbox").bounding_box()
        pg.mouse.move(out_port["x"] + out_port["width"] / 2, out_port["y"] + out_port["height"] / 2); pg.mouse.down(); pg.mouse.move(tgt["x"] + 40, tgt["y"] + 20, steps=8); pg.mouse.up()
        pg.wait_for_selector(".toast"); check("ciclo" in pg.inner_text(".toast"), "ciclo rechazado")
        # borrar arista seleccionada
        n_edges = pg.locator(".gedge-hit").count()
        pg.locator(".gedge-hit").last.dispatch_event("click")
        pg.wait_for_selector(".gedge.sel")
        pg.click(".gtools >> text=Quitar"); pg.wait_for_timeout(1900)
        check(pg.locator(".gedge-hit").count() == n_edges - 1, "arista borrada")
        # ejecutar: colorea nodos (falla de red esperada en medios -> continue)
        pg.click("#runbtn"); pg.wait_for_timeout(4000)
        sts = pg.eval_on_selector_all(".gnode", "els => els.map(e => e.getAttribute('class'))")
        check(any("st-" in x for x in sts), "estado en vivo pintado en nodos")
        pg.screenshot(path=OUT + "g3_run.png")
        check(pg.locator(".tab >> text=Pasos").count() == 0, "ya no existe la pestaña Pasos")
        b.close()
finally:
    srv.stop()
print("PROBLEMAS:", problems)
