# Sucursales desde una lista de enlaces

Ejemplo: `examples/sucursales_desde_enlaces.json` (impórtelo con «Importar»). Dado un CSV/TXT con sitios web, recorre
cada sitio como lo haría una persona, junta las direcciones de sucursales, tiendas, agencias y oficinas, las estructura con
un **modelo de lenguaje local** y exporta CSV, Excel y un resumen por sitio.

```
Lista (CSV/TXT) → Rastreo (sin IA) → IA local → CSV + Excel
                       └──────────────────────→ Resumen por sitio (CSV)
```

## Antes de ejecutar
1. Variables del workflow: `archivo_enlaces` (ruta del CSV/TXT), `ia_url` (IP y puerto de quipullm, termina en `/v1`),
   `ia_modelo` (vacío = el primero del servidor), `paginas_por_sitio`, `carpeta`.
2. Si su servidor de IA usa clave (`api_key` de quipullm), guárdela en **Secretos** con el nombre `quipullm_key`.
3. Plugins → apruebe `url_list_read`, `site_locations_crawl` y `llm_structure_addresses`.
4. Pruebe primero con 2–3 sitios (`limit` en «Lista») y mire el CSV de resumen.

El archivo de enlaces puede ser un TXT con una URL por línea, o un CSV con encabezado (detecta la columna de enlaces y el
separador `;` `,` tab `|`). Los dominios sueltos (`empresa.pe`) reciben `https://`; los duplicados se quitan.

## Qué hace el rastreo (`site_locations_crawl`)
Lee por orden de prioridad: primero los enlaces cuyo texto o ruta dicen *Ubícanos, Sucursales, Tiendas, Locales, Agencias,
Oficinas, Dirección, Dónde estamos, Contacto, Puntos de venta, Sede, Mapa…*; luego los hijos de esas páginas (un enlace por
distrito o por tienda), la paginación y los **selectores desplegables** cuyas opciones son enlaces; después el resto del sitio
hasta `max_pages`. Usa el `sitemap.xml` y, si la portada no tiene ningún enlace de ubicación, prueba rutas comunes
(`/sucursales`, `/tiendas`, `/contacto`…). Respeta `robots.txt`, hace una pausa entre páginas y solo sigue enlaces del mismo sitio.

De cada página extrae candidatos de dirección desde: datos estructurados (JSON-LD de schema.org), el JSON que usan los
buscadores de tiendas (incrustado en la página o en un `.json`/`api` que la página invoca), etiquetas `<address>`, atributos
`data-lat`/`data-lng`, **mapas** (Google Maps, Waze, OpenStreetMap: coordenadas y consulta) y líneas de texto que parecen
direcciones (Av., Jr., Calle, Mz., Urb., Km…). Si un sitio tiene pocos datos estructurados, entrega además el **texto de sus
páginas de ubicación** para que el modelo lo lea.

## Qué hace la IA local (`llm_structure_addresses`)
Habla con cualquier servidor compatible con OpenAI (`/v1/chat/completions`): quipullm, LM Studio, llama.cpp, Ollama.
- Separa nombre, dirección, distrito, ciudad, departamento, teléfono y horario.
- Descarta lo que no es un local (menús, anuncios, textos legales).
- Lee los textos de páginas y extrae las direcciones que contienen.
- Marca `verificada = no` cuando la dirección que devolvió el modelo **no aparece en el texto original** (control contra
  invenciones): revise esas filas a mano.
- **Solo servidores locales**: rechaza IP públicas salvo que active «Permitir servidores fuera de la red local».
- Si el modelo no responde, la clave es incorrecta o devuelve basura, conserva los datos del rastreo (`fuente = rastreo`).
- Pensado para modelos lentos: consultas pequeñas (`batch_size`), tope `max_items` y espera larga (`timeout`).

## Columnas del resultado
`sitio, nombre, direccion, distrito, ciudad, departamento, telefono, horario, lat, lng, fuente (ia/rastreo), verificada,
metodo (jsonld/json/address/data/texto/mapa/texto_pagina), pagina_url, sitio_url`.

## Límites (honestos)
- **No ejecuta JavaScript.** Si un sitio dibuja sus tiendas con JavaScript después de cargar (mapas interactivos, selectores
  que piden los datos a una API privada con firma o POST), no se verán. Aparecerá en «sin resultados» del resumen: revíselo
  a mano o use la URL del `.json` que ve en las herramientas del navegador (F12 → Red) como enlace de entrada.
- Los selectores desplegables cuyas opciones no son enlaces (solo un id) no se pueden «elegir»; sus nombres se pasan al modelo como pista.
- Sitios con captcha, inicio de sesión o que bloquean el rastreo no se leen. El proxy institucional puede bloquear categorías.
- Un modelo pequeño puede equivocarse: por eso existe la columna `verificada` y se conserva `contexto`/`pagina_url` para auditar.
- Probado con un sitio de prueba y un servidor de IA falso (Linux). **No se ha probado con sitios reales ni con quipullm real.**
  Primero use `python plugins\site_locations_crawl\probar_sitio.py https://sitio.pe` para ver qué encuentra en un sitio.
- Sea considerado: no rastree sitios ajenos con muchas páginas ni con pausas cortas; respete sus términos de uso.
