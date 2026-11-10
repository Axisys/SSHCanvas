# -*- coding: utf-8 -*-
"""v1.15 — `CLI.md` clause by clause: the headless surface as the regression file of the base release.
§1 naming and entry points; §2 the command line; §3.0 the verb table; §3.1–§3.5 the five verbs of the
base release; §3.6 the `hostkey verify` family; §4 the `--json` envelope; §5.1–§5.3 the three security
policies; §6 the Qt-free rule; §7 what the CLI does NOT do; §8 the configuration it reads; §9 the release
state. Each check quotes the clause it pins — the contract is FROZEN, so this file is the shape a future
change must meet. Rule — `AGENTS.md` §4.35; mechanism — `DOCUMENTATION.md` §80.
Run: python tests/test_cli_contract.py
"""
import ast
import contextlib
import io
import json
import os
import subprocess
import sys
import threading

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least,
                     translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + sys.path (BEFORE any app import)

import paramiko  # noqa: E402

import cli.args as ARGS  # noqa: E402
import cli.credentials as CREDENTIALS  # noqa: E402
import cli.dispatch as DISPATCH  # noqa: E402
import cli.doctor as DOCTOR  # noqa: E402
import cli.envelope as ENV  # noqa: E402
import cli.errors as ERR  # noqa: E402
import cli.exec as EXEC  # noqa: E402
import cli.exit_codes as EX  # noqa: E402
import cli.hostkeys as CLI_HOSTKEYS  # noqa: E402
import cli.project as PROJECT  # noqa: E402
import cli.report as REPORT  # noqa: E402
import cli.status as STATUS  # noqa: E402
import cli.verb_args as VERB_ARGS  # noqa: E402
import models.server as SERVER  # noqa: E402
import modules.command_guard as GUARD  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import services.reachability as REACH  # noqa: E402
import services.status_probe as PROBE  # noqa: E402
import storage.app_config as APP_CONFIG  # noqa: E402
import storage.export_connections as ECON  # noqa: E402
import storage.export_inventory as EINV  # noqa: E402
import storage.project as SHIPPED  # noqa: E402
import storage.table_text as TABLE  # noqa: E402
import version  # noqa: E402
from cli.main import main  # noqa: E402

CLI_DIR = os.path.join(ROOT, "cli")
CLI_MD = os.path.join(ROOT, "CLI.md")
LANGS = load_i18n_langs(ROOT)
CONTRACT = open(CLI_MD, encoding="utf-8").read()


