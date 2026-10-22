# -*- coding: utf-8 -*-
"""The defects a fourth read of the shipped `v1.13.1.1` confirmed, each one REPRODUCED (v1.13.1.2).
§1 the entry cap — EVERY member counts and the walk stops at it; §2 the decompressors — `zlib` / `lzma`
join the ONE exception tuple; §3 the report — the success belongs to the delivery's ANSWER; §4 the dead
destination — a destroyed pane costs no traceback and no stage; §5 the cap on the REAL copy — a lying
listing size cannot open an archive; §6 the handed-over copy — the LAST extraction drops the spool;
§7 the skip report — a refused directory and an unreadable member are NAMED; §8 the release.
Rule — `AGENTS.md` §4.3.6, §4.4.3, §12.5; mechanism — `DOCUMENTATION.md` §76, §77.
"""
import lzma
import os
import shutil
import sys
import tarfile
import time
import zipfile
import zlib

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, clear_cfg, finish, load_i18n_langs, pane_func_owner,
                     releases_at_least, wait_for, write_cfg)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import i18n  # noqa: E402
import modules.archive_extract as AX  # noqa: E402
import modules.archive_view as AV  # noqa: E402
import modules.local_fs_worker as LOCAL  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402
from modules.sftp_tab import SOURCE_LOCAL, SftpTab  # noqa: E402
from modules.sftp_worker import SftpWorker, TREE_ERROR_TOO_BIG  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)
WORK_TREE = os.path.join(WORK, "patch")
_STAGES = []


def build_zip(path, members):
    """A REAL zip: `members` = [(name, bytes)]."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    return path


def build_dir_zip(path, count):
    """A REAL zip of `count` DIRECTORY entries — one member, no bytes, no file."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for index in range(count):
            archive.writestr(zipfile.ZipInfo("d%05d/" % index), b"")
    return path


def build_link_tar(path, count):
    """A REAL tar of `count` SYMLINK members — a link's body is its target path, never content."""
    with tarfile.open(path, "w") as archive:
        for index in range(count):
            info = tarfile.TarInfo("l%05d" % index)
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            archive.addfile(info)
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


def run_extract(worker, archive_path, dest_dir, limits=None, ms=20000):
    """Drive ONE extraction on a bare `LocalFsWorker` and answer `(result, error_payload)`."""
    seen = {"result": None, "error": ""}
    worker.extract_ready.connect(
        lambda _i, tree, written, skipped: seen.update(result=(tree, written, skipped)))
    worker.task_error.connect(lambda _i, _k, message: seen.update(error=message))
    worker.queue_extract(archive_path, dest_dir, folder="", limits=limits)
    wait_for(lambda: seen["result"] is not None or bool(seen["error"]), timeout_ms=ms)
    return seen["result"], seen["error"]


def record(dest_pane, pane, dest_dir, known, name, stage, local="", spool=""):
    """The record `begin_extract()` writes — ONE extraction in flight."""
    return {"pane": pane, "dest_pane": dest_pane, "dest_dir": dest_dir, "known": known,
            "name": name, "stage": stage, "local": local, "spool": spool, "closed": False}


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the entry cap: EVERY member counts, and the walk stops at the cap ==")
# ════════════════════════════════════════════════════════════════════════════

if os.path.isdir(WORK_TREE):
    shutil.rmtree(WORK_TREE, ignore_errors=True)
os.makedirs(WORK_TREE)

_DIRS_ZIP = build_dir_zip(os.path.join(WORK, "dirs.zip"), 6000)
_PLAN_DIRS, _CODE_DIRS = AX.plan_extract(_DIRS_ZIP, "", WORK_TREE)
check("§1 a zip of 6 000 EMPTY DIRECTORIES is over the entry cap — a directory member counts",
      _CODE_DIRS == TREE_ERROR_TOO_BIG and _PLAN_DIRS.get("dirs") == []
      and _PLAN_DIRS.get("count") == 0,
      f"code={_CODE_DIRS!r} dirs={len(_PLAN_DIRS.get('dirs') or [])} "
      f"entries={_PLAN_DIRS.get('entries')}")

