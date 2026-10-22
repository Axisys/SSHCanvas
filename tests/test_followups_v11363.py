# -*- coding: utf-8 -*-
"""`v1.13.6.3` — the ceiling that keeps itself: ONE clamp on both sides of the reader's cap.
§1 the cap's WRITE side (`R7`): `SettingsDialog` → `collect()` → `config.json` → the resolver → every
open pane, with MIN / MAX / a middle value driven through the widget, a replaced widget clamped all
the same and a foreign value already in the file clamped on READ; §2 the compression's invariants
(`AGENTS.md` §4.3.6 is pointed at, no plan pointer and no per-line history survives, the facade under
its band); §3 the release.
Rule — `AGENTS.md` §4.3.6, §4.15, §12.5; mechanism — `DOCUMENTATION.md` §14f.
"""
import ast
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, clear_cfg, finish, load_i18n_langs, read_cfg,
                     releases_at_least, wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import i18n  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
from modules.sftp_tab import SftpTab  # noqa: E402
from modules.sftp_worker import MAX_READ_BYTES, SftpWorker  # noqa: E402
from ui.settings_dialog import SettingsDialog  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)
FACADE = os.path.join(ROOT, "modules", "sftp_tab.py")
# v1.14rc3: the row, the tree, the button row and the source switch are their own module
WIDGETS = os.path.join(ROOT, "modules", "sftp_pane_widgets.py")
# v1.14rc4: the assembly and the container's three mixins are their own modules too — a docstring
# budget has to read the file the method LIVES in, never one file name.
CLUSTERS = [os.path.join(ROOT, "modules", name) for name in
            ("sftp_pane_assembly.py", "sftp_container_panes.py", "sftp_container_session.py",
             "sftp_container_viewer.py")]
MIN_BYTES = STAB.VIEWER_MAX_BYTES_MIN
MAX_BYTES = STAB.VIEWER_MAX_BYTES_MAX
STEP = STAB.VIEWER_MAX_BYTES_STEP

FS = FakeSftpFS()
FS.add_dir("/data")
FS.add_file("/data/a.txt", b"hello\n")
TAB = SftpTab()
TAB.message.connect(lambda *_a: None)
TAB.set_commander(True)          # TWO panes: "every open pane" has something to walk
WORKER = SftpWorker(FakeSftpClient(FS))
wire_worker(WORKER, EventLog())
WORKER.start()
TAB.set_worker(WORKER)
DLG = SettingsDialog(None)

# ════════════════════════════════════════════════════════════════════════════
print("== §1 the cap's WRITE side — ONE range, and the dialog's form is the key's ONE writer ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 fixture: the container holds TWO panes (the walk below has something to reach)",
      len(TAB.panes) == 2, str(len(TAB.panes)))
check("§1 the range is ONE declaration — MIN / MAX / STEP and the PURE clamp",
      MIN_BYTES == MAX_READ_BYTES and MAX_BYTES == 250 * 1024 * 1024 and STEP == 1024 * 1024
      and STAB.clamp_viewer_max_bytes(0) == MIN_BYTES
      and STAB.clamp_viewer_max_bytes(MAX_BYTES * 4) == MAX_BYTES,
      f"{MIN_BYTES}/{MAX_BYTES}/{STEP}")


def _app_sources():
    """Every module of the application tree, as (relative path, text) — the suite is not scanned."""
    skip = {"tests", "third_party", "examples", "__pycache__", ".git", "build", "dist",
            "test-results", "_tmp_testdata"}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8", errors="replace") as fh:
                yield os.path.relpath(path, ROOT).replace("\\", "/"), fh.read()


_HELPER_NAME = "save" + "_viewer_max_bytes"
_HELPER_SITES = [rel for rel, text in _app_sources() if _HELPER_NAME in text]
check("§1 no helper stands beside the form as a SECOND writer of the key",
      not hasattr(STAB, _HELPER_NAME) and not _HELPER_SITES, str(_HELPER_SITES))

