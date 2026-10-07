"""Registro de rutas del API (decorador @route) y objetos de petición."""

import json
import re

ROUTES = []


class ApiError(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


def route(method, pattern, auth="user"):
    """auth: 'public' | 'user' | 'admin' | 'editor' (editor o admin)."""
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn, auth))
        return fn
    return deco


def find_route(method, path):
    path_matched = False
    for m, rx, fn, auth in ROUTES:
        mo = rx.match(path)
        if mo:
            path_matched = True
            if m == method:
                return fn, auth, mo.groupdict(), True
    return None, None, None, path_matched


class Req:
    def __init__(self, app, method, path, query, raw, params, user, token, ip, user_agent):
        self.app = app
        self.method = method
        self.path = path
        self.query = query
        self.raw = raw
        self.params = params
        self.user = user
        self.token = token
        self.ip = ip
        self.user_agent = user_agent
        self._json = None
        self.set_session = None     # los manejadores de login lo rellenan con el token nuevo
        self.clear_session = False  # logout

    @property
    def db(self):
        return self.app.db

    def body(self):
        if self._json is None:
            if not self.raw:
                self._json = {}
            else:
                try:
                    self._json = json.loads(self.raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    raise ApiError(400, "El cuerpo de la petición no es JSON válido")
        if not isinstance(self._json, dict):
            raise ApiError(400, "El cuerpo debe ser un objeto JSON")
        return self._json

    def qint(self, name, default, lo=0, hi=1000):
        try:
            v = int(self.query.get(name, [default])[0])
        except (TypeError, ValueError):
            v = default
        return max(lo, min(hi, v))

    def qstr(self, name, default=""):
        return self.query.get(name, [default])[0]

    def pid(self, name="id"):
        try:
            return int(self.params[name])
        except (KeyError, ValueError):
            raise ApiError(400, "Identificador inválido")