_LINKS_TAR = build_link_tar(os.path.join(WORK, "links.tar"), 6000)
_PLAN_LINKS, _CODE_LINKS = AX.plan_extract(_LINKS_TAR, "", WORK_TREE)
check("§1 ...and a tar of 6 000 SYMLINKS is over it too, even though links are never written",
      _CODE_LINKS == TREE_ERROR_TOO_BIG and _PLAN_LINKS.get("files") == [],
      f"code={_CODE_LINKS!r} skipped={len(_PLAN_LINKS.get('skipped') or [])} "
      f"entries={_PLAN_LINKS.get('entries')}")

_MANY_ZIP = build_zip(os.path.join(WORK, "many.zip"),
                      [("f%05d.txt" % index, b"x\n") for index in range(5001)])
_PLAN_MANY, _CODE_MANY = AX.plan_extract(_MANY_ZIP, "", WORK_TREE)
check("§1 the regular-file case keeps its answer (the shipped 5 000 sentence, no regression)",
      _CODE_MANY == TREE_ERROR_TOO_BIG and _PLAN_MANY.get("count") == 5001
      and _PLAN_MANY.get("files") == [],
      f"code={_CODE_MANY!r} count={_PLAN_MANY.get('count')} files={len(_PLAN_MANY.get('files') or [])}")

_SEVEN_ZIP = build_zip(os.path.join(WORK, "seven.zip"),
                       [("f%d.txt" % index, b"x\n") for index in range(7)])
_PLAN_SEVEN, _CODE_SEVEN = AX.plan_extract(_SEVEN_ZIP, "", WORK_TREE, {"entries": 7})
_EIGHT_ZIP = build_zip(os.path.join(WORK, "eight.zip"),
                       [("f%d.txt" % index, b"x\n") for index in range(8)])
_PLAN_EIGHT, _CODE_EIGHT = AX.plan_extract(_EIGHT_ZIP, "", WORK_TREE, {"entries": 7})
check("§1 the cap is a BOUND, not an estimate: exactly `entries` members pass, one more does not",
      _CODE_SEVEN == "" and _CODE_EIGHT == TREE_ERROR_TOO_BIG
      and _PLAN_SEVEN.get("entries") == 7 and _PLAN_EIGHT.get("entries") == 8,
      f"7 -> {_CODE_SEVEN!r} ({_PLAN_SEVEN.get('entries')}), "
      f"8 -> {_CODE_EIGHT!r} ({_PLAN_EIGHT.get('entries')})")

_DEEP_ZIP = build_dir_zip(os.path.join(WORK, "deep.zip"), 20000)
_STARTED = time.monotonic()
_PLAN_DEEP, _CODE_DEEP = AX.plan_extract(_DEEP_ZIP, "", WORK_TREE)
_ELAPSED = time.monotonic() - _STARTED
check("§1 the walk STOPS one member past the cap (20 000 members are never walked to the end)",
      _CODE_DEEP == TREE_ERROR_TOO_BIG and _PLAN_DEEP.get("entries") == AX.EXTRACT_MAX_ENTRIES + 1
      and _ELAPSED < 20.0,
      f"code={_CODE_DEEP!r} entries={_PLAN_DEEP.get('entries')} time={_ELAPSED:.2f}s")

try:  # the reproduction of the missing bound: the walk takes no limit at all
    _MEMBERS, _ENC, _MCODE = AV.archive_members(_DIRS_ZIP, "zip", 10)
except TypeError as _exc:
    _MEMBERS, _ENC, _MCODE = None, None, f"TypeError: {_exc}"
check("§1 ...because the CAP is the parse's own: `archive_members(limit=)` answers at most limit + 1",
      _MCODE == "" and isinstance(_MEMBERS, list) and len(_MEMBERS) == 11 and _ENC is False,
      f"code={_MCODE!r} members={len(_MEMBERS) if isinstance(_MEMBERS, list) else _MEMBERS}")

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the decompressors: `zlib` and `lzma` join the ONE exception tuple ==")
# ════════════════════════════════════════════════════════════════════════════

