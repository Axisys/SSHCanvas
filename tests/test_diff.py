# -*- coding: utf-8 -*-
"""The Diff tab of a session (v1.13.4): the pure engine, the readers, the spool, the view and its doors.
§1 the pure engine — lines, tags, pairing, intra-line spans, the aligned blocks and the figures; §2 the
local reader — the cap, the truncation and the two binary screens; §3 the ONE codec of both sides; §4 the
tab — the two columns, the block marks, the summary, the headers, Clear, the two passes; §5 the doors —
the session page, the session row, the Files submenu and the pure target reader; §6 the two readers over
a live fake worker and the spool's drop; §7 the i18n keys, the release state and the untouched schema.
Contract — `DIFF.md`; rule — `AGENTS.md` §4.34; mechanism — `DOCUMENTATION.md` §79.
Run: python tests/test_diff.py
"""
import os
import re
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, VERSION_FORMAT_RE, bootstrap,
                     check, check_i18n_format, check_i18n_parity, check_release_state, clear_cfg,
                     finish, load_i18n_langs, releases_at_least, translation_keys, wait_until)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_diff as D  # noqa: E402
import modules.terminal_page as TP  # noqa: E402
import modules.terminal_standalone as TS  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.command_history import history_key  # noqa: E402
from modules.sftp_worker import SftpWorker  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, FakeSSHThread, wire_worker  # noqa: E402

ST.SSHTerminalThread = FakeSSHThread
clear_cfg()


def _read(*parts) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def _tmp_text(name, text, encoding="utf-8"):
    path = os.path.join(WORK, name)
    with open(path, "w", encoding=encoding, newline="") as handle:
        handle.write(text)
    return path


def _tmp_bytes(name, data):
    path = os.path.join(WORK, name)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def _fresh_tab(cap=None):
    """A `DiffTab` whose ceiling is `cap` (the shipped resolver is not asked — a test seam)."""
    original = D._viewer_cap
    if cap is not None:
        D._viewer_cap = lambda: int(cap)
    try:
        return D.DiffTab()
    finally:
        D._viewer_cap = original


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the pure engine ==")

check("§1 the line split normalises the line endings (a CRLF copy is the same content)",
      D.split_lines("a\r\nb\nc\r") == ["a", "b", "c"]
      and D.split_lines("") == [] and D.split_lines(None) == [])
_equal = D.diff_rows("one\ntwo", "one\ntwo")
check("§1 two identical texts answer equal rows and zero figures",
      [row.tag for row in _equal] == [D.TAG_EQUAL, D.TAG_EQUAL]
      and D.diff_stats(_equal) == {"added": 0, "removed": 0, "changed": 0})
check("§1 an inserted line is ONE insert row and its figures are 1/0/0",
      [row.tag for row in D.diff_rows("a\nb", "a\nx\nb")] == [D.TAG_EQUAL, D.TAG_INSERT,
                                                               D.TAG_EQUAL]
      and D.diff_stats(D.diff_rows("a\nb", "a\nx\nb")) == {"added": 1, "removed": 0,
                                                           "changed": 0})
check("§1 a deleted line is ONE delete row",
      [row.tag for row in D.diff_rows("a\nb", "a")] == [D.TAG_EQUAL, D.TAG_DELETE])
_paired = D.diff_rows("a\nb\nc", "a\nX")
check("§1 a replace pairs the lines one by one and the excess becomes a delete",
      [row.tag for row in _paired] == [D.TAG_EQUAL, D.TAG_CHANGE, D.TAG_DELETE]
      and _paired[1].left_text == "b" and _paired[1].right_text == "X"
      and _paired[2].right_no is None, [(r.tag, r.left_no, r.right_no) for r in _paired])
check("§1 the rows carry the 1-based line numbers of their OWN side",
      D.diff_rows("a\nb", "a\nb\nc")[2].right_no == 3
      and D.diff_rows("a\nb", "a\nb\nc")[2].left_no is None)
_left_spans, _right_spans = D.intra_spans("hello world", "hello there")
check("§1 the intra-line spans are character runs of each side",
      bool(_left_spans) and bool(_right_spans)
      and all(0 <= start < end <= len("hello world") for start, end in _left_spans)
      and all(0 <= start < end <= len("hello there") for start, end in _right_spans),
      (_left_spans, _right_spans))
