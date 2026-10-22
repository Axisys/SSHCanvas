# -*- coding: utf-8 -*-
"""The Diff tab of ONE session — the pure line engine and the two-column view (`v1.13.4`).

`diff_rows()` / `side_blocks()` / `diff_stats()` / `intra_spans()` / `utf16_spans()` are PURE over
`difflib`; `read_local_side()` is the bounded local read. `DiffTab` is the widget: two read-only
`QPlainTextEdit` columns whose `QTextBlock` backgrounds carry the marks, a `QSplitter`, a header and a
summary line. The readers are the local read and the shipped `SftpWorker.queue_read()`; a foreign
session's file crosses through the shipped spool family of `modules/sftp_send.py`. The tab is a WIDGET
of a session, never a session: it dies with its page.

Contract — `DIFF.md`; mechanism — `DOCUMENTATION.md` §79; rule — `AGENTS.md` §4.34.
"""
import difflib
import os
import queue
import threading
from collections import namedtuple

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QTextBlockFormat, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # the SHIPPED read policy and the extension screen
    from .sftp_worker import MAX_READ_BYTES, READ_ERROR_BINARY, classify_extension
except ImportError:
    from sftp_worker import MAX_READ_BYTES, READ_ERROR_BINARY, classify_extension  # type: ignore

try:  # the shipped decode rule and the ONE encoding setting
    from .sftp_pane_helpers import decode_text, format_size, resolve_viewer_encoding
except ImportError:
    from sftp_pane_helpers import (decode_text, format_size,  # type: ignore
                                   resolve_viewer_encoding)

try:  # the spool family of the cross-session send
    from . import sftp_send as send
except ImportError:
    import sftp_send as send  # type: ignore

try:  # the ONE parent-chain walk of a host hook (`diff_targets_for()`'s contract)
    from .terminal_split import find_host_hook
except ImportError:
    from terminal_split import find_host_hook  # type: ignore

try:  # the ACTIVE theme (the three fills come from its own status colours)
    from ..ui import theme
except ImportError:
    from ui import theme  # type: ignore

#: The TWO sides and their ONE spelling.
DIFF_LEFT = "left"
DIFF_RIGHT = "right"
DIFF_SIDES = (DIFF_LEFT, DIFF_RIGHT)

#: The tag of ONE row: an equal line, a modified pair, a line only on the left / on the right, and the
#: blank block the other side keeps for alignment (`DIFF.md` §5).
TAG_EQUAL = "equal"
TAG_CHANGE = "change"
TAG_DELETE = "delete"
TAG_INSERT = "insert"
TAG_GAP = "gap"

#: The intra-line bound: a longer line (or a pair producing more spans) keeps the LINE mark alone.
INLINE_MAX_CHARS = 2000
INLINE_MAX_SPANS = 40

#: The ENGINE's declared budget (`N127`): a pair over this many lines in TOTAL is REFUSED before
#: `SequenceMatcher` — the worst case of a repetitive pair is superlinear, and 4 000 lines is the
#: measured point the view still answers inside the GUI deadline. The pure gate lives in
#: `diff_rows()`, so no caller can run an unbounded comparison.
DIFF_MAX_LINES = 4000

#: How long the GUI waits for ONE comparison before it answers the refusal: a worker result that
#: lands after it is STALE (the generation token drops it). The number is the declared patience of
#: the view, not a cost model — the LINE budget is what bounds the work itself.
DIFF_BUDGET_MS = 1200

#: A pair at or under this line count is computed INLINE (a bounded, sub-frame cost); a larger one
#: goes to `_DiffEngine`'s thread, so the GUI thread never computes an unbounded diff.
DIFF_INLINE_MAX_LINES = 200

#: The ONE alpha of the block fill and of the stronger intra-line fill — the hue is the THEME's.
DIFF_TINT_ALPHA = 48
DIFF_INLINE_ALPHA = 110

DiffRow = namedtuple("DiffRow",
                     "left_no left_text right_no right_text tag left_spans right_spans")
DiffTarget = namedtuple("DiffTarget", "key label load")


def diff_targets_from_pages(pages) -> list:
    """The `Send to ▾ Diff` targets of a container's session pages — ONE record per live session.

    PURE over the pages it is handed (the map window's `_terminal_windows`, the standalone
    surface's `session_tabs`): a page without a Diff door or without an identity is skipped and a
    dead C++ object never hides the rest. The key is the session's `history_key()` — the same fact
    the Files container files its directory memory under, and what tells the source session from a
    foreign one (`DIFF.md` §3).
    """
    try:
        from .command_history import history_key
    except ImportError:
        from command_history import history_key  # type: ignore
    targets = []
    for page in list(pages or ()):
        try:
            loader = getattr(page, "load_into_diff", None)
            if not callable(loader) or getattr(page, "_is_split_pane", False):
                continue
            data = getattr(page, "server_data", None)
            key = history_key(getattr(data, "id", ""))
            if not key:
                continue
            label = getattr(data, "alias", "") or getattr(data, "host", "") or "?"
            targets.append(DiffTarget(key=key, label=label, load=loader))
        except Exception:  # noqa: BLE001 — one dead session never hides the rest
            continue
    return targets


