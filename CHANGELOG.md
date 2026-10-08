# Changelog

## 0.16.4 — 2026-10-08
- **El Registro del Editor arranca plegado** (ocupaba espacio del grafo). Si lo despliega, se queda así durante la sesión; ejecutar ya no lo abre solo, pero su cabecera plegada muestra el estado de la corrida y el paso en curso (▶ nombre). En la pestaña Ejecuciones arranca abierto (es su detalle) y se recuerda aparte.
- Pruebas visuales ajustadas.

## 0.16.3 — 2026-10-08
- **«Acerca de ChaskiFlow»** con el mismo formato que quipullm: logo, nombre y versión centrados, descripción, y tabla **Autor / Contribuciones / Licencia / Repositorio** (enlace a github.com/dagoalguez/chaskiflow). `/api/health` devuelve también `repository`.

## 0.16.2 — 2026-10-08
- Corrección (0.16.1): en la barra ancha aparecía también el botón 🔍 y empujaba «Importar» fuera de la vista. Ahora el 🔍 solo existe en la barra reducida. La prueba visual lo verifica.

## 0.16.1 — 2026-10-08
- **Muchos workflows en la barra lateral.** Barra ancha: **cuadro «Buscar workflow…»** (filtra por nombre o dueño). Barra reducida: ya no lista todos; muestra **solo el abierto y los 5 últimos usados** (se recuerdan en este navegador) y un botón **🔍** que abre un **selector con búsqueda** con todos los workflows (flechas ↑↓ + Enter; sin búsqueda aparecen primero los recientes).
- Prueba nueva `tests/ui_many_smoke.py`.

## 0.16.0 — 2026-10-08
- **Cambio de comportamiento (seguridad): `python servidor.py` ya NO se comparte con la red.** Por defecto escucha solo en `127.0.0.1` (este equipo). Para compartirlo con la LAN: **`python servidor.py --share`** (escucha en `0.0.0.0` e imprime las direcciones de la red). Nuevo `--port N`. Si su `config.json` antiguo trae `"host": "0.0.0.0"` (lo escribían versiones anteriores), ahora se **ignora** con un aviso; la variable de entorno `CHASKIFLOW_HOST` sigue funcionando. **Si su equipo usaba el servidor desde otras PC, agregue `--share` al comando de arranque.**
- **Barra lateral: «reducir» en vez de ocultar.** El botón ☰ ahora deja una columna de iconos (＋ nuevo, ⤓ importar, un círculo con la inicial de cada workflow con su punto de estado, y los accesos de abajo: programaciones, claves, papelera, plugins, usuarios, auditoría); con tooltip. Pulse ☰ otra vez para ampliarla.
- README de GitHub traducido al **inglés** y puesto al día (versión, plugins, `--share`, pestañas Editor/Ejecuciones).
- Pruebas nuevas `tests/test_host.py`.

## 0.15.1 — 2026-10-08
- **Clic derecho en el fondo del grafo → añadir paso** en ese punto, con un **selector con búsqueda** (escriba para filtrar por nombre, categoría o descripción; flechas ↑↓ + Enter, o clic). El menú conserva «Pegar aquí».
- **Clic derecho sobre un paso → «Añadir paso después…»**: crea el paso a su derecha y lo conecta.
- El botón «+ Añadir paso» de la barra usa el mismo selector (reemplaza la lista desplegable larga).
- Solo interfaz; sin cambios en API ni datos.

## 0.15.0 — 2026-10-08
- **Rediseño de Ejecuciones (solo interfaz, sin cambios en el API ni en los datos).** Había dos lugares para ver ejecuciones (panel derecho y pestaña con tabla) y el historial se mostraba «doble». Ahora:
  - **Pestaña «Editor»** (antes «Grafo»): el grafo y el panel del paso, más un **Registro** plegable abajo. Al pulsar «Ejecutar» el grafo se pinta paso a paso (gris → azul girando → verde / rojo) y el Registro lista cada paso con su estado y duración; a la derecha, el detalle del paso activo con sus mensajes en vivo (sigue solo al paso que corre y, al terminar, se queda en el primer error).
  - **Pestaña «Ejecuciones»** (estilo n8n): **lista de ejecuciones a la izquierda**, y a la derecha el **grafo de esa ejecución en solo lectura** con sus colores + el mismo Registro. Pulsar un nodo del grafo selecciona su registro. Se abre sola la ejecución en curso o la más reciente. Desde aquí se puede eliminar una ejecución, limpiar el historial y volver a ejecutar.
  - Se **quitó el panel derecho de ejecuciones** (y su botón ☰) y la tabla del historial. Se conservan las notas «Ejecución parcial» y «Reutiliza el resultado de X», el botón «Ver resultado» y los accesos «Limpiar historial» y «Eliminar esta ejecución».
  - La lista muestra hasta 100 ejecuciones (antes 40).
