# -*- coding: utf-8 -*-
"""The defects the closed 1.12 line still owed, and the code text they arrived with (v1.12.4.1).
§1 the SFTP channel leaves the GUI thread — the bounded open against a stub server that says NOTHING
(the reproduction), the `sftp.opening` moment of the History door and the refusal that keeps
`sftp.open_failed`; §2 a file the reader could not read is COPIED aside, never replaced by a
merge-write; §3 `known_hosts` declares itself a TOFU cache and behaves like one; §4 the lock sentence
of `storage/atomic.py`; §5 the comment budget at its goal; §6 the i18n and the release state.
Rule — `AGENTS.md` §4.4, §4.4.2, §4.8.1, §12.5; mechanism — `DOCUMENTATION.md` §14b, §16, §64, §71.
"""
import ast
import glob
import inspect
import json
import os
import socket
import struct
import sys
import threading
import time

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, clear_cfg, finish, load_i18n_langs, read_cfg,
                     releases_at_least, wait_until)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import paramiko  # noqa: E402

import i18n  # noqa: E402
import models.profile as PROFILE  # noqa: E402
import modules.bookmarks as BM  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import modules.sftp_open as SO  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_page as TP  # noqa: E402
import storage.atomic as ATOMIC  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.command_history import CommandHistoryPanel, CommandHistoryStore  # noqa: E402
from modules.terminal_page import TerminalSessionPage  # noqa: E402

import _comment_budget as CB  # noqa: E402

from _fakes import (FakeParamikoModule, FakeSSHClient, FakeSSHThread, FakeSftpClient,  # noqa: E402
                    FakeSftpFS)

ST.SSHTerminalThread = FakeSSHThread   # every session of this file runs on the fake thread
_LANGS = load_i18n_langs(ROOT)
_PAGES = []


def make_page(alias):
    """A session page over a server that needs no network (the fake SSH thread)."""
    page = TerminalSessionPage(ServerData(id=f"hv-{alias}", alias=alias, host="10.99.0.7",
                                          user="root"), None)
    _PAGES.append(page)
    app.processEvents()
    return page


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the SFTP channel leaves the GUI thread ==")
# ════════════════════════════════════════════════════════════════════════════

_REAL_PARAMIKO = SO.paramiko


class StubSessionChannel:
    """The session channel of the stub — a REAL socket read, so the bound is a real `socket.timeout`.

    `recv()` applies the timeout the opener declared (`Channel.settimeout` semantics: None = wait
    forever), exactly as paramiko's `Channel.recv()` does, which is what makes the reproduction whole.
    """

    def __init__(self, sock, timeout=None):
        self._sock = sock
        self.timeout = timeout
        self.timeouts = []
        self.subsystem = None
        self.closed = False
        self.sent = b""

    def settimeout(self, value):
        self.timeout = value
        self.timeouts.append(value)

    def invoke_subsystem(self, name):
        self.subsystem = name

    def get_name(self):
        """The channel id paramiko's own logger asks for (`[chan 0] …`)."""
        return 0

    def send(self, data):
        self.sent += bytes(data)
        return self._sock.send(data)

    def recv(self, nbytes):
        self._sock.settimeout(self.timeout)
        return self._sock.recv(nbytes)

    def close(self):
        self.closed = True
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass    # an endpoint that is already gone is closed enough
        try:
            self._sock.close()
        except OSError:
            pass


class SilentServer:
    """The stub server of the report's own reproduction: it ACCEPTS the channel, takes the `sftp`
    subsystem and then says NOTHING. `answer=True` writes the version packet a real server sends.

    It is also the `SSHClient` surface the page asks for a transport (`get_transport()`), so the ONE
    object stands for the whole endpoint of the reproduction.
    """

    def __init__(self, answer=False):
        self.client_end, self.server_end = socket.socketpair()
        self.answer = answer
        self.timeout = None
        self.channel = None

    def get_transport(self):
        return self

    def is_active(self):
        return True

    def open_session(self, timeout=None):
        self.timeout = timeout
        self.channel = StubSessionChannel(self.client_end, timeout)
        if self.answer:
            threading.Thread(target=self._answer, daemon=True).start()
        return self.channel

    def _answer(self):
        try:
            if not self.server_end.recv(9):    # the client's INIT packet (length + type + version)
                return
            self.server_end.sendall(struct.pack(">I", 5) + bytes([2]) + struct.pack(">I", 3))
        except OSError:
            pass    # the test closed the pair first — nothing is expected of a gone endpoint

    def close(self):
        for sock in (self.client_end, self.server_end):
            try:
                sock.close()
            except OSError:
                pass


