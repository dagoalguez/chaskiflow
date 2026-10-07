"""Plugin de ejemplo. Contrato mínimo: una función run(config, ctx) que devuelve un dict."""


def run(config, ctx):
    nombre = config.get("nombre") or "mundo"
    filas = int(config.get("filas") or 1)
    ctx.log("Generando %d filas para %s" % (filas, nombre))
    rows = [{"n": i, "mensaje": "Hola, %s (%d)" % (nombre, i)} for i in range(1, filas + 1)]
    return {"mensaje": "Hola, %s" % nombre, "rows": rows, "total": len(rows)}
