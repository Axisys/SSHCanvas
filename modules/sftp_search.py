# -*- coding: utf-8 -*-
"""The PURE content search of the Files panes — the query, the matcher and the walk's report.

`normalize_query()` is the ONE reading of what the user typed; `match_lines()` is the ONE matcher, a
`(line_no, text)` pair per hit and a cap per file; `SearchReport` counts what a run really reached
(`files_scanned` / `files_matched` / `files_cut` / `bytes_read` / `matches`) and names the bound that
stopped it (`cut` + `cut_reason`). The walk and the read are the SHIPPED task family of the pane
(`queue_list()` / `queue_read()`), so this module carries no Qt, no transport and no sentence: a bound
travels as a MACHINE code here and the pane renders it.

Contract — `AGENTS.md` §4.3.6; mechanism — `DOCUMENTATION.md` §14f.
"""
try:  # the SHIPPED walk bounds — the search adds no second ceiling for an entry or a depth
    from .sftp_worker import MAX_TREE_DEPTH, MAX_TREE_ENTRIES
except ImportError:
    from sftp_worker import MAX_TREE_DEPTH, MAX_TREE_ENTRIES  # type: ignore

#: The two SCOPES of a query: the directory on the screen alone, or its whole subtree.
SEARCH_SCOPE_HERE = "here"
SEARCH_SCOPE_SUBTREE = "subtree"
SEARCH_SCOPES = (SEARCH_SCOPE_HERE, SEARCH_SCOPE_SUBTREE)
SEARCH_SCOPE_DEFAULT = SEARCH_SCOPE_SUBTREE

#: The rows ONE file contributes. A file with more hits carries the FIRST ones — the header counts the
#: rows really carried, never an estimate of the rest (the `ARCHIVE_LIST_MAX` rule, one surface over).
MATCHES_PER_FILE = 50

#: The rows ONE run contributes: the results panel is a tree, so a run that reaches this answers its
#: counters and ONE `cut` sentence instead of building a hundred thousand rows.
SEARCH_MAX_MATCHES = 1000

#: The bytes ONE run may read. Every file is bounded by the reader's own ceiling
#: (`ui_viewer_max_bytes`, resolved by the pane) and this is the TOTAL: a folder of 5 000 files at the
#: default 1 MiB cap would otherwise read 5 GiB for one query.
SEARCH_MAX_BYTES = 32 * 1024 * 1024

#: The bounds a run can meet — the machine codes of `SearchReport.cut_reason`.
CUT_ENTRIES = "entries"
CUT_DEPTH = "depth"
CUT_BYTES = "bytes"
CUT_MATCHES = "matches"
SEARCH_CUTS = (CUT_ENTRIES, CUT_DEPTH, CUT_BYTES, CUT_MATCHES)


def normalize_query(needle, case_sensitive=False, scope=SEARCH_SCOPE_DEFAULT):
    """PURE: what the user typed → the declared query record (None — there is nothing to find).

    The needle is kept BYTE FOR BYTE (a leading or trailing space may be what is searched for), while
    a blank one is refused: an empty needle matches every line of every file, which is a walk of the
    whole server and never what a user meant. A foreign scope answers the declared default.
    """
    text = str(needle if needle is not None else "")
    if not text.strip():
        return None
    return {"needle": text, "case_sensitive": bool(case_sensitive),
            "scope": scope if scope in SEARCH_SCOPES else SEARCH_SCOPE_DEFAULT}


def query_needle(query) -> str:
    """The needle of a query record (`""` — no query)."""
    return str((query or {}).get("needle") or "")


def query_scope(query) -> str:
    """The scope of a query record (`subtree` for nothing/foreign)."""
    scope = str((query or {}).get("scope") or "")
    return scope if scope in SEARCH_SCOPES else SEARCH_SCOPE_DEFAULT


def line_matches(line: str, needle: str, case_sensitive: bool = False) -> bool:
    """Does ONE line carry the needle? A plain substring — no regular expression, no word rule."""
    if not needle:
        return False
    if case_sensitive:
        return needle in line
    return needle.lower() in line.lower()


def declared_limit(value, default) -> int:
    """PURE: ONE bound as a whole number — a real `0` is a bound of ZERO, not "the default".

    `0` is legal and means "nothing fits" (a level-0 depth bound is the directory on the screen
    alone), so the fallback covers a MISSING or foreign value only. A negative number is 0.
    """
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        try:
            return max(0, int(default))
        except (TypeError, ValueError):
            return 0


def match_lines(text, needle, case_sensitive=False, limit=MATCHES_PER_FILE):
    """PURE: the hits of ONE file — `([(line_no, text)], cut)`, lines 1-based, at most `limit` pairs.

    The line text is trimmed of its `\\r` and of the trailing blanks (a row is read, not edited), the
    number is what `path:line` says. `cut` is True only when the file carries ANOTHER hit after the
    cap: the line past it is PEEKED and dropped, so a file with exactly the cap is whole and the
    caller's sentence is never an estimate.
    """
    out = []
    cap = max(1, declared_limit(limit, MATCHES_PER_FILE))
    for number, raw in enumerate(str(text or "").splitlines(), 1):
        line = raw.rstrip("\r").rstrip()
        if not line_matches(line, needle, case_sensitive):
            continue
        if len(out) >= cap:
            return out, True
        out.append((number, line))
    return out, False


