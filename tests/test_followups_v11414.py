# -*- coding: utf-8 -*-
"""v1.14.1.4 — THE EXPORT THAT CANNOT EXECUTE: a formula-shaped report cell is DATA, never a program.
§1 the predicate and the ONE writer (`FORMULA_LEAD_CHARS` / `is_formula_cell()` / `list_quote_cell()`:
the six leading characters, the FIRST character alone deciding, the RFC-4180 quoting on top); §2 the
two report consumers inherit it (the inventory's exported file, the connection report, the clipboard
and the problems report); §3 the release pins.
Rule — `AGENTS.md` §4.13; mechanism — `DOCUMENTATION.md` §48.
Run: python tests/test_followups_v11414.py
"""
import csv
import io
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import _size_budget as SBZ  # noqa: E402 — the size ratchet this patch pays
import ui.main_window as MW  # noqa: E402
import ui.sidebar as SB  # noqa: E402
import version  # noqa: E402
from models.server import ServerData  # noqa: E402
from storage import export_connections as EC  # noqa: E402
from storage import export_problems as EPB  # noqa: E402

LANGS = load_i18n_langs(ROOT)
SIDEBAR = os.path.join(ROOT, "ui", "sidebar.py")
_APOSTROPHE = chr(39)  # the spreadsheet's own "this is text" mark, spelled ONCE in this file

_T = lambda key, **kw: key  # noqa: E731 — the report readers' injected translator


def lines(path):
    """The lines of one module — the size pins the slot states."""
    with open(path, encoding="utf-8") as handle:
        return len(handle.read().splitlines())


def app_sources():
    """Every application module as (relative path, source) — the second-writer scan."""
    skip = {"tests", "third_party", "examples", "docs", "__pycache__", ".git", "build", "dist",
            "test-results", "_tmp_testdata"}
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith("_tmp_testdata")]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8", errors="replace") as handle:
                out.append((os.path.relpath(path, ROOT).replace("\\", "/"), handle.read()))
    return out


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the ONE writer neutralises a formula-shaped cell ==")
# ════════════════════════════════════════════════════════════════════════════

_QUOTE = SB.list_quote_cell
check("§1 the six leading characters are declared ONCE (the spreadsheet's own formula starters)",
      SB.FORMULA_LEAD_CHARS == ("=", "+", "-", "@", "\t", "\r"), str(SB.FORMULA_LEAD_CHARS))
check("§1 the predicate: each of the six leads is a formula lead, and nothing else is",
      all(SB.is_formula_cell(ch + "payload") for ch in SB.FORMULA_LEAD_CHARS)
      and not any(SB.is_formula_cell(s) for s in
                  ("x=1", "1+2", "a-b", "22", "", None, "'=1+1", " =1+1")),
      str([(ch, SB.is_formula_cell(ch + "x")) for ch in SB.FORMULA_LEAD_CHARS]))
check("§1 a leading `=` / `+` / `-` / `@` is prefixed with the spreadsheet's text mark",
      [_QUOTE(v) for v in ("=1+1", "+SUM(A1:A2)", "-2+3", "@cmd")]
      == [_APOSTROPHE + "=1+1", _APOSTROPHE + "+SUM(A1:A2)", _APOSTROPHE + "-2+3",
          _APOSTROPHE + "@cmd"],
      str([_QUOTE(v) for v in ("=1+1", "+SUM(A1:A2)", "-2+3", "@cmd")]))
check("§1 a TAB- or CR-led cell is neutralised by the SAME rule",
      _QUOTE("\tTAB") == _APOSTROPHE + "\tTAB"
      and _QUOTE("\rCR") == '"' + _APOSTROPHE + "\rCR" + '"',
      repr([_QUOTE("\tTAB"), _QUOTE("\rCR")]))
