# Contribuir a ChaskiFlow

¡Gracias! El proyecto es pequeño a propósito. Reglas que lo mantienen usable en entornos restringidos:

1. **Solo librería estándar de Python (3.8+)** en el núcleo y en los plugins incluidos. Sin pip, sin npm, sin CDN.
2. **Todo archivo es texto** (`.py .js .css .html .json .md .txt`). Sin binarios ni `.whl`.
3. **Interfaz en español** (hay diccionario ES/EN en `web/app.js`; agregue ambas claves).
4. **Seguridad primero**: la interfaz usa `textContent` (nunca `innerHTML`), el CSP es estricto, solo el
   administrador aprueba plugins. No debilite estas garantías (ver `SECURITY.md`).
5. **Migraciones automáticas**: si cambia el esquema, suba `SCHEMA_VERSION`, agregue `_mN` en `chaskiflow/db.py`
   (idempotente, usando `ensure_column`) y pruebe el salto desde la versión anterior.
6. **Pruebas antes de enviar**: `python tests/run_all.py` debe pasar completo; toda función nueva trae pruebas.
7. **Nada institucional**: ni correos, URLs internas, rutas ni listas de palabras de ninguna organización.

## Flujo

1. Haga una rama, cambie lo mínimo, añada pruebas.
2. Actualice `CHANGELOG.md` (y `LIMITATIONS.md` si aplica).
3. Abra el pull request describiendo el problema, la solución y cómo lo probó.

## Crear un plugin

```
cp -r plugins/_plantilla plugins/mi_plugin
python tools/validar_plugin.py plugins/mi_plugin --probar
```

Guía completa en `docs/PLUGINS.md`. Un plugin incluido debe pasar el validador sin errores ni avisos.

## Licencia

Al contribuir acepta que su aporte se publique bajo la licencia del proyecto (`LICENSE`).
