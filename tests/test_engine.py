"""Pruebas del motor: validación, ejecución, errores, timeout, cancelación, secretos."""

import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chaskiflow.engine import Engine, WorkflowError  # noqa: E402
from chaskiflow.plugin_loader import PluginRegistry  # noqa: E402
from tests.helpers import FIXTURES, PLUGINS, LocalServer  # noqa: E402

SECRETS = {"api_token": "tok-SECRET-123", "tok": "abc-9999"}


def node(nid, typ, config=None, **kw):
    d = {"id": nid, "label": nid, "type": typ, "config": config or {}}
    d.update(kw)
    return d


def wf(nodes, edges=(), **kw):
    d = {"name": "t", "nodes": nodes, "edges": [{"source": a, "target": b} for a, b in edges]}
    d.update(kw)
    return d


class EngineBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.registry = PluginRegistry([PLUGINS, FIXTURES])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def engine(self, **kw):
        kw.setdefault("workdir_root", self.tmp / "runs")
        kw.setdefault("secrets", SECRETS.get)
        return Engine(self.registry, **kw)


class ValidationTests(EngineBase):
    def errs(self, w):
        return self.engine().validate(w)[0]

    def test_valid_workflow(self):
        w = wf([node("A", "ok_echo", {"value": 1}), node("B", "ok_echo", {"value": "{{A.result.echo}}"})],
               [("A", "B")])
        self.assertEqual(self.errs(w), [])

    def test_empty(self):
        self.assertTrue(self.errs(wf([])))

    def test_cycle(self):
        w = wf([node("A", "ok_echo"), node("B", "ok_echo")], [("A", "B"), ("B", "A")])
        self.assertTrue(any("ciclo" in e for e in self.errs(w)))

    def test_unknown_task_type(self):
        w = wf([node("A", "no_existe")])
        self.assertTrue(any("no está instalada" in e for e in self.errs(w)))

    def test_invalid_plugin_cannot_be_used(self):
        self.assertTrue(any("no está instalada" in e for e in self.errs(wf([node("A", "needs_dep")]))))

    def test_reference_to_unconnected_node(self):
        w = wf([node("A", "ok_echo", {"value": 1}), node("B", "ok_echo", {"value": "{{A.result.echo}}"})])
        e = self.errs(w)
        self.assertTrue(any("no está conectado antes" in m for m in e), e)

    def test_reference_to_downstream_node(self):
        w = wf([node("A", "ok_echo", {"value": "{{B.result.echo}}"}), node("B", "ok_echo")], [("A", "B")])
        self.assertTrue(any("no está conectado antes" in m for m in self.errs(w)))

    def test_reference_to_nothing(self):
        w = wf([node("A", "ok_echo", {"value": "{{Fantasma.result.x}}"})])
        self.assertTrue(any("no existe ningún nodo" in m for m in self.errs(w)))

    def test_duplicate_label_and_bad_label(self):
        w = wf([node("A", "ok_echo", label="X"), node("B", "ok_echo", label="X")])
        self.assertTrue(any("repetida" in m for m in self.errs(w)))
        w = wf([dict(node("A", "ok_echo"), label="con espacio")])
        self.assertTrue(any("no es válida" in m for m in self.errs(w)))

    def test_static_config_errors(self):
        w = wf([node("A", "req_field", {"n": 99})])
        e = self.errs(w)
        self.assertTrue(any("url" in m for m in e))
        self.assertTrue(any("≤" in m for m in e))

    def test_bad_edges(self):
        self.assertTrue(self.errs(wf([node("A", "ok_echo")], [("A", "Z")])))
        self.assertTrue(self.errs(wf([node("A", "ok_echo")], [("A", "A")])))

    def test_run_refuses_invalid_workflow(self):
        with self.assertRaises(WorkflowError):
            self.engine().run(wf([node("A", "no_existe")]))