- Pruebas visuales (`tests/ui_*_smoke.py`) adaptadas; se corrigieron dos selectores frágiles que ya fallaban (papelera en `ui_cleanup_smoke`, arista cero-altura en `ui_graph_smoke`).

## 0.14.3 — 2026-10-07
- **Corrección importante en `pdf_keyword_scan`: PDF con el texto convertido a contornos.** Algunos informes (p. ej. dictámenes de auditoras) no traen capa de texto ni imágenes: cada letra es un trazo vectorial. El plugin los tomaba por páginas «en blanco» (o leía solo el logo JPEG) y los daba como **«sin hallazgo» sin avisar**. Ahora una página sin texto con al menos `vec_min_rellenos` (30) rellenos vectoriales se **dibuja** (nuevo `vecrender.py`, Python puro, ≈0,6 s por página a 200 dpi) y esa imagen se manda a la IA. Vale también en PDF mixtos (páginas con texto + páginas dibujadas). Sin servidor de IA, esas páginas quedan como **SIN LEER** y el PDF va a `REVISAR_MANUAL`.
- Respeta `/Rotate`, baja los dpi si la página es enorme y corta el dibujo a los 120 s. Las imágenes incrustadas (logos, firmas) no se dibujan.
- Campos avanzados nuevos: «Rellenos vectoriales mínimos» y «Resolución para dibujar páginas vectoriales». «Tiempo máximo por PDF» sube de 600 a 1800 s (40 páginas × 15–30 s de IA superaban los 600 s).
- Nuevo valor `texto+ia` en `metodo` (PDF con texto y alguna página dibujada leída con IA).
- **Aviso al actualizar:** los resultados guardados en `_cache_escaneo.json` de PDF de este tipo eran falsos negativos; la clave de caché cambió y se **vuelven a revisar** solos. Revise también los «sin hallazgo» de corridas anteriores con PDF de auditoras.
- Pruebas nuevas (`tests.test_smv.VectorPages`): fallan con el `task.py` anterior.

## 0.14.2 — 2026-10-07
- `pdf_keyword_scan`: la línea de registro por PDF ahora indica páginas en blanco, páginas SIN LEER y el **motivo** (formato de imagen no soportado, tope «Máx. páginas por PDF para la IA» o «Tiempo máximo por PDF»).

## 0.14.1 — 2026-10-07
- «Probar conexión»: si el servidor responde que el modelo no tiene visión (falta el mmproj), el mensaje lo explica y dice qué hacer.

## 0.14.0 — 2026-10-07
- **«Secretos» pasa a llamarse «Claves»** en toda la interfaz y los mensajes (el API sigue en `/api/secrets`).
- **Nombre de clave a elección:** nuevo tipo de campo `secret`. Los plugins de IA (`pdf_keyword_scan`, `llm_structure_addresses`) ya no exigen una clave con nombre fijo (`quipullm_key`): el campo **Clave** acepta el nombre que usted guardó (con lista desplegable de sus claves). Vacío = el servidor no pide clave. Un nombre que no existe detiene el paso con un mensaje claro.
- **Botón «Probar conexión con la IA»** en esos plugins (nuevo `"test"` en `plugin.json` y `POST /api/plugins/<id>/test`): comprueba servidor, clave, modelo y que el modelo **vea imágenes** (le envía un cuadro rojo), mostrando el detalle.
- Los ejemplos traen la variable `ia_clave` (vacía) para escribir el nombre de la clave.
- **Aviso al actualizar:** si ya tenía guardada `quipullm_key`, escriba ese nombre en el campo «Clave» (o en la variable `ia_clave`).