def read(path):
    """The text of one repository file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def cli_sources():
    """`(module name, file name, source)` for every module of `cli/` — the static half of the audit."""
    out = []
    for name in sorted(os.listdir(CLI_DIR)):
        if name.endswith(".py"):
            out.append((name[:-3], name, read(os.path.join(CLI_DIR, name))))
    return out


def run(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout text, stderr text)`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def document(text):
    """The ONE `--json` document of a run (`{}` when the text is not one — a defect the check names)."""
    stripped = str(text or "").strip()
    return json.loads(stripped) if stripped.startswith("{") else {}


def fresh(code, extra_env=None):
    """Run a snippet in a FRESH process rooted at the repository (`PYTHONPATH` + UTF-8 IO)."""
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180, env=env)


def child_bytes(argv, extra_env=None):
    """Run the CLI as a REAL process (`python -m cli`) and answer `(code, stdout, stderr)` BYTES."""
    env = dict(os.environ, PYTHONPATH=ROOT)
    env.pop("PYTHONIOENCODING", None)
    env.update(extra_env or {})
    done = subprocess.run([sys.executable, "-m", "cli", *argv], cwd=ROOT, capture_output=True,
                          timeout=180, env=env)
    return done.returncode, done.stdout or b"", done.stderr or b""


def cost(argv):
    """The `CliError` ONE command line costs (`None` — it parsed cleanly)."""
    try:
        ARGS.parse_argv(list(argv))
    except ERR.CliError as exc:
        return exc
    return None


def forget(verb_name):
    """Drop a row the registry accepted — the bookkeeping side of a `register()` probe."""
    DISPATCH.VERBS.pop(verb_name, None)
    order = getattr(DISPATCH, "_REGISTERED_ORDER", [])
    if verb_name in order:
        order.remove(verb_name)


def raises(exception_type, callable_):
    """Does this call raise `exception_type`?"""
    try:
        callable_()
    except exception_type:
        return True
    return False


def imports_of(path):
    """Every ABSOLUTE module and imported name one source names (`from .` stays inside `cli/`)."""
    names = set()
    for node in ast.walk(ast.parse(read(path))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.update(alias.name for alias in node.names)
    return names


def qt_import_lines(source):
    """The lines that IMPORT PySide6 (a docstring may name the rule; an import breaks it)."""
    return [line for line in str(source or "").splitlines()
            if line.lstrip().startswith(("import PySide6", "from PySide6"))]


#: The canonical source of a refusal's hint — the door a missing secret's sentence names.
DOOR = CREDENTIALS.DOOR


# ════════════════════════════════════════════════════════════════════════════
print("== §1 naming and entry points ==")
# ════════════════════════════════════════════════════════════════════════════

_CHAPTERS = [line for line in CONTRACT.splitlines() if line.startswith("## ")]
check("§1 the contract is FROZEN and carries its EIGHT chapters, in order",
      CONTRACT.startswith("# CLI.md — the headless surface") and "**frozen contract**" in CONTRACT
      and len(_CHAPTERS) == 8
      and _CHAPTERS[0].startswith("## 1. Naming and entry points")
      and _CHAPTERS[-1].startswith("## 8. The configuration it READS"),
      _CHAPTERS[:1] + _CHAPTERS[-1:])
_PYPROJECT = read(os.path.join(ROOT, "pyproject.toml"))
check("§1 the two console scripts are a SECOND entry point over `cli.main:main`",
      'sshcanvas-cli = "cli.main:main"' in _PYPROJECT
      and 'sshmap-cli = "cli.main:main"' in _PYPROJECT,
      [line for line in _PYPROJECT.splitlines() if "-cli" in line])
check("§1 `sshcanvas` / `sshmap` keep their GUI entry point (the CLI is never a subcommand of `main()`)",
      'sshcanvas = "main:main"' in _PYPROJECT and 'sshmap = "main:main"' in _PYPROJECT
      and "--cli" not in read(os.path.join(ROOT, "main.py")))
check("§1 `cli` is a top-level PACKAGE of the explicit distribution list (a wheel carries it)",
      os.path.isfile(os.path.join(CLI_DIR, "__init__.py"))
      and any(line.strip() == '"cli",' for line in _PYPROJECT.splitlines()))
_DONE = fresh("import main, sys\nprint('PySide6' in sys.modules)\n")
check("§1 ...and the reason is MEASURED: `import main` loads PySide6, so `main.py --cli` is refused",
      _DONE.returncode == 0 and _DONE.stdout.strip() == "True",
      f"{(_DONE.stdout or '').strip()!r} / {(_DONE.stderr or '')[-160:]}")
_DONE = fresh("import sys\nfrom cli.main import main\nmain(['--version'])\n"
              "print([m for m in ('cli.inventory', 'cli.connections', 'cli.status', 'cli.doctor',\n"
              "                   'cli.exec') if m in sys.modules], file=sys.stderr)\n")
check("§1 the entry module parses argv FIRST — an option answer loads NO verb module",
      _DONE.returncode == 0 and _DONE.stderr.strip() == "[]",
      f"{(_DONE.stdout or '').strip()!r} / {(_DONE.stderr or '').strip()!r}")
_DONE = subprocess.run([sys.executable, "-m", "cli", "--version"], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=180,
                       env=dict(os.environ, PYTHONPATH=ROOT))
check("§1 `python -m cli` is the uninstalled door: `--version` exits 0 with the release",
      _DONE.returncode == EX.EXIT_OK
      and _DONE.stdout.strip() == f"{version.APP_NAME} {version.APP_VERSION}",
      f"{_DONE.returncode} / {(_DONE.stdout or '').strip()!r}")
check("§1 `cli.main:main()` ANSWERS the exit code as an int (the console script exits with it)",
      isinstance(run(["--version"])[0], int)
      and "def main(argv=None) -> int:" in read(os.path.join(CLI_DIR, "main.py")))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the command line ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the ONE option table is the contract's five rows (the parse and the help read it)",
      {name for name, _takes, _meta in ARGS.OPTIONS}
      == {ARGS.OPTION_JSON, ARGS.OPTION_PROJECT, ARGS.OPTION_TIMEOUT, ARGS.OPTION_HELP,
          ARGS.OPTION_VERSION})
check("§2 `--option=value` and `--option value` are the same thing",
      ARGS.parse_argv(["--timeout=5", "status"]) == ARGS.parse_argv(["--timeout", "5", "status"])
      and ARGS.parse_argv(["--project=a.json", "inventory"]).project
      == ARGS.parse_argv(["--project", "a.json", "inventory"]).project)
check("§2 a repeated option takes its LAST value",
      ARGS.parse_argv(["--timeout", "5", "--timeout", "7"]).timeout == 7.0
      and os.path.basename(ARGS.parse_argv(
          ["--project", "first.json", "--project", "last.json"]).project) == "last.json")
check("§2 `--` ends the options: everything after it belongs to the verb verbatim",
      (lambda inv: (inv.verb, inv.arguments, inv.json))(
          ARGS.parse_argv(["--json", "--", "inventory", "--tag"])) == ("inventory", ("--tag",), True))
check("§2 an undeclared option is a USAGE error (a silently ignored `--jsno` prints a report nobody reads)",
      (lambda exc: exc is not None and exc.code == EX.EXIT_USAGE)(cost(["--jsno"]))
      and cost(["-x"]) is not None)
check("§2 the verb is the FIRST bare token — a later flag belongs to that verb, not to the table",
      (lambda inv: (inv.verb, inv.arguments, inv.json))(
          ARGS.parse_argv(["inventory", "--tag", "prod", "--json"]))
      == ("inventory", ("--tag", "prod", "--json"), False))
check("§2 `--help` writes TEXT even under `--json` (a machine that asks for help asked for a human's)",
      (lambda pair: pair[0] == EX.EXIT_OK and pair[1].startswith("usage: sshcanvas-cli")
       and not pair[1].lstrip().startswith("{"))(run(["--json", "--help"])))
check("§2 `--version` / `-V` name the application's release, exit 0",
      run(["-V"])[0] == EX.EXIT_OK
      and run(["-V"])[1].strip() == f"{version.APP_NAME} {version.APP_VERSION}")
check("§2 `--timeout` declares 1..300 s, default 10, and a value outside is USAGE",
      ARGS.TIMEOUT_DEFAULT_S == 10.0 and ARGS.TIMEOUT_MIN_S == 1.0 and ARGS.TIMEOUT_MAX_S == 300.0
      and cost(["--timeout", "0"]) is not None and cost(["--timeout", "301"]) is not None
      and cost(["--timeout", "soon"]) is not None)
check("§2 `--project` is expanded and made ABSOLUTE at parse time (one spelling in the envelope)",
      os.path.isabs(ARGS.parse_argv(["--project", "rel/map.json"], base_dir=WORK).project)
      and ARGS.parse_argv(["--project", "rel/map.json"], base_dir=WORK).project
      == os.path.normpath(os.path.join(WORK, "rel", "map.json")))


def fixture(name, servers=(), connections=(), drop_connections=False):
    """Write ONE SYNTHETIC project into the isolated work folder (never a real map file)."""
    payload = {"version": version.VERSION_FORMAT, "servers": list(servers),
               "connections": list(connections), "notes": [], "groups": [], "background": None}
    if drop_connections:
        payload.pop("connections")
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


WEB = {"id": "srv-web", "alias": "web-1", "host": "192.0.2.10", "ssh_port": 22, "user": "deploy",
       "comment": 'edge, "quoted"', "os_name": "Ubuntu 24.04 LTS", "ram": "8 GB", "disk": "512 GB",
       "tags": ["prod", "web"]}
DB = {"id": "srv-db", "alias": "db-1", "host": "198.51.100.20", "ssh_port": 2222,
      "user": "postgres", "tags": ["prod"]}
LINK = {"source_id": "srv-web", "target_id": "srv-db", "label": "api", "type": "database",
        "bidirectional": True}
MAP = fixture("contract-map.json", [WEB, DB], [LINK])
NO_LINKS = fixture("contract-no-links.json", [WEB, DB])
NO_ARRAY = fixture("contract-no-array.json", [WEB], drop_connections=True)
EMPTY = fixture("contract-empty.json")
DANGLING = fixture("contract-dangling.json", [WEB],
                   [{"source_id": "srv-web", "target_id": "srv-ghost", "label": "gone"}])
UNMANAGED = fixture("contract-unmanaged.json", [dict(DB, unmanaged=True), WEB])
EXEC_MAP = fixture("contract-exec.json", [WEB])
UNICODE_MAP = fixture("contract-unicode.json",
                      [dict(WEB, alias="東京サーバー", comment="café — naïve")])
BROKEN = os.path.join(WORK, "contract-broken.json")
with open(BROKEN, "w", encoding="utf-8") as _handle:
    _handle.write("{ not json")

APP_CONFIG.save_config({"last_project_path": MAP})
try:
    _CODE, _OUT, _ERR = run(["--json", "inventory"])
    _DEFAULT_PROJECT = (document(_OUT).get("data") or {}).get("project")
finally:
    try:
        os.remove(APP_CONFIG.CONFIG_FILE)
    except OSError:
        pass
check("§2 the default project is the last one the GUI opened (the config key, READ-ONLY)",
      _CODE == EX.EXIT_OK and _DEFAULT_PROJECT == MAP, f"{_CODE} / {_DEFAULT_PROJECT!r}")
_CODE, _OUT, _ERR = run(["--json", "inventory"])
check("§2 ...a verb that needs a file answers 5 when there is none (never an empty report)",
      _CODE == EX.EXIT_NOT_FOUND and document(_OUT).get("ok") is False
      and document(_OUT).get("data") is None
      and document(_OUT).get("error", {}).get("kind") == "not_found", _OUT[:140])

_SEEN_TIMEOUTS = []
_ORIGINAL_PROBE = STATUS.probe_ssh


def _recording_probe(host, port, timeout):
    """A probe that records the budget it was handed and answers `online`."""
    _SEEN_TIMEOUTS.append(float(timeout))
    return PROBE.STATUS_ONLINE


STATUS.probe_ssh = _recording_probe
try:
    _CODE, _OUT, _ERR = run(["--project", MAP, "--timeout", "7", "status"])
finally:
    STATUS.probe_ssh = _ORIGINAL_PROBE
check("§2 `--timeout` is the budget of ONE operation: every probe of the round was handed 7 s",
      _CODE == EX.EXIT_OK and _SEEN_TIMEOUTS == [7.0, 7.0], f"{_CODE} / {_SEEN_TIMEOUTS}")


# ════════════════════════════════════════════════════════════════════════════
print("== §3.0 the verb table ==")
# ════════════════════════════════════════════════════════════════════════════

DISPATCH.load_verbs()
VERBS = DISPATCH.VERBS
check("§3.0 the registry is the contract's verbs (the base FIVE plus the `hostkey` and `import` families)",
      set(VERBS) == {"inventory", "connections", "status", "doctor", "exec", "hostkey", "import"},
      str(sorted(VERBS)))
check("§3.0 every row declares a summary, a handler and a renderer (two shapes of ONE fact set)",
      all(callable(row.handler) and callable(row.render) and row.summary.strip()
          for row in VERBS.values()))
check("§3.0 the built-in list is the ONE declaration of the lazy load, in order",
      DISPATCH.BUILTIN_VERB_MODULES == ("cli.inventory", "cli.connections", "cli.status",
                                        "cli.doctor", "cli.exec", "cli.hostkey", "cli.imports"))
DISPATCH.register(DISPATCH.Verb("contract-dup", "the duplicate probe", handler=lambda c, a: {}))
try:
    _DUPLICATE = raises(ValueError, lambda: DISPATCH.register(
        DISPATCH.Verb("contract-dup", "again", handler=lambda c, a: {})))
    _NO_HANDLER = raises(ValueError, lambda: DISPATCH.register(
        DISPATCH.Verb("contract-no-handler", "the handler-less row")))
finally:
    forget("contract-dup")
check("§3.0 `register()` refuses a duplicate name and a row without a handler",
      _DUPLICATE and _NO_HANDLER, f"duplicate={_DUPLICATE} no_handler={_NO_HANDLER}")
check("§3.0 a verb without a row is a USAGE error, never a silent success and never a half-run",
      run(["contract-nosuchverb"])[0] == EX.EXIT_USAGE)
_SPY = {"called": False}


def _spy_handler(context, arguments):
    """A handler that must never fire: the argument-count gate runs BEFORE it."""
    _SPY["called"] = True
    return {}


DISPATCH.register(DISPATCH.Verb("contract-spy", "the argument-count probe", handler=_spy_handler,
                                min_args=1, max_args=1))
try:
    _CODE, _OUT, _ERR = run(["contract-spy"])
finally:
    forget("contract-spy")
check("§3.0 an argument count the row does not declare is USAGE, checked BEFORE the handler",
      _CODE == EX.EXIT_USAGE and not _SPY["called"] and "takes 1..1" in _ERR,
      f"{_CODE} / {_ERR!r}")
_CTX = DISPATCH.Context(invocation=ARGS.parse_argv(["--project", MAP]))
_STDOUT = io.StringIO()
with contextlib.redirect_stdout(_STDOUT):
    _FACTS = VERBS["inventory"].handler(_CTX, ())
check("§3.0 a handler answers FACTS and never prints (the renderer owns the stream)",
      _STDOUT.getvalue() == "" and isinstance(_FACTS, dict) and tuple(_FACTS) == REPORT.DATA_KEYS)
check("§3.0 `exec` is NOT a mutating verb, and no verb of this build declares the flag",
      VERBS["exec"].mutating is False and not any(row.mutating for row in VERBS.values()))
check("§3.0 `raw_code` marks exactly ONE row — a remote command's own status is the ONE foreign code",
      [name for name, row in VERBS.items() if row.raw_code] == ["exec"])
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "inventory"])
_INV_ROWS = (document(_OUT).get("data") or {}).get("rows") or []
EXPECTED_TEXT = TABLE.list_table_text([EINV.inventory_column_ids()] + _INV_ROWS, ",")
_CODE, _OUT, _ERR = run(["--project", MAP, "inventory"])
check("§3.0 a table's BYTES are the writer's: same cells, CRLF rows, UTF-8 with no BOM",
      _CODE == EX.EXIT_OK and _OUT == EXPECTED_TEXT and "\r\n" in _OUT
      and not _OUT.startswith("\ufeff") and _ERR == "", repr(_OUT[:120]))


# ════════════════════════════════════════════════════════════════════════════
print("== §3.1 inventory ==")
# ════════════════════════════════════════════════════════════════════════════

_CLI_NODES = PROJECT.read_servers(MAP)
_SHIPPED_NODES = SHIPPED.read_project_servers(MAP)


def node_facts(nodes):
    """The identity facts of a `ServerData` list — the ONE comparison the reader clause needs."""
    return [(n.id, n.alias, n.host, n.ssh_port, n.user, tuple(n.tags)) for n in nodes]


check("§3.1 the rows come through the SHIPPED conversion (the standalone terminal's own reader)",
      node_facts(_CLI_NODES) == node_facts(_SHIPPED_NODES),
      f"{node_facts(_CLI_NODES)} vs {node_facts(_SHIPPED_NODES)}")
check("§3.1 the clause names the ONE conversion both readers share (`servers_from_project()`)",
      "`storage/project.servers_from_project()`" in CONTRACT)
_DONE = fresh("import ui.sidebar as S\nimport storage.export_inventory as E\n"
              "print(S.LIST_COLUMNS is E.INVENTORY_COLUMNS)\n"
              "print(','.join(E.inventory_column_ids()))\n")
check("§3.1 the columns are `ui/sidebar.LIST_COLUMNS`' schema — ONE tuple, re-exported",
      _DONE.returncode == 0
      and _DONE.stdout.splitlines()[-2:] == ["True", ",".join(EINV.inventory_column_ids())],
      f"{(_DONE.stdout or '').strip()!r} / {(_DONE.stderr or '')[-160:]}")
check("§3.1 the column ids are the report's own vocabulary (English, never a translated caption)",
      EINV.inventory_column_ids() == [field for field, _key in EINV.INVENTORY_COLUMNS]
      and all(isinstance(column, str) and column.isascii() for column in EINV.inventory_column_ids()))
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "inventory"])
_DATA = document(_OUT).get("data") or {}
check("§3.1 `--json` names the project, the row count, the columns and the rows",
      _CODE == EX.EXIT_OK and _DATA.get("project") == MAP and _DATA.get("count") == 2
      and tuple(_DATA) == REPORT.DATA_KEYS, _OUT[:140])
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "inventory", "--tag", "prod"])
_PROD = document(_OUT).get("data") or {}
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "inventory", "--tag", "prod", "--tag", "web"])
_NARROW = document(_OUT).get("data") or {}
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "inventory", "--tag", "staging"])
_NONE = document(_OUT).get("data") or {}
check("§3.1 `--tag` narrows, repeats, and EVERY named tag must match",
      _PROD.get("count") == 2 and _NARROW.get("count") == 1
      and _NARROW["rows"][0][0] == "web-1", f"{_PROD.get('count')} / {_NARROW.get('rows')}")
check("§3.1 a tag nothing carries is an EMPTY table and exit 0 (a filter is not a failure)",
      _CODE == EX.EXIT_OK and _NONE.get("count") == 0 and _NONE.get("rows") == [])
_CODE, _OUT, _ERR = run(["--project", MAP, "inventory", "--format", "tsv"])
check("§3.1 the TEXT form is the ONE RFC-4180 writer, at the format the row declares",
      _CODE == EX.EXIT_OK and _OUT == TABLE.list_table_text(
          [EINV.inventory_column_ids()] + _INV_ROWS, TABLE.list_delimiter("tsv"))
      and "\t" in _OUT and "\r\n" in _OUT)
check("§3.1 an undeclared `--format` is USAGE (the writer's own ids are the declaration)",
      run(["--project", MAP, "inventory", "--format", "xml"])[0] == EX.EXIT_USAGE
      and VERB_ARGS.TABLE_FORMATS == tuple(TABLE.LIST_DELIMITERS))


# ════════════════════════════════════════════════════════════════════════════
print("== §3.2 connections ==")
# ════════════════════════════════════════════════════════════════════════════


class _FakeServer:
    """The `(data)` surface a report's arrow has — one `ServerData` per endpoint."""

    def __init__(self, data):
        self.data = data