class RealClientParamiko:
    """The `paramiko` attribute with the REAL client class — the reproduction needs the real read."""

    SFTPClient = paramiko.SFTPClient   # noqa: N815 — the paramiko name


check("§1 the opener is declared with a bound for BOTH stages paramiko leaves unbounded",
      SO.SFTP_OPEN_TIMEOUT_SEC == 20.0 and SO.SFTP_OPEN_SHUTDOWN_WAIT_MS == 2500)

# ── the defect itself, reproduced: without a bound the read never comes back ──────────────────
_unbounded = SilentServer()
_holder, _result = [], []
_thread_u = threading.Thread(
    target=lambda: _result.append(SO.open_sftp_session(_unbounded, timeout=None,
                                                       on_channel=_holder.append)), daemon=True)
_thread_u.start()
time.sleep(0.6)
check("§1 the UNBOUNDED shape is STILL waiting on the silent server (the reported defect)",
      _thread_u.is_alive() and _result == [], f"alive={_thread_u.is_alive()}")
check("§1 ...the channel is open and the stack sits in the version read",
      bool(_holder) and _holder[0].subsystem == "sftp" and _holder[0].timeouts == [None],
      f"holder={_holder}")
_holder[0].close()
_thread_u.join(3)
check("§1 ...and only closing that channel unblocks it (the window IS that thread)",
      not _thread_u.is_alive() and _result and _result[0][0] is None)
_unbounded.close()

# ── the shipped shape: ONE declared bound, cleared the moment the version answered ────────────
SO.paramiko = RealClientParamiko
_silent = SilentServer()
_t0 = time.monotonic()
_client_s, _chan_s, _detail_s = SO.open_sftp_session(_silent, timeout=0.4)
_elapsed = time.monotonic() - _t0
check("§1 the BOUNDED open answers inside its own bound, never in paramiko's 3600 s",
      _client_s is None and 0.3 <= _elapsed < 3.0, f"elapsed={_elapsed:.2f}")
check("§1 the channel request carried that bound (the transport's default is left alone)",
      _silent.timeout == 0.4, f"timeout={_silent.timeout}")
check("§1 ...and the version read was bounded by the same number",
      _silent.channel.timeouts == [0.4], f"timeouts={_silent.channel.timeouts}")
check("§1 the refusal carries the failure's own bounded text (never a traceback)",
      0 < len(_detail_s) <= SO.SFTP_OPEN_DETAIL_CHARS and "timed out" in _detail_s.lower(),
      f"detail={_detail_s!r}")
check("§1 ...and the half-open channel was closed by the opener",
      _silent.channel.closed is True)
_silent.close()

_answering = SilentServer(answer=True)
_client_a, _chan_a, _detail_a = SO.open_sftp_session(_answering, timeout=1.0)
check("§1 a server that DOES answer the version opens (the ordinary path)",
      _client_a is not None and _detail_a == "", f"detail={_detail_a!r}")
check("§1 the bound is CLEARED once the version answered — a transfer never inherits it",
      _answering.channel.timeouts == [1.0, None], f"timeouts={_answering.channel.timeouts}")
try:
    _client_a.close()
except Exception:   # noqa: BLE001 — the stub pair is torn down right after
    pass
_answering.close()

