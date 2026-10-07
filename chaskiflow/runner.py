"""Proceso hijo que ejecuta UNA tarea. Lo lanza executor.py; no se usa a mano.

Protocolo (JSON, una línea por mensaje):
  entrada  (stdin):  {"plugin_dir", "manifest", "config", "secrets", "inputs", "workdir", "run"}
  salida   (stdout): {"type":"log"|"progress"|"result"|"error", ...}
Todo lo que el plugin imprima con print() va a stderr, así no corrompe el protocolo.
"""

import importlib.util
import io
import json
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.environ.get("CHASKIFLOW_ROOT") or os.path.dirname(_HERE)
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != _HERE]
sys.path.insert(0, _ROOT)


class Secrets:
    """Acceso a los secretos que el plugin DECLARÓ en plugin.json."""

    def __init__(self, declared, values):
        self._declared = set(declared)
        self._values = values

    def get(self, name, default=None):
        if name not in self._declared:
            raise PermissionError("El plugin no declaró el secreto '%s' en plugin.json" % name)
        return self._values.get(name, default)

    def require(self, name):
        v = self.get(name)
        if v in (None, ""):
            raise RuntimeError("Falta el secreto '%s'. Configúrelo en Secretos." % name)
        return v


class Context:
    """Lo que recibe run(config, ctx): registro, progreso, secretos, entradas y carpeta de trabajo."""

    def __init__(self, emit, mask, secrets, inputs, workdir, run):
        self._emit = emit
        self._mask = mask
        self.secrets = secrets
        self.inputs = inputs      # {etiqueta_nodo_anterior: resultado} (si el plugin lo pide)
        self.workdir = workdir
        self.run_id = run.get("run_id")
        self.node = run.get("node")

    def log(self, message, level="info"):
        self._emit({"type": "log", "level": level, "message": self._mask(str(message))})

    def progress(self, done, total=None, message=""):
        self._emit({"type": "progress", "done": done, "total": total,
                    "message": self._mask(str(message))})


def main():
    raw = sys.stdin.buffer.read()
    req = json.loads(raw.decode("utf-8"))
    proto = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n",
                             write_through=True)
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.stdout = sys.stderr  # los print() del plugin no tocan el protocolo

    def emit(obj):
        proto.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        proto.flush()

    manifest = req["manifest"]
    secret_values = {k: v for k, v in (req.get("secrets") or {}).items() if v not in (None, "")}
    needles = [v for v in secret_values.values() if isinstance(v, str) and len(v) >= 4]

    def mask(text):
        for n in needles:
            text = text.replace(n, "***")
        return text

    try:
        workdir = req["workdir"]
        os.chdir(workdir)
        ctx = Context(emit, mask, Secrets(manifest.get("secrets") or [], secret_values),
                      req.get("inputs") or {}, workdir, req.get("run") or {})
        kind = manifest.get("kind", "python")
        config = req.get("config") or {}
        if kind == "http":
            from chaskiflow.declarative import run_http
            result = run_http(manifest["http"], config, secret_values, ctx.log)
        else:
            plugin_dir = req["plugin_dir"]
            sys.path.insert(1, plugin_dir)
            entry = os.path.join(plugin_dir, manifest.get("entry", "task.py"))
            spec = importlib.util.spec_from_file_location("chaskiflow_plugin_task", entry)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "run"):
                raise RuntimeError("task.py debe definir run(config, ctx)")
            result = mod.run(config, ctx)
        if result is None:
            result = {}
        if not isinstance(result, dict):
            result = {"value": result}
        emit({"type": "result", "data": result})
    except BaseException as e:  # incluye SystemExit de un plugin
        if isinstance(e, KeyboardInterrupt):
            raise
        msg = str(e) or type(e).__name__
        if not isinstance(e, (RuntimeError, ValueError, PermissionError)):
            msg = "%s: %s" % (type(e).__name__, msg)
        emit({"type": "error", "message": mask(msg),
              "traceback": mask("".join(traceback.format_exception(type(e), e, e.__traceback__)[-6:]))})


if __name__ == "__main__":
    main()
