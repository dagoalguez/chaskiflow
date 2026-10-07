# Seguridad

## Modelo de amenazas (resumen)
ChaskiFlow está pensado para una **red local de confianza**. Protege contra errores y abusos
entre usuarios autenticados, no contra un atacante con acceso a la red ni contra un administrador malicioso.

## Qué hace
- Contraseñas con PBKDF2-HMAC-SHA256 (310 000 iteraciones); tokens de sesión guardados con hash.
- Bloqueo temporal tras 5 fallos por usuario+IP; el cambio de contraseña cierra las demás sesiones.
- Cookie `HttpOnly; SameSite=Strict`; peticiones que modifican exigen `Origin` igual al `Host`.
- CSP estricta (`script-src 'self'; style-src 'self'`), `X-Frame-Options: DENY`, `nosniff`.
  La interfaz nunca usa `innerHTML`; todo el texto entra con `textContent`.
- Servidor de archivos estáticos con protección contra `..`; solo sirve `web/` y tipos conocidos.
- Plugins: solo el administrador los aprueba; el hash SHA-256 cambia si se edita cualquier archivo.
- Cada tarea corre en un subproceso con tiempo límite; los secretos se enmascaran en los registros.

## Qué NO hace
- **No cifra el tráfico (HTTP)**. Use una red de confianza o un proxy inverso con HTTPS.
- **Los secretos están en texto plano** en `data/app.db`.
- **Un plugin de Python es código arbitrario** con los permisos de quien lanza el servidor.
- No hay límite de velocidad global ni protección contra denegación de servicio.

## Reportar una vulnerabilidad
Abra un aviso privado de seguridad en el repositorio (o escriba al mantenedor) en lugar de un issue público.

## Edición de plugins desde la web (v0.7.0)
Un administrador puede editar el código de los plugins desde la interfaz. Ese código se ejecuta en el servidor, igual que
un plugin aprobado por disco, así que equivale a darle al administrador la capacidad de ejecutar código Python. Ya era así
(el administrador aprueba código), pero ahora es más fácil de hacer y de abusar si una cuenta de administrador se compromete.
Mitigaciones: solo rol admin, comprobación de Origin, cookie SameSite=Strict, auditoría de cada edición, validación previa
y copia recuperable al eliminar. Si no la necesita, desactívela con `"allow_plugin_edit": false` en `config.json`.

## Plugins creados con IA (v0.9.0)
«Plugins → Crear con IA» instala código generado por terceros. Siempre queda **pendiente** y solo el administrador lo aprueba;
revise el código antes (Editar). La validación comprueba forma (JSON, compilación, solo librería estándar), **no** intención.
Se desactiva con `"allow_plugin_edit": false`.
