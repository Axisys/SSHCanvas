# -*- coding: utf-8 -*-
"""`v1.13.6` — FIND IT: the search of the Files panes, the reversible delete and the per-pane codec.
§1 the PURE engine (`modules/sftp_search.py`): the query, the matcher, the report's counters and the
bound that stops a run; §2 the walk over the shipped `queue_list()` / `queue_read()` family and the
ONE `cut` sentence; §3 the surface — the row, the query dialog, the results panel in the reader's
slot and the ONE-panel rule; §4 the trash (a backend that moves, an absent one, a failure that never
degrades into `os.remove`); §5 the per-SESSION encoding memory (`ui_sftp_encodings`) beside the
shipped global default; §6 the keys and the release.
Rule — `AGENTS.md` §4.3.6, §4.15, §4.24; mechanism — `DOCUMENTATION.md` §14f.
"""
import os
import re
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, finish, load_i18n_langs,
                     releases_at_least, wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import i18n  # noqa: E402
import modules.local_fs_worker as LOCAL  # noqa: E402
import modules.sftp_pane_helpers as PH  # noqa: E402
import modules.sftp_pane_viewer as SPV  # noqa: E402
import modules.sftp_search as SEARCH  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402
from modules.sftp_tab import KIND_DELETE, KIND_TRASH, SOURCE_LOCAL, SftpTab  # noqa: E402
from modules.sftp_worker import SftpWorker  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)
TREE = os.path.join(WORK, "tree")
if not os.path.isdir(TREE):
    os.makedirs(TREE)
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def placeholders(value) -> set:
    """The `{name}` placeholders of ONE sentence — the parity rule read off the text."""
    return set(PLACEHOLDER.findall(str(value or "")))


def key_event(code) -> QKeyEvent:
    """A real Qt key event — the two view keys are read through `event.key()` (`AGENTS.md` §8.4)."""
    return QKeyEvent(QEvent.Type.KeyPress, code, Qt.KeyboardModifier.NoModifier)


def make_tab(fs=None, commander=False):
    """(tab, worker, messages) over the fake SFTP surface — the shipped stack."""
    tab = SftpTab()
    messages = []
    tab.message.connect(messages.append)
    if commander:
        tab.set_commander(True)
    worker = None
    if fs is not None:
        worker = SftpWorker(FakeSftpClient(fs))
        wire_worker(worker, EventLog())
        worker.start()
        tab.set_worker(worker)
    return tab, worker, messages


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the PURE engine — the query, the matcher and the report ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 a blank needle is REFUSED (an empty query would match every line of every file)",
      SEARCH.normalize_query("") is None and SEARCH.normalize_query("   ") is None
      and SEARCH.normalize_query(None) is None)
_query = SEARCH.normalize_query("  mixed Case  ", case_sensitive=True, scope="nowhere")
check("§1 the record keeps the needle BYTE FOR BYTE, its flags and the DECLARED default scope",
      _query == {"needle": "  mixed Case  ", "case_sensitive": True,
                 "scope": SEARCH.SEARCH_SCOPE_DEFAULT},
      str(_query))
check("§1 the scope is the declared pair, and a foreign value is the default, never a widening",
      SEARCH.SEARCH_SCOPES == ("here", "subtree")
      and SEARCH.query_scope({"scope": "here"}) == "here"
      and SEARCH.query_scope({}) == "subtree"
      and SEARCH.query_scope({"scope": "everywhere"}) == "subtree")

TEXT = "alpha\nBETA\nneedle here\nbeta needle\n"
_hits, _cut = SEARCH.match_lines(TEXT, "beta")
check("§1 the matcher is case-INSENSITIVE by default and numbers its lines from 1",
      _hits == [(2, "BETA"), (4, "beta needle")] and _cut is False, str(_hits))
_hits, _cut = SEARCH.match_lines(TEXT, "beta", case_sensitive=True)
check("§1 ...and `match case` narrows it to the ONE line that really spells it",
      _hits == [(4, "beta needle")] and _cut is False, str(_hits))
_hits, _cut = SEARCH.match_lines("a\r\nb\r\n", "b")
check("§1 a CRLF line is TRIMMED (the row is read, not edited)",
      _hits == [(2, "b")] and _cut is False, str(_hits))
_many = "\n".join("hit %d" % index for index in range(SEARCH.MATCHES_PER_FILE + 5))
_hits, _cut = SEARCH.match_lines(_many, "hit")
check("§1 ONE file contributes at most MATCHES_PER_FILE rows — and SAYS it was cut",
      len(_hits) == SEARCH.MATCHES_PER_FILE and _cut is True
      and _hits[-1][0] == SEARCH.MATCHES_PER_FILE, f"{len(_hits)}/{_cut}")