# ── the page: the four GUI slots start the open instead of performing it ──────────────────────
SO.paramiko = RealClientParamiko
SO.SFTP_OPEN_TIMEOUT_SEC = 0.5      # the declared bound, shortened for the scenario
_page = make_page("silent")
_msgs = []
_page.status_message.connect(lambda text, ms: _msgs.append(text))
_client_d = SilentServer()
_page.terminal_thread.client = _client_d
_tick_ran = []
QTimer.singleShot(0, lambda: _tick_ran.append(True))
_t0 = time.monotonic()
check("§1 _ensure_sftp() answers AT ONCE (the GUI thread never waits for the server)",
      _page._ensure_sftp() is False and time.monotonic() - _t0 < 0.2)
check("§1 ...the channel is a declared PENDING state, not a `no channel`",
      _page.sftp_channel_pending() is True)
app.processEvents()
check("§1 ...and the GUI thread is really free (a queued 0-timer ran while the server is silent)",
      _tick_ran == [True] and _page._sftp_worker is None)
wait_until(lambda: _page._sftp_handshake is None, timeout_ms=6000)
check("§1 the silent server cost ONE bounded wait and the refusal is the shipped sentence",
      any(str(m).startswith("Failed to open SFTP channel") for m in _msgs), f"msgs={_msgs}")
check("§1 ...and a refused page is not left `pending` (a retry is the next ask)",
      _page.sftp_channel_pending() is False and _page._sftp_worker is None)
_client_d.close()


class SlowParamiko(FakeParamikoModule):
    """The fake client class behind a deliberate answer delay — the `sftp.opening` window."""

    def SFTPClient(self, channel):   # noqa: N802 — the paramiko name
        time.sleep(0.4)
        return super().SFTPClient(channel)


_fs = FakeSftpFS()
_fs.add_file("/readme.txt", b"hello\n")
_page2 = make_page("opening")
_page2.terminal_thread.client = FakeSSHClient(FakeSftpClient(_fs))   # the ordinary wiring
SO.paramiko = SlowParamiko()                                        # ...behind a slow answer
_msgs2 = []
_page2.status_message.connect(lambda text, ms: _msgs2.append(text))
check("§1 the channel is asked for and is not there yet", _page2._ensure_sftp() is False
      and _page2.sftp_channel_pending() is True)
check("§1 ensure_sftp_worker() answers None and REPORTS the opening moment on the status bridge",
      _page2.ensure_sftp_worker() is None
      and _msgs2 and _msgs2[-1] == TP.get_translator()("sftp.opening"), f"msgs={_msgs2}")
_panel = CommandHistoryPanel(store=CommandHistoryStore("hv-opening"), session=_page2)
_panel_msgs = []
_panel.status_message.connect(lambda text, ms: _panel_msgs.append(text))
check("§1 the History door answers False — and does NOT say `server_no_channel` about a channel "
      "that is on its way",
      _panel.import_from_server() is False
      and TP.get_translator()("terminal.history.server_no_channel") not in _panel_msgs,
      f"msgs={_panel_msgs}")
wait_until(lambda: _page2._sftp_worker is not None, timeout_ms=6000)
check("§1 the answer really arrives afterwards: the next ask gets the worker",
      _page2.ensure_sftp_worker() is _page2._sftp_worker and _page2.sftp_channel_pending() is False)
_panel.deleteLater()
SO.paramiko = _REAL_PARAMIKO

# ── the page's teardown takes a channel that is still opening with it ─────────────────────────
_page3 = make_page("teardown")
_slow_client = SilentServer()
_page3.terminal_thread.client = _slow_client
SO.SFTP_OPEN_TIMEOUT_SEC = 5.0      # long enough that only the TEARDOWN can end this wait
SO.paramiko = RealClientParamiko
_page3._ensure_sftp()
check("§1 the third session is inside its open", _page3.sftp_channel_pending() is True)
wait_until(lambda: _slow_client.channel is not None, timeout_ms=5000)
_t0 = time.monotonic()
_page3.shutdown()
check("§1 shutdown() does not wait for the full bound — the handshake is dropped at once",
      time.monotonic() - _t0 < 2.0)
