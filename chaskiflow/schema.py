"""Campos de configuración de un plugin: validación del manifiesto y de los valores.

Cada campo (en plugin.json -> "fields") es un diccionario:
  key, label, type, default, required, help, options (select), min, max, advanced,
  placeholder
Tipos: string, text, password, number, boolean, select, json, any
"""

import json

FIELD_TYPES = {"string", "text", "password", "number", "boolean", "select", "json", "any"}
_TRUE = {"true", "1", "si", "sí", "yes", "y", "on", "verdadero"}
_FALSE = {"false", "0", "no", "n", "off", "falso"}


def has_template(v):
    if isinstance(v, str):
        return "{{" in v
    if isinstance(v, dict):
        return any(has_template(x) for x in v.values())
    if isinstance(v, list):
        return any(has_template(x) for x in v)
    return False


def _option_values(field):
    out = []
    for o in field.get("options") or []:
        out.append(o["value"] if isinstance(o, dict) else o)
    return out


def validate_fields(fields):
    """Errores del bloque 'fields' de un manifiesto (lista de textos)."""
    errs = []
    if not isinstance(fields, list):
        return ["'fields' debe ser una lista"]
    seen = set()
    for i, f in enumerate(fields):
        if not isinstance(f, dict):
            errs.append("fields[%d] debe ser un objeto" % i)
            continue
        key = f.get("key")
        if not isinstance(key, str) or not key.isidentifier():
            errs.append("fields[%d]: 'key' inválida (%r)" % (i, key))
            continue
        if key in seen:
            errs.append("campo repetido: '%s'" % key)
        seen.add(key)
        t = f.get("type", "string")
        if t not in FIELD_TYPES:
            errs.append("campo '%s': tipo desconocido '%s'" % (key, t))
        if t == "select" and not _option_values(f):
            errs.append("campo '%s': un 'select' necesita 'options'" % key)
    return errs


def _coerce(field, value):
    t = field.get("type", "string")
    if t in ("string", "text", "password"):
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
    if t == "number":
        if isinstance(value, bool):
            raise ValueError("debe ser un número")
        if isinstance(value, (int, float)):
            n = value
        else:
            s = str(value).strip().replace(",", ".") if isinstance(value, str) else value
            if s == "":
                return None
            try:
                n = int(s) if str(s).lstrip("-").isdigit() else float(s)
            except (TypeError, ValueError):
                raise ValueError("debe ser un número (recibido %r)" % (value,))
        if "min" in field and n < field["min"]:
            raise ValueError("debe ser ≥ %s" % field["min"])
        if "max" in field and n > field["max"]:
            raise ValueError("debe ser ≤ %s" % field["max"])
        return n
    if t == "boolean":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in _TRUE:
            return True
        if s in _FALSE:
            return False
        raise ValueError("debe ser verdadero o falso (recibido %r)" % (value,))
    if t == "select":
        for opt in _option_values(field):
            if opt == value or str(opt) == str(value):
                return opt
        raise ValueError("valor %r no permitido (opciones: %s)"
                         % (value, ", ".join(str(o) for o in _option_values(field))))
    if t == "json":
        if isinstance(value, str):
            if value.strip() == "":
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                raise ValueError("JSON inválido: %s" % e)
        return value
    return value  # any


def _is_missing(field, value):
    if value is None:
        return True
    if field.get("type", "string") in ("string", "text", "password", "select") and value == "":
        return True
    return False


def apply_config(fields, config, skip_templates=False):
    """Aplica defaults, convierte tipos y valida. Devuelve (limpio, errores, avisos).

    skip_templates=True: los valores con {{...}} se dejan como están y no se validan
    (se usa en la validación estática, antes de conocer los resultados de otros nodos).
    El diccionario limpio siempre tiene TODAS las claves declaradas (None si no hay valor).
    """
    config = config or {}
    clean, errors, warnings = {}, [], []
    declared = set()
    for f in fields:
        key = f["key"]
        declared.add(key)
        label = f.get("label") or key
        raw = config.get(key, None)
        if raw is None and "default" in f:
            raw = f["default"]
        if skip_templates and has_template(raw):
            clean[key] = raw
            continue
        if _is_missing(f, raw):
            if f.get("required"):
                errors.append("Falta el campo requerido '%s'" % label)
            clean[key] = None
            continue
        try:
            clean[key] = _coerce(f, raw)
        except ValueError as e:
            errors.append("Campo '%s': %s" % (label, e))
            clean[key] = None
            continue
        if f.get("required") and _is_missing(f, clean[key]):
            errors.append("Falta el campo requerido '%s'" % label)
    for k in config:
        if k not in declared:
            warnings.append("Campo desconocido '%s' (se ignora)" % k)
    return clean, errors, warnings