check("§1 a line that does not carry the needle is never a hit, and a blank needle never matches",
      SEARCH.match_lines("nothing\n", "needle") == ([], False)
      and SEARCH.match_lines("x\n", "") == ([], False))

_report = SEARCH.SearchReport(SEARCH.normalize_query("needle"))
_report.note_entries(3)
_report.note_read(40)
_report.note_matches([(1, "needle"), (2, "needle")])
_report.note_read(10)
_report.note_matches([])
check("§1 the report counts what a run really reached (entries, files, bytes, matches)",
      (_report.entries, _report.files_scanned, _report.files_matched, _report.bytes_read,
       _report.matches) == (3, 2, 1, 50, 2)
      and _report.cut is False,
      str(_report.as_dict()))
_shared = _report.as_dict()
check("§1 the report's dict carries the FIVE named counters and the bound that stopped it",
      {"files_scanned", "files_matched", "bytes_read", "matches", "cut"} <= set(_shared)
      and {"cut_reason", "needle", "scope", "entries"} <= set(_shared), str(sorted(_shared)))

_capped = SEARCH.SearchReport(SEARCH.normalize_query("x"), max_matches=3)
_capped.note_matches([(1, "x"), (2, "x")])
_capped.note_matches([(3, "x"), (4, "x")])
check("§1 the run's OWN match cap carries the first rows and reports the bound",
      _capped.matches == 3 and _capped.cut is True
      and _capped.cut_reason == SEARCH.CUT_MATCHES, str(_capped.as_dict()))
_entries = SEARCH.SearchReport(SEARCH.normalize_query("x"), entries=2)
check("§1 the ENTRY bound is asked per entry and stops the walk on the one that crosses it",
      _entries.allow_entries() is True and _entries.note_entries() == 1
      and _entries.allow_entries() is True and _entries.note_entries() == 2
      and _entries.allow_entries() is False
      and _entries.cut_reason == SEARCH.CUT_ENTRIES, str(_entries.as_dict()))
_depth = SEARCH.SearchReport(SEARCH.normalize_query("x"), depth=2)
check("§1 the DEPTH bound judges the level a directory sits at",
      _depth.allow_depth(2) is True and _depth.allow_depth(3) is False
      and _depth.cut_reason == SEARCH.CUT_DEPTH)
_budget = SEARCH.SearchReport(SEARCH.normalize_query("x"), max_bytes=100)
check("§1 the byte budget answers the cap ONE read may take, then refuses the next one",
      _budget.allow_read(64) == 64 and _budget.note_read(60) == 60
      and _budget.allow_read(64) == 40 and _budget.note_read(40) == 100
      and _budget.allow_read(64) == 0 and _budget.cut_reason == SEARCH.CUT_BYTES,
      str(_budget.as_dict()))
_first_wins = SEARCH.SearchReport(SEARCH.normalize_query("x"))
_first_wins.cut_with(SEARCH.CUT_DEPTH)
_first_wins.cut_with(SEARCH.CUT_BYTES)
check("§1 the FIRST bound wins (the sentence names the limit the run really hit)",
      _first_wins.cut_reason == SEARCH.CUT_DEPTH and _first_wins.cut is True)
check("§1 the walk's bounds are the SHIPPED declarations, not a second ceiling",
      SEARCH.MAX_TREE_ENTRIES == SW.MAX_TREE_ENTRIES
      and SEARCH.MAX_TREE_DEPTH == SW.MAX_TREE_DEPTH
      and SEARCH.SearchReport(SEARCH.normalize_query("x")).entries_limit == SW.MAX_TREE_ENTRIES,
      f"{SEARCH.MAX_TREE_ENTRIES}/{SW.MAX_TREE_ENTRIES}")

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the walk over the SHIPPED task family, and the ONE `cut` sentence ==")
# ════════════════════════════════════════════════════════════════════════════

FS = FakeSftpFS()
for _directory in ("/srv", "/srv/app", "/srv/app/deep", "/srv/logs"):
    FS.add_dir(_directory)
FS.add_file("/srv/app/main.py", b"import os\n# needle here\nprint('needle')\n")
FS.add_file("/srv/app/deep/deeper.py", b"# needle deep\n")
FS.add_file("/srv/app/notes.txt", b"nothing to see\n")
FS.add_file("/srv/logs/today.log", b"line\nneedle in the log\n")