check("§1 a line over the declared bound keeps the LINE mark alone",
      D.intra_spans("x" * (D.INLINE_MAX_CHARS + 1), "y" * (D.INLINE_MAX_CHARS + 1)) == ((), ()))
try:
    D.diff_rows("\n".join("x" for _ in range(D.DIFF_MAX_LINES + 1)), "")
    _budget_raised = False
except D.DiffBudgetExceeded as _exc:
    _budget_raised = _exc.lines == D.DIFF_MAX_LINES + 1
check("§1 a pair over the declared line budget is REFUSED before the matcher (the engine's bound)",
      _budget_raised and D.DIFF_INLINE_MAX_LINES < D.DIFF_MAX_LINES)
check("§1 the intra-line offsets are converted to the UTF-16 units `QTextCursor` counts",
      D.utf16_spans("😀abcDEF", [(4, 7)]) == ((5, 8),)
      and D.utf16_spans("plain", [(1, 3)]) == ((1, 3),))
check("§1 the two blocks are ALIGNED: one block per row on either side",
      len(D.side_blocks(_paired, D.DIFF_LEFT)) == len(D.side_blocks(_paired, D.DIFF_RIGHT))
      == len(_paired))
_deleted_right = D.side_blocks(_paired, D.DIFF_RIGHT)[2]
check("§1 a delete row is a GAP block on the right (no fabricated line)",
      _deleted_right[0] is None and _deleted_right[1] == ""
      and _deleted_right[2] == D.TAG_GAP
      and D.side_blocks(_paired, D.DIFF_LEFT)[2][2] == D.TAG_DELETE)
check("§1 the three fills are the THEME's status colours at the declared alpha (no new colour)",
      D._fills()[D.TAG_INSERT].name() == QColor(D.theme.STATUS_ONLINE).name()
      and D._fills()[D.TAG_DELETE].name() == QColor(D.theme.STATUS_OFFLINE).name()
      and D._fills()[D.TAG_CHANGE].name() == QColor(D.theme.STATUS_WARN).name()
      and D._fills()[D.TAG_INSERT].alpha() == D.DIFF_TINT_ALPHA
      and D._fills()[D.TAG_GAP].name() == QColor(D.theme.SURFACE_ALT).name())
_source = _read("modules", "terminal_diff.py")
check("§1 the view is QPlainTextEdit blocks, never a custom painter",
      "def paintEvent" not in _source and "QPlainTextEdit" in _source
      and not re.search(r"QColor\(\s*[\"']#", _source))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the local reader ==")
# ════════════════════════════════════════════════════════════════════════════

_lf = _tmp_text("plain.txt", "alpha\nbeta\n")
_data, _total, _code = D.read_local_side(_lf, 64)
check("§2 a readable file answers its bytes, its size and no code",
      _data == b"alpha\nbeta\n" and _total == len(_data) and _code == "", (len(_data), _total))
_big = _tmp_bytes("big.txt", b"z" * 100)
_data, _total, _code = D.read_local_side(_big, 10)
check("§2 the ceiling TRUNCATES the read and the real size travels with it",
      _data == b"z" * 10 and _total == 100 and _code == "")
check("§2 a binary EXTENSION is refused by the shipped screen",
      D.read_local_side(_tmp_text("note.zip", "not really"), 64)[2] == "binary")
check("§2 a NULL byte in the first chunk is refused",
      D.read_local_side(_tmp_bytes("nul.txt", b"text\x00more"), 64)[2] == "binary")
check("§2 a missing file answers the read code, never a traceback",
      D.read_local_side(os.path.join(WORK, "nope.txt"), 64)[2] == "read")
check("§2 an empty file is a LOADED side of zero bytes",
      D.read_local_side(_tmp_text("empty.txt", ""), 64) == (b"", 0, ""))


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the ONE codec of both sides ==")
# ════════════════════════════════════════════════════════════════════════════

