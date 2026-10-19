# -*- coding: utf-8 -*-
"""The defects a third-party read of the shipped `v1.13.1` confirmed, each one REPRODUCED (v1.13.1.1).
§1 the LOCAL refusal classifier — a file another process holds is `locked`, never `permission`; §2 the
extract's delivery — the success sentence belongs to a tree that really landed and names the folder
that RECEIVED it; §3 the refusal payload — the sentence names the ceiling the plan CROSSED; §4 the
archive member path — a member is asked of the ARCHIVE through both its spellings; §5 the reader's
share — the panel that was filled is the panel that is sized; §6 the destination — the directory and
its names are ONE moment; §7 the counters, the ONE cap verdict, the ONE exception tuple, the release.
Rule — `AGENTS.md` §4.3.6, §4.4.3, §12.5; mechanism — `DOCUMENTATION.md` §59, §76, §77.
"""
import os
import shutil
import sys
import zipfile

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least, wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import i18n  # noqa: E402
import modules.archive_extract as AX  # noqa: E402
import modules.archive_view as AV  # noqa: E402
import modules.local_fs_worker as LOCAL  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402
from modules.sftp_tab import SOURCE_LOCAL, SftpTab  # noqa: E402
from modules.sftp_worker import SftpWorker, TREE_ERROR_TOO_BIG  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)
WORK_TREE = os.path.join(WORK, "patch")
#: The member of §4: its RAW spelling (`./notes.txt`) is NOT the display one, and its UTF-8 bytes
#: decode differently under `cp1251` — so "the ARCHIVE answered" is visible in the text itself.
_RAW_MEMBER = "./notes.txt"
_MEMBER_BYTES = b"\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82\n"
_STAGES = []


