# Changelog

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