def diff_targets_for(container) -> list:
    """The `Send to ▾ Diff` targets of ONE Files container — the host provider over the PARENT chain.

    `modules/*` never imports `ui.main_window` (§4.1): the provider is the map window's
    `_diff_targets()` or the standalone surface's, found by `find_host_hook()`; a detached container
    answers nothing. The SOURCE session is included on purpose — two files of one server are a normal
    comparison. Never raises.
    """
    if container is None:
        return []
    provider = find_host_hook(container, "_diff_targets")
    if not callable(provider):
        return []
    try:
        targets = provider() or []
    except Exception:  # noqa: BLE001 — a broken provider must not break the menu
        return []
    return [target for target in targets
            if target is not None and callable(getattr(target, "load", None))]


# ── The pure engine ─────────────────────────────────────────────────────────

class DiffBudgetExceeded(Exception):
    """The pair is over the engine's declared line budget — REFUSED before `SequenceMatcher`.

    Raised by `diff_rows()` itself, so every caller (the inline path, the engine thread, a probe)
    meets the same gate. `lines` is the pair's total line count, `limit` the declared bound.
    """

    def __init__(self, lines=0, limit=DIFF_MAX_LINES):
        self.lines = int(lines or 0)
        self.limit = int(limit or DIFF_MAX_LINES)
        super().__init__(f"diff budget: {self.lines} lines over {self.limit}")


def split_lines(text) -> list:
    """The lines of ONE side (`str.splitlines()` — a CRLF and an LF copy are the same content)."""
    return str(text if text is not None else "").splitlines()


def intra_spans(left: str, right: str) -> tuple:
    """`(left_spans, right_spans)` of the changed character runs of ONE replaced line pair.

    PURE over `difflib.SequenceMatcher`; every span is a `(start, end)` pair of character offsets.
    A line over `INLINE_MAX_CHARS`, or a pair over `INLINE_MAX_SPANS` spans, answers two empty tuples:
    the LINE mark is the declared fallback, never a frozen GUI.
    """
    left, right = str(left or ""), str(right or "")
    if len(left) > INLINE_MAX_CHARS or len(right) > INLINE_MAX_CHARS:
        return (), ()
    left_spans, right_spans = [], []
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if i2 > i1:
            left_spans.append((i1, i2))
        if j2 > j1:
            right_spans.append((j1, j2))
        if len(left_spans) + len(right_spans) > INLINE_MAX_SPANS:
            return (), ()
    return tuple(left_spans), tuple(right_spans)


def utf16_spans(text, spans) -> tuple:
    """Convert code-point span offsets to the UTF-16 code units `QTextCursor` counts (`N130`).

    A non-BMP character (an emoji, an Ext-B CJK glyph) is ONE Python character and TWO UTF-16
    units, so a raw offset taken from the string lands on the wrong character — or past the block
    when enough of them precede the change. PURE; a span outside the line is dropped.
    """
    source = str(text or "")
    units = {}

    def _offset(index: int) -> int:
        if index not in units:
            units[index] = len(source[:index].encode("utf-16-le", "surrogatepass")) // 2
        return units[index]

    out = []
    for span in spans or ():
        try:
            start, end = int(span[0]), int(span[1])
        except (TypeError, ValueError, IndexError):
            continue
        if 0 <= start < end <= len(source):
            out.append((_offset(start), _offset(end)))
    return tuple(out)


def diff_rows(left_text, right_text, max_lines=None) -> list:
    """The ALIGNED rows of two texts — line granularity plus the intra-line spans of a pair.

    A `replace` opcode pairs the lines one by one (`TAG_CHANGE`), and the excess of either side
    becomes `TAG_DELETE` / `TAG_INSERT` rows; an equal run is `TAG_EQUAL`. No row is fabricated: a
    side that has no line for a row answers `None`, and `side_blocks()` turns it into a gap.

    The pair's TOTAL line count is checked against `DIFF_MAX_LINES` BEFORE `SequenceMatcher` runs:
    an input over it raises `DiffBudgetExceeded` (`N127`), never a frozen window.
    """
    left, right = split_lines(left_text), split_lines(right_text)
    limit = DIFF_MAX_LINES if max_lines is None else int(max_lines)
    if limit > 0 and len(left) + len(right) > limit:
        raise DiffBudgetExceeded(len(left) + len(right), limit)
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                rows.append(DiffRow(i1 + k + 1, left[i1 + k], j1 + k + 1, right[j1 + k],
                                    TAG_EQUAL, (), ()))
        elif tag == "delete":
            for k in range(i1, i2):
                rows.append(DiffRow(k + 1, left[k], None, None, TAG_DELETE, (), ()))
        elif tag == "insert":
            for k in range(j1, j2):
                rows.append(DiffRow(None, None, k + 1, right[k], TAG_INSERT, (), ()))
        else:  # replace
            paired = min(i2 - i1, j2 - j1)
            for k in range(paired):
                spans_l, spans_r = intra_spans(left[i1 + k], right[j1 + k])
                rows.append(DiffRow(i1 + k + 1, left[i1 + k], j1 + k + 1, right[j1 + k],
                                    TAG_CHANGE, spans_l, spans_r))
            for k in range(i1 + paired, i2):
                rows.append(DiffRow(k + 1, left[k], None, None, TAG_DELETE, (), ()))
            for k in range(j1 + paired, j2):
                rows.append(DiffRow(None, None, k + 1, right[k], TAG_INSERT, (), ()))
    return rows


def side_blocks(rows, side: str) -> list:
    """The blocks ONE editor carries: `(line_no | None, text, tag, spans)` — one per row.

    The counts of the two answers are equal by construction, which is what keeps the two editors
    scrollable in lockstep (`DIFF.md` §5).
    """
    right = side == DIFF_RIGHT
    blocks = []
    for row in rows:
        number = row.right_no if right else row.left_no
        text = row.right_text if right else row.left_text
        spans = row.right_spans if right else row.left_spans
        if number is None:
            blocks.append((None, "", TAG_GAP, ()))
        else:
            blocks.append((number, text, row.tag, spans))
    return blocks


