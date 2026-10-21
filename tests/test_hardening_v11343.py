# -*- coding: utf-8 -*-
"""The nine defects a review of `v1.13.4` still owed, each one REPRODUCED and fixed (v1.13.4.3).
§1 an archive spool is OWNED by the provider it was copying FROM until that provider answers (N131); §2 a merge write that cannot keep
the copy of an unreadable file REFUSES the publish (N132); §3 a duplicate command id is regenerated at
load/import (N133); §4 ONE encoding for the library family, a BOM included (N134); §5 a plugin command's
wall-clock deadline and the abort that closes its channel (N135); §6 a cancel covers the tasks visible at
the click, never the queue's future (N136); §7 the node deletion never waits on a worker (N137); §8 the
small code leftovers of the review (N138); §9 the release — no new key, no schema move, the pin.
Rule — `AGENTS.md` §4.2, §4.3.6, §4.4.4, §4.8.1, §4.26; mechanism — `DOCUMENTATION.md` §14e, §14f, §15, §33, §49, §71, §76.
Run: python tests/test_hardening_v11343.py
"""
import json
import os
import re
import shutil
import sys
import threading
import time
import zipfile

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least, translation_keys, wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import paramiko  # noqa: E402

import i18n  # noqa: E402
import modules.archive_view as AV  # noqa: E402
import modules.command_library as CL  # noqa: E402
import modules.command_history as CH  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import modules.local_fs_worker as LOCAL  # noqa: E402
import modules.plugin_context as PC  # noqa: E402
import modules.plugin_runner as PR  # noqa: E402
import modules.sftp_send as SEND  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402
import modules.ssh_worker as SSH  # noqa: E402
import modules.terminal_diff as DIFF  # noqa: E402
import storage.atomic as ATOMIC  # noqa: E402
import ui.main_window as MW  # noqa: E402
import ui.main_window_node_ops as NODE  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.sftp_tab import SOURCE_LOCAL, SftpTab  # noqa: E402
from modules.sftp_worker import SftpWorker  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)
clear_cfg()
WORK_TREE = os.path.join(WORK, "v11343")


