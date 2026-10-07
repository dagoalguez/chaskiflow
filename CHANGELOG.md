# Changelog

## 0.7.1 — 2026-10-07
- **Corrección (Windows): `[WinError 5] Acceso denegado` al exportar** cuando el CSV/XLSX de hoy ya existe y está abierto
  (por ejemplo en Excel) o lo bloquea un antivirus. `export_csv` y `export_xlsx` reintentan unos segundos y, si sigue
  bloqueado, guardan con otro nombre (`noticias_2026-10-07_1.csv`) y lo avisan en el registro; el correo adjunta el archivo
  realmente escrito. Si ni así se puede, el error indica «Cierre el archivo si lo tiene abierto (¿Excel?)».
- 4 pruebas nuevas (221 en total).

## 0.7.0 — 2026-10-07
- **Plugins editables desde la interfaz** (Plugins → Editar / Renombrar / Eliminar; solo administrador):
  - *Editar*: archivos de texto del plugin (código, `plugin.json`, ayudas) con validación previa en una copia temporal
    (JSON, manifiesto, sintaxis); si estaba habilitado, queda aprobado con el contenido nuevo. Se pueden crear archivos nuevos.
  - *Renombrar*: nombre visible y/o **ID**; cambiar el ID renombra la carpeta y migra automáticamente los workflows que lo usan.
  - *Eliminar*: mueve la carpeta a `_eliminados/` (recuperable a mano) e indica cuántos workflows lo usaban.
  - API: `GET /api/plugins/{id}/files`, `GET|PUT /api/plugins/{id}/file`, `POST /api/plugins/{id}/rename`, `DELETE /api/plugins/{id}`.
    Auditoría `plugin.edit|rename|delete`. Se puede desactivar con `"allow_plugin_edit": false` en `config.json`.
- **Paneles ocultables con ☰**: lista de workflows (☰ de la barra superior), panel de ejecuciones (☰ en la barra de pestañas
  y en su cabecera) y panel del paso (☰ Panel en el grafo). Se recuerda en el navegador.
- 10 pruebas nuevas (217 en total) y prueba de navegador opcional `tests/ui_panels_smoke.py`.

## 0.6.2 — 2026-10-07
- **Interfaz**: se quita la pestaña «Pasos»; el **Grafo** es la única vista de edición (junto a «Ejecuciones»). Sin nodo
  seleccionado, el panel lateral muestra las **Variables** del workflow. Un paso nuevo se coloca a la derecha del nodo
  seleccionado (sin superponerse) y queda conectado a él.
- **Correo**: el campo Adjuntos acepta varias referencias, una por línea, p. ej. `{{Csv.result.file_paths}}` y
  `{{Excel.result.file_paths}}` (CSV y Excel juntos).
- **Ejemplo de noticias**: CSV y XLSX con exactamente los encabezados y el orden del archivo original (Medio, Fecha
  publicación, Título, URL, Sección, Relevante, Palabras detectadas, Recurrencia, N° medios, Medios, ID recurrencia,
  Contenido), el Excel también con columnas y nombres, y el correo adjunta ambos archivos.
- 2 pruebas nuevas (207 en total), incl. verificación de encabezados exactos.

## 0.6.1 — 2026-10-07
- **Nombre oficial: ChaskiFlow** (antes «Flowkit», provisional). Paquete `chaskiflow/`, variables de entorno `CHASKIFLOW_*` (secretos: `CHASKIFLOW_SECRET_*`), cookie `cf_session`. Licencia MIT confirmada.

## 0.6.0 (V3b) — 2026-10-07
- **Importador de G1G**: al importar un JSON con nodos `data.task_type`, se traduce solo (etiquetas válidas con
  referencias reescritas, `data_export` → `export_csv`/`export_xlsx`, `send_mode`/`body_format` de Outlook, campos
  sin equivalente omitidos) y se muestra un **informe de importación**. Código en `chaskiflow/g1g_import.py`.
- `outlook_send`: los adjuntos aceptan listas anidadas (varios pasos de exportación).
- Plantilla de plugin (`plugins/_plantilla/`) y **validador** `tools/validar_plugin.py` (manifiesto, sintaxis, `run`,
  solo texto, solo librería estándar, ejecución de prueba con `--probar`).
- `CONTRIBUTING.md`, `.gitignore`, `docs/IMPORTAR_G1G.md`.
- Limpieza para publicar: sin datos institucionales por defecto. El plugin `news_feed_scrape` ya NO trae palabras
  relevantes por defecto (la lista anterior queda en `PRIVADO/palabras_relevantes.txt`, ignorada por git); el
  ejemplo usa correos y palabras genéricas.
