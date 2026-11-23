# -*- coding: utf-8 -*-
"""The shared import PREVIEW — the draft rows of `services/import_drafts.py`, one table for any source.

The SSH-config picker keeps its OWN columns (`SshConfigImportDialog`); this dialog renders the generic
draft model for the sources that have no picker of their own — a `.drawio` file
(`NodeOpsMixin._import_map_from_drawio`) and a profiles file (`ProfileManagerDialog`). Data-driven like the
backups dialog: the caller passes the `DraftReport` and receives the CHECKED drafts back through
`selected_drafts()`, so the dialog applies nothing and holds no state beyond its checkboxes. The frame is
`CheckablePickDialog`. The skipped rows are a read-only report (hidden while empty); a reason is a CODE and
the sentence lives in `en.json` (`services/import_drafts.REASON_KEYS`, §27).
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

try:
    from .checkable_pick_dialog import CheckablePickDialog
except ImportError:
    from checkable_pick_dialog import CheckablePickDialog

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


class ImportDraftsDialog(CheckablePickDialog):
    """The checkbox table of an import source's ADD rows + the read-only report of the skipped ones."""

    def __init__(self, report, parent=None):
        super().__init__(parent)
        self._report = report
        self._drafts = list(report.ready())
        self._draft_columns = list(report.columns())
        self._title_key, self._hint_key = SOURCE_KEYS.get(report.source,
                                                          ("import.title", "import.hint"))
        self._build_frame()

    # ── The frame's content hooks ────────────────────────────────

    def _records(self):
        return self._drafts

    def _window_title(self) -> str:
        return t(self._title_key)

    def _window_size(self):
        return 860, 480

    def _hint_text(self) -> str:
        return t(self._hint_key, path=self._report.path or "", count=len(self._drafts))

    def _columns(self):
        return self._draft_columns

    def _header_label(self, column) -> str:
        return column_text(column)

    def _row_cells(self, draft):
        cells = []
        for column in self._draft_columns:
            value = draft.cell(column)
            if len(value) > CELL_MAX:
                cells.append(value[:CELL_MAX] + "…")
            else:
                cells.append(cell_text(draft, column))
        return cells

    def _row_tooltips(self, draft):
        out = []
        for index, column in enumerate(self._draft_columns):
            value = draft.cell(column)
            if value:
                out.append((index, value))
        if draft.source:
            out.append((0, f"{draft.source}:{draft.line}" if draft.line else draft.source))
        return out

    def _report_lines(self):
        skipped = self._report.skipped()
        if not skipped:
            return []
        lines = [t("import.skipped", count=len(skipped))]
        lines += [f"  • {self._subject(draft)} — {reason_text(draft.reason, draft.detail)}"
                  for draft in skipped]
        return lines

    def _subject(self, draft) -> str:
        """The name a skipped row is reported under (the alias / the name / the cell id)."""
        fields = draft.fields or {}
        for name in ("alias", "name", "ref"):
            value = str(fields.get(name) or "").strip()
            if value:
                return value
        return draft.kind

    # ── Public access for tests and the caller ───────────────────

    def selected_drafts(self) -> list:
        """The drafts whose checkbox is checked (in table order)."""
        return self.selected_records()