class SearchReport:
    """The counters of ONE run and the bound that stopped it (PURE — no Qt, no IO, no thread).

    The caller owns the WALK (`queue_list()` / `queue_read()` of the pane's provider) and asks this
    object for every limit: `allow_depth()` before a directory is queued, `allow_entries()` per entry
    the walk meets, `allow_read()` for the cap of ONE read. A run bound is met once — the FIRST one
    wins and is kept, so the sentence the user reads names the limit the run really hit. The PER-FILE
    cap is counted separately (`files_cut`): it stops no walk, and the pane reports it once per run.
    """

    def __init__(self, query=None, entries=MAX_TREE_ENTRIES, depth=MAX_TREE_DEPTH,
                 max_bytes=SEARCH_MAX_BYTES, max_matches=SEARCH_MAX_MATCHES):
        self.query = dict(query or {})
        self.entries_limit = declared_limit(entries, MAX_TREE_ENTRIES)
        self.depth_limit = declared_limit(depth, MAX_TREE_DEPTH)
        self.bytes_limit = declared_limit(max_bytes, SEARCH_MAX_BYTES)
        self.matches_limit = declared_limit(max_matches, SEARCH_MAX_MATCHES)
        self.entries = 0
        self.files_scanned = 0
        self.files_matched = 0
        self.files_cut = 0
        self.bytes_read = 0
        self.matches = 0
        self._cut = ""

    @property
    def cut(self) -> bool:
        """Did a RUN bound stop the search before the walk was over?"""
        return bool(self._cut)

    @property
    def cut_reason(self) -> str:
        """The `CUT_*` code of that bound (`""` — the run was whole)."""
        return self._cut

    def cut_with(self, reason: str) -> bool:
        """Record the bound that stopped the run — the FIRST one wins; True when this is the first."""
        code = str(reason or "")
        if code not in SEARCH_CUTS:
            return False
        if self._cut:
            return False
        self._cut = code
        return True

    def allow_depth(self, level: int) -> bool:
        """May the walk LIST a directory `level` levels under the root? (the shipped depth bound)."""
        if int(level) > self.depth_limit:
            self.cut_with(CUT_DEPTH)
            return False
        return True

    def allow_entries(self, count: int = 1) -> bool:
        """May the walk carry `count` more entries? (the shipped entry bound, over the whole run)."""
        if self.entries + max(0, int(count)) > self.entries_limit:
            self.cut_with(CUT_ENTRIES)
            return False
        return True

    def allow_read(self, cap) -> int:
        """The cap ONE read may take: `cap` itself, the budget's rest, or 0 when the budget is spent.

        A rest SMALLER than the asked cap IS the budget stopping that read, so `CUT_BYTES` is
        recorded HERE — the read it caps spends the last bytes the run had, and a short read nobody
        names would leave the walk looking like a complete one.
        """
        left = self.bytes_limit - self.bytes_read
        if left <= 0:
            self.cut_with(CUT_BYTES)
            return 0
        try:
            wanted = int(cap or 0)
        except (TypeError, ValueError):
            wanted = 0
        if wanted <= 0:
            return 0
        if left < wanted:
            self.cut_with(CUT_BYTES)   # the budget, not the file, is what stops this read
            return left
        return wanted

    def note_entries(self, count: int = 1) -> int:
        """Count the entries the walk really saw (a directory and a file both count)."""
        self.entries += max(0, int(count))
        return self.entries

    def note_read(self, size) -> int:
        """Count ONE file the search really OPENED (a binary refusal opened it too); the bytes read."""
        self.files_scanned += 1
        try:
            self.bytes_read += max(0, int(size or 0))
        except (TypeError, ValueError):  # noqa: BLE001 — the caller owns the fallback: the byte total stands
            pass
        return self.bytes_read

    def note_matches(self, found) -> int:
        """Count the rows carried: at most what the run's own cap still allows; returns them."""
        try:
            count = max(0, len(found) if isinstance(found, (list, tuple)) else int(found or 0))
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            return 0
        self.files_matched += 1
        room = self.matches_limit - self.matches
        if room <= 0:
            self.cut_with(CUT_MATCHES)
            return 0
        carried = min(count, room)
        self.matches += carried
        if carried < count:
            self.cut_with(CUT_MATCHES)
        return carried

    def note_file_cut(self) -> int:
        """Count ONE file whose hits ran past `MATCHES_PER_FILE`; returns the files so far."""
        self.files_cut += 1
        return self.files_cut

    def as_dict(self) -> dict:
        """The report as the panel, the status line and the tests read it."""
        return {"needle": query_needle(self.query), "scope": query_scope(self.query),
                "entries": self.entries, "files_scanned": self.files_scanned,
                "files_matched": self.files_matched, "files_cut": self.files_cut,
                "bytes_read": self.bytes_read,
                "matches": self.matches, "cut": self.cut, "cut_reason": self.cut_reason}
