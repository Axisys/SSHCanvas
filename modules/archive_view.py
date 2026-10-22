# -*- coding: utf-8 -*-
"""The archive READER behind `Open archive` (v1.13) — the pure parse, the policy and the spool.

The suffix table decides the reader (`zipfile` / `tarfile`), `archive_listing()` answers the READABLE
members of ONE level, `read_member()` is the bounded read of the preview and
`resolve_archive_max_bytes()` is the declared cap — a key of its OWN (`ui_archive_max_bytes`). The
spool is the SHIPPED family of `modules/sftp_send.py` (`create_spool()` / `prepare_spool()` /
`drop_spool()` / `sweep_spools()`), so a remote archive reaches the standard library through the ONE
temp path the relay already uses. Every answer is a MACHINE CODE, never a sentence.

Contract — `ARCHIVES.md` §2-§4; mechanism — `DOCUMENTATION.md` §76.
"""
import lzma
import os
import posixpath
import tarfile
import zipfile
import zlib
from datetime import datetime

try:  # the declared read policy and the extension screen of the SHIPPED reader
    from .sftp_worker import (CHUNK_SIZE, MAX_READ_BYTES, MAX_TREE_ENTRIES, READ_ERROR_BINARY,
                              READ_ERROR_TOO_LARGE, classify_extension)
except ImportError:  # flat launch from the project root
    from sftp_worker import (CHUNK_SIZE, MAX_READ_BYTES, MAX_TREE_ENTRIES,  # type: ignore
                             READ_ERROR_BINARY, READ_ERROR_TOO_LARGE, classify_extension)

ARCHIVE_KIND_ZIP = "zip"
ARCHIVE_KIND_TAR = "tar"

#: ONE declaration of the family (`ARCHIVES.md` §2): the suffix decides the READER, the content
#: decides the truth — a `.car` is a ZIP container of the same family as `.war` / `.jar`, and
#: `tarfile`'s `r:*` covers every compression the standard library knows.
ZIP_SUFFIXES = (".zip", ".car", ".war", ".jar", ".ear")
TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
ARCHIVE_SUFFIXES = {**{suffix: ARCHIVE_KIND_ZIP for suffix in ZIP_SUFFIXES},
                    **{suffix: ARCHIVE_KIND_TAR for suffix in TAR_SUFFIXES}}

#: The declared CAP of ONE archive — a key of its OWN, never `ui_viewer_max_bytes`: it bounds the
#: temp copy of a remote archive AND the stream `tarfile` walks to list one (a `tar.gz` listing is
#: O(size)), while the reader's ceiling bounds ONE member's preview.
ARCHIVE_MAX_BYTES_CONFIG = "ui_archive_max_bytes"
ARCHIVE_MAX_BYTES = 256 * 1024 * 1024

#: The ROW bound of ONE listing — the SHIPPED walk bound, because it answers the same question on
#: the same subject ("how many members does this application carry at once"). The cap above bounds
#: BYTES and says nothing about a zip of a million empty files: 100 000 members cost ~18 s and
#: ~76 MB on the GUI thread (the release's measurement), which is a frozen window, not a listing.
ARCHIVE_LIST_MAX = MAX_TREE_ENTRIES

#: The machine codes of this module: the listing's two, and the read's own (the shipped
#: `sftp_worker.READ_ERROR_*` answer the rest, so the pane renders every one of them with ONE table).
ARCHIVE_ERROR_UNREADABLE = "unreadable"
ARCHIVE_ERROR_ENCRYPTED = "encrypted"

#: What ONE member of an archive IS (`archive_members()`): the listing keeps the FILE kind and the
#: extract half asks the rest (`ARCHIVES.md` §3, §6). A directory is a prefix of its children's
#: names, a link's body is its target path and a device holds no bytes at all.
MEMBER_FILE = "file"
MEMBER_DIR = "dir"
MEMBER_LINK = "link"
MEMBER_DEVICE = "device"

#: The zip general-purpose bit 0 marks an encrypted member (APPNOTE 4.4.4) and bit 15 the file type
#: of `external_attr >> 16` — the ONE way a zip spells "this is a symlink".
ZIP_ENCRYPTED_FLAG = 0x1
ZIP_FILE_TYPE_BITS = 0o170000
ZIP_SYMLINK_BITS = 0o120000

