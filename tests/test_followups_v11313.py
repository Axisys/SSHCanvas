# -*- coding: utf-8 -*-
"""The five decisions the `v1.13.1.2` round carried out of the ledger, each answered (v1.13.1.3).
§1 the READ listing has a ROW bound of its own — at most `ARCHIVE_LIST_MAX` rows and ONE sentence;
§2 the folder's `Overwrite` is a MERGE and the question carries that line; §3 the spool name takes
THIS platform's spelling (`:` is an NTFS stream, `?` a `mkstemp` refusal, 300 characters the same);
§4 the extract writes ONE log line with its counters; §5 the SFTP-open slots answer to the handshake
that EMITTED, and a stale one is closed instead of bound; §6 the release.
Rule — `AGENTS.md` §4.3.6, §4.4.3, §4.8; mechanism — `DOCUMENTATION.md` §14b, §64, §76, §77.
"""
import ast
import logging
import os
import sys
import tempfile
import time
import zipfile

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least, wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import i18n  # noqa: E402
import modules.archive_extract as AX  # noqa: E402
import modules.archive_view as AV  # noqa: E402
import modules.local_fs_worker as LOCAL  # noqa: E402
import modules.sftp_send as SS  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.sftp_tab import SOURCE_LOCAL, SftpTab  # noqa: E402
from modules.sftp_worker import SftpWorker  # noqa: E402
from modules.terminal_page import TerminalSessionPage  # noqa: E402

from _fakes import (EventLog, FakeSSHClient, FakeSSHThread, FakeSftpClient, FakeSftpFS,  # noqa: E402
                    wire_worker)

LANGS = load_i18n_langs(ROOT)
ST.SSHTerminalThread = FakeSSHThread
WORK_TREE = os.path.join(WORK, "slot")
if not os.path.isdir(WORK_TREE):
    os.makedirs(WORK_TREE)
# The spool family and the stage reader take `tempfile.gettempdir()`: this file CLAIMS spools on
# purpose, and the suite's own `tests/test_files_surface.py` audits the OS temp for leftovers — so
# the process confines both to its workdir (a sibling test never reads this one's live spool).
_ISOLATED_TMP = os.path.join(WORK, "tmp")
os.makedirs(_ISOLATED_TMP, exist_ok=True)
tempfile.tempdir = _ISOLATED_TMP


def build_zip(path, members):
    """A REAL zip: `members` = [(name, bytes)]."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    return path


def build_dirs_then_files(path, dirs, files):
    """A REAL zip whose FIRST members are DIRECTORY entries — the bound counts rows, not members."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for index in range(dirs):
            archive.writestr(zipfile.ZipInfo("d%04d/" % index), b"")
        for index in range(files):
            archive.writestr("f%04d.txt" % index, b"x\n")
    return path


def make_tab(fs=None):
    """A Files container: over the fake server, or bare (the local source needs no worker)."""
    tab = SftpTab()
    tab.message.connect(lambda *_args: None)
    tab.set_commander(True)
    if fs is not None:
        worker = SftpWorker(FakeSftpClient(fs))
        wire_worker(worker, EventLog())
        worker.start()
        tab.set_worker(worker)
        return tab, worker
    return tab, None


def make_local_pane(tab):
    """The SECOND pane on the OS disk — the only pane the local source is offered to."""
    pane = tab.panes[1]
    tab.set_pane_source(pane, SOURCE_LOCAL)
    pane._relist(WORK_TREE)
    return pane


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
print("== §1 the READ listing's OWN bound: rows, ONE sentence, and the walk stops there ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the row bound IS the shipped walk bound — ONE number for how many members a surface carries",
      AV.ARCHIVE_LIST_MAX == SW.MAX_TREE_ENTRIES == AX.EXTRACT_MAX_ENTRIES == 5000,
      f"{AV.ARCHIVE_LIST_MAX}/{SW.MAX_TREE_ENTRIES}/{AX.EXTRACT_MAX_ENTRIES}")

_MANY = build_zip(os.path.join(WORK, "many.zip"),
                  [("f%05d.txt" % index, b"") for index in range(20000)])
_CALLS = []
_REAL_ENTRY = AV._entry


def _counted_entry(*args, **kwargs):
    _CALLS.append(1)
    return _REAL_ENTRY(*args, **kwargs)