- 19 pruebas nuevas (205 en total).

## 0.5.0 (V3a) — 2026-10-07
- Programación horaria: hilo interno del servidor; tipos diaria (hora fija, por días de la semana) y cada N minutos;
  tolerancia si el servidor estuvo apagado; permisos del creador; auditoría (`schedule.*`).
- API: `GET /api/schedules`, `GET|POST /api/workflows/{id}/schedules`, `PUT|DELETE /api/schedules/{id}`.
- Interfaz: ⋯ → Programar (por workflow) y «Programaciones» (vista global).
- Base de datos **migra a v2** automáticamente (tabla `schedules`) con copia previa `app.db.bak_v1_fecha`.
- Cada hilo de conexión cierra su conexión SQLite (sin ResourceWarning). Config nueva: `scheduler_enabled`, `scheduler_tick_seconds`.
- 18 pruebas nuevas (186 en total).

## 0.4.0 (V2b) — 2026-10-07
- Editor visual de nodos (SVG puro, sin librerías): pestaña **Grafo** con posiciones guardadas, conexión por arrastre,
  validación de ciclos, selección de nodo con su formulario en un panel lateral, zoom/desplazamiento, ajustar y
  ordenar automáticamente, estado de ejecución pintado en los nodos. Convive con la vista de **Pasos**.

## 0.3.0 (V2a) — 2026-10-07
- Paquete de noticias, solo librería estándar: `news_feed_scrape` (sitemap de noticias, RSS, sitemap index,
  portada HTML; filtros por sección/fecha/palabras; relevancia; descarga en paralelo; detección del bloqueo
  del proxy institucional), `news_consolidate` (duplicados por URL + recurrencia TF-IDF/coseno) y
  `outlook_send` (PowerShell + COM; modos enviar / abrir / borrador / solo probar).
- Extractor de texto propio (`newslib.py`) que reemplaza a trafilatura, con `probar_url.py` para validarlo.
- Ejemplo `examples/noticias_diario.json` (6 medios) y `docs/NOTICIAS.md`.
- Corrección: el ejecutor cierra las tuberías del subproceso (avisos ResourceWarning).
- 25 pruebas nuevas (168 en total).

## 0.2.0 (V1) — 2026-10-07
- Servidor web (`python servidor.py`), solo librería estándar: API REST, estáticos, cabeceras de seguridad.
- SQLite con migraciones automáticas (`PRAGMA user_version`) y copia previa `app.db.bak_vN_fecha`.
- Usuarios (PBKDF2-SHA256, sesiones por token, bloqueo por intentos), roles admin/editor/viewer.
- Workflows con dueño, acceso por persona/equipo (ver < ejecutar < editar), versión optimista (409),
  papelera con deshacer, duplicar, importar/exportar JSON.
- Plugins con aprobación del administrador (pendiente / habilitado / cambiado / deshabilitado).
- Secretos por usuario y globales; los workflows usan los del dueño.
- Ejecuciones en vivo (eventos), cancelar, historial, resultados por nodo, retención 90 días.
- Interfaz web (ES/EN, claro/oscuro) con diseño basado en el chat de quipullm: formularios generados
  desde `plugin.json`, referencias `{{Paso.result.campo}}`, variables, autoguardado.
- Auditoría de acciones. 57 pruebas de API nuevas (143 en total).

## 0.1.1 — 2026-10-07
- Pruebas: el servidor local ignora cualquier ConnectionError (en Windows aparecía un traceback inofensivo).
- Verificado en Windows con Python 3.12: 86/86.

## 0.1.0 (V0) — 2026-10-07
- Motor de workflows: validación (ciclos, referencias a nodos no conectados, campos), ejecución
  en paralelo, on_error stop/continue, timeout, cancelación, reejecución de un nodo con semilla.
- Cargador de plugins con manifiesto `plugin.json`, hash SHA-256, plugins inválidos aislados.
- Ejecución de cada tarea en subproceso (protocolo JSON), con enmascarado de secretos.
- Plugins declarativos (`kind: http`) y plugins Python (`run(config, ctx)`).
- Plugins incluidos: http_request, export_csv, export_xlsx (escrito con zipfile), hello_world.
- CLI `run_workflow.py` y batería `tests/run_all.py` (86 pruebas).
