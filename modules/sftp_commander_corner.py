# -*- coding: utf-8 -*-
"""The Files Commander's ROW of the tab-bar corner — the checkable switch of the two-pane view.

It belongs to the CONTAINER (the corner is the tab bar's) while the mode is the SESSION's, so the
control is a VIEW over an action the container reads (`is_commander()`); its button is a ROW of
`modules/terminal_corner.py`, which owns the label-less shape and the two walks. This module keeps
`modules/sftp_tab.py` — the pane FACADE — under the line budget the two split waves won
(`tests/test_sftp_pane_split.py`), and the facade RE-EXPORTS the class, so
`modules.sftp_tab.CommanderCorner` stays the shipped name. Mechanism — `DOCUMENTATION.md` §65."""

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — a build without i18n keeps the keys, not a crash
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # the ONE owner of the corner's shape (`modules/terminal_corner.py`)
    from .terminal_corner import shape_control
except ImportError:  # flat launch from the project root
    try:
        from terminal_corner import shape_control
    except ImportError:  # a stripped build — the button keeps the text it is built with
        def shape_control(button, glyph, tooltip, label):
            return False


class CommanderCorner(QObject):
    """The corner's Commander row: ONE checkable action, a button that views it.

    The `act_split` pattern: the action is the single source of truth and the button is a view of
    it, so the checkmark and the pane state can never diverge. The container calls `set_state()`
    whenever the active session changes, and the action is DISABLED while the active session has no
    Files tab (a split pane). The ROW — the order, the width, the glyph, the tooltip and the
    accessible name — is `modules/terminal_corner.py`'s (`CornerBar.add_control("commander", …)`).
    Never raises — the corner is chrome.
    """

    def __init__(self, host=None):
        super().__init__(host if isinstance(host, QObject) else None)
        self.act = QAction(_t("sftp.commander"), self)
        self.act.setCheckable(True)
        self.act.setToolTip(_t("sftp.commander_tooltip"))
        self.btn = QPushButton()
        self.btn.setCheckable(True)
        self.btn.setText(_t("sftp.commander"))    # the word the STRIPPED build keeps
        shape_control(self.btn, "files", _t("sftp.commander_tooltip"), _t("sftp.commander"))
        self.btn.clicked.connect(self._on_button_clicked)
        self.act.toggled.connect(self._sync_button)
        self.set_enabled(False)   # until a session tells us what it has

    def _on_button_clicked(self, _checked=False):
        """The BUTTON asks the ACTION (one source of truth), exactly like `btn_split`."""
        self.act.setChecked(bool(self.btn.isChecked()))

    def _sync_button(self, checked=None):
        """Keep the button in step with the action WITHOUT re-entering the slot."""
        try:
            if checked is None:
                checked = bool(self.act.isChecked())
            self.btn.blockSignals(True)
            self.btn.setChecked(bool(checked))
            self.btn.blockSignals(False)
        except RuntimeError:
            pass  # Qt teardown — the button is gone

    def is_commander(self) -> bool:
        """The action's state — the ONE answer the container reads."""
        return bool(self.act.isChecked())

    def set_enabled(self, on: bool):
        """Enable/disable both views (a session without a Files tab disables the action)."""
        on = bool(on)
        try:
            self.act.setEnabled(on)
            self.btn.setEnabled(on)
        except RuntimeError:
            pass  # Qt teardown

    def set_state(self, on: bool):
        """Show a session's mode WITHOUT reporting it back (the `_set_split_action_checked`
        discipline: the action's signals stay blocked, so the container is never re-entered)."""
        on = bool(on)
        try:
            self.act.blockSignals(True)
            self.act.setChecked(on)
            self.act.blockSignals(False)
        except RuntimeError:
            pass  # Qt teardown
        self._sync_button(on)

    def retranslate(self):
        """Re-text the ACTION (its word is the menu row); the button's sentence is the bar's."""
        try:
            self.act.setText(_t("sftp.commander"))
            self.act.setToolTip(_t("sftp.commander_tooltip"))
        except RuntimeError:
            pass  # Qt teardown — the corner is already destroyed