AV._entry = _counted_entry
_STARTED = time.monotonic()
_ROWS, _ENC, _CODE, _CUT = AV.archive_listing(_MANY, "zip", 10)
_ELAPSED = time.monotonic() - _STARTED
AV._entry = _REAL_ENTRY
check("§1 a 20 000-member archive answers TEN rows and the flag that it was cut",
      _CODE == "" and len(_ROWS) == 10 and _CUT is True, f"rows={len(_ROWS)} cut={_CUT}")
check("§1 ...and the PARSE is the bound's own: eleven members are built out of twenty thousand",
      len(_CALLS) == 11, f"entries built={len(_CALLS)} in {_ELAPSED:.2f}s")
check("§1 ...so the walk costs the bound, not the archive", _ELAPSED < 5.0, f"{_ELAPSED:.2f}s")

_FEW = build_zip(os.path.join(WORK, "few.zip"), [("a.txt", b"a\n"), ("b.txt", b"b\n")])
_FEW_ROWS, _few_enc, _FEW_CODE, _FEW_CUT = AV.archive_listing(_FEW, "zip", 10)
_FULL_ROWS, _full_enc, _FULL_CODE, _FULL_CUT = AV.archive_listing(_MANY, "zip")
check("§1 an archive INSIDE the bound answers every row and claims no cut",
      _FEW_CODE == "" and len(_FEW_ROWS) == 2 and _FEW_CUT is False, f"{len(_FEW_ROWS)}/{_FEW_CUT}")
check("§1 a bound of ZERO is the shipped full walk (the extract half's own call)",
      _FULL_CODE == "" and len(_FULL_ROWS) == 20000 and _FULL_CUT is False,
      f"{len(_FULL_ROWS)}/{_FULL_CUT}")

_DIRS_FIRST = build_dirs_then_files(os.path.join(WORK, "dirs-first.zip"), 50, 5)
_DIR_ROWS, _dir_enc, _DIR_CODE, _DIR_CUT = AV.archive_listing(_DIRS_FIRST, "zip", 3)
check("§1 the bound counts ROWS: 50 directory members ahead of the files cost the walk, not the rows",
      _DIR_CODE == "" and [row["name"] for row in _DIR_ROWS] == ["f0000.txt", "f0001.txt", "f0002.txt"]
      and _DIR_CUT is True, str([row["name"] for row in _DIR_ROWS]))

check("§1 a refusal keeps its FOURTH answer honest: no rows, the code, and no cut",
      AV.archive_listing(os.path.join(WORK, "gone.zip"), "zip", 10)
      == ([], False, AV.ARCHIVE_ERROR_UNREADABLE, False))

_TAB, _WORKER = make_tab()
_PANE = make_local_pane(_TAB)
_TWELVE = build_zip(os.path.join(WORK_TREE, "twelve.zip"),
                    [("m%02d.txt" % index, b"x\n") for index in range(12)])
_PANE._relist(WORK_TREE)
_SEEN = []
_PANE.message.connect(_SEEN.append)
_REAL_LIST_MAX = AV.ARCHIVE_LIST_MAX
AV.ARCHIVE_LIST_MAX = 7
_PANE._show_archive(_TWELVE, _TWELVE, "zip", "")
app.processEvents()
check("§1 the pane builds at most the bound — a 12-member archive dresses SEVEN rows",
      _PANE.archive_tree.topLevelItemCount() == 7
      and _PANE.archive_label.text() == i18n.t("sftp.archive.header", name="twelve.zip", count=7),
      f"{_PANE.archive_tree.topLevelItemCount()} / {_PANE.archive_label.text()}")
check("§1 ...and says why, ONCE, in the shipped sentence of the bound",
      _SEEN.count(i18n.t("sftp.archive.list_cut", limit=7)) == 1,
      str([text for text in _SEEN if "seven" in text or "7" in text]))
check("§1 ...while the listing still reaches every row it DID carry (the member data is intact)",
      _PANE.archive_state["entries"].keys()
      == {"m%02d.txt" % index for index in range(7)},
      str(sorted(_PANE.archive_state["entries"])))
AV.ARCHIVE_LIST_MAX = _REAL_LIST_MAX
_TAB.close_preview()