_tab = _fresh_tab()
_tab.load_side("left", {"kind": "local", "path": _tmp_text("utf8.txt", "привет\n")})
check("§3 `auto` resolves the codec from the FIRST side and freezes it",
      _tab._codec == "utf-8" and _tab.side_state("left")["encoding"] == "utf-8")
_tab.load_side("right", {"kind": "local", "path": _tmp_bytes("latin.txt", b"caf\xe9\n")})
check("§3 the second side is decoded by the SAME codec and its fallback is NAMED",
      _tab._codec == "utf-8" and _tab.side_state("right")["encoding"] == "latin-1"
      and i18n.t("sftp.viewer.encoding_failed", encoding="utf-8", fallback="latin-1")
      in _tab.header_text("right"), _tab.header_text("right"))
_tab.shutdown()

i18n.save_config({"ui_viewer_encoding": "cp1251"})
try:
    _tab = _fresh_tab()
    check("§3 a NAMED setting is the tab's codec before any side is read", _tab._codec == "cp1251")
    _tab.load_side("left", {"kind": "local",
                            "path": _tmp_bytes("cp1251.txt", "привет\n".encode("cp1251"))})
    check("§3 ...and both sides are decoded by it",
          _tab.side_state("left")["text"] == "привет\n" and _tab._codec == "cp1251")
    _tab.shutdown()
finally:
    i18n.save_config({"ui_viewer_encoding": "auto"})


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the tab: two columns, the marks and the summary ==")
# ════════════════════════════════════════════════════════════════════════════

_tab = D.DiffTab()
check("§4 the tab holds two read-only editors in one splitter",
      len(_tab._editors) == 2 and _tab.splitter.count() == 2
      and all(editor.isReadOnly() for editor in _tab._editors.values())
      and all(editor.lineWrapMode() == editor.LineWrapMode.NoWrap
              for editor in _tab._editors.values()))
_left = _tmp_text("left.txt", "one\ntwo\nthree\n")
_right = _tmp_text("right.txt", "one\nTWO\nthree\nfour\n")
_tab.load_side("left", {"kind": "local", "path": _left})
check("§4 one side alone is shown plainly and the summary asks for the other",
      _tab.status_text().startswith(i18n.t("diff.need_other"))
      and not _tab.rows(), _tab.status_text())
_tab.load_side("right", {"kind": "local", "path": _right})
check("§4 both sides are compared and the figures are the rows'",
      _tab.status_text().startswith(i18n.t("diff.stats", added=1, removed=0, changed=1)),
      _tab.status_text())
check("§4 the two editors carry the SAME block count (the rows are aligned)",
      _tab._editors["left"].blockCount() == _tab._editors["right"].blockCount()
      == len(_tab.rows()))
_change_block = _tab._editors["left"].document().findBlockByNumber(1)
check("§4 the changed block wears the theme's change fill at the declared alpha",
      _change_block.blockFormat().background().style() != 0
      and _change_block.blockFormat().background().color().alpha() == D.DIFF_TINT_ALPHA)
_inline = []
_iterator = _change_block.begin()
while not _iterator.atEnd():
    _fragment = _iterator.fragment()
    if _fragment.charFormat().background().style() != 0:
        _inline.append((_fragment.text(),
                        _fragment.charFormat().background().color().alpha()))
    _iterator += 1
check("§4 the intra-line mark is a STRONGER fill of the changed characters",
      bool(_inline) and any(alpha == D.DIFF_INLINE_ALPHA for _text, alpha in _inline), _inline)
check("§4 the header names the side, the file and its size",
      _tab.header_text("left") == i18n.t("diff.header", side=i18n.t("diff.side.left"),
                                         name="left.txt", size=D.format_size(
                                             os.path.getsize(_left))), _tab.header_text("left"))
_tab.load_side("right", {"kind": "local", "path": _left})
check("§4 two copies of one file answer the identical sentence",
      _tab.status_text().startswith(i18n.t("diff.same")), _tab.status_text())
_tab.refresh_theme()
check("§4 a theme pass re-applies the marks and never the text",
      _tab._editors["left"].toPlainText() == "one\ntwo\nthree")
_tab.clear_side("right")
check("§4 Clear forgets ONE side only (the other side stays loaded)",
      not _tab.side_state("right")["loaded"] and _tab.side_state("left")["loaded"]
      and _tab.status_text().startswith(i18n.t("diff.need_other")))
