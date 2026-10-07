"""Pruebas de plantillas, esquema de campos y cargador de plugins."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chaskiflow import schema, templating  # noqa: E402
from chaskiflow.plugin_loader import PluginRegistry, compute_hash, load_plugin  # noqa: E402
from tests.helpers import FIXTURES, FIXTURES_DUP, PLUGINS  # noqa: E402

T = templating


class TemplatingTests(unittest.TestCase):
    scope = {"A": {"result": {"rows": [{"t": "uno"}, {"t": "dos"}], "n": 2, "ok": True,
                              "nada": None}},
             "vars": {"carpeta": "C:/x"}}

    def test_native_type_when_only_expression(self):
        self.assertEqual(T.resolve("{{A.result.rows}}", self.scope), self.scope["A"]["result"]["rows"])
        self.assertEqual(T.resolve("  {{ A.result.n }}  ", self.scope), 2)
        self.assertIs(T.resolve("{{A.result.ok}}", self.scope), True)

    def test_interpolation_as_text(self):
        self.assertEqual(T.resolve("Total: {{A.result.n}} notas", self.scope), "Total: 2 notas")
        self.assertEqual(T.resolve("{{A.result.n}} y {{vars.carpeta}}", self.scope), "2 y C:/x")
        self.assertEqual(T.resolve("ok={{A.result.ok}} nada=[{{A.result.nada}}]", self.scope),
                         "ok=true nada=[]")
        self.assertIn('"t": "uno"', T.resolve("x {{A.result.rows}}", self.scope))

    def test_paths_and_indexes(self):
        self.assertEqual(T.resolve("{{A.result.rows[1].t}}", self.scope), "dos")
        self.assertEqual(T.resolve("{{A.result.rows.0.t}}", self.scope), "uno")
        self.assertEqual(T.resolve("{{A.result.rows[-1].t}}", self.scope), "dos")

    def test_nested_structures(self):
        out = T.resolve({"a": ["{{A.result.n}}", {"b": "{{vars.carpeta}}"}], "c": 5}, self.scope)
        self.assertEqual(out, {"a": [2, {"b": "C:/x"}], "c": 5})

    def test_plain_text_untouched(self):
        self.assertEqual(T.resolve("sin plantillas", self.scope), "sin plantillas")
        self.assertEqual(T.resolve(5, self.scope), 5)

    def test_errors_are_clear(self):
        with self.assertRaises(T.TemplateError) as c:
            T.resolve("{{A.result.nope}}", self.scope)
        self.assertIn("no existe 'nope'", str(c.exception))
        self.assertIn("rows", str(c.exception))  # lista las claves disponibles
        with self.assertRaises(T.TemplateError):
            T.resolve("{{A.result.rows[9]}}", self.scope)
        with self.assertRaises(T.TemplateError):
            T.resolve("{{Z.result}}", self.scope)
        with self.assertRaises(T.TemplateError):
            T.resolve("{{A.result.n.x}}", self.scope)
        with self.assertRaises(T.TemplateError):
            T.resolve("{{}}", self.scope)

    def test_default_filter(self):
        self.assertEqual(T.resolve('{{Z.result.x | default:"n/a"}}', self.scope), "n/a")
        self.assertEqual(T.resolve("{{A.result.nada | default:[]}}", self.scope), [])
        self.assertEqual(T.resolve("{{A.result.n | default:9}}", self.scope), 2)
        with self.assertRaises(T.TemplateError):
            T.resolve("{{A.result.n | mayusculas}}", self.scope)

    def test_find_refs(self):
        refs = T.find_refs({"a": "{{RPP.result.rows}} y {{vars.x}}", "b": ["{{ Gestion.result.n | default:1 }}"],
                            "c": "sin nada"})
        self.assertEqual(refs, {"RPP", "vars", "Gestion"})


class SchemaTests(unittest.TestCase):
    F = [
        {"key": "url", "type": "string", "required": True},
        {"key": "n", "type": "number", "default": 3, "min": 1, "max": 10},
        {"key": "flag", "type": "boolean", "default": False},
        {"key": "modo", "type": "select", "options": ["a", "b"], "default": "a"},
        {"key": "datos", "type": "json"},
        {"key": "libre", "type": "any"},
    ]

    def test_defaults_and_all_keys_present(self):
        c, e, w = schema.apply_config(self.F, {"url": "http://x"})
        self.assertEqual(e, [])
        self.assertEqual(c["n"], 3)
        self.assertIs(c["flag"], False)
        self.assertEqual(c["modo"], "a")
        self.assertIsNone(c["datos"])
        self.assertIn("libre", c)

    def test_coercion(self):
        c, e, _ = schema.apply_config(self.F, {"url": "u", "n": "7", "flag": "sí",
                                               "datos": '{"a": [1]}', "modo": "b"})
        self.assertEqual((c["n"], c["flag"], c["datos"], c["modo"]), (7, True, {"a": [1]}, "b"))
        c, e, _ = schema.apply_config(self.F, {"url": "u", "n": "2,5"})
        self.assertEqual(c["n"], 2.5)

    def test_errors(self):
        _, e, _ = schema.apply_config(self.F, {})
        self.assertTrue(any("url" in m for m in e))
        _, e, _ = schema.apply_config(self.F, {"url": "u", "n": 99})
        self.assertTrue(any("≤" in m for m in e))
        _, e, _ = schema.apply_config(self.F, {"url": "u", "n": "abc"})
        self.assertTrue(any("número" in m for m in e))
        _, e, _ = schema.apply_config(self.F, {"url": "u", "modo": "z"})
        self.assertTrue(any("no permitido" in m for m in e))
        _, e, _ = schema.apply_config(self.F, {"url": "u", "datos": "{mal"})
        self.assertTrue(any("JSON" in m for m in e))
        _, e, _ = schema.apply_config(self.F, {"url": "u", "flag": "quizás"})
        self.assertTrue(any("verdadero" in m for m in e))

    def test_unknown_key_warning(self):
        _, e, w = schema.apply_config(self.F, {"url": "u", "extra": 1})
        self.assertEqual(e, [])
        self.assertTrue(any("extra" in m for m in w))

    def test_skip_templates(self):
        c, e, _ = schema.apply_config(self.F, {"url": "{{A.result.u}}", "n": "{{A.result.n}}"},
                                      skip_templates=True)
        self.assertEqual(e, [])
        self.assertEqual(c["n"], "{{A.result.n}}")

    def test_validate_fields(self):
        self.assertEqual(schema.validate_fields(self.F), [])
        self.assertTrue(schema.validate_fields([{"key": "x", "type": "raro"}]))
        self.assertTrue(schema.validate_fields([{"key": "x"}, {"key": "x"}]))
        self.assertTrue(schema.validate_fields([{"key": "x", "type": "select"}]))
        self.assertTrue(schema.validate_fields([{"key": "no valida"}]))


class LoaderTests(unittest.TestCase):
    def test_valid_and_problem_plugins_are_separated(self):
        reg = PluginRegistry([FIXTURES])
        for pid in ("ok_echo", "slow", "http_decl", "sum_inputs"):
            self.assertIsNotNone(reg.get(pid), pid)
        bad = {p.path.name: p for p in reg.problems}
        self.assertIn("roto", bad)
        self.assertIn("sin_manifiesto", bad)
        self.assertIn("needs_dep", bad)
        self.assertIn("modulo_que_no_existe_xyz", " ".join(bad["needs_dep"].errors))
        self.assertTrue(any("id" in m for m in bad["roto"].errors))
        self.assertNotIn("_ignorada", bad)  # carpetas con _ se ignoran
        self.assertIsNone(reg.get("roto"))

    def test_bundled_plugins_are_valid(self):
        reg = PluginRegistry([PLUGINS])
        self.assertEqual(reg.problems, [])
        self.assertEqual(sorted(reg.plugins), ["export_csv", "export_xlsx", "hello_world",
                                               "http_request", "llm_structure_addresses", "news_consolidate",
                                               "news_feed_scrape", "outlook_send", "site_locations_crawl",
                                               "url_list_read"])

    def test_duplicate_ids(self):
        reg = PluginRegistry([FIXTURES, FIXTURES_DUP])
        dups = [p for p in reg.problems if any("duplicado" in m for m in p.errors)]
        self.assertEqual(len(dups), 1)
        self.assertIsNotNone(reg.get("ok_echo"))  # el primero se conserva

    def test_catalog_has_everything_the_ui_needs(self):
        reg = PluginRegistry([PLUGINS, FIXTURES])
        cat = {e["id"]: e for e in reg.catalog()}
        e = cat["export_csv"]
        for k in ("name", "version", "icon", "fields", "outputs", "hash", "ok", "kind"):
            self.assertIn(k, e)
        self.assertTrue(any(f["key"] == "data" for f in e["fields"]))
        self.assertFalse(cat["needs_dep"]["ok"])

    def test_hash_changes_when_code_changes(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(FIXTURES / "ok_echo", tmp / "ok_echo")
            h1 = compute_hash(tmp / "ok_echo")
            self.assertEqual(h1, compute_hash(tmp / "ok_echo"))
            (tmp / "ok_echo" / "task.py").write_text("def run(c, x): return {'hack': 1}\n")
            self.assertNotEqual(h1, compute_hash(tmp / "ok_echo"))
            self.assertNotEqual(h1, load_plugin(tmp / "ok_echo").hash)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_reload_picks_up_new_plugins(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            reg = PluginRegistry([tmp])
            self.assertEqual(reg.plugins, {})
            shutil.copytree(FIXTURES / "ok_echo", tmp / "nuevo")
            reg.reload()
            self.assertIsNotNone(reg.get("ok_echo"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_manifest_with_bad_json_does_not_crash(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "p").mkdir()
            (tmp / "p" / "plugin.json").write_text("{esto no es json", encoding="utf-8")
            reg = PluginRegistry([tmp])
            self.assertEqual(len(reg.problems), 1)
            self.assertIn("ilegible", reg.problems[0].errors[0])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_entry_path_traversal_rejected(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "p").mkdir()
            json.dump({"id": "malo", "name": "m", "version": "1.0.0", "entry": "../x.py"},
                      open(tmp / "p" / "plugin.json", "w"))
            reg = PluginRegistry([tmp])
            self.assertTrue(any("entry" in m for m in reg.problems[0].errors))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
