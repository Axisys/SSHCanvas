# -*- coding: utf-8 -*-
"""The archive EXTRACT behind `Extract` (v1.13.1) — the pure plan, the stage and the member reader.

The WRITE half of the archive surface. `plan_extract()` walks ONE local copy of an archive and
answers the members a local disk may receive — the Zip Slip, a link / device member, a name the
platform refuses and the bomb caps are all decided there, BEFORE a byte is written — `MemberReader`
is the ONE open archive the writer streams from, and `create_stage()` / `drop_stage()` /
`sweep_stages()` own the temp folder an extraction lands in before the shipped batch machine
carries it into the destination pane. Every answer is a MACHINE CODE, never a sentence.

Contract — `ARCHIVES.md` §6; mechanism — `DOCUMENTATION.md` §77.
"""
import os
import posixpath
import shutil
import tarfile
import tempfile
import time
import zipfile

try:  # the ONE parse of the archive family (the suffix table, the walk, the two readers)
    from . import archive_view as archive
    from .sftp_worker import (MAX_TREE_ENTRIES, TREE_ERROR_TOO_BIG, local_containment_problem,
                              local_name_problem)
except ImportError:  # flat launch from the project root
    import archive_view as archive  # type: ignore
    from sftp_worker import (MAX_TREE_ENTRIES, TREE_ERROR_TOO_BIG,  # type: ignore
                             local_containment_problem, local_name_problem)

#: The KIND of the extract task of `modules/local_fs_worker.py` — declared HERE, beside the engine.
KIND_EXTRACT = "extract"

#: The caps of ONE extract (`ARCHIVES.md` §6) — the decompression bomb is answered by a cap on the
#: TOTAL and a cap on the RATIO, both asked before the first byte; the member count reuses the
#: shipped walk bound, whose code and sentence already exist.
EXTRACT_MAX_TOTAL_BYTES = 1024 * 1024 * 1024
EXTRACT_MAX_RATIO = 100
EXTRACT_MAX_ENTRIES = MAX_TREE_ENTRIES
EXTRACT_ERROR_BOMB = "extract_bomb"

#: The folder an extraction lands in when the archive's own stem is not a name this system takes.
EXTRACT_FOLDER_FALLBACK = "archive"

#: The ONE temp folder of an extraction — its own prefix, its own age rule, swept at startup.
EXTRACT_STAGE_PREFIX = "sshmap-extract-"
EXTRACT_STAGE_MAX_AGE_SEC = 6 * 60 * 60

#: The codes of an unreadable archive or member (the readers' own exceptions, never a traceback).
_READ_ERRORS = (OSError, ValueError, KeyError, EOFError, RuntimeError, NotImplementedError,
                zipfile.BadZipFile, tarfile.TarError)


