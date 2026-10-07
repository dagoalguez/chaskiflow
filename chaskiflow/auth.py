"""Usuarios, contraseñas (PBKDF2 con hashlib) y sesiones por token."""

import base64
import hashlib
import hmac
import secrets
import threading
import time

from .util import now_iso

ITERATIONS = 310000
ALGO = "pbkdf2_sha256"
ROLES = ("admin", "editor", "viewer")
MIN_PASSWORD = 8


def hash_password(password, iterations=ITERATIONS):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "%s$%d$%s$%s" % (ALGO, iterations, base64.b64encode(salt).decode(),
                            base64.b64encode(dk).decode())


def verify_password(password, stored):
    try:
        algo, iters, salt, dk = stored.split("$")
        if algo != ALGO:
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                   base64.b64decode(salt), int(iters))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


def needs_rehash(stored):
    try:
        return int(stored.split("$")[1]) < ITERATIONS
    except Exception:
        return True


def validate_username(name):
    name = (name or "").strip()
    if not 3 <= len(name) <= 40 or not all(c.isalnum() or c in "._-@" for c in name):
        raise ValueError("El usuario debe tener 3–40 caracteres (letras, números, . _ - @)")
    return name


def validate_password(pw):
    if not isinstance(pw, str) or len(pw) < MIN_PASSWORD:
        raise ValueError("La contraseña debe tener al menos %d caracteres" % MIN_PASSWORD)
    if len(pw) > 200:
        raise ValueError("La contraseña es demasiado larga")
    return pw


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Throttle:
    """Limita intentos fallidos de login por (usuario, ip): 5 fallos -> 5 minutos de bloqueo."""

    def __init__(self, max_fail=5, window=300.0):
        self.max_fail, self.window = max_fail, window
        self._fails = {}
        self._lock = threading.Lock()

    def _key(self, username, ip):
        return ((username or "").lower(), ip)

    def blocked(self, username, ip):
        k = self._key(username, ip)
        with self._lock:
            now = time.time()
            self._fails[k] = [t for t in self._fails.get(k, []) if now - t < self.window]
            if len(self._fails[k]) >= self.max_fail:
                return int(self.window - (now - self._fails[k][0])) + 1
        return 0

    def fail(self, username, ip):
        with self._lock:
            self._fails.setdefault(self._key(username, ip), []).append(time.time())

    def ok(self, username, ip):
        with self._lock:
            self._fails.pop(self._key(username, ip), None)


class AuthError(Exception):
    def __init__(self, message, status=401):
        super().__init__(message)
        self.status = status


class Auth:
    def __init__(self, db, session_hours=12, absolute_days=14):
        self.db = db
        self.idle = session_hours * 3600
        self.absolute = absolute_days * 86400
        self.throttle = Throttle()

    # ----- usuarios --------------------------------------------------------------
    def count_users(self):
        return self.db.one("SELECT count(*) AS n FROM users")["n"]

    def public_user(self, u):
        return {"id": u["id"], "username": u["username"], "display_name": u["display_name"],
                "role": u["role"], "active": bool(u["active"]),
                "must_change_password": bool(u["must_change_password"]),
                "created_at": u["created_at"], "last_login": u["last_login"]}

    def create_user(self, username, password, role="editor", display_name="", by=None,
                    must_change=False):
        username = validate_username(username)
        validate_password(password)
        if role not in ROLES:
            raise ValueError("Rol inválido (admin, editor o viewer)")
        if self.db.one("SELECT 1 FROM users WHERE username=?", (username,)):
            raise ValueError("Ya existe un usuario con ese nombre")
        cur = self.db.run(
            "INSERT INTO users(username, display_name, password_hash, role, must_change_password,"
            " created_at, created_by) VALUES(?,?,?,?,?,?,?)",
            (username, (display_name or username).strip()[:80], hash_password(password), role,
             1 if must_change else 0, now_iso(), by["id"] if by else None))
        return self.db.one("SELECT * FROM users WHERE id=?", (cur.lastrowid,))

    def set_password(self, user_id, password, by=None, must_change=False):
        validate_password(password)
        self.db.run("UPDATE users SET password_hash=?, must_change_password=?, updated_at=?, "
                    "updated_by=? WHERE id=?",
                    (hash_password(password), 1 if must_change else 0, now_iso(),
                     by["id"] if by else user_id, user_id))
        self.db.run("DELETE FROM sessions WHERE user_id=?", (user_id,))  # cierra sesiones viejas

    # ----- sesiones --------------------------------------------------------------
    def login(self, username, password, ip="", user_agent=""):
        wait = self.throttle.blocked(username, ip)
        if wait:
            raise AuthError("Demasiados intentos fallidos. Espere %d s." % wait, 429)
        u = self.db.one("SELECT * FROM users WHERE username=?", ((username or "").strip(),))
        ok = bool(u) and u["active"] and verify_password(password or "", u["password_hash"])
        if not u:  # gasta el mismo tiempo para no revelar si el usuario existe
            verify_password(password or "", hash_password("x", 1000))
        if not ok:
            self.throttle.fail(username, ip)
            raise AuthError("Usuario o contraseña incorrectos", 401)
        self.throttle.ok(username, ip)
        if needs_rehash(u["password_hash"]):
            self.db.run("UPDATE users SET password_hash=? WHERE id=?",
                        (hash_password(password), u["id"]))
        token = secrets.token_urlsafe(32)
        now = time.time()
        self.db.run("INSERT INTO sessions(token_hash, user_id, created_at, expires_at, last_seen, ip,"
                    " user_agent) VALUES(?,?,?,?,?,?,?)",
                    (_token_hash(token), u["id"], now_iso(), now + self.absolute, now, ip,
                     (user_agent or "")[:200]))
        self.db.run("UPDATE users SET last_login=? WHERE id=?", (now_iso(), u["id"]))
        return token, self.db.one("SELECT * FROM users WHERE id=?", (u["id"],))

    def user_for_token(self, token):
        if not token:
            return None
        row = self.db.one(
            "SELECT s.token_hash, s.expires_at, s.last_seen, u.* FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash=?", (_token_hash(token),))
        if not row or not row["active"]:
            return None
        now = time.time()
        if row["expires_at"] < now or now - row["last_seen"] > self.idle:
            self.db.run("DELETE FROM sessions WHERE token_hash=?", (row["token_hash"],))
            return None
        if now - row["last_seen"] > 60:  # renueva la actividad sin escribir en cada petición
            self.db.run("UPDATE sessions SET last_seen=? WHERE token_hash=?",
                        (now, row["token_hash"]))
        row.pop("token_hash", None)
        row.pop("expires_at", None)
        row.pop("last_seen", None)
        return row

    def logout(self, token):
        if token:
            self.db.run("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))

    def purge_sessions(self):
        now = time.time()
        self.db.run("DELETE FROM sessions WHERE expires_at < ? OR last_seen < ?",
                    (now, now - self.idle))
