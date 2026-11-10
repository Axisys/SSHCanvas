# -*- coding: utf-8 -*-
"""v1.15.1.3 — the `1.15.1` residue: the last sixteen logging doors and the version-tag ratchet.
§1 the 16 inline `get_logger` failure handlers ask `optional_logger()` — silent with no tree,
   recorded through it (`AGENTS.md` §12.2);
§2 `VERSION_TAG_PINS` — one pin per surface, the module headers and the three most-marked modules'
   docstrings at zero, the policy in `AGENTS.md` §12.5;
§3 the release state.
Run: python tests/test_cleanup_v11513.py
"""
import ast
import logging
import os
import re

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text,
                     check, check_i18n_parity, check_release_state, finish, load_i18n_langs,
                     rep_doc_text, releases_at_least, translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + sys.path before any app import

import _comment_budget as CB  # noqa: E402 — the ONE owner of the version-tag measurement
import i18n as I18N  # noqa: E402
import modules.multi_input as MULTI  # noqa: E402
import modules.plugin_context as CONTEXT  # noqa: E402
import modules.plugin_runner as RUNNER  # noqa: E402
import ui.settings_dialog as SETTINGS  # noqa: E402
import version  # noqa: E402

LANGS = load_i18n_langs(ROOT)
_TREE = logging.getLogger("sshmap")
_ROOT = logging.getLogger()


class _Sink(logging.Handler):
    """The ONE record sink: what a logger really emitted, at the level the file log gets."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the sixteen inline logging doors ==")
# ════════════════════════════════════════════════════════════════════════════

# The D1 family: (repository-relative file, the module's OWN logger name, the sites this patch
# converted, every site the module now owns). The third figure is the sweep's count — one per removed
# inline acquisition; the fourth is the module total, which may already carry doors from earlier work.
_DOORS = (
    ("dialogs/ssh_connect_dialog.py", "dialogs.ssh_connect_dialog", 2, 2),
    ("graphics/map_view.py", "graphics.map_view", 2, 2),
    ("modules/multi_input.py", "modules.multi_input", 2, 2),
    ("modules/plugin_context.py", "modules.plugin_context", 1, 1),
    ("modules/plugin_runner.py", "modules.plugin_runner", 1, 1),
    ("modules/ssh_terminal.py", "modules.ssh_terminal", 2, 5),
    ("modules/ssh_worker.py", "modules.ssh_worker", 1, 1),
    ("modules/terminal_widget.py", "modules.terminal_widget", 1, 1),
    ("ui/settings_dialog.py", "ui.settings_dialog", 2, 2),
    ("i18n/__init__.py", "i18n", 2, 2),
)


def _source(*parts) -> str:
    """The text of one repository file (the source scans read the shipped tree)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


_INLINE_GET = re.compile(r"from modules\.logger import get_logger\b")
_SITES = 0
for _rel, _name, _converted, _total in _DOORS:
    _src = _source(*_rel.split("/"))
    _calls = re.findall(r'optional_logger\("([^"]+)"\)', _src)
    _SITES += _converted
    check(f"§1 {_rel} asks the ONE door under its OWN logger name, at all {_total} site(s)",
          "from modules.logger import optional_logger" in _src
          and len(_calls) == _total and all(call == _name for call in _calls),
          f"calls={_calls}")
    # The declared ACCESSOR seams (terminal_widget's `_get_app_log`) keep their app logger on purpose.
    _inline = len(_INLINE_GET.findall(_src))
    check(f"§1 {_rel} keeps no inline `get_logger` acquisition in a failure handler",
          _inline == (1 if _rel == "modules/terminal_widget.py" else 0), f"inline={_inline}")
check("§1 the family is the sixteen sites the sweep names (a guard over nothing is useless)",
      _SITES == 16 and len(_DOORS) == 10, f"sites={_SITES} files={len(_DOORS)}")

check("§1 the process starts with NO handler on the `sshmap` tree or the root (the probe's premise)",
      not _TREE.handlers and not _ROOT.handlers, f"{_TREE.handlers} / {_ROOT.handlers}")

_LAST_RESORT = _Sink()
_ORIGINAL_LAST_RESORT = logging.lastResort
logging.lastResort = _LAST_RESORT
try:
    I18N._log_debug("cleanup probe debug")
    I18N._log_warning("cleanup probe warning")
    SETTINGS._log_dialog("cleanup probe dialog")
    CONTEXT.PluginContext("cleanup-probe").log("cleanup probe plugin")
    RUNNER._log_line("warning", "cleanup probe runner")
    _HUB = MULTI.get_hub()
    _HUB.reset()
    _HUB.set_active(True)          # INFO — the state change is a diagnostic of the hub
    _HUB.set_active(False)
finally:
    logging.lastResort = _ORIGINAL_LAST_RESORT
check("§1 every one of the five driven doors is SILENT with no tree (no `lastResort` line)",
      not _LAST_RESORT.lines, str(_LAST_RESORT.lines))