def diff_stats(rows) -> dict:
    """The three counters of ONE row list: `{"added": n, "removed": n, "changed": n}`."""
    stats = {"added": 0, "removed": 0, "changed": 0}
    for row in rows:
        if row.tag == TAG_INSERT:
            stats["added"] += 1
        elif row.tag == TAG_DELETE:
            stats["removed"] += 1
        elif row.tag == TAG_CHANGE:
            stats["changed"] += 1
    return stats


# ── The bounded local read ──────────────────────────────────────────────────

def read_local_side(path: str, cap=0) -> tuple:
    """`(data, total, code)` of ONE local file — the bounded read of a Diff side.

    The ceiling TRUNCATES (`cap` bytes, the shipped `MAX_READ_BYTES` when the caller answers 0), the
    extension screen and the NULL byte of the first chunk refuse a binary file (`"binary"`), and a
    path the OS cannot read answers `"read"`. Never raises.
    """
    try:
        limit = int(cap or 0) or MAX_READ_BYTES
    except (TypeError, ValueError):
        limit = MAX_READ_BYTES
    try:
        total = max(0, int(os.path.getsize(str(path or ""))))
    except (OSError, TypeError, ValueError):
        total = 0
    if classify_extension(path) == "binary":
        return b"", total, "binary"
    try:
        with open(str(path), "rb") as handle:
            data = handle.read(limit)
    except (OSError, TypeError, ValueError):
        return b"", total, "read"
    if b"\x00" in data[:8192]:
        return b"", total, "binary"
    return data, total, ""


def _viewer_cap() -> int:
    """The SHIPPED `ui_viewer_max_bytes` ceiling (`sftp_tab` owns its resolver)."""
    try:
        try:
            from .sftp_tab import resolve_viewer_max_bytes
        except ImportError:
            from sftp_tab import resolve_viewer_max_bytes  # type: ignore
        return int(resolve_viewer_max_bytes())
    except Exception:  # noqa: BLE001 — a build without the Files tab keeps the shipped floor
        return MAX_READ_BYTES


def _read_was_truncated(data_len, cap, known_size=0) -> bool:
    """The shipped truncation predicate (`sftp_tab.read_was_truncated`, the ONE reader)."""
    try:
        try:
            from .sftp_tab import read_was_truncated
        except ImportError:
            from sftp_tab import read_was_truncated  # type: ignore
        return bool(read_was_truncated(data_len, cap, known_size))
    except Exception:  # noqa: BLE001
        try:
            return int(known_size or 0) > int(data_len or 0)
        except (TypeError, ValueError):
            return False


def _claim_spool(name: str = "") -> str:
    """Claim ONE temp copy through the SHIPPED spool family; "" — the temp folder refused it."""
    path = send.create_spool(str(name or ""))
    if not path or not send.prepare_spool(path):
        send.drop_spool(path)
        return ""
    return path


def _drop_spool(path: str) -> int:
    """Delete a spool and its provisional twin (the shipped family); never raises."""
    if not path:
        return 0
    try:
        return int(send.drop_spool(path) or 0)
    except Exception:  # noqa: BLE001 — a temp file is not worth a traceback
        return 0


def _tint(color, alpha) -> QColor:
    """The theme's colour with the ONE declared alpha of a mark (`DIFF.md` §6)."""
    value = QColor(color)
    value.setAlpha(int(alpha))
    return value


def _fills() -> dict:
    """The block fills by tag — the ACTIVE theme's status colours and surface, re-read on every pass."""
    return {TAG_CHANGE: _tint(theme.STATUS_WARN, DIFF_TINT_ALPHA),
            TAG_DELETE: _tint(theme.STATUS_OFFLINE, DIFF_TINT_ALPHA),
            TAG_INSERT: _tint(theme.STATUS_ONLINE, DIFF_TINT_ALPHA),
            TAG_GAP: QColor(theme.SURFACE_ALT)}


class _DiffEngine(QObject):
    """The tab's ONE background engine — a daemon thread, a queue and a GENERATION token (`N127`).

    `diff_rows()` on a repetitive pair is superlinear (measured: 4 000 lines ≈ 72 s), so above
    `DIFF_INLINE_MAX_LINES` the tab never calls it on the GUI thread. The thread is a plain
    daemon `threading.Thread`: a `QThread` would have to be joined at exit (`AGENTS.md` §4.8) and
    the matcher cannot be interrupted mid-call, while this answer is simply DROPPED when its
    generation is stale — the section's declared cancellation. The Qt emission is guarded against a
    tab that is already gone (the `SftpWorker._emit` discipline).
    """

    ready = Signal(int, list)     # generation, rows
    refused = Signal(int, str)    # generation, "lines" | "error"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._asks = queue.Queue()
        self._latest = 0          # the generation of the LAST ask — an int, atomic under the GIL
        self._stop = False        # the tab is gone — the daemon thread ends at the next idle tick
        self._thread = None

    def compute(self, generation: int, left_text, right_text):
        """Queue ONE comparison; a newer generation makes every older answer stale."""
        generation = int(generation)
        self._latest = generation
        self._asks.put((generation, str(left_text or ""), str(right_text or "")))
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="DiffEngine", daemon=True)
            self._thread.start()

    def cancel(self):
        """Abandon every answer in flight (a newer ask owns the view) — the thread stays alive."""
        self._latest = -1

    def close(self):
        """The tab's teardown: abandon every answer AND let the daemon thread end."""
        self._latest = -1
        self._stop = True

    def _run(self):
        while not self._stop:
            try:
                generation, left_text, right_text = self._asks.get(timeout=0.25)
            except queue.Empty:
                continue   # an idle engine — the next ask wakes it, `close()` ends it
            except Exception:  # noqa: BLE001 — a closed queue ends the thread, never a crash
                return
            if generation != self._latest:
                continue   # superseded before it started
            try:
                rows = diff_rows(left_text, right_text)
            except DiffBudgetExceeded:
                answer = (self.refused, generation, "lines")
            except Exception:  # noqa: BLE001 — an engine fault is a refusal, never a crash
                answer = (self.refused, generation, "error")
            else:
                answer = (self.ready, generation, rows)
            if generation != self._latest:
                continue   # superseded while it computed — the answer is never published
            self._emit(*answer)

    def _emit(self, signal, *args):
        """Emit from the engine thread into a possibly-deleted widget — a no-op, never a crash."""
        try:
            signal.emit(*args)
        except RuntimeError:
            pass


