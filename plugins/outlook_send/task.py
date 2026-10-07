"""Outlook: enviar correo vía PowerShell + COM (solo Windows, solo librería estándar)."""

import html
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime

PS_SCRIPT = r"""
param([string]$JsonPath)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$d = Get-Content -LiteralPath $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
try { $ol = New-Object -ComObject Outlook.Application }
catch { Write-Error 'No se pudo abrir Outlook (COM). Verifique que Outlook de escritorio este instalado y abierto con su cuenta.'; exit 2 }
$m = $ol.CreateItem(0)
$m.To = [string]$d.to
if ($d.cc) { $m.CC = [string]$d.cc }
if ($d.bcc) { $m.BCC = [string]$d.bcc }
$m.Subject = [string]$d.subject
$m.HTMLBody = [string]$d.html
foreach ($a in @($d.attachments)) { if ($a) { [void]$m.Attachments.Add([string]$a) } }
switch ($d.mode) {
  'send'    { $m.Send();    Write-Output 'ENVIADO' }
  'display' { $m.Display(); Write-Output 'ABIERTO' }
  'draft'   { $m.Save();    Write-Output 'BORRADOR' }
}
"""

MAIL = re.compile(r"^[^@\s;]+@[^@\s;]+\.[^@\s;]+$")


def _addresses(text):
    return [a.strip() for a in re.split(r"[;,]", text or "") if a.strip()]


def _to_html(body, already_html):
    if already_html:
        return body
    esc = html.escape(body).replace("\r\n", "\n").replace("\n", "<br>\n")
    return ('<div style="font-family:Segoe UI,Calibri,Arial,sans-serif;font-size:14px">%s</div>' % esc)


def _attachments(value):
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        value = [p for p in re.split(r"[;\n]", value)]
    out = []
    for v in value:
        if isinstance(v, (list, tuple)):      # listas anidadas (varios pasos de exportación)
            out.extend(_attachments(list(v)))
            continue
        if isinstance(v, dict):
            v = v.get("file_path") or v.get("path")
        if v and str(v).strip():
            out.append(str(v).strip().strip('"'))
    return out


def run(config, ctx):
    to = _addresses(config.get("to"))
    cc = _addresses(config.get("cc"))
    bcc = _addresses(config.get("bcc"))
    bad = [a for a in to + cc + bcc if not MAIL.match(a)]
    if not to:
        raise RuntimeError("Falta el destinatario (Para)")
    if bad:
        raise RuntimeError("Correo(s) inválido(s): %s" % ", ".join(bad))
    subject = datetime.now().strftime(config.get("subject") or "")
    body = config.get("body")
    if body is None or str(body).strip() == "":
        raise RuntimeError("El mensaje está vacío")
    if not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False, indent=2)
    atts = _attachments(config.get("attachments"))
    for a in atts:
        if not os.path.isfile(a):
            raise RuntimeError("No existe el adjunto: %s" % a)
    mode = config.get("mode") or "send"
    payload = {"to": "; ".join(to), "cc": "; ".join(cc), "bcc": "; ".join(bcc), "subject": subject,
               "html": _to_html(body, bool(config.get("body_is_html"))), "attachments": atts, "mode": mode}
    summary = {"sent": False, "mode": mode, "attachments": atts, "subject": subject, "to": payload["to"]}
    if config.get("dry_run"):
        ctx.log("PRUEBA: no se usó Outlook. Para=%s, asunto='%s', %d adjunto(s), acción=%s"
                % (payload["to"], subject, len(atts), mode))
        summary["dry_run"] = True
        return summary
    if sys.platform != "win32":
        raise RuntimeError("Outlook por COM solo funciona en Windows (este servidor corre en %s)" % sys.platform)
    fd, jpath = tempfile.mkstemp(suffix=".json", dir=ctx.workdir)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    spath = jpath.replace(".json", ".ps1")
    with open(spath, "w", encoding="utf-8-sig") as f:   # BOM: PowerShell 5 lee UTF-8 correctamente
        f.write(PS_SCRIPT)
    ctx.log("Outlook: %s -> %s (%d adjunto(s))" % (mode, payload["to"], len(atts)))
    p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", spath,
                        "-JsonPath", jpath], capture_output=True, timeout=120)
    out = p.stdout.decode("utf-8", "replace").strip()
    err = p.stderr.decode("utf-8", "replace").strip()
    if p.returncode != 0:
        raise RuntimeError("Outlook falló (código %d): %s" % (p.returncode, (err or out)[:600]))
    ctx.log("Outlook respondió: %s" % out)
    summary["sent"] = mode == "send"
    return summary