class _FakeArrow:
    """The live-arrow surface `connection_record()` reads (no Qt: a duck-typed stand-in)."""

    def __init__(self, source, target, connection_type, bidirectional, label):
        self.source = source
        self.target = target
        self.connection_type = connection_type
        self.bidirectional = bidirectional
        self.label_text = label


_ARROW = _FakeArrow(_FakeServer(SERVER.server_data_from_dict(WEB)),
                    _FakeServer(SERVER.server_data_from_dict(DB)), "database", True, "api")
_GUI_CELLS = ECON.connection_cells(ECON.connection_record(_ARROW))
_PROJECT = json.loads(read(MAP))
_CLI_CELLS = ECON.connection_rows_from_records(ECON.connection_records_from_project(_PROJECT))
check("§3.2 the rows ARE the shipped data report's cells — the machine half the GUI's row translates",
      _GUI_CELLS == _CLI_CELLS[0] and len(_CLI_CELLS) == 1,
      f"{_GUI_CELLS} vs {_CLI_CELLS}")
check("§3.2 ...and the clause names that half (`connection_cells()`), never the translated row",
      "`storage/export_connections.connection_cells()`" in CONTRACT
      and "connection_records_from_project()`" in CONTRACT)
check("§3.2 the direction is the shipped `source → target` text and the flag the machine `true`/`false`",
      _CLI_CELLS[0][5] == "web-1 → db-1" and _CLI_CELLS[0][6] == "true"
      and ECON.BIDIRECTIONAL_TRUE == "true" and ECON.BIDIRECTIONAL_FALSE == "false")
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "connections"])
_DATA = document(_OUT).get("data") or {}
check("§3.2 `--json` answers the SAME pinned schema over the CONNECTION columns",
      _CODE == EX.EXIT_OK and tuple(_DATA) == REPORT.DATA_KEYS
      and _DATA.get("columns") == ECON.connection_column_ids() and _DATA.get("count") == 1
      and _DATA.get("project") == MAP, _OUT[:140])
for _name, _path in (("NO links", NO_LINKS), ("NO `connections` array", NO_ARRAY),
                     ("NO servers", EMPTY)):
    _CODE, _OUT, _ERR = run(["--project", _path, "connections"])
    check(f"§3.2 a project with {_name} answers an EMPTY table and exit 0 (nothing is broken)",
          _CODE == EX.EXIT_OK and _OUT == ",".join(ECON.connection_column_ids()) + "\r\n",
          repr(_OUT[:100]))
_CODE, _OUT, _ERR = run(["--json", "--project", DANGLING, "connections"])
_DATA = document(_OUT).get("data") or {}
check("§3.2 a link naming an unknown id keeps its row with EMPTY endpoint cells (a report shows it)",
      _CODE == EX.EXIT_OK and _DATA.get("count") == 1
      and _DATA["rows"][0][2:4] == ["", ""] and _DATA["rows"][0][7] == "gone", str(_DATA.get("rows")))


# ════════════════════════════════════════════════════════════════════════════
print("== §3.3 status ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3.3 the probe is the GUI's OWN `services.status_probe.probe_ssh()` (a card and a cron cannot disagree)",
      STATUS.probe_ssh is PROBE.probe_ssh)
check("§3.3 `data` carries the project, the count, the budget, one record per node and the skipped ids",
      STATUS.DATA_KEYS == ("project", "count", "timeout", "nodes", "skipped"))
_ANSWERS = {"192.0.2.10": PROBE.STATUS_ONLINE, "198.51.100.20": PROBE.STATUS_OFFLINE}


def _mixed_probe(host, port, timeout):
    """The three-status rule's deterministic stand-in: a host decides its own answer."""
    return _ANSWERS.get(host, PROBE.STATUS_WARN)


_STATUS_PROBE_SAVED = STATUS.probe_ssh
STATUS.probe_ssh = _mixed_probe
try:
    _CODE, _OUT, _ERR = run(["--project", MAP, "status"])
    _ROUND = _CODE
    _TEXT_LINES = _OUT.splitlines()
    _CODE_JSON, _OUT_JSON, _ERR_JSON = run(["--json", "--project", MAP, "status"])
