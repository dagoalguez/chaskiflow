"""Validador de plugins (tools/validar_plugin.py) y plantilla."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import validar_plugin as vp  # noqa: E402


class Validator(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p = self.tmp / "mi_plugin"
        shutil.copytree(ROOT / "plugins" / "_plantilla", self.p)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_template_is_valid_and_runs(self):
        errors, warns = vp.check(self.p, probar=True)
        self.assertEqual((errors, warns), ([], []))

    def test_template_not_listed_as_plugin(self):
        from chaskiflow.plugin_loader import PluginRegistry
        self.assertNotIn("mi_plugin", PluginRegistry([ROOT / "plugins"]).plugins)

    def test_bundled_plugins_pass(self):
        for d in sorted((ROOT / "plugins").iterdir()):
            if d.is_dir() and not d.name.startswith("_"):
                errors, _ = vp.check(d)
                self.assertEqual(errors, [], d.name)

    def test_syntax_error(self):
        (self.p / "task.py").write_text("def run(config, ctx:\n", encoding="utf-8")
        self.assertTrue(any("no compila" in e for e in vp.check(self.p)[0]))

    def test_missing_run(self):
        (self.p / "task.py").write_text("x = 1\n", encoding="utf-8")
        self.assertTrue(any("run(config, ctx)" in e for e in vp.check(self.p)[0]))

    def test_third_party_import(self):
        (self.p / "task.py").write_text("import requests\ndef run(config, ctx):\n    return {}\n",
                                        encoding="utf-8")
        if vp.stdlib_names() is not None:
            self.assertTrue(any("requests" in e for e in vp.check(self.p)[0]))

    def test_binary_file_rejected(self):
        (self.p / "x.exe").write_bytes(b"MZ\x00")
        self.assertTrue(any("solo texto" in e for e in vp.check(self.p)[0]))

    def test_bad_manifest(self):
        (self.p / "plugin.json").write_text('{"id": "Mal Id"}', encoding="utf-8")
        self.assertTrue(vp.check(self.p)[0])

    def test_failing_plugin_detected(self):
        (self.p / "task.py").write_text("def run(config, ctx):\n    raise RuntimeError('boom')\n",
                                        encoding="utf-8")
        self.assertTrue(any("boom" in e for e in vp.check(self.p, probar=True)[0]))

    def test_not_a_folder(self):
        self.assertTrue(vp.check(self.tmp / "nada")[0])


if __name__ == "__main__":
    unittest.main()
