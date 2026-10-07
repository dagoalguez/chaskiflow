"""Utilidades pequeñas compartidas por el motor."""

import os
import signal
import subprocess
import sys
from datetime import datetime


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def kill_tree(proc):
    """Mata el proceso y sus hijos (Windows: taskkill /T; POSIX: grupo de procesos)."""
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=15)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def summarize(value, max_str=200, max_items=5, depth=0):
    """Vista compacta de un valor, para registros y pantallas (no para pasar datos)."""
    if isinstance(value, str):
        if len(value) <= max_str:
            return value
        return value[:max_str] + "… (+%d caracteres)" % (len(value) - max_str)
    if isinstance(value, dict):
        if depth >= 3:
            return "{…%d claves}" % len(value)
        return {k: summarize(v, max_str, max_items, depth + 1)
                for k, v in list(value.items())[:30]}
    if isinstance(value, (list, tuple)):
        items = [summarize(v, max_str, max_items, depth + 1) for v in value[:max_items]]
        if len(value) > max_items:
            items.append("… (+%d elementos)" % (len(value) - max_items))
        return items
    return value