check("§1 ...and the full listing of that archive carries every row again (the bound is the caller's)",
      len(AV.archive_listing(_TWELVE, "zip", AV.ARCHIVE_LIST_MAX)[0]) == 12
      and AV.archive_listing(_TWELVE, "zip", AV.ARCHIVE_LIST_MAX)[3] is False)

# ════════════════════════════════════════════════════════════════════════════
print("== §2 `Overwrite` on the extraction folder is a MERGE, and the question says so ==")
# ════════════════════════════════════════════════════════════════════════════

_FS = FakeSftpFS()
_FS.add_dir("/srv")
_FS.add_dir("/srv/data")
_FS.add_file("/srv/data/keep.txt", b"was here before\n")     # the archive does NOT hold it
_FS.add_file("/srv/data/README.txt", b"old content\n")       # the archive REPLACES it
_TAB2, _WORKER2 = make_tab(_FS)
_PANE_A = _TAB2.panes[0]
_STAGE = AX.create_stage()
with open(os.path.join(_STAGE, "README.txt"), "wb") as _handle:
    _handle.write(b"new content\n")
os.makedirs(os.path.join(_STAGE, "etc"))
with open(os.path.join(_STAGE, "etc", "app.conf"), "wb") as _handle:
    _handle.write(b"listen 80\n")
_ASKED = []


def _ask(name, target, remaining, facts=""):
    _ASKED.append({"name": name, "target": target, "remaining": remaining, "facts": facts})
    return "overwrite", False


_PANE_A._ask_conflict = _ask
_DELIVERED = _PANE_A.ship_staged_tree(_STAGE, "/srv", "data", {"data"}, written=2, skipped=[])
check("§2 the delivery is queued as the ONE folder, and the question is the shipped one",
      _DELIVERED == "data" and len(_ASKED) == 1 and _ASKED[0]["name"] == "data"
      and _ASKED[0]["remaining"] == 0, str(_ASKED))
check("§2 ...and it CARRIES the merge line — `Overwrite` describes what the engines really do",
      _ASKED[0]["facts"] == i18n.t("sftp.archive.merge_facts")
      and bool(str(_ASKED[0]["facts"]).strip()), repr(_ASKED[0]["facts"]))
check("§2 the facts line is a declared key of every language (not a literal of the pane)",
      all(str(data.get("sftp.archive.merge_facts") or "").strip() for data in LANGS.values()),
      str({code: bool(data.get("sftp.archive.merge_facts")) for code, data in LANGS.items()}))
check("§2 the delivery really lands, and the folder MERGES (the file the archive never held stays)",
      wait_for(lambda: _PANE_A._staged_deliveries == {}, timeout_ms=15000)
      and _FS.files.get("/srv/data/keep.txt") == b"was here before\n"
      and _FS.files.get("/srv/data/README.txt") == b"new content\n"
      and _FS.files.get("/srv/data/etc/app.conf") == b"listen 80\n",
      str(sorted(_FS.files)))

_ASKED_CLEAR = []
_PANE_A._ask_conflict = lambda name, target, remaining, facts="": (
    _ASKED_CLEAR.append(facts) or ("skip", False))
_SKIPPED = _PANE_A.ship_staged_tree(_STAGE, "/srv", "data", {"data"}, written=2, skipped=[])
check("§2 a `Skip` still refuses the WHOLE folder (the merge line never turns Skip into Overwrite)",
      _SKIPPED == "" and _ASKED_CLEAR == [i18n.t("sftp.archive.merge_facts")]
      and _FS.files.get("/srv/data/README.txt") == b"new content\n", str(_SKIPPED))
AX.drop_stage(_STAGE)

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the spool name: THIS platform's spelling, and the download leg accepts it ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 a `:` is an NTFS STREAM — the spool's own name takes the platform's spelling",
      SS._spool_base("report:final.pdf", windows=True) == "report_final.pdf"
      and SS._spool_base("report:final.pdf", windows=False) == "report:final.pdf",
      f"{SS._spool_base('report:final.pdf', windows=True)!r}")
check("§3 the wildcards `mkstemp` refuses become an ordinary name (and a control char too)",
      SS._spool_base("q?.txt", windows=True) == "q_.txt"
      and SS._spool_base('a<b>c|d"e.txt', windows=True) == "a_b_c_d_e.txt"
      and SS._spool_base("bell\x07.txt", windows=True) == "bell_.txt",
      SS._spool_base('a<b>c|d"e.txt', windows=True))