finally:
    STATUS.probe_ssh = _STATUS_PROBE_SAVED
_DATA = document(_OUT_JSON).get("data") or {}
check("§3.3 the process code is the ROUND's verdict: 4 when any node is warn/offline, with the report intact",
      _ROUND == EX.EXIT_NETWORK and _CODE_JSON == EX.EXIT_NETWORK
      and document(_OUT_JSON).get("ok") is True and document(_OUT_JSON).get("error") is None,
      f"{_ROUND} / {_CODE_JSON}")
check("§3.3 ...the text form is one line per node, in the selection order",
      _TEXT_LINES == ["web-1\tonline", "db-1\toffline"], str(_TEXT_LINES))
check("§3.3 ...and the payload is the pinned keys, `count` counting the nodes really probed",
      tuple(_DATA) == STATUS.DATA_KEYS and _DATA.get("count") == 2
      and _DATA.get("project") == MAP and _DATA.get("timeout") == 10.0
      and [record["status"] for record in _DATA.get("nodes") or ()] == ["online", "offline"],
      str(_DATA))
STATUS.probe_ssh = lambda host, port, timeout: PROBE.STATUS_ONLINE
try:
    _CODE, _OUT, _ERR = run(["--project", MAP, "status"])
finally:
    STATUS.probe_ssh = _STATUS_PROBE_SAVED
check("§3.3 every probed node online is exit 0", _CODE == EX.EXIT_OK, f"{_CODE} / {_ERR!r}")
_NO_PROBE = {"called": False}


def _forbidden_probe(host, port, timeout):
    """A probe that must not fire: an unknown token is a `5` BEFORE the network."""
    _NO_PROBE["called"] = True
    return PROBE.STATUS_ONLINE


STATUS.probe_ssh = _forbidden_probe
try:
    _CODE, _OUT, _ERR = run(["--json", "--project", MAP, "status", "web-1", "nope"])
finally:
    STATUS.probe_ssh = _STATUS_PROBE_SAVED
check("§3.3 an unknown node token is `5`, resolved BEFORE any probe",
      _CODE == EX.EXIT_NOT_FOUND and not _NO_PROBE["called"]
      and document(_OUT).get("error", {}).get("kind") == "not_found", f"{_CODE} / {_OUT[:140]!r}")
STATUS.probe_ssh = lambda host, port, timeout: PROBE.STATUS_ONLINE
try:
    _CODE, _OUT, _ERR = run(["--json", "--project", UNMANAGED, "status"])
finally:
    STATUS.probe_ssh = _STATUS_PROBE_SAVED
_DATA = document(_OUT).get("data") or {}
check("§3.3 an `unmanaged` node is never probed: it is SKIPPED and named in `data.skipped`",
      _CODE == EX.EXIT_OK and _DATA.get("count") == 1 and _DATA.get("skipped") == ["srv-db"]
      and [record["id"] for record in _DATA.get("nodes") or ()] == ["srv-web"], str(_DATA))
_BEFORE = open(MAP, "rb").read()
STATUS.probe_ssh = _mixed_probe
try:
    run(["--project", MAP, "status"])
    run(["--json", "--project", MAP, "status"])
finally:
    STATUS.probe_ssh = _STATUS_PROBE_SAVED
check("§3.3 the round is a READ: no status is written into the project file",
      open(MAP, "rb").read() == _BEFORE)


# ════════════════════════════════════════════════════════════════════════════
print("== §3.4 doctor ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3.4 the steps are the GUI's OWN `services.reachability.diagnose_reachability()`",
      DOCTOR.diagnose_reachability is REACH.diagnose_reachability)
check("§3.4 `data` is the report's own seven fields, no more and no less",
      DOCTOR.DATA_KEYS == ("host", "port", "kind", "ip", "detail", "ping", "elapsed"))


class _Reachability:
    """One report object shaped like `ReachabilityReport` — the fields `doctor` copies."""

    def __init__(self, kind, host="192.0.2.10", port=22, ip="192.0.2.10",
                 detail="SSH-2.0-Contract", ping="", elapsed=0.125):
        self.host, self.port, self.kind, self.ip = host, port, kind, ip
        self.detail, self.ping, self.elapsed = detail, ping, elapsed


_KIND = {"value": "ok"}
_DOCTOR_SAVED = DOCTOR.diagnose_reachability
DOCTOR.diagnose_reachability = lambda host, port, timeout: _Reachability(_KIND["value"])
try:
    _CODE, _OUT, _ERR = run(["--json", "--project", MAP, "doctor", "web-1"])
    _OK_DOC = document(_OUT)
    _KIND["value"] = "tcp_timeout"
    _CODE_TIMEOUT, _OUT_TIMEOUT, _ERR_TIMEOUT = run(["--json", "--project", MAP, "doctor", "web-1"])
    _KIND["value"] = "banner_foreign"
    _CODE_FOREIGN, _OUT_FOREIGN, _ERR_FOREIGN = run(["--json", "--project", MAP, "doctor", "web-1"])
    _KIND["value"] = "ok"
    _CODE_TEXT, _OUT_TEXT, _ERR_TEXT = run(["--project", MAP, "doctor", "web-1"])
finally:
    DOCTOR.diagnose_reachability = _DOCTOR_SAVED
_DOCTOR_DATA = _OK_DOC.get("data") or {}
check("§3.4 a live node answers 0, `ok: true`, and the report's seven fields in their own order",
      _CODE == EX.EXIT_OK and _OK_DOC.get("ok") is True
      and tuple(_DOCTOR_DATA) == DOCTOR.DATA_KEYS
      and _DOCTOR_DATA.get("host") == "192.0.2.10"
      and _DOCTOR_DATA.get("port") == 22 and _DOCTOR_DATA.get("detail") == "SSH-2.0-Contract",
      str(_DOCTOR_DATA))
check("§3.4 the verdict is the report's OWN kind: a timeout is 6, every other failure is 4",
      _CODE_TIMEOUT == EX.EXIT_TIMEOUT and _CODE_FOREIGN == EX.EXIT_NETWORK
      and document(_OUT_TIMEOUT).get("ok") is True
      and document(_OUT_FOREIGN).get("ok") is True,
      f"{_CODE_TIMEOUT} / {_CODE_FOREIGN}")
check("§3.4 a broken node is still a REPORT: `ok: true`, the data intact, the failure only in the code",
      (document(_OUT_TIMEOUT).get("data") or {}).get("kind") == "tcp_timeout"
      and (document(_OUT_FOREIGN).get("data") or {}).get("kind") == "banner_foreign"
      and document(_OUT_TIMEOUT).get("error") is None)
check("§3.4 the TEXT form renders the same facts, one `key: value` line each, `elapsed` rounded there",
      _CODE_TEXT == EX.EXIT_OK and len(_OUT_TEXT.splitlines()) == len(DOCTOR.DATA_KEYS)
      and _OUT_TEXT.splitlines()[-1] == "elapsed: 0.125"
      and _DOCTOR_DATA.get("elapsed") == 0.125, repr(_OUT_TEXT))
check("§3.4 an unknown node is `not_found` (5) with `ok: false` and NO data",
      (lambda pair: pair[0] == EX.EXIT_NOT_FOUND and document(pair[1]).get("ok") is False
       and document(pair[1]).get("data") is None
       and document(pair[1]).get("error", {}).get("kind") == "not_found")(
          run(["--json", "--project", MAP, "doctor", "nope"])))
check("§3.4 `doctor` takes exactly ONE node (two tokens are a USAGE error before any probe)",
      run(["--project", MAP, "doctor", "web-1", "db-1"])[0] == EX.EXIT_USAGE)
check("§3.4 the kind→code table declares the contract's three classes and nothing else",
      DOCTOR.exit_code_for_kind("ok") == EX.EXIT_OK
      and DOCTOR.exit_code_for_kind("dns_timeout") == EX.EXIT_TIMEOUT
      and DOCTOR.exit_code_for_kind("tcp_timeout") == EX.EXIT_TIMEOUT
      and all(DOCTOR.exit_code_for_kind(kind) == EX.EXIT_NETWORK
              for kind in REACH.REPORT_KINDS if kind not in ("ok", "dns_timeout", "tcp_timeout")),
      {kind: DOCTOR.exit_code_for_kind(kind) for kind in REACH.REPORT_KINDS})


# ════════════════════════════════════════════════════════════════════════════
print("== §3.5 exec ==")
# ════════════════════════════════════════════════════════════════════════════

_REQUEST = VERB_ARGS.read_exec(["web-1", "df -h"])
check("§3.5 `<node> \"<command>\"`: the FIRST bare token is the node, the rest join with ONE space",
      (_REQUEST.node, _REQUEST.command) == ("web-1", "df -h"), str(_REQUEST))
