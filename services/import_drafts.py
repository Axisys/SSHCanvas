# -*- coding: utf-8 -*-
"""The import DRAFT ROWS — ONE pure row model over the three import sources (§27, §80).

A source is READ, never applied: `ssh-config` (`services/ssh_config_importer.parse_ssh_config`),
`drawio` (`storage/import_drawio`, the reverse of the shipped writer's vocabulary) and `profiles`
(`storage/import_profiles`). Every draft is a ROW the user may take — `kind`, the source's `fields`,
`verdict` (`add` / `skip`) and a `reason` CODE the renderers translate (`REASON_KEYS`, ONE home). The GUI
preview (`dialogs/import_drafts_dialog.py`) and the headless report (`cli/imports.py`) render the SAME
rows, which is what keeps a preview and a script from disagreeing. PURE: no Qt, no i18n, no network —
`collect()` reads ONE file and touches nothing. Rule — `AGENTS.md` §4.36; mechanism — `DOCUMENTATION.md` §27.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

try:
    from models import profile as PROFILE_MODEL
    from services import ssh_config_importer as SCI
    from storage import import_drawio as DRAWIO
    from storage import import_profiles as PROFILES
except ImportError:  # pragma: no cover — the package layout (sshmap.services.*)
    from ..models import profile as PROFILE_MODEL
    from ..services import ssh_config_importer as SCI
    from ..storage import import_drawio as DRAWIO
    from ..storage import import_profiles as PROFILES

# ── the sources: the CLI's `import` subcommands and the GUI's two pickers ─────────────────────
SOURCE_SSH_CONFIG = "ssh-config"
SOURCE_DRAWIO = "drawio"
SOURCE_PROFILES = "profiles"
SOURCES = (SOURCE_SSH_CONFIG, SOURCE_DRAWIO, SOURCE_PROFILES)

# ── the kinds of a row ──────────────────────────────────────────────────────────────────────
KIND_SERVER = "server"
KIND_CONNECTION = "connection"
KIND_NOTE = "note"
KIND_PROFILE = "profile"
KIND_GROUP = "group"
KIND_BACKGROUND = "background"
KINDS = (KIND_SERVER, KIND_CONNECTION, KIND_NOTE, KIND_PROFILE, KIND_GROUP, KIND_BACKGROUND)

# ── the two verdicts ─────────────────────────────────────────────────────────────────────────
VERDICT_ADD = "add"
VERDICT_SKIP = "skip"

# ── the reason codes (the renderers own the sentences; `REASON_KEYS` is the ONE home) ────────
REASON_DUPLICATE = SCI.REASON_DUPLICATE
REASON_FOREIGN_SHAPE = DRAWIO.REASON_FOREIGN_SHAPE
REASON_GROUP = DRAWIO.REASON_GROUP
REASON_BACKGROUND = DRAWIO.REASON_BACKGROUND
REASON_UNKNOWN_TARGET = DRAWIO.REASON_UNKNOWN_TARGET
REASON_UNSUPPORTED = DRAWIO.REASON_UNSUPPORTED
REASON_MISSING_NAME = PROFILES.REASON_MISSING_NAME
REASON_MISSING_USER = PROFILES.REASON_MISSING_USER
REASON_NOT_A_LIST = PROFILES.REASON_NOT_A_LIST
REASON_MALFORMED_ENTRY = PROFILES.REASON_MALFORMED_ENTRY
REASON_DUPLICATE_NAME = "duplicate_name"

#: reason code → the i18n key that renders it. The SSH-config codes reuse the picker's OWN keys.
REASON_KEYS = {
    SCI.REASON_WILDCARD: "sshconfig.reason.wildcard",
    SCI.REASON_MATCH: "sshconfig.reason.match",
    SCI.REASON_INCLUDE_MISSING: "sshconfig.reason.include_missing",
    SCI.REASON_DUPLICATE: "sshconfig.reason.duplicate",
    SCI.NOTE_PROXY: "sshconfig.note.proxy",
    SCI.NOTE_IDENTITY_EXTRA: "sshconfig.note.identity_extra",
    REASON_FOREIGN_SHAPE: "import.reason.foreign_shape",
    REASON_GROUP: "import.reason.group",
    REASON_BACKGROUND: "import.reason.background",
    REASON_UNKNOWN_TARGET: "import.reason.unknown_target",
    REASON_UNSUPPORTED: "import.reason.unsupported",
    REASON_MISSING_NAME: "import.reason.missing_name",
    REASON_MISSING_USER: "import.reason.missing_user",
    REASON_NOT_A_LIST: "import.reason.not_a_list",
    REASON_MALFORMED_ENTRY: "import.reason.malformed_entry",
    REASON_DUPLICATE_NAME: "import.reason.duplicate_name",
}

#: kind → the i18n key of its caption (the preview's `kind` column and the report row).
KIND_KEYS = {
    KIND_SERVER: "import.kind.server",
    KIND_CONNECTION: "import.kind.connection",
    KIND_NOTE: "import.kind.note",
    KIND_PROFILE: "import.kind.profile",
    KIND_GROUP: "import.kind.group",
    KIND_BACKGROUND: "import.kind.background",
}

#: The fields of one kind, in the order the preview and the report write them.
FIELDS = {
    KIND_SERVER: ("ref", "alias", "host", "port", "user", "key_path", "jump_host", "tags",
                  "comment", "x", "y"),
    KIND_CONNECTION: ("ref", "source", "target", "label", "type", "bidirectional"),
    KIND_NOTE: ("ref", "text", "x", "y", "width", "height"),
    KIND_PROFILE: ("name", "user"),
    KIND_GROUP: ("ref",),
    KIND_BACKGROUND: ("ref",),
}

#: Every row's OWN columns, before the kind-specific fields — the report's declared header.
LEAD_COLUMNS = ("kind", "verdict", "reason", "detail")

# ── the loader's failure classes (the CLI maps them onto its exit codes) ─────────────────────
ERROR_MISSING = "missing"
ERROR_UNREADABLE = "unreadable"
ERROR_PARSE = "parse"


class SourceError(Exception):
    """The source file cannot be used: ``code`` (missing / unreadable / parse) + a detail."""

    def __init__(self, code: str, detail: str = "", source: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.source = source


def cell_text(value) -> str:
    """ONE field as the report cell: "" for None, `true`/`false` for a flag, `g` for a number."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(part) for part in value)
    return str(value)


