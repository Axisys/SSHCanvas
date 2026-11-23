# -*- coding: utf-8 -*-
"""The "Import from ~/.ssh/config" picker (AGENTS.md §4.4; DOCUMENTATION.md §27).

Data-driven like the backups dialog: the caller (`MainWindow._import_servers_from_ssh_config`) passes what
`services/ssh_config_importer.py` parsed and receives the CHECKED records back through `selected_hosts()`,
so the dialog imports nothing itself and holds no state beyond its checkboxes. Every row starts checked, so
"import the whole config" is one OK, and the "Import" button is DISABLED while nothing is checked (there is
no import to confirm). The frame is `CheckablePickDialog`.

The report under the tree shows what the parse DROPPED: `skipped` (not imported at all — a wildcard pattern,
a `Match` block, an unreadable `Include`, a host the map already knows) and `notes` (imported, but a
directive was dropped — `ProxyCommand`, an extra `IdentityFile`). Both are hidden while empty, so
a clean config shows the table and nothing else; the reason CODES are the parser's and the translation lives here (`_REASON_KEYS`)."""

try:
    from ..i18n import t
except ImportError:
    try:
        from i18n import t
    except ImportError:  # flat layout without i18n — keys as-is (main_window pattern)
        def t(key, **kwargs):
            return key.format(**kwargs) if kwargs else key

try:  # the ONE reason-code table of the import family (the generic preview reads it too)
    from ..services.import_drafts import REASON_KEYS as _REASON_KEYS
except ImportError:
    from services.import_drafts import REASON_KEYS as _REASON_KEYS

try:
    from .checkable_pick_dialog import CheckablePickDialog
except ImportError:
    from checkable_pick_dialog import CheckablePickDialog

from PySide6.QtWidgets import QHeaderView


def reason_text(issue) -> str:
    """The user-facing line of a skip record / a note (i18n; falls back to the code)."""
    key = _REASON_KEYS.get(getattr(issue, "reason", ""), "")
    if not key:
        return f"{getattr(issue, 'subject', '')} ({getattr(issue, 'reason', '')})"
    return t(key, detail=getattr(issue, "detail", "") or "")


class SshConfigImportDialog(CheckablePickDialog):
    """The checkbox table of the hosts found in the SSH config + its skip report."""

    #: column id → the `sshconfig.col_*` header key (the row cells answer in the same order).
    _COLUMNS = ("alias", "host", "port", "user", "key", "jump")

    def __init__(self, hosts, skipped=(), notes=(), source: str = "", parent=None):
        super().__init__(parent)
        self._hosts = list(hosts)
        self.skipped = list(skipped)
        self.notes = list(notes)
        self._source = source
        self._build_frame()

    # ── The frame's content hooks ────────────────────────────────

    def _records(self):
        return self._hosts

    def _window_title(self) -> str:
        return t("sshconfig.title")

    def _window_size(self):
        return 780, 470

    def _hint_text(self) -> str:
        return t("sshconfig.hint", path=self._source or "", count=len(self._hosts))

    def _columns(self):
        return self._COLUMNS

    def _header_label(self, column) -> str:
        return t(f"sshconfig.col_{column}")

    def _row_cells(self, host):
        return [
            host.alias, host.host, host.port, host.user, host.key_path or "",
            # v1.12.3: the `ProxyJump` value the row was parsed with — the
            # fifth column is the key FILE, this one is the proxy the connect will carry.
            getattr(host, "jump_host", "") or "",
        ]

    def _row_tooltips(self, host):
        if not host.source:
            return ()
        return ((0, f"{host.source}:{host.line}"),)

    def _report_lines(self):
        lines = []
        if self.skipped:
            lines.append(t("sshconfig.skipped", count=len(self.skipped)))
            lines += [f"  • {i.subject} — {reason_text(i)}" for i in self.skipped]
        if self.notes:
            lines.append(t("sshconfig.notes", count=len(self.notes)))
            lines += [f"  • {i.subject} — {reason_text(i)}" for i in self.notes]
        return lines

    def _resize_columns(self, header):
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)

    # ── Public access for tests and the caller ───────────────────

    def selected_hosts(self) -> list:
        """The records whose checkbox is checked (in table order)."""
        return self.selected_records()