check("§1 ...and the channel it held was closed with it", _slow_client.channel.closed is True)
check("§1 ...the reference is gone", _page3._sftp_handshake is None)
_slow_client.close()
SO.SFTP_OPEN_TIMEOUT_SEC = 20.0
SO.paramiko = _REAL_PARAMIKO


# ════════════════════════════════════════════════════════════════════════════
print("== §2 a file the reader could not read is never replaced by a merge-write ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the family's THREE-state reader lives in the layer that merges",
      (ATOMIC.STORE_MISSING, ATOMIC.STORE_OK, ATOMIC.STORE_UNREADABLE)
      == ("missing", "ok", "unreadable") and callable(ATOMIC.read_json_state)
      and PROFILE.STORE_UNREADABLE == ATOMIC.STORE_UNREADABLE)

_bad_dir = os.path.join(WORK, "atomic_bad")
os.makedirs(_bad_dir, exist_ok=True)
_cfg = os.path.join(_bad_dir, "config.json")
with open(_cfg, "w", encoding="utf-8") as _fh:   # ONE extra comma — the report's own reproduction
    _fh.write('{\n  "ui_map_collapsed": true,\n  "keep_me": 1,\n}\n')
_state, _doc, _reason = ATOMIC.read_json_state(_cfg)
check("§2 the reader really calls that file UNREADABLE and names the reason",
      _state == ATOMIC.STORE_UNREADABLE and "invalid JSON at line" in _reason, f"reason={_reason}")
check("§2 the merge-write still answers True — the application never stops saving",
      ATOMIC.write_json_atomic(_cfg, {"language": "ru"}, merge=True) is True)
check("§2 ...and the published document is the merged write",
      ATOMIC.read_json(_cfg) == {"language": "ru"}, str(ATOMIC.read_json(_cfg)))
_copies = glob.glob(_cfg + ATOMIC.BAD_SUFFIX + "*")
check("§2 the bytes nobody could parse are KEPT beside the file (copy-then-write)",
      len(_copies) == 1 and "keep_me" in open(_copies[0], encoding="utf-8").read(),
      f"copies={_copies}")

_ok = os.path.join(_bad_dir, "ordinary.json")
ATOMIC.write_json_atomic(_ok, {"first": 1})
ATOMIC.write_json_atomic(_ok, {"second": 2}, merge=True)
check("§2 an ORDINARY merge copies nothing aside (the policy reacts to the unreadable state alone)",
      ATOMIC.read_json(_ok) == {"first": 1, "second": 2}
      and glob.glob(_ok + ATOMIC.BAD_SUFFIX + "*") == [])
_missing = os.path.join(_bad_dir, "fresh.json")
check("§2 a MISSING file is not an unreadable one",
      ATOMIC.write_json_atomic(_missing, {"a": 1}, merge=True) is True
      and ATOMIC.read_json_state(_missing)[0] == ATOMIC.STORE_OK
      and glob.glob(_missing + ATOMIC.BAD_SUFFIX + "*") == [])

# ── the two merge-writers of the report, end to end ───────────────────────────────────────────
clear_cfg()
_cfg_file = os.path.join(os.path.expanduser("~"), ".sshmap", "config.json")
os.makedirs(os.path.dirname(_cfg_file), exist_ok=True)
with open(_cfg_file, "w", encoding="utf-8") as _fh:
    _fh.write('{"language": "ru",,}')
check("§2 i18n.save_config() survives the file its own reader cannot parse",
      i18n.save_config({"ui_map_collapsed": True}) is True)
check("§2 ...the broken bytes were copied aside BEFORE the publish",
      len(glob.glob(_cfg_file + ATOMIC.BAD_SUFFIX + "*")) == 1)
check("§2 ...and the merged config really parses (the setting is saved, not lost)",
      read_cfg() == {"ui_map_collapsed": True}, str(read_cfg()))

_bm_path = os.path.join(_bad_dir, "bookmarks.json")
with open(_bm_path, "w", encoding="utf-8") as _fh:
    _fh.write('{"bookmarks": [], "foreign_key": "KEEP-ME",}')
