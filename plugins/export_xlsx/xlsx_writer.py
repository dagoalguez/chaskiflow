"""Escritor mínimo de .xlsx con la librería estándar (zipfile + XML a mano).

Soporta una hoja, encabezado en negrita, fila fija, autofiltro, anchos de columna,
números, booleanos y texto. Los textos se guardan como texto (nunca se evalúan como fórmula).
"""

import re
import zipfile
from xml.sax.saxutils import escape

MAX_ROWS = 1048576
MAX_CELL = 32767
_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")
_BAD_SHEET = re.compile(r"[\[\]:*?/\\]")


def col_letter(idx):  # 0 -> A
    s = ""
    idx += 1
    while idx:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def clean_text(value, limit=MAX_CELL):
    text = _ILLEGAL.sub("", str(value))
    return text[:min(limit or MAX_CELL, MAX_CELL)]


def sheet_title(name):
    name = _BAD_SHEET.sub("_", str(name or "Datos")).strip("'").strip() or "Datos"
    return name[:31]


def _cell(ref, value, style, limit):
    s = ' s="%d"' % style if style else ""
    if value is None:
        return ""
    if isinstance(value, bool):
        return '<c r="%s" t="b"%s><v>%d</v></c>' % (ref, s, 1 if value else 0)
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            return ""
        return '<c r="%s"%s><v>%s</v></c>' % (ref, s, repr(value))
    text = escape(clean_text(value, limit))
    return '<c r="%s" t="inlineStr"%s><is><t xml:space="preserve">%s</t></is></c>' % (ref, s, text)


def write_xlsx(path, header, rows, sheet_name="Datos", max_cell_chars=MAX_CELL):
    """rows: lista de listas (mismo largo que header). Escribe 'path'."""
    if len(rows) + 1 > MAX_ROWS:
        raise ValueError("Excel admite hasta %d filas (hay %d)" % (MAX_ROWS - 1, len(rows)))
    ncols = max(len(header), 1)
    last_col = col_letter(ncols - 1)
    widths = []
    for ci, h in enumerate(header):
        longest = len(str(h))
        for r in rows[:200]:
            v = r[ci] if ci < len(r) else None
            if isinstance(v, str):
                longest = max(longest, min(len(v), 60))
        widths.append(min(max(longest + 2, 10), 60))

    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           '<sheetViews><sheetView workbookViewId="0">'
           '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
           '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/><cols>']
    for ci, w in enumerate(widths):
        out.append('<col min="%d" max="%d" width="%d" customWidth="1"/>' % (ci + 1, ci + 1, w))
    out.append("</cols><sheetData>")
    out.append('<row r="1">%s</row>' % "".join(
        _cell("%s1" % col_letter(ci), h, 1, max_cell_chars) for ci, h in enumerate(header)))
    for ri, row in enumerate(rows, start=2):
        cells = "".join(_cell("%s%d" % (col_letter(ci), ri), v, 0, max_cell_chars)
                        for ci, v in enumerate(row))
        out.append('<row r="%d">%s</row>' % (ri, cells))
    out.append("</sheetData>")
    out.append('<autoFilter ref="A1:%s%d"/>' % (last_col, max(len(rows) + 1, 1)))
    out.append("</worksheet>")
    sheet_xml = "".join(out)

    files = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="%s" sheetId="1" r:id="rId1"/></sheets></workbook>'
            % escape(sheet_title(sheet_name), {'"': "&quot;"}),
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>',
        "xl/styles.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            '</styleSheet>',
        "xl/worksheets/sheet1.xml": sheet_xml,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content.encode("utf-8"))
