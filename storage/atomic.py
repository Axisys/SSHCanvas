# -*- coding: utf-8 -*-
"""Atomic writes — the ONE mechanism behind every user file of the application (AGENTS.md §4.4).

`publish_atomic(path, write_temp)` is the publish: the caller fills a UNIQUE provisional file
(`<name>.<random>.tmp`, same folder) and it is fsynced and `os.replace()`-d onto `path`, so a reader
sees the whole document or the previous one, and a failed write removes the provisional file.
`write_json_atomic()` adds the READ-MODIFY-WRITE half under `atomic_lock(path)` — an `RLock`
covering the read, the merge and the publish, which is what a MERGE-writer needs — and `dump_json()`
is the JSON `write_temp`. `read_json_state()` is the family's THREE-state reader; a merge over a
file that EXISTS and cannot be parsed COPIES it to `<file>.bad-<ts>` before the publish, and a copy
that cannot be made REFUSES that publish. The cross-process writers are deliberately OUT of scope
and DECLARED, the ONE answer the known_hosts store gives as well: the atomic replace is what keeps
a second instance from reading a truncated file. Mechanism — `DOCUMENTATION.md` §71."""
import json
import os
import shutil
import stat
import tempfile
import threading
import time

#: The suffix of the provisional file — a crash orphan reads as `<name>.<random>.tmp`.
TEMP_SUFFIX = ".tmp"

#: The three answers of ONE read of a user file — the policy every writer of the family shares.
STORE_MISSING = "missing"        # no file yet — a fresh install (a writer may create it)
STORE_OK = "ok"                  # the file parsed (the caller judges the SHAPE it expected)
STORE_UNREADABLE = "unreadable"  # the file EXISTS and cannot be parsed — a merge COPIES it first

#: The suffix of the copy a merge-writer keeps of a file it could not read: `<file>.bad-<stamp>`.
BAD_SUFFIX = ".bad-"

_locks = {}
_locks_guard = threading.Lock()


def _default_mode() -> int:
    """The mode a published file gets: what a plain `open(path, "w")` would have used (umask read
    ONCE, because `os.umask()` is process-global and must not be touched per write)."""
    try:
        mask = os.umask(0)
        os.umask(mask)
        return 0o666 & ~mask
    except OSError:
        return 0o644


#: The mode of a published file — one answer for every writer of the family.
TEMP_MODE = _default_mode()


def _log():
    """The app logger, lazily imported — the writer keeps working without the logger tree."""
    try:
        from modules.logger import get_logger
        return get_logger("storage.atomic")
    except Exception:  # noqa: BLE001 — a build without the logger still writes files
        return None


def atomic_lock(path) -> threading.RLock:
    """The ONE lock of `path`'s read-modify-write: every writer of the same file gets one object.

    A re-entrant lock, because a writer may hold it and call another function of this module.
    """
    key = os.path.normcase(os.path.abspath(str(path)))
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


def read_json_state(path):
    """ONE read of a JSON document — `(state, data, reason)`, the three answers of the family.

    `STORE_MISSING` when there is no file yet; `STORE_OK` with the parsed document, whose SHAPE the
    caller judges; `STORE_UNREADABLE` with the reason (an `OSError` text, `invalid JSON at line L
    column C`) when the file EXISTS and cannot be read — the state a merge-writer must not lose. A
    race that removes the file between the probe and the read answers `STORE_MISSING`.
    """
    if not os.path.isfile(path):
        return STORE_MISSING, None, ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return STORE_OK, json.load(handle), ""
    except FileNotFoundError:
        return STORE_MISSING, None, "the file disappeared while it was read"
    except json.JSONDecodeError as e:
        return STORE_UNREADABLE, None, f"invalid JSON at line {e.lineno} column {e.colno}"
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return STORE_UNREADABLE, None, str(e)


def read_json(path) -> dict:
    """The current document of a merge-writer: `{}` when the file is missing, broken or not an object."""
    state, data, _reason = read_json_state(path)
    if state != STORE_OK or not isinstance(data, dict):
        return {}
    return data