#: The codes of an unreadable path or member (the readers' own exceptions, never a traceback) — the
#: ONE declaration of the family: both halves catch the parse's own refusals through it. The two
#: DECOMPRESSORS answer exceptions of their own (`zlib.error` on a corrupt DEFLATE stream,
#: `lzma.LZMAError` on a corrupt xz one), and they are refused members like any other parse failure.
READ_ERRORS = (OSError, ValueError, KeyError, EOFError, RuntimeError, NotImplementedError,
               zipfile.BadZipFile, tarfile.TarError, zlib.error, lzma.LZMAError)


def archive_kind(path) -> str:
    """The declared READER of a path — "zip" | "tar" | "" (the suffix is not an archive of this family).

    The suffix is a HINT and the parse is the verdict (the `detect_syntax()` rule of the reader): a
    file this table does not know is never opened, and one it knows is refused by the parse when the
    content does not agree.
    """
    name = posixpath.basename(str(path or "").replace("\\", "/")).lower()
    for suffix, kind in ARCHIVE_SUFFIXES.items():
        if name.endswith(suffix):
            return kind
    return ""


def member_name(raw) -> str:
    """The ONE spelling of a member: a leading "./" is noise, the rest is the archive's own name."""
    name = str(raw or "")
    while name.startswith("./"):
        name = name[2:]
    return name


def size_allowed(size, limit=None) -> bool:
    """Is this many bytes inside the declared cap of ONE archive?"""
    try:
        return 0 <= int(size or 0) <= int(ARCHIVE_MAX_BYTES if limit is None else limit)
    except (TypeError, ValueError):
        return False


def resolve_archive_max_bytes(cfg: dict = None) -> int:
    """The declared cap as a PURE value: the config's number, else `ARCHIVE_MAX_BYTES`.

    Only a real positive integer counts — a string, a boolean, a zero, a negative or an unreadable
    config answers the default (the `resolve_viewer_max_bytes()` rule).
    """
    if not isinstance(cfg, dict):
        try:
            from i18n import load_config
        except Exception:  # noqa: BLE001 — a build without i18n keeps the default
            return ARCHIVE_MAX_BYTES
        try:
            cfg = load_config() or {}
        except Exception:  # noqa: BLE001 — a broken config store keeps the default
            cfg = {}
    value = cfg.get(ARCHIVE_MAX_BYTES_CONFIG) if isinstance(cfg, dict) else None
    if isinstance(value, bool):
        return ARCHIVE_MAX_BYTES
    try:
        value = int(value)
    except (TypeError, ValueError):
        return ARCHIVE_MAX_BYTES
    return value if value > 0 else ARCHIVE_MAX_BYTES


def local_size(path) -> int:
    """How many bytes ONE local file holds — 0 for a path the OS will not size. Never raises.

    The ONE reader of the size the cap is really asked about: the listing's row is a hint the server
    wrote, while the copy on THIS disk is the file a parse would open (`ARCHIVES.md` §2).
    """
    try:
        return max(0, int(os.path.getsize(str(path or ""))))
    except (OSError, TypeError, ValueError):
        return 0


# ── The listing: the READABLE members of ONE level ───────────────────────────

def _entry(raw, size, mtime, kind: str = MEMBER_FILE) -> dict:
    """ONE row of the walk — the display name, the RAW name the reader asks for, its facts, its kind."""
    return {"name": member_name(raw), "raw": str(raw or ""), "size": int(size or 0),
            "mtime": int(mtime or 0), "kind": str(kind or MEMBER_FILE)}


def _zip_mtime(info) -> int:
    try:
        return int(datetime(*tuple(info.date_time)).timestamp())
    except (TypeError, ValueError, OverflowError, OSError):
        return 0


def zip_is_link(info) -> bool:
    """Is this member a SYMLINK? (`external_attr >> 16` carries the POSIX mode when it is set.)"""
    mode = int(getattr(info, "external_attr", 0) or 0) >> 16
    return (mode & ZIP_FILE_TYPE_BITS) == ZIP_SYMLINK_BITS


def _zip_kind(info) -> str:
    if info.is_dir():
        return MEMBER_DIR
    return MEMBER_LINK if zip_is_link(info) else MEMBER_FILE


