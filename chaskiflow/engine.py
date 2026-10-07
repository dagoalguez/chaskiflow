"""Motor de workflows: valida el grafo, lo ejecuta en paralelo y registra cada nodo.

Formato de workflow (JSON):
  {
    "name": "Mi flujo",
    "variables": {"carpeta": "C:/reportes"},          # opcional -> {{vars.carpeta}}
    "nodes": [
      {"id": "n1", "label": "RPP", "type": "http_request",
       "config": {"url": "https://..."},
       "on_error": "stop" | "continue",                 # por defecto "stop"
       "enabled": true,
       "position": {"x": 0, "y": 0}}                    # lo usa el editor visual
    ],
    "edges": [{"source": "n1", "target": "n2"}]
  }
Un nodo usa los resultados de otro con {{Etiqueta.result.campo}}; ese otro debe estar
conectado antes (ser antecesor).
"""

import copy
import os
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from .executor import run_task
from .schema import apply_config
from .templating import TemplateError, find_refs, resolve
from .util import now_iso, summarize


class WorkflowError(ValueError):
    pass


def normalize(workflow):
    """Copia del workflow con valores por defecto aplicados."""
    wf = copy.deepcopy(workflow) if isinstance(workflow, dict) else {}
    wf.setdefault("name", "Sin nombre")
    wf.setdefault("variables", {})
    nodes = []
    for n in wf.get("nodes") or []:
        n = dict(n)
        n.setdefault("label", n.get("id"))
        n.setdefault("config", {})
        n.setdefault("on_error", "stop")
        n.setdefault("enabled", True)
        nodes.append(n)
    wf["nodes"] = nodes
    wf["edges"] = [dict(e) for e in (wf.get("edges") or [])]
    return wf


def _graph(wf):
    ids = [n["id"] for n in wf["nodes"]]
    preds = {i: [] for i in ids}
    succs = {i: [] for i in ids}
    for e in wf["edges"]:
        s, t = e.get("source"), e.get("target")
        if s in preds and t in preds:
            if s not in preds[t]:
                preds[t].append(s)
                succs[s].append(t)
    return preds, succs


def _topological(ids, preds):
    indeg = {i: len(preds[i]) for i in ids}
    succs = {i: [] for i in ids}
    for t, ps in preds.items():
        for s in ps:
            succs[s].append(t)
    queue = [i for i in ids if indeg[i] == 0]
    order = []
    while queue:
        i = queue.pop(0)
        order.append(i)
        for t in succs[i]:
            indeg[t] -= 1
            if indeg[t] == 0:
                queue.append(t)
    return order


def _ancestors(nid, preds):
    seen, stack = set(), list(preds.get(nid, []))
    while stack:
        x = stack.pop()
        if x not in seen:
            seen.add(x)
            stack.extend(preds.get(x, []))
    return seen


def env_secret_provider(name):
    """Proveedor de secretos por defecto: variable de entorno CHASKIFLOW_SECRET_<NOMBRE>."""
    return os.environ.get("CHASKIFLOW_SECRET_" + name.upper())


class RunResult:
    def __init__(self, run_id, workflow_name):
        self.run_id = run_id
        self.workflow = workflow_name
        self.status = "running"
        self.started = now_iso()
        self.finished = None
        self.duration = 0.0
        self.nodes = {}      # id -> registro del nodo
        self.order = []

    def to_dict(self, full=True):
        nodes = []
        for nid in self.order:
            r = dict(self.nodes[nid])
            if not full:
                r["result"] = summarize(r.get("result"))
            nodes.append(r)
        return {"run_id": self.run_id, "workflow": self.workflow, "status": self.status,
                "started": self.started, "finished": self.finished,
                "duration": self.duration, "nodes": nodes}


