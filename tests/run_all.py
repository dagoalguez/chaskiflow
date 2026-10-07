#!/usr/bin/env python3
"""Ejecuta toda la batería de pruebas.   python tests/run_all.py   (o con -v para detalle)"""

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    verbose = "-v" in sys.argv
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py",
                                                top_level_dir=str(ROOT))
    t = time.monotonic()
    res = unittest.TextTestRunner(verbosity=2 if verbose else 1).run(suite)
    ok = res.testsRun - len(res.failures) - len(res.errors) - len(res.skipped)
    print("\n%d/%d pruebas OK (%d omitidas) en %.1f s" % (ok, res.testsRun - len(res.skipped),
                                                         len(res.skipped), time.monotonic() - t))
    return 0 if res.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