def build_zip(path, members):
    """A REAL zip: `members` = [(name, bytes)]."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    return path


def make_stage(marker="marker.txt", text=b"payload\n"):
    """A REAL stage tree of ONE extraction — what `_on_extract_ready()` receives."""
    stage = AX.create_stage()
    _STAGES.append(stage)
    with open(os.path.join(stage, marker), "wb") as handle:
        handle.write(text)
    return stage


def plant_extract(tab, task_id, record):
    """Put ONE extraction in flight — the record shape the door writes, planted by hand."""
    tab._extracts[int(task_id)] = record


def make_remote_tab(fs):
    """(tab, worker, log) over the fake SFTP surface, in the two-pane mode."""
    worker = SftpWorker(FakeSftpClient(fs))
    log = EventLog()
    wire_worker(worker, log)
    worker.start()
    tab = SftpTab()
    tab.message.connect(lambda *_a: None)
    tab.set_commander(True)
    tab.set_worker(worker)
    return tab, worker, log


def rows(pane):
    return [pane.tree.topLevelItem(index).text(0) for index in range(pane.tree.topLevelItemCount())]


def item_named(pane, name):
    for index in range(pane.tree.topLevelItemCount()):
        if pane.tree.topLevelItem(index).text(0) == name:
            return pane.tree.topLevelItem(index)
    return None


def wait_row(pane, name, ms=10000):
    return wait_for(lambda: name in rows(pane), timeout_ms=ms)


def open_archive(pane, item, ms=10000):
    pane._op_view_archive(item)
    app.processEvents()
    return wait_for(lambda: pane.archive_open, timeout_ms=ms)


def run_extract(worker, archive_path, dest_dir, limits=None, ms=20000):
    """Drive ONE extraction on a bare `LocalFsWorker` and answer `(result, error_payload)`."""
    seen = {"result": None, "error": ""}
    worker.extract_ready.connect(
        lambda _i, tree, written, skipped: seen.update(result=(tree, written, skipped)))
    worker.task_error.connect(lambda _i, _k, message: seen.update(error=message))
    worker.queue_extract(archive_path, dest_dir, folder="", limits=limits)
    wait_for(lambda: seen["result"] is not None or bool(seen["error"]), timeout_ms=ms)
    return seen["result"], seen["error"]


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the LOCAL refusal classifier: a held file is LOCKED, never a permission ==")
# ════════════════════════════════════════════════════════════════════════════

_SHARING = PermissionError(32, "The process cannot access the file")
_SHARING.winerror = 32
_LOCK_VIOLATION = OSError(33, "The file is locked")
_LOCK_VIOLATION.winerror = 33
check("§1 the Windows sharing / lock violations answer `locked` (a tuple is MEMBERSHIP, not equality)",
      LOCAL.local_error_code(_SHARING) == LOCAL.LOCAL_LOCKED
      and LOCAL.local_error_code(_LOCK_VIOLATION) == LOCAL.LOCAL_LOCKED,
      f"32 -> {LOCAL.local_error_code(_SHARING)}, 33 -> {LOCAL.local_error_code(_LOCK_VIOLATION)}, "
      f"WINERROR_LOCKED={LOCAL.WINERROR_LOCKED!r}")
check("§1 ...and the numeric gate is asked BEFORE `PermissionError` (the platform maps 32/33 onto EACCES)",
      isinstance(_SHARING, PermissionError)
      and LOCAL.local_error_code(_SHARING) != LOCAL.LOCAL_PERMISSION
      and LOCAL.local_error_code(PermissionError(13, "denied")) == LOCAL.LOCAL_PERMISSION)
_TOO_LONG = OSError(206, "name too long")
_TOO_LONG.winerror = 206
check("§1 the other declared code keeps its own branch (`winerror` 206 → too_long)",
      LOCAL.local_error_code(_TOO_LONG) == LOCAL.LOCAL_TOO_LONG
      and LOCAL.local_error_code(OSError("other")) == LOCAL.LOCAL_UNREADABLE)
_LOCKED_KEY = LOCAL.LOCAL_ERROR_KEYS[LOCAL.LOCAL_LOCKED]
check("§1 the `locked` sentence is declared in every language (the code table answers a real key)",
      all(str(data.get(_LOCKED_KEY) or "").strip() for data in LANGS.values())
      and "{error}" in str(LANGS["en"].get(_LOCKED_KEY) or ""),
      str({code: bool(data.get(_LOCKED_KEY)) for code, data in LANGS.items()}))

if os.name == "nt":
    # The real OS shape: a byte range held by another handle, removed by this process — the report's
    # own reproduction, and the reason the numeric gate cannot be an `isinstance()` chain alone.
    import msvcrt  # noqa: E402 — a Windows-only import, inside the guard

    _HOLD_DIR = os.path.join(WORK, "held")
    os.makedirs(_HOLD_DIR, exist_ok=True)
    _HELD = os.path.join(_HOLD_DIR, "held.bin")
    with open(_HELD, "wb") as _handle:
        _handle.write(b"x" * 16)
    _FD = os.open(_HELD, os.O_RDWR)
    msvcrt.locking(_FD, msvcrt.LK_NBLCK, 1)
    try:
        os.remove(_HELD)
        _REAL = None
    except OSError as _exc:   # the refusal IS the subject here
        _REAL = _exc
    msvcrt.locking(_FD, msvcrt.LK_UNLCK, 1)
    os.close(_FD)
    check("§1 ...and a REAL Windows lock reproduces the report: `locked`, not `permission`",
          _REAL is not None and getattr(_REAL, "winerror", None) in LOCAL.WINERROR_LOCKED
          and LOCAL.local_error_code(_REAL) == LOCAL.LOCAL_LOCKED,
          f"{type(_REAL).__name__ if _REAL else 'no error'} "
          f"winerror={getattr(_REAL, 'winerror', None)} "
          f"-> {LOCAL.local_error_code(_REAL) if _REAL else '-'}")
else:
    print("  SKIP  the real Windows byte-range lock (this platform does not hold one)")

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the delivery report: a success sentence belongs to a tree that really landed ==")
# ════════════════════════════════════════════════════════════════════════════

if os.path.isdir(WORK_TREE):
    shutil.rmtree(WORK_TREE, ignore_errors=True)
os.makedirs(WORK_TREE)
_REMOTE = FakeSftpFS()
for _dir in ("/srv", "/srv/data", "/srv/data-2", "/srv/quiet", "/empty"):
    _REMOTE.add_dir(_dir)
_REMOTE.add_file("/srv/data.car", b"PK\x03\x04", mtime=1_700_000_000)
_TAB, _WORKER, _LOG = make_remote_tab(_REMOTE)
_PANE_A, _PANE_B = _TAB.panes[0], _TAB.panes[1]
_PANE_A._relist("/srv")
check("§2 the remote pane lists the fake server (the fixture is real)",
      wait_row(_PANE_A, "data.car"), str(rows(_PANE_A)))
_SEEN = []
_PANE_A.message.connect(_SEEN.append)
_ASKED = []


def _answer(action):
    """The shipped conflict seam, replaced by the ONE answer this check is about."""
    return lambda name, target, remaining, facts="": (
        _ASKED.append((name, target)) or (action, False))


def _record(dest_dir, known, name, stage):
    return {"pane": _PANE_A, "dest_pane": _PANE_A, "dest_dir": dest_dir, "known": known,
            "name": name, "stage": stage, "local": "", "spool": "", "closed": False}


_PANE_A._ask_conflict = _answer("skip")
_STAGE_SKIP = make_stage()
plant_extract(_TAB, 9001, _record("/srv", {"data"}, "data", _STAGE_SKIP))
_TAB._on_extract_ready(9001, _STAGE_SKIP, 2, [])
check("§2 `Skip` writes nothing AND reports nothing (the shipped lie named a path nothing reached)",
      _ASKED == [("data", "/srv")]
      and i18n.t("sftp.archive.extract_done", count=2, target="/srv/data") not in _SEEN
      and not os.path.exists(_STAGE_SKIP)
      and "/srv/data/marker.txt" not in _REMOTE.files,
      f"asked={_ASKED} seen={_SEEN}")

_PANE_A._ask_conflict = _answer("overwrite")
_STAGE_OK = make_stage()
plant_extract(_TAB, 9002, _record("/srv", {"data"}, "data", _STAGE_OK))
_TAB._on_extract_ready(9002, _STAGE_OK, 2, ["link.txt"])
check("§2 a DELIVERED tree reports the files it wrote and the folder that received it",
      wait_for(lambda: i18n.t("sftp.archive.extract_done", count=2, target="/srv/data") in _SEEN,
               timeout_ms=15000)
      and wait_for(lambda: i18n.t("sftp.local.skipped", count=1, names="link.txt") in _SEEN,
                   timeout_ms=15000)
      and wait_for(lambda: "/srv/data/marker.txt" in _REMOTE.files, timeout_ms=15000),
      f"seen={_SEEN} files={sorted(_REMOTE.files)}")

_PANE_A._prompt_name = lambda title, current="": "data-2"
_PANE_A._ask_conflict = _answer("rename")
_STAGE_RENAMED = make_stage()
plant_extract(_TAB, 9003, _record("/srv", {"data"}, "data", _STAGE_RENAMED))
_TAB._on_extract_ready(9003, _STAGE_RENAMED, 1, [])
check("§2 ...and `Rename` reports the folder the tree LANDED in, never the name it was asked about",
      wait_for(lambda: i18n.t("sftp.archive.extract_done", count=1, target="/srv/data-2") in _SEEN,
               timeout_ms=15000)
      and wait_for(lambda: "/srv/data-2/marker.txt" in _REMOTE.files, timeout_ms=15000)
      and i18n.t("sftp.archive.extract_done", count=1, target="/srv/data") not in _SEEN,
      f"seen={_SEEN} files={sorted(_REMOTE.files)}")

# The LOCAL pane is the one whose provider can be GONE without touching the container's binding.
check("§2 the second pane takes the OS disk as its source (the LOCAL_PANE.md §4 rule)",
      _TAB.can_use_local(_PANE_A) is False and _TAB.can_use_local(_PANE_B) is True
      and _TAB.set_pane_source(_PANE_B, SOURCE_LOCAL) is True
      and _PANE_B.source == SOURCE_LOCAL)
_SEEN_REFUSAL = []
_PANE_B.message.connect(_SEEN_REFUSAL.append)
_STAGE_GONE = make_stage()
_SAVED_LOCAL = _PANE_B._local_provider
_PANE_B._local_provider = None   # the declared "provider is gone" state of a LOCAL pane
_ANSWERED = _PANE_B.ship_staged_tree(_STAGE_GONE, "/srv", "data", {"data"})
_PANE_B._local_provider = _SAVED_LOCAL
check("§2 a provider that is gone answers `\"\"` and keeps its OWN sentence — one answer, never a pair",
      _ANSWERED == "" and i18n.t("sftp.waiting_connection") in _SEEN_REFUSAL
      and os.path.exists(_STAGE_GONE), f"{_ANSWERED!r} {_SEEN_REFUSAL}")
AX.drop_stage(_STAGE_GONE)

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the refusal payload: the sentence names the ceiling the plan CROSSED ==")
# ════════════════════════════════════════════════════════════════════════════

_ENTRIES_ZIP = build_zip(os.path.join(WORK, "many.zip"),
                         [("a.txt", b"a\n"), ("b.txt", b"b\n"), ("c.txt", b"c\n")])
_BOMB_ZIP = build_zip(os.path.join(WORK, "bomb.zip"), [("big.bin", b"\x00" * 200000)])
_VERDICT = getattr(AX, "bomb_verdict", None)
_LIMIT = getattr(AX, "refusal_limit", None)


def _limit_of(plan, path, limits=None):
    """The crossed ceiling through the seam IF this build has it — a DETAIL must never raise."""
    return _LIMIT(plan, path, limits) if callable(_LIMIT) else "-"


check("§3 the ONE cap verdict answers the code AND the ceiling it crossed",
      callable(_VERDICT) and callable(_LIMIT)
      and _VERDICT({"count": SW.MAX_TREE_ENTRIES + 1, "entries": SW.MAX_TREE_ENTRIES + 1,
                    "total": 0}, _ENTRIES_ZIP, None)
      == (TREE_ERROR_TOO_BIG, AX.EXTRACT_MAX_ENTRIES)
      and _VERDICT({"count": 1, "entries": 1, "total": 200000}, _BOMB_ZIP, {"total_bytes": 1024})
      == (AX.EXTRACT_ERROR_BOMB, 1024)
      and AX.EXTRACT_MAX_ENTRIES == 5000 and AX.EXTRACT_MAX_TOTAL_BYTES == 1024 ** 3,
      f"entries={AX.EXTRACT_MAX_ENTRIES} total={AX.EXTRACT_MAX_TOTAL_BYTES}")
check("§3 a COUNT refusal names the entry cap (a byte cap here read '1 073 741 824 entries')",
      callable(_LIMIT)
      and _LIMIT({"entries": SW.MAX_TREE_ENTRIES + 1, "total": 0}, _ENTRIES_ZIP, None) == 5000
      and _LIMIT({"entries": 5001, "total": 0}, _ENTRIES_ZIP, {"entries": 7}) == 7)
check("§3 a BYTE refusal names the ceiling that was really crossed — total, or the ratio threshold",
      callable(_LIMIT)
      and _LIMIT({"count": 1, "total": 200000}, _BOMB_ZIP, {"total_bytes": 1024}) == 1024
      and _LIMIT({"count": 1, "total": 200000}, _BOMB_ZIP, {"total_bytes": 10 ** 9, "ratio": 2})
      == max(1, os.path.getsize(_BOMB_ZIP)) * 2
      # The DECLARED caps: the ratio (100 × the archive's own size) is the smaller ceiling here, and
      # it is the one the sentence must name — the total cap is 1 GiB and was never reached.
      and _LIMIT({"count": 1, "total": 200000}, _BOMB_ZIP)
      == max(1, os.path.getsize(_BOMB_ZIP)) * AX.EXTRACT_MAX_RATIO
      and _LIMIT({"count": 1, "total": 200000}, _BOMB_ZIP) != AX.EXTRACT_MAX_TOTAL_BYTES
      and _LIMIT({"count": 1, "total": 10}, _BOMB_ZIP, None) == 0,
      f"total={_limit_of({'count': 1, 'total': 200000}, _BOMB_ZIP, {'total_bytes': 1024})} "
      f"declared={_limit_of({'count': 1, 'total': 200000}, _BOMB_ZIP)} "
      f"ratio={_limit_of({'count': 1, 'total': 200000}, _BOMB_ZIP, {'ratio': 2})}")

_EXTRACT_WORKER = LOCAL.LocalFsWorker(root=WORK)
_EXTRACT_WORKER.start()
_COUNTED, _COUNTED_ERROR = run_extract(_EXTRACT_WORKER, _ENTRIES_ZIP, os.path.join(WORK_TREE, "many"),
                                       limits={"entries": 2})
_COUNTED_PAYLOAD = SW.parse_task_payload(_COUNTED_ERROR) or {}
check("§3 the ENGINE's count refusal carries the entry cap in its payload",
      _COUNTED is None and _COUNTED_PAYLOAD.get("code") == TREE_ERROR_TOO_BIG
      and _COUNTED_PAYLOAD.get("limit") == 2 and _COUNTED_PAYLOAD.get("count") == 3,
      str(_COUNTED_ERROR))
_RATIO_REFUSED, _RATIO_ERROR = run_extract(_EXTRACT_WORKER, _BOMB_ZIP, os.path.join(WORK_TREE, "bombed"),
                                           limits={"total_bytes": 10 ** 9, "ratio": 2})
_RATIO_PAYLOAD = SW.parse_task_payload(_RATIO_ERROR) or {}
check("§3 ...and a RATIO refusal carries the threshold it crossed, not the total cap",
      _RATIO_REFUSED is None and _RATIO_PAYLOAD.get("code") == AX.EXTRACT_ERROR_BOMB
      and _RATIO_PAYLOAD.get("limit") == max(1, os.path.getsize(_BOMB_ZIP)) * 2,
      str(_RATIO_ERROR))
_COUNT_SENTENCE = SftpTab._extract_error_text(_COUNTED_ERROR)
check("§3 the sentence the user reads names those numbers (the shipped renderer, unchanged)",
      _COUNT_SENTENCE == i18n.t("sftp.cmd.tree_too_big", limit=2)
      and "1073741824" not in _COUNT_SENTENCE
      and SftpTab._extract_error_text(
          SW.task_payload(TREE_ERROR_TOO_BIG, count=5001, total=0,
                          limit=AX.EXTRACT_MAX_ENTRIES))
      == i18n.t("sftp.cmd.tree_too_big", limit=5000),
      _COUNT_SENTENCE)

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the member of the open archive: BOTH spellings are asked of the ARCHIVE ==")
# ════════════════════════════════════════════════════════════════════════════

_LOCAL_ZIP = build_zip(os.path.join(WORK_TREE, "dots.zip"), [(_RAW_MEMBER, _MEMBER_BYTES)])
check("§4 the fixture IS the trap: the RAW name is not the display one",
      AV.member_name(_RAW_MEMBER) == "notes.txt"
      and AV.archive_listing(_LOCAL_ZIP)[0][0]["raw"] == _RAW_MEMBER)
_PANE_B._relist(WORK_TREE)
check("§4 the LOCAL pane lists the real file", wait_row(_PANE_B, "dots.zip"), str(rows(_PANE_B)))
check("§4 the LOCAL archive opens in place (no spool: the OS disk is already local)",
      open_archive(_PANE_B, item_named(_PANE_B, "dots.zip"))
      and _PANE_B.archive_state["spool"] == ""
      and _PANE_B.archive_state["local"] == _LOCAL_ZIP
      and _PANE_B.archive_panel.parent() is _PANE_A.splitter)
check("§4 the listing is keyed by the RAW name while its row hands the display one",
      _RAW_MEMBER in _PANE_B.archive_state["entries"]
      and _PANE_B.archive_tree.topLevelItem(0).text(0) == "notes.txt"
      and _PANE_B.archive_tree.topLevelItem(0).data(0, _PANE_B.PATH_ROLE) == _RAW_MEMBER,
      str(list(_PANE_B.archive_state["entries"])))

_ITEM = _PANE_B.archive_tree.topLevelItem(0)
_PANE_B._preview_member(_ITEM)
app.processEvents()
check("§4 a member previews through the shipped reader, under its DISPLAY name",
      _PANE_B.viewer_text.toPlainText().startswith(_MEMBER_BYTES.decode("utf-8")[:6])
      and _PANE_B._viewer_path == "notes.txt",
      f"{_PANE_B._viewer_path!r} {_PANE_B.viewer_text.toPlainText()[:12]!r}")

_READS = []
_ENGINE = _PANE_B.provider
_REAL_QUEUE_READ = _ENGINE.queue_read


def _spy_queue_read(path, *args, **kwargs):
    """Every PROVIDER read of this pane — a member name must never land here (`ARCHIVES.md` §4)."""
    _READS.append(path)
    return _REAL_QUEUE_READ(path, *args, **kwargs)


_ENGINE.queue_read = _spy_queue_read
_PANE_B.set_viewer_encoding("cp1251")
app.processEvents()
check("§4 the encoding re-read asks the ARCHIVE (a member name is no path of the server)",
      _READS == [] and _PANE_B.viewer_text.toPlainText().startswith(
          _MEMBER_BYTES.decode("cp1251")[:6]),
      f"reads={_READS} text={_PANE_B.viewer_text.toPlainText()[:12]!r}")
_MEMBER_RAW = getattr(_PANE_B, "_archive_member_raw", None)
check("§4 ...while a path that is NOT a member still goes to the provider (the routing is a gate)",
      callable(_MEMBER_RAW) and _MEMBER_RAW("stranger.txt") == ""
      and _MEMBER_RAW("notes.txt") == _RAW_MEMBER and _MEMBER_RAW(_RAW_MEMBER) == _RAW_MEMBER
      and _MEMBER_RAW("./gone.txt") == "")
_ENGINE.queue_read = _REAL_QUEUE_READ

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the reader's share: the panel that was FILLED is the panel that is sized ==")
# ════════════════════════════════════════════════════════════════════════════

_HOME, _NEIGHBOUR = _PANE_B.splitter, _PANE_A.splitter
_SIZED = []
_HOME_SET, _NEIGHBOUR_SET = _HOME.setSizes, _NEIGHBOUR.setSizes


def _watch(splitter_name, real_setter):
    def _set_sizes(sizes):
        _SIZED.append((splitter_name, list(sizes)))
        return real_setter(sizes)
    return _set_sizes


_HOME.setSizes = _watch("home", _HOME_SET)
_NEIGHBOUR.setSizes = _watch("neighbour", _NEIGHBOUR_SET)
check("§5 the scene IS the trap: the NEIGHBOUR carries the borrowed archive listing",
      _NEIGHBOUR.indexOf(_PANE_B.archive_panel) >= 0
      and _PANE_B.viewer.parent() is _HOME
      and _PANE_A._viewer_borrowed is True
      and _PANE_B.panel_in_slot() is _PANE_B.archive_panel,
      f"archive={_NEIGHBOUR.indexOf(_PANE_B.archive_panel)} "
      f"viewer={_HOME.indexOf(_PANE_B.viewer)}")
_PANE_B._preview_member(_ITEM)
app.processEvents()
_TOTAL = max(_HOME.width(), _PANE_B.VIEWER_MIN_TOTAL_PX)
_LEFT = int(_TOTAL * _PANE_B.VIEWER_TREE_SHARE)
check("§5 ...so the reader's share is laid out on ITS splitter — never on the listing's",
      bool(_SIZED) and _SIZED[-1][0] == "home"
      and _SIZED[-1][1][_HOME.indexOf(_PANE_B.viewer)] == _TOTAL - _LEFT
      and _SIZED[-1][1][0] == _LEFT,
      f"sized={_SIZED[-1] if _SIZED else '-'} home={_HOME.sizes()} "
      f"neighbour={_NEIGHBOUR.sizes()}")
_HOME.setSizes = _HOME_SET
_NEIGHBOUR.setSizes = _NEIGHBOUR_SET
_TAB.close_preview()
app.processEvents()

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the destination: the directory and its names are ONE moment ==")
# ════════════════════════════════════════════════════════════════════════════

_PANE_A._ask_conflict = _answer("overwrite")
_PANE_A._relist("/srv")
check("§6 the destination pane lists a directory that HOLDS the folder name",
      wait_row(_PANE_A, "data") and "data" in _PANE_A._names_in_current_dir(),
      str(rows(_PANE_A)))
_SNAPSHOT_HERE = _PANE_A._names_in_current_dir()
_PANE_A._relist("/empty")
check("§6 ...and the pane MOVES while the extraction is still unpacking",
      wait_for(lambda: _PANE_A.current_dir == "/empty"
               and "data" not in _PANE_A._names_in_current_dir(), timeout_ms=10000),
      f"{_PANE_A.current_dir} {_PANE_A._names_in_current_dir()}")
_ASKED.clear()
_STAGE_MOVED = make_stage("moved.txt")
plant_extract(_TAB, 9101, _record("/srv", _SNAPSHOT_HERE, "data", _STAGE_MOVED))
_TAB._on_extract_ready(9101, _STAGE_MOVED, 1, [])
check("§6 a REAL conflict is still asked about the directory the door captured (no silent merge)",
      _ASKED == [("data", "/srv")]
      and wait_for(lambda: "/srv/data/moved.txt" in _REMOTE.files, timeout_ms=15000),
      f"asked={_ASKED} files={sorted(_REMOTE.files)}")

_PANE_A._relist("/empty")
wait_for(lambda: _PANE_A.current_dir == "/empty", timeout_ms=10000)
_SNAPSHOT_THERE = _PANE_A._names_in_current_dir()
_PANE_A._relist("/srv")
check("§6 ...while the pane is back on a directory that holds a folder of that very name",
      wait_for(lambda: _PANE_A.current_dir == "/srv" and "quiet" in _PANE_A._names_in_current_dir(),
               timeout_ms=10000),
      f"{_PANE_A.current_dir} {_PANE_A._names_in_current_dir()}")
_ASKED.clear()
_STAGE_QUIET = make_stage("quiet.txt")
plant_extract(_TAB, 9102, _record("/empty", _SNAPSHOT_THERE, "quiet", _STAGE_QUIET))
_TAB._on_extract_ready(9102, _STAGE_QUIET, 1, [])
check("§6 ...and NO question is asked about a folder of a directory the extraction never writes to",
      _ASKED == [] and wait_for(lambda: "/empty/quiet/quiet.txt" in _REMOTE.files, timeout_ms=15000),
      f"asked={_ASKED} files={sorted(_REMOTE.files)}")

_PANE_B._ask_conflict = _answer("overwrite")
_DOOR_OPEN = open_archive(_PANE_B, item_named(_PANE_B, "dots.zip"))
_NAMES_AT_DOOR = _PANE_B._names_in_current_dir()
_DOOR_STARTED = _TAB.begin_extract(_PANE_B)
_DOOR_RECORD = next(iter(_TAB._extracts.values()), {})
check("§6 the DOOR captures the pair together — the directory and its names in ONE moment",
      _DOOR_OPEN and _DOOR_STARTED is True and _DOOR_RECORD.get("dest_dir") == WORK_TREE
      and _DOOR_RECORD.get("known") == _NAMES_AT_DOOR and "dots" not in _NAMES_AT_DOOR,
      f"dest_dir={_DOOR_RECORD.get('dest_dir')!r} known={_DOOR_RECORD.get('known')} "
      f"at_door={_NAMES_AT_DOOR}")
check("§6 ...and the extraction it started still delivers into the directory of that pair",
      wait_for(lambda: os.path.isfile(os.path.join(WORK_TREE, "dots", "notes.txt")), timeout_ms=20000)
      and wait_for(lambda: _TAB.extract_active() is False, timeout_ms=10000),
      f"{_TAB.extract_active()} {sorted(os.listdir(WORK_TREE))}")

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the counters, the ONE cap verdict, the ONE exception tuple, the release ==")
# ════════════════════════════════════════════════════════════════════════════

_HALF_ZIP = build_zip(os.path.join(WORK, "half.zip"),
                      [("gone.txt", b"gone\n"), ("kept.txt", b"kept\n")])


class _HalfReader(AX.MemberReader):
    """The reader of ONE member that is NOT there — a counter that counts it lies about the disk."""

    def stream(self, raw):
        return None if str(raw) == "gone.txt" else super().stream(raw)


_REAL_READER = AX.MemberReader
AX.MemberReader = _HalfReader
_HALF_RESULT, _HALF_ERROR = run_extract(_EXTRACT_WORKER, _HALF_ZIP, os.path.join(WORK_TREE, "half"))
AX.MemberReader = _REAL_READER
check("§7 only a member really WRITTEN is counted (a `None` stream is not a file on the disk)",
      _HALF_ERROR == "" and _HALF_RESULT is not None and _HALF_RESULT[1] == 1
      and os.path.isfile(os.path.join(WORK_TREE, "half", "kept.txt"))
      and not os.path.exists(os.path.join(WORK_TREE, "half", "gone.txt")),
      f"{_HALF_RESULT} {_HALF_ERROR}")

_READ_ERRORS = getattr(AV, "READ_ERRORS", None)
check("§7 the readers' exception tuple has ONE declaration — the parse family's",
      isinstance(_READ_ERRORS, tuple) and OSError in _READ_ERRORS and ValueError in _READ_ERRORS
      and not hasattr(AX, "_READ_ERRORS")
      and getattr(AX.archive, "READ_ERRORS", None) is _READ_ERRORS,
      f"view={_READ_ERRORS} extract={getattr(AX.archive, 'READ_ERRORS', None)}")
_LOCAL_SRC = open(os.path.join(ROOT, "modules", "local_fs_worker.py"), encoding="utf-8").read()
check("§7 `queue_extract()` hands the folder name down and invents no target of its own (no dead code)",
      "target = str(dest_dir" not in _LOCAL_SRC
      and "path2=str(dest_dir or \"\") or self.root" in _LOCAL_SRC)
check("§7 the extract engine still answers `(written, bytes)` per member — the ONE counter",
      "return 1, done" in _LOCAL_SRC and "return 0, 0" in _LOCAL_SRC)

check_i18n_parity(LANGS)
check_release_state(ROOT)
check("§7 the pin is the released 1 118 plus the archive's seven and the fifth read's two",
      EXPECTED_I18N_KEYS == 1118 + 4 + 3 + 2 + 8 + 9 + 18, str(EXPECTED_I18N_KEYS))
check("§7 the pin names this release's line", releases_at_least(EXPECTED_APP_VERSION, "1.13.1"),
      EXPECTED_APP_VERSION)

_WORKER.shutdown(2500)
_EXTRACT_WORKER.shutdown(2500)
_TAB.release()
for _stage in _STAGES:
    AX.drop_stage(_stage)

finish()
