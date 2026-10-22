# -*- coding: utf-8 -*-
"""The READER's own verbs: the find bar and the background hue of ONE Files pane (v1.14.1).

`SftpViewerVerbsMixin` adds the two controls the preview lacked to the panel `SftpPaneViewerMixin`
builds: a find bar over the reader's DOCUMENT (`Ctrl+F`, `Enter` / `Shift+Enter`, `Esc`, a `k / N`
counter — `QTextDocument.find()` is the search, so no second engine exists) and the background chip
that paints the reader's surface with the hue of `ui_viewer_background`. The bar is a ROW of the panel
(hidden until asked for), the chip a 22 px control in its header; neither covers the text. The hue is
read by the PURE `modules/sftp_pane_helpers.py`, the colour is the `viewer.background` builder of
`ui/theme_qss.py`.

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

#: The matches the counter walks before it stops counting — a `QTextDocument.find()` per hit over a
#: 1 MB file would be O(n²), so the total is a DECLARED bound and the counter says "N+" when it is met.
VIEWER_FIND_MATCH_MAX = 2000

#: The inset of the bar's own layout, in pixels, and the chip's side (the header's cross is 24 px).
VIEWER_FIND_MARGIN = 4
VIEWER_BACKGROUND_CHIP_PX = 22


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
        self._count = (0, 0)
        self.retranslate()
        self.hide()

    def retranslate(self):
        """Re-text the placeholder, the three tooltips and the counter (a language switch)."""
        self.query_edit.setPlaceholderText(_t("sftp.find.placeholder"))
        self.btn_prev.setToolTip(_t("sftp.find.prev"))
        self.btn_next.setToolTip(_t("sftp.find.next"))
        self.btn_close.setToolTip(_t("sftp.viewer.close_tooltip"))
        self.set_count(*self._count)

    def set_count(self, current: int, total):
        """The counter: `k / N` (or `k / N+` at the bound), the empty state when nothing matches.

        `total` may be a STRING (`"2000+"`) — the bound the walk met, said instead of a number it
        never reached, so the panel never presents a truncated count as the whole one.
        """
        self._count = (int(current), total)
        if isinstance(total, int) and total <= 0:
            self.count_label.setText(_t("search.no_results"))
            return
        self.count_label.setText(_t("sftp.find.count", cur=int(current), total=total))

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
        self._viewer_find_bar = None
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
        bar.query_changed.connect(self._on_viewer_find_query)
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
        """The query changed: a fresh match list over the WHOLE document, the first hit revealed."""
        self._viewer_find_query = str(text or "")
        self._refresh_viewer_find_matches()

    def _refresh_viewer_find_matches(self):
        """Collect the matches of the query (bounded) and show the first one.

        `QTextDocument.find()` walks forward from a cursor, so ONE pass collects the starts in
        document order; the walk stops at `VIEWER_FIND_MATCH_MAX` and the counter says the bound was
        met (`N+`) instead of presenting the number it stopped at as the whole one.
        """
        query = self._viewer_find_query.strip()
        matches = []
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
                matches.append(cursor.selectionStart())
        self._viewer_find_matches = matches
        self._viewer_find_current = 0 if matches else -1
        if matches:
            self._reveal_viewer_find_match()
        self._sync_viewer_find_counter()

    def _sync_viewer_find_counter(self):
        """Push the counter into the bar — the bound is said as `N+`, never as `N`."""
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is None:
            return
        total = len(getattr(self, "_viewer_find_matches", None) or [])
        shown = f"{VIEWER_FIND_MATCH_MAX}+" if total >= VIEWER_FIND_MATCH_MAX else total
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
        start = int(matches[index])
        try:
            cursor = QTextCursor(self.viewer_text.document())
            cursor.setPosition(start)
            cursor.setPosition(start + len(self._viewer_find_query.strip()),
                               QTextCursor.MoveMode.KeepAnchor)
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
        """Move by `delta` through the matches with WRAPAROUND (the terminal bar's rule)."""
        total = len(getattr(self, "_viewer_find_matches", None) or [])
        if total <= 0:
            self._sync_viewer_find_counter()
            return False
        self._viewer_find_current = (int(self._viewer_find_current) + int(delta)) % total
        self._reveal_viewer_find_match()
        self._sync_viewer_find_counter()
        return True

    def _reset_viewer_find(self):
        """Forget the matches (the document they index into is about to change)."""
        self._viewer_find_matches = []
        self._viewer_find_current = -1
        self._viewer_find_query = ""
        bar = getattr(self, "_viewer_find_bar", None)
        if bar is not None:
            try:
                bar.set_count(0, 0)
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
        builder; `persist` writes the ONE key of the reader's family. Returns the applied hue.
        """
        resolved = viewer_background_hue(hue)[0]
        self._viewer_background = resolved
        if persist:
            host_attr(self, "save_viewer_background")(resolved)
        self._apply_viewer_background(resolved)
        return resolved

    def _apply_viewer_background(self, hue):
        """Paint the reader with `hue` and mirror it on the chip — the ONE writer of the surface.

        The registry builder reads the SAME hue from the config, so this method is only the
        refresh: an empty hue leaves no rule at all and the global `QPlainTextEdit` look stands.
        """
        if theme_qss is not None:
            try:
                self.viewer_text.setStyleSheet(theme_qss.style("viewer.background"))
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