DLG.viewer_max_spin.setValue(1)
COLLECT_MIN = DLG.collect()["ui_viewer_max_bytes"]
DLG.viewer_max_spin.setValue(250)
COLLECT_MAX = DLG.collect()["ui_viewer_max_bytes"]
DLG.viewer_max_spin.setValue(6)
COLLECT_MID = DLG.collect()["ui_viewer_max_bytes"]
check("§1 the value box drives MIN / MAX / a middle value into BYTES (the row's own unit)",
      (COLLECT_MIN, COLLECT_MAX, COLLECT_MID) == (MIN_BYTES, MAX_BYTES, 6 * STEP),
      str((COLLECT_MIN, COLLECT_MAX, COLLECT_MID)))


class _HugeSpin:
    """A stand-in widget answering a value the real box cannot express (the `AttributeError` seam)."""

    def value(self):
        return 10 ** 6


_real_spin = DLG.viewer_max_spin
try:
    DLG.viewer_max_spin = _HugeSpin()
    REPLACED = DLG.viewer_max_bytes()
finally:
    DLG.viewer_max_spin = _real_spin
check("§1 a REPLACED widget cannot write an out-of-range cap — the clamp judges the value (R7a)",
      REPLACED == MAX_BYTES, str(REPLACED))

clear_cfg()
DLG.viewer_max_spin.setValue(6)
SAVED = i18n.save_config(DLG.collect())          # the dialog's OWN write path (collect() → save_config)
STORED = (read_cfg({}) or {}).get("ui_viewer_max_bytes")
RESOLVED = STAB.resolve_viewer_max_bytes()
APPLIED = TAB.apply_viewer_max_bytes(RESOLVED)
check("§1 the REAL cycle: collect() → config.json → resolve → every OPEN pane (R7)",
      SAVED is True and STORED == 6 * STEP and RESOLVED == 6 * STEP and APPLIED == 6 * STEP
      and [pane.viewer_cap() for pane in TAB.panes] == [6 * STEP] * len(TAB.panes),
      f"saved={SAVED} stored={STORED} resolved={RESOLVED} applied={APPLIED} "
      f"panes={[p.viewer_cap() for p in TAB.panes]}")
check("§1 ...and each pane really asks the new cap of its own reads (the task carries it)",
      all(pane.viewer_cap() == 6 * STEP for pane in TAB.panes)
      and TAB.panes[0].set_viewer_max_bytes(10 ** 12) == MAX_BYTES
      and TAB.panes[0].set_viewer_max_bytes(0) == MIN_BYTES,
      str([p.viewer_cap() for p in TAB.panes]))

clear_cfg()
i18n.save_config({"ui_viewer_max_bytes": 10 ** 12})
RAW_HIGH = STAB.resolve_viewer_max_bytes()
i18n.save_config({"ui_viewer_max_bytes": "8"})
RAW_STR = STAB.resolve_viewer_max_bytes()
clear_cfg()
check("§1 a foreign value already in the file is clamped on READ, never handed to a task",
      (RAW_HIGH, RAW_STR) == (MAX_BYTES, MIN_BYTES), str((RAW_HIGH, RAW_STR)))

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the compression — the owners are POINTED at, the facade is under its band ==")
# ════════════════════════════════════════════════════════════════════════════

_TEXT = open(FACADE, encoding="utf-8").read()
_LINES = _TEXT.splitlines()
_WIDGET_TEXT = open(WIDGETS, encoding="utf-8").read()
_WIDGET_LINES = _WIDGET_TEXT.splitlines()