## 0.13.6 — 2026-10-07
- Panel de **Variables**: el valor se muestra **debajo** del nombre (a ancho completo) en vez de al lado, donde quedaba cortado en el panel angosto.

## 0.13.5 — 2026-10-07
- `pdf_keyword_scan`: guarda el **texto limpio completo** de cada PDF (`TEXTOS/Empresa/Año/archivo.txt`, con marcas `[p. N]`) y lo reparte en las columnas `texto_1…texto_5` (≈30 000 caracteres por celda; configurable). `texto_completo` indica si todo cupo en la tabla. Las columnas se agregaron al ejemplo (CSV y Excel).
- Nuevo `probar_pdf.py` (diagnóstico): por página, texto e imagen y, si es JBIG2, los tipos de segmento. Sirve para decidir si se puede leer ese formato sin instalar nada.

## 0.13.4 — 2026-10-07
- `pdf_keyword_scan`: la IA se decide **por archivo**. Si alguna página del PDF trae texto, se busca solo en el texto (ninguna página usa IA). Solo un PDF con cero texto (todo escaneado) manda sus páginas a la IA, una por una.

## 0.13.3 — 2026-10-07
- `pdf_keyword_scan`: si el servidor de IA falla ya **no se aborta** el escaneo; los PDF con texto se buscan directo y solo los escaneados quedan en REVISAR_MANUAL (y no se recuerdan, para reintentarlos).

## 0.13.2 — 2026-10-07
- `smv_financial_download`: el registro lista las empresas elegidas y recuerda que solo se descargan las escritas en «Empresas» (vacío = todas).
- `pdf_keyword_scan`: una línea por PDF con páginas con texto / sin texto / leídas con IA, para ver qué se procesa por IA.

## 0.13.1 — 2026-10-07
- Corrección: si la URL del servidor de IA se escribe sin `/v1` (p. ej. `http://localhost:1234`), `pdf_keyword_scan` y `llm_structure_addresses` la completan solos; antes daban «HTTP 404 Route not found: /chat/completions».

## 0.13.0 — 2026-10-07
- **Ejemplo «SMV: fusiones, escisiones y reorganizaciones»** (`examples/smv_fusiones_escisiones.json`, `docs/SMV_FUSIONES.md`).
- Plugin nuevo **`smv_financial_download`**: busca en el portal *Información Financiera* de la SMV cada empresa y año (Individual/Consolidada, Anual) y descarga los «Estados Financieros y Dictamen». Retoma sin repetir, reintenta, sigue ante errores y admite «Tiempo máximo total». `probar_smv.py` para probar una empresa desde la consola.
- Plugin nuevo **`pdf_keyword_scan`**: busca palabras en PDF (texto; sin mayúsculas, tildes, con plurales y guiones de fin de línea) y copia los que tienen hallazgos a `IDENTIFICADOS/Empresa/Año`. Las **páginas sin texto** se leen con un modelo local con visión (LFM2.5-VL en quipullm); lo que no se pueda leer va a `REVISAR_MANUAL`. Recuerda lo revisado para continuar sin repetir. Incluye **pypdf 6.19.0** (BSD, pura Python; ver `NOTICE`), sin pip ni binarios.
- Pruebas nuevas `tests/test_smv.py` con un portal simulado (formulario con `__VIEWSTATE`, paginación), PDF de prueba generados sin librerías (`tests/pdfmaker.py`) y visión simulada.

## 0.12.0 — 2026-10-07
- **Duplicar, copiar y pegar pasos en el grafo.** Clic derecho en un paso: *Duplicar* (Ctrl+D), *Copiar* (Ctrl+C), *Eliminar*. Clic derecho en el fondo: *Pegar aquí* (Ctrl+V). Se puede pegar también en **otro workflow**.
- **El paso pegado queda sin conexiones.** Para que no haya referencias rotas, las plantillas que apuntan a otros pasos (`{{Paso.result...}}`) se **vacían** y el aviso lo indica; `{{vars.x}}` se conserva y, si la variable no existe en el workflow destino, se crea con su valor. El nombre se hace único («Rastreo2»).
- El aviso al pegar trae **Deshacer** (quita el paso y las variables agregadas).
- Prueba nueva `tests/ui_copy_smoke.py`.

