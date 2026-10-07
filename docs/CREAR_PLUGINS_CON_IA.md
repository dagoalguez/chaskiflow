# Crear plugins con una IA

La "magia" de ChaskiFlow son los plugins, y una IA (Claude, ChatGPT, Copilot…) escribe muy bien plugins pequeños si conoce
el contrato y las restricciones del entorno. ChaskiFlow incluye el prompt para dárselo.

## Paso a paso (administrador)
1. **Plugins → ✨ Crear con IA → Copiar prompt**. (Está también en `docs/PROMPT_CREAR_PLUGIN.txt`.)
2. Péguelo en su IA y reemplace `[DESCRIBE AQUÍ LA TAREA]` por lo que necesita: qué recibe, qué debe devolver y un ejemplo.
   Si el plugin lee una web o API, pegue también un trozo real de la respuesta (HTML/JSON): la IA acierta mucho más.
3. La IA responde con bloques `=== plugin.json ===`, `=== task.py ===`, `=== README.md ===`. Cópielos tal cual.
4. Pegue la respuesta en el segundo cuadro y pulse **Instalar plugin**. Se valida antes de instalarse; si hay errores, se listan
   (cópielos y pídale a la IA que los corrija).
5. El plugin aparece **Pendiente de aprobación**. Ábralo con **Editar**, revise el código y recién entonces **Aprobar**.
6. Pruébelo en un workflow pequeño. Si falla, copie el mensaje de error del historial a la IA.

## Alternativa sin la interfaz
Guarde los archivos en `plugins\mi_plugin\` y valide: `python tools\validar_plugin.py plugins\mi_plugin --probar`.

## Seguridad
Un plugin es código que se ejecuta en el servidor con los permisos de quien lo arrancó. El código de una IA puede tener errores o
hacer más de lo pedido: **léalo antes de aprobar**, sobre todo si usa `subprocess`, `os.remove`, `shutil.rmtree`, `eval/exec`
o conexiones a direcciones que no esperaba. No pegue tokens ni claves reales en el chat con la IA; los secretos se declaran en
`secrets` y se entregan por variables de entorno. Con `"allow_plugin_edit": false` en `config.json` se desactiva todo esto.
