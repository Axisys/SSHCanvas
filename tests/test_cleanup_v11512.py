# -*- coding: utf-8 -*-
"""v1.15.1.2 — the cleanup of v1.15.1.1: ONE logging door, two texts and ONE harness silence.
§1 `modules/logger.optional_logger()` — the ONE predicate, and the nineteen doors that keep no shim;
§2 `StatusChecker.stop()` — the invariant and the pointer, the arithmetic in the code alone;
§3 the harness installs the headless surface's own paramiko silence, ONCE (`tests/_common.bootstrap`);
§4 the release state.
Rule — `AGENTS.md` §12.2, §8.1; mechanism — `DOCUMENTATION.md` §18, §19.
Run: python tests/test_cleanup_v11512.py
"""
import ast
import logging
import os
import re

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text,
                     check, check_i18n_parity, check_release_state, finish, load_i18n_langs,
                     rep_doc_text, releases_at_least, translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + sys.path + the SHIPPED paramiko silence (BEFORE any app import)

import cli.exec as EXEC  # noqa: E402
import models.profile as PROFILE  # noqa: E402
import modules.logger as LOGGER  # noqa: E402
import services.exit_gate as GATE  # noqa: E402
import storage.atomic as ATOMIC  # noqa: E402
import version  # noqa: E402

LANGS = load_i18n_langs(ROOT)
_TREE = logging.getLogger("sshmap")
_ROOT = logging.getLogger()

#: The application tree the `def _log(` sweep reads (the same set as `tests/test_code_pointers.py`).
APP_TREES = ("main.py", "version.py", "models", "graphics", "modules", "storage", "services",
             "dialogs", "ui", "i18n")
_SKIP_DIRS = {"__pycache__", "_tmp_testdata"}


def _source(*parts) -> str:
    """The text of one repository file (the source scans read the shipped tree)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def _app_sources() -> list:
    """Every Python source of the application tree, repository-relative and sorted."""
    out = []
    for tree in APP_TREES:
        path = os.path.join(ROOT, tree)
        if os.path.isfile(path):
            out.append(tree)
            continue
        for base, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
            for name in sorted(names):
                if name.endswith(".py"):
                    out.append(os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/"))
    return sorted(out)


def _method_docstring(source: str, class_name: str, method: str) -> str:
    """The docstring ONE method really carries (AST — no regex over the indented text)."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method:
                    return ast.get_docstring(item, clean=False) or ""
    return ""