class Engine:
    def __init__(self, registry, *, secrets=None, workdir_root=None, max_parallel=4,
                 python=None):
        self.registry = registry
        self.secrets = secrets or env_secret_provider
        self.workdir_root = Path(workdir_root or Path.cwd() / "runs")
        self.max_parallel = max(1, int(max_parallel))
        self.python = python

    # ------------------------------------------------------------------ validación
    def validate(self, workflow):
        """Devuelve (errores, avisos) sin ejecutar nada."""
        wf = normalize(workflow)
        errors, warnings = [], []
        nodes = wf["nodes"]
        if not nodes:
            errors.append("El workflow no tiene nodos")
            return errors, warnings
        ids, labels = {}, {}
        for n in nodes:
            nid = n.get("id")
            if not isinstance(nid, str) or not nid:
                errors.append("Hay un nodo sin 'id'")
                continue
            if nid in ids:
                errors.append("Id de nodo repetido: '%s'" % nid)
            ids[nid] = n
            lab = n.get("label")
            if not isinstance(lab, str) or not lab.isidentifier():
                errors.append("Nodo '%s': la etiqueta '%s' no es válida (use letras, números y _, "
                              "sin espacios; no puede empezar con número)" % (nid, lab))
            elif lab in labels:
                errors.append("Etiqueta repetida: '%s'" % lab)
            else:
                labels[lab] = nid
            if n.get("on_error") not in ("stop", "continue"):
                errors.append("Nodo '%s': on_error debe ser 'stop' o 'continue'" % nid)
        for lab, nid in labels.items():
            if lab in ids and lab != nid:
                errors.append("La etiqueta '%s' coincide con el id de otro nodo" % lab)
        if errors:
            return errors, warnings

        seen_edges = set()
        for e in wf["edges"]:
            s, t = e.get("source"), e.get("target")
            if s not in ids or t not in ids:
                errors.append("Conexión inválida: %s → %s (el nodo no existe)" % (s, t))
            elif s == t:
                errors.append("Un nodo no puede conectarse consigo mismo: '%s'" % s)
            elif (s, t) in seen_edges:
                warnings.append("Conexión repetida %s → %s" % (s, t))
            seen_edges.add((s, t))
        if errors:
            return errors, warnings
        preds, _ = _graph(wf)
        if len(_topological(list(ids), preds)) != len(ids):
            errors.append("El workflow tiene un ciclo: las conexiones no pueden volver atrás")
            return errors, warnings

        for n in nodes:
            nid, lab = n["id"], n["label"]
            plugin = self.registry.get(n.get("type"))
            if plugin is None:
                why = getattr(self.registry, "why_unavailable", None)
                errors.append("Nodo '%s': %s" % (lab, why(n.get("type")) if why else
                              "la tarea '%s' no está instalada o está inválida" % n.get("type")))
                continue
            _, cerrs, cwarns = apply_config(plugin.fields, n.get("config"), skip_templates=True)
            errors += ["Nodo '%s': %s" % (lab, m) for m in cerrs]
            warnings += ["Nodo '%s': %s" % (lab, m) for m in cwarns]
            anc = _ancestors(nid, preds)
            allowed = {"vars"}
            for a in anc:
                allowed.add(ids[a]["label"])
                allowed.add(a)
            for root in sorted(find_refs(n.get("config"))):
                if root in allowed:
                    continue
                if root in labels or root in ids:
                    errors.append("Nodo '%s' usa '{{%s...}}' pero '%s' no está conectado antes "
                                  "(conéctelo como antecesor)" % (lab, root, root))
                else:
                    errors.append("Nodo '%s' usa '{{%s...}}' pero no existe ningún nodo ni "
                                  "variable llamada '%s'" % (lab, root, root))
        return errors, warnings

    # ------------------------------------------------------------------ ejecución
    def run(self, workflow, *, run_id=None, on_event=None, cancel=None, only=None,
            seed=None, variables=None):
        """Ejecuta el workflow. 'only' = ids a (re)ejecutar; 'seed' = registros previos por id."""
        wf = normalize(workflow)
        errors, _ = self.validate(wf)
        if errors:
            raise WorkflowError("; ".join(errors))
        run_id = run_id or time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        cancel = cancel or threading.Event()
        ev_lock = threading.Lock()

        def emit(ev):
            ev = dict(ev, ts=now_iso(), run_id=run_id)
            if on_event:
                with ev_lock:
                    try:
                        on_event(ev)
                    except Exception:
                        pass

        nodes = {n["id"]: n for n in wf["nodes"]}
        preds, succs = _graph(wf)
        order = _topological(list(nodes), preds)
        result = RunResult(run_id, wf["name"])
        result.order = order
        variables_all = dict(wf.get("variables") or {})
        variables_all.update(variables or {})

        lock = threading.Lock()
        scope = {"vars": variables_all}
        status = {}
        stop_reason = {"msg": None}
        pending = set()

        def record_scope(nid, rec):
            entry = {"id": nid, "label": rec["label"], "status": rec["status"],
                     "result": rec.get("result"), "error": rec.get("error")}
            scope[nid] = entry
            scope[rec["label"]] = entry

        for nid in order:
            n = nodes[nid]
            base = {"id": nid, "label": n["label"], "type": n.get("type"), "status": "pending",
                    "started": None, "finished": None, "duration": 0.0, "error": None,
                    "result": None, "logs": [], "config": None, "reason": None}
            result.nodes[nid] = base
            if only is not None and nid not in only:
                prev = (seed or {}).get(nid)
                if prev and prev.get("status") == "ok":
                    base.update(prev)
                    base["status"] = "ok"
                    base["reason"] = "resultado reutilizado"
                    status[nid] = "ok"
                    record_scope(nid, base)
                else:
                    base.update(status="skipped", reason="no solicitado")
                    status[nid] = "skipped"
            elif not n.get("enabled", True):
                base.update(status="skipped", reason="nodo deshabilitado")
                status[nid] = "skipped"
            else:
                status[nid] = "pending"
                pending.add(nid)

        emit({"type": "run_start", "workflow": wf["name"], "nodes": [
            {"id": i, "label": nodes[i]["label"], "type": nodes[i].get("type")} for i in order]})
        t0 = time.monotonic()

        def exec_node(nid):
            n = nodes[nid]
            rec = result.nodes[nid]
            plugin = self.registry.get(n["type"])
            rec["started"] = now_iso()
            emit({"type": "node_start", "node_id": nid, "label": n["label"]})
            ts = time.monotonic()

            def finish(st, error=None, res=None, outcome=None, reason=None):
                rec["status"] = st
                rec["error"] = error
                rec["result"] = res
                rec["reason"] = reason
                rec["finished"] = now_iso()
                rec["duration"] = round(time.monotonic() - ts, 3)
                if outcome:
                    rec["logs"] = outcome.logs
                    if outcome.traceback:
                        rec["traceback"] = outcome.traceback
                emit({"type": "node_end", "node_id": nid, "label": n["label"], "status": st,
                      "duration": rec["duration"], "error": error,
                      "summary": summarize(res) if res is not None else None})

            try:
                with lock:
                    snapshot = dict(scope)
                cfg = resolve(n.get("config") or {}, snapshot)
            except TemplateError as e:
                return finish("error", "Plantilla: %s" % e)
            clean, errs, warns = apply_config(plugin.fields, cfg)
            rec["config"] = summarize(clean)
            if errs:
                return finish("error", "Configuración inválida: " + "; ".join(errs))
            secrets = {}
            for name in plugin.secrets:
                try:
                    v = self.secrets(name)
                except Exception:
                    v = None
                if v not in (None, ""):
                    secrets[name] = v
            inputs = {}
            if plugin.wants_inputs:
                with lock:
                    for p in preds[nid]:
                        if status.get(p) == "ok":
                            inputs[nodes[p]["label"]] = result.nodes[p]["result"]
            workdir = self.workdir_root / run_id / n["label"]
            workdir.mkdir(parents=True, exist_ok=True)
            payload = {"plugin_dir": str(plugin.path), "manifest": plugin.manifest,
                       "config": clean, "secrets": secrets, "inputs": inputs,
                       "workdir": str(workdir),
                       "run": {"run_id": run_id, "node": n["label"]}}

            def on_task_event(e):
                if e["type"] in ("log", "progress"):
                    emit(dict(e, node_id=nid, label=n["label"]))

            for w in warns:
                emit({"type": "log", "node_id": nid, "level": "warn", "message": w})
            outcome = run_task(payload, workdir=workdir, timeout=plugin.timeout, cancel=cancel,
                               on_event=on_task_event, python=self.python)
            if outcome.ok:
                return finish("ok", None, outcome.result, outcome)
            st = "cancelled" if outcome.reason == "cancelled" else "error"
            return finish(st, outcome.error, None, outcome, outcome.reason or None)

        def decide(nid):
            ps = preds[nid]
            if any(status[p] in ("pending", "running") for p in ps):
                return "wait", None
            if cancel.is_set():
                return "cancelled", "cancelado"
            if stop_reason["msg"]:
                return "skipped", stop_reason["msg"]
            for p in ps:
                if status[p] in ("skipped", "cancelled"):
                    return "skipped", "depende de '%s' que no se ejecutó" % nodes[p]["label"]
                if status[p] == "error" and nodes[p].get("on_error", "stop") == "stop":
                    return "skipped", "depende de '%s' que falló" % nodes[p]["label"]
            return "run", None

        running = {}
        with ThreadPoolExecutor(max_workers=self.max_parallel) as pool:
            while pending or running:
                progressed = False
                for nid in [i for i in order if i in pending]:
                    with lock:
                        action, why = decide(nid)
                    if action == "wait":
                        continue
                    progressed = True
                    pending.discard(nid)
                    if action == "run":
                        with lock:
                            status[nid] = "running"
                        result.nodes[nid]["status"] = "running"
                        running[pool.submit(exec_node, nid)] = nid
                    else:
                        rec = result.nodes[nid]
                        with lock:
                            status[nid] = action
                        rec.update(status=action, reason=why)
                        emit({"type": "node_end", "node_id": nid, "label": rec["label"],
                              "status": action, "duration": 0, "error": None, "reason": why})
                if running:
                    done, _ = wait(list(running), timeout=0.2, return_when=FIRST_COMPLETED)
                    for fut in done:
                        nid = running.pop(fut)
                        try:
                            fut.result()
                        except Exception as e:  # error interno del motor, no del plugin
                            rec = result.nodes[nid]
                            rec.update(status="error", error="Error interno: %s" % e)
                        rec = result.nodes[nid]
                        with lock:
                            status[nid] = rec["status"]
                            record_scope(nid, rec)
                            if rec["status"] == "error" and \
                                    nodes[nid].get("on_error", "stop") == "stop":
                                stop_reason["msg"] = "detenido por el error en '%s'" % rec["label"]
                elif pending and not progressed:
                    break  # no debería ocurrir (se validó que no hay ciclos)

        statuses = [r["status"] for r in result.nodes.values()]
        if cancel.is_set() or "cancelled" in statuses:
            result.status = "cancelled"
        elif any(r["status"] == "error" and nodes[i].get("on_error", "stop") == "stop"
                 for i, r in result.nodes.items()):
            result.status = "error"
        elif "error" in statuses:
            result.status = "partial"
        else:
            result.status = "ok"
        result.finished = now_iso()
        result.duration = round(time.monotonic() - t0, 3)
        emit({"type": "run_end", "status": result.status, "duration": result.duration})
        return result