tab, worker, messages = make_tab(FS)
tab.set_session_info(key="search-session", label="Fake", host="192.0.2.10", port=22)
pane = tab.panes[0]
wait_for(lambda: pane.tree.topLevelItemCount() >= 1, timeout_ms=5000)
pane._relist("/srv")
wait_for(lambda: pane.current_dir == "/srv" and pane.tree.topLevelItemCount() >= 3,
         timeout_ms=5000)


def run_search(pane_obj, query, limits=None, ms=20000):
    """Drive ONE search of `pane_obj` to its end and answer the report."""
    pane_obj._start_search(query, limits=limits)
    wait_for(lambda: (pane_obj._search or {}).get("done"), timeout_ms=ms)
    return pane_obj.search_report


_sub = run_search(pane, {"needle": "needle", "scope": "subtree"})
check("§2 a SUBTREE search walks the shipped listings and reads the files it meets",
      _sub["matches"] == 4 and _sub["files_matched"] == 3 and _sub["files_scanned"] == 4
      and _sub["bytes_read"] > 0 and _sub["cut"] is False,
      str(_sub))
check("§2 ...and the panel carries ONE `path:line` row per hit, with the matched text",
      [row[0] for row in pane.search_rows()] == ["/srv/app/main.py"] * 2
      + ["/srv/logs/today.log", "/srv/app/deep/deeper.py"]
      and pane.search_rows()[0][1] == "2"
      and pane.search_rows()[0][2] == "# needle here",
      str(pane.search_rows()))
check("§2 ...the header names the needle and the counters the run really reached",
      pane.search_label.text() == i18n.t("sftp.search.header", needle="needle", matches=4,
                                         files=3, scanned=4),
      pane.search_label.text())
check("§2 ...and the results panel is the ONE panel of the reader's slot",
      pane.search_open is True and pane.panel_in_slot() is pane.search_panel
      and pane.viewer_host() is pane)
pane._container.close_preview()
check("§2 a close restores the listing and drops the run's bookkeeping",
      pane.search_open is False and not pane._search_lists and not pane._search_reads
      and pane._search is None
      and pane.panel_in_slot() is pane.viewer)

_here = run_search(pane, {"needle": "needle", "scope": "here"})
check("§2 `here` lists the directory on the screen and NEVER descends",
      _here["matches"] == 0 and _here["files_scanned"] == 0 and _here["entries"] == 2,
      str(_here))
check("§2 ...and a run with no hit says so in ONE sentence",
      i18n.t("sftp.search.none", needle="needle") in messages, str(messages[-3:]))
pane._container.close_preview()

_cut = run_search(pane, {"needle": "needle", "scope": "subtree"}, limits={"entries": 1})
check("§2 the ENTRY bound stops the walk and answers the counters it reached",
      _cut["cut"] is True and _cut["cut_reason"] == SEARCH.CUT_ENTRIES and _cut["entries"] == 1,
      str(_cut))
check("§2 ...and the bound is REPORTED in ONE sentence naming the limit",
      i18n.t("sftp.search.cut_entries", limit=1) in messages, str(messages[-3:]))
pane._container.close_preview()

_bytes = run_search(pane, {"needle": "needle", "scope": "subtree"}, limits={"max_bytes": 8})
check("§2 the byte budget cuts the run, and the files read before it are still counted",
      _bytes["cut"] is True and _bytes["cut_reason"] == SEARCH.CUT_BYTES
      and 0 < _bytes["bytes_read"] <= 8, str(_bytes))
check("§2 ...and ITS sentence names the budget",
      i18n.t("sftp.search.cut_bytes", limit=STAB.format_size(8)) in messages, str(messages[-3:]))
pane._container.close_preview()

_depth = run_search(pane, {"needle": "needle", "scope": "subtree"}, limits={"depth": 0})
check("§2 the DEPTH bound refuses a SUBFOLDER before it is listed",
      _depth["cut"] is True and _depth["cut_reason"] == SEARCH.CUT_DEPTH, str(_depth))
check("§2 ...and its sentence names the levels",
      i18n.t("sftp.search.cut_depth", limit=0) in messages, str(messages[-3:]))
pane._container.close_preview()

# The LOCAL source needs no special case: its walk is `local_entries()` behind `queue_list()`.
LOCAL_TREE = os.path.join(TREE, "local_search")
os.makedirs(os.path.join(LOCAL_TREE, "sub"), exist_ok=True)
with open(os.path.join(LOCAL_TREE, "top.txt"), "w", encoding="utf-8") as handle:
    handle.write("plain\nneedle on the local disk\n")
with open(os.path.join(LOCAL_TREE, "sub", "deep.txt"), "w", encoding="utf-8") as handle:
    handle.write("needle deep on the local disk\n")