def _zip_members(path, limit: int = 0, wanted=None):
    entries, encrypted = [], False
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if limit > 0 and len(entries) > limit:
                break   # one WANTED member PAST the bound: the caller can tell the walk was cut
            if int(info.flag_bits or 0) & ZIP_ENCRYPTED_FLAG:
                encrypted = True
            kind = _zip_kind(info)
            if wanted is not None and not wanted(kind):
                continue
            entries.append(_entry(info.filename, info.file_size, _zip_mtime(info), kind))
    return entries, encrypted, ""


def _tar_kind(info) -> str:
    if info.isdir():
        return MEMBER_DIR
    if info.isfile():
        return MEMBER_FILE
    if info.issym() or info.islnk():
        return MEMBER_LINK
    return MEMBER_DEVICE   # a character / block device or a fifo: no bytes a panel could open


def _tar_members(path, limit: int = 0, wanted=None):
    entries = []
    with tarfile.open(path, "r:*") as archive:
        for info in archive:
            if limit > 0 and len(entries) > limit:
                break   # streaming: the rest of the container is never even decompressed
            kind = _tar_kind(info)
            if wanted is not None and not wanted(kind):
                continue
            entries.append(_entry(info.name, info.size, info.mtime, kind))
    return entries, False, ""


def archive_members(path, kind: str = "", limit: int = 0, wanted=None) -> tuple:
    """`(members, encrypted, code)` of ONE archive — the entries of ONE level, in archive order.

    The full walk behind `archive_listing()`: a directory member is a prefix of its children's
    names (a zip may omit it entirely), the body of a symlink / hardlink member is its TARGET PATH
    and a device or fifo member holds no bytes — the listing drops them and the extract half owns
    what they mean (`ARCHIVES.md` §3, §6), so ONE parse serves both halves.

    A positive `limit` is the ENTRY BOUND of the walk: it answers at most `limit + 1` members, so a
    5 000-member cap costs 5 001 entries of memory and time whatever the archive holds beyond it.
    `wanted` is the KIND filter of the READ half (a row is a regular FILE member): the bound counts
    what the filter KEEPS, so 100 000 directory entries ahead of the first readable file cost the
    walk and never the rows.
    """
    resolved = kind or archive_kind(path)
    if not resolved:
        return [], False, ARCHIVE_ERROR_UNREADABLE
    try:
        if resolved == ARCHIVE_KIND_ZIP:
            return _zip_members(path, limit, wanted)
        return _tar_members(path, limit, wanted)
    except READ_ERRORS:
        return [], False, ARCHIVE_ERROR_UNREADABLE


def _is_row(kind) -> bool:
    """Is this member a ROW of the listing? (the ONE predicate the READ half filters with)"""
    return kind == MEMBER_FILE


def archive_listing(path, kind: str = "", limit: int = 0) -> tuple:
    """`(entries, encrypted, code, cut)` of ONE archive — the members a READER can open, in order.

    A row is a REGULAR FILE member: a directory entry is a prefix of its children's names, and the
    body of a link member is its TARGET PATH rather than content, so neither is something the panel
    could preview (the extract half owns what those members mean, `ARCHIVES.md` §6). `encrypted` is
    the zip flag — a `tar` container declares none — and an encrypted archive still LISTS: its
    members are refused at the read, with ONE sentence and no password prompt.

    A positive `limit` is the ROW bound: the answer holds at most `limit` rows and `cut` says the
    walk met more, so a panel never builds more rows than the bound and never claims a total it did
    not count (`ARCHIVE_LIST_MAX` is the caller's number).
    """
    members, encrypted, code = archive_members(path, kind, limit, wanted=_is_row)
    if code:
        return [], encrypted, code, False
    if limit > 0 and len(members) > limit:
        return members[:limit], encrypted, "", True
    return members, encrypted, "", False


# ── The read of ONE member: the shipped policy, bounded twice ────────────────

def read_member(path, kind: str, raw: str, cap=0, size=0) -> tuple:
    """`(data, code)` of ONE member's first `cap` bytes — the shipped read policy, over a member.

    The SAME three screens a local file passes (`modules/local_fs_worker.py`): a binary extension (a
    nested archive of the declared family included — ONE level, `ARCHIVES.md` §3), the NULL byte of
    the first chunk, and the ceiling, which TRUNCATES instead of refusing once it is positive. A
    positive `size` above a cap of ZERO is refused (`READ_ERROR_TOO_LARGE`, the shipped
    `READ_CAP_NONE` rule); an encrypted archive answers `ARCHIVE_ERROR_ENCRYPTED` from the reader
    itself and no password is ever asked.
    """
    if archive_kind(raw) or classify_extension(raw) == "binary":
        return b"", READ_ERROR_BINARY
    resolved = kind or archive_kind(path)
    try:
        if resolved == ARCHIVE_KIND_ZIP:
            return _read_zip(path, raw, cap, size)
        if resolved == ARCHIVE_KIND_TAR:
            return _read_tar(path, raw, cap, size)
    except READ_ERRORS:
        return b"", ARCHIVE_ERROR_UNREADABLE
    return b"", ARCHIVE_ERROR_UNREADABLE


