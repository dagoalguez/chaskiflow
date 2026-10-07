"""Ejecuta una tarea en un subproceso aislado, con timeout y cancelación."""

import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from .util import kill_tree, now_iso

RUNNER = str(Path(__file__).with_name("runner.py"))
ROOT = str(Path(__file__).resolve().parent.parent)
MAX_LOGS = 2000
MAX_STDERR_FORWARD = 500


class Outcome:
    def __init__(self):
        self.ok = False
        self.result = None
        self.error = None
        self.traceback = None
        self.logs = []
        self.duration = 0.0
        self.reason = ""  # "", "timeout", "cancelled", "crash"


def run_task(payload, *, workdir, timeout, cancel=None, on_event=None, python=None):
    """Lanza runner.py con 'payload' por stdin. Devuelve un Outcome (nunca lanza)."""
    out = Outcome()
    on_event = on_event or (lambda e: None)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["CHASKIFLOW_ROOT"] = ROOT
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    t0 = time.monotonic()
    try:
        proc = subprocess.Popen([python or sys.executable, "-X", "utf8", "-u", RUNNER],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=str(workdir), env=env, **kw)
    except OSError as e:
        out.error = "No se pudo iniciar el proceso de la tarea: %s" % e
        out.reason = "crash"
        return out

    state = {"reason": "", "stderr_forwarded": 0}
    stderr_tail = deque(maxlen=60)

    def add_log(level, message):
        entry = {"ts": now_iso(), "level": level, "message": message}
        if len(out.logs) < MAX_LOGS:
            out.logs.append(entry)
        on_event({"type": "log", **entry})

    def writer():
        try:
            data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            proc.stdin.write(data)
            proc.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass

    def err_reader():
        for line in proc.stderr:
            text = line.decode("utf-8", errors="replace").rstrip("\r\n")
            stderr_tail.append(text)
            if state["stderr_forwarded"] < MAX_STDERR_FORWARD:
                state["stderr_forwarded"] += 1
                add_log("stderr", text)

    def watchdog():
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                state["reason"] = "cancelled"
                kill_tree(proc)
                return
            if time.monotonic() - t0 > timeout:
                state["reason"] = "timeout"
                kill_tree(proc)
                return
            time.sleep(0.05)

    threads = [threading.Thread(target=f, daemon=True) for f in (writer, err_reader, watchdog)]
    for t in threads:
        t.start()

    got_result = got_error = False
    for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            add_log("stdout", line[:500])
            continue
        mtype = msg.get("type")
        if mtype == "log":
            add_log(msg.get("level", "info"), msg.get("message", ""))
        elif mtype == "progress":
            on_event({"type": "progress", "done": msg.get("done"), "total": msg.get("total"),
                      "message": msg.get("message", "")})
        elif mtype == "result":
            out.result = msg.get("data")
            got_result = True
        elif mtype == "error":
            out.error = msg.get("message", "Error desconocido")
            out.traceback = msg.get("traceback")
            got_error = True
    rc = proc.wait()
    for t in threads:
        t.join(timeout=5)
    for pipe in (proc.stdout, proc.stderr):
        try:
            pipe.close()
        except Exception:
            pass
    out.duration = round(time.monotonic() - t0, 3)

    if state["reason"] == "timeout":
        out.reason, out.error = "timeout", "Tiempo excedido (%g s): la tarea fue terminada." % timeout
    elif state["reason"] == "cancelled":
        out.reason, out.error = "cancelled", "Cancelada por el usuario."
    elif got_error:
        out.reason = ""
    elif got_result:
        out.ok = True
    else:
        out.reason = "crash"
        tail = " | ".join(list(stderr_tail)[-5:])
        out.error = "El proceso terminó sin resultado (código %s). %s" % (rc, tail[:600])
    return out
