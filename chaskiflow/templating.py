"""Plantillas {{ruta.al.valor}} para pasar datos entre nodos.

Reglas:
  * Si un texto es SOLO una expresión ("{{RPP.result.rows}}") se devuelve el valor
    tal cual (lista, diccionario, número...), sin convertirlo a texto.
  * Si la expresión va mezclada con texto ("Total: {{A.result.n}} notas") se
    interpola como texto (listas/diccionarios se escriben como JSON).
  * Rutas: a.b.c, a.lista[0].x, a.lista.0.x
  * Filtro único: {{ruta | default:"valor"}}  (el argumento es JSON). Se usa si la
    ruta no existe o vale null.
"""

import json
import re

__all__ = ["TemplateError", "resolve", "find_refs", "lookup_path"]


class TemplateError(ValueError):
    pass


_EXPR = re.compile(r"\{\{(.*?)\}\}", re.S)
_PATH_PART = re.compile(r"\[(-?\d+)\]|([^.\[\]]+)")


def _split_filter(expr):
    if "|" in expr:
        path, _, flt = expr.partition("|")
        name, _, arg = flt.strip().partition(":")
        return path.strip(), name.strip(), arg.strip()
    return expr.strip(), None, None


def parse_path(path):
    parts = []
    for m in _PATH_PART.finditer(path):
        if m.group(1) is not None:
            parts.append(int(m.group(1)))
        else:
            parts.append(m.group(2).strip())
    if not parts:
        raise TemplateError("expresión vacía '{{}}'")
    return parts


def lookup_path(scope, path):
    """Busca 'a.b[0].c' dentro de scope. Lanza TemplateError si no existe."""
    parts = parse_path(path)
    cur = scope
    walked = []
    for p in parts:
        where = ".".join(walked) or "el contexto"
        if isinstance(cur, dict):
            key = p if isinstance(p, str) else str(p)
            if key not in cur:
                avail = ", ".join(list(cur.keys())[:12])
                raise TemplateError("'%s': no existe '%s' en %s (disponibles: %s)"
                                    % (path, key, where, avail or "ninguno"))
            cur = cur[key]
        elif isinstance(cur, (list, tuple)):
            try:
                idx = p if isinstance(p, int) else int(p)
            except ValueError:
                raise TemplateError("'%s': '%s' no es un índice de lista válido" % (path, p))
            if not -len(cur) <= idx < len(cur):
                raise TemplateError("'%s': índice %d fuera de rango (la lista tiene %d elementos)"
                                    % (path, idx, len(cur)))
            cur = cur[idx]
        else:
            raise TemplateError("'%s': no se puede entrar en '%s' (valor de tipo %s)"
                                % (path, where, type(cur).__name__))
        walked.append(str(p))
    return cur


def _json_arg(arg):
    if arg == "":
        return None
    try:
        return json.loads(arg)
    except json.JSONDecodeError:
        raise TemplateError("argumento de default inválido (debe ser JSON): %s" % arg)


def _eval(expr, scope):
    path, fname, farg = _split_filter(expr)
    if fname not in (None, "default"):
        raise TemplateError("filtro desconocido '%s' (solo existe 'default')" % fname)
    try:
        val = lookup_path(scope, path)
    except TemplateError:
        if fname == "default":
            return _json_arg(farg)
        raise
    if val is None and fname == "default":
        return _json_arg(farg)
    return val


def _to_text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(v, ensure_ascii=False, default=str)


def _resolve_str(s, scope):
    if "{{" not in s:
        return s
    st = s.strip()
    ms = list(_EXPR.finditer(st))
    if len(ms) == 1 and ms[0].span() == (0, len(st)):
        return _eval(ms[0].group(1), scope)
    out, last = [], 0
    for m in _EXPR.finditer(s):
        out.append(s[last:m.start()])
        out.append(_to_text(_eval(m.group(1), scope)))
        last = m.end()
    out.append(s[last:])
    return "".join(out)


def resolve(value, scope):
    """Resuelve todas las plantillas dentro de value (texto, dict o lista)."""
    if isinstance(value, str):
        return _resolve_str(value, scope)
    if isinstance(value, dict):
        return {k: resolve(v, scope) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, scope) for v in value]
    return value


def find_refs(value):
    """Conjunto de raíces usadas en las plantillas (primer segmento de cada ruta)."""
    roots = set()

    def walk(v):
        if isinstance(v, str):
            for m in _EXPR.finditer(v):
                path, _, _ = _split_filter(m.group(1))
                try:
                    first = parse_path(path)[0]
                except TemplateError:
                    continue
                if isinstance(first, str):
                    roots.add(first)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(value)
    return roots
