"""Gestor de ejecuciones: corre workflows en hilos, guarda el resultado y entrega eventos en vivo."""

import json
import shutil
import threading
import time
import uuid
import zlib
from pathlib import Path

from .engine import Engine, WorkflowError, _graph, normalize
from .templating import find_refs
from .util import now_iso

MAX_STORED_RESULT = 50 * 1024 * 1024
MAX_LIVE_EVENTS = 5000


class RunError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class LiveRun:
    def __init__(self, run_id, workflow_id):
        self.run_id = run_id
        self.workflow_id = workflow_id
        self.events = []
        self.seq = 0
        self.cancel = threading.Event()
        self.status = "queued"
        self.done = False
        self.finished_at = None
        self.lock = threading.Lock()

    def add(self, ev):
        with self.lock:
            self.seq += 1
            if len(self.events) < MAX_LIVE_EVENTS or ev.get("type") not in ("log", "progress"):
                self.events.append(dict(ev, seq=self.seq))

    def after(self, seq):
        with self.lock:
            return [e for e in self.events if e["seq"] > seq]


def pack_result(result):
    """Resultado de un nodo -> (blob comprimido, tamaño). Si es enorme se guarda un marcador."""
    raw = json.dumps(result, ensure_ascii=False, default=str).encode("utf-8")
    if len(raw) > MAX_STORED_RESULT:
        raw = json.dumps({"_truncado": True, "tamano_bytes": len(raw),
                          "motivo": "El resultado supera %d MB y no se guardó" %
                                    (MAX_STORED_RESULT // 1048576)}).encode("utf-8")
    return zlib.compress(raw, 6), len(raw)


def unpack_result(blob):
    if blob is None:
        return None
    return json.loads(zlib.decompress(blob).decode("utf-8"))


class RunManager:
    def __init__(self, db, gate, data_dir, *, max_concurrent=2, max_parallel=4,
                 retention_days=90):
        self.db = db
        self.gate = gate
        self.data_dir = Path(data_dir)
        self.tmp_root = self.data_dir / "runs_tmp"
        self.max_parallel = max_parallel
        self.retention_days = retention_days
        self.sem = threading.Semaphore(max_concurrent)
        self.live = {}
        self.lock = threading.Lock()
        self.python = None
        self.mark_interrupted()

    # ----- ayudas ----------------------------------------------------------------
    def mark_interrupted(self):
        """Ejecuciones que quedaron 'running' porque el servidor se cerró."""
        self.db.run("UPDATE runs SET status='error', finished=?, error=? "
                    "WHERE status IN ('running','queued')",
                    (now_iso(), "Interrumpida: el servidor se reinició durante la ejecución"))

    def secret_resolver(self, owner_id):
        def resolve(name):
            r = self.db.one("SELECT value FROM secrets WHERE owner_id=? AND name=?", (owner_id, name))
            if r is None:
                r = self.db.one("SELECT value FROM secrets WHERE owner_id IS NULL AND name=?", (name,))
            return r["value"] if r else None
        return resolve

    def engine_for(self, owner_id):
        return Engine(self.gate, secrets=self.secret_resolver(owner_id),
                      workdir_root=self.tmp_root, max_parallel=self.max_parallel,
                      python=self.python)

    def active_run_for(self, workflow_id):
        with self.lock:
            for lr in self.live.values():
                if lr.workflow_id == workflow_id and not lr.done:
                    return lr.run_id
        return None

    # ----- iniciar ---------------------------------------------------------------
    def start(self, wf, user, variables=None, only=None, seed_run=None, trigger="manual"):
        """wf: fila de workflows. Devuelve run_id; la ejecución sigue en un hilo."""
        return self.start_ex(wf, user, variables, only, seed_run, trigger)[0]

    def start_ex(self, wf, user, variables=None, only=None, seed_run=None, trigger="manual"):
        """Como start(), pero devuelve (run_id, reutilizados). 'only' = ejecutar solo esos pasos; los
        demás toman su último resultado correcto (de 'seed_run' o de las ejecuciones recientes)."""
        definition = json.loads(wf["definition"])
        definition["name"] = wf["name"]
        engine = self.engine_for(wf["owner_id"])
        errors, _ = engine.validate(definition)
        if errors:
            raise RunError("El workflow no es válido: " + "; ".join(errors), 422)
        if self.active_run_for(wf["id"]):
            raise RunError("Este workflow ya se está ejecutando", 409)
        seed, reused = None, []
        if only is not None:
            known = {n["id"] for n in definition.get("nodes", [])}
            if not only or not only <= known:
                raise RunError("Paso inexistente en este workflow", 400)
            if seed_run:
                seed, info = self._seed_from(seed_run), {}
            else:
                seed, info = self._seed_latest(wf["id"])
            reused = self._check_seed(engine, definition, only, seed, info)
        run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        lr = LiveRun(run_id, wf["id"])
        with self.lock:
            self.live[run_id] = lr
        self.db.run("INSERT INTO runs(id, workflow_id, workflow_name, started_by, trigger, status,"
                    " started, variables) VALUES(?,?,?,?,?,?,?,?)",
                    (run_id, wf["id"], wf["name"], user["id"] if user else None, trigger,
                     "queued", now_iso(), json.dumps(variables or {}, ensure_ascii=False)))
        th = threading.Thread(target=self._worker, name="run-" + run_id, daemon=True,
                              args=(lr, engine, definition, variables or {}, only, seed))
        th.start()
        return run_id, reused

    def _seed_latest(self, workflow_id, depth=20):
        """Último resultado correcto de cada paso entre las ejecuciones recientes del workflow."""
        seed, info = {}, {}
        runs = self.db.all("SELECT id, started FROM runs WHERE workflow_id=? AND status IN "
                           "('ok','partial','error','cancelled') ORDER BY started DESC LIMIT ?", (workflow_id, depth))
        for r in runs:
            for row in self.db.all("SELECT * FROM run_nodes WHERE run_id=? AND status='ok'", (r["id"],)):
                if row["node_id"] in seed:
                    continue
                seed[row["node_id"]] = {"id": row["node_id"], "label": row["label"], "type": row["type"],
                                        "status": "ok", "result": unpack_result(row["result"]),
                                        "error": None, "logs": [], "config": None, "duration": 0.0,
                                        "started": row["started"], "finished": row["finished"]}
                info[row["node_id"]] = {"run_id": r["id"], "finished": row["finished"] or r["started"]}
        return seed, info

    def _check_seed(self, engine, definition, only, seed, info):
        """Falla con un mensaje claro si a un paso le falta el resultado de un antecesor que usa."""
        wf = normalize(definition)
        nodes = {n["id"]: n for n in wf["nodes"]}
        preds, _ = _graph(wf)
        reused, missing = [], []
        for nid in only:
            n = nodes[nid]
            plugin = engine.registry.get(n.get("type"))
            refs = find_refs(n.get("config"))
            for p in preds.get(nid, []):
                if p in only:
                    continue
                needed = nodes[p]["label"] in refs or p in refs or (plugin is not None and plugin.wants_inputs)
                if not needed:
                    continue
                if (seed or {}).get(p):
                    reused.append({"node": nodes[p]["label"], "run_id": (info or {}).get(p, {}).get("run_id"),
                                   "finished": (info or {}).get(p, {}).get("finished")})
                else:
                    missing.append(nodes[p]["label"])
        if missing:
            raise RunError("Este paso necesita el resultado de: %s, que aún no se ha ejecutado bien. "
                           "Use «Hasta aquí» o ejecute el flujo completo una vez." % ", ".join(sorted(set(missing))), 409)
        return reused

    def _seed_from(self, run_id):
        if not run_id:
            return None
        seed = {}
        for r in self.db.all("SELECT * FROM run_nodes WHERE run_id=?", (run_id,)):
            if r["status"] == "ok":
                seed[r["node_id"]] = {"id": r["node_id"], "label": r["label"], "type": r["type"],
                                      "status": "ok", "result": unpack_result(r["result"]),
                                      "error": None, "logs": [], "config": None, "duration": 0.0,
                                      "started": r["started"], "finished": r["finished"]}
        return seed

    # ----- hilo de ejecución -------------------------------------------------------
    def _worker(self, lr, engine, definition, variables, only, seed):
        try:
            lr.add({"type": "queued"})
            self.sem.acquire()
            try:
                if lr.cancel.is_set():
                    self._finish(lr, None, "cancelled", "Cancelada antes de empezar")
                    return
                lr.status = "running"
                self.db.run("UPDATE runs SET status='running' WHERE id=?", (lr.run_id,))
                result = engine.run(definition, run_id=lr.run_id, on_event=lr.add,
                                    cancel=lr.cancel, only=only, seed=seed, variables=variables)
                self._finish(lr, result, result.status, None)
            finally:
                self.sem.release()
        except WorkflowError as e:
            self._finish(lr, None, "error", str(e))
        except Exception as e:  # error interno: no debe dejar la ejecución colgada
            self._finish(lr, None, "error", "Error interno: %s" % e)
        finally:
            shutil.rmtree(self.tmp_root / lr.run_id, ignore_errors=True)
            self.db.close_thread()

    def _finish(self, lr, result, status, error):
        if result is not None:
            for nid in result.order:
                r = result.nodes[nid]
                blob, size = (pack_result(r["result"]) if r.get("result") is not None
                              else (None, 0))
                self.db.run(
                    "INSERT OR REPLACE INTO run_nodes(run_id, node_id, label, type, status, started,"
                    " finished, duration, error, reason, config, logs, result, result_size) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (lr.run_id, nid, r["label"], r["type"], r["status"], r["started"],
                     r["finished"], r["duration"], r["error"], r.get("reason"),
                     json.dumps(r.get("config"), ensure_ascii=False, default=str),
                     json.dumps(r.get("logs") or [], ensure_ascii=False, default=str), blob, size))
            self.db.run("UPDATE runs SET status=?, finished=?, duration=?, error=? WHERE id=?",
                        (status, result.finished, result.duration, error, lr.run_id))
        else:
            self.db.run("UPDATE runs SET status=?, finished=?, error=? WHERE id=?",
                        (status, now_iso(), error, lr.run_id))
        lr.status = status
        lr.add({"type": "run_final", "status": status, "error": error})
        lr.done = True
        lr.finished_at = time.time()

    # ----- consultas -----------------------------------------------------------------
    def cancel(self, run_id):
        with self.lock:
            lr = self.live.get(run_id)
        if not lr or lr.done:
            raise RunError("La ejecución ya terminó o no existe", 409)
        lr.cancel.set()

    def events(self, run_id, after=0):
        with self.lock:
            lr = self.live.get(run_id)
        if lr is None:
            r = self.db.one("SELECT status FROM runs WHERE id=?", (run_id,))
            return {"events": [], "status": r["status"] if r else None, "done": True, "seq": after}
        evs = lr.after(after)
        return {"events": evs, "status": lr.status, "done": lr.done,
                "seq": evs[-1]["seq"] if evs else after}

    def run_detail(self, run_id, include_results=False):
        r = self.db.one("SELECT * FROM runs WHERE id=?", (run_id,))
        if not r:
            return None
        r["variables"] = json.loads(r["variables"] or "{}")
        nodes = []
        for n in self.db.all("SELECT * FROM run_nodes WHERE run_id=?", (run_id,)):
            n["config"] = json.loads(n["config"]) if n["config"] else None
            n["logs"] = json.loads(n["logs"]) if n["logs"] else []
            blob = n.pop("result")
            if include_results:
                n["result"] = unpack_result(blob)
            n["has_result"] = blob is not None
            nodes.append(n)
        r["nodes"] = nodes
        r["live"] = run_id in self.live and not self.live[run_id].done
        return r

    # ----- mantenimiento -----------------------------------------------------------
    def forget(self, run_id):
        """Olvida el estado en memoria de una ejecución terminada (al borrarla del historial)."""
        with self.lock:
            lr = self.live.get(run_id)
            if lr is not None and lr.done:
                del self.live[run_id]

    def purge_old(self):
        if self.retention_days <= 0:
            return 0
        limit = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - self.retention_days * 86400))
        n = self.db.run("DELETE FROM runs WHERE started < ? AND status NOT IN ('running','queued')",
                        (limit,)).rowcount
        with self.lock:
            for rid in [k for k, v in self.live.items()
                        if v.done and v.finished_at and time.time() - v.finished_at > 600]:
                del self.live[rid]
        return n