def keep_unreadable(path, reason: str = "") -> str:
    """COPY a file nobody could parse to `<file>.bad-<stamp>`; the copy's path, or "" on failure.

    The DECIDED policy of the merge-writers (`AGENTS.md` §4.4): a file the reader could not read is
    never silently replaced — its bytes are kept BESIDE it before the publish, and ONE log line
    names the copy. The stamp carries the second, so two merges in one second stay two copies.
    "" answers "no copy" and the CALLER owns the consequence: `write_json_atomic()` refuses the
    publish, because the copy is what makes the write safe.
    """
    logger = _log()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = f"{path}{BAD_SUFFIX}{stamp}"
    index = 1
    while os.path.exists(target):
        target = f"{path}{BAD_SUFFIX}{stamp}-{index}"
        index += 1
    try:
        shutil.copy2(path, target)
    except OSError as e:
        if logger is not None:
            logger.error("The file %s cannot be read (%s) and could not be copied aside (%s) — the "
                         "write is refused and the file is left as it is", path,
                         reason or "unreadable", e)
        return ""
    if logger is not None:
        logger.warning("The file %s cannot be read (%s) — its bytes were kept in %s before the "
                       "write", path, reason or "unreadable", target)
    return target


def dump_json(path, data, indent=2) -> None:
    """The JSON `write_temp`: the whole document into `path`, utf-8, no `\\uXXXX` escaping."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=indent)


def _fsync(path) -> None:
    """Put the bytes of a WRITTEN provisional file on the disk BEFORE it is published.

    The mode its WRITER left is preserved: a `write_temp` that COPIES a file (`shutil.copy2`) brings
    the SOURCE's own mode along, so a READ-ONLY source reaches this function unwritable and
    `os.open(…, os.O_RDWR)` would refuse the handle. Write access is granted for the ONE call and
    put back, because `os.replace()` publishes this inode's mode.
    """
    mode = stat.S_IMODE(os.stat(path).st_mode)
    writable = bool(mode & 0o200)
    if not writable:
        os.chmod(path, mode | 0o200)
    try:
        handle = os.open(path, os.O_RDWR)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)
    finally:
        if not writable:
            os.chmod(path, mode)


def _remove(path) -> None:
    """Best-effort delete of a provisional file (a failure here is never the caller's error)."""
    if not path:
        return
    try:
        os.remove(path)
    except OSError as e:
        logger = _log()
        if logger is not None:
            logger.debug("The provisional file %s was not removed (%s)", path, e)


def publish_atomic(path, write_temp) -> None:
    """Publish `path` in ONE visible step; RAISES the failure (the caller owns the answer).

    `write_temp(temp_path)` fills the provisional file. The name is UNIQUE and PREFIXED with the
    target's own name — two writers never share it, and a crash orphan is recognisable — and the
    replace happens in the SAME folder, hence on the same file system. The published file keeps the
    mode its writer gave it (`TEMP_MODE` for a plain write, the SOURCE's for a copy), so a read-only
    source is copied instead of refused.
    """
    directory = os.path.dirname(str(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=os.path.basename(str(path)) + ".", suffix=TEMP_SUFFIX,
                                    dir=directory or ".")
    os.close(handle)
    try:
        # mkstemp creates the file 0600; the published file keeps the mode a plain write would give.
        os.chmod(temp, TEMP_MODE)
        write_temp(temp)
        _fsync(temp)
        os.replace(temp, path)
    except BaseException:
        _remove(temp)
        raise


def write_json_atomic(path, data, merge: bool = False, reader=None, indent: int = 2) -> bool:
    """Write a JSON document ATOMICALLY; False on any error, never a raise.

    `merge=True` re-reads the file INSIDE the lock (a `reader`, a zero-argument callable, wins over
    the default `read_json_state(path)` read) and updates it with `data`: the read, the merge and the
    publish are ONE critical section, so two writers cannot publish each other's stale snapshot. A
    file that EXISTS and cannot be parsed is COPIED aside first (`keep_unreadable`) and the merge
    runs over an empty base. A copy that could NOT be made REFUSES the publish — False, the file
    untouched: the policy is copy-then-write, never a silent loss.
    """
    try:
        with atomic_lock(path):
            payload = data
            if merge:
                state, current, reason = read_json_state(path)
                if state == STORE_UNREADABLE:
                    if not keep_unreadable(path, reason):
                        return False
                    current = None
                if reader is not None:
                    current = reader()
                if not isinstance(current, dict):
                    current = {}
                current.update(data)
                payload = current
            publish_atomic(path, lambda temp: dump_json(temp, payload, indent=indent))
        return True
    except (OSError, TypeError, ValueError) as e:
        logger = _log()
        if logger is not None:
            logger.warning("The write of %s was refused: %s", path, e)
        return False
