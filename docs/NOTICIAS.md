# Paquete de noticias

Reemplaza el flujo manual de `Noticias.ipynb`. Tres plugins, solo librería estándar:

| Plugin | Qué hace |
|---|---|
| `news_feed_scrape` | **Un nodo por medio.** Lee su feed, filtra, descarga las notas, extrae el texto y marca las relevantes |
| `news_consolidate` | Une los medios, quita duplicados por URL y detecta la misma noticia en varios medios |
| `outlook_send` | Envía, abre o guarda como borrador un correo con adjuntos usando Outlook |

## Puesta en marcha
1. Como administrador: **Plugins** → aprobar los tres (en una instalación nueva ya vienen aprobados).
2. **Importar** → `examples/noticias_diario.json` (6 medios → consolidar → CSV + Excel → correo).
3. Cambie las variables `carpeta` y `destinatarios`.
4. Ejecute. El correo se **abre sin enviarse** (acción `display`); cuando todo esté bien, cámbielo a `send`.

## Validar el extractor en su oficina (importante)
El extractor de texto es propio y heurístico. Pruébelo con una nota real de cada medio:

```
python plugins\news_feed_scrape\probar_url.py https://rpp.pe/politica/...una-nota
python plugins\news_feed_scrape\probar_url.py https://rpp.pe/sitemap/news --feed
```
Muestra la estrategia usada, título, fecha y los primeros 1500 caracteres. Opciones: `--ca ruta.pem`,
`--sin-ssl`, `--proxy http://host:puerto`. Si un medio sale mal, envíeme esa salida y se ajusta.

## Tipos de feed
`auto` (detecta), `news_sitemap`, `rss`, `sitemap_index` (sigue hasta 10 sitemaps hijos), `html_index`
(portada de sección sin feed: toma los links que parecen notas; `url_regex` afina cuáles).

## Qué pasa si falla
- Proxy institucional: error claro con la categoría; lo habilita TI.
- Certificado SSL: use `Certificado CA (.pem)` o desmarque *Verificar SSL* en ese nodo.
- Con `on_error = continue` en el nodo, un medio caído no detiene el flujo (queda en *parcial*).
- En el consolidador, *Medios esperados* lista los que no aportaron notas.

## Relevancia y exclusión
Palabras sin tildes ni mayúsculas, palabra completa. Las listas por defecto vienen de su notebook y se editan
en cada nodo. `exclude_scope = titulo` excluye por título/URL antes de descargar (rápido).

## Recurrencia
TF-IDF + similitud coseno sobre título + primeros 1200 caracteres. `Umbral` 0.40 por defecto: súbalo si agrupa
notas distintas, bájelo si se le escapan. Con *solo entre medios distintos* (por defecto) dos notas del mismo medio
no cuentan como recurrencia. Agrega `recurrencia`, `id_recurrencia`, `nro_medios` y `medios`.