check("§1 ONLY the first character decides (an inner `-`, `+`, `=` stay as typed)",
      _QUOTE("a-b") == "a-b" and _QUOTE("A+B") == "A+B" and _QUOTE("22") == "22"
      and _QUOTE("x=1") == "x=1",
      repr([_QUOTE("a-b"), _QUOTE("A+B"), _QUOTE("22"), _QUOTE("x=1")]))
check("§1 a cell that ALREADY carries the mark (or a leading space) is not guarded twice",
      _QUOTE("'=1+1") == "'=1+1" and _QUOTE(" =1+1") == " =1+1",
      repr([_QUOTE("'=1+1"), _QUOTE(" =1+1")]))
check("§1 empty / None stay EMPTY fields (there is no first character to judge)",
      _QUOTE("") == "" and _QUOTE(None) == "" and not SB.is_formula_cell(None),
      repr([_QUOTE(""), _QUOTE(None)]))
check("§1 the RFC-4180 quoting runs on the GUARDED text (a comma after the prefix is quoted)",
      _QUOTE("=1,2") == '"' + _APOSTROPHE + "=1,2" + '"'
      and _QUOTE("@SUM(A1,A2)", "\t") == _APOSTROPHE + "@SUM(A1,A2)",
      repr([_QUOTE("=1,2"), _QUOTE("@SUM(A1,A2)", "\t")]))
check("§1 the guard costs ONE apostrophe and no byte of the cell's own text",
      _QUOTE("=1+1") == _APOSTROPHE + "=1+1"
      and _QUOTE('plain, with comma') == '"plain, with comma"',
      repr([_QUOTE("=1+1"), _QUOTE("plain, with comma")]))

_PROBE = [["Name", "Host"], ["=1+1", "prod"], ["+SUM(A1:A2)", "db"], ["-2+3", "x"],
          ["@cmd", "y"], ["plain, with comma", "z"]]
_TEXT = SB.list_table_text(_PROBE, ",")
check("§1 the defect's probe: every formula-shaped cell leaves the application as TEXT",
      _TEXT == "Name,Host\r\n'=1+1,prod\r\n'+SUM(A1:A2),db\r\n'-2+3,x\r\n'@cmd,y\r\n"
               '"plain, with comma",z\r\n', repr(_TEXT))
check("§1 ...and the whole report still round-trips through Python's own csv reader",
      list(csv.reader(io.StringIO(_TEXT)))
      == [["Name", "Host"], ["'=1+1", "prod"], ["'+SUM(A1:A2)", "db"], ["'-2+3", "x"],
          ["'@cmd", "y"], ["plain, with comma", "z"]],
      str(list(csv.reader(io.StringIO(_TEXT)))))
check("§1 TSV neutralises by the SAME rule (one writer, two delimiters)",
      SB.list_table_text([["-1"]], "\t") == "'-1\r\n" and _QUOTE("prod, db", "\t") == "prod, db",
      repr(SB.list_table_text([["-1"]], "\t")))
check("§1 `list_table_text()` asks the ONE writer for every cell (no second quoting path)",
      "list_quote_cell(cell, sep)" in open(SIDEBAR, encoding="utf-8").read())

_SOURCES = app_sources()
_WRITERS = [rel for rel, src in _SOURCES if "\ndef list_quote_cell(" in src]
check("§1 `list_quote_cell()` is defined ONCE in the application tree (a second writer is the defect)",
      _WRITERS == ["ui/sidebar.py"], str(_WRITERS))
_DOUBLERS = [rel for rel, src in _SOURCES if """replace('"', '""')""" in src]
check("§1 ...and no module carries a second RFC-4180 quoter (the doubling lives beside the prefix)",
      _DOUBLERS == ["ui/sidebar.py"], str(_DOUBLERS))
_CONSUMERS = ("ui/main_window_exports.py", "storage/export_connections.py",
              "storage/export_problems.py")
