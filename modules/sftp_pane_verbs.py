# -*- coding: utf-8 -*-
"""The READER's own verbs: the find bar and the background hue of ONE Files pane (v1.14.1).

`SftpViewerVerbsMixin` adds the two controls the preview lacked to the panel `SftpPaneViewerMixin`
builds: a find bar over the reader's DOCUMENT (`Ctrl+F`, `Enter` / `Shift+Enter`, `Esc`, a `k / N`
counter — `QTextDocument.find()` is the search, so no second engine exists; the query is DEBOUNCED
and a match stores its UTF-16 pair) and the background chip that paints the surface with the hue of
`ui_viewer_background` (ONE painter with the chip: `theme_qss.viewer_background_qss`). The bar is a
ROW of the panel (re-seeded on every new document), the chip a 22 px header control; the hue is read
by the PURE `modules/sftp_pane_helpers.py`, the presets by `ui/accent_presets.py`.

Contract — `SFTP_PANES.md` §3b, `AGENTS.md` §4.15; mechanism — `DOCUMENTATION.md` §38.
"""
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton,
                               QWidget)

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # v1.4.3: the ONE QSS registry — the find card and the reader's surface
    from ..ui import theme_qss
except ImportError:
    try:
        from ui import theme_qss
    except ImportError:  # a stripped build — the global rules stand
        theme_qss = None

try:  # the surface the reader's hue is derived from (a pure, Qt-free module)
    from ..ui import theme as theme_module
except ImportError:
    try:
        from ui import theme as theme_module
    except ImportError:  # a stripped build — the chip keeps the widget's own fill
        theme_module = None

try:  # AGENTS.md §4.1: the ONE seam for a facade global — a mixin never imports the facade module
    from ..ui.mixin_support import host_attr
except ImportError:
    from ui.mixin_support import host_attr

try:  # the PURE hue reader of the pane family
    from .sftp_pane_helpers import (VIEWER_BACKGROUND_PRESETS, resolve_viewer_background,
                                    viewer_background_hue)
except ImportError:  # flat launch from the project root
    from sftp_pane_helpers import (VIEWER_BACKGROUND_PRESETS,  # type: ignore
                                   resolve_viewer_background, viewer_background_hue)

try:  # the ONE log of this module — a failed config write is said ONCE (AGENTS.md §4.15)
    from .logger import get_logger
except ImportError:
    try:
        from modules.logger import get_logger
    except ImportError:  # pragma: no cover — a stripped build logs nowhere
        import logging

        def get_logger(name):  # noqa: N802 — the same signature
            return logging.getLogger(name)

log = get_logger(__name__)

#: The matches the counter walks before it stops counting — a `QTextDocument.find()` per hit over a
#: 1 MB file would be O(n²), so the total is a DECLARED bound and the counter says "N+" when a
#: FURTHER hit exists past it.
VIEWER_FIND_MATCH_MAX = 2000

#: The debounce of the query field, in milliseconds: a burst of keystrokes runs ONE scan per pause, so
#: a document at the reader's 250 MiB ceiling is never walked per character typed (declared window
#: 150..250 ms — `tests/test_followups_v11412.py` §4 drives the burst).
VIEWER_FIND_DEBOUNCE_MS = 180

#: The inset of the bar's own layout, in pixels, and the chip's side (the header's cross is 24 px).
VIEWER_FIND_MARGIN = 4
VIEWER_BACKGROUND_CHIP_PX = 22


def persist_viewer_background(host, hue) -> bool:
    """Write the ONE hue through the host's own door and answer whether it was STORED (N154).

    The write's ANSWER is the contract: a surface painted from a key that was never written shows a
    colour the next build forgets, so both callers — the chip's pane and the container's walk — leave
    the surface AND the chip at the old hue when this answers False, and the log carries ONE line.
    """
    try:
        stored = bool(host_attr(host, "save_viewer_background")(hue))
    except (RuntimeError, TypeError, AttributeError):
        stored = False
    if not stored:
        log.warning("the reader's background %r was not stored — the readers keep their own", hue)
    return stored