_GOOD_ZIP = build_zip(os.path.join(WORK, "good.zip"), [("payload.txt", b"A" * 200000)])
_RAW = bytearray(open(_GOOD_ZIP, "rb").read())
_INFO = zipfile.ZipFile(_GOOD_ZIP).infolist()[0]
_BODY = _INFO.header_offset + 30 + len(_INFO.filename.encode("utf-8")) + len(_INFO.extra)
for _index in range(_BODY + 2, min(_BODY + 40, len(_RAW) - 30)):
    _RAW[_index] = 0xFF
_CORRUPT_ZIP = os.path.join(WORK, "corrupt.zip")
with open(_CORRUPT_ZIP, "wb") as _handle:
    _handle.write(_RAW)

_RAISED = None
try:
    _DATA, _RCODE = AV.read_member(_CORRUPT_ZIP, "zip", "payload.txt", 1000)
except Exception as _exc:  # noqa: BLE001 — the exception IS the subject here
    _RAISED = _exc
    _DATA, _RCODE = b"", ""
check("§2 a member the DEFLATE stream refuses answers `unreadable` — never a traceback in a GUI slot",
      _RAISED is None and _RCODE == AV.ARCHIVE_ERROR_UNREADABLE and _DATA == b"",
      f"{type(_RAISED).__name__ if _RAISED else 'no exception'}: {_RAISED} -> {_RCODE!r}")

check("§2 ...because the decompressors' own refusals are IN the family's ONE tuple",
      zlib.error in AV.READ_ERRORS and lzma.LZMAError in AV.READ_ERRORS
      and AV.READ_ERRORS is AX.archive.READ_ERRORS,
      str(AV.READ_ERRORS))

_READ_RAISED = None
try:
    with AX.MemberReader(_CORRUPT_ZIP, "zip") as _READER:
        _STREAM = _READER.stream("payload.txt")
        while _STREAM.read(65536):
            pass
except Exception as _exc:  # noqa: BLE001 — the reader answers None / raises; the TYPE is the fact
    _READ_RAISED = _exc
check("§2 the extract's reader answers `None` or a refusal the SAME tuple names (one declaration)",
      _READ_RAISED is not None and isinstance(_READ_RAISED, AV.READ_ERRORS),
      f"{type(_READ_RAISED).__name__ if _READ_RAISED else 'no exception'}: {_READ_RAISED}")

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the report: the success belongs to the delivery's ANSWER ==")
# ════════════════════════════════════════════════════════════════════════════

_REMOTE = FakeSftpFS()
for _dir in ("/srv", "/srv/denied"):
    _REMOTE.add_dir(_dir)
_TAB, _WORKER, _LOG = make_remote_tab(_REMOTE)
_PANE_A, _PANE_B = _TAB.panes[0], _TAB.panes[1]
_PANE_A._relist("/srv")
check("§3 the remote pane lists the fake server (the fixture is real)",
      wait_for(lambda: _PANE_A.current_dir == "/srv" and "denied" in rows(_PANE_A),
               timeout_ms=10000), f"{_PANE_A.current_dir} {rows(_PANE_A)}")
_SEEN = []
_PANE_A.message.connect(_SEEN.append)
_SENTENCE_QUEUED = i18n.t("sftp.archive.extract_done", count=2, target="/srv/quiet")

_STAGE_QUIET = make_stage()
plant_extract(_TAB, 4242, record(_PANE_A, _PANE_A, "/srv", set(), "quiet", _STAGE_QUIET))
_TAB._on_extract_ready(4242, _STAGE_QUIET, 2, [])
check("§3 a delivery that has NOT answered reports nothing — a queue is not a landing",
      _SENTENCE_QUEUED not in _SEEN and os.path.exists(_STAGE_QUIET), str(_SEEN))
