# Cómo crear un plugin

Un plugin es una **carpeta** dentro de `plugins/`. Para instalarlo se copia la carpeta y se pulsa
"Recargar" (o se reinicia el servidor). No se toca el núcleo.

```
plugins/
  mi_tarea/
    plugin.json     <- obligatorio: qué es, qué campos tiene, qué devuelve
    task.py         <- código (solo si kind = "python")
    README.md       <- recomendado
```

Las carpetas que empiezan con `_` o `.` se ignoran. Un plugin con errores aparece en la lista
con sus errores y no se puede usar; nunca rompe el sistema.

## plugin.json

| Clave | Obligatoria | Descripción |
|---|---|---|
| `id` | sí | minúsculas, números y `_` (2–64). Único en todo el sistema |
| `name` | sí | nombre visible |
| `version` | sí | `1.0.0` |
| `kind` | no | `"python"` (por defecto) o `"http"` (declarativo, sin código) |
| `entry` | no | archivo con `run()`; por defecto `task.py` |
| `fields` | no | campos del formulario (ver abajo) |
| `outputs` | no | qué devuelve (documentación para la interfaz y para quien arma el flujo) |
| `secrets` | no | nombres de secretos que el plugin necesita (ver "Secretos") |
| `inputs` | no | `true` si necesita los resultados de los nodos anteriores (ver "Entradas") |
| `requires` | no | módulos Python que necesita (`["requests"]`). El sistema solo **avisa** si faltan |
| `timeout` | no | segundos máximos (por defecto 300). Pasado ese tiempo el proceso se termina |
| `author`, `description`, `icon`, `category` | no | para el catálogo |

### Campos (`fields`)

```json
{"key": "url", "label": "URL", "type": "string", "required": true,
 "default": "", "help": "texto de ayuda", "advanced": false}
```

Tipos: `string`, `text` (multilínea), `password`, `number` (`min`/`max`), `boolean`,
`select` (`options`), `json` (acepta texto JSON y lo convierte), `any` (cualquier valor:
listas, objetos... útil para recibir datos de otro nodo).

El sistema **aplica defaults, convierte tipos y valida** antes de llamar a tu código. Tu
`run()` recibe un diccionario con **todas** las claves declaradas (`None` si no hay valor).

## Plugin con código (`kind: "python"`)

```python
# task.py
def run(config, ctx):
    ctx.log("empezando")                  # aparece en el historial
    ctx.progress(3, 10, "descargando")    # progreso opcional
    token = ctx.secrets.require("api_token")
    return {"total": 3, "rows": [...]}    # siempre un diccionario
```

* Se ejecuta en **un proceso aparte** por cada nodo: si falla o se cuelga, el servidor sigue.
* `print()` es seguro: va al registro, no rompe nada.
* Para fallar con un mensaje claro: `raise RuntimeError("Falta la carpeta X")`.
* Puedes tener otros `.py` en la carpeta del plugin e importarlos (`from mi_modulo import f`).
* `ctx.workdir`: carpeta temporal propia de esta ejecución.
* Solo librería estándar es lo recomendado; si usas otra, decláralo en `requires`.

## Plugin declarativo (`kind: "http"`)

Para integrar una API **sin escribir Python**: se describe la petición en el bloque `http`.
Dentro se puede usar `{{config.campo}}` y `{{secret.nombre}}`.

```json
{
  "id": "whatsapp_texto", "name": "WhatsApp: enviar texto", "version": "1.0.0",
  "kind": "http",
  "secrets": ["whatsapp_token"],
  "fields": [
    {"key": "phone_id", "label": "ID del número", "type": "string", "required": true},
    {"key": "para", "label": "Destinatario", "type": "string", "required": true},
    {"key": "texto", "label": "Mensaje", "type": "text", "required": true}
  ],
  "outputs": [{"key": "message_id", "type": "string"}],
  "http": {
    "method": "POST",
    "url": "https://graph.facebook.com/v20.0/{{config.phone_id}}/messages",
    "headers": {"Authorization": "Bearer {{secret.whatsapp_token}}"},
    "json": {"messaging_product": "whatsapp", "to": "{{config.para}}",
             "type": "text", "text": {"body": "{{config.texto}}"}},
    "response_map": {"message_id": "json.messages[0].id"}
  }
}
```

Claves del bloque `http`: `method`, `url`, `query`, `headers`, `json`, `body`, `timeout`,
`verify_ssl`, `ca_bundle`, `proxy`, `user_agent`, `max_mb`, `fail_on_http_error`,
`success_status`, `response_map`. La respuesta siempre incluye `status`, `ok`, `headers`,
`text`, `json` y `elapsed_ms`; `response_map` agrega campos extra a partir de rutas dentro de
esa respuesta. (El ejemplo es ilustrativo; no está probado contra la API real.)

## Secretos

Los secretos (claves de API, tokens) **no** viajan dentro del JSON del workflow, así se pueden
compartir workflows sin filtrar credenciales. El plugin debe declararlos en `secrets`; solo
esos nombres llegan a su proceso. `ctx.secrets.get(nombre)` o `ctx.secrets.require(nombre)`.
Los valores se enmascaran (`***`) en logs y mensajes de error.
En esta versión el valor sale de la variable de entorno `CHASKIFLOW_SECRET_<NOMBRE>`; el almacén
por usuario llega con la V1.

## Entradas automáticas (`inputs: true`)

Si el plugin necesita **todos** los resultados de los nodos anteriores (por ejemplo, un
consolidador que une las filas de varios medios), declara `"inputs": true` y los recibe en
`ctx.inputs` como `{etiqueta_del_nodo: resultado}`. Solo se incluyen nodos que terminaron bien.

## Datos entre nodos

En la configuración de un nodo se escribe `{{Etiqueta.result.campo}}`.
* Si el valor es solo la expresión, llega con su tipo original (lista, número...).
* Mezclado con texto se convierte a texto.
* `{{Etiqueta.result.campo | default:"n/a"}}` usa un valor alternativo si no existe.
* Solo se pueden usar nodos **conectados antes**; el sistema lo valida antes de ejecutar.
* `{{vars.nombre}}` lee las variables del workflow.

## Empezar rápido: plantilla y validador

```
xcopy /E /I plugins\_plantilla plugins\mi_plugin      (Linux/Mac: cp -r plugins/_plantilla plugins/mi_plugin)
python tools\validar_plugin.py plugins\mi_plugin --probar
```

El validador revisa manifiesto, que `task.py` compile y defina `run(config, ctx)`, que todo sea texto,
que solo se importe librería estándar y (con `--probar`) ejecuta el plugin. Si tiene campos requeridos,
pase valores con `--config "{\"campo\": \"valor\"}"`.

## Checklist para publicar un plugin

- [ ] `plugin.json` válido (`python run_workflow.py --list-plugins` debe mostrarlo con `OK`)
- [ ] Mensajes de error claros, en el idioma de la interfaz
- [ ] Sin secretos ni rutas personales dentro de la carpeta
- [ ] README con un ejemplo de configuración
- [ ] Declarar `requires` y `secrets` con honestidad: el administrador los revisa al instalar