class ViewerTextView(QPlainTextEdit):
    """The reader's TEXT — it OWNS its keys (v1.14.1.1).

    `Ctrl+F` is claimed through `QEvent.ShortcutOverride` (the canvas's `_owns_shortcut()` precedent).
    A widget-scoped `QShortcut` here is the trap: with `view.find_on_map` on the window (`Ctrl+F`,
    `WindowShortcut`), Qt 6.11 answers `Ambiguous shortcut overload` and fires NEITHER. An accepted
    override takes the key out of the shortcut map's way, and `keyPressEvent()` opens the bar — the
    pane's `open_viewer_find()` is reached through `find_requested`.
    """

    find_requested = Signal()

    @staticmethod
    def _owns_find_key(event) -> bool:
        """Is this event the reader's own `Ctrl+F` (the ONE spelling both handlers read)?"""
        return (event.key() == Qt.Key.Key_F
                and event.modifiers() == Qt.KeyboardModifier.ControlModifier)

    def event(self, event):  # noqa: N802 — Qt's own spelling
        if event.type() == QEvent.Type.ShortcutOverride and self._owns_find_key(event):
            event.accept()   # the key is MINE — the window action must not be asked
            return True
        return super().event(event)

    def keyPressEvent(self, event):  # noqa: N802 — Qt's own spelling
        if self._owns_find_key(event):
            self.find_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _ViewerFindLineEdit(QLineEdit):
    """The query field: `Enter` — next, `Shift+Enter` — previous, `Esc` — close.

    A SUBCLASS, never a patched slot (`AGENTS.md` §7): `returnPressed` fires for both keys and does
    not carry the modifiers, so the three keys are read here — the `terminal_find_bar.py` shape.
    """

    next_pressed = Signal()
    prev_pressed = Signal()
    close_pressed = Signal()

    def keyPressEvent(self, event):  # noqa: N802 — Qt's own spelling
        key = int(event.key())
        if key in (int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter)):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.prev_pressed.emit()
            else:
                self.next_pressed.emit()
            event.accept()
            return
        if key == int(Qt.Key.Key_Escape):
            self.close_pressed.emit()
            event.accept()   # no "beep": Esc is a meaningful action here
            return
        super().keyPressEvent(event)