check("§3 ...and the ANSWER is what earns the sentence, with the extraction's own counters",
      wait_for(lambda: _SENTENCE_QUEUED in _SEEN and "/srv/quiet/marker.txt" in _REMOTE.files,
               timeout_ms=15000)
      and not os.path.exists(_STAGE_QUIET),
      f"seen={_SEEN} files={sorted(_REMOTE.files)}")

_STAGE_LANDED = make_stage()
plant_extract(_TAB, 4243, record(_PANE_A, _PANE_A, "/srv", set(), "data", _STAGE_LANDED))
_SEEN.clear()
_TAB._on_extract_ready(4243, _STAGE_LANDED, 1, [])
_SENTENCE_LANDED = i18n.t("sftp.archive.extract_done", count=1, target="/srv/data")
check("§3 the SHIPPED engine's answer is the report — the tree really reached the destination",
      wait_for(lambda: _SENTENCE_LANDED in _SEEN and "/srv/data/marker.txt" in _REMOTE.files,
               timeout_ms=15000),
      f"seen={_SEEN} files={sorted(_REMOTE.files)}")

_REMOTE.deny_dirs.add("/srv/denied")
_STAGE_DENIED = make_stage()
plant_extract(_TAB, 4244, record(_PANE_A, _PANE_A, "/srv/denied", set(), "data", _STAGE_DENIED))
_SEEN.clear()
_TAB._on_extract_ready(4244, _STAGE_DENIED, 1, [])
_FAILED = wait_for(lambda: _TAB.extract_active() is False
                   and not os.path.exists(_STAGE_DENIED), timeout_ms=15000)
check("§3 a REFUSED delivery reports no success at all — the failure is the only truth",
      _FAILED and _SENTENCE_LANDED not in _SEEN
      and "/srv/denied/data/marker.txt" not in _REMOTE.files,
      f"seen={_SEEN} files={sorted(_REMOTE.files)}")
_REMOTE.deny_dirs.clear()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the dead destination: no traceback and no stage left behind ==")
# ════════════════════════════════════════════════════════════════════════════

_STAGE_DEAD = make_stage()
plant_extract(_TAB, 4300, record(_PANE_B, _PANE_B, "/srv", set(), "gone", _STAGE_DEAD))
_TAB.set_commander(False)   # the destination pane — the one the extraction named — is DESTROYED
app.processEvents()
_RAISED = None
try:
    _TAB._on_extract_ready(4300, _STAGE_DEAD, 1, [])
except Exception as _exc:  # noqa: BLE001 — the traceback IS the subject here
    _RAISED = _exc
check("§4 a destination pane that is GONE costs neither a traceback nor a temp tree",
      _RAISED is None and not os.path.exists(_STAGE_DEAD) and _TAB._extracts == {},
      f"{type(_RAISED).__name__ if _RAISED else 'no exception'}: {_RAISED} "
      f"stage={os.path.exists(_STAGE_DEAD)} extracts={_TAB._extracts}")

_TAB.set_commander(True)
_PANE_B = _TAB.panes[1]
_STAGE_RACE = make_stage()


def _boom(*_args, **_kwargs):
    """The pane dying BETWEEN the liveness check and the delivery — the reproduced race."""
    raise RuntimeError("Internal C++ object already deleted")


_REAL_SHIP_B = _PANE_B.ship_staged_tree
_PANE_B.ship_staged_tree = _boom
plant_extract(_TAB, 4301, record(_PANE_B, _PANE_A, "/srv", set(), "raced", _STAGE_RACE))
_RAISED = None
try:
    _TAB._on_extract_ready(4301, _STAGE_RACE, 1, [])
except Exception as _exc:  # noqa: BLE001 — the traceback IS the subject here
    _RAISED = _exc
_PANE_B.ship_staged_tree = _REAL_SHIP_B
check("§4 ...and a pane that dies MID-DELIVERY is a dropped tree, never a crash in the slot",
      _RAISED is None and not os.path.exists(_STAGE_RACE) and _TAB._extracts == {},
      f"{type(_RAISED).__name__ if _RAISED else 'no exception'}: {_RAISED}")

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the cap on the REAL copy: a lying listing size cannot open an archive ==")
# ════════════════════════════════════════════════════════════════════════════