check("§3 a trailing dot or space is not a name on this platform — the spool carries neither",
      SS._spool_base("trail.", windows=True) == "trail"
      and SS._spool_base("space ", windows=True) == "space"
      and SS._spool_base("trail.", windows=False) == "trail.")
_LONG = SS._spool_base("x" * 300 + ".zip", windows=True)
check("§3 a 300-character stem is CUT, inside the name limit, and keeps its extension",
      len(_LONG) <= SS.SPOOL_BASE_MAX and _LONG.endswith(".zip") and _LONG.startswith("xxx"),
      f"{len(_LONG)} {_LONG[-12:]!r}")
check("§3 a name this platform already takes is returned UNCHANGED (the sanitiser is not a mangler)",
      SS._spool_base("payload.bin", windows=True) == "payload.bin"
      and SS._spool_base("payload.bin", windows=False) == "payload.bin"
      and SS._spool_base("", windows=True) == "file"
      and SS._spool_base(None, windows=True) == "file")

_SPOOL = SS.create_spool("report:final.pdf")
_SPOOL_NAME = os.path.basename(_SPOOL)
check("§3 the OS really claims it, and its name passes the SAME gate the download leg asks",
      bool(_SPOOL) and os.path.exists(_SPOOL) and SW.local_name_problem(_SPOOL_NAME) is None,
      f"{_SPOOL_NAME!r} -> {SW.local_name_problem(_SPOOL_NAME)!r}")
_COLON_PATH = SS.spool_path("report:final.pdf", token=1)
_EXPECTED_TAIL = "-report_final.pdf" if os.name == "nt" else "-report:final.pdf"
check("§3 `spool_path()` and `create_spool()` agree on the name (ONE reader of the base)",
      _COLON_PATH.endswith(_EXPECTED_TAIL), _COLON_PATH)
SS.drop_spool(_SPOOL)

_FS_SPOOL = FakeSftpFS()
_FS_SPOOL.add_dir("/srv")
_FS_SPOOL.add_file("/srv/report:final.pdf", b"x" * 100)
_TAB3, _WORKER3 = make_tab(_FS_SPOOL)
_LOG3 = EventLog()
wire_worker(_WORKER3, _LOG3)
_COLON_SPOOL = AV.spool_archive("report:final.pdf")
_SPOOL_DIR, _SPOOL_LOCAL, _SPOOL_MODE = AV.spool_download_args(_COLON_SPOOL)
_TASK = _WORKER3.queue_download("/srv/report:final.pdf", _SPOOL_DIR, total_size=100,
                                local_name=_SPOOL_LOCAL, part_mode=_SPOOL_MODE)
check("§3 ...so the READ half's leg really lands the copy (it was REFUSED as `unsafe_local_name`)",
      wait_for(lambda: _LOG3.of_kind("done", _TASK) or _LOG3.of_kind("error", _TASK),
               timeout_ms=15000)
      and _LOG3.of_kind("error", _TASK) == [] and AV.local_size(_COLON_SPOOL) == 100,
      f"task={_TASK} done={_LOG3.of_kind('done', _TASK)} error={_LOG3.of_kind('error', _TASK)} "
      f"size={AV.local_size(_COLON_SPOOL)}")
AV.drop_archive(_COLON_SPOOL)

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the extract leaves ONE line in the log: the counters, never the members ==")
# ════════════════════════════════════════════════════════════════════════════

_RECORDS = []


class _Capture(logging.Handler):
    """Collect what the application's own logger tree says (the `sshmap.*` family)."""

    def emit(self, record):
        try:
            _RECORDS.append((record.name, record.getMessage()))
        except Exception:   # noqa: BLE001 — a formatting failure must not break the extract
            pass


_CAPTURE = _Capture()
_LOGGER = logging.getLogger("sshmap")
_LOGGER.addHandler(_CAPTURE)
_LOGGER.setLevel(logging.DEBUG)

_EXTRACT_WORKER = LOCAL.LocalFsWorker(root=WORK)
_EXTRACT_WORKER.start()
_LOG_ZIP = build_zip(os.path.join(WORK, "logged.zip"),
                     [("one.txt", b"1\n"), ("two.txt", b"2\n")])
