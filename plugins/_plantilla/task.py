"""Plantilla de plugin. Copie esta carpeta a plugins/<su_id>/ y edite plugin.json y este archivo.

Reglas: solo librería estándar; devuelva un dict (JSON serializable); use ctx.log() para el
registro; lance una excepción con un mensaje claro si algo falla.
La carpeta que empieza con "_" es ignorada por ChaskiFlow: esta plantilla no aparece como plugin.
"""


def run(config, ctx):
    texto = str(config.get("texto") or "")
    veces = int(config.get("veces") or 1)
    ctx.log("Repitiendo %r %d veces" % (texto, veces))
    rows = [{"n": i, "texto": texto} for i in range(1, veces + 1)]
    return {"rows": rows, "total": len(rows)}
