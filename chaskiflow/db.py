"""SQLite en un solo archivo (app.db) con migraciones automáticas al arrancar.

Las migraciones son idempotentes: usan CREATE TABLE IF NOT EXISTS y ensure_column()
(que mira PRAGMA table_info), así una base vieja o a medias se repara sin perder datos.
Antes de migrar una base con datos se hace una copia app.db.bak_vN_FECHA.
"""

import contextlib
import json
import shutil
import sqlite3
import threading
import time
from pathlib import Path

from .util import now_iso

SCHEMA_VERSION = 2


def table_columns(conn, table):
    return [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]


def ensure_column(conn, table, column, ddl):
    """Agrega la columna si no existe (para bases creadas por versiones anteriores)."""
    if column not in table_columns(conn, table):
        conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl))
        return True
    return False


def _m1(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL COLLATE NOCASE UNIQUE,
      display_name TEXT NOT NULL DEFAULT '',
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'editor' CHECK(role IN ('admin','editor','viewer')),
      active INTEGER NOT NULL DEFAULT 1,
      must_change_password INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL, created_by INTEGER,
      updated_at TEXT, updated_by INTEGER,
      last_login TEXT
    );
    CREATE TABLE IF NOT EXISTS sessions(
      token_hash TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      created_at TEXT NOT NULL, expires_at REAL NOT NULL, last_seen REAL NOT NULL,
      ip TEXT, user_agent TEXT
    );
    CREATE TABLE IF NOT EXISTS workflows(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      definition TEXT NOT NULL,
      owner_id INTEGER NOT NULL REFERENCES users(id),
      team_access TEXT NOT NULL DEFAULT 'none' CHECK(team_access IN ('none','view','run','edit')),
      version INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL, created_by INTEGER,
      updated_at TEXT NOT NULL, updated_by INTEGER,
      deleted_at TEXT, deleted_by INTEGER
    );
    CREATE TABLE IF NOT EXISTS workflow_shares(
      workflow_id INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      permission TEXT NOT NULL CHECK(permission IN ('view','run','edit')),
      PRIMARY KEY(workflow_id, user_id)
    );
    CREATE TABLE IF NOT EXISTS runs(
      id TEXT PRIMARY KEY,
      workflow_id INTEGER, workflow_name TEXT,
      started_by INTEGER, trigger TEXT NOT NULL DEFAULT 'manual',
      status TEXT NOT NULL, started TEXT, finished TEXT, duration REAL NOT NULL DEFAULT 0,
      variables TEXT, error TEXT
    );
    CREATE TABLE IF NOT EXISTS run_nodes(
      run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
      node_id TEXT NOT NULL, label TEXT, type TEXT, status TEXT,
      started TEXT, finished TEXT, duration REAL, error TEXT, reason TEXT,
      config TEXT, logs TEXT, result BLOB, result_size INTEGER,
      PRIMARY KEY(run_id, node_id)
    );
    CREATE TABLE IF NOT EXISTS secrets(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      name TEXT NOT NULL, value TEXT NOT NULL,
      created_at TEXT NOT NULL, created_by INTEGER,
      updated_at TEXT, updated_by INTEGER
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_secrets ON secrets(COALESCE(owner_id, 0), name);
    CREATE TABLE IF NOT EXISTS plugin_state(
      plugin_id TEXT PRIMARY KEY,
      enabled INTEGER NOT NULL DEFAULT 0,
      approved_hash TEXT, updated_at TEXT, updated_by INTEGER
    );
    CREATE TABLE IF NOT EXISTS audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL, user_id INTEGER, username TEXT,
      action TEXT NOT NULL, detail TEXT
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE INDEX IF NOT EXISTS ix_workflows_owner ON workflows(owner_id);
    CREATE INDEX IF NOT EXISTS ix_runs_wf ON runs(workflow_id, started);
    CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);
    """)
    # reparación de bases anteriores: columnas que podrían faltar
    ensure_column(conn, "users", "must_change_password", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "workflows", "team_access", "TEXT NOT NULL DEFAULT 'none'")
    ensure_column(conn, "workflows", "deleted_at", "TEXT")
    ensure_column(conn, "workflows", "deleted_by", "INTEGER")
    ensure_column(conn, "runs", "trigger", "TEXT NOT NULL DEFAULT 'manual'")
    ensure_column(conn, "run_nodes", "reason", "TEXT")


def _m2(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS schedules(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      workflow_id INTEGER NOT NULL, name TEXT NOT NULL DEFAULT '',
      kind TEXT NOT NULL DEFAULT 'daily', time TEXT NOT NULL DEFAULT '',
      days TEXT NOT NULL DEFAULT '', every_minutes INTEGER,
      enabled INTEGER NOT NULL DEFAULT 1, variables TEXT NOT NULL DEFAULT '{}',
      grace_minutes INTEGER NOT NULL DEFAULT 120, next_run INTEGER,
      last_fire INTEGER, last_status TEXT, last_message TEXT, last_run_id TEXT,
      created_by INTEGER, created_at TEXT NOT NULL, updated_by INTEGER, updated_at TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_schedules_due ON schedules(enabled, next_run);
    CREATE INDEX IF NOT EXISTS ix_schedules_wf ON schedules(workflow_id);
    """)


