"""Exportación con el archivo de destino abierto/bloqueado (WinError 5 en Windows): se reintenta y se guarda con otro nombre."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


class Ctx:
    def __init__(self):
        self.lines = []

    def log(self, m):
        self.lines.append(m)


def load(name):
    d = ROOT / "plugins" / name
    sys.path.insert(0, str(d))
    try:
        spec = importlib.util.spec_from_file_location("task_" + name, d / "task.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(d))
    return mod


class Locked(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def run_plugin(self, name, lock_target):
        mod = load(name)
        real = Path.replace

        def fake(self_, target):
            if Path(target).name == lock_target:
                raise PermissionError(5, "Acceso denegado")
            return real(self_, target)
        ctx = Ctx()
        cfg = {"data": [{"a": 1}], "output_dir": str(self.tmp), "filename": "n"}
        with mock.patch.object(Path, "replace", fake), mock.patch("time.sleep"):
            return mod.run(cfg, ctx), ctx

    def test_csv_locked_saves_with_other_name(self):
        res, ctx = self.run_plugin("export_csv", "n.csv")
        self.assertEqual(res["filename"], "n_1.csv")
        self.assertTrue(Path(res["file_path"]).is_file())
        self.assertTrue(any("AVISO" in l for l in ctx.lines))
        self.assertEqual([p.name for p in self.tmp.glob("*.tmp")], [])

    def test_xlsx_locked_saves_with_other_name(self):
        res, ctx = self.run_plugin("export_xlsx", "n.xlsx")
        self.assertEqual(res["filename"], "n_1.xlsx")
        self.assertTrue(Path(res["file_path"]).is_file())

    def test_everything_locked_gives_clear_error(self):
        mod = load("export_csv")

        def fake(self_, target):
            raise PermissionError(5, "Acceso denegado")
        with mock.patch.object(Path, "replace", fake), mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError) as cm:
                mod.run({"data": [{"a": 1}], "output_dir": str(self.tmp), "filename": "n"}, Ctx())
        self.assertIn("Cierre el archivo", str(cm.exception))
        self.assertEqual([p.name for p in self.tmp.glob("*.tmp")], [])

    def test_normal_case_unchanged(self):
        mod = load("export_csv")
        res = mod.run({"data": [{"a": 1}], "output_dir": str(self.tmp), "filename": "n"}, Ctx())
        self.assertEqual(res["filename"], "n.csv")


if __name__ == "__main__":
    unittest.main()
