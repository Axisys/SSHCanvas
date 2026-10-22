# -*- coding: utf-8 -*-
"""The four WIDGETS of a Files pane — the row, its listing, the row buttons and the source switch.

`_SftpRowItem` is the row class whose `__lt__` carries the two GROUP rules, `_SftpTree` the listing
that drags a row OUT (a subclass: `startDrag()` is a C++ slot), `_ButtonRow` the operation row as ONE
unit and `_SourceSwitch` the `Server | Local | Elevated` control; `_sync_source_switch()` is the ONE
call of every state change and `_apply_status_style()` the ONE muted-label style. The row roles, the
source vocabulary and the drag MIME come DOWNWARD from the pure `modules/sftp_pane_helpers.py`, and
this module never imports `modules/sftp_tab` (`AGENTS.md` §4.1): the facade re-exports every name.

Contract — `SFTP_PANES.md` §4; mechanism — `DOCUMENTATION.md` §59, §64, §68.
"""

import json

from PySide6.QtCore import QEvent, QMimeData, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QWidget)

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # the central theme (the muted-label fallback — ui/theme.py)
    from ..ui import theme
except ImportError:
    from ui import theme

try:  # the ONE QSS registry
    from ..ui import theme_qss
except ImportError:
    try:
        from ui import theme_qss
    except ImportError:  # flat layout: the ui/ directory itself is on sys.path
        theme_qss = None

try:  # the pure layer DOWNWARD: the sort table, the row readers and the pane's vocabulary
    from .sftp_pane_listing import SORT_COLUMNS, SORT_DEFAULT_COLUMN
    from .sftp_pane_helpers import (ISDIR_ROLE, MTIME_ROLE, PANE_DRAG_MIME, PATH_ROLE,
                                    SIZE_ROLE, SOURCE_ELEVATED, SOURCE_LOCAL, SOURCE_REMOTE,
                                    row_name, row_path)
except ImportError:  # flat launch from the project root
    from sftp_pane_listing import SORT_COLUMNS, SORT_DEFAULT_COLUMN
    from sftp_pane_helpers import (ISDIR_ROLE, MTIME_ROLE, PANE_DRAG_MIME, PATH_ROLE,
                                   SIZE_ROLE, SOURCE_ELEVATED, SOURCE_LOCAL, SOURCE_REMOTE,
                                   row_name, row_path)


#: The floor of the `_ButtonRow` wrapper, in pixels (the class docstring owns the story of the row).
BUTTONS_BAR_MIN_WIDTH = 0

#: The local pane's control and the sentence of its two structural refusals — declared ONCE.
LOCAL_SOURCE_LABEL = "sftp.local.source"
LOCAL_UNAVAILABLE_HINT = "sftp.local.unavailable"

#: v1.8: the elevated pane's third button of the SAME control (`ELEVATED_PANE.md` §4).
ELEVATED_SOURCE_LABEL = "sftp.elevated.button"
ELEVATED_SOURCE_TOOLTIP = "sftp.elevated.tooltip"


def _apply_status_style(widget, key: str) -> None:
    """v1.4.3: apply a muted status-label style from the registry.

    Falls back to the pre-v1.4.3 inline string when the Qt theme module is not
    importable (a flat run outside the project tree), so a status label is styled
    either way. Never raises: a missing registry key yields an empty stylesheet.
    """
    if theme_qss is not None:
        widget.setStyleSheet(theme_qss.style(key))
    else:
        widget.setStyleSheet(f"color: {theme.TEXT_MUTED}; padding: 2px 0;")