class ExecutionTests(EngineBase):
    def test_native_value_flows_between_nodes(self):
        w = wf([node("A", "ok_echo", {"value": [1, 2, {"k": "ñ"}]}),
                node("B", "ok_echo", {"value": "{{A.result.echo}}"}),
                node("C", "ok_echo", {"value": "n={{A.result.echo[0]}}"})],
               [("A", "B"), ("A", "C")])
        r = self.engine().run(w)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.nodes["B"]["result"]["echo"], [1, 2, {"k": "ñ"}])
        self.assertEqual(r.nodes["C"]["result"]["echo"], "n=1")

    def test_every_task_runs_in_its_own_process(self):
        import os
        w = wf([node("A", "ok_echo"), node("B", "ok_echo")], [("A", "B")])
        r = self.engine().run(w)
        pids = {r.nodes["A"]["result"]["pid"], r.nodes["B"]["result"]["pid"], os.getpid()}
        self.assertEqual(len(pids), 3)

    def test_parallel_branches(self):
        w = wf([node("A", "slow", {"seconds": 1.2}), node("B", "slow", {"seconds": 1.2})])
        t = time.monotonic()
        r = self.engine(max_parallel=2).run(w)
        par = time.monotonic() - t
        self.assertEqual(r.status, "ok")
        self.assertLess(par, 2.2)
        t = time.monotonic()
        self.engine(max_parallel=1).run(w)
        self.assertGreaterEqual(time.monotonic() - t, 2.4)

    def test_error_with_stop_skips_downstream(self):
        w = wf([node("A", "fail"), node("B", "ok_echo")], [("A", "B")])
        r = self.engine().run(w)
        self.assertEqual(r.status, "error")
        self.assertEqual(r.nodes["A"]["status"], "error")
        self.assertIn("falló a propósito", r.nodes["A"]["error"])
        self.assertEqual(r.nodes["B"]["status"], "skipped")

    def test_error_with_continue_keeps_going(self):
        w = wf([node("A", "fail", on_error="continue"), node("OK", "ok_echo", {"value": 5}),
                node("C", "sum_inputs")], [("A", "C"), ("OK", "C")])
        w["nodes"][2]["config"] = {}
        r = self.engine().run(w)
        self.assertEqual(r.status, "partial")
        self.assertEqual(r.nodes["C"]["status"], "ok")
        self.assertEqual(r.nodes["C"]["result"]["names"], ["OK"])  # solo entradas correctas

    def test_reference_to_failed_node_and_default(self):
        w = wf([node("A", "fail", on_error="continue"),
                node("B", "ok_echo", {"value": "{{A.result.x}}"}),
                node("C", "ok_echo", {"value": '{{A.result.x | default:"sin dato"}}'})],
               [("A", "B"), ("A", "C")])
        r = self.engine().run(w)
        self.assertEqual(r.nodes["B"]["status"], "error")
        self.assertIn("Plantilla", r.nodes["B"]["error"])
        self.assertEqual(r.nodes["C"]["result"]["echo"], "sin dato")

    def test_timeout_kills_the_task(self):
        w = wf([node("A", "slow_timeout", {"seconds": 30})])
        t = time.monotonic()
        r = self.engine().run(w)
        self.assertLess(time.monotonic() - t, 6)
        self.assertEqual(r.nodes["A"]["status"], "error")
        self.assertIn("Tiempo excedido", r.nodes["A"]["error"])
        self.assertEqual(r.nodes["A"]["reason"], "timeout")

    def test_cancel(self):
        cancel = threading.Event()
        threading.Timer(0.8, cancel.set).start()
        w = wf([node("A", "slow", {"seconds": 20}), node("B", "ok_echo")], [("A", "B")])
        t = time.monotonic()
        r = self.engine().run(w, cancel=cancel)
        self.assertLess(time.monotonic() - t, 6)
        self.assertEqual(r.status, "cancelled")
        self.assertEqual(r.nodes["A"]["status"], "cancelled")
        self.assertEqual(r.nodes["B"]["status"], "cancelled")

    def test_crashing_process_is_reported(self):
        r = self.engine().run(wf([node("A", "crash")]))
        self.assertEqual(r.nodes["A"]["status"], "error")
        self.assertIn("código 3", r.nodes["A"]["error"])
        self.assertIn("a punto de morir", r.nodes["A"]["error"])

    def test_unexpected_exception_includes_type(self):
        r = self.engine().run(wf([node("A", "fail_keyerror")]))
        self.assertTrue(r.nodes["A"]["error"].startswith("KeyError"))
        self.assertIn("traceback", r.nodes["A"])

    def test_print_noise_does_not_break_protocol(self):
        events = []
        r = self.engine().run(wf([node("A", "noisy")]), on_event=events.append)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.nodes["A"]["result"], {"ok": 1})
        msgs = [e.get("message") for e in events if e["type"] == "log"]
        self.assertIn("hola desde el plugin", msgs)
        self.assertTrue(any(str(m).startswith("basura") for m in msgs))
        self.assertTrue(any(e["type"] == "progress" and e["done"] == 1 for e in events))

    def test_big_result_passes_through(self):
        w = wf([node("A", "big"), node("B", "ok_echo", {"value": "{{A.result.blob}}"})], [("A", "B")])
        r = self.engine().run(w)
        self.assertEqual(r.status, "ok")
        self.assertEqual(len(r.nodes["B"]["result"]["echo"]), 5000000)

    def test_inputs_for_plugins_that_ask(self):
        w = wf([node("H1", "hello_world", {"filas": 2}), node("H2", "hello_world", {"filas": 3}),
                node("S", "sum_inputs")], [("H1", "S"), ("H2", "S")])
        r = self.engine().run(w)
        self.assertEqual(r.nodes["S"]["result"], {"total": 5, "names": ["H1", "H2"]})

    def test_disabled_node_is_skipped_with_downstream(self):
        w = wf([node("A", "ok_echo", enabled=False), node("B", "ok_echo")], [("A", "B")])
        r = self.engine().run(w)
        self.assertEqual(r.nodes["A"]["status"], "skipped")
        self.assertEqual(r.nodes["B"]["status"], "skipped")

    def test_runtime_config_validation_after_templates(self):
        w = wf([node("A", "ok_echo", {"value": 9}),
                node("B", "req_field", {"url": "u", "n": "{{A.result.echo}}"})], [("A", "B")])
        r = self.engine().run(w)
        self.assertEqual(r.nodes["B"]["status"], "error")
        self.assertIn("Configuración inválida", r.nodes["B"]["error"])

    def test_workflow_variables_and_override(self):
        w = wf([node("A", "ok_echo", {"value": "{{vars.x}}"})], variables={"x": "base"})
        self.assertEqual(self.engine().run(w).nodes["A"]["result"]["echo"], "base")
        r = self.engine().run(w, variables={"x": "otro"})
        self.assertEqual(r.nodes["A"]["result"]["echo"], "otro")

    def test_events_are_ordered(self):
        events = []
        w = wf([node("A", "ok_echo"), node("B", "ok_echo")], [("A", "B")])
        self.engine().run(w, on_event=events.append)
        types = [e["type"] for e in events]
        self.assertEqual(types[0], "run_start")
        self.assertEqual(types[-1], "run_end")
        order = [(e["type"], e["label"]) for e in events if e["type"].startswith("node_")]
        self.assertEqual(order, [("node_start", "A"), ("node_end", "A"),
                                 ("node_start", "B"), ("node_end", "B")])

    def test_rerun_single_node_with_seed(self):
        w = wf([node("A", "ok_echo", {"value": 7}),
                node("B", "ok_echo", {"value": "{{A.result.echo}}"})], [("A", "B")])
        first = self.engine().run(w)
        seed = {"A": first.nodes["A"]}
        second = self.engine().run(w, only={"B"}, seed=seed)
        self.assertEqual(second.nodes["B"]["result"]["echo"], 7)
        self.assertEqual(second.nodes["A"]["result"]["pid"], first.nodes["A"]["result"]["pid"])
        self.assertNotEqual(second.nodes["B"]["result"]["pid"], first.nodes["B"]["result"]["pid"])

    def test_to_dict_summarizes_big_results(self):
        r = self.engine().run(wf([node("A", "big")]))
        d = r.to_dict(full=False)
        self.assertLess(len(str(d)), 2000)
        self.assertEqual(len(r.nodes["A"]["result"]["blob"]), 5000000)