_AUDIT = _Sink()
_TREE.addHandler(_AUDIT)
_OLD_LEVEL = _TREE.level
_TREE.setLevel(logging.DEBUG)      # the tree's own level: INFO is a record the file log keeps
try:
    I18N._log_warning("cleanup probe warning")
    SETTINGS._log_dialog("cleanup probe dialog")
    CONTEXT.PluginContext("cleanup-probe").log("cleanup probe plugin")
    RUNNER._log_line("warning", "cleanup probe runner")
    _HUB.set_active(True)
    _HUB.set_active(False)
finally:
    _TREE.setLevel(_OLD_LEVEL)
    _TREE.removeHandler(_AUDIT)
check("§1 ...and the SAME calls are recorded once the tree owns a handler (the door is not a silencer)",
      all(any(text in line for line in _AUDIT.lines) for text in
          ("cleanup probe warning", "cleanup probe dialog", "cleanup probe plugin",
           "cleanup probe runner", "Multi-input mode enabled", "Multi-input mode disabled")),
      str(_AUDIT.lines))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the version-tag policy and its ratchet ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the ratchet names ONE pin per surface (headers, docstrings, comments)",
      set(CB.VERSION_TAG_PINS) == {"headers", "docstrings", "comments"},
      str(CB.VERSION_TAG_PINS))
check("§2 the matcher reads a release tag and leaves a bare letter alone",
      CB.VERSION_TAG_RE.findall("v1.15.1.3 v1.2rc4 v1.5 v7 v1.2.3.4") ==
      ["v1.15.1.3", "v1.2rc4", "v1.5", "v1.2.3.4"],
      str(CB.VERSION_TAG_RE.findall("v1.15.1.3 v1.2rc4 v1.5 v7 v1.2.3.4")))

_MEASURED = CB.measure(ROOT)
check("§2 the measurement reads the application tree (a guard over nothing is useless)",
      _MEASURED["version_headers"] + _MEASURED["version_docstrings"]
      + _MEASURED["version_comments"] > 0, str({s: _MEASURED[f"version_{s}"] for s in CB.VERSION_TAG_PINS}))
check("§2 every surface sits at or under its pin (the ratchet only goes DOWN)",
      all(_MEASURED[f"version_{surface}"] <= pin for surface, pin in CB.VERSION_TAG_PINS.items()),
      f"measured={ {s: _MEASURED[f'version_{s}'] for s in CB.VERSION_TAG_PINS} } "
      f"pins={CB.VERSION_TAG_PINS}")
check("§2 the module headers carry NO version tag (the bounded tranche reached 0)",
      _MEASURED["version_headers"] == 0, f"headers={_MEASURED['version_headers']}")

# The tranche's second half: the function/class docstrings of the three most-marked modules are CURRENT
# invariant text — no tag, no change story. Read from the AST, not a regex over the indented text.
for _rel in ("graphics/server_node.py", "modules/terminal_page.py", "modules/ssh_terminal.py"):
    with open(os.path.join(ROOT, *_rel.split("/")), encoding="utf-8") as _handle:
        _tree = ast.parse(_handle.read())
    _tagged = []
    for _node in ast.walk(_tree):
        if not isinstance(_node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        _doc = ast.get_docstring(_node, clean=False) or ""
        if CB.VERSION_TAG_RE.search(_doc):
            _tagged.append(_node.name)
    check(f"§2 {_rel}: every function/class docstring orients, none narrates a release",
          not _tagged, str(_tagged[:6]))

_AGENTS_TEXT = rep_doc_text("AGENTS.md")
check("§2 the rule is `AGENTS.md` §12.5 (a tag marks a CURRENT/frozen decision)",
      not _AGENTS_TEXT or ("VERSION_TAG_PINS" in _AGENTS_TEXT and "ORIENTS" in _AGENTS_TEXT),
      "AGENTS.md §12.5")


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check(f"§3 this release is v{EXPECTED_APP_VERSION} (the residue patch on the shipped follow-up)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15.1.3") and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§3 the patch adds NO i18n key (the parity pin stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1256
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
check("§3 the JSON project format did NOT move (`VERSION_FORMAT` stays 0.9)",
      version.VERSION_FORMAT == "0.9")
check("§3 no new dependency: requirements.txt keeps its four pins",
      len([line for line in _source("requirements.txt").splitlines()
           if line.strip() and not line.strip().startswith("#")]) == 4)
check("§3 the changelog family carries the residue patch (`v1.15.1.3`)",
      "v1.15.1.3" in changelog_family_text(ROOT))
_PLAN = rep_doc_text("ROADMAP.md")
check("§3 the plan no longer PLANS the shipped patch (a shipped version leaves `ROADMAP.md`)",
      not _PLAN or "The PATCH `v1.15.1.3`" not in _PLAN)

finish()