@dataclass(frozen=True)
class Draft:
    """ONE row of an import source: its kind, the source's fields and the verdict of the preview."""

    kind: str
    fields: Dict[str, object] = field(default_factory=dict)
    verdict: str = VERDICT_ADD
    reason: str = ""
    detail: str = ""
    source: str = ""
    line: int = 0

    def cell(self, column) -> str:
        """One CELL of this row — the lead columns first, then the kind's own fields."""
        if column in LEAD_COLUMNS:
            return cell_text(getattr(self, column, ""))
        return cell_text((self.fields or {}).get(column, ""))


@dataclass(frozen=True)
class DraftReport:
    """The rows of ONE source: what may be added, what was left out, and the path it came from."""

    source: str
    path: str = ""
    drafts: Tuple[Draft, ...] = ()

    def ready(self) -> list:
        """The rows the user may take (they start CHECKED in the preview)."""
        return [draft for draft in self.drafts if draft.verdict == VERDICT_ADD]

    def skipped(self) -> list:
        """The rows the preview reports and nobody takes."""
        return [draft for draft in self.drafts if draft.verdict == VERDICT_SKIP]

    def count(self) -> int:
        """Every row of the report (ready + skipped)."""
        return len(self.drafts)

    def columns(self) -> list:
        """The header: the lead columns then the fields of every kind the rows carry."""
        out = list(LEAD_COLUMNS)
        for draft in self.drafts:
            for name in FIELDS.get(draft.kind, ()):
                if name not in out:
                    out.append(name)
        return out

    def rows(self) -> list:
        """The cells of every row, in the declared column order."""
        columns = self.columns()
        return [[draft.cell(column) for column in columns] for draft in self.drafts]

    def payload(self) -> dict:
        """The `--json` shape of the report — the table verbs' pinned keys over the drafts' rows."""
        return {"source": str(self.source or ""), "path": str(self.path or ""),
                "count": self.count(), "columns": self.columns(), "rows": self.rows()}


