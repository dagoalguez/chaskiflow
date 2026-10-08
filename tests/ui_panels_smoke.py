"""Prueba opcional en navegador real: paneles ocultables con ☰ y edición/renombrado/eliminación de plugins.
Uso:  python tests/ui_panels_smoke.py [carpeta_de_capturas]   (CHROMIUM_PATH=ruta si hace falta)"""
import os, sys, shutil, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.apiclient import TestServer
from playwright.sync_api import sync_playwright
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(), "")
srv = TestServer()
shutil.copytree(str(ROOT / "plugins" / "_plantilla"), str(srv.extra_plugins / "mi_plugin"))
problems = []
def check(c, m):
    print(("OK   " if c else "FAIL ") + m)
    if not c: problems.append(m)
def until(fn, t=8000):
    import time
    t0 = time.time()
    while time.time() - t0 < t / 1000:
        try:
            if fn(): return True
        except Exception: pass
        time.sleep(0.1)
    raise AssertionError("tiempo agotado esperando condición")
def shown(pg, sel): return pg.eval_on_selector(sel, "e => getComputedStyle(e).display !== 'none'")
try:
    c = srv.client(); c.post("/api/setup", {"username": "admin", "password": "clave-segura-1"})
    c.post("/api/plugins/reload"); c.post("/api/plugins/mi_plugin/enable")
    wid = c.post("/api/workflows", {"name": "Prueba", "definition": {"nodes": [{"id": "a", "label": "A", "type": "mi_plugin", "config": {}}], "edges": []}})[1]["workflow"]["id"]
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}))
        ctx = b.new_context(locale="es-PE", viewport={"width": 1400, "height": 850}); pg = ctx.new_page()
        pg.on("console", lambda m: problems.append("console: " + m.text) if m.type in ("error", "warning") and "401" not in m.text else None)
        pg.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
        pg.on("dialog", lambda d: d.accept())
        pg.goto(srv.base); pg.fill("#lg-user", "admin"); pg.fill("#lg-pass", "clave-segura-1"); pg.click("button[type=submit]")
        pg.wait_for_selector(".wf-item"); pg.click(".wf-item"); pg.wait_for_selector(".gsvg")
        # --- paneles
        check(shown(pg, ".sidebar") and shown(pg, ".inspector"), "los 2 paneles visibles al inicio")
        pg.click(".topbar .panel-toggle"); pg.wait_for_timeout(150)
        w_rail = pg.eval_on_selector(".sidebar", "e => e.getBoundingClientRect().width")
        check(w_rail < 80 and shown(pg, ".sidebar .sb-new") and shown(pg, ".sidebar .sb-link") and shown(pg, ".sidebar .wf-item .ini")
              and not shown(pg, ".sidebar .sb-link .lb") and not shown(pg, ".sidebar .wf-item .nm"), "☰ reduce la barra lateral a una columna de iconos (%dpx)" % w_rail)
        pg.screenshot(path=OUT + "p0_reducida.png")
        pg.click(".gtools .panel-toggle"); pg.wait_for_timeout(150)
        check(not shown(pg, ".inspector"), "☰ Panel oculta el panel del paso")
        pg.screenshot(path=OUT + "p1_ocultos.png")
        pg.reload(); pg.wait_for_selector(".shell")
        cls = pg.eval_on_selector(".shell", "e => e.className")
        check("hide-sb" in cls and "hide-insp" in cls, "el estado oculto se recuerda al recargar: " + cls)
        pg.click(".topbar .panel-toggle"); pg.wait_for_selector(".wf-item"); pg.click(".wf-item"); pg.wait_for_selector(".gsvg")
        pg.click(".gtools .panel-toggle"); pg.wait_for_timeout(150)
        check(pg.eval_on_selector(".sidebar", "e => e.getBoundingClientRect().width") > 200 and shown(pg, ".inspector"), "se vuelven a mostrar")
        # con el panel del paso oculto, elegir un nodo lo abre
        pg.click(".gtools .panel-toggle"); pg.wait_for_timeout(150)
        check(not shown(pg, ".inspector"), "panel del paso oculto de nuevo")
        pg.locator(".gnode").first.locator(".gbox").click(); pg.wait_for_timeout(250)
        check(shown(pg, ".inspector") and pg.locator(".inspector .card").count() >= 1, "clic en un nodo abre el panel del paso si estaba oculto")
        # el registro inferior se pliega y se despliega
        check(pg.locator(".dk-body").count() == 0, "el Registro arranca plegado en el Editor")
        pg.click(".dk-head"); pg.wait_for_timeout(150)
        check(pg.locator(".dk-body").count() == 1, "pulsar la cabecera del Registro lo despliega")
        pg.click(".dk-head"); pg.wait_for_timeout(150)
        check(pg.locator(".dk-body").count() == 0, "pulsar otra vez lo pliega")
        # --- plugins
        pg.click("text=Plugins"); pg.wait_for_selector(".dialog table")
        row = pg.locator(".dialog tr", has_text="mi_plugin")
        row.locator("text=Editar").click(); pg.wait_for_selector("textarea.code")
        until(lambda: "def run" in pg.input_value("textarea.code"))
        pg.fill("textarea.code", "def run(:\n"); pg.click(".dialog .df >> text=Guardar")
        until(lambda: "no compila" in pg.locator(".overlay").last.inner_text())
        check(True, "código con error de sintaxis se rechaza con mensaje")
        pg.fill("textarea.code", 'def run(config, ctx):\n    return {"rows": [], "total": 7}\n'); pg.click(".dialog .df >> text=Guardar")
        until(lambda: "Guardado" in pg.locator(".overlay").last.inner_text())
        check("total\": 7" in (srv.extra_plugins / "mi_plugin" / "task.py").read_text(encoding="utf-8"), "código válido se guarda en disco")
        pg.screenshot(path=OUT + "p2_editar.png")
        pg.locator(".overlay").last.locator(".df >> text=Cerrar").click()
        pg.locator(".dialog tr", has_text="mi_plugin").locator("text=Renombrar").click()
        pg.wait_for_selector(".dialog input.mono")
        pg.locator(".dialog input").first.fill("Plugin renombrado"); pg.fill(".dialog input.mono", "plugin_nuevo")
        pg.click(".dialog .df >> text=Guardar"); pg.wait_for_selector("td:has-text('plugin_nuevo')")
        check((srv.extra_plugins / "plugin_nuevo").is_dir() and "Plugin renombrado" in pg.inner_text(".dialog"), "renombrado de nombre e ID")
        wf = c.get("/api/workflows/%d" % wid)[1]["workflow"]
        check(wf["definition"]["nodes"][0]["type"] == "plugin_nuevo", "el workflow se migró al ID nuevo")
        pg.locator(".dialog tr", has_text="plugin_nuevo").locator("text=Eliminar").click()
        pg.wait_for_selector(".dialog >> text=Lo usan 1 workflow")
        pg.locator(".dialog .df >> text=Eliminar").last.click()
        until(lambda: not (srv.extra_plugins / "plugin_nuevo").exists())
        check(not (srv.extra_plugins / "plugin_nuevo").exists() and any((srv.extra_plugins / "_eliminados").iterdir()), "eliminado: carpeta movida a _eliminados")
        pg.screenshot(path=OUT + "p3_eliminado.png")
        b.close()
finally:
    srv.stop()
print("PROBLEMAS:", problems)