_bm = BM.BookmarkStore(path=_bm_path)
check("§2 the bookmarks store saves over a file it cannot read",
      _bm.save([{"type": "url", "name": "Kept", "value": "https://kept.example.com"}]) is True
      and [e["name"] for e in _bm.load_urls()] == ["Kept"])
check("§2 ...and the foreign keys nobody could read are in the copy",
      any("foreign_key" in open(p, encoding="utf-8").read()
          for p in glob.glob(_bm_path + ATOMIC.BAD_SUFFIX + "*")))

# ── the profile store keeps its STRICTER refusal ──────────────────────────────────────────────
_prof_path = PROFILE._profiles_path()
with open(_prof_path, "w", encoding="utf-8") as _fh:
    _fh.write("[{,]")
_raised = None
try:
    PROFILE.save_profiles([])
except PROFILE.ProfileStoreError as _exc:
    _raised = _exc
check("§2 the profile store keeps its refusal (raised BEFORE the publish)",
      _raised is not None and _raised.path == _prof_path, f"raised={_raised!r}")
check("§2 ...nothing was written, nothing was copied aside, the file is byte-identical",
      open(_prof_path, encoding="utf-8").read() == "[{,]"
      and glob.glob(_prof_path + ATOMIC.BAD_SUFFIX + "*") == []
      and PROFILE.read_store()[0] == PROFILE.STORE_UNREADABLE)


# ════════════════════════════════════════════════════════════════════════════
print("== §3 known_hosts declares itself a TOFU cache (and behaves like one) ==")
# ════════════════════════════════════════════════════════════════════════════

_hkp_src = open(os.path.join(ROOT, "modules", "host_key_policy.py"), encoding="utf-8").read()
check("§3 the module declares the store for what it is — a TOFU cache, not a verbatim file",
      "TOFU CACHE, not a" in _hkp_src)
check("§3 ...and says a write keeps what paramiko parses and only that",
      "keeps what paramiko parses and only that" in _hkp_src)
check("§3 ...while an unreadable file is still never overwritten",
      "never overwritten" in _hkp_src and "_refuse_overwrite" in _hkp_src)

_hk = os.path.join(WORK, "tofu_known_hosts")
_key_a = paramiko.ECDSAKey.generate()
HKP.KnownHostsStore(path=_hk).pin("host-a", _key_a.get_name(), _key_a)
_entry_a = [ln for ln in open(_hk, encoding="utf-8").read().splitlines() if ln.strip()][0]
with open(_hk, "w", encoding="utf-8") as _fh:   # the "soft" garbage of the report
    _fh.write("# a comment a human wrote\n\n")
    _fh.write("host-old ssh-rsa AAAA\n")
    _fh.write(_entry_a + "\n")
_key_b = paramiko.ECDSAKey.generate()
check("§3 pin() really wrote the merged file",
      HKP.KnownHostsStore(path=_hk).pin("host-b", _key_b.get_name(), _key_b) is True)
_after = open(_hk, encoding="utf-8").read()
check("§3 a comment, a blank line and a two-field line do NOT survive a write",
      "# a comment" not in _after and "host-old" not in _after, _after[:80])
check("§3 ...while the valid entries do (the merge is real)",
      "host-a" in _after and "host-b" in _after)
_pinned = HKP.KnownHostsStore(path=_hk)
check("§3 the surviving file really loads as a store",
      sorted(_pinned.entries()) == ["host-a", "host-b"], str(sorted(_pinned.entries())))

_hard = os.path.join(WORK, "tofu_hard")
with open(_hard, "w", encoding="utf-8") as _fh:
    _fh.write("host-x ssh-rsa !!!not-base64!!!\n")
check("§3 the base64 line the report called HARD is the case the refusal protects",
      HKP.KnownHostsStore(path=_hard).pin("host-y", _key_a.get_name(), _key_a) is False
      and open(_hard, encoding="utf-8").read() == "host-x ssh-rsa !!!not-base64!!!\n")


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the lock sentence and §5 the comment budget at its goal ==")
# ════════════════════════════════════════════════════════════════════════════

