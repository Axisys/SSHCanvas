# -*- coding: utf-8 -*-
"""The archive EXTRACT (v1.13.1) — the WRITE half of `ARCHIVES.md`, clause by clause.

§1 the pure plan — the folder name, the shipped gates and the caps; §2 the engine — the extract task
of `modules/local_fs_worker.py` over real archives; §3 the defect class — a link / device member, the
Zip Slip, the total / ratio / entry caps and the encrypted refusal; §4 the delivery — the stage, the
shipped batch machine and the ONE conflict question; §5 the pane — the ONE row of the archive menu
and its door; §6 the lifetime — a closed preview, a provider change, the container's teardown and the
startup sweep; §7 the family, the language files and the release. Offscreen and hermetic: the remote
half runs over `_fakes.py`, the local half over a real HOME tree (`DOCUMENTATION.md` §77)."""
import io
import os
import shutil
import sys
import tarfile
import time
import zipfile

from _common import (bootstrap, check, check_i18n_format, check_i18n_parity, check_release_state,
                     finish, load_i18n_langs, pane_func_owner, wait_for, EXPECTED_APP_VERSION,
                     EXPECTED_I18N_KEYS, releases_at_least)

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
WORK_TREE = os.path.join(WORK, "extract")
BOMB_CODE = AX.EXTRACT_ERROR_BOMB

#: The stages THIS file created — the tracking seam of the "nothing survives the answer" checks.
_STAGES = []
_create_stage = AX.create_stage


def _tracked_create_stage():
    stage = _create_stage()
    _STAGES.append(stage)
    return stage


AX.create_stage = _tracked_create_stage