## 0.11.7 — 2026-10-07
- **Corrige «tiempo excedido de 7200 s» en el rastreo con muchos enlaces.** Ese límite era el tope de todo el paso (2 h), no un ajuste; con ~100 sitios se superaba y se perdía lo recogido. Ahora el tope del paso es de **12 h** en `site_locations_crawl` y `llm_structure_addresses`.
- Campo nuevo **«Tiempo máximo total (s)»** en ambos plugins (0 = sin límite propio). Al agotarse, el paso termina bien: no inicia más sitios (quedan marcados «tiempo total» en el resumen) o no envía más consultas al modelo (conserva el dato del rastreo), y avisa en el registro.
- Los dos plugins cambian de huella: hay que **volver a aprobarlos** en Plugins.

## 0.11.6 — 2026-10-07
- **Al volver a un workflow que está ejecutándose, la pantalla se reconecta sola** al avance en vivo (grafo con el nodo en curso, registros, botón Detener). Antes había que abrir la ejecución desde el historial.
- La lista lateral se refresca cada pocos segundos mientras haya ejecuciones en curso (el punto pasa de azul a verde/rojo al terminar sin tocar nada) y marca el workflow apenas se lanza.
- Prueba nueva `tests/ui_reconnect_smoke.py`.

## 0.11.5 — 2026-10-07
- El logo aparece al inicio del `README` (centrado, como en quipullm); copia en `docs/img/logo.svg`.

## 0.11.4 — 2026-10-07
- **Logo transparente**, en el mismo estilo de línea que el de quipullm (trazo azul, sin fondo): el flujo de nodos con la flecha de llegada. En el login y en «Acerca de» es SVG en línea y toma el color del tema; en la cabecera y la pestaña usa `web/logo.svg`.

## 0.11.3 — 2026-10-07
- **Créditos dentro de la aplicación**: línea «ChaskiFlow vX · Diego Guevara B. · Apache-2.0» en el login y al pie de la barra lateral, y diálogo «Acerca de» (autor, contribuciones, licencia, aviso de copyright). `/api/health` informa autor, contribuciones y licencia.

## 0.11.2 — 2026-10-07
- Licencia cambiada de MIT a **Apache-2.0** (igual que quipullm). Créditos: autor Diego Guevara B.; contribuciones: Claude (`NOTICE`, `AUTHORS`, `README`).

## 0.11.1 — 2026-10-07
- El prompt «Crear con IA» (`docs/PROMPT_CREAR_PLUGIN.txt`) ya no menciona dónde corre ChaskiFlow; se conservan las reglas técnicas del entorno.

## 0.11.0 — 2026-10-07
- **Nuevo ejemplo «Sucursales desde una lista de enlaces»** (`examples/sucursales_desde_enlaces.json`, `docs/SUCURSALES.md`):
  CSV/TXT de sitios → rastreo completo → IA local → CSV, Excel y resumen por sitio.
- Plugin **`url_list_read`** (Lista de enlaces): CSV/TXT, detecta columna/separador/codificación, agrega https://, quita duplicados.
- Plugin **`site_locations_crawl`** (Sitios: rastrear sucursales): recorre cada sitio por prioridad (Ubícanos, Sucursales, Tiendas…,
  enlaces por distrito, selectores, paginación, sitemap), respeta robots.txt, y extrae candidatos de JSON-LD, JSON de buscadores de tiendas,
  `<address>`, `data-lat/lng`, mapas incrustados y texto. Incluye `probar_sitio.py` para probar un sitio desde la consola.
- Plugin **`llm_structure_addresses`** (IA local): servidor compatible con OpenAI (quipullm, LM Studio…) con IP y clave (secreto
  `quipullm_key`); estructura direcciones, descarta lo que no es un local, lee textos de páginas, marca `verificada` y, si el modelo
  falla, conserva los datos del rastreo. Solo servidores de la red local salvo autorización expresa.