_local_search_tab, _local_search_worker, _local_search_msgs = make_tab(FS, commander=True)
_local_search_tab.set_session_info(key="local-search", label="Local", host="192.0.2.13", port=22)
_local_search_pane = _local_search_tab.panes[1]
_local_search_tab.set_pane_source(_local_search_pane, SOURCE_LOCAL)
_local_search_pane._relist(LOCAL_TREE)
wait_for(lambda: _local_search_pane.current_dir == LOCAL_TREE
         and _local_search_pane.tree.topLevelItemCount() >= 2, timeout_ms=5000)
_local_found = run_search(_local_search_pane, {"needle": "needle", "scope": "subtree"})
check("§2 the LOCAL pane searches the OS disk through the SAME walk (no second path)",
      _local_found["matches"] == 2 and _local_found["files_matched"] == 2
      and _local_found["files_scanned"] == 2
      and sorted(row[0] for row in _local_search_pane.search_rows())
      == sorted([os.path.join(LOCAL_TREE, "top.txt"),
                 os.path.join(LOCAL_TREE, "sub", "deep.txt")]),
      str(_local_found))
_local_search_tab.close_preview()

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the surface — the row, the dialog, the panel and the ONE-panel rule ==")
# ════════════════════════════════════════════════════════════════════════════

_menu = pane._build_context_menu(None)
_labels = [action.text() for action in _menu.actions() if not action.isSeparator()]
check("§3 `Find text…` is a row of the pane's OWN menu — it needs no target row",
      i18n.t("sftp.search.row") in _labels
      and _labels.index(i18n.t("sftp.search.row")) == _labels.index(i18n.t("sftp.op.delete")) + 1,
      str(_labels))
_find = next(action for action in _menu.actions()
             if action.text() == i18n.t("sftp.search.row"))
check("§3 ...and it is LIVE on empty space (the walk starts at the directory on the screen)",
      _find.isEnabled() is True)

_dialog = SPV._FindTextDialog(pane, {"needle": "prior", "case_sensitive": True,
                                     "scope": SEARCH.SEARCH_SCOPE_HERE})
check("§3 the query dialog opens on the LAST query of the pane (the re-ask is one keystroke)",
      _dialog.needle_edit.text() == "prior" and _dialog.case_box.isChecked() is True
      and _dialog.subfolders_box.isChecked() is False
      and _dialog.windowTitle() == i18n.t("sftp.search.title"))
_dialog.needle_edit.setText("  next need  ")
_dialog.case_box.setChecked(False)
_dialog.subfolders_box.setChecked(True)
check("§3 ...and it answers the DECLARED query record (needle, case, scope)",
      _dialog.query() == {"needle": "  next need  ", "case_sensitive": False,
                          "scope": SEARCH.SEARCH_SCOPE_SUBTREE},
      str(_dialog.query()))
_dialog.needle_edit.setText("   ")
check("§3 ...a blank needle answers None (nothing is queued)",
      _dialog.query() is None)
_dialog.deleteLater()

_ASKED = []


def _fake_ask(self):
    _ASKED.append(1)
    return {"needle": "needle", "scope": SEARCH.SEARCH_SCOPE_SUBTREE}


_orig_ask = SPV.SftpPaneViewerMixin._ask_search_query
SPV.SftpPaneViewerMixin._ask_search_query = _fake_ask
try:
    pane._op_find_text(None)
    _asked_ran = wait_for(lambda: (pane._search or {}).get("done"), timeout_ms=20000)
finally:
    SPV.SftpPaneViewerMixin._ask_search_query = _orig_ask
check("§3 the row goes through the dialog seam and starts the walk",
      _ASKED == [1] and _asked_ran is True and pane.search_report["matches"] == 4,
      str(pane.search_report))

_rows = pane.search_rows()
check("§3 a row carries the file, the line and its size (the preview needs no second listing)",
      pane.search_tree.topLevelItem(0).data(0, pane.SIZE_ROLE)
      == len(b"import os\n# needle here\nprint('needle')\n") and len(_rows) == 4)
_first = pane.search_tree.topLevelItem(0)
pane.search_tree.setCurrentItem(_first)
pane._on_search_item(_first)
_applied = wait_for(lambda: not pane.viewer.isHidden(), timeout_ms=10000)
check("§3 a double click opens that file through the SHIPPED preview",
      _applied is True and pane._viewer_path == "/srv/app/main.py"
      and "needle here" in pane.viewer_text.toPlainText(),
      f"{pane._viewer_path!r} hidden={pane.viewer.isHidden()}")
