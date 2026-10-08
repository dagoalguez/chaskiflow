# Ejemplo: fusión, escisión y reorganización societaria en los estados financieros de la SMV

Archivo: `examples/smv_fusiones_escisiones.json` (Importar → elegir ese archivo).

## Qué hace

1. **SMV: descargar estados financieros** (`smv_financial_download`). Entra al portal *Información Financiera* de la SMV, busca cada
   empresa y cada año (por defecto 2021–2025, **Individual**, **Anual**) y descarga el PDF de las filas cuyo *Documento* es
   «Estados Financieros y Dictamen». Los guarda en `Carpeta/Descargas/Empresa/Año/`.
2. **PDF: buscar palabras y organizar** (`pdf_keyword_scan`). Lee el texto de cada PDF y busca *fusión*, *escisión* y
   *reorganización societaria* (sin importar mayúsculas ni tildes; acepta plurales y palabras partidas con guion a fin de línea;
   «confusión» no cuenta). Copia los que tienen hallazgos a `Carpeta/IDENTIFICADOS/Empresa/Año/`.
3. Exporta **CSV y Excel** con una fila por PDF (palabras halladas, páginas, un trozo de texto alrededor para revisarlo rápido)
   y un CSV con el detalle de las descargas.

## PDF escaneados (sin texto)

La decisión es **por archivo**: si alguna página del PDF trae texto, se busca solo en el texto y no se usa IA. Solo un PDF **sin ningún texto** (todo escaneado) manda sus páginas, una por una, a un modelo local con visión (por ejemplo **LFM2.5-VL 1.6B en quipullm**). Se extrae la
imagen de la página (JPEG, o imagen sin comprimir/Flate) y se le pregunta qué palabras de la lista aparecen escritas.

- Cada página escaneada puede tardar de 15 a 30 s. Use «Máx. páginas por PDF para la IA» y «Tiempo máximo total».
- Es una ayuda, no una garantía: un modelo pequeño puede no ver una palabra. En la planilla, la columna **Detección** dice si el
  hallazgo fue por *texto* o por *IA* (verifíquelo). Un «no» en un PDF escaneado no es un descarte seguro.
- Si el escaneo viene en un formato que no se puede leer sin instalar programas (JBIG2, CCITT…), o no hay servidor de IA, esas
  páginas **no se leen**: si no hubo hallazgos en el resto, el PDF se copia a `REVISAR_MANUAL/Empresa/Año/` y se anota el motivo.
- Las páginas en blanco o sin imagen no cuentan como «sin leer».

## Cómo se usa

1. Cambie las variables: `carpeta`, `empresas` (separadas por punto y coma: parte del nombre o el código del portal; **vacío = todas**, más de 200),
   `anio_desde`, `anio_hasta`, `ia_url` (IP y puerto de quipullm, termina en `/v1`) y `ia_modelo`.
2. En **Plugins**, apruebe los dos plugins nuevos. Si su servidor de IA usa clave, guárdela en **🔑 Claves** con el nombre que prefiera y escriba ese nombre en el campo **Clave** del Escaneo.
3. Ejecute. Si se corta o se agota el tiempo, vuelva a ejecutar: **no repite** lo descargado ni lo ya revisado.

## Probar el portal sin el workflow

```
python plugins\smv_financial_download\probar_smv.py ALICORP 2022
python plugins\smv_financial_download\probar_smv.py ALICORP 2022 --descargar C:\prueba
```
Con proxy que re-firma SSL agregue `--sin-ssl`.

## Límites

- Depende de cómo está hecho el portal hoy (un formulario ASP.NET). Si la SMV lo cambia, el paso falla con un mensaje claro
  («el formulario del portal cambió»). **Probado solo contra una réplica**: confirme con una empresa y un año antes de lanzar todo.
- Empresas «retiradas» (casilla *Retiradas* del portal) y período *Intermedio* no están soportados.
- Las carpetas no pueden terminar en punto: «ALICORP S.A.A.» queda como «ALICORP S.A.A».
- Todas las empresas × 5 años son más de 1 000 consultas; con 1 s de pausa son ~20 minutos más las descargas.
- Se incluye `pypdf` (BSD) para leer PDF sin instalar nada; no abre PDF cifrados con AES ni dañados (quedan marcados como error).

## Texto de cada PDF

El plugin guarda el texto limpio (sin guiones de fin de línea ni saltos) en `TEXTOS/Empresa/Año/archivo.txt`, con marcas `[p. N]`, y lo reparte en las columnas `texto_1` … `texto_5` (unos 30 000 caracteres cada una; ajustable en «Columnas de texto» y «Caracteres por celda»). Si todo cupo, `texto_completo` dice «sí»; si no, el texto completo está en el archivo `.txt`. Los PDF escaneados leídos por IA no tienen texto, solo hallazgos.

## Diagnóstico de un PDF

`python plugins\pdf_keyword_scan\probar_pdf.py archivo.pdf` muestra por página cuánto texto trae y qué imagen tiene (formato, tamaño y, en JBIG2, los tipos de segmento).
