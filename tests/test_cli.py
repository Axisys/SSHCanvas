# -*- coding: utf-8 -*-
"""v1.15rc2 — the HEADLESS SURFACE: the frozen `CLI.md`, the `cli/` skeleton and the two report verbs.
§1 the contract is frozen, complete and registered in both directions; §2 the Qt-FREE gate — every module
of `cli/` (and the pure layers it reads) imports in a fresh process without PySide6; §3 the option table,
the argv parse and the seven exit codes; §4 the `--json` envelope; §5 the dispatch and the two streams;
§6 the release state; §7 `inventory`/`connections` over SYNTHETIC projects, the `--json` schema PINNED.
Rule — `AGENTS.md` §4.35; contract — `CLI.md`; mechanism — `DOCUMENTATION.md` §80.
Run: python tests/test_cli.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least,
                     translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + sys.path (BEFORE any app import)

import cli.args as ARGS  # noqa: E402
import cli.dispatch as DISPATCH  # noqa: E402
import cli.envelope as ENV  # noqa: E402
import cli.errors as ERR  # noqa: E402
import cli.exit_codes as EX  # noqa: E402
import cli.output as OUT  # noqa: E402
import cli.report as REPORT  # noqa: E402
import cli.verb_args as VERB_ARGS  # noqa: E402
import storage.app_config as APP_CONFIG  # noqa: E402
import storage.export_connections as ECON  # noqa: E402
import storage.export_inventory as EINV  # noqa: E402
import storage.table_text as TABLE_TEXT  # noqa: E402
import version  # noqa: E402
from cli.main import main  # noqa: E402

CLI_MD = os.path.join(ROOT, "CLI.md")
AGENTS_MD = os.path.join(ROOT, "AGENTS.md")
GITIGNORE = os.path.join(ROOT, ".gitignore")
CLI_DIR = os.path.join(ROOT, "cli")
LANGS = load_i18n_langs(ROOT)


def read(path):
    """The text of one repository file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def imports_qt(source):
    """Does this source IMPORT PySide6? (a docstring may name the rule, an import breaks it)."""
    return any(line.lstrip().startswith(("import PySide6", "from PySide6"))
               for line in str(source or "").splitlines())


def module_files():
    """`(module name, file name)` of every module of `cli/` — the gate's own scan, no import."""
    out = []
    for name in sorted(os.listdir(CLI_DIR)):
        if name.endswith(".py"):
            stem = name[:-3]
            out.append(("cli" if stem == "__init__" else f"cli.{stem}", name))
    return out


def qt_free_verdict(module, snippet=""):
    """`("PySide6" in sys.modules)` after importing `module` (+ `snippet`) in a FRESH process.

    `None` — the probe itself failed, and the detail says why. One process per module on purpose: a
    module that loads Qt would otherwise be MASKED by a neighbour that already loaded it.
    """
    code = (f"import importlib\nimportlib.import_module({module!r})\n{snippet}"
            f"import sys\nprint('PySide6' in sys.modules)\n")
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                          timeout=180, env=dict(os.environ, PYTHONPATH=ROOT))
    if done.returncode != 0:
        return None, (done.stderr or "").strip()[-300:]
    return done.stdout.strip() == "True", ""