_CONSUMER_SOURCES = {rel: src for rel, src in _SOURCES if rel in _CONSUMERS}
check("§1 every consumer CALLS the writer instead of re-implementing the rule",
      len(_CONSUMER_SOURCES) == len(_CONSUMERS)
      and all("list_table_text(" in src for src in _CONSUMER_SOURCES.values())
      and not any("def list_quote_cell" in src for src in _CONSUMER_SOURCES.values()),
      str(sorted(_CONSUMER_SOURCES)))

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the report consumers inherit the guard (the table on screen does not move) ==")
# ════════════════════════════════════════════════════════════════════════════

from _fakes import QuestionStub  # noqa: E402 — no modal box may block an offscreen run

box_events = []
answers = QuestionStub(
    QMessageBox.Discard,
    record=lambda title, text: box_events.append(("question", title))).install(MW)
MW.QMessageBox.critical = staticmethod(lambda *a, **k: box_events.append(("critical",)))
MW.QMessageBox.warning = staticmethod(lambda *a, **k: box_events.append(("warning",)))
MW.QMessageBox.information = staticmethod(lambda *a, **k: box_events.append(("information",)))


def make_main():
    """An offscreen MainWindow with the timers stopped (determinism, no real probing)."""
    win = MW.MainWindow()
    win._autosave_timer.stop()
    win._freshness_timer.stop()
    win.resize(1200, 800)
    win.show()
    app.processEvents()
    return win


def add_node(win, nid, alias, host, **kw):
    """Add a node straight onto the scene + refresh (the ordinary composition hook)."""
    data = ServerData(id=nid, alias=alias, host=host, user="root", **kw)
    node = win.scene.add_server(data)
    win.refresh_sidebar()
    return node


def collapse_map(win, collapsed=True):
    """Collapse/expand the map through the ORDINARY QAction (every control path converges)."""
    win.act_show_map.setChecked(not collapsed)
    app.processEvents()


def close_window(win):
    """Close without the unsaved-changes question."""
    win._dirty = False
    win._undo_baseline_dirty = False
    win.close()
    app.processEvents()


clear_cfg()
win = make_main()
add_node(win, "r-a", "=1+1", "10.0.0.1", comment="@cmd")
add_node(win, "r-b", "db-01", "10.0.0.2")
collapse_map(win)

_ALIAS = SB.list_column_index("alias")
_COMMENT = SB.list_column_index("comment")
_report = win.sidebar.list_report_rows()
check("§2 the rows handed to the writer are RAW (the user's own text, unguarded)",
      [r[_ALIAS] for r in _report[1:]] == ["=1+1", "db-01"]
      and _report[1][_COMMENT] == "@cmd", str(_report[1]))
check("§2 ...and the TABLE on screen keeps it verbatim (the guard is export-only)",
      win.tree.topLevelItem(0).text(_ALIAS) == "=1+1"
      and win.tree.topLevelItem(0).text(_COMMENT) == "@cmd",
      repr([win.tree.topLevelItem(0).text(_ALIAS), win.tree.topLevelItem(0).text(_COMMENT)]))

_saved = os.path.join(WORK, "inventory.csv")
_orig_save = MW.QFileDialog.getSaveFileName
MW.QFileDialog.getSaveFileName = staticmethod(
    lambda *a, **k: (_saved, "CSV — Comma Separated Values (*.csv)"))
try:
    win.act_export_list.trigger()
    app.processEvents()
finally:
    MW.QFileDialog.getSaveFileName = _orig_save
_written = open(_saved, encoding="utf-8-sig", newline="").read()
_parsed = list(csv.reader(io.StringIO(_written)))
check("§2 the inventory EXPORT writes the guarded cell (the alias and the comment alike)",
      os.path.exists(_saved) and _parsed[1][_ALIAS] == "'=1+1"
      and _parsed[1][_COMMENT] == "'@cmd", str(_parsed[1]))
check("§2 ...the exported bytes ARE the shipped writer's text (no second path in the window)",
      _written == SB.list_table_text(_report, ","), repr(_written[:60]))