try:
    i18n.set_language("ru")
    _tab.retranslate()
    check("§4 a language switch re-texts the buttons and the summary",
          _tab._buttons[("left", "local")].text() == i18n.t("diff.load_local")
          and _tab._buttons[("left", "clear")].text() == i18n.t("diff.clear")
          and _tab.status_text() == i18n.t("diff.need_other") + " · "
          + i18n.t("diff.encoding", encoding="utf-8"), _tab.status_text())
finally:
    i18n.set_language("en")
    _tab.retranslate()
check("§4 a binary side is ONE sentence and the side stays empty",
      _tab.load_side("right", {"kind": "local", "path": _tmp_text("x.zip", "zip")}) is False
      and not _tab.side_state("right")["loaded"]
      and _tab.side_state("right")["error"] == i18n.t("diff.error_binary", name="x.zip"),
      _tab.side_state("right")["error"])
check("§4 a missing file is the read sentence",
      _tab.load_side("right", {"kind": "local", "path": os.path.join(WORK, "gone.txt")}) is False
      and _tab.side_state("right")["error"] == i18n.t("diff.error_read", name="gone.txt"))
_capped = _fresh_tab(cap=8)
_capped.load_side("left", {"kind": "local", "path": _big})
check("§4 a truncated side says how much of how many it shows (the shipped sentence)",
      i18n.t("sftp.viewer.truncated", shown=D.format_size(8), total=D.format_size(100))
      in _capped.header_text("left"), _capped.header_text("left"))
_capped.shutdown()
_tab.shutdown()
check("§4 shutdown is idempotent", _tab.shutdown() is None and _tab._shut_down is True)


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the doors ==")
# ════════════════════════════════════════════════════════════════════════════

_page = TP.TerminalSessionPage(ServerData(id="diff-1", alias="web", host="10.0.0.1",
                                          user="root"))
check("§5 a session is born with three tabs and NO Diff tab",
      _page.tabs.count() == 3 and _page.diff_tab is None)
_first = _page.open_diff()
check("§5 the first door creates ONE Diff tab and makes it current",
      _first is not None and _page.tabs.count() == 4
      and _page.tabs.currentWidget() is _first
      and _page.tabs.tabText(3) == i18n.t("terminal.tab_diff"))
check("§5 a second door reuses the same tab (never a second view)",
      _page.open_diff() is _first and _page.tabs.count() == 4)
check("§5 `load_into_diff()` opens the tab and fills the side",
      _page.load_into_diff("left", {"kind": "local", "path": _left}) is True
      and _first.side_state("left")["loaded"] and _first.side_state("left")["name"] == "left.txt")
_page.retranslate()
_page.refresh_theme()
check("§5 the page's own passes reach the tab (the tab title re-texts)",
      _page.tabs.tabText(3) == i18n.t("terminal.tab_diff"))

_menu = QMenu()
_called = []
_rows = TP.add_session_actions(_menu, _page, lambda page: None, lambda page: None,
                               lambda page: _called.append(page))
check("§5 the session row is the builder's THIRD row and it is live",
      len(_menu.actions()) == 3 and _rows[2].text() == i18n.t("terminal.diff.open")
      and _rows[2].isEnabled() is True)
_rows[2].trigger()
check("§5 ...and it hands its OWN page to the container's delegate", _called == [_page])
_none_menu = QMenu()
_lone = TP.add_session_actions(_none_menu, None, lambda page: None, lambda page: None,
                               lambda page: None)
check("§5 a page-less menu disables every row",
      [action.isEnabled() for action in _none_menu.actions()] == [False, False, False]
      and _lone[2].isEnabled() is False)

_split = TP.TerminalSessionPage(ServerData(id="diff-2", alias="pane", host="10.0.0.2",
                                           user="root"), with_sftp=False, split=True)
check("§5 a split pane has no Diff tab and its door answers None", _split.open_diff() is None)
_split.shutdown()