def _read(*parts) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def _tmp(name, data=b"", binary=True):
    os.makedirs(WORK_TREE, exist_ok=True)
    path = os.path.join(WORK_TREE, name)
    with open(path, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as fh:
        fh.write(data)
    return path


class _YesBox:
    """The shipped dialog seam: every question answers Yes (the module attribute IS the seam)."""

    Yes = QMessageBox.StandardButton.Yes
    No = QMessageBox.StandardButton.No

    @staticmethod
    def question(*_a, **_kw):
        return QMessageBox.StandardButton.Yes


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the archive spool a source switch abandons (N131) ==")
# ════════════════════════════════════════════════════════════════════════════

BIG_ZIP = os.path.join(WORK_TREE, "big.zip")
os.makedirs(WORK_TREE, exist_ok=True)
with zipfile.ZipFile(BIG_ZIP, "w", zipfile.ZIP_STORED) as _zip:
    _zip.writestr("inside.txt", b"z" * (8 * 32768))
with open(BIG_ZIP, "rb") as _fh:
    BIG_DATA = _fh.read()

_fs = FakeSftpFS()
_fs.add_dir("/srv")
_fs.add_file("/big.zip", BIG_DATA, mtime=1_700_000_000)
_worker = SftpWorker(FakeSftpClient(_fs, chunk_delay=0.02))   # a leg that is still copying
_log = EventLog()
wire_worker(_worker, _log)
_worker.start()
_tab = SftpTab()
_tab.message.connect(lambda *_a: None)
_tab.set_commander(True)
_tab.set_worker(_worker)
_pane = _tab.panes[0]
check("§1 the slow fixture lists its archive (the leg is about to be interrupted)",
      wait_for(lambda: any(_pane.tree.topLevelItem(i).text(0) == "big.zip"
                           for i in range(_pane.tree.topLevelItemCount())), timeout_ms=5000),
      str(_worker.isRunning()))
_item = next(_pane.tree.topLevelItem(i) for i in range(_pane.tree.topLevelItemCount())
             if _pane.tree.topLevelItem(i).text(0) == "big.zip")
_pane._op_view_archive(_item)
app.processEvents()
_spool = next(iter(_pane._archive_tasks.values()))[1] if _pane._archive_tasks else ""
check("§1 the door claimed a spool and queued ONE leg of the shipped queue",
      bool(_spool) and os.path.exists(_spool) and not _pane.archive_open, _spool)

_tab.set_worker(None)   # the SOURCE SWITCH: the provider is left while the leg is still copying
check("§1 the leg is OWNED by the provider it belonged to — not forgotten, not dropped under it",
      _pane._archive_tasks == {} and list(_pane._archive_legs) == [_worker]
      and os.path.exists(_spool), f"{_pane._archive_legs} / spool={os.path.exists(_spool)}")
check("§1 …and the pane answers on that provider's OWN signals (one connection per owner)",
      bool(wait_for(lambda: not _pane._archive_legs, timeout_ms=10000)), str(_pane._archive_legs))
check("§1 the answer dropped the copy the commit really published (no spool survives the switch)",
      not os.path.exists(_spool) and _pane._archive_legs == {} and _pane.archive_open is False
      and bool(_log.of_kind("done")), f"spool={os.path.exists(_spool)} log={_log.of_kind('done')}")
check("§1 a leg that is answered twice is a no-op (the id left the map with its answer)",
      _pane._on_leg_done(1, "") is None and _pane._archive_legs == {})

_orphan = AV.spool_archive("orphan.car")
with open(_orphan, "wb") as _fh:
    _fh.write(b"stale")
_pane._archive_tasks[424242] = ("/big.zip", _orphan, "zip")
_pane._archive_forget_legs()   # a TEARDOWN: no provider answers any more
check("§1 a teardown with no provider left drops the spool at once and forgets the leg",
      not os.path.exists(_orphan) and _pane._archive_tasks == {} and _pane._archive_legs == {},
      str(_pane._archive_tasks))

_worker.shutdown(3000)
_tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the merge write that cannot keep a copy refuses the publish (N132) ==")
# ════════════════════════════════════════════════════════════════════════════

BROKEN = _tmp("config.json", b'{"broken": ')   # exists, cannot be parsed
_BEFORE = open(BROKEN, "rb").read()


class _RefusingCopy:
    """A `shutil` whose ONE call fails — the transient copy failure of the entry."""

    @staticmethod
    def copy2(*_a, **_kw):
        raise OSError("copy refused")


_REAL_SHUTIL = ATOMIC.shutil
ATOMIC.shutil = _RefusingCopy
try:
    _wrote = ATOMIC.write_json_atomic(BROKEN, {"saved": True}, merge=True)
finally:
    ATOMIC.shutil = _REAL_SHUTIL
check("§2 a copy that cannot be made REFUSES the write (False, never a logged risk)",
      _wrote is False, str(_wrote))
check("§2 …and the file it could not read is left byte-identical",
      open(BROKEN, "rb").read() == _BEFORE, open(BROKEN, "rb").read()[:40])
check("§2 …with no `.bad-` copy invented by the refusal",
      not [n for n in os.listdir(WORK_TREE) if ".bad-" in n], str(os.listdir(WORK_TREE)))

_wrote_ok = ATOMIC.write_json_atomic(BROKEN, {"saved": True}, merge=True)
_copies = [n for n in os.listdir(WORK_TREE) if ".bad-" in n]
check("§2 the ordinary merge still copies the unreadable file aside and then writes",
      _wrote_ok is True and len(_copies) == 1
      and open(os.path.join(WORK_TREE, _copies[0]), "rb").read() == _BEFORE,
      f"wrote={_wrote_ok} copies={_copies}")
check("§2 …and the merged document is the payload over an empty base",
      json.load(open(BROKEN, encoding="utf-8")) == {"saved": True},
      open(BROKEN, encoding="utf-8").read())

CLEAN = _tmp("clean.json", b'{"a": 1}')
check("§2 a merge over a HEALTHY file needs no copy at all",
      ATOMIC.write_json_atomic(CLEAN, {"b": 2}, merge=True) is True
      and json.load(open(CLEAN, encoding="utf-8")) == {"a": 1, "b": 2}
      and not [n for n in os.listdir(WORK_TREE) if n.startswith("clean.json.bad-")])

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the duplicate command id is regenerated at load and import (N133) ==")
# ════════════════════════════════════════════════════════════════════════════

LIB = _tmp("commands.json", json.dumps({"seeded": True, "commands": [
    {"id": "dup", "name": "first", "command": "echo one", "category": "", "enabled": True},
    {"id": "dup", "name": "second", "command": "echo two", "category": "", "enabled": True},
    {"id": "", "name": "third", "command": "echo three", "category": "", "enabled": True},
]}, ensure_ascii=False).encode("utf-8"))
_entries = CL.CommandLibraryStore(LIB).load()
_ids = [e["id"] for e in _entries]
check("§3 the FIRST record keeps its id, the duplicate gets a fresh one",
      len(_entries) == 3 and _ids[0] == "dup" and len(set(_ids)) == 3
      and all(isinstance(i, str) and i for i in _ids), str(_ids))
check("§3 the ONE document reader answers the same rule as the store",
      [(e["id"] == "dup", e["name"]) for e in
       CL.entries_from_document(json.load(open(LIB, encoding="utf-8")))]
      == [(True, "first"), (False, "second"), (False, "third")])
check("§3 the IMPORT reader answers the same rule too",
      [e["name"] for e in CL.read_library_file(LIB)["entries"]] == ["first", "second", "third"]
      and len({e["id"] for e in CL.read_library_file(LIB)["entries"]}) == 3)

_panel = CL.CommandLibraryPanel(None, store=CL.CommandLibraryStore(LIB))
_panel.reload()


def _tree_rows(panel):
    """Every ROW of the commands tree, category by category (a refresh rebuilds these items)."""
    out = []
    for index in range(panel.tree.topLevelItemCount()):
        top = panel.tree.topLevelItem(index)
        for child in range(top.childCount()):
            out.append(top.child(child))
    return out


_rows = _tree_rows(_panel)
check("§3 every record keeps its OWN row (no row resolves to another record)",
      len(_rows) == 3
      and [_panel._entry_for_item(r)["name"] for r in _rows] == ["first", "second", "third"],
      str([_panel._entry_for_item(r)["name"] for r in _rows]))

_first = _panel._entry_for_item(_rows[0])


class _StubDialog:
    """The ONE dialog seam: an accepted form that answers fixed fields."""

    data = {}

    def __init__(self, *_a, **_kw):
        pass

    def exec(self):
        return QDialog.DialogCode.Accepted

    def result_entry(self):
        return dict(type(self).data)


_DIALOG = CL.CommandLibraryDialog
_BOX_CL = CL.QMessageBox
CL.CommandLibraryDialog = _StubDialog
CL.QMessageBox = _YesBox   # the shipped confirmation answers Yes (the module attribute seam)
try:
    _StubDialog.data = {"name": "first (edited)", "command": "echo one",
                        "category": "", "enabled": True, "confirm": False}
    _panel._edit_entry(_first)
    _after_edit = CL.CommandLibraryStore(LIB).load()
    check("§3 Edit acts on the record its ROW carries (the second record is untouched)",
          [_e["name"] for _e in _after_edit] == ["first (edited)", "second", "third"],
          str([_e["name"] for _e in _after_edit]))
    _panel._delete_entry(_panel._entry_for_item(_tree_rows(_panel)[0]))
    _after_delete = CL.CommandLibraryStore(LIB).load()
    check("§3 Delete removes the record its ROW carries, and only that one",
          [_e["name"] for _e in _after_delete] == ["second", "third"]
          and len({_e["id"] for _e in _after_delete}) == 2,
          str([_e["name"] for _e in _after_delete]))
finally:
    CL.CommandLibraryDialog = _DIALOG
    CL.QMessageBox = _BOX_CL
_panel.deleteLater()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 ONE encoding for the library family (N134) ==")
# ════════════════════════════════════════════════════════════════════════════

BOM_LIB = os.path.join(WORK_TREE, "bom", "commands.json")
os.makedirs(os.path.dirname(BOM_LIB), exist_ok=True)
_BOM_DOC = json.dumps({"seeded": True, "commands": [
    {"id": "bom1", "name": "BOM entry", "command": "echo bom", "category": "", "enabled": True},
]}, ensure_ascii=False).encode("utf-8")
with open(BOM_LIB, "wb") as _fh:
    _fh.write(b"\xef\xbb\xbf" + _BOM_DOC)

check("§4 the family declares ONE encoding (the language-file rule)",
      CL.LIBRARY_ENCODING == "utf-8-sig", CL.LIBRARY_ENCODING)
check("§4 a BOM'd library is NOT corruption — the panel reads it",
      [e["name"] for e in CL.CommandLibraryStore(BOM_LIB).load()] == ["BOM entry"],
      str(CL.CommandLibraryStore(BOM_LIB).load()))
check("§4 …and the import reader reads the SAME file the same way",
      CL.read_library_file(BOM_LIB)["ok"] is True
      and [e["name"] for e in CL.read_library_file(BOM_LIB)["entries"]] == ["BOM entry"])

_RESTORE_DOC = json.dumps({"seeded": True, "commands": [
    {"id": "ring1", "name": "from the ring", "command": "echo ring", "category": "",
     "enabled": True}]}, ensure_ascii=False).encode("utf-8")
CL.restore_library_payload(b"\xef\xbb\xbf" + _RESTORE_DOC, BOM_LIB)
check("§4 …and a RING slot restored as raw bytes is read by the same reader",
      [e["name"] for e in CL.CommandLibraryStore(BOM_LIB).load()] == ["from the ring"],
      str(CL.CommandLibraryStore(BOM_LIB).load()))
check("§4 …while a plain UTF-8 file needs no marker either",
      CL.read_library_file(_tmp("plainlib.json", _RESTORE_DOC))["count"] == 1)

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the plugin command's deadline and its abort (N135) ==")
# ════════════════════════════════════════════════════════════════════════════


class _DribbleChannel:
    """A producer that dribbles ONE byte per `recv()` — the case a channel timeout never ends."""

    def __init__(self):
        self.calls, self.timeouts, self.closed = [], [], False
        self.status_event = threading.Event()
        self.status_event.set()

    def recv(self, n):
        self.calls.append(int(n))
        if self.closed:
            raise OSError("channel closed")
        time.sleep(0.002)
        return b"x"

    def settimeout(self, value):
        self.timeouts.append(float(value))

    def recv_exit_status(self):
        return 0

    def close(self):
        self.closed = True


class _BlockedChannel(_DribbleChannel):
    """A `recv()` that blocks until the channel is CLOSED from another thread (the abort's case)."""

    def __init__(self):
        super().__init__()
        self.release = threading.Event()
        self.blocked = threading.Event()

    def recv(self, n):
        self.calls.append(int(n))
        self.blocked.set()
        self.release.wait(10.0)
        if not self.closed:
            return b"x"
        raise OSError("channel closed")

    def close(self):
        self.closed = True
        self.release.set()


class _EofChannel(_DribbleChannel):
    """A stream with nothing on it (the error stream of an ordinary command)."""

    def recv(self, n):
        return b""


class _Stream:
    def __init__(self, channel):
        self.channel = channel

    def read(self, *args):
        raise AssertionError("the stream was read without a bounded size")


class _Stdin:
    def close(self):
        pass


class _PluginClient:
    """A minimal `paramiko.SSHClient` for ONE `exec_command` (no socket, no auth)."""

    channel_factory = _DribbleChannel
    last = None

    def __init__(self, *_a, **_kw):
        self.out = type(self).channel_factory()
        self.err = _EofChannel()
        type(self).last = self

    def connect(self, **_kw):
        pass

    def exec_command(self, command, timeout=None):
        self.timeout = timeout
        return _Stdin(), _Stream(self.out), _Stream(self.err)

    def close(self):
        pass


_NODE = PC.node_record({"id": "cap", "alias": "cap", "host": "127.0.0.1", "user": "root"})
_ORIG_CLIENT, _ORIG_POLICY = paramiko.SSHClient, HKP.SshKnownHostsPolicy
HKP.SshKnownHostsPolicy = type("_Policy", (), {
    "__init__": lambda s, *a, **k: None, "apply_to_client": lambda s, c: None})
paramiko.SSHClient = _PluginClient
try:
    _PluginClient.channel_factory = _DribbleChannel
    _t0 = time.monotonic()
    _dribbled = PR.run_command_over_ssh(_NODE, "watch date", timeout=0.4)
    _elapsed = time.monotonic() - _t0
    _dribble_ch = _PluginClient.last.out
    check("§5 a DRIBBLING producer ends at the declared wall clock, not at the byte cap",
          _elapsed < 3.0 and 0 < len(_dribbled.output) < PR.OUTPUT_MAX,
          f"elapsed={_elapsed:.2f} bytes={len(_dribbled.output)}")
    check("§5 …and every `recv()` was bounded by the time the budget had left",
          bool(_dribble_ch.timeouts) and all(t <= 0.4 + 1e-6 for t in _dribble_ch.timeouts),
          str(_dribble_ch.timeouts[:4]))
    _PluginClient.channel_factory = _EofChannel
    _ordinary = PR.run_command_over_ssh(_NODE, "true", timeout=0.4)
    check("§5 …while an ordinary command under the cap keeps its whole output and its exit code",
          _ordinary.output == "" and _ordinary.exit_code == 0, str(_ordinary.as_dict()))

    _PluginClient.channel_factory = _BlockedChannel
    _PluginClient.last = None   # the fixture of THIS call is the one the wait looks for
    _runner = PR.PluginCommandRunner([_NODE], "tail -f /var/log/syslog", plugin_id="bound",
                                     timeout=10.0)
    _results = []
    _runner.node_result.connect(lambda nid, payload: _results.append(payload))
    _runner.start()
    check("§5 the node in flight is really BLOCKED in its channel",
          wait_for(lambda: _PluginClient.last is not None
                   and _PluginClient.last.out.blocked.is_set(), timeout_ms=5000))
    _blocked_ch = _PluginClient.last.out
    _t1 = time.monotonic()
    _stopped = _runner.stop(3000)
    check("§5 stop() ABORTS it — the channel the read blocks on is closed",
          _stopped is True and _blocked_ch.closed is True
          and time.monotonic() - _t1 < 3.0,
          f"stopped={_stopped} closed={_blocked_ch.closed}")
    app.processEvents()
    check("§5 …and the call reports the node it stopped (no answer lost, no thread left)",
          len(_results) == 1 and _runner.is_done() is True, str(_results))
finally:
    paramiko.SSHClient = _ORIG_CLIENT
    HKP.SshKnownHostsPolicy = _ORIG_POLICY

check("§5 a transport that does NOT declare the seam is called with its own four arguments",
      PR._accepts_control(PR.run_command_over_ssh) is True
      and PR._accepts_control(lambda node, command, timeout, credentials: None) is False)

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the cancel token covers the click, not the queue's future (N136) ==")
# ════════════════════════════════════════════════════════════════════════════

_fs2 = FakeSftpFS()
_fs2.add_dir("/srv")
_fs2.add_file("/slow.bin", b"s" * (8 * 32768), mtime=1_700_000_000)
_worker2 = SftpWorker(FakeSftpClient(_fs2, chunk_delay=0.02))
_log2 = EventLog()
wire_worker(_worker2, _log2)
_worker2.start()
_local_src = os.path.join(WORK_TREE, "slow.bin")
with open(_local_src, "wb") as _fh:
    _fh.write(b"u" * (8 * 32768))
_tid_slow = _worker2.queue_upload(_local_src, "/srv")
check("§6 the slow upload is really in flight", wait_for(lambda: bool(_log2.of_kind("progress", _tid_slow)),
                                                     timeout_ms=5000))
_worker2.cancel()   # the click covers the tasks VISIBLE now
_tid_late = _worker2.queue_upload(_local_src, "/srv")   # queued while the first one unwinds
check("§6 the clicked task is cancelled", bool(wait_for(
    lambda: _log2.of_kind("cancelled", _tid_slow), timeout_ms=8000)))
check("§6 …and the task queued AFTER the click really RUNS (the defect of the entry)",
      bool(wait_for(lambda: _log2.of_kind("done", _tid_late), timeout_ms=10000))
      and not _log2.of_kind("cancelled", _tid_late), str([e[:2] for e in _log2.events]))
check("§6 …with the shipped atomic copy, so the previous remote file is not truncated",
      len(_fs2.files.get("/srv/slow.bin", b"")) == 8 * 32768
      and not [p for p in _fs2.files if p.endswith(".part")], str(sorted(_fs2.files)))
_worker2.shutdown(3000)

# The same rule without threads: the token is the ids of THIS worker, compared per task.
_plain = SftpWorker(FakeSftpClient(FakeSftpFS()))
_early = _plain.queue_list("/")
_plain.cancel()
_later = _plain.queue_list("/")
check("§6 an IDLE-click arming covers the very next task and nothing else",
      _plain._begin_task(_plain._queue.get_nowait()) is True
      and _plain._end_task(_early) is None
      and _plain._begin_task(_plain._queue.get_nowait()) is False,
      f"ids={_early},{_later}")

_LATE = LOCAL.LocalFsWorker(root=WORK_TREE)
_late_ids = [_LATE.queue_list(WORK_TREE), _LATE.queue_list(WORK_TREE)]
_LATE.cancel()
_task = _LATE._queue.get_nowait()
check("§6 the LOCAL provider mirrors the rule (one snapshot, one comparison per task)",
      _LATE._begin_task(_task) is True and _LATE._end_task(_task.id) is None
      and _LATE._begin_task(_LATE._queue.get_nowait()) is True)
_LATE.queue_list(WORK_TREE)
check("§6 …and the task queued after the click is never covered",
      _LATE._begin_task(_LATE._queue.get_nowait()) is False, str(_late_ids))
_LATE.shutdown(1000)

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the node deletion never waits on a worker (N137) ==")
# ════════════════════════════════════════════════════════════════════════════


class _SlowWorker(QThread):
    """The running worker a deletion waits on: it holds the removal until it answers."""

    def __init__(self):
        super().__init__()
        self._start_requested = False
        self.stop_asked = False
        self._hold = threading.Event()

    def request_stop(self):
        self.stop_asked = True

    def run(self):
        self._hold.wait(10.0)

    def release_hold(self):
        self._hold.set()


_window = MW.MainWindow()
_node = _window.scene.add_server(
    ServerData(id="n137", alias="slow-delete", host="10.0.0.1", user="u"))
_slow = _SlowWorker()
_slow.start()
SSH._active_workers["n137"] = _slow
_BOX = NODE.QMessageBox
NODE.QMessageBox = _YesBox
try:
    _t2 = time.monotonic()
    _accepted = _window._remove_node_guarded(_node)
    _waited = time.monotonic() - _t2
finally:
    NODE.QMessageBox = _BOX
check("§7 the deletion answers AT ONCE — the GUI thread never waits on a QThread",
      _waited < 0.5 and _accepted is True and _slow.stop_asked is True, f"waited={_waited:.3f}s")
check("§7 …the node is still on the map while the worker runs (the removal is DEFERRED)",
      _window.scene.get_node("n137") is not None and _window._deferred_deletes.get("n137") is True)
_slow.release_hold()
check("§7 …and the removal follows the worker's ANSWER",
      wait_for(lambda: _window.scene.get_node("n137") is None, timeout_ms=5000)
      and not _window._deferred_deletes, str(list(_window._deferred_deletes)))
_slow.wait(3000)
SSH._active_workers.pop("n137", None)

check("§7 no GUI module calls the BLOCKING wait any more",
      "wait_for_worker" not in _read("ui", "main_window_node_ops.py"),
      [ln for ln in _read("ui", "main_window_node_ops.py").splitlines()
       if "wait_for_worker" in ln])
check("§7 …and the worker's own door is what a stop asks (additive to its public API)",
      callable(getattr(SSH.SSHWorker, "request_stop", None))
      and callable(getattr(SSH.SSHWorker, "is_stop_requested", None)))

# ════════════════════════════════════════════════════════════════════════════
print("== §8 the small code leftovers (N138) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§8 `history_key()` of NO id answers \"\" — the empty digest is not an identity",
      CH.history_key("") == "" and CH.history_key(None) == "" and CH.history_key("  ") == ""
      and CH.history_path_for("") == "" and CH.history_key("srv-1") != "")


class _PageStub:
    """The page surface `diff_targets_from_pages()` reads."""

    def __init__(self, server_id):
        self.server_data = type("_Data", (), {"id": server_id, "alias": "a" + server_id,
                                              "host": "10.0.0.9"})()
        self._is_split_pane = False

    def load_into_diff(self):
        return True


_targets = DIFF.diff_targets_from_pages([_PageStub(""), _PageStub("srv-1")])
check("§8 the pure target reader keeps the identified session and drops the anonymous one",
      len(_targets) == 1 and _targets[0].key == CH.history_key("srv-1"),
      str([t.key for t in _targets]))
check("§8 the dead `..modules` fallback is gone — ONE spelling of the import",
      all(f"from ..modules.{name}" not in _read("ui", "main_window_ssh.py")
          for name in ("sftp_send", "command_history", "terminal_diff"))
      and _window._send_session_targets() == [] and _window._diff_targets() == [])

_KEYS = ("legend.status.online", "legend.status.offline", "legend.status.warn",
         "statusbar.filter.online", "statusbar.filter.offline", "statusbar.filter.warn")
_EN, _RU = LANGS["en"], LANGS["ru"]
check("§8 the ru legend and status filter are TRANSLATED (no English value left)",
      all(_RU[key] != _EN[key] for key in _KEYS),
      str({key: _RU[key] for key in _KEYS}))
check("§8 …with the placeholders and the line breaks of the en value",
      all(re.findall(r"\{(\w+)\}", _RU[key]) == re.findall(r"\{(\w+)\}", _EN[key])
          and _RU[key].count("\n") == _EN[key].count("\n") for key in _KEYS),
      str({key: re.findall(r"\{(\w+)\}", _RU[key]) for key in _KEYS}))

# ════════════════════════════════════════════════════════════════════════════
print("== §9 the release ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check("§9 the pin names this release or a later one",
      releases_at_least(EXPECTED_APP_VERSION, "1.13.4.3"), EXPECTED_APP_VERSION)
check("§9 the patch adds NO key (the parity baseline is the shipped figure)",
      all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      str({code: len(translation_keys(data)) for code, data in LANGS.items()}))
from version import VERSION_FORMAT  # noqa: E402 — the schema owner, read where it is used
check("§9 the project SCHEMA did not move (a patch is not a format change)",
      VERSION_FORMAT == "0.9", VERSION_FORMAT)

finish()