class ViewerFindBar(QWidget):
    """The find row of the reader: `[query] ["k / N"] [▲] [▼] [×]` — a child of the panel's layout.

    The widget holds NO search state: it emits and the pane decides (the `TerminalFindBar` contract).
    `retranslate()` and `refresh_theme()` are the two walks a language or a theme switch makes.
    """

    query_changed = Signal(str)
    next_requested = Signal()
    prev_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ViewerFindBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(theme_qss.style("viewer_find_bar") if theme_qss is not None else "")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(VIEWER_FIND_MARGIN, 2, VIEWER_FIND_MARGIN, 2)
        layout.setSpacing(6)
        self.query_edit = _ViewerFindLineEdit(self)
        self.query_edit.textChanged.connect(self.query_changed.emit)
        self.query_edit.next_pressed.connect(self.next_requested)
        self.query_edit.prev_pressed.connect(self.prev_requested)
        self.query_edit.close_pressed.connect(self.close_requested)
        self.count_label = QLabel("", self)
        self.btn_prev = QPushButton("\u25b2", self)   # ▲
        self.btn_next = QPushButton("\u25bc", self)   # ▼
        self.btn_close = QPushButton("\u00d7", self)  # ×
        for button in (self.btn_prev, self.btn_next, self.btn_close):
            button.setFixedSize(20, 20)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_prev.clicked.connect(self.prev_requested)
        self.btn_next.clicked.connect(self.next_requested)
        self.btn_close.clicked.connect(self.close_requested)
        layout.addWidget(self.query_edit, 1)
        layout.addWidget(self.count_label, 0)
        layout.addWidget(self.btn_prev, 0)
        layout.addWidget(self.btn_next, 0)
        layout.addWidget(self.btn_close, 0)
        self._count = (0, None)   # no query yet — the first paint owes the EMPTY state, not "No matches"
        self.retranslate()
        self.hide()

    def retranslate(self):
        """Re-text the placeholder, the three tooltips and the counter (a language switch)."""
        self.query_edit.setPlaceholderText(_t("sftp.find.placeholder"))
        self.btn_prev.setToolTip(_t("sftp.find.prev"))
        self.btn_next.setToolTip(_t("sftp.find.next"))
        self.btn_close.setToolTip(_t("sftp.viewer.close_tooltip"))
        self.set_count(*self._count)

    def set_count(self, current: int, total=None):
        """The counter: `k / N` (or `k / N+` past the bound), `No matches`, or NOTHING.

        `total` is `None` while the field is EMPTY — no query means no sentence at all; `0` is a query
        that really found nothing; a STRING (`"2000+"`) is the bound that has a FURTHER hit past it,
        said instead of a count the walk never reached.
        """
        self._count = (int(current), total)
        if total is None:
            self.count_label.setText("")
            return
        if isinstance(total, int) and total <= 0:
            self.count_label.setText(_t("search.no_results"))
            return
        self.count_label.setText(_t("sftp.find.count", cur=int(current), total=total))

    def set_query(self, text: str):
        """Re-seed the field with `text` and NO signal — the pane owns the state, not `textChanged`."""
        blocked = self.query_edit.blockSignals(True)
        try:
            self.query_edit.setText(str(text or ""))
        finally:
            self.query_edit.blockSignals(blocked)

    def refresh_theme(self):
        """Re-read the find card's stylesheet (a theme switch). Never raises."""
        if theme_qss is not None:
            theme_qss.refresh(self, "viewer_find_bar")

    def focus_input(self):
        """Focus the field and select its text (a quick re-query)."""
        self.query_edit.setFocus()
        self.query_edit.selectAll()


