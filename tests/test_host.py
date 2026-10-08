"""Por defecto el servidor solo escucha en este equipo; --share lo abre a la red."""
import json, os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from chaskiflow.config import load_config


class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ.pop("CHASKIFLOW_HOST", None)

    def test_default_is_local(self):
        self.assertEqual(load_config(self.tmp, create=False)["host"], "127.0.0.1")

    def test_new_config_does_not_write_host(self):
        load_config(self.tmp)
        self.assertNotIn("host", json.loads((self.tmp / "config.json").read_text(encoding="utf-8")))

    def test_old_config_with_open_host_is_ignored(self):
        (self.tmp / "config.json").write_text('{"host": "0.0.0.0", "port": 8123}', encoding="utf-8")
        cfg = load_config(self.tmp)
        self.assertEqual(cfg["host"], "127.0.0.1")
        self.assertEqual(cfg["port"], 8123)

    def test_share_flag(self):
        import servidor
        self.assertTrue(servidor.parse_args(["--share"]).share)
        self.assertFalse(servidor.parse_args([]).share)
        self.assertEqual(servidor.parse_args(["--port", "9000"]).port, 9000)


if __name__ == "__main__":
    unittest.main()