- 17 pruebas nuevas (259 en total) con un sitio de prueba y un servidor de IA falso.

## 0.10.1 — 2026-10-07
- **Grafo y ejecuciones del historial**: al abrir una ejecución pasada, el grafo ahora se pinta con el estado que tuvo cada paso
  (ok, error, omitido, cancelado…). Al volver a «← Historial» o cambiar de workflow se limpia.
- Prueba de navegador ampliada (`tests/ui_cleanup_smoke.py`).

## 0.10.0 — 2026-10-07
- **Logo e icono**: `web/logo.svg` (flujo de nodos con el «mensaje» en ámbar) en el login, la barra superior y como icono de la pestaña.
- **Modo oscuro**: los campos de hora/fecha (p. ej. «Hora (del servidor)» al programar) ahora tienen el mismo estilo que el resto de
  campos y el selector nativo usa el tema oscuro; antes quedaban con fondo claro y texto casi invisible.
- **Cerrar workflow**: botón ✕ en la barra del workflow (vuelve a la pantalla inicial; guarda antes si hay cambios).
- **Borrar ejecuciones**: ✕ en cada fila del historial (panel y pestaña Ejecuciones), «Eliminar esta ejecución» en el detalle y
  «Limpiar historial…» (conservar las últimas N). Las ejecuciones en curso no se pueden borrar. API: `DELETE /api/runs/{id}`,
  `POST /api/workflows/{id}/runs/clear {"keep": N}`.
- **Papelera**: «Eliminar definitivamente» por workflow y «Vaciar papelera» (borra también su historial y programaciones; solo el
  dueño o un administrador). API: `DELETE /api/workflows/{id}/purge`, `POST /api/workflows/trash/empty`.
- **Barra lateral ordenada**: dos grupos («Mi espacio»: Programaciones, Secretos, Papelera; «Administración»: Plugins, Usuarios, Auditoría)
  con una opción por fila.
- Corrección: error de JavaScript si se cerraba o cambiaba de workflow mientras terminaba el guardado automático.
- 5 pruebas nuevas (242 en total) y prueba de navegador `tests/ui_cleanup_smoke.py`. BD sin cambios (v2).

## 0.9.0 — 2026-10-07
- **Crear plugins con IA**: Plugins → «✨ Crear con IA» muestra un prompt listo para copiar (`docs/PROMPT_CREAR_PLUGIN.txt`:
  contrato completo, reglas del entorno —solo librería estándar, solo texto— y formato de entrega) y un cuadro para pegar la
  respuesta de la IA (bloques `=== plugin.json ===` / `=== task.py ===`, o JSON). Se valida (JSON, manifiesto, compila, solo
  librería estándar, nombres de archivo) y se instala **pendiente de aprobación**: el administrador revisa el código antes de aprobar.
- API (admin): `GET /api/plugins/prompt`, `POST /api/plugins/import` (`text` o `files`, `overwrite`). Respeta `allow_plugin_edit`.
- Nuevo `docs/CREAR_PLUGINS_CON_IA.md`. 8 pruebas nuevas (237 en total) y prueba de navegador `tests/ui_ai_plugin_smoke.py`.

## 0.8.0 — 2026-10-07
- **Ejecución parcial desde el grafo**: al seleccionar un nodo aparecen «▶ Este paso», «▶ Hasta aquí» y «▶ Desde aquí».
  Los pasos que no se ejecutan reutilizan su último resultado correcto (de las 20 ejecuciones más recientes) y la ejecución
  parcial queda en el historial. Si a un paso le falta el resultado de un antecesor que usa, se explica con un mensaje claro
  (use «Hasta aquí» o ejecute el flujo completo una vez). El panel de ejecuciones indica «Ejecución parcial» y qué resultados reutiliza.
- API: `POST /api/workflows/{id}/run` con `{"only": [ids]}` (ya existía) ahora toma por defecto los últimos resultados correctos y
  devuelve `reused`; `from_run` sigue permitiendo fijar una ejecución concreta.
- 8 pruebas nuevas (229 en total) y prueba de navegador `tests/ui_partial_smoke.py`.

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
