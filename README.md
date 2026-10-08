<p align="center"><img src="docs/img/logo.svg" alt="ChaskiFlow logo" width="72"></p>

# ChaskiFlow

By **Diego Guevara B.** · Contributions: Claude · License: Apache-2.0

A workflow platform built around **plugins**. You wire tasks together as connected nodes, and anyone who
needs a new kind of task just drops a folder into `plugins/` — no changes to the core.

**Python standard library only.** No pip, no npm, no binaries, no services. The web UI is plain
JavaScript (nothing to compile, no CDN), so it works on locked-down networks where package registries and
binary downloads are blocked.

> Status: **v0.15** — multi-user web server, visual node editor, run history, admin-approved plugins,
> keys, hourly scheduling, and bundled example workflows (news digest, branch lookup with a local LLM,
> SMV financial statements). The UI is in Spanish (with an English switch); the docs under `docs/` are
> currently in Spanish. See [`LIMITATIONS.md`](LIMITATIONS.md) for what is not covered.

## Run the web server

```
python servidor.py
```

Open `http://127.0.0.1:8000`. The first time, it asks you to create the administrator account. Data lives
in a single SQLite file, `data/app.db` (backup = copy that file).

**By default the server is only reachable from the same computer.** To share it with your local network
(LAN), start it with:

```
python servidor.py --share
```

It then prints the LAN addresses other computers can use. If they cannot connect, allow the port in your
firewall (e.g. Windows Defender Firewall). Traffic is plain HTTP, so only share it on a network you trust.
`--port 9000` changes the port. Other optional settings live in `config.json` (created automatically):
`port`, `data_dir`, `plugin_dirs`, `max_concurrent_runs`, `scheduler_enabled`, `scheduler_tick_seconds`, etc.

- **Roles**: admin (everything, installs/approves plugins), editor (creates and runs), viewer (read-only).
- **Sharing**: every workflow has an owner; access can be granted per person or to the whole team (view / run / edit).
- **Plugins**: only an admin can enable them; if a plugin's code changes on disk it stays blocked until re-approved.
- **Keys** (formerly "secrets"): personal or global (admin); steps use them as `{{secret.name}}` and they are masked in logs.
- **Editor tab**: node graph, step inspector, and a collapsible live **Log** panel. Right-click the canvas to add a step (with search); right-click a step to add one after it, copy, duplicate or delete.
- **Runs tab**: list of past runs on the left; the selected run's graph (read-only, colored by status) and its step-by-step log on the right. Partial runs ("this step", "up to here", "from here") are supported.
- **Scheduling**: the server itself triggers runs (that PC's clock, the creator's permissions). The PC must be on and not suspended; a run missed while it was off is skipped.
- **Autosave**, trash with undo, a warning when two people edit at once, ES/EN, light/dark, collapsible sidebar.

## Try it from the console (2 minutes)

```
python run_workflow.py --list-plugins
python run_workflow.py examples/hola_reporte.json --var carpeta=./salida
python tests/run_all.py
```

Requires Python 3.8 or later.

## What is inside

| Piece | Description |
|---|---|
| `chaskiflow/engine.py` | Validates the graph (cycles, references, fields), runs it in parallel, handles errors, timeouts and cancellation |
| `chaskiflow/plugin_loader.py` | Discovers plugins, validates manifests, computes their hash |
| `chaskiflow/executor.py`, `runner.py` | Every task runs in a **separate subprocess** (JSON over stdin/stdout) |
| `chaskiflow/templating.py` | `{{Node.result.field}}` references between nodes, with native types |
| `chaskiflow/declarative.py` | Code-free plugins: an HTTP request described in JSON |
| `chaskiflow/server.py`, `api.py` | HTTP server (stdlib) and REST API |
| `chaskiflow/db.py`, `auth.py`, `access.py` | SQLite with automatic migrations, PBKDF2 passwords, permissions |
| `chaskiflow/runs.py`, `plugin_gate.py` | Live runs, plugin approval |
| `web/` | Plain-JavaScript UI (no build step, no CDN) |
| `plugins/` | `http_request`, `export_csv`, `export_xlsx`, `hello_world`, news pack (`news_*`, `outlook_send`), `site_locations_crawl`, `llm_structure_addresses`, `url_list_read`, `smv_financial_download`, `pdf_keyword_scan`, and `_plantilla` (a plugin template) |
| `examples/` | Ready-to-import workflows |
| `docs/PLUGINS.md` | How to write a plugin |
| `docs/CREAR_PLUGINS_CON_IA.md` | Create plugins with an AI assistant (prompt included) |
| `docs/NOTICIAS.md`, `SUCURSALES.md`, `SMV_FUSIONES.md`, `IMPORTAR_G1G.md` | Guides for the bundled examples (in Spanish) |

## Example workflow

```json
{
  "name": "Hola reporte",
  "variables": {"carpeta": "./salida"},
  "nodes": [
    {"id": "n1", "label": "Datos", "type": "hello_world", "config": {"filas": 5}},
    {"id": "n2", "label": "Excel", "type": "export_xlsx",
     "config": {"data": "{{Datos.result.rows}}", "output_dir": "{{vars.carpeta}}"}}
  ],
  "edges": [{"source": "n1", "target": "n2"}]
}
```

## Design constraints

ChaskiFlow was designed for institutional environments where the proxy breaks SSL and blocks binary
downloads, so: the backend is pure Python stdlib (no compiled dependencies, `pypdf` is vendored as pure
Python), the UI ships ready to run, and every release is plain text files. Plugins that need a local LLM
talk to any OpenAI-compatible server (for example quipullm or LM Studio) running on
your own network.

## Roadmap

V1 server, users, SQLite, forms · V2 visual editor + news pack · V3 scheduling and run history ·
V4 polish, plugin template, validator · V5 SMV and branch-lookup examples with a local LLM,
redesigned runs view · next: step-level undo in the graph, loops (foreach), JavaScript-rendered pages.

## License

Apache-2.0 (see `LICENSE` and `NOTICE`).

Author: **Diego Guevara B.** · Contributions: **Claude**.