class SftpViewerVerbsMixin:
    """The reader's find bar and background chip (mixed into `_SftpPane`)."""

    # ── the two controls (installed once, by the pane's assembly) ────────

    def _setup_viewer_verbs(self):
        """Install the reader's own controls — the `Ctrl+F` owner and the background chip.

        Called ONCE by the pane's assembly, after the reader panel exists: the reader's TEXT owns
        the key (`ViewerTextView`, so no window action is re-bound), the object name is what the
        `viewer.background` QSS rule selects, and the stored hue is applied at build time so an open
        Files tab wears the user's surface from its first paint. A stored value that is not a hue is
        REFUSED once — and that sentence is DEFERRED to the next event-loop turn, because a signal
        emitted from this constructor stage has no receiver yet (`_new_pane()` connects
        `pane.message` after it, the page later still — `AGENTS.md` §4.15).
        """
        try:
            self.viewer_text.setObjectName("SftpViewerText")
            self.viewer_text.find_requested.connect(self.open_viewer_find)
        except (RuntimeError, AttributeError):
            return   # Qt teardown / a reader substituted by a stub — nothing to install on
        self._viewer_find_matches = []
        self._viewer_find_current = -1
        self._viewer_find_query = ""
        self._viewer_find_more = False
        self._viewer_find_bar = None
        # The debounce: ONE single-shot timer, restarted by every keystroke, so a burst runs ONE scan.
        self._viewer_find_timer = QTimer(self)
        self._viewer_find_timer.setSingleShot(True)
        self._viewer_find_timer.setInterval(VIEWER_FIND_DEBOUNCE_MS)
        self._viewer_find_timer.timeout.connect(self._run_viewer_find_scan)
        self._apply_stored_viewer_background(deferred=True)

    def _apply_stored_viewer_background(self, deferred: bool = False):
        """Read `ui_viewer_background` ONCE and paint the reader — the refusal is said HERE.

        Called by the setup (`deferred=True`: the message has no receiver before the container and
        the page are wired) and by a re-read (a suite drives the refusal through it, synchronously).
        A value that is not a hue leaves the theme's own surface and answers
        `sftp.viewer.background_refused` once.
        """
        hue, refused = resolve_viewer_background()
        self._viewer_background = hue
        self._apply_viewer_background(hue)
        if not refused:
            return
        if deferred:
            QTimer.singleShot(0, self._say_viewer_background_refused)
        else:
            self._say_viewer_background_refused()

    def _say_viewer_background_refused(self):
        """Say the ONE refusal sentence — never raises (a queued turn may outlive the pane)."""
        try:
            self.message.emit(_t("sftp.viewer.background_refused"))
        except RuntimeError:
            pass   # Qt teardown — the reader is already gone, so the sentence has no audience

    # ── the find bar (`Ctrl+F`) ──────────────────────────────────────────

    def _ensure_viewer_find_bar(self):
        """The find row, created on the first `Ctrl+F` and inserted under the reader's header."""
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is not None:
            return bar
        bar = ViewerFindBar(self.viewer)
        bar.query_changed.connect(self._schedule_viewer_find)
        bar.next_requested.connect(self.viewer_find_next)
        bar.prev_requested.connect(self.viewer_find_prev)
        bar.close_requested.connect(self.close_viewer_find)
        layout = self.viewer.layout()
        if layout is not None:
            layout.insertWidget(1, bar)   # index 0 is the header row (the label and the two controls)
        self._viewer_find_bar = bar
        return bar

    def open_viewer_find(self):
        """`Ctrl+F`: show the bar over the reader and focus its field (idempotent)."""
        if not getattr(self, "_viewer_open", False):
            return   # nothing to search — the bar belongs to a file on the screen
        bar = self._ensure_viewer_find_bar()
        selection = self.viewer_selection()
        if selection and not bar.query_edit.text():
            bar.query_edit.setText(selection)   # the selection is the first question
        bar.show()
        bar.focus_input()
        if bar.query_edit.text().strip():
            self._on_viewer_find_query(bar.query_edit.text())

    def close_viewer_find(self, restore_focus: bool = True):
        """Hide the bar and drop its matches (`Esc`, `×`, a new file, the panel's own close).

        `restore_focus` is TRUE for the user's own close (the keyboard returns to the text) and
        FALSE from `close_viewer()`: the panel is going away and a focus change there would fire the
        APP-level `focusChanged` hook of the container — the mark of a session's own state has no
        business moving because a preview closed (the `_sync_commander` cascade).
        """
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is not None:
            try:
                bar.hide()
            except RuntimeError:
                self._viewer_find_bar = bar = None   # the C++ object is gone
        self._reset_viewer_find()
        if not restore_focus:
            return
        try:
            self.viewer_text.setFocus()
        except RuntimeError:
            pass   # the C++ object was already destroyed (a close race)

    @property
    def viewer_find_active(self) -> bool:
        """Is the find bar open? (`isHidden()`, never `isVisible()` — the offscreen-pane rule)."""
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is None:
            return False
        try:
            return not bar.isHidden()
        except RuntimeError:
            return False

    def viewer_find_state(self) -> dict:
        """`{"query", "current" (1-based), "total"}` — the topical seam of the bar."""
        total = len(getattr(self, "_viewer_find_matches", None) or [])
        current = int(getattr(self, "_viewer_find_current", -1)) + 1 if total else 0
        return {"query": str(getattr(self, "_viewer_find_query", "") or ""),
                "current": current, "total": total}

    def viewer_selection(self) -> str:
        """The SELECTED text of the reader, stripped ("" — no selection). Untrusted by definition."""
        try:
            return str(self.viewer_text.textCursor().selectedText() or "").strip()
        except RuntimeError:
            return ""

    def _on_viewer_find_query(self, text: str):
        """The query was ASKED for (a door, not a keystroke): a fresh match list, the first hit.

        The field is brought in line with the query (signals blocked): every entry point searches for
        what the bar SHOWS, or a re-run of `_refit_viewer_find()` would find nothing to repeat.
        """
        self._viewer_find_query = str(text or "")
        self._stop_viewer_find_scan()
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is not None and bar.query_edit.text() != self._viewer_find_query:
            try:
                bar.set_query(self._viewer_find_query)
            except RuntimeError:
                self._viewer_find_bar = None
        self._refresh_viewer_find_matches()

    def _schedule_viewer_find(self, text: str):
        """A KEYSTROKE: keep the query and let the debounce run ONE pass after the pause."""
        self._viewer_find_query = str(text or "")
        timer = getattr(self, "_viewer_find_timer", None)
        if timer is None:
            self._refresh_viewer_find_matches()
            return
        timer.start(VIEWER_FIND_DEBOUNCE_MS)   # restarting IS the coalescing of a burst

    def _stop_viewer_find_scan(self):
        """Drop a pending debounced pass (a door that searches NOW supersedes it). Never raises."""
        timer = getattr(self, "_viewer_find_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except RuntimeError:
                self._viewer_find_timer = None

    def _run_viewer_find_scan(self):
        """The debounce's ONE pass — the timer stopped coalescing the keystrokes."""
        self._refresh_viewer_find_matches()

    def _flush_viewer_find_scan(self):
        """Run a PENDING debounced pass NOW — a step walks the field's query, not the last list.

        Inside the window the query is already the new one while the match list is the previous
        query's (`AGENTS.md` §4.15). A pane with no timer searches through its door instead.
        """
        timer = getattr(self, "_viewer_find_timer", None)
        if timer is None:
            return
        try:
            pending = timer.isActive()
            if pending:
                timer.stop()
        except RuntimeError:
            self._viewer_find_timer = None
            return
        if pending:
            self._refresh_viewer_find_matches()

    def _refresh_viewer_find_matches(self):
        """Collect the matches of the query (bounded) and show the first one.

        `QTextDocument.find()` walks forward from a cursor, so ONE pass collects the matches in
        document order, each as its `(selectionStart, selectionEnd)` PAIR — `QTextCursor` positions
        are UTF-16 units, so `start + len(query)` would select nothing for every non-BMP character.
        The walk stops at `VIEWER_FIND_MATCH_MAX`; ONE further find() decides whether the counter may
        say `N+` (a bound met by EXACTLY N hits is `N`, never `N+`).
        """
        query = self._viewer_find_query.strip()
        matches = []
        self._viewer_find_more = False
        try:
            document = self.viewer_text.document()
        except RuntimeError:
            return   # Qt teardown — nothing to search
        if query:
            cursor = QTextCursor(document)
            while len(matches) < VIEWER_FIND_MATCH_MAX:
                cursor = document.find(query, cursor)
                if cursor.isNull():
                    break
                matches.append((cursor.selectionStart(), cursor.selectionEnd()))
            self._viewer_find_more = (len(matches) >= VIEWER_FIND_MATCH_MAX
                                      and not document.find(query, cursor).isNull())
        self._viewer_find_matches = matches
        self._viewer_find_current = 0 if matches else -1
        if matches:
            self._reveal_viewer_find_match()
        self._sync_viewer_find_counter()

    def _sync_viewer_find_counter(self):
        """Push the counter into the bar — an empty field says nothing, the bound says `N+`."""
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is None:
            return
        total = len(getattr(self, "_viewer_find_matches", None) or [])
        if not str(getattr(self, "_viewer_find_query", "") or "").strip():
            shown = None   # no query at all — the bar has no sentence to give
        elif total and getattr(self, "_viewer_find_more", False):
            shown = f"{VIEWER_FIND_MATCH_MAX}+"
        else:
            shown = total
        try:
            bar.set_count(self._viewer_find_current + 1 if total else 0, shown)
        except RuntimeError:
            self._viewer_find_bar = None   # the bar is already destroyed

    def _reveal_viewer_find_match(self):
        """Select the current match and scroll it into view (the selection IS the highlight)."""
        matches = getattr(self, "_viewer_find_matches", None) or []
        index = int(getattr(self, "_viewer_find_current", -1))
        if not (0 <= index < len(matches)):
            return
        start, end = matches[index]
        try:
            cursor = QTextCursor(self.viewer_text.document())
            cursor.setPosition(int(start))
            cursor.setPosition(int(end), QTextCursor.MoveMode.KeepAnchor)
            self.viewer_text.setTextCursor(cursor)
            self.viewer_text.centerCursor()
        except RuntimeError:
            return   # Qt teardown — the reveal is cosmetic

    def viewer_find_next(self) -> bool:
        """`Enter`: the next match, wrapping around to the first; False — no matches."""
        return self._step_viewer_find(1)

    def viewer_find_prev(self) -> bool:
        """`Shift+Enter`: the previous match, wrapping around to the last one."""
        return self._step_viewer_find(-1)

    def _step_viewer_find(self, delta: int) -> bool:
        """Move by `delta` through the matches with WRAPAROUND (the terminal bar's rule).

        A pending debounced pass is FLUSHED first: `Enter` inside the debounce window would otherwise
        walk the PREVIOUS query's list while the field shows the new one.
        """
        self._flush_viewer_find_scan()
        total = len(getattr(self, "_viewer_find_matches", None) or [])
        if total <= 0:
            self._sync_viewer_find_counter()
            return False
        self._viewer_find_current = (int(self._viewer_find_current) + int(delta)) % total
        self._reveal_viewer_find_match()
        self._sync_viewer_find_counter()
        return True

    def _refit_viewer_find(self):
        """The document CHANGED: the bar that stays visible must tell the truth about the new one.

        A visible bar is re-seeded from its own field: `_reset_viewer_find()` clears the stale query
        (signals blocked) and the pass then re-runs the SAME query over the document on the screen, so
        a visible "No matches" is never left over a document it did not search, and `Enter` steps
        again. A closed bar costs one dict lookup.
        """
        bar = getattr(self, "_viewer_find_bar", None)
        query = ""
        if bar is not None:
            try:
                query = str(bar.query_edit.text() or "")
            except RuntimeError:
                self._viewer_find_bar = bar = None
        self._reset_viewer_find()
        if bar is None or not query.strip():
            return
        try:
            bar.set_query(query)   # signals blocked — the re-run below is the pane's, not a keystroke
        except RuntimeError:
            self._viewer_find_bar = None
            return
        self._on_viewer_find_query(query)

    def _reset_viewer_find(self):
        """Forget the matches (the document they index into is about to change). Never raises."""
        self._viewer_find_matches = []
        self._viewer_find_current = -1
        self._viewer_find_query = ""
        self._viewer_find_more = False
        self._stop_viewer_find_scan()
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is None:
            return
        try:
            bar.set_query("")       # the field never keeps a query no match list was built from
            bar.set_count(0, None)  # an empty field says nothing — not "No matches"
        except RuntimeError:
            self._viewer_find_bar = None

    # ── the background hue (`ui_viewer_background`) ──────────────────────

    @property
    def viewer_background_hue(self):
        """The hue the reader's surface is painted with — None while it is the theme's own."""
        hue = self.__dict__.get("_viewer_background")
        if hue is None:
            hue = resolve_viewer_background()[0]
            self._viewer_background = hue
        return hue

    def set_viewer_background(self, hue, persist: bool = True):
        """Apply ONE hue to this reader's surface (`None` — the theme's own look).

        The hue is NORMALISED by the pure reader, so a hand-edited value never reaches the QSS
        builder; `persist` writes the ONE key of the reader's family. A write that FAILS leaves the
        surface and the chip at the old hue and is said once — the answer is the whole point.
        Returns the hue the reader wears afterwards.
        """
        resolved = viewer_background_hue(hue)[0]
        if persist and not persist_viewer_background(self, resolved):
            return self.viewer_background_hue
        self._viewer_background = resolved
        self._apply_viewer_background(resolved)
        return resolved

    def _apply_viewer_background(self, hue):
        """Paint the reader with `hue` and mirror it on the chip — the ONE painter of BOTH (N154).

        The surface is built from the hue ARGUMENT (`theme_qss.viewer_background_qss`), never re-read
        from the config: the config is persistence only, so a switch, a second container's write and
        a failed save all leave the chip and the surface on the same colour by construction.
        """
        if theme_qss is not None and theme_module is not None:
            try:
                self.viewer_text.setStyleSheet(
                    theme_qss.viewer_background_qss(hue, str(theme_module.THEME.base_bg)))
            except RuntimeError:
                return   # Qt teardown — the panel is already gone
        self._paint_viewer_background_chip(hue)

    def _paint_viewer_background_chip(self, hue):
        """Mirror the CURRENT hue on the header's chip (its fill is the colour it installs)."""
        chip = getattr(self, "btn_viewer_background", None)
        if chip is None or theme_qss is None or theme_module is None:
            return
        try:
            base = str(theme_module.THEME.base_bg)
            fill = base if hue is None else theme_qss.viewer_background_hex(hue, base)
            chip.setStyleSheet(theme_qss.accent_swatch_style(fill))
        except (RuntimeError, AttributeError, TypeError):
            return   # Qt teardown / a stripped build without the registry

    def _build_background_menu(self):
        """The chip's menu: `Theme` plus the eight PRESET hues (the accent vocabulary).

        A test seam like every other `_build_*_menu()`: a suite triggers the `QAction`s directly.
        """
        menu = QMenu(self)
        theme_action = menu.addAction(_t("sftp.viewer.background_theme"))
        theme_action.setCheckable(True)
        theme_action.setChecked(self.viewer_background_hue is None)
        theme_action.triggered.connect(lambda _checked=False: self._on_background_chosen(None))
        menu.addSeparator()
        current = self.viewer_background_hue
        for name, hue in VIEWER_BACKGROUND_PRESETS:
            action = menu.addAction(_t(f"settings.appearance.accent.{name}"))
            action.setCheckable(True)
            action.setChecked(current is not None and int(current) == int(round(hue)))
            action.triggered.connect(lambda _checked=False, h=hue: self._on_background_chosen(h))
        return menu

    def _on_viewer_background_clicked(self):
        """The chip: show its menu at the chip (the event is the only caller of the seam)."""
        try:
            menu = self._build_background_menu()
            menu.exec(self.btn_viewer_background.mapToGlobal(
                self.btn_viewer_background.rect().bottomLeft()))
            menu.deleteLater()
        except RuntimeError:
            return   # Qt teardown — the chip is already gone

    def _on_background_chosen(self, hue):
        """A menu row was picked: the CONTAINER writes the one key and walks every pane.

        The ASKING pane travels with the choice (`pane=self`): the applied sentence is answered to
        it, and the container emits only when a receiver exists — a global setting changed with no
        confirmation was the shipped defect (v1.14.1.1).
        """
        apply_all = getattr(self._container, "apply_viewer_background", None)
        if callable(apply_all):
            try:
                apply_all(hue, pane=self)
                return
            except RuntimeError:
                return   # Qt teardown — nothing to repaint
        self.set_viewer_background(hue)

    @staticmethod
    def background_name(hue) -> str:
        """The NAME of a hue in the menu's own vocabulary (translated; the hue itself otherwise)."""
        if hue is None:
            return _t("sftp.viewer.background_theme")
        for name, preset in VIEWER_BACKGROUND_PRESETS:
            if int(round(preset)) == int(hue):
                return _t(f"settings.appearance.accent.{name}")
        return str(int(hue))

    # ── the two walks a switch makes ─────────────────────────────────────

    def _retranslate_viewer_verbs(self):
        """Re-text the find bar and the chip (a language switch). Never raises."""
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is not None:
            try:
                bar.retranslate()
            except RuntimeError:
                self._viewer_find_bar = None
        chip = getattr(self, "btn_viewer_background", None)
        if chip is not None:
            try:
                chip.setToolTip(_t("sftp.viewer.background"))
            except RuntimeError:
                pass   # Qt teardown — the chip is already gone

    def _refresh_viewer_verbs(self):
        """Re-read the two registry styles after a theme switch (the chip follows the surface)."""
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is not None:
            try:
                bar.refresh_theme()
            except RuntimeError:
                self._viewer_find_bar = None
        self._apply_viewer_background(self.viewer_background_hue)