check("§3 ...and the results panel gives the slot up (ONE panel at a time)",
      pane.search_open is False and pane.panel_in_slot() is pane.viewer)
pane._container.close_preview()

run_search(pane, {"needle": "needle", "scope": "subtree"})
pane.search_tree.setCurrentItem(pane.search_tree.topLevelItem(0))
_enter = pane.search_key(key_event(Qt.Key.Key_Return))
_enter_done = wait_for(lambda: not pane.viewer.isHidden(), timeout_ms=10000)
check("§3 `Enter` on a result is the double click's twin (the panel's OWN key)",
      _enter is True and _enter_done is True and pane._viewer_path == "/srv/app/main.py")
run_search(pane, {"needle": "needle", "scope": "subtree"})
_esc = pane.search_key(key_event(Qt.Key.Key_Escape))
check("§3 `Esc` closes the results through the container's ONE door",
      _esc is True and pane.search_open is False and pane.viewer_host() is None)

tab.set_commander(True)
_pane_b = tab.panes[1]
wait_for(lambda: _pane_b.tree.topLevelItemCount() >= 1, timeout_ms=5000)
run_search(pane, {"needle": "needle", "scope": "subtree"})
check("§3 the search panel takes the OTHER pane's slot in the two-pane view (the mc rule)",
      pane.viewer_host() is _pane_b and _pane_b._viewer_borrowed is True
      and tab.preview_pane() is pane
      and pane.panel_in_slot() is pane.search_panel,
      f"host={pane.viewer_host()!r} borrowed={_pane_b._viewer_borrowed}")
_messages_before = len(messages)
check("§3 ...and the SECOND pane's own search is REFUSED while that panel is up",
      _pane_b._start_search({"needle": "x", "scope": "subtree"}) is False
      and _pane_b.search_open is False,
      "the one-panel gate")
check("§3 ...with the shipped busy sentence, never a second panel",
      i18n.t("sftp.cmd.preview_busy") in messages[_messages_before:]
      and tab.preview_pane() is pane,
      str(messages[-3:]))
tab.close_preview()
check("§3 the close puts BOTH panes' listings back",
      pane.search_open is False and pane.viewer_host() is None
      and _pane_b._viewer_borrowed is False and _pane_b.tree.isHidden() is False)
tab.set_commander(False)

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the REVERSIBLE delete — the trash backend, its absence and its failure ==")
# ════════════════════════════════════════════════════════════════════════════

check("§4 the backend is DECIDED from the platform, and `gio` is looked for on a POSIX host",
      LOCAL.trash_backend("win32") == LOCAL.TRASH_BACKEND_WIN32
      and LOCAL.trash_backend("linux", lambda name: None) == ""
      and LOCAL.trash_backend("linux", lambda name: "/usr/bin/gio") == LOCAL.TRASH_BACKEND_GIO
      and LOCAL.trash_backend("darwin", lambda name: "") == "",
      f"{LOCAL.trash_backend('win32')}/{LOCAL.trash_backend('linux', lambda n: None)}")
_orig_backend = LOCAL.trash_backend
_orig_move = LOCAL.trash_move
try:
    LOCAL.trash_backend = lambda *a, **k: ""
    _refused = []
    try:
        LOCAL.trash_move(os.path.join(TREE, "ghost.txt"), "")
    except LOCAL._LocalRefusal as exc:
        _refused.append(exc.code)
    check("§4 a host with NO backend refuses the move with the ONE `trash_failed` code "
          "(never a quiet `os.remove`)",
          _refused == [LOCAL.LOCAL_TRASH_FAILED] and LOCAL.LOCAL_ERROR_KEYS[
              LOCAL.LOCAL_TRASH_FAILED] == "sftp.local.trash_failed",
          str(_refused))
finally:
    LOCAL.trash_backend = _orig_backend

_local_tab, _local_worker, _local_msgs = make_tab(FS, commander=True)
_local_tab.set_session_info(key="local-session", label="Fake", host="192.0.2.10", port=22)
_local_pane = _local_tab.panes[1]
check("§4 the switch to the OS disk is offered to the SECOND pane alone",
      _local_tab.set_pane_source(_local_pane, SOURCE_LOCAL) is True
      and _local_pane.source == SOURCE_LOCAL)
_moved = []
_texts = []


class _DeleteBox:
    """The monkeypatched `STAB.QMessageBox` — records the confirmation text and says YES."""
    Yes, No = 0x4000, 0x10000

    @staticmethod
    def question(parent, title, text, buttons, default):
        _texts.append(text)
        return _DeleteBox.Yes