_fs = FakeSftpFS()
_fs.add_dir("/data")
_fs.add_file("/plain.txt", b"alpha\nbeta\n")
_worker = SftpWorker(FakeSftpClient(_fs))
wire_worker(_worker, EventLog())
_worker.start()
_stab = STAB.SftpTab()
_stab.set_worker(_worker)
_stab._navigate("/")
wait_until(lambda: any(_stab.tree.topLevelItem(i).text(0) == "plain.txt"
                       for i in range(_stab.tree.topLevelItemCount())), timeout_ms=5000)
_pane = _stab.active_pane


def _item(name):
    for index in range(_stab.tree.topLevelItemCount()):
        item = _stab.tree.topLevelItem(index)
        if item.text(0) == name:
            return item
    return None


_dir_menu = _pane._build_diff_menu(_item("data"))
check("§5 a DIRECTORY row answers the shipped no-file sentence",
      _dir_menu is not None and len(_dir_menu.actions()) == 1
      and _dir_menu.actions()[0].isEnabled() is False
      and _dir_menu.actions()[0].text() == i18n.t("sftp.send.no_file"))


class _Target:
    """A `DiffTarget`-shaped recorder: the pane hands it a side and an entry, nothing else."""

    def __init__(self, key, label):
        self.key = key
        self.label = label
        self.calls = []

    def load(self, side, entry):
        self.calls.append((side, dict(entry)))
        return True


_same = _Target(history_key("diff-1"), "web")
_foreign = _Target(history_key("other"), "db")
_original_hook = D.find_host_hook
D.find_host_hook = lambda widget, name: (
    (lambda *_args: [_same, _foreign]) if name == "_diff_targets" else None)
try:
    _build = _pane._build_diff_menu(_item("plain.txt"))
    check("§5 the Files row's submenu lists a side pair per target",
          _build is not None
          and [action.text() for action in _build.actions()]
          == [i18n.t("diff.send.row", target="web", side=i18n.t("diff.side.left")),
              i18n.t("diff.send.row", target="web", side=i18n.t("diff.side.right")),
              i18n.t("diff.send.row", target="db", side=i18n.t("diff.side.left")),
              i18n.t("diff.send.row", target="db", side=i18n.t("diff.side.right"))],
          [action.text() for action in _build.actions()])
    _build.actions()[0].trigger()
    check("§5 a FOREIGN session's row travels through the shipped spool family",
          bool(_same.calls) and _same.calls[0][1]["kind"] == "spool"
          and _same.calls[0][1]["worker"] is _pane.provider, _same.calls)
    _build.actions()[2].trigger()
    check("§5 a row of ANOTHER session is a spool too (its worker carries the bytes)",
          bool(_foreign.calls) and _foreign.calls[0][1]["kind"] == "spool"
          and _foreign.calls[0][1]["name"] == "plain.txt", _foreign.calls)

    _stab.set_session_info(key=history_key("diff-1"), label="web", host="10.0.0.1",
                           port=22, user="root")
    _same.calls.clear()
    _pane._op_send_to_diff(_item("plain.txt"), _same, D.DIFF_LEFT)
    check("§5 a row of THIS session hands the tab a `remote` entry (the worker reader)",
          bool(_same.calls) and _same.calls[0][1]["kind"] == "remote"
          and _same.calls[0][0] == D.DIFF_LEFT, _same.calls)
    _pane._source = STAB.SOURCE_LOCAL
    try:
        _same.calls.clear()
        _pane._op_send_to_diff(_item("plain.txt"), _same, D.DIFF_RIGHT)
    finally:
        _pane._source = STAB.SOURCE_REMOTE
    check("§5 a LOCAL row is read where it lies (no copy, no worker)",
          bool(_same.calls) and _same.calls[0][1]["kind"] == "local"
          and _same.calls[0][1]["path"] == "/plain.txt")

    D.find_host_hook = lambda widget, name: ((lambda *_args: [])
                                             if name == "_diff_targets" else None)
    _empty_menu = _pane._build_diff_menu(_item("plain.txt"))
    check("§5 a provider that answers nothing offers ONE disabled sentence",
          _empty_menu is not None and len(_empty_menu.actions()) == 1
          and _empty_menu.actions()[0].isEnabled() is False
          and _empty_menu.actions()[0].text() == i18n.t("diff.send.no_targets"))
finally:
    D.find_host_hook = _original_hook