class _Sink(logging.Handler):
    """The ONE record sink: what a logger really emitted, at the level the file log gets."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class _DeadDoor:
    """A thread whose stop door raises — the gate must name it and keep walking."""

    def stop(self):
        raise ValueError("the door died")


class _IgnoringThread:
    """A thread that ignored its own door — the ONE warning the last resort writes."""

    def objectName(self):
        return "cleanup-probe"

    def isRunning(self):
        return True

    def terminate(self):
        pass

    def wait(self, _ms=None):
        return True


class _BadClose:
    """A channel whose close() raises — the state a dropped transport leaves."""

    def close(self):
        raise IOError("the channel is gone")


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the ONE logging door: `optional_logger()` and the nineteen doors ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the process starts with NO handler on the `sshmap` tree or the root (the probe's premise)",
      not _TREE.handlers and not _ROOT.handlers, f"{_TREE.handlers} / {_ROOT.handlers}")
check("§1 with no handler anywhere the door answers None — the record never reaches `lastResort()`",
      LOGGER.optional_logger("cleanup.probe") is None)

_TREE_SINK = _Sink()
_TREE.addHandler(_TREE_SINK)
try:
    _TREE_LOG = LOGGER.optional_logger("cleanup.probe")
    _TREE_LOG.warning("the tree is installed")
finally:
    _TREE.removeHandler(_TREE_SINK)
check("§1 ...and a child logger while the tree HAS a handler (the name stays the caller's)",
      _TREE_LOG is not None and _TREE_LOG.name == "sshmap.cleanup.probe"
      and _TREE_SINK.lines == ["the tree is installed"], f"{_TREE_SINK.lines}")

_CHILD_SINK = _Sink()
_CHILD = logging.getLogger("sshmap.cleanup.probe")
_CHILD.addHandler(_CHILD_SINK)
try:
    _CHILD_LOG = LOGGER.optional_logger("cleanup.probe")
    _CHILD_LOG.warning("the harness sink is attached")
finally:
    _CHILD.removeHandler(_CHILD_SINK)
check("§1 ...a handler on the caller's OWN logger counts too (the `_records()` the suite uses)",
      _CHILD_LOG is not None and _CHILD_LOG.name == "sshmap.cleanup.probe"
      and _CHILD_SINK.lines == ["the harness sink is attached"], f"{_CHILD_SINK.lines}")

_SHIM_SITES = [rel for rel in _app_sources() if "def _log(" in _source(*rel.split("/"))]
_APP_FILES = _app_sources()
check("§1 the application tree keeps NO local `_log()` shim (the sweep is the whole tree)",
      bool(_APP_FILES) and len(_APP_FILES) > 100 and not _SHIM_SITES,
      f"{len(_APP_FILES)} files, shims={_SHIM_SITES[:4]}")

_DOORS = (
    ("services/exit_gate.py", "services.exit_gate"),
    ("storage/atomic.py", "storage.atomic"),
    ("cli/exec.py", "cli.exec"),
    ("models/profile.py", "models.profile"),
    ("dialogs/profile_manager_dialog.py", "dialogs.profile_manager_dialog"),
    ("services/credential_manager.py", "services.credential_manager"),
    ("modules/bookmarks.py", "modules.bookmarks"),
    ("modules/command_history.py", "modules.command_history"),
    ("modules/command_library.py", "modules.command_library"),
    ("modules/host_key_policy.py", "modules.host_key_policy"),
    ("modules/interactive_ask.py", "modules.interactive_ask"),
    ("modules/plugin_manager.py", "modules.plugin_manager"),
    ("modules/ssh_terminal.py", "modules.ssh_terminal"),
    ("modules/terminal_corner.py", "modules.terminal_corner"),
    ("modules/terminal_page.py", "modules.terminal_page"),
    ("modules/terminal_standalone.py", "modules.terminal_standalone"),
    ("storage/project.py", "storage.project"),
    ("ui/hotkey_registry.py", "ui.hotkey_registry"),
    ("ui/theme_store.py", "theme"),
)
for _rel, _name in _DOORS:
    _src = _source(*_rel.split("/"))
    _calls = re.findall(r'optional_logger\("([^"]+)"\)', _src)
    check(f"§1 {_rel} asks the ONE door at its points of use, under its OWN logger name",
          "from modules.logger import optional_logger" in _src and _calls
          and all(call == _name for call in _calls), f"calls={_calls}")

_BLOCKER = os.path.join(str(WORK), "blocker.txt")
with open(_BLOCKER, "w", encoding="utf-8") as _handle:
    _handle.write("not a folder")

_LAST_RESORT = _Sink()
_ORIGINAL_LAST_RESORT = logging.lastResort
logging.lastResort = _LAST_RESORT
try:
    _refused = ATOMIC.write_json_atomic(os.path.join(_BLOCKER, "x.json"), {"a": 1})
    _door = GATE.stop_thread(_DeadDoor())
    _terminated = GATE._terminate(_IgnoringThread())
    _closed = EXEC.close_stdin(_BadClose())
finally:
    logging.lastResort = _ORIGINAL_LAST_RESORT
check("§1 a refused write, a dead door, a terminated thread and a dead stdin answer with NO raw line",
      _refused is False and _door == "" and _terminated is True and _closed is False
      and not _LAST_RESORT.lines, f"{_refused} / {_door!r} / {_terminated} / {_closed} / {_LAST_RESORT.lines}")

_AUDIT_SINK = _Sink()
_TREE.addHandler(_AUDIT_SINK)
try:
    _refused_again = ATOMIC.write_json_atomic(os.path.join(_BLOCKER, "x.json"), {"a": 1})
finally:
    _TREE.removeHandler(_AUDIT_SINK)
check("§1 ...and the SAME refusal is recorded once the tree owns handlers (the door is not a silencer)",
      _refused_again is False and any("refused" in line.lower() for line in _AUDIT_SINK.lines),
      f"{_refused_again} / {_AUDIT_SINK.lines}")

# One of the fourteen swept modules, driven for REAL: a corrupt profiles file is the declared WARNING of
# `models/profile.py`, and the door must keep it off `lastResort` while the tree is bare — then record it
# once a handler exists (the `_records()` pattern the suite already uses, `tests/test_followups_v11402.py`).
_PROFILE_FILE = PROFILE._profiles_path()
with open(_PROFILE_FILE, "w", encoding="utf-8") as _handle:
    _handle.write('{"profiles": [')          # invalid JSON on purpose — STORE_UNREADABLE

_PROFILE_LAST = _Sink()
_ORIGINAL_LAST_RESORT = logging.lastResort
logging.lastResort = _PROFILE_LAST
try:
    _loaded = PROFILE.load_profiles()
finally:
    logging.lastResort = _ORIGINAL_LAST_RESORT
check("§1 a swept module stays SILENT with no tree (the profiles warning never reaches `lastResort()`)",
      _loaded == [] and not _PROFILE_LAST.lines, f"{_loaded} / {_PROFILE_LAST.lines}")

_PROFILE_SINK = _Sink()
_PROFILE_LOG = logging.getLogger("sshmap.models.profile")
_PROFILE_LOG.addHandler(_PROFILE_SINK)
try:
    PROFILE.load_profiles()
finally:
    _PROFILE_LOG.removeHandler(_PROFILE_SINK)
check("§1 ...and the SAME warning is recorded through the tree (the door is not a silencer)",
      any("cannot be read" in line for line in _PROFILE_SINK.lines), str(_PROFILE_SINK.lines))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 `StatusChecker.stop()` — the invariant and the owner, not the arithmetic ==")
# ════════════════════════════════════════════════════════════════════════════

_STATUS_SRC = _source("services", "status_checker.py")
_STOP_DOC = _method_docstring(_STATUS_SRC, "StatusChecker", "stop")
check("§2 the docstring keeps the invariant (the IN-FLIGHT batch alone) and the answer to a survivor",
      "IN-FLIGHT" in _STOP_DOC and "orphan registry" in _STOP_DOC and "exit gate" in _STOP_DOC,
      _STOP_DOC)
check("§2 ...and points at the mechanism that owns the budget (`DOCUMENTATION.md` §19)",
      "`DOCUMENTATION.md` §19" in _STOP_DOC, _STOP_DOC.replace("\n", " ")[:120])
check("§2 ...instead of re-deriving it (no `ceil`, no `probe_timeout` margin, no `+ 2 s`)",
      "ceil" not in _STOP_DOC and "probe_timeout" not in _STOP_DOC and "+ 2 s" not in _STOP_DOC,
      _STOP_DOC.replace("\n", " ")[:120])
check("§2 the arithmetic stays in the code alone (the docstring moved no budget)",
      "int(self._probe_timeout * 1000) + 2000" in _STATUS_SRC)
_DOC_TEXT = rep_doc_text("DOCUMENTATION.md")
check("§2 the mechanism still owns both halves of the budget (`--docs` regime)",
      not _DOC_TEXT or ("`probe_timeout` + 2 s" in _DOC_TEXT and "ceil(N/max_parallel)" in _DOC_TEXT),
      "DOCUMENTATION.md §19")


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the harness installs the SHIPPED paramiko silence, ONCE ==")
# ════════════════════════════════════════════════════════════════════════════

_COMMON_SRC = _source("tests", "_common.py")
_BOOTSTRAP_BODY = _COMMON_SRC[_COMMON_SRC.find("def bootstrap("):_COMMON_SRC.find("def default_root(")]
check("§3 `bootstrap()` calls the SHIPPED door of the headless surface — never a second copy of it",
      "from cli.main import silence_library_logs" in _BOOTSTRAP_BODY
      and "silence_library_logs()" in _BOOTSTRAP_BODY, _BOOTSTRAP_BODY[:160])
_LIBRARY = logging.getLogger("paramiko")
check("§3 ...and the silence is really in force in THIS process (the harness' peers die quietly)",
      any(isinstance(handler, logging.NullHandler) for handler in _LIBRARY.handlers)
      and _LIBRARY.propagate is False, f"{_LIBRARY.handlers} propagate={_LIBRARY.propagate}")
_HOSTKEY_SRC = _source("tests", "test_cli_hostkey.py")
check("§3 the topical file keeps no copy of the silence (`NullHandler` / `getLogger(\"paramiko\")`)",
      "NullHandler" not in _HOSTKEY_SRC and 'getLogger("paramiko")' not in _HOSTKEY_SRC)
_COPIES = []
for _name in sorted(os.listdir(os.path.join(ROOT, "tests"))):
    if not (_name.startswith("test_") and _name.endswith(".py")):
        continue
    if _name == os.path.basename(__file__):
        continue   # this file NAMES the patterns it refuses; the scan is about the others
    _text = _source("tests", _name)
    if 'getLogger("paramiko").addHandler' in _text or 'getLogger("paramiko").propagate' in _text:
        _COPIES.append(_name)
check("§3 no topical file re-installs the library's silence (ONE door, ONE copy in the harness)",
      not _COPIES, str(_COPIES))


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check(f"§4 this release is v{EXPECTED_APP_VERSION} (the cleanup patch on the shipped follow-up)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15.1.2") and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§4 the cleanup adds NO i18n key (the parity pin stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1256
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
check("§4 the JSON project format did NOT move (`VERSION_FORMAT` stays 0.9)",
      version.VERSION_FORMAT == "0.9")
check("§4 no new dependency: requirements.txt keeps its four pins",
      len([line for line in _source("requirements.txt").splitlines()
           if line.strip() and not line.strip().startswith("#")]) == 4)
check("§4 the changelog family carries the cleanup patch (`v1.15.1.2`)",
      "v1.15.1.2" in changelog_family_text(ROOT))
_PLAN = rep_doc_text("ROADMAP.md")
check("§4 the plan no longer PLANS the shipped cleanup (a shipped version leaves `ROADMAP.md`)",
      not _PLAN or "The PATCH `v1.15.1.2`" not in _PLAN)
_AGENTS_TEXT = rep_doc_text("AGENTS.md")
check("§4 the rule the patch settles is `AGENTS.md` §12.2 (optional_logger, never a local shim)",
      not _AGENTS_TEXT or "optional_logger" in _AGENTS_TEXT)
check("§4 ...and §8.1 owns the harness silence (ONE shipped door, no topical copy)",
      not _AGENTS_TEXT or "silence_library_logs" in _AGENTS_TEXT)

finish()