def _row_named(pane_obj, name):
    """The listing row by its visible name (None — not on the screen)."""
    for index in range(pane_obj.tree.topLevelItemCount()):
        item = pane_obj.tree.topLevelItem(index)
        if item.text(0) == name:
            return item
    return None


def _listing_has(pane_obj, name, ms=5000) -> bool:
    return wait_for(lambda: _row_named(pane_obj, name) is not None, timeout_ms=ms)


_queued_kinds = []
_orig_queue_op = _local_pane._queue_op
_local_pane._queue_op = lambda task_id, kind: _queued_kinds.append(kind) \
    or _orig_queue_op(task_id, kind)
try:
    LOCAL.trash_backend = lambda *a, **k: LOCAL.TRASH_BACKEND_WIN32
    LOCAL.trash_move = lambda path, backend="": _moved.append((path, backend)) or backend
    check("§4 the plan of a LOCAL row names the TRASH sentence and its backend",
          _local_pane._delete_plan() == ("sftp.local.trash_confirm",
                                         LOCAL.TRASH_BACKEND_WIN32),
          str(_local_pane._delete_plan()))
    _victim = os.path.join(TREE, "victim.txt")
    with open(_victim, "wb") as handle:
        handle.write(b"bye\n")
    _local_pane._relist(TREE)
    _listing_has(_local_pane, "victim.txt")
    _item = _row_named(_local_pane, "victim.txt")
    _orig_box = STAB.QMessageBox
    STAB.QMessageBox = _DeleteBox
    try:
        _local_pane._op_delete(_item)
        _done = wait_for(lambda: bool(_moved), timeout_ms=5000)
    finally:
        STAB.QMessageBox = _orig_box
    check("§4 a click on a LOCAL row moves it through the TRASH task (`task_done`)",
          _done is True and _moved == [(_victim, LOCAL.TRASH_BACKEND_WIN32)]
          and _queued_kinds == [KIND_TRASH],
          f"moved={_moved} kinds={_queued_kinds}")
    check("§4 ...the question SAYS the trash can be restored",
          _texts == [i18n.t("sftp.local.trash_confirm", name="victim.txt")], str(_texts))
    check("§4 ...and the pane itself never deletes (the OS owns the move)",
          os.path.exists(_victim) is True)

    LOCAL.trash_backend = lambda *a, **k: ""
    check("§4 without a backend the plan keeps the shipped PERMANENT warning",
          _local_pane._delete_plan() == ("sftp.local.delete_confirm", ""),
          str(_local_pane._delete_plan()))
    _texts.clear()
    _queued_kinds.clear()
    _listing_has(_local_pane, "victim.txt")
    _again_item = _row_named(_local_pane, "victim.txt")
    _orig_box = STAB.QMessageBox
    STAB.QMessageBox = _DeleteBox
    try:
        _local_pane._op_delete(_again_item)
        _gone = wait_for(lambda: not os.path.exists(_victim), timeout_ms=5000)
    finally:
        STAB.QMessageBox = _orig_box
    check("§4 ...and the click really deletes for good (the shipped `os.remove`, KIND_DELETE)",
          _gone is True and _queued_kinds == [KIND_DELETE]
          and "recycle" in _texts[0].lower(), f"{_queued_kinds} {_texts}")

    def _boom(path, backend=""):
        raise LOCAL._LocalRefusal(LOCAL.LOCAL_TRASH_FAILED, "denied by the OS")

    LOCAL.trash_backend = lambda *a, **k: LOCAL.TRASH_BACKEND_WIN32
    LOCAL.trash_move = _boom
    _failing = os.path.join(TREE, "failing.txt")
    with open(_failing, "wb") as handle:
        handle.write(b"keep me\n")
    _local_pane._relist(TREE)
    _listing_has(_local_pane, "failing.txt")
    _fail_item = _row_named(_local_pane, "failing.txt")
    _local_msgs.clear()
    _orig_box = STAB.QMessageBox
    STAB.QMessageBox = _DeleteBox
    try:
        _local_pane._op_delete(_fail_item)
        _reported = wait_for(
            lambda: i18n.t("sftp.local.trash_failed", error="denied by the OS")
            in _local_msgs, timeout_ms=5000)
    finally:
        STAB.QMessageBox = _orig_box
    check("§4 a REFUSED move is an ERROR with its own sentence — never a silent delete",
          _reported is True and os.path.exists(_failing) is True, str(_local_msgs[-3:]))
    check("§4 ...and no `os.remove` ran (the reversible delete never degrades)",
          os.path.exists(_failing) is True)
finally:
    LOCAL.trash_backend = _orig_backend
    LOCAL.trash_move = _orig_move
    _local_pane._queue_op = _orig_queue_op

