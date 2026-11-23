# -*- coding: utf-8 -*-
"""The ONE frame of a checkable picker — the tree, the all/none pair, the Import lock and the report.

A subclass answers the CONTENT through hooks and calls `_build_frame()` LAST, after its own state:
`_records()`, `_window_title()` / `_window_size()` / `_hint_text()`, `_columns()` / `_header_label()`,
`_row_cells()` / `_row_tooltips()` and `_report_lines()`. The frame owns the widgets and the state:
every row starts checked, a check change re-syncs the Import button (disabled at zero checked), and the
report is a read-only `QPlainTextEdit` hidden while its lines are empty.

Owners: `dialogs/ssh_config_import_dialog.py` (the SSH-config picker) and
`dialogs/import_drafts_dialog.py` (the generic draft preview). Mechanism — `DOCUMENTATION.md` §27.
"""

try:
    from ..i18n import t
except ImportError:
    try:
        from i18n import t
    except ImportError:  # flat layout without i18n — keys as-is (main_window pattern)
        def t(key, **kwargs):
            return key.format(**kwargs) if kwargs else key

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QPlainTextEdit, QHeaderView,
)

#: The index of the record inside a row — gotcha #12: `QTreeWidgetItem.setData` stores a COPY.
_RECORD_ROLE = Qt.ItemDataRole.UserRole

#: The frame's own sentences — the keys both pickers shipped (`sshconfig.*` and `btn.*`; additive only).
_SELECT_ALL_KEY = "sshconfig.select_all"
_SELECT_NONE_KEY = "sshconfig.select_none"
_IMPORT_KEY = "btn.import"
_CANCEL_KEY = "btn.cancel"


class CheckablePickDialog(QDialog):
    """The shared frame of the two import pickers — the content comes from the subclass hooks."""

    def __init__(self, parent=None):
        super().__init__(parent)

    # ── The hooks a subclass answers ─────────────────────────────

    def _records(self):
        """The records the rows stand for, in table order."""
        raise NotImplementedError

    def _window_title(self) -> str:
        raise NotImplementedError

    def _window_size(self):
        raise NotImplementedError

    def _hint_text(self) -> str:
        raise NotImplementedError

    def _columns(self):
        """The column identifiers, in table order (the base reads only their count and labels)."""
        raise NotImplementedError

    def _header_label(self, column) -> str:
        return str(column)

    def _row_cells(self, record):
        """The cell texts of ONE record, one per column."""
        raise NotImplementedError

    def _row_tooltips(self, record):
        """`(column index, text)` pairs of ONE row — an empty text is skipped."""
        return ()

    def _report_lines(self):
        """The report body's lines; an empty answer hides the report."""
        return ()

    def _resize_columns(self, header):
        """The default column policy: content-sized columns, the FIRST takes the slack."""
        for index in range(self.tree.columnCount()):
            header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
        if self.tree.columnCount():
            header.setSectionResizeMode(0, QHeaderView.Stretch)

    # ── The frame ────────────────────────────────────────────────

    def _build_frame(self) -> None:
        """Build the skeleton — the LAST call of a subclass `__init__`, after its own state."""
        self._record_list = list(self._records())
        self._rows = []
        self.setWindowTitle(self._window_title())
        self.resize(*self._window_size())

        layout = QVBoxLayout(self)
        hint = QLabel(self._hint_text())
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self._column_list = list(self._columns())
        self.tree.setColumnCount(len(self._column_list))
        self.tree.setHeaderLabels([self._header_label(column) for column in self._column_list])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.itemChanged.connect(lambda *_args: self._sync_import_button())
        for record in self._record_list:
            row = QTreeWidgetItem([str(text) for text in self._row_cells(record)])
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(0, Qt.CheckState.Checked)
            for index, text in self._row_tooltips(record):
                if text:
                    row.setToolTip(index, str(text))
            row.setData(0, _RECORD_ROLE, len(self._rows))
            self.tree.addTopLevelItem(row)
            self._rows.append(row)
        self._resize_columns(self.tree.header())
        layout.addWidget(self.tree, 1)

        buttons = QHBoxLayout()
        self.btn_all = QPushButton(t(_SELECT_ALL_KEY))
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none = QPushButton(t(_SELECT_NONE_KEY))
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        self.btn_import = QPushButton(t(_IMPORT_KEY))
        self.btn_import.setDefault(True)
        self.btn_import.clicked.connect(self.accept)
        btn_cancel = QPushButton(t(_CANCEL_KEY))
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_all)
        buttons.addWidget(self.btn_none)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_import)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(120)
        lines = list(self._report_lines())
        if lines:
            self.report.setPlainText("\n".join(lines))
            layout.addWidget(self.report)
        else:
            self.report.hide()

        self._sync_import_button()

    # ── Public access for tests and the caller ───────────────────

    def item_count(self) -> int:
        return len(self._rows)

    def checked_count(self) -> int:
        return sum(1 for row in self._rows
                   if row.checkState(0) == Qt.CheckState.Checked)

    def selected_records(self) -> list:
        """The records whose checkbox is checked (in table order)."""
        out = []
        for row in self._rows:
            if row.checkState(0) != Qt.CheckState.Checked:
                continue
            index = row.data(0, _RECORD_ROLE)
            if isinstance(index, int) and 0 <= index < len(self._record_list):
                out.append(self._record_list[index])
        return out

    def report_text(self) -> str:
        """The report body ("" when there is nothing to tell)."""
        return self.report.toPlainText()

    # ── Slots ────────────────────────────────────────────────────

    def _set_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in self._rows:
            row.setCheckState(0, state)
        self._sync_import_button()

    def _sync_import_button(self):
        self.btn_import.setEnabled(self.checked_count() > 0)
