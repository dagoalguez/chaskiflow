# Importar workflows de G1G

En la barra lateral: **Importar** → pegue o cargue el `.json` de G1G. ChaskiFlow detecta el formato solo
(nodos con `data.task_type`) y muestra un informe con lo que cambió.

| G1G | ChaskiFlow |
|---|---|
| `data.label` con espacios/tildes | etiqueta válida (`El Comercio` → `El_Comercio`); las referencias `{{…}}` se reescriben |
| `news_feed_scrape` | igual; se omiten `headless`, `stealth`, `session_id`, `keep_session`, `seen_key`, `fetch_mode` |
| `link_selector` | no soportado (aviso): use `url_regex` / `include_paths` |
| `config.on_error: continue` | `on_error` del paso |
| `news_consolidate` | igual |
| `data_export` `format: csv` / `xlsx` | paso `export_csv` / `export_xlsx` |
| `data_export` `format: both` | dos pasos (`X` CSV y `X_xlsx`); los adjuntos del correo listan ambos |
| `outlook_send` `body_format`, `send_mode` | `body_is_html`, `mode` |
| bucles / grupos (`foreach`) | no soportado: aviso, el nodo queda suelto |
| tipo desconocido | se conserva con aviso (instale un plugin con ese id) |

Revise siempre el informe y use **Validar** antes de ejecutar. Los campos que usan nombres de resultado
distintos (por ejemplo `{{Paso.result.files}}`) deben ajustarse a los de ChaskiFlow (ver «salidas» de cada plugin).