def _docstrings(source):
    """{name: (lines, text)} of every class/function docstring of ONE module."""
    out = {}
    for _node in ast.walk(ast.parse(source)):
        if not isinstance(_node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        _body = getattr(_node, "body", [])
        if (_body and isinstance(_body[0], ast.Expr) and isinstance(_body[0].value, ast.Constant)
                and isinstance(_body[0].value.value, str)):
            _doc = _body[0].value
            out[_node.name] = ((_doc.end_lineno or _doc.lineno) - _doc.lineno + 1, _doc.value)
    return out


_DOCS = _docstrings(_TEXT + "\n" + "\n".join(
    open(path, encoding="utf-8").read() for path in CLUSTERS))
_WIDGET_DOCS = _docstrings(_WIDGET_TEXT)

check("§2 no plan pointer survives in the facade or the widgets (a plan section is DELETED "
      "on shipping)",
      "ROADMAP" not in _TEXT and "ROADMAP" not in _WIDGET_TEXT,
      str((_TEXT.count("ROADMAP"), _WIDGET_TEXT.count("ROADMAP"))))
HISTORY = ("before the wrapper existed", "the old QLabel", "EDITABLE QLineEdit now",
           "before the private type existed", "plain layout of the pane")
check("§2 no per-line history phrase survives (the changelog family owns the story)",
      [phrase for phrase in HISTORY if phrase in _TEXT] == [],
      str([phrase for phrase in HISTORY if phrase in _TEXT]))
check("§2 the GROUP rules point at their owner (`AGENTS.md` §4.3.6) instead of re-telling it",
      "§4.3.6" in _WIDGET_DOCS.get("_SftpRowItem", (0, ""))[1]
      and all(rule in _WIDGET_DOCS.get("_SftpRowItem", (0, ""))[1]
              for rule in ('".." row', "DIRECTORIES", "COLUMN")),
      _WIDGET_DOCS.get("_SftpRowItem", (0, ""))[1][:120])
check("§2 the `_ButtonRow` story is told ONCE — the constant and `__init__` point at the class",
      _WIDGET_TEXT.count("whole minimum") == 1
      and "BUTTONS_BAR_MIN_WIDTH" in _WIDGET_DOCS.get("_ButtonRow", (0, ""))[1],
      f"copies={_WIDGET_TEXT.count('whole minimum')}")
_DECL = next(i for i, line in enumerate(_WIDGET_LINES)
             if line.startswith("BUTTONS_BAR_MIN_WIDTH = 0"))
check("§2 ...and the constant's own pointer is ONE line above it",
      _WIDGET_LINES[_DECL - 1].startswith("#:") and "docstring" in _WIDGET_LINES[_DECL - 1],
      _WIDGET_LINES[_DECL - 1])
SIZES = ("_SftpRowItem", "preview_allowed", "present_viewer", "bind_worker", "set_source",
         "_disconnect_worker")
BUDGETS = {"_SftpRowItem": 7, "preview_allowed": 6, "present_viewer": 6, "bind_worker": 7,
           "set_source": 7, "_disconnect_worker": 4}
_ALL_DOCS = {**_DOCS, **_WIDGET_DOCS}
check("§2 every compressed header is the declared size (a docstring, measured)",
      all(_ALL_DOCS.get(name, (99, ""))[0] <= BUDGETS[name] for name in SIZES),
      str({name: _ALL_DOCS.get(name, (None, ""))[0] for name in SIZES}))
check("§2 the facade is under its band (≤ 2 940 lines — the release's own target)",
      len(_LINES) <= 2940, str(len(_LINES)))
check("§2 the shipped surface survives the compression (the readers, the classes, the container)",
      all(hasattr(STAB, name) for name in ("clamp_viewer_max_bytes", "resolve_viewer_max_bytes",
                                           "SftpTab", "_SftpRowItem", "_ButtonRow",
                                           "SftpPaneViewerMixin", "MODULE_FACADE_SEAMS")))

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the release ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_release_state(ROOT)
check("§3 this patch adds NO translation key (the pin stays 1180)",
      EXPECTED_I18N_KEYS == 1180 + 1, str(EXPECTED_I18N_KEYS))
check("§3 the JSON schema did NOT move (`VERSION_FORMAT` stays 0.9)",
      __import__("version").VERSION_FORMAT == "0.9")
check("§3 the pin names this patch's line", releases_at_least(EXPECTED_APP_VERSION, "1.13.6.3"),
      EXPECTED_APP_VERSION)

try:
    DLG.reject()
except Exception:  # noqa: BLE001 — the teardown must never fail the file
    pass
try:
    TAB.release()
except Exception:  # noqa: BLE001 — the teardown must never fail the file
    pass
try:
    WORKER.shutdown()
except Exception:  # noqa: BLE001 — the teardown must never fail the file
    pass
finish()