check("§3.5 the five policy flags are the contract's, read wherever they stand in the tail",
      VERB_ARGS.EXEC_VALUE_FLAGS == ("--identity", "--host-key")
      and VERB_ARGS.EXEC_SWITCHES == ("--accept-new", "--allow-destructive", "--dry-run")
      and VERB_ARGS.read_exec(["web-1", "ls", "--identity", "k", "--accept-new",
                               "--host-key", "SHA256:x", "--allow-destructive"]).identity == "k")
check("§3.5 an unquoted flag-shaped word is a USAGE error: `exec web-1 df -h` is not the command `df -h`",
      cost(["exec", "web-1", "df", "-h"]) is None
      and raises(ERR.CliError, lambda: VERB_ARGS.read_exec(["web-1", "df", "-h"])))
check("§3.5 ...while a QUOTED command stays one token, verbatim (never re-split and never interpreted)",
      VERB_ARGS.read_exec(["web-1", "df -h --all"]).command == "df -h --all"
      and VERB_ARGS.read_exec(["web-1", "echo", "a", "b"]).command == "echo a b")
check("§3.5 a switch carrying `=value`, a value flag with no value and a bare node are all USAGE",
      raises(ERR.CliError, lambda: VERB_ARGS.read_exec(["web-1", "ls", "--accept-new=yes"]))
      and raises(ERR.CliError, lambda: VERB_ARGS.read_exec(["web-1", "ls", "--host-key"]))
      and raises(ERR.CliError, lambda: VERB_ARGS.read_exec(["web-1"])))
_CODE, _OUT, _ERR = run(["--project", EXEC_MAP, "exec", "web-1", "uptime", "--dry-run"])
check("§3.5 `--dry-run` prints the guard's verdict and the command it WOULD run, opens nothing, exits 0",
      _CODE == EX.EXIT_OK and _OUT.splitlines() == ["guard: none", "command: uptime"] and _ERR == "",
      f"{_CODE} / {_OUT!r}")
_CRED_CALLED = {"value": False}
_ORIGINAL_RESOLVE = CREDENTIALS.resolve


def _forbidden_resolve(node, identity="", manager=None):
    """A credential resolution that must not fire: the guard answers first."""
    _CRED_CALLED["value"] = True
    return CREDENTIALS.Credential(CREDENTIALS.CRED_AGENT)


EXEC.credentials.resolve = _forbidden_resolve
try:
    _CODE, _OUT, _ERR = run(["--project", EXEC_MAP, "exec", "web-1", "rm -rf /"])
finally:
    EXEC.credentials.resolve = _ORIGINAL_RESOLVE
check("§5.3 ...and a destructive command is REFUSED (2) by the guard BEFORE the credential and the wire",
      _CODE == EX.EXIT_REFUSAL and not _CRED_CALLED["value"]
      and "rm -rf" in _ERR and "rm -rf /" in _ERR, f"{_CODE} / {_ERR!r}")
_CODE, _OUT, _ERR = run(["--json", "--project", UNMANAGED, "exec", "db-1", "uptime"])
check("§3.5 an `unmanaged` node is REFUSED (2): nothing may open a session to it",
      _CODE == EX.EXIT_REFUSAL
      and document(_OUT).get("error", {}).get("kind") == "refusal"
      and "unmanaged" in document(_OUT).get("error", {}).get("message", ""), _OUT[:160])

_DATA_KEYS_EXEC = ("project", "node", "command", "dry_run", "guard", "auth", "exit_code", "stdout",
                   "stderr", "truncated")
check("§3.5 the remote answer's `data` keys are the pinned ten, in the pinned order",
      EXEC.DATA_KEYS == _DATA_KEYS_EXEC)


class _FakeSession:
    """One authenticated session's answer — the ONE seam the verb's policy tests replace."""

    def __init__(self, answer=(0, "", "", False)):
        self.answer = answer
        self.calls = []
        self.closed = False

    def run(self, command, timeout):
        """Record the command and its budget, then answer the configured result."""
        self.calls.append((command, float(timeout)))
        return self.answer

    def close(self):
        """Mark the session closed (the verb closes it on every path)."""
        self.closed = True


_SESSION = _FakeSession((7, "out\n", "warning: x\n", False))
_ORIGINAL_OPEN = EXEC.open_session
EXEC.open_session = lambda node, credential, options, timeout, note=None: _SESSION
EXEC.credentials.resolve = lambda node, identity="", manager=None: CREDENTIALS.Credential(
    CREDENTIALS.CRED_AGENT)
try:
    _CODE, _OUT, _ERR = run(["--project", EXEC_MAP, "--timeout", "3", "exec", "web-1", "uptime"])
    _CODE_JSON, _OUT_JSON, _ERR_JSON = run(["--json", "--project", EXEC_MAP, "--timeout", "3",
                                            "exec", "web-1", "uptime"])
finally:
    EXEC.open_session = _ORIGINAL_OPEN
    EXEC.credentials.resolve = _ORIGINAL_RESOLVE
_EXEC_DATA = document(_OUT_JSON).get("data") or {}
check("§3.5 the REMOTE exit code is the process's own answer, and the stdout is the text form verbatim",
      _CODE == 7 and _OUT == "out\n" and _SESSION.calls[-1] == ("uptime", 3.0)
      and len(_SESSION.calls) == 2, f"{_CODE} / {_OUT!r} / {_SESSION.calls}")
check("§3.5 ...and the session is CLOSED on that path (a run leaves no client behind)",
      _SESSION.closed is True)
check("§3.5 ...the remote stderr is the diagnostics channel, never mixed into the report",
      _ERR.strip() == "warning: x" and "warning" not in _OUT, repr(_ERR))
check("§3.5 ...and `--json` keeps the same facts under the pinned keys",
      _CODE_JSON == 7 and tuple(_EXEC_DATA) == EXEC.DATA_KEYS
      and _EXEC_DATA.get("exit_code") == 7 and _EXEC_DATA.get("stdout") == "out\n"
      and _EXEC_DATA.get("stderr") == "warning: x\n" and _EXEC_DATA.get("dry_run") is False
      and _EXEC_DATA.get("truncated") is False and _EXEC_DATA.get("auth") == CREDENTIALS.CRED_AGENT
      and (_EXEC_DATA.get("node") or {}).get("id") == "srv-web", str(_EXEC_DATA))
_SESSION = _FakeSession((0, "x" * 4, "", True))
EXEC.open_session = lambda node, credential, options, timeout, note=None: _SESSION
EXEC.credentials.resolve = lambda node, identity="", manager=None: CREDENTIALS.Credential(
    CREDENTIALS.CRED_AGENT)
try:
    _CODE, _OUT, _ERR = run(["--json", "--project", EXEC_MAP, "exec", "web-1", "cat"])
finally:
    EXEC.open_session = _ORIGINAL_OPEN
    EXEC.credentials.resolve = _ORIGINAL_RESOLVE
check("§3.5 a cut remote stream is `truncated: true` AND ONE stderr line (a cut report is never silent)",
      _CODE == EX.EXIT_OK and (document(_OUT).get("data") or {}).get("truncated") is True
      and _ERR.splitlines() == [f"the remote output was truncated at {EXEC.OUTPUT_MAX_BYTES} "
                                f"bytes per stream"], repr(_ERR))


class _Channel:
    """The status surface of ONE fake channel: `shutdown_write()` is the EOF the run must send."""

    def __init__(self, code):
        self.exit_status = int(code)
        self.status_event = threading.Event()
        self.status_event.set()
        self.eof = False

    def recv_exit_status(self):
        """Answer the configured remote code."""
        return self.exit_status

    def shutdown_write(self):
        """Record the EOF (paramiko's `ChannelStdinFile.close()` calls exactly this)."""
        self.eof = True


class _Stdin:
    """The stdin handle of a fake channel — `close()` IS the EOF."""

    def __init__(self, channel, log):
        self.channel, self.log = channel, log

    def close(self):
        """Send the EOF the remote command waits for."""
        self.log.append("eof")
        self.channel.shutdown_write()


class _Stream:
    """One fake stdout/stderr: it REFUSES a read before the EOF (the order the clause declares)."""

    def __init__(self, payload, channel, log):
        self.payload, self.channel, self.log = payload, channel, log

    def read(self, size=None):
        """Answer the next chunk — and fail the run when stdin was not closed first."""
        assert self.channel.eof, "a stream was read before stdin got its EOF"
        size = len(self.payload) if size is None else max(0, int(size))
        chunk, self.payload = self.payload[:size], self.payload[size:]
        self.log.append("read")
        return chunk


class _Wire:
    """A fake client for `Session.run()` — no socket, no Qt, the three surfaces paramiko answers."""

    def __init__(self, answer, log):
        self.answer, self.log = answer, log

    def exec_command(self, command, timeout=None):
        """Answer the three channel handles of ONE command."""
        code, out, err = self.answer
        channel = _Channel(code)
        return (_Stdin(channel, self.log), _Stream(out, channel, self.log),
                _Stream(err, channel, self.log))

    def close(self):
        """Record the close."""
        self.log.append("closed")