_LOG_DEST = os.path.join(WORK_TREE, "logged")
_RESULT, _ERROR = run_extract(_EXTRACT_WORKER, _LOG_ZIP, _LOG_DEST)
_LINES = [message for _name, message in _RECORDS if message.startswith("Extract:")]
check("§4 a COMPLETE extraction writes exactly ONE line", _ERROR == "" and len(_LINES) == 1,
      f"{_LINES} error={_ERROR!r}")
check("§4 ...naming the members written, the destination and both skip counters",
      _LINES and "2 file(s)" in _LINES[0] and _LOG_DEST in _LINES[0]
      and "0 skipped by the plan" in _LINES[0] and "0 unreadable" in _LINES[0], str(_LINES))
check("§4 ...and it is the ENGINE's line (the worker's own logger, not a pane's)", 
      any(name == LOCAL.log.name for name, message in _RECORDS if message.startswith("Extract:")),
      f"{LOCAL.log.name} / {[name for name, _m in _RECORDS]}")

_RECORDS.clear()
_REFUSED_RESULT, _REFUSED_ERROR = run_extract(
    _EXTRACT_WORKER, _LOG_ZIP, os.path.join(WORK_TREE, "refused"), limits={"entries": 1})
check("§4 a REFUSED extraction writes no success line at all",
      _REFUSED_RESULT is None and _REFUSED_ERROR != ""
      and not [message for _name, message in _RECORDS if message.startswith("Extract:")],
      f"{_REFUSED_ERROR!r} {_RECORDS}")
_LOGGER.removeHandler(_CAPTURE)

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the SFTP-open slots answer to the handshake that EMITTED ==")
# ════════════════════════════════════════════════════════════════════════════


class _Client:
    """The smallest client a slot can close — the record says WHO closed it."""

    def __init__(self, label):
        self.label = label
        self.closed = False

    def close(self):
        self.closed = True


class _Handshake(QObject):
    """The handshake's THREE signals and the two readers the slots ask for."""

    ready = Signal()
    failed = Signal(str)
    finished = Signal()

    def __init__(self, label, client):
        super().__init__()
        self.label = label
        self.client = client
        self.transport = f"transport-{label}"
        self.taken = []
        self.done = False

    def take_client(self):
        client, self.client = self.client, None
        if client is not None:
            self.taken.append(client)
        return client

    def isFinished(self):
        return self.done

    def close(self):
        """The teardown's call: drop what the fake still holds (the shipped `close()` shape)."""

    def shutdown(self, wait_ms=0):
        """The teardown's second call: nothing to join — the fake has no thread."""


_PAGE = TerminalSessionPage(ServerData(id="slot-1", alias="slot", host="10.99.0.7",
                                       user="root"), None)
app.processEvents()
_BOUND = []
_REAL_BIND = _PAGE._bind_sftp_worker
_PAGE._bind_sftp_worker = lambda sftp, transport: _BOUND.append((sftp, transport)) or True
_MESSAGES = []
_PAGE.status_message.connect(lambda text, ms: _MESSAGES.append(text))

_STALE = _Handshake("stale", _Client("stale"))
_CURRENT = _Handshake("current", _Client("current"))
_PAGE._sftp_handshake = _CURRENT
_STALE.ready.connect(_PAGE._on_sftp_open_ready)
_CURRENT.ready.connect(_PAGE._on_sftp_open_ready)
_STALE.ready.emit()
app.processEvents()
check("§5 an answer from a STALE handshake binds nothing — the page's own open is still the one",
      _BOUND == [] and _CURRENT.taken == [] and _PAGE._sftp_handshake is _CURRENT,
      f"bound={_BOUND} current_taken={_CURRENT.taken}")
check("§5 ...and the channel that stale open produced is CLOSED, never leaked",
      _STALE.taken and _STALE.taken[0].closed is True, str(_STALE.taken))

_STALE.failed.emit("refused by the stale open")
app.processEvents()
check("§5 a stale REFUSAL is not this session's sentence (the live open is still waiting)",
      _MESSAGES == [] and _PAGE._sftp_handshake is _CURRENT, str(_MESSAGES))

_STALE.done = True
_STALE.finished.emit()
app.processEvents()
check("§5 a stale `finished` never clears the reference of the LIVE handshake",
      _PAGE._sftp_handshake is _CURRENT, str(_PAGE._sftp_handshake))