def _bounded(stream, cap, size):
    """The shipped chunked read over ONE open member: the NULL screen, the ceiling, 32 KB chunks."""
    try:
        limit = int(cap or 0)
    except (TypeError, ValueError):
        limit = 0
    truncating = limit > 0
    if not truncating:
        limit = MAX_READ_BYTES
        try:
            if int(size or 0) > limit:
                return b"", READ_ERROR_TOO_LARGE
        except (TypeError, ValueError):  # noqa: BLE001 — the caller owns the fallback: the read bound stands
            pass
    chunks, done = [], 0
    while True:
        want = CHUNK_SIZE if not truncating else min(CHUNK_SIZE, limit - done)
        if want <= 0:
            break
        chunk = stream.read(want)
        if not chunk:
            break
        if not chunks and b"\x00" in chunk:
            return b"", READ_ERROR_BINARY
        done += len(chunk)
        if not truncating and done > limit:
            return b"", READ_ERROR_TOO_LARGE
        chunks.append(chunk)
    return b"".join(chunks), ""


def _read_zip(path, raw, cap, size):
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(raw)
        if info.is_dir() or zip_is_link(info):
            return b"", READ_ERROR_BINARY   # nothing a reader could show
        try:
            with archive.open(info) as stream:
                return _bounded(stream, cap, size)
        except RuntimeError as exc:
            # The ONE RuntimeError a READ answers is the password zipfile refuses to invent: the
            # archive lists its members and this read is refused — no prompt, no second question.
            if "encrypted" in str(exc).lower():
                return b"", ARCHIVE_ERROR_ENCRYPTED
            raise


def _read_tar(path, raw, cap, size):
    with tarfile.open(path, "r:*") as archive:
        info = archive.getmember(raw)
        if not info.isfile():
            return b"", READ_ERROR_BINARY   # a link's body is its target path, a device has none
        stream = archive.extractfile(info)
        if stream is None:
            return b"", READ_ERROR_BINARY
        with stream:
            return _bounded(stream, cap, size)


# ── The spool: the SHIPPED family of `modules/sftp_send.py` ──────────────────

def _spool_family():
    """The shipped spool family, imported LATE (`modules/sftp_send.py` imports the pane family)."""
    try:
        from . import sftp_send as send
    except ImportError:  # flat launch from the project root
        import sftp_send as send
    return send


def spool_archive(name: str = "") -> str:
    """Claim the temp copy of ONE archive through the SHIPPED spool family; "" — the folder refused.

    `create_spool()` claims a name nobody else could have (`mkstemp`, the tight mode) and
    `prepare_spool()` verifies its provisional twin before the first byte, so a planted name answers
    "" instead of being accepted. The prefix is the relay's: `sweep_spools()` at startup takes the
    leftovers of BOTH kinds, and the age rule keeps a live instance's spools young.
    """
    send = _spool_family()
    path = send.create_spool(str(name or ""))
    if not path or not send.prepare_spool(path):
        send.drop_spool(path)   # a refused spool leaves nothing of ours in the temp folder
        return ""
    return path


def spool_download_args(spool: str) -> tuple:
    """`(folder, name, mode)` — the three arguments the DOWNLOAD leg of ONE spool needs.

    The mode is the family's OWN declaration (`sftp_send.SPOOL_FILE_MODE`): the leg publishes the
    inode of the provisional file it creates, so the permission travels WITH the task
    (`queue_download(part_mode=…)`) instead of being applied to the destination afterwards.
    """
    return (os.path.dirname(str(spool or "")), os.path.basename(str(spool or "")),
            _spool_family().SPOOL_FILE_MODE)


def drop_archive(path: str) -> int:
    """Delete a spool AND its provisional twin through the SHIPPED family; how many went. Never raises."""
    if not path:
        return 0
    return _spool_family().drop_spool(path)
