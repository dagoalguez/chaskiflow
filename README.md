<p align="center"><img src="docs/img/logo.svg" alt="ChaskiFlow logo" width="72"></p>

# ChaskiFlow

Por **Diego Guevara B.** · Contribuciones: Claude · Licencia Apache-2.0

Plataforma de workflows con **plugins**: armas flujos de tareas (nodos conectados), y quien
quiera una tarea nueva solo agrega una carpeta a `plugins/`, sin tocar el núcleo.

**Solo librería estándar de Python.** Sin pip, sin npm, sin binarios, sin servicios.

> Estado: **v0.6.2** — servidor web multiusuario por LAN, interfaz, plugins con aprobación del
> administrador, claves, historial y **paquete de noticias** (leer medios, recurrencia, Outlook).
> Incluye **editor visual de nodos** (vista Grafo, única vista de edición). Incluye **programación horaria** (diaria por días, o cada N minutos; menú ⋯ → Programar). Incluye **importador de G1G**, plantilla y validador de plugins. Ejecución parcial desde el grafo (este paso / hasta aquí / desde aquí). Repositorio en GitHub. Ver `LIMITATIONS.md`.

## Servidor web (equipo en red local)

```
python servidor.py
```

Abra `http://127.0.0.1:8000` (el servidor imprime también las direcciones de la LAN). La primera vez
pide crear la cuenta del administrador. Los datos viven en `data/app.db` (respaldo = copiar el archivo).
Si otros equipos no entran, permita el puerto 8000 en el Firewall de Windows. Ajustes opcionales en
`config.json` (se crea solo): `host`, `port`, `data_dir`, `plugin_dirs`, `max_concurrent_runs`, `scheduler_enabled`, `scheduler_tick_seconds`, etc.

- **Roles**: admin (todo, instala/aprueba plugins), editor (crea y ejecuta), viewer (solo ve).
- **Compartir**: cada workflow tiene dueño; acceso por persona o por todo el equipo (ver / ejecutar / editar).
- **Plugins**: solo el admin los habilita; si el código de un plugin cambia en disco, queda bloqueado hasta reaprobarlo.
- **Claves** (antes «secretos»): propias o globales (admin); los pasos los usan con `{{secret.nombre}}` y se enmascaran en los registros.
- **Programación**: el servidor mismo dispara las ejecuciones (hora de esa PC, permisos de quien la crea). La PC debe estar encendida y sin suspensión; si estaba apagada a la hora, esa ejecución se omite.
- **Guardado automático**, papelera con deshacer, aviso si dos personas editan a la vez, ES/EN, claro/oscuro.

## Probarlo por consola (2 minutos)

```
python run_workflow.py --list-plugins
python run_workflow.py examples/hola_reporte.json --var carpeta=./salida
python tests/run_all.py
```

Requiere Python 3.8 o superior.

## Qué incluye

| Pieza | Descripción |
|---|---|
| `chaskiflow/engine.py` | Valida el grafo (ciclos, referencias, campos), lo ejecuta en paralelo, maneja errores, timeout y cancelación |
| `chaskiflow/plugin_loader.py` | Descubre plugins, valida manifiestos, calcula su hash |
| `chaskiflow/executor.py`, `runner.py` | Cada tarea corre en un **subproceso aparte** (JSON por stdin/stdout) |
| `chaskiflow/templating.py` | `{{Nodo.result.campo}}` entre nodos, con tipos nativos |
| `chaskiflow/declarative.py` | Plugins sin código: una petición HTTP descrita en JSON |
| `plugins/` | `http_request`, `export_csv`, `export_xlsx`, `hello_world` |
| `chaskiflow/server.py`, `api.py` | Servidor HTTP (stdlib) y API REST |
| `chaskiflow/db.py`, `auth.py`, `access.py` | SQLite con migraciones, PBKDF2, permisos |
| `chaskiflow/runs.py`, `plugin_gate.py` | Ejecuciones en vivo, aprobación de plugins |
| `plugins/news_*`, `outlook_send` | Paquete de noticias (ver `docs/NOTICIAS.md`) |
| `web/` | Interfaz en JavaScript puro (sin compilar, sin CDN) |
| `docs/PLUGINS.md` | Guía para crear plugins |
| `docs/SUCURSALES.md` | Ejemplo: sucursales desde una lista de enlaces con IA local |
| `docs/SMV_FUSIONES.md` | Ejemplo: estados financieros de la SMV, búsqueda de fusión/escisión/reorganización societaria |
| `docs/CREAR_PLUGINS_CON_IA.md` | Crear plugins con una IA (prompt incluido) |

## Ejemplo de workflow

```json
{
  "name": "Hola reporte",
  "variables": {"carpeta": "./salida"},
  "nodes": [
    {"id": "n1", "label": "Datos", "type": "hello_world", "config": {"filas": 5}},
    {"id": "n2", "label": "Excel", "type": "export_xlsx",
     "config": {"data": "{{Datos.result.rows}}", "output_dir": "{{vars.carpeta}}"}}
  ],
  "edges": [{"source": "n1", "target": "n2"}]
}
```

## Hoja de ruta

V1 servidor, usuarios, SQLite, formularios · V2 editor visual + paquete de noticias ·
V3 programación e historial · V4 pulido, plantilla de plugin, validador.

Licencia: Apache-2.0 (ver `LICENSE` y `NOTICE`).

Autor: **Diego Guevara B.** · Contribuciones: **Claude**.