# (versión, función). Para agregar una migración: sube SCHEMA_VERSION y añade aquí _m2, etc.
MIGRATIONS = [(1, _m1), (2, _m2)]


def migrate(conn):
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, fn in MIGRATIONS:
        if version > current:
            fn(conn)
            conn.execute("PRAGMA user_version = %d" % version)
            conn.commit()
    # aunque la versión esté al día, repara columnas faltantes (bases editadas a mano)
    _m1(conn)
    _m2(conn)
    conn.commit()
    return conn.execute("PRAGMA user_version").fetchone()[0]


class Database:
    """Conexión por hilo (SQLite no comparte conexiones entre hilos) con ayudas simples."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.created_new = not self.path.exists() or self.path.stat().st_size == 0
        self.backup_path = None
        self._prepare()

    def _connect(self):
        c = sqlite3.connect(str(self.path), timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA synchronous=NORMAL")
        return c

    def _prepare(self):
        c = self._connect()
        try:
            current = c.execute("PRAGMA user_version").fetchone()[0]
            has_data = c.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0] > 0
            if has_data and current < SCHEMA_VERSION:
                c.execute("PRAGMA wal_checkpoint(FULL)")
                self.backup_path = self.path.with_name("%s.bak_v%d_%s" % (
                    self.path.name, current, time.strftime("%Y%m%d-%H%M%S")))
                shutil.copy2(str(self.path), str(self.backup_path))
            migrate(c)
        finally:
            c.close()

    def conn(self):
        c = getattr(self._local, "c", None)
        if c is None:
            c = self._local.c = self._connect()
        return c

    def close_thread(self):
        c = getattr(self._local, "c", None)
        if c is not None:
            c.close()
            self._local.c = None

    # --- ayudas -----------------------------------------------------------------
    def all(self, sql, params=()):
        return [dict(r) for r in self.conn().execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        r = self.conn().execute(sql, params).fetchone()
        return dict(r) if r else None

    def run(self, sql, params=()):
        c = self.conn()
        cur = c.execute(sql, params)
        c.commit()
        return cur

    @contextlib.contextmanager
    def tx(self):
        c = self.conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise

    def audit(self, user, action, detail=""):
        uid = user["id"] if isinstance(user, dict) else None
        uname = user["username"] if isinstance(user, dict) else (user or "")
        self.run("INSERT INTO audit(ts, user_id, username, action, detail) VALUES(?,?,?,?,?)",
                 (now_iso(), uid, uname, action, str(detail)[:1000]))

    def get_setting(self, key, default=None):
        r = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(r["value"]) if r else default

    def set_setting(self, key, value):
        self.run("INSERT INTO settings(key,value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
