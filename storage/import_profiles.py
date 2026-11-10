# -*- coding: utf-8 -*-
"""Read a PROFILES file into drafts — `~/.sshmap_profiles.json` or a copy another machine produced.

The format is `models/profile.py`'s: a JSON LIST of `{id, name, user}`. The id is IGNORED on import
(a name merge, never an id merge) and the password is not in the file at all (`save_profiles()` strips
it — a secret lives in the OS keyring, `AGENTS.md` §4.4.1). An unusable entry is a SKIP record with a
reason code, so an import never guesses what a store the user asked to read was meant to hold.
PURE — `json` only, no Qt, no i18n; the mechanism is `DOCUMENTATION.md` §3, §27.
"""
import json
from dataclasses import dataclass
from typing import Tuple

# ── loader error codes (the caller maps them to its own class) ───────────────────────────────
ERROR_UNREADABLE = "unreadable"
ERROR_PARSE = "parse"

# ── skip reasons: an entry that is NOT imported ──────────────────────────────────────────────
REASON_MALFORMED_ENTRY = "malformed_entry"   # not a JSON object
REASON_MISSING_NAME = "missing_name"         # the merge key of the whole flow
REASON_MISSING_USER = "missing_user"         # no login name — the profile would carry nothing
REASON_NOT_A_LIST = "not_a_list"             # a JSON object, not the array the format declares


class ProfilesFileError(Exception):
    """The profiles file cannot be used (``code`` = ERROR_UNREADABLE / ERROR_PARSE)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ProfileRow:
    """One usable profile record: the merge key ``name`` and its login, never a secret."""

    name: str
    user: str
    line: int = 0          # the entry's 1-based index in the file — what a report names


@dataclass(frozen=True)
class ProfileIssue:
    """One entry left out: ``subject`` (a name or an index) + a reason code."""

    subject: str
    reason: str
    detail: str = ""
    line: int = 0


@dataclass(frozen=True)
class ProfilesDocument:
    """The parsed file: the usable rows, the entries left out and the path it was read from."""

    rows: Tuple[ProfileRow, ...] = ()
    skipped: Tuple[ProfileIssue, ...] = ()
    path: str = ""


def parse_profiles_text(text, source: str = "") -> ProfilesDocument:
    """Parse ONE profiles JSON text — a document that is not valid JSON raises `ProfilesFileError`."""
    try:
        raw = json.loads(str(text if text is not None else ""))
    except json.JSONDecodeError as exc:
        raise ProfilesFileError(ERROR_PARSE, f"{source or 'the file'}: {exc}")
    rows, skipped = [], []
    if not isinstance(raw, (list, tuple)):
        return ProfilesDocument(skipped=(ProfileIssue(source or "the file", REASON_NOT_A_LIST,
                                                      type(raw).__name__),), path=str(source or ""))
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            skipped.append(ProfileIssue(str(index), REASON_MALFORMED_ENTRY,
                                        type(entry).__name__, index))
            continue
        name = str(entry.get("name") or "").strip()
        user = str(entry.get("user") or "").strip()
        if not name:
            skipped.append(ProfileIssue(str(index), REASON_MISSING_NAME, user, index))
            continue
        if not user:
            skipped.append(ProfileIssue(name, REASON_MISSING_USER, "", index))
            continue
        rows.append(ProfileRow(name=name, user=user, line=index))
    return ProfilesDocument(rows=tuple(rows), skipped=tuple(skipped), path=str(source or ""))


def parse_profiles_file(path) -> ProfilesDocument:
    """Read and parse a profiles FILE — a missing or unreadable one raises `ProfilesFileError`."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read()
    except FileNotFoundError:
        raise ProfilesFileError(ERROR_UNREADABLE, f"no file at {path}")
    except OSError as exc:
        raise ProfilesFileError(ERROR_UNREADABLE, f"{path}: {exc}")
    return parse_profiles_text(text, str(path or ""))