class DiffTab(QWidget):
    """The `Diff` tab: two sides, one engine, one summary (`DIFF.md` §1-§6)."""

    #: A sentence for the session's status bridge (a refused read, a waiting channel).
    message = Signal(str)

    def __init__(self, page=None, parent=None):
        super().__init__(parent if parent is not None else page)
        self._page = page
        self._shut_down = False
        self._cap = _viewer_cap()
        self._codec = resolve_viewer_encoding()
        self._codec_frozen = False
        self._sides = {side: {"text": None, "loaded": False, "name": "", "path": "",
                              "source": "", "encoding": "", "total": 0, "shown": 0,
                              "truncated": False, "error": "", "reading": ""}
                       for side in DIFF_SIDES}
        self._rows = []
        self._blocks = {side: [] for side in DIFF_SIDES}
        self._editors = {}
        self._headers = {}
        self._buttons = {}
        self._pending_reads = {}    # (worker, task_id) -> (side, seq, path, size, name)
        self._pending_spools = {}   # (worker, task_id) -> (side, seq, path, spool, name, size)
        self._side_seq = {side: 0 for side in DIFF_SIDES}   # a late answer never lands on a newer side
        self._spools = []
        self._workers = []
        self._engine = _DiffEngine(self)
        self._engine.ready.connect(self._on_engine_ready)
        self._engine.refused.connect(self._on_engine_refused)
        self._render_seq = 0        # the generation a pending answer must carry
        self._rendering = False     # the engine owns the marks of the loaded pair right now
        self._render_name = ""      # the side the running comparison was asked for
        self._render_lines = 0       # the pair's total line count of that comparison
        self._budget_error = ""     # the engine's refusal sentence ("" — none)
        self._syncing = False
        self._build_ui()
        self.retranslate()

    # ── the widget ──────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        for side in DIFF_SIDES:
            self.splitter.addWidget(self._build_column(side))
        layout.addWidget(self.splitter, 1)
        self.summary_label = QLabel("", self)
        layout.addWidget(self.summary_label)
        self._connect_scroll()

    def _build_column(self, side: str) -> QWidget:
        column = QWidget(self.splitter)
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(2)
        header = QLabel("", column)
        header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        self._headers[side] = header
        inner.addWidget(header)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        btn_local = QPushButton("", column)
        btn_clear = QPushButton("", column)
        btn_local.clicked.connect(lambda _checked=False, s=side: self._choose_local(s))
        btn_clear.clicked.connect(lambda _checked=False, s=side: self.clear_side(s))
        row.addWidget(btn_local)
        row.addWidget(btn_clear)
        row.addStretch(1)
        inner.addLayout(row)
        self._buttons[(side, "local")] = btn_local
        self._buttons[(side, "clear")] = btn_clear
        editor = QPlainTextEdit(column)
        editor.setReadOnly(True)
        editor.setUndoRedoEnabled(False)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setFont(QFont(theme.FONT_MONO))
        editor.setTabChangesFocus(False)
        self._editors[side] = editor
        inner.addWidget(editor, 1)
        return column

    def _connect_scroll(self):
        """Synchronise the two vertical scrollbars on the BLOCK index (`DIFF.md` §6)."""
        left, right = self._editors[DIFF_LEFT], self._editors[DIFF_RIGHT]
        left.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_scroll(DIFF_LEFT, value))
        right.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_scroll(DIFF_RIGHT, value))

    def _sync_scroll(self, source: str, value: int):
        if self._syncing:
            return
        target = self._editors[DIFF_RIGHT if source == DIFF_LEFT else DIFF_LEFT]
        self._syncing = True
        try:
            bar = target.verticalScrollBar()
            if bar.value() != value:
                bar.setValue(int(value))
        finally:
            self._syncing = False

    # ── the readers ─────────────────────────────────────────────────────────

    def load_side(self, side, entry) -> bool:
        """Fill ONE side from an entry — the ONE loading door of the tab (`DIFF.md` §3).

        `entry` is `{"kind": "local" | "remote" | "spool", "path", "name", "size", "worker",
        "track"}`. Answers False on a refusal; nothing is queued twice for one side. `track` is the
        SOURCE pane of a spool leg: the leg joins its Cancel bookkeeping (`N129`).
        """
        if self._shut_down:
            return False
        side = side if side in DIFF_SIDES else DIFF_LEFT
        entry = dict(entry or {})
        path = str(entry.get("path") or "")
        if not path:
            self._say("diff.error_read", name=str(entry.get("name") or "?"))
            return False
        name = str(entry.get("name") or os.path.basename(path) or path)
        kind = str(entry.get("kind") or "local")
        self._budget_error = ""     # a new side is a new question — the old refusal is gone
        self._side_seq[side] = int(self._side_seq.get(side, 0)) + 1
        seq = self._side_seq[side]
        if kind == "local":
            return self._load_local(side, path, name)
        if kind == "remote":
            return self._queue_read(side, entry.get("worker"), path, int(entry.get("size") or 0),
                                    name, seq)
        if kind == "spool":
            return self._queue_spool(side, entry.get("worker"), path, int(entry.get("size") or 0),
                                     name, seq, entry.get("track"))
        self._say("diff.error_read", name=name)
        return False

    def _load_local(self, side: str, path: str, name: str) -> bool:
        data, total, code = read_local_side(path, self._cap)
        if code == "binary":
            self._side_error(side, "diff.error_binary", name)
            return False
        if code:
            self._side_error(side, "diff.error_read", name)
            return False
        self._set_side(side, data, total, name, path)
        return True

    def _queue_read(self, side: str, worker, path: str, size: int, name: str, seq: int = 0) -> bool:
        if worker is None:
            self._say("sftp.waiting_connection")
            return False
        self._bind_worker(worker)
        try:
            task_id = worker.queue_read(path, int(size or 0), max_bytes=self._cap)
        except (RuntimeError, AttributeError):
            task_id = None
        if task_id is None:
            self._say("sftp.waiting_connection")
            return False
        self._pending_reads[(worker, int(task_id))] = (side, int(seq), path, int(size or 0), name)
        self._set_reading(side, name)
        return True

    def _queue_spool(self, side: str, worker, path: str, size: int, name: str,
                     seq: int = 0, track=None) -> bool:
        """Copy a FOREIGN file into the shipped spool — REFUSED over the viewer cap (`N128`).

        The download has no byte bound of its own, so the size gate runs BEFORE `queue_download()`:
        a file the listing reports over `ui_viewer_max_bytes` never becomes a spool, and the answer
        is the shipped read refusal (`sftp.viewer.read_failed` over `sftp.viewer.too_large`).
        """
        if worker is None:
            self._say("sftp.waiting_connection")
            return False
        size = int(size or 0)
        if self._cap > 0 and size > self._cap:
            self._side_error(side, "sftp.viewer.read_failed", name,
                             error=_t("sftp.viewer.too_large", limit=format_size(self._cap)))
            return False
        spool = _claim_spool(name)
        if not spool:
            self._side_error(side, "diff.error_read", name)
            return False
        self._spools.append(spool)
        self._bind_worker(worker)
        try:
            task_id = worker.queue_download(
                path, os.path.dirname(spool), total_size=size,
                local_name=os.path.basename(spool), part_mode=int(send.SPOOL_FILE_MODE))
        except (RuntimeError, AttributeError):
            task_id = None
        if task_id is None:
            self._drop_spool_copy(spool)
            self._say("sftp.waiting_connection")
            return False
        self._pending_spools[(worker, int(task_id))] = (side, int(seq), path, spool, name, size)
        self._track_leg(track, task_id)   # the source pane's Cancel covers the leg (`N129`)
        self._set_reading(side, name)
        return True

    def _bind_worker(self, worker):
        """Bind ONCE to the source worker's four answers (`read_ready` / done / error / cancelled)."""
        if worker is None or any(worker is bound for bound in self._workers):
            return
        try:
            worker.read_ready.connect(self._on_read_ready)
            worker.task_done.connect(self._on_task_done)
            worker.task_error.connect(self._on_task_error)
            worker.task_cancelled.connect(self._on_task_cancelled)
        except (RuntimeError, AttributeError):
            return
        self._workers.append(worker)

    def _unbind_workers(self):
        """Drop every worker connection of this tab (its spools are settled by then)."""
        for worker in list(self._workers):
            for signal, slot in ((getattr(worker, "read_ready", None), self._on_read_ready),
                                 (getattr(worker, "task_done", None), self._on_task_done),
                                 (getattr(worker, "task_error", None), self._on_task_error),
                                 (getattr(worker, "task_cancelled", None), self._on_task_cancelled)):
                if signal is None:
                    continue
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):  # noqa: BLE001 — teardown of a dead object: the slot was never connected
                    pass   # not connected / the C++ object is already gone
        self._workers.clear()

    def _emitting_worker(self):
        """The worker that EMITTED the answer being handled — None outside a slot (`N125`).

        A slot may not read "the worker this tab holds now": two sides may be filled from two
        workers whose task ids collide, and `sender()` is Qt's ONE answer to WHICH object spoke.
        """
        try:
            return self.sender()
        except (AttributeError, RuntimeError):
            return None

    def _leg_key(self, pending_map, task_id):
        """The `(worker, task_id)` key of the leg that answered — None when it is not ours.

        A direct call (a test, a teardown) has no sender: the answer is then taken only when EXACTLY
        ONE pending leg carries that number, so an ambiguous id is never guessed.
        """
        worker = self._emitting_worker()
        if worker is not None:
            key = (worker, int(task_id))
            return key if key in pending_map else None
        matches = [key for key in pending_map if key[1] == int(task_id)]
        return matches[0] if len(matches) == 1 else None

    def _track_leg(self, track, task_id):
        """Register a spool leg with the SOURCE pane's Cancel — the shipped button, no second one."""
        register = getattr(track, "track_transfer", None)
        if not callable(register):
            return
        try:
            register(int(task_id))
        except (RuntimeError, AttributeError, TypeError, ValueError):  # noqa: BLE001 — teardown of a dead object: a dead widget is not cancellable
            pass   # a dead widget is already "not cancellable"

    def _on_read_ready(self, task_id, remote_path, data):
        key = self._leg_key(self._pending_reads, task_id)
        if key is None:
            return
        pending = self._pending_reads.pop(key, None)
        if self._shut_down:
            return
        side, seq, path, size, name = pending
        if int(seq) != self._side_seq.get(side):
            return   # a newer load owns this side — a late answer never overwrites it
        self._set_side(side, bytes(data), size, name, path)

    def _on_task_done(self, task_id, detail=""):
        key = self._leg_key(self._pending_spools, task_id)
        if key is None:
            return
        pending = self._pending_spools.pop(key, None)
        side, seq, path, spool, name, size = pending
        if self._shut_down:
            self._drop_spool_copy(spool)   # the answer that lands owns the copy past `shutdown()`
            self._drain_workers()
            return
        if int(seq) != self._side_seq.get(side):
            self._drop_spool_copy(spool)
            return   # a newer load owns this side — the copy goes unread
        data, total, code = read_local_side(spool, self._cap)
        self._drop_spool_copy(spool)
        if code == "binary":
            self._side_error(side, "diff.error_binary", name)
            return
        if code:
            self._side_error(side, "diff.error_read", name)
            return
        self._set_side(side, data, size or total, name, path)

    def _on_task_error(self, task_id, kind, message):
        key = self._leg_key(self._pending_spools, task_id)
        if key is not None:
            pending = self._pending_spools.pop(key, None)
            self._drop_spool_copy(pending[3])
            if self._shut_down:
                self._drain_workers()
                return
            if int(pending[1]) == self._side_seq.get(pending[0]):
                self._side_error(pending[0], "diff.error_read", pending[4])
            return
        key = self._leg_key(self._pending_reads, task_id)
        if key is None:
            return
        pending = self._pending_reads.pop(key, None)
        if self._shut_down or int(pending[1]) != self._side_seq.get(pending[0]):
            return
        error_key = ("diff.error_binary" if str(message or "") == READ_ERROR_BINARY
                     else "diff.error_read")
        self._side_error(pending[0], error_key, pending[4])

    def _on_task_cancelled(self, task_id, kind):
        key = self._leg_key(self._pending_spools, task_id)
        if key is not None:
            pending = self._pending_spools.pop(key, None)
            self._drop_spool_copy(pending[3])
            if self._shut_down:
                self._drain_workers()
                return
            if int(pending[1]) == self._side_seq.get(pending[0]):
                self._clear_reading(pending[0])
            return
        key = self._leg_key(self._pending_reads, task_id)
        if key is None:
            return
        pending = self._pending_reads.pop(key, None)
        if not self._shut_down and int(pending[1]) == self._side_seq.get(pending[0]):
            self._clear_reading(pending[0])

    def _drain_workers(self):
        """Unbind the workers once a torn-down tab holds no leg any more — the ONE drain point."""
        if self._shut_down and not self._pending_spools and not self._pending_reads:
            self._unbind_workers()

    def _drop_spool_copy(self, spool):
        """Drop ONE spool and forget it (the copy never outlives the decode — `DIFF.md` §3)."""
        try:
            self._spools.remove(spool)
        except ValueError:  # noqa: BLE001 — best effort (declared): a double drop
            pass
        _drop_spool(spool)

    # ── the side state ──────────────────────────────────────────────────────

    def _set_side(self, side, data, total, name, path):
        truncated = _read_was_truncated(len(data), self._cap, total)
        text, used = self._decode(data, truncated)
        state = self._sides[side]
        state.update({"text": text, "loaded": True, "name": name, "path": path, "encoding": used,
                      "total": int(total or 0), "shown": len(data), "truncated": bool(truncated),
                      "error": "", "reading": ""})
        self._render_name = str(name or "")
        self._budget_error = ""
        self._render()

    def _decode(self, data, truncated) -> tuple:
        """The ONE codec of BOTH sides, resolved once (`DIFF.md` §4)."""
        if not self._codec_frozen:
            self._codec = resolve_viewer_encoding()
            if self._codec == "auto":
                try:
                    bytes(data).decode("utf-8-sig")
                    self._codec = "utf-8"
                except UnicodeDecodeError:
                    self._codec = "latin-1"
            self._codec_frozen = True
        return decode_text(bytes(data), truncated=bool(truncated), encoding=self._codec)

    def _set_reading(self, side, name):
        state = self._sides[side]
        state["reading"] = str(name or "")
        state["error"] = ""
        self._refresh_header(side)

    def _clear_reading(self, side):
        self._sides[side]["reading"] = ""
        self._refresh_header(side)

    def _side_error(self, side, key, name, **kwargs):
        state = self._sides[side]
        state.update({"text": None, "loaded": False,
                      "error": _t(key, name=str(name or "?"), **kwargs),
                      "reading": "", "name": "", "path": ""})
        self._budget_error = ""
        self._render()
        self.message.emit(str(state["error"]))

    def clear_side(self, side):
        """Forget ONE side (its text, its marks and any leg still in flight) — the other side stays."""
        side = side if side in DIFF_SIDES else DIFF_LEFT
        self._side_seq[side] = int(self._side_seq.get(side, 0)) + 1
        self._sides[side].update({"text": None, "loaded": False, "name": "", "path": "",
                                  "encoding": "", "total": 0, "shown": 0, "truncated": False,
                                  "error": "", "reading": ""})
        self._budget_error = ""
        self._render()

    def _choose_local(self, side):
        path, _selected = QFileDialog.getOpenFileName(self, _t("diff.load_local"))
        if not path:
            return
        self.load_side(side, {"kind": "local", "path": str(path)})

    # ── the view ────────────────────────────────────────────────────────────

    def _render(self):
        """Rebuild both editors from the two sides — the ONE writer of the text and the marks.

        A pair at or under `DIFF_INLINE_MAX_LINES` is computed INLINE (a bounded, sub-frame cost);
        a larger one is handed to `_DiffEngine` and the text is shown without marks until its
        answer lands (`N127`). The answer is accepted only for the generation it was asked for, so
        a newer side, a Clear and a teardown all drop it.
        """
        both = self._sides[DIFF_LEFT]["loaded"] and self._sides[DIFF_RIGHT]["loaded"]
        if not both:
            self._cancel_engine()
            self._rows = []
            self._blocks = {}
            for side in DIFF_SIDES:
                state = self._sides[side]
                lines = split_lines(state["text"]) if state["loaded"] else []
                self._blocks[side] = [(index + 1, line, TAG_EQUAL, ())
                                      for index, line in enumerate(lines)]
            self._paint_columns()
            self._update_status()
            return
        left_text = self._sides[DIFF_LEFT]["text"]
        right_text = self._sides[DIFF_RIGHT]["text"]
        pair_lines = len(split_lines(left_text)) + len(split_lines(right_text))
        if pair_lines <= DIFF_INLINE_MAX_LINES:
            self._cancel_engine()
            try:
                self._apply_rows(diff_rows(left_text, right_text))
            except DiffBudgetExceeded:
                self._refuse_engine("lines", pair_lines)
            return
        self._start_engine(left_text, right_text, pair_lines)

    def _paint_columns(self):
        """Write both editors from `_blocks` and paint their marks — the ONE document writer."""
        for side in DIFF_SIDES:
            blocks = self._blocks.get(side) or []
            editor = self._editors[side]
            values = editor.verticalScrollBar().value()
            editor.setPlainText("\n".join(str(block[1]) for block in blocks))
            self._apply_marks(side)
            editor.verticalScrollBar().setValue(values)
            self._refresh_header(side)

    def _apply_rows(self, rows):
        """Take ONE finished comparison: the rows, the two aligned block lists and the marks."""
        self._rendering = False
        self._budget_error = ""
        self._rows = list(rows or [])
        self._blocks = {DIFF_LEFT: side_blocks(self._rows, DIFF_LEFT),
                        DIFF_RIGHT: side_blocks(self._rows, DIFF_RIGHT)}
        self._paint_columns()
        self._update_status()

    def _start_engine(self, left_text, right_text, pair_lines=0):
        """Hand a large pair to the engine thread and show its text until the marks arrive."""
        self._render_seq += 1
        seq = self._render_seq
        self._rendering = True
        self._render_lines = int(pair_lines or 0)
        self._budget_error = ""
        self._rows = []
        self._blocks = {}
        for side in DIFF_SIDES:
            state = self._sides[side]
            lines = split_lines(state["text"]) if state["loaded"] else []
            self._blocks[side] = [(index + 1, line, TAG_EQUAL, ())
                                  for index, line in enumerate(lines)]
        self._paint_columns()
        self._update_status()
        self._engine.compute(seq, left_text, right_text)
        QTimer.singleShot(int(DIFF_BUDGET_MS), lambda: self._on_engine_deadline(seq))

    def _cancel_engine(self):
        """Abandon whatever the engine is computing — its answer belongs to an older view."""
        self._render_seq += 1
        self._rendering = False
        self._engine.cancel()

    def _on_engine_deadline(self, seq):
        """The GUI's declared patience ran out — refuse the comparison, drop the late answer."""
        try:
            if self._shut_down or not self._rendering or int(seq) != self._render_seq:
                return
            self._refuse_engine("time", self._render_lines)
        except RuntimeError:
            pass   # Qt teardown — a dying tab may not speak

    def _on_engine_ready(self, seq, rows):
        if self._shut_down or not self._rendering or int(seq) != self._render_seq:
            return   # a stale answer of an older side, a Clear or a teardown
        self._apply_rows(rows)

    def _on_engine_refused(self, seq, reason):
        if self._shut_down or not self._rendering or int(seq) != self._render_seq:
            return
        self._refuse_engine(str(reason or "error"), None)

    def _refuse_engine(self, reason, pair_lines):
        """One shipped sentence in place of the marks (`N127`) — never a silently frozen window.

        The sentence is the viewer's own `sftp.viewer.too_large`; its `{limit}` is the DECLARED line
        budget for a pair that crossed it, and the pair's own line count when the TIME budget was
        the one that ran out.
        """
        self._rendering = False
        self._render_seq += 1
        self._engine.cancel()
        self._rows = []
        limit = DIFF_MAX_LINES if pair_lines is None else int(pair_lines)
        self._budget_error = _t("sftp.viewer.too_large", limit=limit)
        self._update_status()
        self.message.emit(self._budget_error)

    def _apply_marks(self, side):
        """Paint the block fills and the intra-line spans of ONE editor (`DIFF.md` §6).

        The span offsets are PYTHON character offsets; `QTextCursor` counts UTF-16 code units, so
        every span is converted first (`utf16_spans()`, `N130`).
        """
        editor = self._editors[side]
        blocks = self._blocks.get(side) or []
        fills = _fills()
        block = editor.document().begin()
        for entry in blocks:
            if not block.isValid():
                break
            tag, spans, text = entry[2], entry[3], str(entry[1])
            fill = fills.get(tag)
            if fill is not None:
                block_format = QTextBlockFormat()
                block_format.setBackground(QBrush(fill))
                cursor = QTextCursor(block)
                cursor.setBlockFormat(block_format)
            if spans:
                inline = _tint(theme.STATUS_WARN, DIFF_INLINE_ALPHA)
                for start, end in utf16_spans(text, spans):
                    if end <= start:
                        continue
                    cursor = QTextCursor(block)
                    cursor.setPosition(block.position() + int(start))
                    cursor.setPosition(block.position() + int(end), QTextCursor.MoveMode.KeepAnchor)
                    char_format = QTextCharFormat()
                    char_format.setBackground(QBrush(inline))
                    cursor.setCharFormat(char_format)
            block = block.next()

    def _refresh_header(self, side):
        state = self._sides[side]
        side_name = _t("diff.side.left" if side == DIFF_LEFT else "diff.side.right")
        if state["error"]:
            text = f"{side_name} · {state['error']}"
        elif state["reading"]:
            text = _t("sftp.viewer.reading", name=state["reading"])
        elif not state["loaded"]:
            text = side_name
        else:
            size_text = format_size(state["shown"])
            if state["truncated"]:
                size_text = _t("sftp.viewer.truncated", shown=size_text,
                               total=format_size(state["total"]))
            text = _t("diff.header", side=side_name, name=state["name"], size=size_text)
            if state["encoding"] and self._codec not in ("", "auto") \
                    and state["encoding"] != self._codec:
                text = f"{text} · " + _t("sftp.viewer.encoding_failed", encoding=self._codec,
                                         fallback=state["encoding"])
        self._headers[side].setText(text)
        self._headers[side].setToolTip(str(state["path"] or ""))

    def _update_status(self):
        t = _t
        both = self._sides[DIFF_LEFT]["loaded"] and self._sides[DIFF_RIGHT]["loaded"]
        one = self._sides[DIFF_LEFT]["loaded"] or self._sides[DIFF_RIGHT]["loaded"]
        error = (self._sides[DIFF_LEFT]["error"] or self._sides[DIFF_RIGHT]["error"])
        if error:
            text = error
        elif self._budget_error:
            text = self._budget_error
        elif both and self._rendering:
            text = t("sftp.viewer.reading", name=self._render_name or "?")
        elif both:
            stats = diff_stats(self._rows)
            if not any(stats.values()):
                text = t("diff.same")
            else:
                text = t("diff.stats", added=stats["added"], removed=stats["removed"],
                         changed=stats["changed"])
        elif one:
            text = t("diff.need_other")
        else:
            text = t("diff.empty")
        if self._codec and self._codec != "auto":
            text = f"{text} · " + t("diff.encoding", encoding=self._codec)
        self.summary_label.setText(text)

    def retranslate(self):
        """Re-text the tab's own chrome (the page re-texts the tab title)."""
        for side in DIFF_SIDES:
            self._buttons[(side, "local")].setText(_t("diff.load_local"))
            self._buttons[(side, "local")].setToolTip(_t("diff.load_local"))
            self._buttons[(side, "clear")].setText(_t("diff.clear"))
            self._buttons[(side, "clear")].setToolTip(_t("diff.clear"))
            self._editors[side].setPlaceholderText(_t("diff.empty"))
            self._refresh_header(side)
        self._update_status()

    def refresh_theme(self):
        """Re-apply the fills of the ACTIVE theme to the documents on the screen."""
        if self._shut_down:
            return
        for side in DIFF_SIDES:
            self._apply_marks(side)

    def shutdown(self):
        """The ONE teardown: cancel the engine, settle the spools and unbind the workers.

        A spool leg IN FLIGHT is not forgotten (`N129`): it keeps its entry and its slots, so the
        answer that lands drops the copy it publishes (the archive's abandoned-leg pattern), and
        the workers are unbound once the last such answer arrives (`_drain_workers()`). A read is
        memory only, so its pending map simply goes.
        """
        if self._shut_down:
            return
        self._shut_down = True
        self._cancel_engine()
        self._engine.close()
        pending = {value[3] for value in self._pending_spools.values()}
        for spool in list(self._spools):
            if spool not in pending:
                self._drop_spool_copy(spool)
        self._pending_reads.clear()
        if not self._pending_spools:
            self._unbind_workers()

    # ── the read seams (the tests and the session) ──────────────────────────

    def side_state(self, side) -> dict:
        """The CURRENT state of ONE side (a copy — the caller cannot mutate it)."""
        return dict(self._sides[side if side in DIFF_SIDES else DIFF_LEFT])

    def rows(self) -> list:
        """The rows on the screen (`[]` while one side alone is loaded)."""
        return list(self._rows)

    def blocks(self, side) -> list:
        """The blocks ONE editor carries — `(line_no, text, tag, spans)` per block."""
        return list(self._blocks.get(side) or [])

    def status_text(self) -> str:
        """The summary line as it reads now."""
        return str(self.summary_label.text())

    def header_text(self, side) -> str:
        """The header line of ONE side as it reads now."""
        return str(self._headers[side].text())

    def _say(self, key, **kwargs):
        """One sentence through the tab's message signal (the page's status bridge)."""
        try:
            self.message.emit(_t(key, **kwargs))
        except RuntimeError:
            pass   # Qt teardown — a dying widget may not speak