_LOG = []
_CODE, _OUT, _ERR, _CUT = EXEC.Session(_Wire((5, b"out", b"err"), _LOG)).run("cat", 5)
check("§3.5 the remote command receives EOF on stdin BEFORE its output is read",
      _CODE == 5 and _LOG[0] == "eof" and "read" in _LOG and _CUT is False, str(_LOG))
_ORIGINAL_LIMIT = EXEC.OUTPUT_MAX_BYTES
try:
    EXEC.OUTPUT_MAX_BYTES = 4
    _LOG = []
    _CODE, _OUT, _ERR, _CUT = EXEC.Session(_Wire((0, b"0123456789", b""), _LOG)).run("cat", 5)
    check("§3.5 the output is BOUNDED: the head is kept, the stream still drained, the cut reported",
          _CODE == EX.EXIT_OK and _OUT == "0123" and _CUT is True, f"{_OUT!r} / {_CUT}")
finally:
    EXEC.OUTPUT_MAX_BYTES = _ORIGINAL_LIMIT
check("§3.5 the ceiling is ONE declaration: 64 MiB per stream",
      EXEC.OUTPUT_MAX_BYTES == 64 * 1024 * 1024)

_KEY_A = paramiko.ECDSAKey.generate()
_KEY_B = paramiko.ECDSAKey.generate()


class _Transport:
    """The transport surface `--host-key` verification reads the presented key from."""

    def __init__(self, key=None, error=None):
        self.key, self.error = key, error

    def get_remote_server_key(self):
        """The key this connection presented (or the failure of reading it)."""
        if self.error is not None:
            raise self.error
        return self.key


class _Presented:
    """A client whose transport presented `key` — the ONE half `verify_presented_key()` reads."""

    def __init__(self, key=None, error=None):
        self._transport = _Transport(key, error)

    def get_transport(self):
        """The transport of THIS connection."""
        return self._transport


_VERIFIED = True
try:
    EXEC.verify_presented_key(_Presented(_KEY_A), HKP.fingerprint(_KEY_A))
except HKP.HostKeyRejected:
    _VERIFIED = False
check("§3.5 `--host-key` is VERIFIED against the key the server presented on EVERY path",
      _VERIFIED
      and raises(HKP.HostKeyRejected,
                 lambda: EXEC.verify_presented_key(_Presented(_KEY_A), HKP.fingerprint(_KEY_B)))
      and raises(HKP.HostKeyRejected,
                 lambda: EXEC.verify_presented_key(_Presented(None, RuntimeError("no transport")),
                                                   HKP.fingerprint(_KEY_A))))
_CHANGED = EXEC.classify(paramiko.BadHostKeyException("192.0.2.10", _KEY_A, _KEY_B))
check("§5.2 a CHANGED key is a REFUSAL (2) under every flag — a moved pin is not a new host",
      _CHANGED.code == EX.EXIT_REFUSAL and "CHANGED" in _CHANGED.message
      and "--accept-new never covers a moved pin" in _CHANGED.message, _CHANGED.message)


# ════════════════════════════════════════════════════════════════════════════
print("== §3.6 hostkey verify ==")
# ════════════════════════════════════════════════════════════════════════════

import cli.hostkey as HOSTKEY  # noqa: E402 — the sixth row, asked of its own module

check("§3.6 the contract declares the form, the four verdicts and the read-only rule",
      "| `hostkey verify` |" in CONTRACT
      and all(f"`{verdict}`" in CONTRACT for verdict in HKP.VERIFY_VERDICTS)
      and "**Nothing is written, ever:**" in CONTRACT)
_HK_ROW = VERBS["hostkey"]
check("§3.6 the row takes its ONE subcommand token, draws a report and writes nothing",
      (_HK_ROW.min_args, _HK_ROW.max_args) == (1, 1) and _HK_ROW.mutating is False
      and callable(_HK_ROW.render) and callable(_HK_ROW.verdict)
      and VERB_ARGS.SUBCOMMANDS == {"hostkey": ("verify",)}, str(_HK_ROW))
check("§3.6 the payload is the contract's — store, count, timeout, entries — and a row its SIX columns",
      HOSTKEY.DATA_KEYS == ("store", "count", "timeout", "entries")
      and HOSTKEY.COLUMNS == ("host", "keytype", "verdict", "stored", "presented", "detail"))
check("§3.6 ONE probe per ENDPOINT: the pins of one `[host]:port` share a single target",
      [len(target[2]) for target in HKP.verify_targets(
          [{"host": "[a]:22", "keytype": "ssh-rsa", "fingerprint": "SHA256:1"},
           {"host": "[a]:22", "keytype": "ssh-ed25519", "fingerprint": "SHA256:2"},
           {"host": "b", "keytype": "ssh-rsa", "fingerprint": "SHA256:3"}])] == [2, 1])
check("§3.6 the process code is the ROUND's verdict: changed 2, else unreachable 4, else 0",
      HOSTKEY.verdict({"entries": [{"verdict": HKP.VERIFY_OK}]}) == EX.EXIT_OK
      and HOSTKEY.verdict({"entries": [{"verdict": HKP.VERIFY_UNVERIFIED}]}) == EX.EXIT_OK
      and HOSTKEY.verdict({"entries": [{"verdict": HKP.VERIFY_UNREACHABLE}]}) == EX.EXIT_NETWORK
      and HOSTKEY.verdict({"entries": [{"verdict": HKP.VERIFY_UNREACHABLE},
                                       {"verdict": HKP.VERIFY_CHANGED}]}) == EX.EXIT_REFUSAL
      and HOSTKEY.verdict({}) == EX.EXIT_OK)
_BAD_STORE = os.path.join(str(WORK), "contract_bad_known_hosts")
with open(_BAD_STORE, "w", encoding="utf-8") as _handle:
    _handle.write("web-1 ssh-rsa AAAAnotbase64\n")
_BAD_BYTES = open(_BAD_STORE, "rb").read()
HKP.set_store(HKP.KnownHostsStore(_BAD_STORE))
_CODE, _OUT, _ERR = run(["--json", "hostkey", "verify"])
_BAD_DOC = json.loads(_OUT or "{}")
check("§3.6 an unreadable store is a REFUSAL (2) naming the path, and the file is left as it was",
      _CODE == EX.EXIT_REFUSAL and _BAD_DOC.get("ok") is False and _BAD_DOC.get("data") is None
      and _BAD_DOC.get("error", {}).get("kind") == "refusal"
      and _BAD_STORE in _BAD_DOC.get("error", {}).get("message", "")
      and open(_BAD_STORE, "rb").read() == _BAD_BYTES, _OUT[:160])
HKP.set_store(HKP.KnownHostsStore(os.path.join(WORK, "contract_known_hosts")))


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the `--json` envelope ==")
# ════════════════════════════════════════════════════════════════════════════

_OK = ENV.build("inventory", data={"count": 1})
_FAIL = ENV.build("inventory", error=ERR.refusal("nope", "pin the key").record())
check("§4 the envelope has FIVE keys and no others, in the declared order",
      tuple(_OK) == ENV.ENVELOPE_KEYS == ("schema", "verb", "ok", "data", "error")
      and tuple(_FAIL) == ENV.ENVELOPE_KEYS)
check("§4 `schema` is the ENVELOPE's own version, apart from the project JSON format",
      ENV.SCHEMA_VERSION == 1 and version.VERSION_FORMAT == "0.9")
check("§4 `ok` describes the RUN: a success carries data and no error, a failure the reverse",
      _OK["ok"] is True and _OK["data"] == {"count": 1} and _OK["error"] is None
      and _FAIL["ok"] is False and _FAIL["data"] is None
      and _FAIL["error"] == {"code": EX.EXIT_REFUSAL, "kind": "refusal",
                             "message": "nope", "hint": "pin the key"}, str(_FAIL["error"]))
check("§4 `kind` is the exit-code table's machine name (one vocabulary for a message, a doc and a script)",
      set(EX.EXIT_NAMES.values()) == {"ok", "usage", "refusal", "auth", "network", "not_found",
                                      "timeout"}
      and all(ERR.CliError("m", code).record()["kind"] == EX.EXIT_NAMES[code] for code in EX.EXIT_CODES))
_CODE, _OUT, _ERR = run(["--json", "--version"])
_DOC = document(_OUT)
check("§4 `verb` is \"\" when an option answered, and the option's facts are the payload",
      _CODE == EX.EXIT_OK and _DOC.get("verb") == "" and _DOC.get("ok") is True
      and _DOC.get("data") == {"name": version.APP_NAME, "version": version.APP_VERSION}, _OUT[:120])
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "inventory"])
check("§4 a `--json` run writes exactly ONE document on stdout and NOTHING on stderr",
      _CODE == EX.EXIT_OK and _OUT.strip().startswith("{") and _OUT.strip().endswith("}")
      and _OUT.count("\n{") == 0 and _ERR == "", f"{_ERR!r} / {_OUT[:120]!r}")
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "doctor", "nope"])
check("§4 a run that could NOT answer a report answers `ok: false`, `data: null` and the error record",
      _CODE == EX.EXIT_NOT_FOUND and document(_OUT).get("ok") is False
      and document(_OUT).get("data") is None and document(_OUT).get("error"))