class SecretsTests(EngineBase):
    def test_declared_secret_is_available_and_masked(self):
        events = []
        r = self.engine().run(wf([node("A", "secret_reader")]), on_event=events.append)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.nodes["A"]["result"], {"len": 14, "denied": True})
        logs = " ".join(str(e.get("message")) for e in events if e["type"] == "log")
        self.assertNotIn("tok-SECRET-123", logs)
        self.assertIn("***", logs)
        for entry in r.nodes["A"]["logs"]:
            self.assertNotIn("tok-SECRET-123", entry["message"])

    def test_secret_in_error_is_masked(self):
        r = self.engine().run(wf([node("A", "leaky")]))
        self.assertEqual(r.nodes["A"]["status"], "error")
        self.assertNotIn("tok-SECRET-123", r.nodes["A"]["error"])
        self.assertNotIn("tok-SECRET-123", r.nodes["A"].get("traceback", ""))
        self.assertIn("***", r.nodes["A"]["error"])

    def test_missing_secret_gives_clear_error(self):
        r = self.engine(secrets=lambda n: None).run(wf([node("A", "secret_reader")]))
        self.assertIn("Falta la clave 'api_token'", r.nodes["A"]["error"])

    def test_secret_not_in_recorded_config(self):
        r = self.engine().run(wf([node("A", "secret_reader")]))
        self.assertNotIn("tok-SECRET-123", str(r.to_dict()))


class DeclarativePluginTests(EngineBase):
    def test_declarative_http_plugin_with_secret(self):
        with LocalServer() as srv:
            r = self.engine().run(wf([node("A", "http_decl", {"base": srv.base, "name": "Ana"})]))
        res = r.nodes["A"]["result"]
        self.assertEqual(r.status, "ok", r.nodes["A"]["error"])
        self.assertEqual(res["echoed"], "Ana")
        self.assertEqual(res["auth"], "Bearer abc-9999")
        self.assertIsNone(res["nada"])  # ruta inexistente en response_map -> None
        self.assertEqual(res["status"], 200)

    def test_declarative_missing_secret_is_clear(self):
        with LocalServer() as srv:
            r = self.engine(secrets=lambda n: None).run(
                wf([node("A", "http_decl", {"base": srv.base})]))
        self.assertEqual(r.nodes["A"]["status"], "error")
        self.assertIn("clave", r.nodes["A"]["error"])


if __name__ == "__main__":
    unittest.main()
