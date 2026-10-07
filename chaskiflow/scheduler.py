"""Programación horaria: un hilo del propio servidor revisa cada pocos segundos qué ejecuciones tocan.

Hora local del servidor. Tipos: 'daily' (hora fija, opcionalmente solo ciertos días) y 'interval'
(cada N minutos). Si el servidor estuvo apagado y el retraso supera `grace_minutes`, esa ejecución se
omite (no se acumulan ejecuciones atrasadas) y se deja constancia.
"""

import json
import re
import threading
import time
import traceback
from datetime import datetime, timedelta

from .access import allows, workflow_level
from .runs import RunError
from .util import now_iso

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
DAY_NAMES = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


class ScheduleError(ValueError):
    pass


def clean_schedule(b):
    """Valida y normaliza el cuerpo de una programación. Devuelve dict de campos."""
    kind = b.get("kind") or "daily"
    if kind not in ("daily", "interval"):
        raise ScheduleError("Tipo de programación inválido (daily o interval)")
    out = {"kind": kind, "time": "", "days": "", "every_minutes": None}
    if kind == "daily":
        m = TIME_RE.match(str(b.get("time") or "").strip())
        if not m:
            raise ScheduleError("La hora debe tener el formato HH:MM (por ejemplo 07:30)")
        out["time"] = "%02d:%s" % (int(m.group(1)), m.group(2))
        days = b.get("days") or []
        if isinstance(days, str):
            days = [d for d in re.split(r"[,\s]+", days) if d != ""]
        try:
            days = sorted({int(d) for d in days})
        except (TypeError, ValueError):
            raise ScheduleError("Los días deben ser números de 0 (lunes) a 6 (domingo)")
        if any(d < 0 or d > 6 for d in days):
            raise ScheduleError("Los días deben ser números de 0 (lunes) a 6 (domingo)")
        out["days"] = ",".join(str(d) for d in days) if len(days) < 7 else ""
    else:
        try:
            ev = int(b.get("every_minutes"))
        except (TypeError, ValueError):
            raise ScheduleError("Indique cada cuántos minutos se ejecuta")
        if not 1 <= ev <= 10080:
            raise ScheduleError("Los minutos deben estar entre 1 y 10080")
        out["every_minutes"] = ev
    try:
        g = int(b.get("grace_minutes", 120))
    except (TypeError, ValueError):
        raise ScheduleError("Los minutos de tolerancia deben ser un número")
    if not 1 <= g <= 1440:
        raise ScheduleError("La tolerancia debe estar entre 1 y 1440 minutos")
    out["grace_minutes"] = g
    v = b.get("variables") or {}
    if not isinstance(v, dict):
        raise ScheduleError("'variables' debe ser un objeto")
    out["variables"] = json.dumps(v, ensure_ascii=False)
    return out


def compute_next(kind, hhmm, days, every_minutes, after):
    """Siguiente instante (epoch, estrictamente posterior a `after`) según la hora local del servidor."""
    if kind == "interval":
        return int(after) + int(every_minutes) * 60
    hh, mm = [int(x) for x in hhmm.split(":")]
    allowed = {int(d) for d in days.split(",") if d != ""} if days else set(range(7))
    start = datetime.fromtimestamp(after)
    for off in range(0, 9):
        day = start + timedelta(days=off)
        if day.weekday() not in allowed:
            continue
        cand = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
        ts = time.mktime(cand.timetuple())
        if ts > after:
            return int(ts)
    raise ScheduleError("No hay ninguna fecha futura con esos días")


def describe(row):
    if row["kind"] == "interval":
        n = row["every_minutes"]
        return "Cada %d min" % n if n < 120 else "Cada %g h" % (n / 60.0)
    days = [int(d) for d in row["days"].split(",") if d != ""] if row["days"] else list(range(7))
    if days == list(range(7)):
        d = "Todos los días"
    elif days == [0, 1, 2, 3, 4]:
        d = "Lun–Vie"
    else:
        d = ", ".join(DAY_NAMES[i] for i in days)
    return "%s a las %s" % (d, row["time"])


class Scheduler:
    def __init__(self, db, runs, tick_seconds=15):
        self.db, self.runs, self.tick_seconds = db, runs, max(1, tick_seconds)
        self._stop = threading.Event()
        self._th = None
        self.lock = threading.Lock()

    def start(self):
        self._th = threading.Thread(target=self._loop, name="scheduler", daemon=True)
        self._th.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(self.tick_seconds):
            try:
                self.tick()
            except Exception:
                traceback.print_exc()

    # ------------------------------------------------------------------
    def tick(self, now=None):
        """Dispara lo que toca. Devuelve lista de (id, estado). `now` (epoch) permite probar sin esperar."""
        now = int(time.time() if now is None else now)
        fired = []
        with self.lock:
            due = self.db.all("SELECT * FROM schedules WHERE enabled=1 AND next_run IS NOT NULL AND next_run<=?", (now,))
            for s in due:
                try:
                    nxt = compute_next(s["kind"], s["time"], s["days"], s["every_minutes"], now)
                except ScheduleError:
                    nxt = None
                cur = self.db.run("UPDATE schedules SET next_run=? WHERE id=? AND next_run=?", (nxt, s["id"], s["next_run"]))
                if cur.rowcount == 0:
                    continue
                status, msg, run_id = self._fire(s, now)
                self.db.run("UPDATE schedules SET last_fire=?, last_status=?, last_message=?, last_run_id=? WHERE id=?",
                            (now, status, msg, run_id, s["id"]))
                self.db.audit("sistema", "schedule." + status, "%s #%d: %s" % (s["name"], s["id"], msg))
                fired.append((s["id"], status))
        return fired

    def _fire(self, s, now):
        late = now - s["next_run"]
        if late > s["grace_minutes"] * 60:
            return "omitida", "Se omitió: el servidor no estaba disponible (retraso de %d min, tolerancia %d min)" % (
                late // 60, s["grace_minutes"]), None
        wf = self.db.one("SELECT * FROM workflows WHERE id=? AND deleted_at IS NULL", (s["workflow_id"],))
        if not wf:
            self.db.run("UPDATE schedules SET enabled=0, next_run=NULL WHERE id=?", (s["id"],))
            return "error", "El workflow fue eliminado: la programación se desactivó", None
        user = self.db.one("SELECT * FROM users WHERE id=? AND active=1", (s["created_by"],))
        if not user:
            return "error", "El usuario que creó la programación está inactivo", None
        level = workflow_level(self.db, user, wf)
        if user["role"] == "viewer" or not level or not allows(level, "run"):
            return "error", "El usuario ya no tiene permiso para ejecutar este workflow", None
        try:
            variables = json.loads(s["variables"] or "{}")
            run_id = self.runs.start(wf, user, variables, trigger="schedule")
        except RunError as e:
            return "omitida", str(e), None
        return "iniciada", "Ejecución iniciada", run_id