check("§5 the second pane takes the OS disk as its source (the LOCAL_PANE.md §4 rule)",
      _TAB.can_use_local(_PANE_A) is False and _TAB.can_use_local(_PANE_B) is True
      and _TAB.set_pane_source(_PANE_B, SOURCE_LOCAL) is True and _PANE_B.source == SOURCE_LOCAL)
_LOCAL_BIG = os.path.join(WORK_TREE, "big.zip")
build_zip(_LOCAL_BIG, [("payload.txt", os.urandom(4096))])   # incompressible: the FILE is the cost
check("§5 the fixture IS the trap: the copy is far larger than the cap the door was told",
      os.path.getsize(_LOCAL_BIG) > 1024,
      str(os.path.getsize(_LOCAL_BIG)))
_PANE_B._relist(WORK_TREE)
check("§5 the local pane lists the real archive", wait_row(_PANE_B, "big.zip"), str(rows(_PANE_B)))
_ITEM_BIG = item_named(_PANE_B, "big.zip")
_ITEM_BIG.setData(0, _PANE_B.SIZE_ROLE, 10)   # the listing LIES: the file is 4 096 bytes
write_cfg({AV.ARCHIVE_MAX_BYTES_CONFIG: 512})
_SEEN_B = []
_PANE_B.message.connect(_SEEN_B.append)
_PANE_B._op_view_archive(_ITEM_BIG)
app.processEvents()
_CAP_SENTENCE = i18n.t("sftp.archive.cap", size=STAB.format_size(os.path.getsize(_LOCAL_BIG)),
                       limit=STAB.format_size(512))
check("§5 the cap is asked AGAIN on the copy itself — the listing's word is not evidence",
      _PANE_B.archive_open is False and _CAP_SENTENCE in _SEEN_B,
      f"open={_PANE_B.archive_open} seen={_SEEN_B} real={os.path.getsize(_LOCAL_BIG)}")
clear_cfg()
if _PANE_B.archive_open:
    _TAB.close_preview()
_PANE_B._relist(WORK_TREE)

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the handed-over copy: the LAST extraction drops the spool ==")
# ════════════════════════════════════════════════════════════════════════════

_COPY = os.path.join(WORK_TREE, "copy.car")
with open(_COPY, "wb") as _handle:
    _handle.write(b"PK\x03\x04 not really")
_SPOOL = AV.spool_archive("held.car")
with open(_SPOOL, "wb") as _handle:
    _handle.write(b"a plaintext copy")
plant_extract(_TAB, 4401, record(_PANE_A, _PANE_A, "/srv", set(), "held", "", _COPY, _SPOOL))
plant_extract(_TAB, 4402, record(_PANE_A, _PANE_A, "/srv", set(), "held", "", _COPY, _SPOOL))
check("§6 TWO extractions of ONE archive both take the copy when the view closes",
      _TAB.take_archive_copy(_COPY) is True
      and _TAB._extracts[4401]["closed"] is True and _TAB._extracts[4402]["closed"] is True,
      str({key: value["closed"] for key, value in _TAB._extracts.items()}))
_TAB._on_extract_cancelled(4401, "extract")
check("§6 ...and the FIRST of them to answer keeps the spool the second one is still reading",
      os.path.exists(_SPOOL) and 4402 in _TAB._extracts,
      f"spool={os.path.exists(_SPOOL)} extracts={sorted(_TAB._extracts)}")
_TAB._on_extract_cancelled(4402, "extract")
check("§6 ...while the LAST one takes it with it — nothing outlives its last reader",
      not os.path.exists(_SPOOL) and _TAB._extracts == {},
      f"spool={os.path.exists(_SPOOL)} extracts={sorted(_TAB._extracts)}")

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the skip report: a refused directory and an unreadable member are NAMED ==")
# ════════════════════════════════════════════════════════════════════════════

_REFUSED_ZIP = build_zip(os.path.join(WORK, "refused.zip"),
                         [("../", b""), ("ok.txt", b"ok\n")])