class _SftpRowItem(QTreeWidgetItem):
    """ONE row of a pane's listing, ordered by the ROLES (the tree asks this `__lt__`).

    Group rules — ANY column, ANY direction (`AGENTS.md` §4.3.6):
      * the ".." row (`pinned`) FIRST, then DIRECTORIES above the files;
      * the chosen COLUMN inside one group, then the path as the deterministic tie-break;
      * Qt is asked for `AscendingOrder` only — `_sort_column` / `_sort_desc` hold the direction.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: the ".." row — the ONE row no order may move (rule 1).
        self.pinned = False

    def sort_state(self):
        """`(column, descending)` of the pane this row is listed by — the DECLARED view state."""
        pane = getattr(self.treeWidget(), "pane", None)
        if pane is None:
            return SORT_DEFAULT_COLUMN, False
        column = getattr(pane, "_sort_column", SORT_DEFAULT_COLUMN)
        try:
            column = int(column)
        except (TypeError, ValueError):
            column = SORT_DEFAULT_COLUMN
        return (column if column in SORT_COLUMNS else SORT_DEFAULT_COLUMN,
                bool(getattr(pane, "_sort_desc", False)))

    def group_rank(self) -> int:
        """The GROUP of a row: 0 — the pinned ".." row, 1 — a directory, 2 — a file."""
        if getattr(self, "pinned", False):
            return 0
        try:
            return 1 if self.data(0, ISDIR_ROLE) else 2
        except (RuntimeError, AttributeError):
            return 2

    def sort_key(self, column: int):
        """The value of THIS row in `column`: the NAME, the SIZE or the MTIME, read off the ROLES."""
        role = {1: SIZE_ROLE, 2: MTIME_ROLE}.get(int(column))
        if role is not None:
            try:
                return int(self.data(0, role) or 0)
            except (RuntimeError, AttributeError, TypeError, ValueError):
                return 0
        try:
            # `lower()` is the provider's own key (`local_entries`, the worker's listing), so the
            # default order of a fresh listing and a click on the Name header agree to the character.
            return row_name(self).lower()
        except (RuntimeError, AttributeError):
            return ""

    def __lt__(self, other) -> bool:
        if not isinstance(other, _SftpRowItem):
            return False
        mine, theirs = self.group_rank(), other.group_rank()
        if mine != theirs:
            return mine < theirs          # the two GROUP rules, whatever the direction
        if mine == 0:
            return False                  # two pinned rows — the ".." row never moves
        column, descending = self.sort_state()
        my_key = self.sort_key(column)
        other_key = other.sort_key(column)
        if my_key == other_key:
            # A stable tie-break: the full PATH of the row, so two rows that share a size or an
            # mtime keep ONE deterministic order (the direction applies to it as well).
            my_key, other_key = row_path(self), row_path(other)
        return (my_key > other_key) if descending else (my_key < other_key)


class _SftpTree(QTreeWidget):
    """The listing tree of a PANE (v1.3.3.2): drag-OUT.

    A row can be dragged into a terminal, an editor or a chat window: the drag
    payload is the REMOTE PATH of the row as `text/plain` (the file itself is not
    transferred). A SUBCLASS, because `startDrag()` is a C++ slot — runtime
    monkey-patching is forbidden (Qt gotcha #7).

    `drag_mime(item)` builds the payload on its own, which is the seam the tests
    read (a real drag needs an event loop and a drop target).

    v1.7rc1: the tree also REPORTS the keyboard focus (`focus_in`), which is what makes
    a pane become the ACTIVE pane of the container — the ring is drawn on the tree, so
    a click in a pane has to move it.

    v1.7rc3: the tree hands the KEYS it does not own to the pane (`pane_key`), so the walk of
    the two-pane view (`Tab`/`Shift+Tab`, `Enter`, `Insert`/`Space`, `Left`) is decided in ONE
    place (`_SftpPane._on_pane_key`) whether the event comes from the tree or from the pane's
    `eventFilter`. The tree's own navigation (the arrows, `Home`/`End`, type-ahead, the
    multi-selection modifiers) stays Qt's.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.focus_in = None   # a zero-argument callable — set by the owning pane
        self.pane_key = None   # a one-argument callable (the key event) — set by the pane
        self.pane = None       # v1.7.3: the pane this tree lists (the drag payload's identity)

    def keyPressEvent(self, event):
        """Hand the key to the pane first (v1.7rc3); False — Qt's own tree behaviour."""
        hook = self.pane_key
        if hook is not None:
            try:
                if hook(event):
                    return
            except RuntimeError:
                pass  # Qt teardown — the owner is already gone
        super().keyPressEvent(event)

    def event(self, event):
        """Catch `Tab`/`Shift+Tab` BEFORE Qt's focus walk consumes them (v1.7rc3).

        A shown `QTreeWidget` never hands `Tab` to `keyPressEvent()`: Qt's own focus framework
        answers the key first, so the mc/far pane toggle has to be intercepted one level higher,
        in `event()` — the SAME seam the terminal canvas uses for its claimed keys
        (`QEvent.ShortcutOverride` / `_owns_shortcut()`, §4.3). The pane's hook answers False for
        everything that is not part of the walk, so `Tab` in a SINGLE-pane tab still moves the
        focus the ordinary way.
        """
        hook = self.pane_key
        if hook is not None and event.type() in (QEvent.Type.KeyPress,
                                                 QEvent.Type.ShortcutOverride):
            try:
                key = int(event.key())
            except (AttributeError, TypeError, ValueError):
                key = -1
            if key in (int(Qt.Key.Key_Tab), int(Qt.Key.Key_Backtab)):
                try:
                    if hook(event):
                        event.accept()
                        return True
                except RuntimeError:
                    pass  # Qt teardown — the owner is already gone
        return super().event(event)

    def startDrag(self, supported_actions):
        mime = self.drag_mime(self.currentItem())
        if mime is None:
            return
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def drag_mime(self, item):
        """The drag payload of a row: the path as text/plain, plus the PANE identity.

        None — nothing to drag (no row / a row without a path). v1.7.3: the private
        `PANE_DRAG_MIME` carries `{session, pane, path}` so a drop INSIDE a pane can tell which
        pane the row came from (two servers can show the same path) and refuse a foreign session —
        while `text/plain` keeps the plain path for every foreign target. v1.7.4rc2: a LOCAL row
        also hands out a real OS path (`text/uri-list`, the Explorer contract) and the payload
        DECLARES its source dialect, so the drop never guesses which spelling it received.
        """
        if item is None:
            return None
        path = item.data(0, PATH_ROLE)
        if not path:
            return None
        mime = QMimeData()
        mime.setText(str(path))
        pane = self.pane
        if pane is not None:
            payload = {"session": pane.session_key(), "pane": id(pane), "path": str(path),
                       "source": pane.source,
                       "size": int(item.data(0, SIZE_ROLE) or 0)}
            mime.setData(PANE_DRAG_MIME, json.dumps(payload).encode("utf-8"))
            if pane.source == SOURCE_LOCAL:
                mime.setUrls([QUrl.fromLocalFile(str(path))])
        return mime

    def focusInEvent(self, event):
        """v1.7rc1: the tree took the keyboard — tell the pane (the ACTIVE pane rule)."""
        super().focusInEvent(event)
        hook = self.focus_in
        if hook is not None:
            try:
                hook()
            except RuntimeError:
                pass  # Qt teardown — the owner is already gone