def _source_key(host) -> tuple:
    """The `(host, port, user)` merge key of the SSH-config import (the `dedupe_hosts` rule)."""
    return (str(getattr(host, "host", "")).strip().lower(), int(getattr(host, "port", 0) or 0),
            str(getattr(host, "user", "")).strip().lower())


def _host_fields(host) -> dict:
    """The fields of ONE SSH-config host — the map's own card fields."""
    return {"ref": f"{host.source}:{host.line}" if host.source else str(host.line),
            "alias": host.alias, "host": host.host, "port": host.port, "user": host.user,
            "key_path": host.key_path or "", "jump_host": getattr(host, "jump_host", "") or ""}


def ssh_config_drafts(result, existing_keys=None) -> DraftReport:
    """The SSH config's hosts as draft rows — a host the caller already knows is a SKIP row."""
    notes_of: Dict[str, list] = {}
    for note in getattr(result, "notes", ()) or ():
        notes_of.setdefault(str(note.subject), []).append(note)
    notes_text = {alias: "; ".join(n.detail or f"note: {n.reason}" for n in notes)
                  for alias, notes in notes_of.items()}
    fresh, duplicates = SCI.dedupe_hosts(getattr(result, "hosts", ()) or (),
                                         set(existing_keys or ()))
    drafts = []
    for host in fresh:
        fields = _host_fields(host)
        drafts.append(Draft(KIND_SERVER, fields, source=host.source, line=host.line,
                            detail=notes_text.get(str(host.alias), "")))
    for host in duplicates:
        drafts.append(Draft(KIND_SERVER, _host_fields(host), verdict=VERDICT_SKIP,
                            reason=REASON_DUPLICATE, detail=host.host,
                            source=host.source, line=host.line))
    for issue in getattr(result, "skipped", ()) or ():
        drafts.append(Draft(KIND_SERVER, {"alias": issue.subject}, verdict=VERDICT_SKIP,
                            reason=issue.reason, detail=issue.detail or "",
                            source=issue.source, line=issue.line))
    return DraftReport(SOURCE_SSH_CONFIG, getattr(result, "path", "") or "", tuple(drafts))


def drawio_drafts(document, source_path="") -> DraftReport:
    """The `.drawio` document as draft rows — cards, links and notes beside the cells left out."""
    drafts = []
    for card in getattr(document, "cards", ()) or ():
        drafts.append(Draft(KIND_SERVER, {
            "ref": card.cell_id, "alias": card.alias, "host": card.host, "port": "",
            "user": "", "key_path": "", "jump_host": "", "tags": tuple(card.tags),
            "comment": card.comment, "x": card.x, "y": card.y},
            source=str(source_path or ""), detail=_card_detail(card)))
    for edge in getattr(document, "edges", ()) or ():
        drafts.append(Draft(KIND_CONNECTION, {
            "ref": edge.cell_id, "source": edge.source, "target": edge.target,
            "label": edge.label, "type": edge.ctype, "bidirectional": edge.bidirectional},
            source=str(source_path or "")))
    for note in getattr(document, "notes", ()) or ():
        drafts.append(Draft(KIND_NOTE, {"ref": note.cell_id, "text": note.text,
                                        "x": note.x, "y": note.y,
                                        "width": note.width, "height": note.height},
                            source=str(source_path or "")))
    for issue in getattr(document, "skipped", ()) or ():
        drafts.append(Draft(_skipped_kind(issue.reason), {"ref": issue.subject},
                            verdict=VERDICT_SKIP, reason=issue.reason, detail=issue.detail or "",
                            source=str(source_path or "")))
    return DraftReport(SOURCE_DRAWIO, str(getattr(document, "path", "") or source_path or ""),
                       tuple(drafts))


def _skipped_kind(reason) -> str:
    """The kind a SKIPPED drawio cell would have had — the group frame and the image keep theirs."""
    return {REASON_GROUP: KIND_GROUP, REASON_BACKGROUND: KIND_BACKGROUND,
            REASON_UNKNOWN_TARGET: KIND_CONNECTION}.get(str(reason or ""), KIND_SERVER)


