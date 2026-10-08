#!/usr/bin/env python3
"""Arranca ChaskiFlow:   python servidor.py   (solo librería estándar)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from chaskiflow import __version__  # noqa: E402
from chaskiflow.config import SHARE_HOST, load_config  # noqa: E402
from chaskiflow.server import create_server, lan_addresses  # noqa: E402


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="python servidor.py", description="ChaskiFlow — servidor de workflows.")
    ap.add_argument("--share", action="store_true",
                    help="comparte el servidor con la red local (escucha en 0.0.0.0). Sin esto solo se entra desde este equipo.")
    ap.add_argument("--port", type=int, help="puerto (por defecto el de config.json, 8000)")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    cfg = load_config(ROOT)
    if args.share:
        cfg["host"] = SHARE_HOST
    if args.port:
        cfg["port"] = args.port
    try:
        httpd, app = create_server(cfg)
    except OSError as e:
        print("No se pudo abrir el puerto %s: %s" % (cfg["port"], e))
        print("Cambie 'port' en config.json o cierre el programa que lo usa.")
        return 1
    print("ChaskiFlow %s" % __version__)
    print("Datos:     %s" % app.data_dir)
    print("Plugins:   %d válidos, %d con problemas" % (len(app.registry.plugins),
                                                     len(app.registry.problems)))
    if app.db.backup_path:
        print("Copia de seguridad previa a la migración: %s" % app.db.backup_path)
    if app.seeded:
        print("Primera ejecución: %d plugins aprobados automáticamente." % app.seeded)
    port = cfg["port"]
    print("\nAbra en este equipo:   http://127.0.0.1:%s" % port)
    if cfg["host"] in ("0.0.0.0", ""):
        for ip in lan_addresses():
            print("Desde la red local:    http://%s:%s" % (ip, port))
        print("(Si otros equipos no pueden entrar, permita el puerto %s en el Firewall de Windows.)" % port)
        print("\nCOMPARTIDO con la red local, sin cifrado (HTTP): úselo solo en una red de confianza. Ctrl+C para detener.\n")
    else:
        print("Solo accesible desde este equipo. Para compartirlo con la red local:  python servidor.py --share")
        print("\nCtrl+C para detener.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo…")
    finally:
        app.stop()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