def build_zip(path, members):
    """A REAL zip: `members` = [(name, bytes)]; a name ending in "/" is a directory entry."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    with open(path, "rb") as handle:
        return handle.read()


def build_tar(path, mode="w:gz"):
    """A REAL tar with a directory, an empty directory, a symlink, a hardlink, a fifo and two files."""
    with tarfile.open(path, mode) as archive:
        for name, data, mtime in (("etc/app.conf", b"listen 80\n", 1_700_000_100),
                                  ("etc/notes.txt", b"hello archive\n", 1_700_000_200)):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = mtime
            archive.addfile(info, io.BytesIO(data))
        for name, kind, target in (("etc", tarfile.DIRTYPE, ""), ("empty", tarfile.DIRTYPE, ""),
                                   ("etc/latest.conf", tarfile.SYMTYPE, "app.conf"),
                                   ("etc/again.conf", tarfile.LNKTYPE, "etc/app.conf"),
                                   ("etc/pipe", tarfile.FIFOTYPE, "")):
            info = tarfile.TarInfo(name)
            info.type = kind
            info.linkname = target
            archive.addfile(info)
    return path


def encrypt_zip(path):
    """Mark every member of a REAL zip as ENCRYPTED — the standard library writes no such file."""
    with open(path, "rb") as handle:
        raw = bytearray(handle.read())
    raw[6:8] = (int.from_bytes(raw[6:8], "little") | AV.ZIP_ENCRYPTED_FLAG).to_bytes(2, "little")
    start = raw.find(b"PK\x01\x02")
    raw[start + 8:start + 10] = (int.from_bytes(raw[start + 8:start + 10], "little")
                                 | AV.ZIP_ENCRYPTED_FLAG).to_bytes(2, "little")
    with open(path, "wb") as handle:
        handle.write(bytes(raw))
    return path


def make_remote_tab(fs, commander=True):
    """(tab, worker, log) over the fake SFTP surface, optionally in the two-pane mode."""
    worker = SftpWorker(FakeSftpClient(fs))
    log = EventLog()
    wire_worker(worker, log)
    worker.start()
    tab = SftpTab()
    tab.message.connect(lambda *_a: None)
    if commander:
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


def menu_action(menu, key):
    """The `QAction` of ONE row of a menu, found by its TRANSLATED text (the `AGENTS.md` §8.4 seam)."""
    label = i18n.t(key)
    for act in (menu.actions() if menu is not None else []):
        if act.text() == label:
            return act
    return None


def open_archive(pane, item, ms=10000):
    pane._op_view_archive(item)
    app.processEvents()
    return wait_for(lambda: pane.archive_open, timeout_ms=ms)


def tree_files(root):
    """Every FILE of an extracted tree, `/`-joined and sorted — the shape the checks read."""
    out = []
    for base, _dirs, names in os.walk(root):
        for name in names:
            out.append(os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/"))
    return sorted(out)


def run_extract(worker, archive_path, dest_dir, folder="", limits=None, ms=20000):
    """Drive ONE extraction on a bare `LocalFsWorker` and answer `(result, error_payload)`."""
    seen = {"result": None, "error": ""}

    def _ready(_task_id, tree, written, skipped):
        seen["result"] = (tree, written, skipped)

    worker.extract_ready.connect(_ready)
    worker.task_error.connect(lambda _i, _k, message: seen.update(error=message))
    worker.queue_extract(archive_path, dest_dir, folder=folder, limits=limits)
    wait_for(lambda: seen["result"] is not None or bool(seen["error"]), timeout_ms=ms)
    return seen["result"], seen["error"]


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the pure plan: the folder, the shipped gates and the caps ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the destination folder is the archive's own stem, whatever the suffix's length",
      AX.extract_folder("/srv/backup/data.car") == "data"
      and AX.extract_folder("a/b/release.tar.gz") == "release"
      and AX.extract_folder("plain.zip") == "plain"
      and AX.extract_folder("weird.tbz2") == "weird"
      and AX.extract_folder("x.TAR.XZ") == "x",
      str([AX.extract_folder(n) for n in ("data.car", "release.tar.gz", "plain.zip", "weird.tbz2")]))
check("§1 ...and a stem this system would not take answers ONE declared name, never a guess",
      AX.extract_folder(".zip") == AX.EXTRACT_FOLDER_FALLBACK
      and AX.extract_folder("") == AX.EXTRACT_FOLDER_FALLBACK
      and AX.extract_folder(None) == AX.EXTRACT_FOLDER_FALLBACK
      and AX.EXTRACT_FOLDER_FALLBACK == "archive")
check("§1 a member name is a RELATIVE path of ordinary components",
      AX.member_parts("etc/app.conf", WORK) == (["etc", "app.conf"], "")
      and AX.member_parts("./etc/app.conf", WORK)[0] == ["etc", "app.conf"]
      and AX.member_parts("one.txt", WORK) == (["one.txt"], "")
      and AX.member_parts("a//b///c.txt", WORK)[0] == ["a", "b", "c.txt"])
check("§1 the Zip Slip is refused — a `..` component never escapes the destination",
      AX.member_parts("../escape.txt", WORK)[0] == []
      and AX.member_parts("a/../../escape.txt", WORK)[0] == []
      and AX.member_parts("..", WORK)[0] == []
      and AX.member_parts("etc/../../../escape.txt", WORK)[0] == [])
check("§1 an ABSOLUTE member name is refused (POSIX, a drive letter, an empty name)",
      AX.member_parts("/etc/passwd", WORK)[0] == []
      and AX.member_parts("C:/windows/system32", WORK)[0] == []
      and AX.member_parts("c:evil.txt", WORK)[0] == []
      and AX.member_parts("", WORK)[0] == []
      and AX.member_parts(None, WORK)[0] == [])
check("§1 a name the local platform refuses is refused through the SHIPPED gate",
      AX.member_parts("bad\x00name.txt", WORK)[0] == []
      and AX.member_parts("ok.txt", WORK)[0] == ["ok.txt"]
      and bool(SW.local_name_problem("bad\x00name.txt")))
check("§1 the containment belt is the SHIPPED predicate, never a `startswith()` of our own",
      AX.member_parts("etc/app.conf", WORK)[1] == ""
      and SW.local_containment_problem(os.path.join(WORK, "etc", "app.conf"), WORK) is None
      and SW.local_containment_problem(WORK, WORK) == "outside")

check("§1 the caps are the declared constants, and a foreign value never turns one off",
      AX.extract_limits(None) == (AX.EXTRACT_MAX_TOTAL_BYTES, AX.EXTRACT_MAX_RATIO,
                                  AX.EXTRACT_MAX_ENTRIES)
      and AX.EXTRACT_MAX_TOTAL_BYTES == 1024 * 1024 * 1024
      and AX.EXTRACT_MAX_RATIO == 100
      and AX.EXTRACT_MAX_ENTRIES == SW.MAX_TREE_ENTRIES
      and AX.extract_limits({"total_bytes": 8, "ratio": 2, "entries": 3}) == (8, 2, 3)
      and AX.extract_limits({"total_bytes": 0})[0] == AX.EXTRACT_MAX_TOTAL_BYTES
      and AX.extract_limits({"ratio": -5})[1] == AX.EXTRACT_MAX_RATIO
      and AX.extract_limits({"entries": "x"})[2] == AX.EXTRACT_MAX_ENTRIES
      and AX.extract_limits("nonsense") == AX.extract_limits(None))

if os.path.isdir(WORK_TREE):
    shutil.rmtree(WORK_TREE, ignore_errors=True)
os.makedirs(WORK_TREE)
PLAIN_ZIP = os.path.join(WORK, "plan.car")
PLAIN_DATA = build_zip(PLAIN_ZIP, [("etc/app.conf", b"listen 80\n"), ("etc/", b""),
                                   ("README.txt", b"hello archive\n"),
                                   ("../escape.txt", b"nope\n"), ("/abs.txt", b"nope\n")])
_PLAN, _CODE = AX.plan_extract(PLAIN_ZIP, "zip", os.path.join(WORK, "out"))
check("§1 the plan names the members to write, the directories, and the members it refuses",
      _CODE == "" and [m["parts"] for m in _PLAN["files"]]
      == [("etc", "app.conf"), ("README.txt",)]
      and _PLAN["dirs"] == [("etc",)]
      and sorted(_PLAN["skipped"]) == ["../escape.txt", "/abs.txt"]
      and _PLAN["total"] == 24 and _PLAN["count"] == 2,
      str(_PLAN))
check("§1 a member's RAW name is what the reader asks for (the display name is the tidy one)",
      [m["raw"] for m in _PLAN["files"]] == ["etc/app.conf", "README.txt"]
      and all(m["mtime"] > 0 for m in _PLAN["files"]))
check("§1 a REFUSED plan answers its counters and NOT ONE member to write",
      AX.plan_extract(PLAIN_ZIP, "zip", os.path.join(WORK, "out"), {"total_bytes": 4})[0]["files"]
      == []
      and AX.plan_extract(PLAIN_ZIP, "zip", os.path.join(WORK, "out"), {"total_bytes": 4})[0]["total"]
      > 4)
check("§1 the plan refuses what the READER refuses (no archive, a missing one)",
      AX.plan_extract(os.path.join(WORK, "plan.txt"), "", WORK)[1] == AV.ARCHIVE_ERROR_UNREADABLE
      and AX.plan_extract(os.path.join(WORK, "gone.zip"), "", WORK)[1]
      == AV.ARCHIVE_ERROR_UNREADABLE)
check("§1 the member reader opens what the plan allowed and nothing else",
      AX.MemberReader(PLAIN_ZIP, "zip").__enter__() is not None)
with AX.MemberReader(PLAIN_ZIP, "zip") as _reader:
    _STREAM = _reader.stream("README.txt")
    check("§1 `stream()` answers a regular file member and refuses the rest with None",
          _STREAM is not None and _STREAM.read() == b"hello archive\n"
          and _reader.stream("etc/gone.txt") is None and _reader.stream("etc") is None)

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the engine: the extract task of the LOCAL provider ==")
# ════════════════════════════════════════════════════════════════════════════

_TAR = build_tar(os.path.join(WORK, "sample.tar.gz"))
_WORKER = LOCAL.LocalFsWorker(root=WORK)
_WORKER.start()
_PROGRESS = []
_WORKER.progress.connect(lambda task_id, done, total: _PROGRESS.append((task_id, done, total)))
_RESULT, _ERROR = run_extract(_WORKER, _TAR, WORK_TREE, folder="sample")
_TREE = os.path.join(WORK_TREE, "sample")
check("§2 the task writes the tree the plan allowed and answers ONE result",
      _ERROR == "" and _RESULT is not None and _RESULT[0] == _TREE and _RESULT[1] == 2,
      f"{_RESULT} | {_ERROR}")
check("§2 ...a REGULAR FILE member becomes a file with its own bytes",
      tree_files(_TREE) == ["etc/app.conf", "etc/notes.txt"]
      and open(os.path.join(_TREE, "etc", "app.conf"), "rb").read() == b"listen 80\n")
check("§2 ...a DIRECTORY member becomes a directory (an EMPTY one included)",
      os.path.isdir(os.path.join(_TREE, "etc")) and os.path.isdir(os.path.join(_TREE, "empty")))
check("§2 ...and the member's OWN mtime travels onto the file it wrote",
      int(os.path.getmtime(os.path.join(_TREE, "etc", "app.conf"))) == 1_700_000_100
      and int(os.path.getmtime(os.path.join(_TREE, "etc", "notes.txt"))) == 1_700_000_200,
      str([int(os.path.getmtime(os.path.join(_TREE, "etc", n)))
           for n in ("app.conf", "notes.txt")]))
check("§2 the write is the SHIPPED one — `.part` + `os.replace`, so no provisional file survives",
      not [name for name in os.listdir(os.path.join(_TREE, "etc")) if name.endswith(".part")])
check("§2 the progress of an extraction is the shipped `progress` signal (bytes, not files)",
      bool(_PROGRESS) and all(total == 24 for _i, _d, total in _PROGRESS)
      and _PROGRESS[-1][1] == 24,
      str(_PROGRESS))

_ZIP_PATH = os.path.join(WORK, "two.zip")
build_zip(_ZIP_PATH, [("one.txt", b"one\n"), ("deep/two.txt", b"two\n")])
_RESULT2, _ERROR2 = run_extract(_WORKER, _ZIP_PATH, WORK_TREE, folder="two")
check("§2 a zip is extracted by the same task, and a parent the archive never declared is made",
      _ERROR2 == "" and _RESULT2[1] == 2
      and tree_files(os.path.join(WORK_TREE, "two")) == ["deep/two.txt", "one.txt"])
_NAMED, _NAMED_ERROR = run_extract(_WORKER, _ZIP_PATH, WORK_TREE, folder="custom")
check("§2 the caller may name the folder (ONE name, handed down — the worker invents none)",
      _NAMED_ERROR == "" and _NAMED[0] == os.path.join(WORK_TREE, "custom")
      and tree_files(_NAMED[0]) == ["deep/two.txt", "one.txt"])

_CANCEL_WORKER = LOCAL.LocalFsWorker(root=WORK)
_CANCEL_WORKER.start()
_CANCELLED = []
_CANCEL_WORKER.task_cancelled.connect(lambda task_id, kind: _CANCELLED.append((task_id, kind)))
_CANCEL_WORKER.cancel()   # the shipped flag: everything queued answers "cancelled"
_CANCEL_WORKER.queue_extract(_ZIP_PATH, os.path.join(WORK_TREE, "never"))
check("§2 a cancelled extraction writes nothing and answers the SHIPPED cancellation",
      wait_for(lambda: bool(_CANCELLED), timeout_ms=5000)
      and not os.path.exists(os.path.join(WORK_TREE, "never")), str(_CANCELLED))
_CANCEL_WORKER.shutdown(2500)

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the defect class: the Zip Slip, the links, the bomb and the encrypted case ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 a symlink, a hardlink and a fifo member are SKIPPED and NAMED, never written",
      sorted(_RESULT[2]) == ["etc/again.conf", "etc/latest.conf", "etc/pipe"]
      and not os.path.lexists(os.path.join(_TREE, "etc", "latest.conf"))
      and not os.path.lexists(os.path.join(_TREE, "etc", "again.conf"))
      and not os.path.lexists(os.path.join(_TREE, "etc", "pipe")),
      str(_RESULT[2]))

_ESCAPE = os.path.join(WORK, "escape.zip")
build_zip(_ESCAPE, [("../../escaped.txt", b"nope\n"), ("ok.txt", b"fine\n")])
_SLIP, _SLIP_ERROR = run_extract(_WORKER, _ESCAPE, os.path.join(WORK_TREE, "slip"),
                                 folder="escape")
check("§3 the Zip Slip of a REAL archive lands nothing outside the destination",
      _SLIP_ERROR == "" and _SLIP[1] == 1 and _SLIP[2] == ["../../escaped.txt"]
      and tree_files(_SLIP[0]) == ["ok.txt"]
      and not os.path.exists(os.path.join(WORK_TREE, "escaped.txt"))
      and not os.path.exists(os.path.join(WORK_TREE, "slip", "escaped.txt"))
      and not os.path.exists(os.path.join(WORK, "escaped.txt")),
      f"{_SLIP} -> {tree_files(_SLIP[0]) if _SLIP else 'none'}")

_BOMB = os.path.join(WORK, "bomb.zip")
build_zip(_BOMB, [("big.bin", b"\x00" * 200000)])
_BOMB_PLAN, _BOMB_CODE = AX.plan_extract(_BOMB, "zip", WORK, {"total_bytes": 1024})
check("§3 the TOTAL cap refuses the bomb before a byte — counters survive, members do not",
      _BOMB_CODE == BOMB_CODE and _BOMB_PLAN["files"] == []
      and _BOMB_PLAN["total"] == 200000 and _BOMB_PLAN["count"] == 1,
      f"{_BOMB_CODE} {_BOMB_PLAN}")
_RATIO_CODE = AX.plan_extract(_BOMB, "zip", WORK, {"total_bytes": 10 ** 9, "ratio": 2})[1]
check("§3 the RATIO cap catches the archive that is small only because it is COMPRESSED",
      _RATIO_CODE == BOMB_CODE
      and AX.plan_extract(_BOMB, "zip", WORK, {"total_bytes": 10 ** 9, "ratio": 10 ** 6})[1] == ""
      and os.path.getsize(_BOMB) < 200000,
      f"{_RATIO_CODE} size={os.path.getsize(_BOMB)}")
_ENTRY_CODE = AX.plan_extract(PLAIN_ZIP, "zip", WORK, {"entries": 1})[1]
check("§3 the member count reuses the SHIPPED walk bound and its own code",
      _ENTRY_CODE == TREE_ERROR_TOO_BIG
      and AX.plan_extract(PLAIN_ZIP, "zip", WORK, {"entries": 50})[1] == "",
      str(_ENTRY_CODE))

_REFUSED_DEST = os.path.join(WORK_TREE, "bombed")
_BOMB_RESULT, _BOMB_ERROR = run_extract(_WORKER, _BOMB, _REFUSED_DEST, folder="bomb",
                                        limits={"total_bytes": 1024})
_BOMB_PAYLOAD = SW.parse_task_payload(_BOMB_ERROR) or {}
check("§3 the ENGINE refuses the same archive, and its destination tree is never created",
      _BOMB_RESULT is None and _BOMB_PAYLOAD.get("code") == BOMB_CODE
      and _BOMB_PAYLOAD.get("total") == 200000 and _BOMB_PAYLOAD.get("limit") == 1024
      and not os.path.exists(os.path.join(_REFUSED_DEST, "bomb")),
      str(_BOMB_ERROR))

_ENCRYPTED = os.path.join(WORK, "locked.zip")
build_zip(_ENCRYPTED, [("secret.txt", b"hidden\n")])
encrypt_zip(_ENCRYPTED)
check("§3 an ENCRYPTED archive is refused by the PLAN as well as by the door",
      AX.plan_extract(_ENCRYPTED, "zip", WORK)[1] == AV.ARCHIVE_ERROR_ENCRYPTED
      and AV.archive_listing(_ENCRYPTED)[1] is True)
_ENCRYPTED_RESULT, _ENCRYPTED_ERROR = run_extract(_WORKER, _ENCRYPTED,
                                                  os.path.join(WORK_TREE, "locked"),
                                                  folder="locked")
check("§3 ...and the engine writes NOTHING for it (no password is ever asked)",
      _ENCRYPTED_RESULT is None
      and (SW.parse_task_payload(_ENCRYPTED_ERROR) or {}).get("code")
      == AV.ARCHIVE_ERROR_ENCRYPTED
      and not os.path.exists(os.path.join(WORK_TREE, "locked")),
      str(_ENCRYPTED_ERROR))

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the delivery: the stage, the shipped batch machine and the ONE question ==")
# ════════════════════════════════════════════════════════════════════════════

_STAGE = AX.create_stage()
check("§4 the stage is a UNIQUE folder of the declared family",
      bool(_STAGE) and os.path.isdir(_STAGE)
      and os.path.basename(_STAGE).startswith(AX.EXTRACT_STAGE_PREFIX)
      and AX.create_stage() != _STAGE)
AX.drop_stage(_STAGE)
check("§4 ...and dropping it takes the whole tree; an empty path is a refusal, a gone one is gone",
      not os.path.exists(_STAGE) and AX.drop_stage("") is False
      and AX.drop_stage(os.path.join(WORK, "never-was")) is True)

_REMOTE = FakeSftpFS()
_REMOTE.add_dir("/srv")
_REMOTE.add_dir("/srv/data")
_REMOTE.add_file("/srv/data.car", PLAIN_DATA, mtime=1_700_000_000)
_REMOTE.add_file("/srv/locked.zip", open(_ENCRYPTED, "rb").read(), mtime=1_700_000_000)
_TAB, _REMOTE_WORKER, _LOG = make_remote_tab(_REMOTE)
_PANE_A, _PANE_B = _TAB.panes[0], _TAB.panes[1]
_PANE_A._relist("/srv")
check("§4 the two panes list the fake server (the fixture is real)",
      wait_row(_PANE_A, "data.car") and wait_row(_PANE_B, "srv"), str(rows(_PANE_A)))

_SEEN = []
_PANE_A.message.connect(_SEEN.append)
_ASKED = []
_PANE_A._ask_conflict = lambda name, target, remaining, facts="": (
    _ASKED.append((name, target, remaining)) or ("overwrite", False))
check("§4 the destination is the pane whose LISTING is on screen — the panel is in the other one",
      open_archive(_PANE_A, item_named(_PANE_A, "data.car"))
      and _TAB.preview_source() is _PANE_A and _PANE_B._viewer_borrowed is True
      and _PANE_A.current_dir == "/srv")
_STAGE_COUNT = len(_STAGES)
check("§4 the door starts ONE extraction and says which archive it is reading",
      _TAB.begin_extract(_PANE_A) is True
      and len(_STAGES) == _STAGE_COUNT + 1
      and i18n.t("sftp.viewer.reading", name="data.car") in _SEEN, str(_SEEN))
_DELIVERED_STAGE = _STAGES[-1]
check("§4 ...and the tree reaches the destination pane's directory through the SHIPPED engine",
      wait_for(lambda: "/srv/data/README.txt" in _REMOTE.files, timeout_ms=15000)
      and _REMOTE.files.get("/srv/data/etc/app.conf") == b"listen 80\n"
      and "/srv/data" in _REMOTE.dirs,
      str(sorted(_REMOTE.files)))
check("§4 NEVER `extract here`: the members land in ONE folder, never beside the archive",
      "/srv/README.txt" not in _REMOTE.files and "/srv/etc" not in _REMOTE.dirs
      and sorted(name for name in _REMOTE.files if name.startswith("/srv/"))
      == ["/srv/data.car", "/srv/data/README.txt", "/srv/data/etc/app.conf", "/srv/locked.zip"],
      str(sorted(_REMOTE.files)))
check("§4 the overwrite question was asked exactly ONCE, about the FOLDER it writes",
      len(_ASKED) == 1 and _ASKED[0][0] == "data" and _ASKED[0][1] == "/srv"
      and _ASKED[0][2] == 0, str(_ASKED))
check("§4 ONE closing report names how many files landed where",
      i18n.t("sftp.archive.extract_done", count=2, target="/srv/data") in _SEEN, str(_SEEN))
check("§4 the members the plan left out are NAMED in the SHIPPED skip sentence",
      i18n.t("sftp.local.skipped", count=2, names="../escape.txt, /abs.txt") in _SEEN, str(_SEEN))
check("§4 the staged tree is gone with the answer — a plaintext duplicate outlives nothing",
      wait_for(lambda: not os.path.exists(_DELIVERED_STAGE), timeout_ms=8000)
      and _PANE_A._staged_deliveries == {} and _TAB.extract_active() is False,
      f"{_DELIVERED_STAGE} {_PANE_A._staged_deliveries}")

_PANE_A._ask_conflict = lambda name, target, remaining, facts="": ("skip", False)
_SKIP_RESULT = _TAB.begin_extract(_PANE_A)
_SKIP_STAGE = _STAGES[-1]
check("§4 `Skip` refuses the whole extraction: nothing is queued and the stage goes at once",
      _SKIP_RESULT is True
      and wait_for(lambda: _TAB._extracts == {} and not os.path.exists(_SKIP_STAGE), timeout_ms=8000)
      and _PANE_A._staged_deliveries == {},
      f"{_SKIP_RESULT} {_SKIP_STAGE} {_TAB._extracts}")

_RENAMED = []
_PANE_A._ask_conflict = lambda name, target, remaining, facts="": ("rename", False)
_PANE_A._prompt_name = lambda title, current="": _RENAMED.append(current) or "data-2"
check("§4 `Rename` names the ONE folder, and the question is still the shipped one",
      _TAB.begin_extract(_PANE_A) is True
      and wait_for(lambda: "/srv/data-2/README.txt" in _REMOTE.files, timeout_ms=15000)
      and wait_for(lambda: _TAB._extracts == {}, timeout_ms=8000)
      and _RENAMED == ["data"], str(_RENAMED))
_PANE_A._ask_conflict = lambda name, target, remaining, facts="": (
    _ASKED.append((name, target, remaining)) or ("overwrite", False))

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the pane: the ONE row of the archive menu and its door ==")
# ════════════════════════════════════════════════════════════════════════════

_MENU = _PANE_A._build_archive_menu()
_ACT = menu_action(_MENU, "sftp.archive.extract")
check("§5 the archive listing carries ONE verb, live while an archive is open",
      _MENU is not None and _ACT is not None and _ACT.isEnabled() is True
      and len(_MENU.actions()) == 1,
      str([a.text() for a in (_MENU.actions() if _MENU else [])]))
check("§5 ...and it is the SHIPPED key of the archive surface (no second spelling of the door)",
      _ACT.text() == i18n.t("sftp.archive.extract")
      and i18n.t("sftp.archive.extract") in
      open(os.path.join(ROOT, "modules", "sftp_pane_viewer.py"), encoding="utf-8").read())
_PANE_A.close_viewer()
_STAGES_BEFORE = len(_STAGES)
check("§5 a closed listing answers `None`, and its door starts nothing",
      _PANE_A._build_archive_menu() is None
      and _PANE_A._op_extract_archive() is None
      and len(_STAGES) == _STAGES_BEFORE and _TAB._extracts == {})
check("§5 the archive panel takes no drop, and its listing is no drop target either",
      _PANE_A.archive_panel.acceptDrops() is False
      and _PANE_A.archive_tree.acceptDrops() is False)

check("§5 the door opens the listing again for the encrypted case",
      open_archive(_PANE_A, item_named(_PANE_A, "locked.zip")))
_ENCRYPTED_SEEN = []
_PANE_A.message.connect(_ENCRYPTED_SEEN.append)
_BEFORE = len(_STAGES)
_PANE_A._op_extract_archive()
app.processEvents()
check("§5 an encrypted archive is REFUSED before a byte — no stage is even claimed",
      i18n.t("sftp.archive.encrypted") in _ENCRYPTED_SEEN and len(_STAGES) == _BEFORE
      and _TAB._extracts == {}, str(_ENCRYPTED_SEEN))

_TAB.close_preview()
_LOCAL_ZIP = os.path.join(WORK_TREE, "local.zip")
build_zip(_LOCAL_ZIP, [("inside/one.txt", b"one\n"), ("two.txt", b"two\n")])
check("§5 only the SECOND pane may read the OS disk (the LOCAL_PANE.md §4 rule)",
      _TAB.can_use_local(_PANE_A) is False and _TAB.can_use_local(_PANE_B) is True
      and _TAB.set_pane_source(_PANE_B, SOURCE_LOCAL) is True and _PANE_B.source == SOURCE_LOCAL)
_PANE_B._ask_conflict = lambda name, target, remaining, facts="": (
    _ASKED.append((name, target, remaining)) or ("overwrite", False))
_PANE_B._relist(WORK_TREE)
check("§5 ...and lists the real file", wait_row(_PANE_B, "local.zip"), str(rows(_PANE_B)))
check("§5 a LOCAL archive opens in place (no spool: the OS disk is already local)",
      open_archive(_PANE_B, item_named(_PANE_B, "local.zip"))
      and _PANE_B.archive_state["spool"] == ""
      and _PANE_B.archive_state["local"] == _LOCAL_ZIP
      and _PANE_B.archive_panel.parent() is _PANE_A.splitter)
check("§5 the extract of a LOCAL archive writes into THAT pane's directory, through the local engine",
      _TAB.begin_extract(_PANE_B) is True
      and wait_for(lambda: os.path.isfile(os.path.join(WORK_TREE, "local", "two.txt")),
                   timeout_ms=15000)
      and wait_for(lambda: _TAB.extract_active() is False, timeout_ms=8000)
      and tree_files(os.path.join(WORK_TREE, "local")) == ["inside/one.txt", "two.txt"],
      str(tree_files(os.path.join(WORK_TREE, "local"))
          if os.path.isdir(os.path.join(WORK_TREE, "local")) else "missing"))

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the lifetime: the deliveries, a provider change, the teardown, the sweep ==")
# ════════════════════════════════════════════════════════════════════════════

check("§6 the delivery of a staged tree is the SHIPPED engine of the destination pane",
      _PANE_A.ship_staged_tree(os.path.join(WORK_TREE, "local"), "/srv", "local", set()) is True
      and wait_for(lambda: "/srv/local/two.txt" in _REMOTE.files, timeout_ms=15000),
      str(sorted(_REMOTE.files)))
_ELEVATED_SEEN = []
_PANE_A.message.connect(_ELEVATED_SEEN.append)
_PANE_A._elevated_provider = object()   # the declared state of `elevated`
_STAGE_ELEVATED = AX.create_stage()
check("§6 an ELEVATED destination refuses at the shipped door of the batch machine",
      _PANE_A.ship_staged_tree(_STAGE_ELEVATED, "/srv", "nope", set()) is False
      and i18n.t("sftp.elevated.read_only") in _ELEVATED_SEEN
      and _PANE_A._staged_deliveries == {}, str(_ELEVATED_SEEN))
_PANE_A._elevated_provider = None
AX.drop_stage(_STAGE_ELEVATED)

_STAGED = AX.create_stage()
_PANE_B._staged_deliveries[987654] = _STAGED
check("§6 a staged tree is dropped with the answer of ITS task, and only that one",
      _PANE_B._drop_staged(424242) is False and _PANE_B._drop_staged(987654) is True
      and not os.path.exists(_STAGED) and _PANE_B._staged_deliveries == {})
_STAGED_TWO = AX.create_stage()
_STAGED_THREE = AX.create_stage()
_PANE_B._staged_deliveries[1] = _STAGED_TWO
_PANE_B._staged_deliveries[2] = _STAGED_THREE
check("§6 dropping ALL of them takes every staged tree of the pane",
      _PANE_B._drop_staged_all() == 2 and not os.path.exists(_STAGED_TWO)
      and not os.path.exists(_STAGED_THREE) and _PANE_B._staged_deliveries == {})

_STAGED_FOUR = AX.create_stage()
_PANE_B._staged_deliveries[777] = _STAGED_FOUR
check("§6 a PROVIDER CHANGE drops what the provider it leaves was still delivering",
      _TAB.set_worker(None) is None and _PANE_B._staged_deliveries == {}
      and not os.path.exists(_STAGED_FOUR))
_TAB.set_worker(_REMOTE_WORKER)
check("§6 ...and the transport comes back on the pane that reads it",
      _TAB.worker is _REMOTE_WORKER and _PANE_A.provider is _REMOTE_WORKER
      and _PANE_B.provider is _PANE_B._local_provider,
      f"{_TAB.worker} {_PANE_A.provider}")
_PANE_A._relist("/srv")
check("§6 ...and the pane lists through it again", wait_row(_PANE_A, "data.car"), str(rows(_PANE_A)))
_PANE_B._relist(WORK_TREE)
check("§6 ...while the LOCAL pane keeps its own engine and its directory",
      wait_row(_PANE_B, "local.zip"), str(rows(_PANE_B)))

_SPOOL = os.path.join(WORK, "held.car")   # a plain file: the spool FAMILY is the sibling tests' temp
with open(_SPOOL, "wb") as _handle:
    _handle.write(b"a plaintext copy")
_LOCAL_COPY = os.path.join(WORK_TREE, "local.zip")
_TAB._extracts[555] = {"pane": _PANE_B, "local": _LOCAL_COPY, "spool": _SPOOL,
                       "stage": "", "closed": False, "dest_pane": _PANE_B,
                       "dest_dir": WORK_TREE, "name": "held"}
check("§6 a preview closed while an extraction is running hands its copy to the container",
      open_archive(_PANE_B, item_named(_PANE_B, "local.zip"))
      and _TAB.take_archive_copy(_LOCAL_COPY) is True
      and _TAB._extracts[555]["closed"] is True
      and _TAB.take_archive_copy("") is False
      and _TAB.take_archive_copy(os.path.join(WORK, "stranger.zip")) is False)
_TAB.close_preview()
check("§6 ...the closed view does NOT delete the copy that extraction is still reading",
      os.path.exists(_SPOOL) and _PANE_B.archive_open is False)
_TAB._release_extracts()
check("§6 ...and the container drops it with the extraction, so nothing outlives the pair",
      not os.path.exists(_SPOOL) and _TAB._extracts == {})

_AGED = AX.create_stage()
_OLD = time.time() - (AX.EXTRACT_STAGE_MAX_AGE_SEC + 60)
os.utime(_AGED, (_OLD, _OLD))
_YOUNG = AX.create_stage()
check("§6 the startup sweep takes a CRASHED run's stage and keeps a live instance's young one",
      AX.sweep_stages() >= 1 and not os.path.exists(_AGED) and os.path.exists(_YOUNG)
      and AX.sweep_stages(os.path.join(WORK, "no-such-folder")) == 0,
      f"{_AGED} {_YOUNG}")
AX.drop_stage(_YOUNG)

_EXTRACT_TAB = SftpTab()
_EXTRACT_TAB.message.connect(lambda *_a: None)
_EXTRACT_TAB.set_commander(True)
_EXTRACT_NOTICE = _EXTRACT_TAB.panes[0]
_EXTRACT_TAB.extract_provider()
_STAGE_FIVE = AX.create_stage()
_EXTRACT_TAB._extracts[1] = {"pane": _EXTRACT_NOTICE, "local": "", "spool": "", "stage": _STAGE_FIVE,
                            "closed": False, "dest_pane": _EXTRACT_NOTICE, "dest_dir": WORK,
                            "name": "x"}
_PROVIDER = _EXTRACT_TAB._extract_provider
_EXTRACT_TAB.release()
check("§6 the container's OWN teardown stops the extract engine and drops what it holds",
      _EXTRACT_TAB._extracts == {} and not os.path.exists(_STAGE_FIVE)
      and _EXTRACT_TAB._extract_provider is None and _PROVIDER.isRunning() is False)

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the family, the language files and the release ==")
# ════════════════════════════════════════════════════════════════════════════

check("§7 the extract cluster lives in the SHIPPED pane and tab family (ONE owner per door)",
      pane_func_owner("_op_extract_archive", ROOT) == "modules/sftp_pane_viewer.py"
      and pane_func_owner("_build_archive_menu", ROOT) == "modules/sftp_pane_viewer.py"
      and pane_func_owner("ship_staged_tree", ROOT) == "modules/sftp_pane_transfer.py"
      and hasattr(STAB._SftpPane, "_op_extract_archive")
      and hasattr(STAB.SftpTab, "begin_extract")
      and not hasattr(STAB.SftpTab, "_op_extract_archive"))
check("§7 the pure half carries no Qt and no provider (the module is importable alone)",
      all(needle not in open(os.path.join(ROOT, "modules", "archive_extract.py"),
                             encoding="utf-8").read()
          for needle in ("PySide6", "paramiko")))
check("§7 the engine is the LOCAL provider's — ONE task kind, declared by the engine it runs",
      AX.KIND_EXTRACT == "extract"
      and hasattr(LOCAL.LocalFsWorker, "queue_extract")
      and hasattr(LOCAL.LocalFsWorker, "_do_extract")
      and "extract_ready" in LOCAL.LocalFsWorker.__dict__)
check("§7 the product carries no THIRD-PARTY extractor (the standard library is the engine)",
      all(needle not in open(os.path.join(ROOT, "modules", "archive_extract.py"),
                             encoding="utf-8").read()
          for needle in ("subprocess", "unzip", "shutil.unpack_archive")))
check("§7 the READ half and the WRITE half share ONE parse of the family",
      AV.archive_members(PLAIN_ZIP, "zip")[0][1]["name"] == "etc/"
      and [e["name"] for e in AV.archive_listing(PLAIN_ZIP)[0]]
      == ["etc/app.conf", "README.txt", "../escape.txt", "/abs.txt"]
      and [e["kind"] for e in AV.archive_members(PLAIN_ZIP, "zip")[0]]
      == [AV.MEMBER_FILE, AV.MEMBER_DIR, AV.MEMBER_FILE, AV.MEMBER_FILE, AV.MEMBER_FILE],
      str([e["kind"] for e in AV.archive_members(PLAIN_ZIP, "zip")[0]]))

for _key in ("sftp.archive.extract", "sftp.archive.extract_done", "sftp.archive.extract_bomb"):
    check(f"§7 {_key} is present and non-empty in every language",
          all(str(data.get(_key) or "").strip() for data in LANGS.values()),
          str({code: bool(data.get(_key)) for code, data in LANGS.items()}))
check_i18n_parity(LANGS)
check_i18n_format(LANGS)

check_release_state(ROOT)
check("§7 the pin names this release's line", releases_at_least(EXPECTED_APP_VERSION, "1.13.1"),
      EXPECTED_APP_VERSION)
check("§7 the extract's three keys are the whole of what this release adds to the pin",
      EXPECTED_I18N_KEYS == 1118 + 4 + 3, str(EXPECTED_I18N_KEYS))
check("§7 the project schema did NOT move (an extraction is not project state)",
      'VERSION_FORMAT = "0.9"' in open(os.path.join(ROOT, "version.py"), encoding="utf-8").read())

_WORKER.shutdown(2500)
_REMOTE_WORKER.shutdown(2500)
_TAB.release()

finish()