def run(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout text, stderr text)`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def cost(argv):
    """The `CliError` ONE command line costs (`None` — it parsed cleanly)."""
    try:
        ARGS.parse_argv(list(argv))
    except ERR.CliError as exc:
        return exc
    return None


def forget(name):
    """Drop a row the registry accepted — the bookkeeping side of `registered()`."""
    DISPATCH.VERBS.pop(name, None)
    order = getattr(DISPATCH, "_REGISTERED_ORDER", [])
    if name in order:
        order.remove(name)


@contextlib.contextmanager
def registered(verb):
    """Register ONE verb for the length of a block, then take the row back out of the table."""
    DISPATCH.register(verb)
    try:
        yield verb
    finally:
        forget(verb.name)


def raises_value_error(callable_):
    """Does this call raise `ValueError`? (the registry's own refusal of a bad row)."""
    try:
        callable_()
    except ValueError:
        return True
    return False


def raise_refusal():
    """A handler that refuses — the declared failure a verb raises instead of printing."""
    raise ERR.refusal("the command guard refused the command", "run with --allow-destructive")


# ════════════════════════════════════════════════════════════════════════════
# §1 The frozen contract
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the frozen contract `CLI.md` ==")

CONTRACT = read(CLI_MD)
CHAPTERS = ("## 1. Naming and entry points", "## 2. The command line", "## 3. The verbs",
            "## 4. The `--json` envelope", "## 5. The three security policies",
            "## 6. The Qt-free rule and its gate", "## 7. What the CLI does NOT do",
            "## 8. The configuration it READS (and never writes)")
_AGENTS = read(AGENTS_MD)

check("§1 `CLI.md` is the contract of the line (its status block says frozen and forbids a change)",
      CONTRACT.startswith("# CLI.md — the headless surface") and "**frozen contract**" in CONTRACT
      and "the versions implement this contract, they do not" in CONTRACT,
      CONTRACT.splitlines()[0])
check("§1 the contract carries its EIGHT chapters, in order, and no ninth",
      [line for line in CONTRACT.splitlines() if line.startswith("## ")] == list(CHAPTERS),
      [line for line in CONTRACT.splitlines() if line.startswith("## ")])
check("§1 the naming chapter declares BOTH console scripts and leaves the GUI pair alone",
      all(token in CONTRACT for token in
          ("`sshcanvas-cli`", "`sshmap-cli`", "`sshcanvas`, `sshmap`", "cli.main:main")))
check("§1 the option table of the contract is the code's OWN table (never a second list)",
      all(name in CONTRACT for name, _takes, _meta in ARGS.OPTIONS),
      [name for name, _takes, _meta in ARGS.OPTIONS if name not in CONTRACT])
check("§1 the contract names the seven exit codes and their machine kinds",
      all(f"`{code}`" in CONTRACT for code in EX.EXIT_CODES)
      and all(kind in CONTRACT for kind in EX.EXIT_NAMES.values()),
      [kind for kind in EX.EXIT_NAMES.values() if kind not in CONTRACT])
check("§1 the contract declares the envelope's FIVE keys, in the code's own names",
      all(f"`{key}`" in CONTRACT for key in ENV.ENVELOPE_KEYS),
      [key for key in ENV.ENVELOPE_KEYS if f"`{key}`" not in CONTRACT])
check("§1 the three policies are declared (keyring-only, refuse-unless-pinned, the guard ASKED)",
      all(token in CONTRACT for token in ("`--identity PATH`", "`--accept-new`",
                                          "`--host-key <fingerprint>`", "`--allow-destructive`",
                                          "`--dry-run`")))
check("§1 the Qt-free rule points a reader at THIS gate",
      "tests/test_cli.py" in CONTRACT and "§2" in CONTRACT)
check("§1 the contract says what the surface does NOT do",
      "No listener" in CONTRACT and "No map mutation" in CONTRACT and "No GUI control" in CONTRACT
      and "No i18n" in CONTRACT)
check("§1 the contract names the configuration it reads and calls it READ-ONLY",
      all(token in CONTRACT for token in ("`~/.sshmap/config.json`", "known_hosts", "keyring"))
      and "READ-ONLY, without exception" in CONTRACT)
check("§1 `CLI.md` is REGISTERED in `.gitignore` (an internal contract is never published)",
      "CLI.md" in read(GITIGNORE))
_S13 = _AGENTS[_AGENTS.find("The internal, gitignored documents"):]
check("§1 AGENTS.md §13.1 names `CLI.md` among the internal documents",
      "`CLI.md`" in _S13[:_S13.find("— are never linked")], "the §13.1 list does not carry CLI.md")
check("§1 AGENTS.md §10 points at the contract (the table an agent reads first)",
      "CLI.md" in _AGENTS[_AGENTS.find("## 10. Where to read deeper"):][:2500],
      "the §10 table does not name CLI.md")
check("§1 the closed world holds in BOTH directions (tree ↔ .gitignore ↔ §13.1)",
      os.path.isfile(CLI_MD) and "CLI.md" in read(GITIGNORE) and "`CLI.md`" in _S13)


# ════════════════════════════════════════════════════════════════════════════
# §2 The Qt-free gate
# ════════════════════════════════════════════════════════════════════════════
print("== §2 the Qt-free gate (a fresh process per module) ==")

_FILES = module_files()
_MODULES = [name for name, _file in _FILES]
PURE_LAYERS = ("services.reachability", "services.status_probe", "modules.terminal_config",
               "modules.sftp_search", "modules.sftp_limits", "storage.table_text",
               "storage.export_problems", "storage.export_connections", "storage.export_inventory",
               "storage.project", "storage.project_recent", "storage.app_config",
               "modules.command_guard")

_LOADED_QT, _PROBE_ERRORS = [], []
for _module in _MODULES:
    _verdict, _detail = qt_free_verdict(_module)
    if _verdict is None:
        _PROBE_ERRORS.append(f"{_module}: {_detail}")
    elif _verdict:
        _LOADED_QT.append(_module)
check("§2 the gate really scans the package (a guard over nothing is useless)",
      len(_MODULES) >= 8 and _MODULES[0] == "cli", str(_MODULES))
check("§2 the probe itself runs (a broken subprocess is not a green gate)", not _PROBE_ERRORS,
      _PROBE_ERRORS[:2])
check("§2 importing EVERY module of `cli/` leaves PySide6 out of `sys.modules`",
      not _LOADED_QT, f"these modules load Qt: {_LOADED_QT}")
check("§2 ...and no module of `cli/` even IMPORTS PySide6 (the gate has no hole)",
      not [name for name, file in _FILES if imports_qt(read(os.path.join(CLI_DIR, file)))],
      [name for name, file in _FILES if imports_qt(read(os.path.join(CLI_DIR, file)))])

_PURE_QT, _PURE_ERRORS = [], []
for _layer in PURE_LAYERS:
    _verdict, _detail = qt_free_verdict(_layer)
    if _verdict is None:
        _PURE_ERRORS.append(f"{_layer}: {_detail}")
    elif _verdict:
        _PURE_QT.append(_layer)
check("§2 the pure layers a headless surface reads import without PySide6 (`N169`-`N172` turned)",
      not _PURE_QT and not _PURE_ERRORS, f"load Qt: {_PURE_QT} / errors: {_PURE_ERRORS[:2]}")

_CALL_VERDICT, _CALL_DETAIL = qt_free_verdict(
    "storage.export_connections",
    "import storage.export_connections as EC\n"
    "import storage.export_problems as EP\n"
    "EC.connection_report_text([], translate=lambda key, **kw: key)\n"
    "EP.problem_report_text([], translate=lambda key, **kw: key)\n")
check("§2 a report's TEXT form needs no Qt either — the CALL is as clean as the import (`N172`)",
      _CALL_VERDICT is False, f"verdict={_CALL_VERDICT} {_CALL_DETAIL}")

_GUARD_VERDICT, _GUARD_DETAIL = qt_free_verdict(
    "modules.command_guard",
    "import modules.command_guard as G\n"
    "assert G.needs_confirmation('rm -rf /') == 'rm -rf'\n")
check("§2 the command guard ANSWERS a process with no Qt (its dialog import is lazy)",
      _GUARD_VERDICT is False, f"verdict={_GUARD_VERDICT} {_GUARD_DETAIL}")

_TERM_VERDICT, _TERM_DETAIL = qt_free_verdict(
    "modules.terminal_config",
    "import modules.terminal_config as C\n"
    "assert C.CURSOR_STYLES == ('block', 'bar', 'underline') and C.FONT_SIZE_MAX == 72\n")
check("§2 the terminal CONFIG reader owns the cursor/font constants (`N169`)",
      _TERM_VERDICT is False, f"verdict={_TERM_VERDICT} {_TERM_DETAIL}")


# ════════════════════════════════════════════════════════════════════════════
# §3 The option table, the parse and the exit codes
# ════════════════════════════════════════════════════════════════════════════
print("== §3 the command line and the exit-code table ==")

check("§3 the exit-code table is the SEVEN declared codes, mildest first",
      EX.EXIT_CODES == (0, 1, 2, 3, 4, 5, 6), str(EX.EXIT_CODES))
check("§3 every code answers its machine name, and an unknown one answers `unknown`",
      EX.exit_name(0) == "ok" and EX.exit_name(EX.EXIT_TIMEOUT) == "timeout"
      and EX.exit_name(99) == "unknown" and EX.exit_name("x") == "unknown"
      and EX.is_declared(2) and not EX.is_declared(7), str(EX.EXIT_NAMES))
check("§3 the option table declares the five options of the contract, and nothing else",
      {name for name, _takes, _meta in ARGS.OPTIONS} ==
      {ARGS.OPTION_JSON, ARGS.OPTION_PROJECT, ARGS.OPTION_TIMEOUT, ARGS.OPTION_HELP,
       ARGS.OPTION_VERSION}, str([name for name, _t, _m in ARGS.OPTIONS]))
check("§3 a bare command line parses to NO verb and the declared defaults",
      ARGS.parse_argv([]) == ARGS.Invocation(), str(ARGS.parse_argv([])))
check("§3 the verb is the FIRST bare token and everything after it is its argument",
      (lambda inv: (inv.verb, inv.arguments))(ARGS.parse_argv(["inventory", "a", "b"]))
      == ("inventory", ("a", "b")))
check("§3 `--option=value` and `--option value` are the same thing",
      ARGS.parse_argv(["--timeout=5", "status"]).timeout == 5.0
      and ARGS.parse_argv(["--timeout", "5", "status"]).timeout == 5.0)
check("§3 a repeated option takes its LAST value",
      ARGS.parse_argv(["--timeout", "5", "--timeout", "7"]).timeout == 7.0)
check("§3 `--` ends the options and the tokens after it are the verb and its arguments",
      (lambda inv: (inv.verb, inv.arguments, inv.json))(
          ARGS.parse_argv(["--json", "--", "inventory", "--tag"])) == ("inventory", ("--tag",), True))
check("§3 `--json` is the envelope switch and takes NO value",
      ARGS.parse_argv(["--json"]).json is True and cost(["--json=1"]) is not None)
check("§3 the two aliases are the two options (`-h`, `-V`)",
      ARGS.parse_argv(["-h"]).help is True and ARGS.parse_argv(["-V"]).version is True)
check("§3 an undeclared option is a USAGE error, never a silent pass",
      (lambda exc: exc is not None and exc.code == EX.EXIT_USAGE)(cost(["--bogus"]))
      and cost(["-x"]) is not None, str(cost(["--bogus"])))
check("§3 an option that needs a value refuses to be the last token",
      cost(["--project"]) is not None and cost(["--timeout"]) is not None)
check("§3 the timeout is a number inside the DECLARED range",
      ARGS.TIMEOUT_DEFAULT_S == 10.0 and ARGS.TIMEOUT_MIN_S == 1.0 and ARGS.TIMEOUT_MAX_S == 300.0
      and cost(["--timeout", "0"]) is not None and cost(["--timeout", "301"]) is not None
      and cost(["--timeout", "soon"]) is not None
      and ARGS.parse_argv(["--timeout", "300"]).timeout == 300.0)
check("§3 `--project` resolves `~` and makes the path ABSOLUTE (one spelling in the envelope)",
      ARGS.resolve_project_path("~/map.json")
      == os.path.normpath(os.path.join(os.path.expanduser("~"), "map.json"))
      and os.path.isabs(ARGS.resolve_project_path("rel/map.json", base_dir=WORK))
      and ARGS.parse_argv(["--project", "rel/map.json"], base_dir=WORK).project
      == os.path.normpath(os.path.join(WORK, "rel", "map.json"))
      and ARGS.resolve_project_path("") == "" and ARGS.resolve_project_path(None) == "")
check("§3 the parse STOPS at the verb — a later flag belongs to that verb, not to the global table",
      (lambda inv: (inv.verb, inv.arguments, inv.json))(
          ARGS.parse_argv(["inventory", "--tag", "prod", "--json"]))
      == ("inventory", ("--tag", "prod", "--json"), False)
      and ARGS.parse_argv(["--json", "inventory", "--tag", "prod"]).json is True
      and ARGS.parse_argv(["--json", "--", "inventory", "--tag"]).verb == "inventory")
check("§3 a USAGE error carries its code, its kind and its hint",
      (lambda exc: (exc.code, exc.kind, bool(exc.hint), exc.record()["kind"]))(
          cost(["--bogus"])) == (EX.EXIT_USAGE, "usage", True, "usage"))
check("§3 the help text is built from the SAME option table",
      all(name in ARGS.usage_text() for name, _takes, _meta in ARGS.OPTIONS)
      and "usage: sshcanvas-cli" in ARGS.usage_text()
      and "exit codes: 0 ok, 1 usage" in ARGS.usage_text())
check("§3 the help text lists the REGISTRY's verbs, and an empty registry says so",
      ARGS.usage_text([("inventory", "one row per server")]).find("inventory") > 0
      and "(this build declares none)" in ARGS.usage_text())


# ════════════════════════════════════════════════════════════════════════════
# §4 The `--json` envelope
# ════════════════════════════════════════════════════════════════════════════
print("== §4 the `--json` envelope ==")

_OK = ENV.build("inventory", data={"count": 2})
_BAD = ENV.build("inventory", error=ERR.refusal("nope", "pin the key").record())
_TEXT = ENV.dumps(_OK)

check("§4 the envelope has the FIVE keys and no others, in the declared order",
      tuple(_OK) == ENV.ENVELOPE_KEYS and tuple(_BAD) == ENV.ENVELOPE_KEYS, str(tuple(_OK)))
check("§4 a success answers `ok: true`, its data and NO error",
      _OK["ok"] is True and _OK["data"] == {"count": 2} and _OK["error"] is None
      and _OK["verb"] == "inventory" and _OK["schema"] == ENV.SCHEMA_VERSION)
check("§4 a failure answers `ok: false`, NO data and the error record",
      _BAD["ok"] is False and _BAD["data"] is None
      and _BAD["error"] == {"code": EX.EXIT_REFUSAL, "kind": "refusal",
                            "message": "nope", "hint": "pin the key"}, str(_BAD["error"]))
check("§4 the envelope's schema is its OWN version, apart from the project format",
      ENV.SCHEMA_VERSION == 1 and version.VERSION_FORMAT == "0.9")
check("§4 the document parses as JSON and keeps every key",
      (lambda doc: sorted(doc) == sorted(ENV.ENVELOPE_KEYS) and doc["schema"] == 1)(
          json.loads(_TEXT)), _TEXT[:80])
check("§4 a foreign payload degrades instead of raising (a report never loses its shape)",
      isinstance(json.loads(ENV.dumps(ENV.build("x", data={"when": object()}))), dict)
      and "object" in json.loads(ENV.dumps(ENV.build("x", data={"when": object()})))["data"])
check("§4 a `None` payload stays `null` in the document (absent is not empty)",
      json.loads(ENV.dumps(ENV.build("x")))["data"] is None
      and json.loads(ENV.dumps(ENV.build("x", data={})))["data"] == {})


# ════════════════════════════════════════════════════════════════════════════
# §5 The dispatch, the entry points and the two streams
# ════════════════════════════════════════════════════════════════════════════
print("== §5 the dispatch and the entry points ==")

check("§5 the registry answers the help rows from ONE table",
      DISPATCH.registered() == [(name, DISPATCH.VERBS[name].summary)
                                for name in sorted(DISPATCH.VERBS)], str(DISPATCH.registered()))
DISPATCH.register(DISPATCH.Verb("dup-verb", "the duplicate probe", handler=lambda c, a: {}))
_DUPLICATE_REFUSED = raises_value_error(
    lambda: DISPATCH.register(DISPATCH.Verb("dup-verb", "again", handler=lambda c, a: {})))
_NO_HANDLER_REFUSED = raises_value_error(lambda: DISPATCH.register(DISPATCH.Verb("no-handler", "s")))
forget("dup-verb")
check("§5 `register()` refuses a duplicate name and a row without a handler",
      _DUPLICATE_REFUSED and _NO_HANDLER_REFUSED,
      f"duplicate={_DUPLICATE_REFUSED} no_handler={_NO_HANDLER_REFUSED}")

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--version"])
check("§5 `--version` exits 0 and names the SHIPPED release on stdout",
      _CODE == EX.EXIT_OK and _OUT_TEXT.strip() == f"{version.APP_NAME} {version.APP_VERSION}"
      and _ERR_TEXT == "", f"{_CODE} / {_OUT_TEXT!r} / {_ERR_TEXT!r}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--version"])
_VER_DOC = json.loads(_OUT_TEXT) if _OUT_TEXT.strip().startswith("{") else {}
check("§5 `--json --version` prints ONE envelope whose data is the version pair",
      _CODE == EX.EXIT_OK and _VER_DOC.get("ok") is True and _VER_DOC.get("error") is None
      and _VER_DOC.get("data") == {"name": version.APP_NAME, "version": version.APP_VERSION}
      and _OUT_TEXT.strip().count("\n}") == 1, _OUT_TEXT[:120])
_CODE, _OUT_TEXT, _ERR_TEXT = run([])
check("§5 a command line with no verb is a USAGE answer on stderr, exit 1",
      _CODE == EX.EXIT_USAGE and "no verb given" in _ERR_TEXT and _OUT_TEXT == "",
      f"{_CODE} / {_ERR_TEXT!r}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json"])
_NO_VERB = json.loads(_OUT_TEXT or "{}")
check("§5 ...and under `--json` the same answer is ONE envelope with a `usage` record, stderr empty",
      _CODE == EX.EXIT_USAGE and _NO_VERB.get("error", {}).get("kind") == "usage"
      and _NO_VERB.get("data") is None and _ERR_TEXT == "", f"{_CODE} / {_OUT_TEXT[:100]!r}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["nosuchverb"])
check("§5 an unknown verb is a USAGE answer that NAMES the verb",
      _CODE == EX.EXIT_USAGE and "nosuchverb" in _ERR_TEXT, f"{_CODE} / {_ERR_TEXT!r}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--help"])
check("§5 `--help` exits 0 and prints the usage text",
      _CODE == EX.EXIT_OK and _OUT_TEXT.startswith("usage: sshcanvas-cli")
      and "options:" in _OUT_TEXT and "verbs:" in _OUT_TEXT, _OUT_TEXT[:60])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--help"])
check("§5 `--help` writes TEXT even under `--json` (a human asked for it)",
      _CODE == EX.EXIT_OK and _OUT_TEXT.startswith("usage:")
      and not _OUT_TEXT.lstrip().startswith("{"))
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--bogus"])
_PARSE_DOC = json.loads(_OUT_TEXT or "{}")
check("§5 a PARSE failure under `--json` still answers an envelope (one shape, always)",
      _CODE == EX.EXIT_USAGE and _PARSE_DOC.get("error", {}).get("kind") == "usage"
      and _PARSE_DOC.get("verb") == "", f"{_CODE} / {_OUT_TEXT[:120]!r}")

with registered(DISPATCH.Verb("sample-verb", "the sample of the seam", min_args=0, max_args=1,
                              handler=lambda context, arguments: {
                                  "echo": list(arguments), "timeout": context.timeout},
                              render=lambda context, data: [f"echo={','.join(data['echo'])}"])):
    _CODE, _OUT_TEXT, _ERR_TEXT = run(["--timeout", "42", "sample-verb", "hello"])
    check("§5 a verb registered through the seam RUNS: its renderer's lines reach stdout, exit 0",
          _CODE == EX.EXIT_OK and _OUT_TEXT.strip() == "echo=hello" and _ERR_TEXT == "",
          f"{_CODE} / {_OUT_TEXT!r}")
    _CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--timeout", "42", "sample-verb", "hello"])
    _VERB_DOC = json.loads(_OUT_TEXT or "{}")
    check("§5 ...and in `--json` mode its DATA reaches the envelope's `data`",
          _CODE == EX.EXIT_OK and _VERB_DOC.get("data") == {"echo": ["hello"], "timeout": 42.0}
          and _VERB_DOC.get("verb") == "sample-verb", _OUT_TEXT[:120])
    _CODE, _OUT_TEXT, _ERR_TEXT = run(["sample-verb", "one", "two"])
    check("§5 an argument count the row does not declare is a USAGE error before the handler runs",
          _CODE == EX.EXIT_USAGE and "sample-verb takes 0..1" in _ERR_TEXT, _ERR_TEXT[:80])

with registered(DISPATCH.Verb("refusing-verb", "always refuses",
                              handler=lambda context, arguments: raise_refusal())):
    _CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "refusing-verb"])
    _REF_DOC = json.loads(_OUT_TEXT or "{}")
    check("§5 a handler's `CliError` answers ITS code, and its record carries the kind",
          _CODE == EX.EXIT_REFUSAL and _REF_DOC.get("error", {}).get("kind") == "refusal"
          and "guard" in _REF_DOC.get("error", {}).get("message", ""), _OUT_TEXT[:140])

with registered(DISPATCH.Verb("crashing-verb", "raises",
                              handler=lambda context, arguments: 1 / 0)):
    _CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "crashing-verb"])
    _CRASH_DOC = json.loads(_OUT_TEXT or "{}")
    check("§5 a handler that raises is an `internal error`, never a traceback on stdout",
          _CODE == EX.EXIT_USAGE
          and _CRASH_DOC.get("error", {}).get("message", "")
          .startswith("internal error: ZeroDivisionError"), _OUT_TEXT[:140])

_PYPROJECT = read(os.path.join(ROOT, "pyproject.toml"))
check("§5 the console scripts are declared in pyproject.toml and point at `cli.main:main`",
      'sshcanvas-cli = "cli.main:main"' in _PYPROJECT and 'sshmap-cli = "cli.main:main"' in _PYPROJECT,
      [line for line in _PYPROJECT.splitlines() if "-cli" in line])
check("§5 `cli` is in the explicit package list (the surface ships with the wheel)",
      any(line.strip() == '"cli",' for line in _PYPROJECT.splitlines()),
      [line for line in _PYPROJECT.splitlines() if "cli" in line])
check("§5 the GUI entries are untouched (the CLI is a SECOND entry point)",
      'sshcanvas = "main:main"' in _PYPROJECT and 'sshmap = "main:main"' in _PYPROJECT)
check("§5 the writer answers an int and never calls sys.exit (a launcher keeps the code)",
      isinstance(run(["--version"])[0], int))


# ════════════════════════════════════════════════════════════════════════════
# §6 The release state
# ════════════════════════════════════════════════════════════════════════════
print("== §6 the release state ==")

check_release_state(ROOT)
check(f"§6 this release is v{EXPECTED_APP_VERSION} (the line's base release or a later one)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15")
      and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§6 the milestone adds NO i18n key (the parity pin stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1205
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
check("§6 no new dependency: requirements.txt keeps its four pins",
      len([line for line in read(os.path.join(ROOT, "requirements.txt")).splitlines()
           if line.strip() and not line.strip().startswith("#")]) == 4,
      read(os.path.join(ROOT, "requirements.txt")).splitlines()[:4])
check("§6 the contract's own schema figure is the code's (`schema: 1`)",
      ENV.SCHEMA_VERSION == 1 and "| `schema` | int |" in CONTRACT)


# ════════════════════════════════════════════════════════════════════════════
# §7 `inventory` and `connections` over SYNTHETIC projects (the pinned `--json` schema)
# ════════════════════════════════════════════════════════════════════════════
print("== §7 `inventory` and `connections` over SYNTHETIC projects ==")

FIXTURES = os.path.join(WORK, "projects")
os.makedirs(FIXTURES, exist_ok=True)

INVENTORY_IDS = ["alias", "host", "port", "user", "status", "status_age", "os", "cpu", "ram",
                 "disk", "info_age", "comment", "tags"]
CONNECTION_IDS = ["source_alias", "source_host", "target_alias", "target_host", "type",
                  "direction", "bidirectional", "label"]

WEB = {"id": "srv-web", "alias": "web-1", "host": "192.0.2.10", "ip": "192.0.2.10",
       "ssh_port": 22, "user": "deploy", "comment": 'edge, "quoted"', "os_name": "Ubuntu 24.04 LTS",
       "ram": "8 GB", "disk": "512 GB", "tags": ["prod", "web"]}
DB = {"id": "srv-db", "alias": "db-1", "host": "198.51.100.20", "ssh_port": 2222,
      "user": "postgres", "tags": ["prod"]}
LINK = {"source_id": "srv-web", "target_id": "srv-db", "label": "api", "type": "database",
        "bidirectional": True}


def fixture(name, servers=(), connections=(), **extra):
    """Write ONE SYNTHETIC project into the isolated work folder — never a real map file."""
    payload = {"version": version.VERSION_FORMAT, "servers": list(servers),
               "connections": list(connections), "notes": [], "groups": [], "background": None}
    payload.update(extra)
    path = os.path.join(FIXTURES, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def document(text):
    """The ONE `--json` document of a run (a second document on stdout is a defect)."""
    stripped = str(text or "").strip()
    return json.loads(stripped) if stripped.startswith("{") else {}


def cells(document_, key="rows"):
    """ONE field of a document's `data` payload (`None` — the run answered an error instead)."""
    return (document_.get("data") or {}).get(key)


MAP = fixture("map.json", [WEB, DB], [LINK])
NO_LINKS = fixture("no-links.json", [WEB, DB])
LABEL = fixture("label.json", [{"id": "srv-x", "alias": "=cmd|calc", "host": "203.0.113.5",
                               "ssh_port": 22, "user": "root", "tags": []}])
BROKEN = os.path.join(FIXTURES, "broken.json")
with open(BROKEN, "w", encoding="utf-8") as handle:
    handle.write("{ not json")

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", MAP, "inventory"])
_INV = document(_OUT_TEXT)
_DATA = _INV.get("data") or {}
check("§7 `inventory --json` answers ONE envelope: ok, the verb, a `data` payload and no error",
      _CODE == EX.EXIT_OK and tuple(_INV) == ENV.ENVELOPE_KEYS and _INV.get("ok") is True
      and _INV.get("error") is None and _INV.get("verb") == "inventory" and _ERR_TEXT == "",
      f"{_CODE} / {_OUT_TEXT[:120]!r} / {_ERR_TEXT!r}")
check("§7 ...whose `data` is the PINNED schema — project, count, columns, rows and no other key",
      tuple(_DATA) == REPORT.DATA_KEYS == ("project", "count", "columns", "rows"),
      str(tuple(_DATA)))
check("§7 the columns are the INVENTORY report's own ids, in the report's order",
      _DATA.get("columns") == INVENTORY_IDS == EINV.inventory_column_ids(),
      str(_DATA.get("columns")))
check("§7 the count is the row count and the project is the path that was read",
      _DATA.get("count") == 2 and _DATA.get("project") == MAP,
      f"{_DATA.get('count')} / {_DATA.get('project')}")
check("§7 the cells are the shipped schema's: port, user, OS, sizes, the comma-carrying comment, tags",
      _DATA.get("rows", [[]])[0] == ["web-1", "192.0.2.10", "22", "deploy", "", "",
                                     "Ubuntu 24.04 LTS", "", "8 GB", "512 GB", "",
                                     'edge, "quoted"', "prod, web"],
      str(_DATA.get("rows", [[]])[0]))
check("§7 ...and an ABSENT field is an EMPTY cell, never the string \"None\"",
      _DATA.get("rows", [[], []])[1] == ["db-1", "198.51.100.20", "2222", "postgres", "", "", "",
                                         "", "", "", "", "", "prod"],
      str(_DATA.get("rows", [[], []])[1]))

_CODE, _OUT_TEXT, _ = run(["--json", "--project", MAP, "inventory", "--tag", "prod"])
_TAGGED = document(_OUT_TEXT)
_CODE2, _OUT_TEXT2, _ = run(["--json", "--project", MAP, "inventory", "--tag", "prod", "--tag", "web"])
_NARROW = document(_OUT_TEXT2)
_CODE3, _OUT_TEXT3, _ = run(["--json", "--project", MAP, "inventory", "--tag", "staging"])
check("§7 `--tag` narrows the rows and REPEATS as an AND (every named tag must match)",
      _CODE == EX.EXIT_OK and cells(_TAGGED, "count") == 2
      and cells(_NARROW, "count") == 1 and cells(_NARROW)[0][0] == "web-1"
      and _CODE2 == EX.EXIT_OK, f"{cells(_TAGGED, 'count')} / {cells(_NARROW)}")
check("§7 ...and a tag nothing carries is an EMPTY table, exit 0 (a filter is not a failure)",
      _CODE3 == EX.EXIT_OK and cells(document(_OUT_TEXT3), "count") == 0, f"{_CODE3}")

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--project", MAP, "inventory"])
_EXPECTED_TEXT = TABLE_TEXT.list_table_text([INVENTORY_IDS] + _DATA["rows"],
                                            TABLE_TEXT.list_delimiter("csv"))
check("§7 the TEXT form is the shipped RFC-4180 writer — the column ids as the header, CRLF rows",
      _CODE == EX.EXIT_OK and _ERR_TEXT == "" and _OUT_TEXT == _EXPECTED_TEXT
      and _OUT_TEXT.startswith(",".join(INVENTORY_IDS) + "\r\n")
      and _OUT_TEXT.count("\r\n") == 3, repr(_OUT_TEXT[:100]))
check("§7 ...the comma-carrying cells are QUOTED and a quote is doubled (the GUI's own writer)",
      '"edge, ""quoted"""' in _OUT_TEXT and '"prod, web"' in _OUT_TEXT, repr(_OUT_TEXT))
_CODE, _OUT_TEXT, _ = run(["--project", MAP, "inventory", "--format", "tsv"])
check("§7 `--format tsv` writes the SAME rows with tabs",
      _CODE == EX.EXIT_OK and _OUT_TEXT == TABLE_TEXT.list_table_text(
          [INVENTORY_IDS] + _DATA["rows"], TABLE_TEXT.list_delimiter("tsv")), repr(_OUT_TEXT[:60]))
_CODE, _OUT_TEXT, _ = run(["--project", LABEL, "inventory"])
check("§7 a formula cell is neutralised by the ONE writer (a report is DATA, never a program)",
      _CODE == EX.EXIT_OK and "'=cmd|calc" in _OUT_TEXT, repr(_OUT_TEXT))

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", MAP, "connections"])
_LINKS = document(_OUT_TEXT)
_LINK_DATA = _LINKS.get("data") or {}
check("§7 `connections --json` answers the SAME pinned schema over the CONNECTION columns",
      _CODE == EX.EXIT_OK and tuple(_LINKS) == ENV.ENVELOPE_KEYS and _LINKS.get("ok") is True
      and tuple(_LINK_DATA) == REPORT.DATA_KEYS
      and _LINK_DATA.get("columns") == CONNECTION_IDS == ECON.connection_column_ids()
      and _LINK_DATA.get("count") == 1 and _LINK_DATA.get("project") == MAP,
      _OUT_TEXT[:120])
check("§7 the row resolves BOTH endpoints, the type, the direction text, the flag and the label",
      _LINK_DATA.get("rows") == [["web-1", "192.0.2.10", "db-1", "198.51.100.20", "database",
                                  "web-1 \u2192 db-1", "true", "api"]],
      str(_LINK_DATA.get("rows")))
_CODE, _OUT_TEXT, _ = run(["--json", "--project", NO_LINKS, "connections"])
_EMPTY = document(_OUT_TEXT).get("data") or {}
_CODE2, _OUT_TEXT2, _ = run(["--project", NO_LINKS, "connections"])
check("§7 a project with no link answers an EMPTY table and exit 0 (nothing is broken)",
      _CODE == EX.EXIT_OK and _EMPTY.get("count") == 0 and _EMPTY.get("rows") == []
      and _EMPTY.get("columns") == CONNECTION_IDS, _OUT_TEXT[:100])
check("§7 ...and its TEXT form is the header row alone",
      _CODE2 == EX.EXIT_OK and _OUT_TEXT2 == ",".join(CONNECTION_IDS) + "\r\n", repr(_OUT_TEXT2))

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "inventory"])
check("§7 no `--project` and nothing remembered is `not_found` (5), never a silent empty report",
      _CODE == EX.EXIT_NOT_FOUND
      and document(_OUT_TEXT).get("error", {}).get("kind") == "not_found",
      f"{_CODE} / {_OUT_TEXT[:100]!r}")
APP_CONFIG.save_config({"last_project_path": MAP})
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "inventory"])
check("§7 ...while the DEFAULT project is the last one the GUI opened (the config key, read-only)",
      _CODE == EX.EXIT_OK and cells(document(_OUT_TEXT), "project") == MAP,
      f"{_CODE} / {_OUT_TEXT[:100]!r}")
try:
    os.remove(APP_CONFIG.CONFIG_FILE)
except OSError:
    pass

_GONE = os.path.join(FIXTURES, "gone.json")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", _GONE, "inventory"])
check("§7 a `--project` that is not there answers 5 and NAMES the path",
      _CODE == EX.EXIT_NOT_FOUND
      and _GONE in document(_OUT_TEXT).get("error", {}).get("message", ""), _OUT_TEXT[:120])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", BROKEN, "inventory"])
check("§7 a project that does not parse is a USAGE failure (never an empty report)",
      _CODE == EX.EXIT_USAGE
      and document(_OUT_TEXT).get("error", {}).get("kind") == "usage", _OUT_TEXT[:120])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--project", MAP, "inventory", "--format", "xml"])
check("§7 an undeclared `--format` is a USAGE error", _CODE == EX.EXIT_USAGE
      and "--format" in _ERR_TEXT, _ERR_TEXT[:80])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--project", MAP, "inventory", "--bogus"])
check("§7 an undeclared verb FLAG is a USAGE error too (the verb's table refuses it)",
      _CODE == EX.EXIT_USAGE and "--bogus" in _ERR_TEXT, _ERR_TEXT[:80])

_BEFORE = open(MAP, "rb").read()
_LISTING = sorted(os.listdir(FIXTURES))
for _argv in (["--project", MAP, "inventory"], ["--project", MAP, "connections"],
              ["--json", "--project", MAP, "inventory"]):
    run(_argv)
check("§7 a report NEVER writes its project (the bytes and the folder are unchanged)",
      open(MAP, "rb").read() == _BEFORE and sorted(os.listdir(FIXTURES)) == _LISTING)
check("§7 the fixtures are SYNTHETIC — every one of them lives under the isolated work folder",
      all(str(path).startswith(WORK) for path in (MAP, LABEL, NO_LINKS, BROKEN))
      and not any(name.startswith("server_map") for name in os.listdir(FIXTURES)))
check("§7 no module of `cli/` names a REAL map file (the surface reads what it is given)",
      not [name for name, file in _FILES
           if "server_map" in read(os.path.join(CLI_DIR, file))],
      [name for name, file in _FILES if "server_map" in read(os.path.join(CLI_DIR, file))])

_ROWS = dict(DISPATCH.registered())
check("§7 the registry answers BOTH table verbs (the lazy load fills the table on the first question)",
      {"inventory", "connections"} <= set(_ROWS)
      and "--format" in _ROWS.get("inventory", "") and "--tag" in _ROWS.get("inventory", ""),
      str(sorted(_ROWS)))
check("§7 the argument table covers exactly the two table verbs; the probe verbs are POSITIONAL",
      set(VERB_ARGS.ARGUMENT_TABLE) == {"inventory", "connections"}
      and VERB_ARGS.ARGUMENT_TABLE["connections"] == (VERB_ARGS.FORMAT_OPTION,)
      and VERB_ARGS.ARGUMENT_TABLE["inventory"] == (VERB_ARGS.TAG_OPTION,
                                                    VERB_ARGS.FORMAT_OPTION)
      and VERB_ARGS.POSITIONAL_VERBS == ("status", "doctor")
      and VERB_ARGS.TABLE_FORMATS == ("csv", "tsv"), str(VERB_ARGS.ARGUMENT_TABLE))

finish()