check("§4 a REMOTE row keeps the shipped question (no trash on a server)",
      _local_tab.panes[0]._delete_plan() == ("sftp.op.delete_confirm", ""),
      str(_local_tab.panes[0]._delete_plan()))
check("§4 the trash is a KIND of the operation family — the page stays silent about it",
      KIND_TRASH == "trash" and KIND_TRASH in SW.OP_KINDS and KIND_DELETE in SW.OP_KINDS
      and "trash" not in SW.LOGGED_KINDS)

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the per-SESSION encoding memory (`ui_sftp_encodings`) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§5 the map is the declared key family beside `ui_sftp_dirs`",
      PH.ENCODINGS_CONFIG == "ui_sftp_encodings"
      and STAB.DIRS_CONFIG == "ui_sftp_dirs"
      and PH.ENCODING_SLOTS == 2 and PH.MAX_REMEMBERED_ENCODINGS > 0)
check("§5 a FOREIGN entry is dropped (a broken config never decodes a pane)",
      PH.sanitize_encodings({"a": ["cp1251", "latin-1"], "b": "cp1251", "c": ["nope", ""],
                             "": ["cp1251", ""]}) == {"a": ["cp1251", "latin-1"]}
      and PH.sanitize_encodings(None) == {} and PH.sanitize_encodings("x") == {},
      str(PH.sanitize_encodings({"a": ["cp1251", "latin-1"], "b": "cp1251",
                                 "c": ["nope", ""], "": ["cp1251", ""]})))
_map = PH.remember_encoding({}, "sess", 0, "cp1251")
_map = PH.remember_encoding(_map, "sess", 1, "latin-1")
check("§5 ONE choice is filed per pane index, and an EMPTY slot means `never chose`",
      _map == {"sess": ["cp1251", "latin-1"]}
      and PH.remembered_encoding_for(_map, "sess", 0) == "cp1251"
      and PH.remembered_encoding_for(_map, "sess", 1) == "latin-1"
      and PH.remembered_encoding_for({"s": ["", "cp866"]}, "s", 0) == ""
      and PH.remembered_encoding_for({}, "s", 0) == ""
      and PH.remembered_encoding_for(_map, "sess", 7) == "",
      str(_map))
_bounded = PH.remember_encoding({}, "a", 0, "utf-8", limit=2)
_bounded = PH.remember_encoding(_bounded, "b", 0, "utf-8", limit=2)
_bounded = PH.remember_encoding(_bounded, "c", 0, "utf-8", limit=2)
check("§5 the map is BOUNDED, oldest-first (insertion order IS the age)",
      _bounded == {"b": ["utf-8", ""], "c": ["utf-8", ""]} and list(_bounded) == ["b", "c"],
      str(_bounded))
check("§5 a session that chose NOTHING is never filed as the default (the slot stays EMPTY)",
      PH.sanitize_encodings({"sess": ["", ""]}) == {}
      and PH.remember_encoding({}, "sess", 0, "") == {}
      and PH.remembered_encoding_for({"sess": ["", ""]}, "sess", 0) == "",
      str(PH.remember_encoding({}, "sess", 0, "")))

STAB.save_viewer_encoding(PH.VIEWER_ENCODING_DEFAULT)
i18n.save_config({PH.ENCODINGS_CONFIG: {}})
_enc_tab, _enc_worker, _enc_msgs = make_tab(FS, commander=True)
_enc_tab.set_session_info(key="codec-session", label="Codec", host="192.0.2.11", port=22)
_pane_a, _pane_b = _enc_tab.panes[0], _enc_tab.panes[1]
check("§5 a pane with no memory starts on the shipped GLOBAL default",
      _pane_a.viewer_encoding_choice == STAB.resolve_viewer_encoding()
      and _pane_a.remembered_encoding_choice == "",
      f"{_pane_a.viewer_encoding_choice} vs {STAB.resolve_viewer_encoding()}")
_pane_a._on_encoding_chosen("cp1251")
_pane_b._on_encoding_chosen("latin-1")
_stored = i18n.load_config().get(PH.ENCODINGS_CONFIG)
check("§5 TWO panes of ONE session keep their OWN codec side by side",
      _stored == {"codec-session": ["cp1251", "latin-1"]}
      and _pane_a.viewer_encoding_choice == "cp1251"
      and _pane_b.viewer_encoding_choice == "latin-1"
      and _pane_a.remembered_encoding_choice == "cp1251",
      str(_stored))
