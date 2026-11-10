# -*- coding: utf-8 -*-
"""The shared import PREVIEW — the draft rows of `services/import_drafts.py`, one table for any source.

The SSH-config picker keeps its OWN columns (`SshConfigImportDialog`); this dialog renders the generic
draft model for the sources that have no picker of their own — a `.drawio` file
(`NodeOpsMixin._import_map_from_drawio`) and a profiles file (`ProfileManagerDialog`). Data-driven like the
backups dialog: the caller passes the `DraftReport` and receives the CHECKED drafts back through
`selected_drafts()`, so the dialog applies nothing and holds no state beyond its checkboxes. The skipped
rows are a read-only report (hidden while empty); a reason is a CODE and the sentence lives in `en.json`
(`services/import_drafts.REASON_KEYS`, §27).
"""
try:
    from ..i18n import t
except ImportError:
    try:
        from i18n import t
    except ImportError:  # flat layout without i18n — keys as-is (main_window pattern)
        def t(key, **kwargs):
            return key.format(**kwargs) if kwargs else key

try:
    from ..services import import_drafts
except ImportError:
    from services import import_drafts

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QPlainTextEdit, QHeaderView,
)

#: column id → the i18n key of its header (a column with no key shows its own id — English, never blank).
COLUMN_KEYS = {
    "kind": "import.col.kind", "verdict": "import.col.verdict", "reason": "import.col.reason",
    "detail": "import.col.detail", "ref": "import.col.ref", "alias": "import.col.alias",
    "host": "import.col.host", "port": "import.col.port", "user": "import.col.user",
    "key_path": "import.col.key_path", "jump_host": "import.col.jump_host",
    "tags": "import.col.tags", "comment": "import.col.comment", "x": "import.col.x",
    "y": "import.col.y", "width": "import.col.width", "height": "import.col.height",
    "source": "import.col.source", "target": "import.col.target",
    "label": "import.col.label", "type": "import.col.type",
    "bidirectional": "import.col.bidirectional", "name": "import.col.name", "text": "import.col.text",
}

#: source id → (title key, hint key) — the picker that has its own dialog is not in this table.
SOURCE_KEYS = {
    import_drafts.SOURCE_DRAWIO: ("import.drawio.title", "import.drawio.hint"),
    import_drafts.SOURCE_PROFILES: ("import.profiles.title", "import.profiles.hint"),
}

#: The index of the draft inside the tree row — gotcha #12: an item's data is a COPY.
_RECORD_ROLE = Qt.ItemDataRole.UserRole

#: The longest cell a preview shows (the full value stays in the tooltip) — a table, not a text dump.
CELL_MAX = 120


def reason_text(reason, detail="") -> str:
    """The user-facing line of ONE skip reason (i18n; falls back to the code and its detail)."""
    key = import_drafts.REASON_KEYS.get(str(reason or ""), "")
    if not key:
        text = str(reason or "")
        return f"{text} ({detail})" if detail else text
    return t(key, detail=str(detail or ""))


def kind_text(kind) -> str:
    """The user-facing caption of a draft kind (falls back to the kind id)."""
    key = import_drafts.KIND_KEYS.get(str(kind or ""), "")
    return t(key) if key else str(kind or "")


def column_text(column) -> str:
    """The header of ONE column (its own id when the table has no key for it)."""
    key = COLUMN_KEYS.get(str(column or ""))
    return t(key) if key else str(column or "")


def cell_text(draft, column) -> str:
    """One cell of a draft row — the `kind` column is its translated caption, never the raw id."""
    if column == "kind":
        return kind_text(draft.kind)
    return draft.cell(column)


class ImportDraftsDialog(QDialog):
    """The checkbox table of an import source's ADD rows + the read-only report of the skipped ones."""

    def __init__(self, report, parent=None):
        super().__init__(parent)
        self._report = report
        self._drafts = list(report.ready())
        self._columns = list(report.columns())
        title_key, hint_key = SOURCE_KEYS.get(report.source, ("import.title", "import.hint"))
        self.setWindowTitle(t(title_key))
        self.resize(860, 480)

        layout = QVBoxLayout(self)
        hint = QLabel(t(hint_key, path=report.path or "", count=len(self._drafts)))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(self._columns))
        self.tree.setHeaderLabels([column_text(column) for column in self._columns])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.itemChanged.connect(lambda *_args: self._sync_import_button())
        self._rows = []
        for draft in self._drafts:
            row = QTreeWidgetItem([cell_text(draft, column) for column in self._columns])
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(0, Qt.CheckState.Checked)
            for index, column in enumerate(self._columns):
                value = draft.cell(column)
                if len(value) > CELL_MAX:
                    row.setText(index, value[:CELL_MAX] + "…")
                if value:
                    row.setToolTip(index, value)
            if draft.source:
                row.setToolTip(0, f"{draft.source}:{draft.line}" if draft.line else draft.source)
            row.setData(0, _RECORD_ROLE, len(self._rows))
            self.tree.addTopLevelItem(row)
            self._rows.append(row)
        header = self.tree.header()
        for index in range(len(self._columns)):
            header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
        if self._columns:
            header.setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.tree, 1)

        buttons = QHBoxLayout()
        self.btn_all = QPushButton(t("sshconfig.select_all"))
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none = QPushButton(t("sshconfig.select_none"))
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        self.btn_import = QPushButton(t("btn.import"))
        self.btn_import.setDefault(True)
        self.btn_import.clicked.connect(self.accept)
        btn_cancel = QPushButton(t("btn.cancel"))
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
        skipped = report.skipped()
        if skipped:
            lines = [t("import.skipped", count=len(skipped))]
            lines += [f"  • {self._subject(draft)} — {reason_text(draft.reason, draft.detail)}"
                      for draft in skipped]
            self.report.setPlainText("\n".join(lines))
            layout.addWidget(self.report)
        else:
            self.report.hide()
        self._sync_import_button()

    def _subject(self, draft) -> str:
        """The name a skipped row is reported under (the alias / the name / the cell id)."""
        fields = draft.fields or {}
        for name in ("alias", "name", "ref"):
            value = str(fields.get(name) or "").strip()
            if value:
                return value
        return draft.kind

    # ── Public access for tests and the caller ───────────────────

    def item_count(self) -> int:
        return len(self._rows)

    def checked_count(self) -> int:
        return sum(1 for row in self._rows if row.checkState(0) == Qt.CheckState.Checked)

    def selected_drafts(self) -> list:
        """The drafts whose checkbox is checked (in table order)."""
        out = []
        for row in self._rows:
            if row.checkState(0) != Qt.CheckState.Checked:
                continue
            index = row.data(0, _RECORD_ROLE)
            if isinstance(index, int) and 0 <= index < len(self._drafts):
                out.append(self._drafts[index])
        return out

    def report_text(self) -> str:
        """The skipped rows' report ("" when nothing was left out)."""
        return self.report.toPlainText()

    # ── Slots ────────────────────────────────────────────────────

    def _set_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in self._rows:
            row.setCheckState(0, state)
        self._sync_import_button()

    def _sync_import_button(self):
        self.btn_import.setEnabled(self.checked_count() > 0)
