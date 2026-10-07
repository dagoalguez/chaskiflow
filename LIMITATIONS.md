# Limitaciones conocidas (v0.2.0)

Honestas y a propósito: aquí va lo que **no** hace o **no se ha medido**.

## No implementado todavía
- Publicación en GitHub (licencia Apache-2.0; falta verificar que el nombre «ChaskiFlow» no choque con otro proyecto).
- Importador G1G: no soporta bucles (`foreach`/grupos) ni tareas sin plugin equivalente; se importan sueltas con aviso.
- Sin bucles `foreach` ni nodos condicionales (el grafo es un DAG simple).
- Sin cambio de contraseña "olvidada" por correo: el admin la restablece en Usuarios.

## Sucursales (rastreo + IA local)
- No ejecuta JavaScript; no se ha probado con sitios reales ni con quipullm real. Ver `docs/SUCURSALES.md`.

## Programación
- Corre **dentro del servidor**: si `servidor.py` no está en marcha (o la PC está apagada/suspendida) a la hora
  indicada, esa ejecución **se omite** si el retraso supera la tolerancia (120 min por defecto); no se acumulan.
  Desactive la suspensión de Windows en la PC del servidor.
- Usa la **hora local de la PC del servidor**. Sin fechas puntuales ni calendarios de feriados.
- Se ejecuta con los permisos de **quien creó la programación**; si esa persona se desactiva o pierde acceso, falla
  con un mensaje (no ejecuta). Un workflow eliminado desactiva sus programaciones.
- Si el workflow ya se está ejecutando a esa hora, la programada se omite. Probado con relojes simulados y con el hilo
  real (1 s); **no se ha probado dejando el servidor días seguidos** ni el cambio de horario (Perú no lo usa).

## Editor visual
- Pestaña **Grafo**: mover nodos, conectar arrastrando del punto derecho al izquierdo, rechazo de ciclos, borrar con
  «Quitar»/Suprimir, zoom con rueda, estado en vivo. Solo se probó con ratón en Chromium; **no hay deshacer de
  cambios en el grafo** (salvo reimportar) ni selección múltiple, ni soporte táctil verificado.

## Noticias
- **El extractor de texto propio solo se probó con páginas sintéticas**, no con los medios reales (este entorno
  no llega a ellos). Antes de confiar, corra `python plugins\news_feed_scrape\probar_url.py <url-de-una-nota>`
  con una nota de cada medio y compare con lo que obtenía con trafilatura.
- No hay navegador (Playwright): si un medio carga el texto con JavaScript, saldrá sin cuerpo. Perú21 puede
  necesitar `url_regex`; no se usan selectores CSS.
- `outlook_send` **no se pudo probar con Outlook real** (solo el modo "Solo probar"). Pruebe primero con la acción
  "display" (abre el correo sin enviarlo). Requiere Outlook de escritorio abierto en la PC que corre el servidor.
- Un medio que falla no aparece en el resumen salvo que se liste en "Medios esperados" del consolidador.
- Si el proxy bloquea un dominio, solo TI puede habilitarlo; ChaskiFlow lo detecta y lo dice.

## Seguridad
- **Un plugin de Python es código arbitrario**: corre con los permisos del usuario que lanza el
  servidor. Que corra en un proceso aparte lo protege de caídas, **no de un plugin malicioso**.
  Con la librería estándar no hay una forma fiable de aislarlo en Windows. Instale solo plugins
  que haya revisado (el hash SHA-256 de cada plugin está en el catálogo).
- Los plugins de exportación escriben en cualquier carpeta que se les indique.
- **Sin TLS**: el tráfico en la LAN va por HTTP sin cifrar (contraseñas y secretos incluidos). Úselo solo
  en una red de confianza o detrás de un proxy inverso con HTTPS.
- **Los secretos se guardan en texto plano dentro de `data/app.db`** (sin dependencias no hay cifrado
  fuerte disponible). Proteja la carpeta `data/` y sus copias de seguridad.
- Defensas del servidor: cookie HttpOnly + SameSite=Strict, comprobación de Origin en peticiones que
  modifican, CSP sin scripts/estilos en línea, bloqueo tras 5 intentos fallidos por usuario+IP.
- Los plugins se ejecutan con los permisos del usuario que lanza el servidor; la aprobación del admin
  (hash SHA-256) es el control principal.

## Pruebas
- 143 pruebas automáticas (motor 86 + API 57). Verificado en Linux (Python 3.13); las 86 del motor
  también en Windows 3.12. **Las 143 aún no se han corrido en Windows**: ejecute `python tests\run_all.py`.
- La interfaz se probó en Chromium (flujo completo: crear, editar, ejecutar, compartir, conflicto,
  papelera, claro/oscuro) pero **no en Edge/Chrome de Windows ni en pantallas táctiles**.
- Las pruebas de `http_request` usan un servidor local, no sitios reales. No se ha probado
  detrás de un proxy que re-firme SSL.
- La verificación de que el XLSX abre bien se hizo con openpyxl, no con Excel.