_CODE_B, _OUT_B, _ERR_B = child_bytes(["--json", "--project", UNICODE_MAP, "inventory"],
                                      {"PYTHONIOENCODING": "cp1251"})
check("§4 the document is UTF-8 BYTES with ONE trailing newline, no BOM, whatever the console code page",
      _CODE_B == EX.EXIT_OK and _OUT_B.startswith(b"{") and not _OUT_B.startswith(b"\xef\xbb\xbf")
      and _OUT_B.endswith(b"}\n") and not _OUT_B.endswith(b"\r\n")
      and "東京サーバー".encode("utf-8") in _OUT_B, _OUT_B[:120])


# ════════════════════════════════════════════════════════════════════════════
print("== §5.1 the credential policy ==")
# ════════════════════════════════════════════════════════════════════════════

_NODE = SERVER.server_data_from_dict(WEB)
_KEY_FILE = os.path.join(WORK, "contract_key")
with open(_KEY_FILE, "w", encoding="utf-8") as _handle:
    _handle.write("not a real key — only the PATH is read here\n")
check("§5.1 the three declared sources are key / password / agent, in that order",
      CREDENTIALS.CRED_SOURCES == ("key", "password", "agent"))
_IDENTITY = CREDENTIALS.resolve(_NODE, identity=_KEY_FILE)
check("§5.1 `--identity PATH` selects a private key FILE, and it wins over everything",
      _IDENTITY.branch == CREDENTIALS.CRED_KEY and _IDENTITY.key_path == os.path.abspath(_KEY_FILE)
      and _IDENTITY.password == "")
_MISSING = None
try:
    CREDENTIALS.resolve(_NODE, identity=os.path.join(WORK, "no_such_key"))
except ERR.CliError as exc:
    _MISSING = exc
check("§5.1 a key the run NAMES and cannot open is a REFUSAL (2) whose sentence names the door",
      _MISSING is not None and _MISSING.code == EX.EXIT_REFUSAL and DOOR in _MISSING.hint,
      repr(_MISSING))
_NODE_KEY = SERVER.server_data_from_dict(dict(WEB, key_path=_KEY_FILE))
check("§5.1 ...else the node's OWN key file answers the same source",
      CREDENTIALS.resolve(_NODE_KEY).branch == CREDENTIALS.CRED_KEY)


class _SecretStore:
    """A keyring-shaped stand-in: one secret for ONE endpoint, one saved scope, never a write."""

    def __init__(self, secret="", scope="", bound=""):
        self.secret, self.scope, self.bound = secret, scope, bound

    def load_password(self, server_id, scope=None):
        """The secret bound to `scope` — the endpoint rule the real manager applies."""
        return self.secret if str(scope or "") == self.scope else ""

    def stored_scope(self, server_id):
        """The endpoint the secret was saved FOR."""
        return self.bound


_SCOPE = "deploy@192.0.2.10:22"
_STORED = CREDENTIALS.resolve(_NODE, manager=_SecretStore("pw", _SCOPE))
check("§5.1 the keyring answers only for the ENDPOINT the secret was stored for (`sshmap:{id}` + scope)",
      _STORED.branch == CREDENTIALS.CRED_PASSWORD and _STORED.password == "pw"
      and _STORED.scope == _SCOPE, str(_STORED))
_FOREIGN = None
try:
    CREDENTIALS.resolve(_NODE, manager=_SecretStore("", "", "someone@203.0.113.9:2222"))
except ERR.CliError as exc:
    _FOREIGN = exc
check("§5.1 a secret bound to ANOTHER endpoint is that same refusal — never a fall-through to the agent",
      _FOREIGN is not None and _FOREIGN.code == EX.EXIT_REFUSAL
      and "203.0.113.9:2222" in _FOREIGN.message and _SCOPE in _FOREIGN.message, repr(_FOREIGN))
check("§5.1 ...and with no secret of ours the ssh-agent is the LAST source (the shipped fallback)",
      CREDENTIALS.resolve(_NODE, manager=_SecretStore()).branch == CREDENTIALS.CRED_AGENT)
_SECRET_SCAN = {name: source for name, _file, source in cli_sources()}
check("§5.1 no secret is read from stdin, an environment variable or argv (the three forbidden doors)",
      not [name for name, source in _SECRET_SCAN.items()
           if any(token in source for token in ("getpass", "input(", "os.environ"))]
      and [name for name, source in _SECRET_SCAN.items() if "sys.argv" in source] == ["main"],
      [name for name, source in _SECRET_SCAN.items()
       if any(token in source for token in ("getpass", "input(", "os.environ", "sys.argv"))])


# ════════════════════════════════════════════════════════════════════════════
print("== §5.2 the host-key policy ==")
# ════════════════════════════════════════════════════════════════════════════

HKP.set_store(HKP.KnownHostsStore(os.path.join(WORK, "contract_known_hosts")))
_STORE = HKP.get_store()


def policy_verdict(policy, key, name="h-contract"):
    """Call the policy's `missing_host_key()` and answer `(raised message, policy)`."""
    try:
        policy.missing_host_key(None, name, key)
    except HKP.HostKeyRejected as exc:
        return str(exc), policy
    return "", policy


_MESSAGE, _POLICY = policy_verdict(CLI_HOSTKEYS.CliHostKeyPolicy("h-unknown", 22), _KEY_A)
check("§5.2 an unpinned host key is a REFUSAL (2) — a bulk run has no dialog to ask through",
      bool(_MESSAGE) and "not pinned" in _MESSAGE and HKP.fingerprint(_KEY_A) in _MESSAGE
      and _POLICY.pinned is False and _STORE.lookup("h-unknown") is None, _MESSAGE)
_NOTES = []
_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-accept", 22, accept_new=True, note=_NOTES.append), _KEY_A)
check("§5.2 `--accept-new` pins a NEW key through `KnownHostsStore.replace()` and says so on stderr",
      not _MESSAGE and _POLICY.pinned is True and _POLICY.accepted_new_key is True
      and _STORE.lookup("h-accept") is not None and "pinned the host key of h-accept" in _NOTES[0],
      repr(_NOTES))
_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-named", 22, expected=HKP.fingerprint(_KEY_A)), _KEY_A)
check("§5.2 `--host-key FP` pins the key it NAMES (the `SHA256:` head matched either way)",
      not _MESSAGE and _POLICY.pinned is True and _STORE.lookup("h-named") is not None,
      _MESSAGE)
_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-foreign", 22, expected=HKP.fingerprint(_KEY_B)), _KEY_A)
check("§5.2 ...and REFUSES any other key the server presents",
      bool(_MESSAGE) and HKP.fingerprint(_KEY_B) in _MESSAGE
      and _STORE.lookup("h-foreign") is None, _MESSAGE)
check("§5.2 the fingerprint normaliser is ONE reader (`SHA256:` in either case)",
      CLI_HOSTKEYS.normalize_fingerprint(" sha256:abc ") == "SHA256:abc"
      and CLI_HOSTKEYS.normalize_fingerprint("abc") == "abc")
_BROKEN_STORE = os.path.join(WORK, "contract_known_hosts_broken")
with open(_BROKEN_STORE, "w", encoding="utf-8") as _handle:
    _handle.write("h-broken ssh-rsa NOT-A-KEY\n")
HKP.set_store(HKP.KnownHostsStore(_BROKEN_STORE))
_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-broken", 22, accept_new=True), _KEY_A)
check("§5.2 a store that cannot be WRITTEN refuses the run (never an unremembered pin)",
      bool(_MESSAGE) and "refuses" in _MESSAGE and _POLICY.pinned is False
      and read(_BROKEN_STORE).endswith("NOT-A-KEY\n"), _MESSAGE)
HKP.set_store(HKP.KnownHostsStore(os.path.join(WORK, "contract_known_hosts")))


# ════════════════════════════════════════════════════════════════════════════
print("== §5.3 the command guard is ASKED ==")
# ════════════════════════════════════════════════════════════════════════════

check("§5.3 the classifier is the SHIPPED `modules.command_guard.dangerous_token()` (the ONE rule)",
      GUARD.dangerous_token("rm -rf /") == "rm -rf" and GUARD.dangerous_token("uptime") == ""
      and GUARD.dangerous_token("reboot") == "reboot")
_CODE, _OUT, _ERR = run(["--project", EXEC_MAP, "exec", "web-1", "rm -rf /"])
check("§5.3 a destructive shape is REFUSED (2) unless `--allow-destructive`, naming token and command",
      _CODE == EX.EXIT_REFUSAL and "'rm -rf'" in _ERR and "'rm -rf /'" in _ERR
      and "the command guard refused" in _ERR, _ERR[:160])
APP_CONFIG.save_config({GUARD.GUARD_COMMANDS_KEY: False})
try:
    _CODE, _OUT, _ERR = run(["--project", EXEC_MAP, "exec", "web-1", "reboot"])
finally:
    try:
        os.remove(APP_CONFIG.CONFIG_FILE)
    except OSError:
        pass