_page_targets = D.diff_targets_from_pages([_page, _split, object()])
check("§5 the pure target reader keys a session by its `history_key()` and skips the rest",
      [target.key for target in _page_targets] == [history_key("diff-1")]
      and _page_targets[0].label == "web"
      and D.diff_targets_from_pages([]) == [])
check("§5 the standalone surface answers the same provider from its own window",
      callable(getattr(TS.StandaloneSurface, "_diff_targets", None)))
_worker.shutdown(wait_ms=2000)
_stab.release()
_page.shutdown()


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the two readers over the fake worker and the spool's drop ==")
# ════════════════════════════════════════════════════════════════════════════

_fs2 = FakeSftpFS()
_fs2.add_file("/remote.txt", b"remote line\nsecond\n")
_fs2.add_file("/blob.zip", b"not really a zip\n")
_worker2 = SftpWorker(FakeSftpClient(_fs2))
wire_worker(_worker2, EventLog())
_worker2.start()

_tab = D.DiffTab()
check("§6 a remote read is QUEUED on the source worker (no GUI-thread network)",
      _tab.load_side("left", {"kind": "remote", "worker": _worker2, "path": "/remote.txt",
                              "size": 19, "name": "remote.txt"}) is True
      and _tab.side_state("left")["reading"] == "remote.txt")
wait_until(lambda: _tab.side_state("left")["loaded"], timeout_ms=5000)
check("§6 ...and its answer is decoded like a local one",
      _tab.side_state("left")["text"] == "remote line\nsecond\n"
      and _tab.side_state("left")["name"] == "remote.txt",
      _tab.side_state("left")["text"])
check("§6 a spool leg is queued for a foreign session (the shipped download)",
      _tab.load_side("right", {"kind": "spool", "worker": _worker2, "path": "/remote.txt",
                               "size": 19, "name": "remote.txt"}) is True)
_left_spool = list(_tab._spools)   # THIS tab's copy — a parallel run owns its own spool
wait_until(lambda: _tab.side_state("right")["loaded"], timeout_ms=8000)
check("§6 ...the spool is read and the two sides compare",
      _tab.side_state("right")["text"] == "remote line\nsecond\n"
      and _tab.status_text().startswith(i18n.t("diff.same")), _tab.status_text())
check("§6 ...and the copy never outlives the decode",
      bool(_left_spool) and _tab._spools == []
      and not any(os.path.exists(p) for p in _left_spool), _tab._spools)
_tab.load_side("left", {"kind": "remote", "worker": _worker2, "path": "/blob.zip",
                        "size": 18, "name": "blob.zip"})
wait_until(lambda: _tab.side_state("left")["error"], timeout_ms=5000)
check("§6 a binary remote side is refused with the ONE sentence",
      _tab.side_state("left")["error"] == i18n.t("diff.error_binary", name="blob.zip"),
      _tab.side_state("left")["error"])
check("§6 a remote side without a worker is 'waiting', never a traceback",
      _tab.load_side("left", {"kind": "remote", "worker": None, "path": "/remote.txt"}) is False)
_tab.shutdown()
_worker2.shutdown(wait_ms=2000)


class _FakeReadWorker(QObject):
    """A worker surface with the four answers the tab binds — the read legs are driven by hand."""

    read_ready = Signal(int, str, bytes)
    task_done = Signal(int, str)
    task_error = Signal(int, str, str)
    task_cancelled = Signal(int, str)

    def __init__(self):
        super().__init__()
        self.ids = []
        self._next = 100

    def queue_read(self, path, size=0, max_bytes=0):
        self._next += 1
        self.ids.append(self._next)
        return self._next


_fake = _FakeReadWorker()
_tab = D.DiffTab()
_tab.load_side("left", {"kind": "remote", "worker": _fake, "path": "/a.txt", "name": "a.txt"})
_tab.load_side("left", {"kind": "remote", "worker": _fake, "path": "/b.txt", "name": "b.txt"})
_first_id, _second_id = _fake.ids
_fake.read_ready.emit(_first_id, "/a.txt", b"old\n")
check("§6 a LATE answer never overwrites a side that a newer load owns",
      not _tab.side_state("left")["loaded"], _tab.side_state("left"))