_CURRENT.ready.emit()
app.processEvents()
check("§5 the CURRENT handshake binds its own client over its own transport",
      len(_BOUND) == 1 and _BOUND[0][0] is _CURRENT.taken[0]
      and _BOUND[0][1] == "transport-current" and _CURRENT.taken[0].closed is False,
      str(_BOUND))

_BOUND.clear()
_DIRECT = _Handshake("direct", _Client("direct"))
_PAGE._sftp_handshake = _DIRECT
_PAGE._on_sftp_open_ready()
app.processEvents()
check("§5 a DIRECT call (a teardown, a probe) still answers the page's own handshake — the seam holds",
      len(_BOUND) == 1 and _BOUND[0][0] is _DIRECT.taken[0], str(_BOUND))

_LIVE = TerminalSessionPage(ServerData(id="slot-2", alias="live", host="10.99.0.7",
                                       user="root"), None)
app.processEvents()
_FS_LIVE = FakeSftpFS()
_FS_LIVE.add_dir("/srv")
_LIVE.terminal_thread.client = FakeSSHClient(FakeSftpClient(_FS_LIVE))
check("§5 the ORDINARY open still runs end to end (the fake transport answers the version)",
      _LIVE._ensure_sftp() is False and _LIVE.sftp_channel_pending() is True,
      f"pending={_LIVE.sftp_channel_pending()}")
check("§5 ...and the worker is bound by the handshake that really emitted it",
      wait_for(lambda: _LIVE._sftp_worker is not None, timeout_ms=15000)
      and _LIVE.sftp_channel_pending() is False, f"worker={_LIVE._sftp_worker}")

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the release: one owner per answer, the pin, the version ==")
# ════════════════════════════════════════════════════════════════════════════

def owners_of(function_name):
    """Every module of the tree that DEFINES this top-level function (the one-owner rule)."""
    found = []
    for folder, _dirs, names in os.walk(os.path.join(ROOT, "modules")):
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            if any(isinstance(node, ast.FunctionDef) and node.name == function_name
                   for node in tree.body):
                found.append(os.path.relpath(path, ROOT).replace("\\", "/"))
    return found


check("§6 the spool's name reader has ONE home (`modules/sftp_send.py`)",
      owners_of("_spool_base") == ["modules/sftp_send.py"], str(owners_of("_spool_base")))
_VIEWER_SRC = open(os.path.join(ROOT, "modules", "sftp_pane_viewer.py"), encoding="utf-8").read()
check("§6 the pane asks the listing with the bound (the door reads the constant, not a literal)",
      "ARCHIVE_LIST_MAX" in _VIEWER_SRC and "archive_listing(local, kind" in _VIEWER_SRC)
_PAGE_SRC = open(os.path.join(ROOT, "modules", "terminal_page_sftp.py"), encoding="utf-8").read()
check("§6 the three handshake slots ask WHO emitted (ONE reader, three callers)",
      _PAGE_SRC.count("self._emitting_handshake()") == 3
      and "_on_sftp_open_ready(self, handshake=None)" in _PAGE_SRC)
check("§6 the facade keeps its declared budget (`< 3 000` lines) with this patch in place",
      len(open(os.path.join(ROOT, "modules", "sftp_tab.py"), encoding="utf-8").read().splitlines())
      < 3000)

for _key in ("sftp.archive.list_cut", "sftp.archive.merge_facts"):
    check(f"§6 {_key} is present and non-empty in every language",
          all(str(data.get(_key) or "").strip() for data in LANGS.values()),
          str({code: bool(data.get(_key)) for code, data in LANGS.items()}))
check_i18n_parity(LANGS)
check_release_state(ROOT)
check("§6 the pin is the released 1 125 plus the slot's TWO keys — and nothing else",
      EXPECTED_I18N_KEYS == 1127 + 8 + 9 + 18 + 4 + 13 + 1 + 1 + 12 + 3 + 2, str(EXPECTED_I18N_KEYS))
check("§6 the version is the THIRD patch of the released line",
      releases_at_least(EXPECTED_APP_VERSION, "1.13.1.3"), EXPECTED_APP_VERSION)

for _worker in (_WORKER, _WORKER2, _WORKER3):
    if _worker is not None:
        _worker.shutdown(2500)
for _container in (_TAB, _TAB2, _TAB3):
    _container.release()
_EXTRACT_WORKER.shutdown(2500)
_PAGE.shutdown()
_LIVE.shutdown()
finish()