def extract_folder(path) -> str:
    """The ONE folder an extraction of `path` lands in — the archive's own stem, platform-safe.

    `data.car` → `data`, `backup.tar.gz` → `backup`; the longest declared suffix wins, and a stem
    this system would not take as a name (empty, reserved, a trailing dot) falls back to
    `EXTRACT_FOLDER_FALLBACK`. PURE — the caller never invents a folder name of its own.
    """
    name = posixpath.basename(str(path or "").replace("\\", "/"))
    lowered = name.lower()
    for suffix in sorted(archive.ARCHIVE_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(suffix):
            name = name[: len(name) - len(suffix)]
            break
    name = name.rstrip(" .")
    return EXTRACT_FOLDER_FALLBACK if local_name_problem(name) else name


def local_size(path) -> int:
    """How many bytes ONE local file holds — 0 for a path the OS will not size. Never raises."""
    try:
        return max(0, int(os.path.getsize(str(path or ""))))
    except (OSError, TypeError, ValueError):
        return 0


def extract_limits(limits=None) -> tuple:
    """`(total_bytes, ratio, entries)` of ONE extraction — the declared caps, or the caller's own.

    The task carries them (`limits`), so the worker never reads a config (`AGENTS.md` §4.8); a
    foreign or non-positive value answers the declared constant, so a broken caller cannot turn a
    cap off.
    """
    data = limits if isinstance(limits, dict) else {}

    def value(key, fallback):
        try:
            number = int(data.get(key, fallback))
        except (TypeError, ValueError):
            return fallback
        return number if number > 0 else fallback

    return (value("total_bytes", EXTRACT_MAX_TOTAL_BYTES),
            value("ratio", EXTRACT_MAX_RATIO),
            value("entries", EXTRACT_MAX_ENTRIES))


def member_parts(name, dest_root) -> tuple:
    """`(the components to join under the destination, "")` — or `([], "refused")`.

    The Zip Slip is judged TWICE and by the shipped gates: a `..` component (or an absolute /
    drive-qualified member name) is refused first, every component goes through
    `local_name_problem()` — a reserved device name, a separator or a trailing dot is not a file on
    this system — and the path really written goes through `local_containment_problem()`, the
    authoritative belt (`AGENTS.md` §4.4). ONE member name is ONE component: a `\\` inside it is the
    platform's own verdict, never a second separator.
    """
    text = str(name or "")
    if not text:
        return [], "empty"
    if text.startswith("/") or (len(text) > 1 and text[1] == ":"):
        return [], "absolute"
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return [], "escape"
    if any(local_name_problem(part) for part in parts):
        return [], "name"
    if local_containment_problem(os.path.join(str(dest_root or "."), *parts), dest_root):
        return [], "outside"
    return parts, ""


def empty_plan() -> dict:
    """The plan of an archive that writes nothing — the ONE shape `plan_extract()` answers."""
    return {"dirs": [], "files": [], "skipped": [], "total": 0, "count": 0}


def bomb_code(plan: dict, archive_path, limits=None) -> str:
    """The code of ONE plan that is too much to write, or "" — the bomb and the walk bound.

    Three caps, asked BEFORE the first byte: the member count (the shipped `TREE_ERROR_TOO_BIG`,
    whose sentence already exists), the declared TOTAL and the declared RATIO against the archive's
    own size — a 1 KiB `zip` that claims 4 GiB is refused whatever the total cap is.
    """
    total_bytes, ratio, entries = extract_limits(limits)
    if int(plan.get("count") or 0) > entries:
        return TREE_ERROR_TOO_BIG
    total = int(plan.get("total") or 0)
    if total > total_bytes:
        return EXTRACT_ERROR_BOMB
    if total > max(1, local_size(archive_path)) * ratio:
        return EXTRACT_ERROR_BOMB
    return ""


def plan_extract(path, kind: str, dest_root, limits=None) -> tuple:
    """`(plan, code)` of ONE extraction — the members to write, in the archive's own order.

    A DIRECTORY member becomes a directory; a REGULAR FILE member is judged by `member_parts()`,
    carries its own mtime and counts against the caps; a LINK / DEVICE member is SKIPPED and named
    (`ARCHIVES.md` §6 — its body is a target path, not content). An encrypted archive, a path that
    is not an archive and an archive over a cap all answer ONE code.

    A non-empty `code` is a REFUSAL: the plan answers the walk's own counters (`total`, `count` and
    `skipped`, which is what the sentence needs) and NEVER a member to write, so a caller that
    honours the code cannot write a byte by accident.
    """
    resolved = kind or archive.archive_kind(path)
    if not resolved:
        return empty_plan(), archive.ARCHIVE_ERROR_UNREADABLE
    try:
        members, encrypted, code = archive.archive_members(path, resolved)
    except _READ_ERRORS:
        return empty_plan(), archive.ARCHIVE_ERROR_UNREADABLE
    if code:
        return empty_plan(), code
    if encrypted:
        return empty_plan(), archive.ARCHIVE_ERROR_ENCRYPTED
    plan = empty_plan()
    for entry in members:
        member_kind = entry.get("kind")
        if member_kind == archive.MEMBER_DIR:
            parts, _reason = member_parts(entry.get("name"), dest_root)
            if parts:
                plan["dirs"].append(tuple(parts))
            continue
        if member_kind != archive.MEMBER_FILE:
            plan["skipped"].append(str(entry.get("name") or ""))
            continue
        parts, _reason = member_parts(entry.get("name"), dest_root)
        if not parts:
            plan["skipped"].append(str(entry.get("name") or ""))
            continue
        size = max(0, int(entry.get("size") or 0))
        plan["files"].append({"raw": str(entry.get("raw") or ""), "parts": tuple(parts),
                              "size": size, "mtime": int(entry.get("mtime") or 0)})
        plan["total"] += size
        plan["count"] += 1
    refused = bomb_code(plan, path, limits)
    if refused:
        plan["files"], plan["dirs"] = [], []
        return plan, refused
    return plan, ""


class MemberReader:
    """The ONE open archive of an extraction: `stream(raw)` answers ONE member's bytes.

    The same two readers the LISTING opens, so a member a reader could open is exactly a member the
    writer can. `None` — the member is not there, or it is not a regular file.
    """

    def __init__(self, path, kind: str):
        self.path = str(path or "")
        self.kind = str(kind or "")
        self._archive = None

    def __enter__(self):
        if self.kind == archive.ARCHIVE_KIND_ZIP:
            self._archive = zipfile.ZipFile(self.path)
        else:
            self._archive = tarfile.open(self.path, "r:*")
        return self

    def __exit__(self, *_exc):
        handle, self._archive = self._archive, None
        if handle is not None:
            try:
                handle.close()
            except Exception:  # noqa: BLE001 — a close that fails on teardown is not an error
                pass
        return False

    def stream(self, raw):
        """A readable file-like of ONE member, or None. Never raises."""
        try:
            if self.kind == archive.ARCHIVE_KIND_ZIP:
                info = self._archive.getinfo(str(raw))
                if info.is_dir() or archive.zip_is_link(info):
                    return None
                return self._archive.open(info)
            info = self._archive.getmember(str(raw))
            if not info.isfile():
                return None
            return self._archive.extractfile(info)
        except _READ_ERRORS:
            return None


# ── The stage: the ONE temp folder an extraction lands in ────────────────────

def stage_root() -> str:
    """The OS temp directory — the ONE place an extraction may leave a tree."""
    return tempfile.gettempdir()


def create_stage() -> str:
    """Claim a UNIQUE temp folder for ONE extraction; "" — the folder refused.

    `mkdtemp` claims a name nobody else could have and creates it 0700 in one exclusive step, so a
    planted name is never accepted; the prefix is the family's, which is what makes `sweep_stages()`
    take the leftovers of a crashed run.
    """
    try:
        return tempfile.mkdtemp(prefix=f"{EXTRACT_STAGE_PREFIX}{os.getpid()}-", dir=stage_root())
    except OSError:
        return ""


def drop_stage(path) -> bool:
    """Delete ONE staged tree; True — it is gone. Never raises.

    The write is the SHIPPED discipline (`modules/local_fs_worker.py`): every file of the tree is
    written to `<target>.part` and committed with `os.replace` BEFORE this call, so a tree is either
    a complete extraction or nothing at all.
    """
    if not path:
        return False
    try:
        shutil.rmtree(path)
        return True
    except OSError:
        return not os.path.exists(path)


def sweep_stages(directory: str = "", max_age_sec=EXTRACT_STAGE_MAX_AGE_SEC) -> int:
    """Delete the staged trees of a CRASHED run — only the ones past the declared age. Never raises.

    The age rule is the owner rule of the shipped spool sweep: a live sibling instance keeps its
    stages (they are young, and its extraction may be mid-flight), while a crashed run's leftovers
    go at the next startup.
    """
    folder = directory or stage_root()
    removed = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0
    now = time.time()
    for name in names:
        if not name.startswith(EXTRACT_STAGE_PREFIX):
            continue
        candidate = os.path.join(folder, name)
        try:
            if (now - os.lstat(candidate).st_mtime) <= float(max_age_sec):
                continue   # young enough to belong to a live instance (or to this one)
        except (OSError, TypeError, ValueError):
            continue
        if drop_stage(candidate):
            removed += 1
    return removed