_fake.read_ready.emit(_second_id, "/b.txt", b"new\n")
check("§6 ...the newest answer is the one on the screen",
      _tab.side_state("left")["loaded"] and _tab.side_state("left")["text"] == "new\n",
      _tab.side_state("left")["text"])
_tab.load_side("right", {"kind": "remote", "worker": _fake, "path": "/c.txt", "name": "c.txt"})
_stale_id = _fake.ids[-1]
_tab.clear_side("right")
_fake.read_ready.emit(_stale_id, "/c.txt", b"late\n")
check("§6 Clear invalidates a leg still in flight (nothing reopens the side)",
      not _tab.side_state("right")["loaded"], _tab.side_state("right"))
_tab.shutdown()


# ════════════════════════════════════════════════════════════════════════════
print("== §7 the i18n keys, the documents and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

LANGS = load_i18n_langs(ROOT)
_NEW_KEYS = ["terminal.tab_diff", "terminal.diff.open", "terminal.diff.tooltip",
             "diff.side.left", "diff.side.right", "diff.empty", "diff.header",
             "diff.load_local", "diff.clear", "diff.encoding", "diff.same", "diff.stats",
             "diff.need_other", "diff.error_binary", "diff.error_read", "diff.send.menu",
             "diff.send.row", "diff.send.no_targets"]
check("§7 the EIGHTEEN keys of the release are non-empty in every language",
      all(LANGS[code].get(key) for code in LANGS for key in _NEW_KEYS),
      str({code: [key for key in _NEW_KEYS if not LANGS[code].get(key)]
           for code in sorted(LANGS)}))
check("§7 ...and the pin carries them (1144 + the release's 18 + the later four)",
      len(_NEW_KEYS) == 18
      and EXPECTED_I18N_KEYS == 1144 + len(_NEW_KEYS) + 4, str(EXPECTED_I18N_KEYS))
check("§7 the keys are really TRANSLATED, not the English copy",
      len({LANGS[code].get("terminal.diff.tooltip") for code in LANGS}) > 1
      and len({LANGS[code].get("diff.same") for code in LANGS}) > 1)
check("§7 every placeholder the tab fills exists in every language",
      all(set(re.findall(r"\{(\w+)\}", LANGS[code].get("diff.header", "")))
          == {"side", "name", "size"}
          and set(re.findall(r"\{(\w+)\}", LANGS[code].get("diff.stats", "")))
          == {"added", "removed", "changed"}
          and set(re.findall(r"\{(\w+)\}", LANGS[code].get("diff.send.row", "")))
          == {"target", "side"}
          for code in LANGS))
check("§7 the reconnect-era keys are still translated (no drift in the shared files)",
      all(all(key in translation_keys(data) for key in ("terminal.reconnect", "sftp.op.upload"))
          for data in LANGS.values()))
check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check("§7 the release is the one this file describes (a PATCH on `X.Y.Z` adds a component)",
      releases_at_least(EXPECTED_APP_VERSION, "1.13.4")
      and bool(VERSION_FORMAT_RE.match(EXPECTED_APP_VERSION)),
      EXPECTED_APP_VERSION)
check("§7 the schema did NOT move and no dependency arrived (difflib is the standard library)",
      'VERSION_FORMAT = "0.9"' in _read("version.py")
      and "difflib" not in _read("requirements.txt")
      and "difflib" not in _read("pyproject.toml")
      and all(f"{name}>=" in _read("requirements.txt")
              for name in ("PySide6", "paramiko", "keyring", "wcwidth")))
check("§7 the contract is frozen and registered in the internal world",
      os.path.isfile(os.path.join(ROOT, "DIFF.md"))
      and "DIFF.md" in _read(".gitignore") and "DIFF.md" in _read("AGENTS.md")
      and "DIFF.md" not in _read("README.md"))
check("§7 the mechanism and the rule are written where they are owned",
      "§4.34" in _read("AGENTS.md") and "§79" in _read("DOCUMENTATION.md"))
check("§7 the suite map lists this file (tests/INDEX.md regenerated)",
      "test_diff" in _read("tests", "INDEX.md"))


finish()