_PLAN_REFUSED, _CODE_REFUSED = AX.plan_extract(_REFUSED_ZIP, "", WORK_TREE)
check("§7 a DIRECTORY member the gates refuse is named in the plan's skip list, never dropped",
      _CODE_REFUSED == "" and _PLAN_REFUSED.get("skipped") == ["../"]
      and _PLAN_REFUSED.get("dirs") == [] and _PLAN_REFUSED.get("count") == 1,
      f"skipped={_PLAN_REFUSED.get('skipped')} dirs={_PLAN_REFUSED.get('dirs')}")

_EXTRACT_WORKER = LOCAL.LocalFsWorker(root=WORK)
_EXTRACT_WORKER.start()
_HALF_ZIP = build_zip(os.path.join(WORK, "half.zip"),
                      [("gone.txt", b"gone\n"), ("kept.txt", b"kept\n")])


class _HalfReader(AX.MemberReader):
    """The reader of ONE member that is NOT there — a report that omits it is incomplete."""

    def stream(self, raw):
        return None if str(raw) == "gone.txt" else super().stream(raw)


_REAL_READER = AX.MemberReader
AX.MemberReader = _HalfReader
_HALF_RESULT, _HALF_ERROR = run_extract(_EXTRACT_WORKER, _HALF_ZIP, os.path.join(WORK_TREE, "half"))
AX.MemberReader = _REAL_READER
check("§7 a member the READER cannot open is NAMED in the skip report (the count stays honest)",
      _HALF_ERROR == "" and _HALF_RESULT is not None and _HALF_RESULT[1] == 1
      and _HALF_RESULT[2] == ["gone.txt"]
      and os.path.isfile(os.path.join(WORK_TREE, "half", "kept.txt")),
      f"{_HALF_RESULT} {_HALF_ERROR}")

# ════════════════════════════════════════════════════════════════════════════
print("== §8 the release: the patches, the one owner and the pin ==")
# ════════════════════════════════════════════════════════════════════════════

check("§8 the report has ONE owner in the pane family (the transfer mixin, the shipped slot)",
      pane_func_owner("_report_staged", ROOT) == "modules/sftp_pane_transfer.py"
      and hasattr(STAB._SftpPane, "_report_staged")
      and not hasattr(STAB.SftpTab, "_report_staged"))
check("§8 the size reader has ONE home — the READ half's module, and the extract half imports it",
      callable(getattr(AV, "local_size", None)) and not hasattr(AX, "local_size")
      and AV.local_size(__file__) > 0 and AV.local_size(os.path.join(WORK, "gone")) == 0)
_FACADE = open(os.path.join(ROOT, "modules", "sftp_tab.py"), encoding="utf-8").read()
check("§8 the facade keeps its declared budget (`< 3 000` lines) with the patch in place",
      len(_FACADE.splitlines()) < 3000, str(len(_FACADE.splitlines())))

for _key in ("sftp.archive.extract_done", "sftp.archive.extract_bomb", "sftp.cmd.tree_too_big",
             "sftp.local.skipped", "sftp.archive.cap"):
    check(f"§8 {_key} is present and non-empty in every language",
          all(str(data.get(_key) or "").strip() for data in LANGS.values()),
          str({code: bool(data.get(_key)) for code, data in LANGS.items()}))
check_i18n_parity(LANGS)
check_release_state(ROOT)
check("§8 the pin of this release's line plus the fifth read's TWO keys — no key of the patch itself",
      EXPECTED_I18N_KEYS == 1125 + 2 + 8 + 9 + 18 + 4 + 13 + 1 + 1 + 12, str(EXPECTED_I18N_KEYS))
check("§8 the pin names this release's line", releases_at_least(EXPECTED_APP_VERSION, "1.13.1"),
      EXPECTED_APP_VERSION)

_WORKER.shutdown(2500)
_EXTRACT_WORKER.shutdown(2500)
_TAB.release()
for _stage in _STAGES:
    AX.drop_stage(_stage)

finish()