check("§5.3 `guard_commands` governs the map's DIALOGS only — it never disarms a headless run",
      _CODE == EX.EXIT_REFUSAL and "reboot" in _ERR
      and GUARD.guard_enabled({GUARD.GUARD_COMMANDS_KEY: False}) is False, _ERR[:160])
_SESSION = _FakeSession((0, "done\n", "", False))
EXEC.open_session = lambda node, credential, options, timeout, note=None: _SESSION
EXEC.credentials.resolve = lambda node, identity="", manager=None: CREDENTIALS.Credential(
    CREDENTIALS.CRED_AGENT)
try:
    _CODE, _OUT, _ERR = run(["--project", EXEC_MAP, "exec", "web-1", "reboot",
                             "--allow-destructive"])
finally:
    EXEC.open_session = _ORIGINAL_OPEN
    EXEC.credentials.resolve = _ORIGINAL_RESOLVE
check("§5.3 `--allow-destructive` is the ONE opt-in — the same command then runs",
      _CODE == EX.EXIT_OK and _SESSION.calls == [("reboot", 10.0)] and _OUT == "done\n",
      f"{_CODE} / {_SESSION.calls}")
_CODE, _OUT, _ERR = run(["--project", EXEC_MAP, "exec", "web-1", "rm -rf /", "--dry-run"])
check("§5.3 `--dry-run` prints the guard's verdict with NO connection and NO credential",
      _CODE == EX.EXIT_OK and _OUT.splitlines() == ["guard: rm -rf", "command: rm -rf /"],
      f"{_CODE} / {_OUT!r}")


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the Qt-free rule ==")
# ════════════════════════════════════════════════════════════════════════════

_SOURCES = cli_sources()
check("§6 no module of `cli/` imports PySide6 — at import time or at call time",
      not [name for name, _file, source in _SOURCES if qt_import_lines(source)],
      [name for name, _file, source in _SOURCES if qt_import_lines(source)])
_SOURCE_NAMES = sorted(name for name, _file, _source in _SOURCES)
_DONE = fresh("import importlib, sys\n"
              f"for name in {_SOURCE_NAMES!r}:\n"
              "    importlib.import_module('cli' if name == '__init__' else 'cli.' + name)\n"
              "print('QT', 'PySide6' in sys.modules, file=sys.stderr)\n")
check("§6 importing EVERY module of `cli/` prints NOTHING on stdout and leaves PySide6 out",
      _DONE.returncode == 0 and _DONE.stdout == "" and _DONE.stderr.strip() == "QT False",
      f"{(_DONE.stdout or '')[:80]!r} / {(_DONE.stderr or '').strip()[-160:]!r}")
_PURE_LAYERS = ("storage.project", "storage.table_text", "storage.export_connections",
                "storage.export_problems", "modules.sftp_search", "modules.sftp_limits",
                "modules.command_guard", "modules.ssh_connect", "modules.host_key_policy",
                "modules.local_paths", "services.reachability", "services.status_probe",
                "services.credential_manager", "modules.terminal_config")
_DONE = fresh("import importlib, sys\n"
              f"for name in {_PURE_LAYERS!r}:\n"
              "    importlib.import_module(name)\n"
              "print('QT', 'PySide6' in sys.modules, file=sys.stderr)\n")
check("§6 every pure layer the contract names imports without Qt (`N169`–`N172` turned)",
      _DONE.returncode == 0 and _DONE.stderr.strip() == "QT False",
      f"{(_DONE.stderr or '').strip()[-200:]!r}")
check("§6 the gate the contract POINTS at is the one this suite runs (`tests/test_cli.py` §2)",
      "tests/test_cli.py" in CONTRACT and "§2" in CONTRACT
      and os.path.isfile(os.path.join(ROOT, "tests", "test_cli.py")))


# ════════════════════════════════════════════════════════════════════════════
print("== §7 what the CLI does NOT do ==")
# ════════════════════════════════════════════════════════════════════════════

_FORBIDDEN_IMPORTS = {"PySide6", "ui", "graphics", "i18n", "main"}
_IMPORTERS = {name: imports_of(os.path.join(CLI_DIR, file)) for name, file, _source in _SOURCES}
check("§7 no GUI control: `cli/` imports no `ui/`, `graphics/` or `main`, and no PySide6",
      not [name for name, imports in _IMPORTERS.items()
           if {module.split(".")[0] for module in imports} & _FORBIDDEN_IMPORTS],
      {name: sorted(module for module in imports
                    if module.split(".")[0] in _FORBIDDEN_IMPORTS)
       for name, imports in _IMPORTERS.items()})
_LISTENER = [name for name, _file, source in _SOURCES
             if any(token in source for token in (".bind(", ".listen(", ".accept(", "socketserver"))]
check("§7 no listener and no server: no module of `cli/` binds, listens or accepts",
      not _LISTENER, str(_LISTENER))
_BEFORE = open(MAP, "rb").read()
_LISTING = sorted(os.listdir(WORK))
STATUS.probe_ssh = _mixed_probe
DOCTOR.diagnose_reachability = lambda host, port, timeout: _Reachability("ok")
try:
    run(["--project", MAP, "inventory"])
    run(["--project", MAP, "connections"])
    run(["--project", MAP, "status"])
    run(["--project", MAP, "doctor", "web-1"])
    run(["--project", MAP, "exec", "web-1", "uptime", "--dry-run"])
    check("§7 ...no verb writes the project, and the work folder gains no file",
          open(MAP, "rb").read() == _BEFORE and sorted(os.listdir(WORK)) == _LISTING)
finally:
    STATUS.probe_ssh = _STATUS_PROBE_SAVED
    DOCTOR.diagnose_reachability = _DOCTOR_SAVED
check("§7 no file transfer in the base release (`put` / `get` are a follow-up slot)",
      set(VERBS) == {"inventory", "connections", "status", "doctor", "exec", "hostkey", "import"})
check("§7 no interactive prompt of any kind: `cli/` never reads stdin, an env var or argv for a secret",
      not [name for name, _file, source in _SOURCES if "input(" in source or "getpass" in source],
      [name for name, _file, source in _SOURCES if "input(" in source or "getpass" in source])
check("§7 no i18n: `cli/` imports no `i18n` and adds no translation key",
      not any("i18n" in imports for imports in _IMPORTERS.values())
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})


# ════════════════════════════════════════════════════════════════════════════
print("== §8 the configuration it READS (and never writes) ==")
# ════════════════════════════════════════════════════════════════════════════

_DANGEROUS_NAMES = ("save_config", "save_password", "delete_password", "save_profiles",
                    "write_json_atomic", "save_project")
_WRITERS = {name: sorted(symbol for symbol in imports if symbol.split(".")[-1] in _DANGEROUS_NAMES)
            for name, imports in _IMPORTERS.items()}
check("§8 READ-ONLY: no module of `cli/` imports a writer of the config, the keyring or a project",
      not [name for name, hits in _WRITERS.items() if hits]
      and not any("os.replace(" in source or "os.remove(" in source for _n, _f, source in _SOURCES),
      str({k: v for k, v in _WRITERS.items() if v}))
_REPLACE_CALLS = sum(source.count("store.replace(") for _name, _file, source in _SOURCES)
check("§8 ...the ONE write is the host-key pin, through `KnownHostsStore.replace()`",
      _REPLACE_CALLS == 1, str(_REPLACE_CALLS))
check("§8 ...and the clause names BOTH opt-ins of that ONE write (`--accept-new`, `--host-key`)",
      "--accept-new` pins a NEW host key" in CONTRACT
      and "--host-key <fingerprint>` pins the key it names" in CONTRACT)
check("§8 the config key it reads is the remembered project (`last_project_path`), never a policy",
      "last_project_path" in read(os.path.join(CLI_DIR, "project.py"))
      and "guard_commands" not in "".join(source for _n, _f, source in _SOURCES))
check("§8 `config.json` is never CREATED by a run (the declared default of its reader is the answer)",
      not os.path.exists(APP_CONFIG.CONFIG_FILE))
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "uptime", "--dry-run"])
check("§8 the project file is never written, not even when a verb reports on it",
      _CODE == EX.EXIT_OK and open(MAP, "rb").read() == _BEFORE)
check("§8 `VERSION_FORMAT` is untouched by the surface (`0.9`), and the envelope has its own schema",
      version.VERSION_FORMAT == "0.9" and ENV.SCHEMA_VERSION == 1)


# ════════════════════════════════════════════════════════════════════════════
print("== §9 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check(f"§9 this release is v{EXPECTED_APP_VERSION} (the base of the 1.15 line or a later one)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15")
      and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§9 the base adds NO i18n key — the CLI speaks English (parity stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1256
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
_REQUIREMENTS = [line for line in read(os.path.join(ROOT, "requirements.txt")).splitlines()
                 if line.strip() and not line.strip().startswith("#")]
check("§9 no new dependency: the surface imports the standard library and the shipped pins only",
      len(_REQUIREMENTS) == 4, str(_REQUIREMENTS))

finish()