def _card_detail(card) -> str:
    """The facts a card carried that the import cannot place on a node (the dialog shows them)."""
    parts = []
    for name in ("os_name", "cpu_model", "ram", "ip"):
        value = str(getattr(card, name, "") or "")
        if value:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def profile_drafts(document, existing_names=None) -> DraftReport:
    """The profiles document as draft rows — a NAME the store already holds is a SKIP row."""
    seen = {str(name or "").strip().lower() for name in (existing_names or ())}
    drafts = []
    for row in getattr(document, "rows", ()) or ():
        key = str(row.name).strip().lower()
        if key in seen:
            drafts.append(Draft(KIND_PROFILE, {"name": row.name, "user": row.user},
                                verdict=VERDICT_SKIP, reason=REASON_DUPLICATE_NAME,
                                detail=row.user, line=row.line))
            continue
        seen.add(key)
        drafts.append(Draft(KIND_PROFILE, {"name": row.name, "user": row.user}, line=row.line))
    for issue in getattr(document, "skipped", ()) or ():
        drafts.append(Draft(KIND_PROFILE, {"name": issue.subject}, verdict=VERDICT_SKIP,
                            reason=issue.reason, detail=issue.detail or "", line=issue.line))
    return DraftReport(SOURCE_PROFILES, str(getattr(document, "path", "") or ""), tuple(drafts))


def default_path(source, home: Optional[str] = None) -> str:
    """The file a source reads when the caller names none ("" — the source REQUIRES a path)."""
    if source == SOURCE_SSH_CONFIG:
        return SCI.default_config_path(home)
    if source == SOURCE_PROFILES:
        return PROFILE_MODEL.profiles_path()
    return ""


def collect(source, path="", home=None, project_keys=None, store_names=None) -> DraftReport:
    """Read ONE source into a report — the draft rows of the file at `path` (or its declared default).

    `project_keys` marks the hosts a project already carries (`dedupe_hosts`), `store_names` marks the
    profiles the store already holds; `None` means "nothing to compare against" and adds no SKIP row.
    A file that cannot be read or parsed raises `SourceError`, never an empty report.
    """
    wanted = str(source or "").strip()
    if wanted not in SOURCES:
        raise SourceError(ERROR_PARSE, f"unknown source {source!r}")
    target = str(path or "").strip() or default_path(wanted, home)
    if not target:
        raise SourceError(ERROR_MISSING, f"{wanted} needs a file path")
    if wanted == SOURCE_SSH_CONFIG:
        return _ssh_config_report(target, home, project_keys)
    if wanted == SOURCE_DRAWIO:
        return _drawio_report(target)
    return _profiles_report(target, store_names)


def _ssh_config_report(path, home, project_keys) -> DraftReport:
    """The SSH config at `path` — the shipped loader, its codes mapped onto `SourceError`."""
    try:
        result = SCI.load_ssh_config(path, home=home)
    except SCI.SshConfigError as exc:
        code = ERROR_MISSING if exc.code == SCI.ERROR_MISSING else ERROR_UNREADABLE
        raise SourceError(code, exc.detail or str(exc), path)
    return ssh_config_drafts(result, project_keys)


def _drawio_report(path) -> DraftReport:
    """The `.drawio` file at `path` — `storage/import_drawio`'s codes mapped onto `SourceError`."""
    if not os.path.isfile(path):
        raise SourceError(ERROR_MISSING, f"no file at {path}", path)
    try:
        document = DRAWIO.parse_drawio_file(path)
    except DRAWIO.DrawioError as exc:
        code = ERROR_MISSING if exc.code == DRAWIO.ERROR_UNREADABLE else ERROR_PARSE
        raise SourceError(code, exc.detail or str(exc), path)
    return drawio_drafts(document, path)


def _profiles_report(path, store_names) -> DraftReport:
    """The profiles file at `path` — a duplicate NAME is a SKIP row, nothing is overwritten."""
    if not os.path.isfile(path):
        raise SourceError(ERROR_MISSING, f"no file at {path}", path)
    try:
        document = PROFILES.parse_profiles_file(path)
    except PROFILES.ProfilesFileError as exc:
        code = ERROR_MISSING if exc.code == PROFILES.ERROR_UNREADABLE else ERROR_PARSE
        raise SourceError(code, exc.detail or str(exc), path)
    return profile_drafts(document, store_names)