win.act_copy_list.trigger()
app.processEvents()
_clip = list(csv.reader(io.StringIO(app.clipboard().text()), delimiter="\t"))
check("§2 the CLIPBOARD path (Copy List as TSV) carries the same guard",
      _clip[1][_ALIAS] == "'=1+1" and _clip[1][_COMMENT] == "'@cmd", str(_clip[1]))

_left = add_node(win, "c-l", "=1+1", "10.0.0.5")
_right = add_node(win, "c-r", "db-2", "10.0.0.6")
_left.setPos(0, 0)
_right.setPos(500, 0)
# Two guard sites in ONE row: the label AND the composed direction (it starts with the alias).
win.scene.add_connection("c-l", "c-r", '=HYPERLINK("http://x","click")', "database",
                         bidirectional=True)
_conn_rows = EC.connection_report_rows(win.scene.arrows(), _T)
_conn_text = EC.connection_report_text(win.scene.arrows(), ",", _T)
_conn_parsed = list(csv.reader(io.StringIO(_conn_text)))
check("§2 the connection report's ROWS stay raw (the writer is the only place that guards)",
      _conn_rows[1][7] == '=HYPERLINK("http://x","click")'
      and _conn_rows[1][5].startswith("=1+1 "), str(_conn_rows[1]))
check("§2 ...while its TEXT guards the label and the composed direction",
      _conn_parsed[1][7].startswith("'=HYPERLINK") and _conn_parsed[1][5].startswith("'=1+1 "),
      str(_conn_parsed[1]))
_conn_file = os.path.join(WORK, "connections.csv")
MW.QFileDialog.getSaveFileName = staticmethod(
    lambda *a, **k: (_conn_file, "CSV — Comma Separated Values (*.csv)"))
try:
    win._export_connections_table()
    app.processEvents()
finally:
    MW.QFileDialog.getSaveFileName = _orig_save
_conn_written = list(csv.reader(io.StringIO(
    open(_conn_file, encoding="utf-8-sig", newline="").read())))
check("§2 the connections EXPORT FILE is the same guarded text (the second named consumer)",
      os.path.exists(_conn_file) and _conn_written[1][7].startswith("'=HYPERLINK")
      and _conn_written[1][5].startswith("'=1+1 "), str(_conn_written[1]))


class _CardInTrouble:
    """A duck-typed card in trouble — the shipped report readers accept any node shape."""

    status = "offline"
    is_stale = False
    data = ServerData(id="pb-1", alias="=1+1", host="10.0.0.9", user="root")


_problem_text = EPB.problem_report_text([_CardInTrouble()], ",", _T)
check("§2 the problems report — the third consumer — inherits the rule with no line of its own",
      list(csv.reader(io.StringIO(_problem_text)))[1][0] == "'=1+1", repr(_problem_text))
close_window(win)

# ════════════════════════════════════════════════════════════════════════════
print("== §3 i18n, the size ratchet and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§3 the patch adds NO i18n key (parity stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1193 + 3, str(EXPECTED_I18N_KEYS))
check("§3 the pin names this release's line and the schema did NOT move",
      releases_at_least(EXPECTED_APP_VERSION, "1.14.1.4") and version.VERSION_FORMAT == "0.9",
      f"{EXPECTED_APP_VERSION} / {version.VERSION_FORMAT}")
check("§3 the writer's module rides its LINE PIN (the predicate is paid in THIS change)",
      SBZ.LINE_PINS.get("ui/sidebar.py") == lines(SIDEBAR),
      f"pin={SBZ.LINE_PINS.get('ui/sidebar.py')} measured={lines(SIDEBAR)}")
check("§3 the connection report earned no pin (it calls the writer, it does not grow one)",
      lines(EC.__file__) == 125 and "storage/export_connections.py" not in SBZ.LINE_PINS,
      f"{lines(EC.__file__)} lines")
finish()