_again, _again_worker, _again_msgs = make_tab(FS, commander=True)
_again.set_session_info(key="codec-session", label="Codec", host="192.0.2.11", port=22)
check("§5 ...and a RESTART of that session returns both panes as they were left",
      _again.panes[0].viewer_encoding_choice == "cp1251"
      and _again.panes[1].viewer_encoding_choice == "latin-1",
      f"{_again.panes[0].viewer_encoding_choice}/{_again.panes[1].viewer_encoding_choice}")
STAB.save_viewer_encoding("cp866")
_other, _other_worker, _other_msgs = make_tab(FS, commander=True)
_other.set_session_info(key="another-session", label="Other", host="192.0.2.12", port=22)
check("§5 a session that never chose keeps the GLOBAL default (`ui_viewer_encoding`)",
      _other.panes[0].viewer_encoding_choice == "cp866"
      and _other.panes[0].remembered_encoding_choice == ""
      and STAB.resolve_viewer_encoding() == "cp866",
      f"{_other.panes[0].viewer_encoding_choice}/{STAB.resolve_viewer_encoding()}")
check("§5 ...and the sibling of the remembered session does NOT leak into it",
      _again.panes[0].viewer_encoding_choice == "cp1251"
      and _again.panes[1].viewer_encoding_choice == "latin-1")
STAB.save_viewer_encoding(PH.VIEWER_ENCODING_DEFAULT)
i18n.save_config({PH.ENCODINGS_CONFIG: {}})

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the keys and the release ==")
# ════════════════════════════════════════════════════════════════════════════

_NEW_KEYS = ("sftp.search.row", "sftp.search.title", "sftp.search.needle",
             "sftp.search.subfolders", "sftp.search.case", "sftp.search.header",
             "sftp.search.none", "sftp.search.cut_entries", "sftp.search.cut_depth",
             "sftp.search.cut_bytes", "sftp.search.cut_matches", "sftp.local.trash_confirm",
             "sftp.local.trash_failed")
check("§6 the THIRTEEN keys of the release are present and non-empty in EVERY language",
      len(_NEW_KEYS) == 13
      and all(str(LANGS[code].get(key) or "").strip() for code in LANGS for key in _NEW_KEYS),
      str({code: [key for key in _NEW_KEYS if not LANGS[code].get(key)]
           for code in sorted(LANGS)}))
check("§6 ...and the pin counts them beside the previous release (1166 + 13)",
      EXPECTED_I18N_KEYS == 1166 + 13 + 1 + 1 and len(_NEW_KEYS) == 13, str(EXPECTED_I18N_KEYS))
check("§6 every sentence of the family is really TRANSLATED, not the English copy",
      len({LANGS[code]["sftp.search.header"] for code in LANGS}) > 1
      and len({LANGS[code]["sftp.local.trash_confirm"] for code in LANGS}) > 1)
check("§6 the placeholders of the header and of the trash sentence match en in every language",
      all(placeholders(LANGS[code]["sftp.search.header"])
          == {"needle", "matches", "files", "scanned"} for code in LANGS)
      and all(placeholders(LANGS[code]["sftp.local.trash_failed"]) == {"error"}
              for code in LANGS)
      and all(placeholders(LANGS[code]["sftp.search.cut_bytes"]) == {"limit"}
              for code in LANGS),
      str({code: placeholders(LANGS[code]["sftp.search.header"]) for code in sorted(LANGS)}))
_SOURCES = "".join(open(os.path.join(ROOT, "modules", name), encoding="utf-8").read()
                   for name in ("sftp_pane_viewer.py", "sftp_pane_dnd.py",
                                "sftp_pane_helpers.py", "local_fs_worker.py"))
check("§6 ...and every one of them is USED by the shipped code (a key nobody reads is dead weight)",
      all(key in _SOURCES for key in _NEW_KEYS),
      str([key for key in _NEW_KEYS if key not in _SOURCES]))
check_release_state(ROOT)
check("§6 the shipped version is the one this file describes or a later release",
      releases_at_least(EXPECTED_APP_VERSION, "1.13.6"), EXPECTED_APP_VERSION)
check("§6 the JSON schema did NOT move (the memory lives in `config.json`)",
      __import__("version").VERSION_FORMAT == "0.9")
check_i18n_parity(LANGS)
check_i18n_format(LANGS)

for _tab, _worker in ((tab, worker), (_local_search_tab, _local_search_worker),
                      (_local_tab, _local_worker), (_enc_tab, _enc_worker),
                      (_again, _again_worker), (_other, _other_worker)):
    try:
        _tab.release()
    except Exception:  # noqa: BLE001 — the teardown must never fail the file
        pass
    if _worker is not None:
        _worker.shutdown()
finish()