class _ButtonRow(QWidget):
    """The pane's button row as ONE widget (v1.7rc3) — the two-pane view needs it as a unit.

    The FIRST pane keeps the row, the SECOND hides it for the key hints. A bare `QWidget` would
    report its LAYOUT's whole minimum (five buttons) as the pane's, which raises the terminal
    WINDOW's floor, so a narrow window that clips the row refuses to shrink. The row therefore
    shrinks and CLIPS: the floor is `BUTTONS_BAR_MIN_WIDTH`, the HEIGHT keeps the layout's hint.
    """

    def minimumSizeHint(self):  # noqa: N802 — Qt's own spelling
        try:
            height = self.layout().minimumSize().height() if self.layout() is not None else 0
        except RuntimeError:
            height = 0
        return QSize(BUTTONS_BAR_MIN_WIDTH, height)


class _SourceSwitch(QWidget):
    """The `Server | Local | Elevated` control of the pane's address row (v1.7.4rc1, LOCAL_PANE.md §4).

    ONE checkable group driving ONE state (the `CommanderCorner` discipline: the buttons are
    views of `source`, so the look can never disagree with the provider the pane bound), and the
    label spells out WHAT is being switched — the pane's own source, not the session's. The widget
    only EMITS: the container decides whether the local and the elevated sources are available at
    all, and the pane translates the elevated token into "a REMOTE pane whose provider is elevated".
    """

    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = SOURCE_REMOTE
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        self.lbl = QLabel(_t(LOCAL_SOURCE_LABEL))
        _apply_status_style(self.lbl, "status.sftp_row")
        row.addWidget(self.lbl)
        self.btn_server = QToolButton()
        self.btn_local = QToolButton()
        self.btn_elevated = QToolButton()
        for button, source, key in ((self.btn_server, SOURCE_REMOTE, "sftp.local.server"),
                                    (self.btn_local, SOURCE_LOCAL, "sftp.local.local"),
                                    (self.btn_elevated, SOURCE_ELEVATED, ELEVATED_SOURCE_LABEL)):
            button.setText(_t(key))
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _checked=False, s=source: self._on_clicked(s))
            row.addWidget(button)
        self.btn_elevated.setToolTip(_t(ELEVATED_SOURCE_TOOLTIP))
        # v1.9.8: all THREE states say what they read — the elevated one had its tooltip
        # while its two neighbours had none, and a toggle without one is a riddle.
        self.btn_server.setToolTip(_t("sftp.local.server_tooltip"))
        self.btn_local.setToolTip(_t("sftp.local.local_tooltip"))
        self._apply_switch_style()
        self.apply(SOURCE_REMOTE)

    def _apply_switch_style(self):
        """Give the three states the declared contrast (`sftp.source_button`). Never raises.

        The inactive state of a source toggle is the one a user has to READ (the audit's finding),
        so the ink and the checked state come from the ONE registry instead of the platform style.
        """
        if theme_qss is None:
            return
        for button in (self.btn_server, self.btn_local, self.btn_elevated):
            try:
                theme_qss.refresh(button, "sftp.source_button")
            except RuntimeError:
                continue  # Qt teardown — this button is already destroyed

    def _on_clicked(self, source: str):
        if source == self._source:
            self.apply(source)   # a click on the state that already holds — the look is re-synced
            return
        self.changed.emit(source)

    def source(self) -> str:
        return self._source

    def apply(self, source: str):
        """Show ONE source as the live one (the state is written HERE and nowhere else)."""
        token = str(source or "")
        self._source = token if token in (SOURCE_LOCAL, SOURCE_ELEVATED) else SOURCE_REMOTE
        for button, value in ((self.btn_server, SOURCE_REMOTE), (self.btn_local, SOURCE_LOCAL),
                              (self.btn_elevated, SOURCE_ELEVATED)):
            try:
                button.setChecked(self._source == value)
            except RuntimeError:
                pass  # Qt teardown — the button is already gone

    def set_available(self, enabled: bool, available: bool = True):
        """Enable/disable the group and say WHY through the tooltip (never a silent dead control).

        The WIDGET itself is disabled as well as its parts, so the whole control reads as one
        (a disabled container with enabled children would be an ambiguous answer).
        """
        on = bool(enabled) and bool(available)
        for widget in (self, self.lbl, self.btn_server, self.btn_local, self.btn_elevated):
            try:
                widget.setEnabled(on)
            except RuntimeError:
                continue
        try:
            self.setToolTip("" if available else _t(LOCAL_UNAVAILABLE_HINT))
        except RuntimeError:
            pass

    def retranslate(self):
        try:
            self.lbl.setText(_t(LOCAL_SOURCE_LABEL))
            self.btn_server.setText(_t("sftp.local.server"))
            self.btn_local.setText(_t("sftp.local.local"))
            self.btn_elevated.setText(_t(ELEVATED_SOURCE_LABEL))
            self.btn_elevated.setToolTip(_t(ELEVATED_SOURCE_TOOLTIP))
            self.btn_server.setToolTip(_t("sftp.local.server_tooltip"))
            self.btn_local.setToolTip(_t("sftp.local.local_tooltip"))
            self.apply(self._source)
        except RuntimeError:
            pass  # Qt teardown

    def refresh_theme(self):
        """Re-apply the three states' stylesheet after a theme switch (v1.9.8)."""
        self._apply_switch_style()


def _sync_source_switch(switch, source: str, enabled: bool = True, available: bool = True):
    """Show a source and the availability of the switch (the ONE call of every state change)."""
    if switch is None:
        return
    try:
        if source:
            switch.apply(source)
        switch.set_available(enabled, available)
    except (RuntimeError, AttributeError):
        pass  # Qt teardown / a bare stub in a unit test — never raises