_doc = ATOMIC.__doc__ or ""
check("§4 the module docstring names the `RLock` that `atomic_lock()` really returns",
      "`RLock`" in _doc and "a `threading.Lock` (this application" not in _doc)
_lock = ATOMIC.atomic_lock(os.path.join(_bad_dir, "lock.json"))
_lock.acquire()
_reentered = _lock.acquire(blocking=False)   # a plain Lock would deadlock the second acquire here
_lock.release()
if _reentered:
    _lock.release()
check("§4 ...and the accessor answers a RE-ENTRANT lock (a writer may re-enter it)", _reentered is True)

check("§5 every pin of the code-comment budget IS the rule itself (the goal state)",
      CB.MAX_HEADER_PIN == CB.HEADER_BUDGET_LINES == 12
      and CB.MAX_BLOCK_PIN == CB.BLOCK_BUDGET_LINES == 5
      and CB.HEADER_FILES_PIN == 0 and CB.BLOCK_FILES_PIN == 0
      and CB.BLOCK_LINES_PIN == 0 and CB.NARRATIVE_PIN == 0)
_measured = CB.measure(ROOT)
check("§5 ...and the tree really measures it (no header and no block over its budget)",
      _measured["header_files"] == 0 and _measured["block_files"] == 0
      and _measured["max_header"] <= 12 and _measured["max_block"] <= 5
      and _measured["narrative"] == 0, str({k: _measured[k] for k in
                                            ("max_header", "max_block", "narrative")}))
check("§5 the suite now asks for the STRICT form (the budget is a gate, not a report)",
      inspect.signature(CB.report).parameters["enforce"].default is True)


# ════════════════════════════════════════════════════════════════════════════
print("== §6 i18n and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check_i18n_parity(_LANGS)
check("§6 the ONE key of the release is present and non-empty in every language",
      EXPECTED_I18N_KEYS == 1117 + 1 + 4 + 3 + 2 + 8 + 9 + 18 + 4 + 13
      and all(str(data.get("sftp.opening") or "").strip() for data in _LANGS.values()),
      str({c: d.get("sftp.opening") for c, d in _LANGS.items()}))
check("§6 the pin counts the SHIPPED release",
      releases_at_least(EXPECTED_APP_VERSION, "1.13") and len(_LANGS) == 4,
      f"{EXPECTED_APP_VERSION} langs={sorted(_LANGS)}")
_tp_src = open(os.path.join(ROOT, "modules", "terminal_page.py"), encoding="utf-8").read()
_tp_sftp_src = open(os.path.join(ROOT, "modules", "terminal_page_sftp.py"), encoding="utf-8").read()
_opener_src = open(os.path.join(ROOT, "modules", "sftp_open.py"), encoding="utf-8").read()
check("§6 the new key is really USED by the shipped code (a key nobody reads is dead weight)",
      '"sftp.opening"' in _tp_src)
check("§6 the blocking open is GONE from the session page (no `client.open_sftp()` call is left)",
      "open_sftp()" not in _tp_sftp_src and "def open_sftp_session" in _opener_src)
check("§6 the opener follows the handshake pattern the plan named",
      'setObjectName("SftpOpenHandshake")' in _opener_src
      and "ready = Signal()" in _opener_src and "failed = Signal(str)" in _opener_src
      and "def shutdown(" in _opener_src and "def close(" in _opener_src
      and "register_orphan_sftp_open" in _opener_src)
check("§6 ...and the page owns ONE handshake (a second ask joins the open in flight)",
      "if self.sftp_channel_pending():" in _tp_sftp_src and "_sftp_handshake" in _tp_sftp_src)
check("§6 the file parses as the module it ships as (a guard over the text, not a memory of it)",
      isinstance(ast.parse(_opener_src), ast.Module)
      and json.dumps({"name": _LANGS["en"]["name"]}) != "")

# cleanup: every session of this file goes through the ONE teardown
for _page_x in _PAGES:
    try:
        _page_x.shutdown()
    except Exception:   # noqa: BLE001 — teardown robustness of the scenario
        pass
finish()
