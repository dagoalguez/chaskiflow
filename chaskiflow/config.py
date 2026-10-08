"""Configuración del servidor: config.json (se crea con valores por defecto si no existe)."""

import json
import os
from pathlib import Path

LOCAL_HOST = "127.0.0.1"
SHARE_HOST = "0.0.0.0"

DEFAULTS = {
    "port": 8000,
    "data_dir": "data",                 # aquí van app.db y los archivos temporales
    "plugin_dirs": ["plugins"],         # carpetas donde se buscan plugins
    "max_concurrent_runs": 2,           # workflows ejecutándose a la vez
    "max_parallel_nodes": 4,            # nodos en paralelo dentro de un workflow
    "session_idle_hours": 12,           # cierre de sesión por inactividad
    "run_retention_days": 90,           # 0 = no borrar nunca el historial
    "max_body_mb": 10,                  # tamaño máximo de una petición
    "allow_plugin_edit": True,          # el administrador puede editar/renombrar/eliminar plugins desde la web
    "scheduler_enabled": True,          # programación horaria (hilo interno)
    "scheduler_tick_seconds": 15,       # cada cuánto revisa qué toca ejecutar
}


def load_config(base_dir, path=None, create=True):
    base = Path(base_dir)
    p = Path(path) if path else base / "config.json"
    cfg = dict(DEFAULTS)
    if p.is_file():
        try:
            user = json.loads(p.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            raise SystemExit("config.json no es un JSON válido: %s" % e)
        if not isinstance(user, dict):
            raise SystemExit("config.json debe ser un objeto JSON")
        if "host" in user:
            # versiones anteriores escribían "host": "0.0.0.0" en config.json; ahora se comparte solo con --share
            user.pop("host")
            print("AVISO: «host» de config.json se ignora; para compartir con la red local use:  python servidor.py --share")
        unknown = [k for k in user if k not in DEFAULTS]
        if unknown:
            print("AVISO: claves desconocidas en config.json: %s" % ", ".join(unknown))
        cfg.update({k: v for k, v in user.items() if k in DEFAULTS})
    elif create:
        try:
            p.write_text(json.dumps(DEFAULTS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass
    if os.environ.get("CHASKIFLOW_PORT"):
        cfg["port"] = int(os.environ["CHASKIFLOW_PORT"])
    cfg["host"] = LOCAL_HOST            # por defecto solo este equipo; --share (servidor.py) lo abre a la red
    if os.environ.get("CHASKIFLOW_HOST"):
        cfg["host"] = os.environ["CHASKIFLOW_HOST"]
    cfg["base_dir"] = str(base)
    cfg["data_dir"] = str((base / cfg["data_dir"]).resolve()) if not os.path.isabs(cfg["data_dir"]) \
        else cfg["data_dir"]
    cfg["plugin_dirs"] = [str((base / d).resolve()) if not os.path.isabs(d) else d
                          for d in cfg["plugin_dirs"]]
    return cfg
