# -*- coding: utf-8 -*-
"""The six defects a review of the shipped `v1.13.4` confirmed, each one REPRODUCED and fixed (v1.13.4.1).
§1 the credential keeps its ENDPOINT — the dialog's own fields are its scope, and a scope that cannot be
written is a False (N119); §2 a replaced host key takes every other algorithm of the name with it (N120);
§3 a handshake that outlives the pane's wait is never `deleteLater()`-ed while running (N121); §4 the exit
gate joins every registered thread against ONE budget (N122); §5 the probe round ends with the window
(N123); §6 the info batch shares ONE deadline instead of a wait per collector (N124); §7 the release.
Rule — `AGENTS.md` §4.4, §4.8; mechanism — `DOCUMENTATION.md` §16, §19, §46, §64.
"""
import inspect
import os
import subprocess
import sys
import threading
import time

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, clear_cfg, finish, load_i18n_langs, releases_at_least,
                     wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication(sys.argv)

import paramiko  # noqa: E402

import i18n  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import modules.sftp_elevated as ELEVATION  # noqa: E402
import modules.sftp_pane_elevated as PANE  # noqa: E402
import services.credential_manager as CM  # noqa: E402
import services.diagnostics as DG  # noqa: E402
import services.exit_gate as GATE  # noqa: E402
import services.info_batch as IB  # noqa: E402
import services.system_info_collector as SIC  # noqa: E402
import ui.main_window_ssh as MWSSH  # noqa: E402
from dialogs import ssh_connect_dialog as SCD  # noqa: E402
from models.server import ServerData  # noqa: E402

LANGS = load_i18n_langs(ROOT)
WORK_TREE = os.path.join(WORK, "patch")
os.makedirs(WORK_TREE, exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the credential keeps its ENDPOINT: the dialog's own fields are the scope ==")
# ════════════════════════════════════════════════════════════════════════════

class _FakeBackend:
    """An in-memory stand-in for wincred — the suite never touches the real credential store."""

    def __init__(self, refuse_scope=False):
        self.store = {}
        self.refuse_scope = refuse_scope

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, value):
        if self.refuse_scope and str(username).endswith(CM.SCOPE_SUFFIX):
            raise RuntimeError("the endpoint entry was refused")
        self.store[(service, username)] = value

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


def _cm(backend=None):
    manager = CM.CredentialManager.__new__(CM.CredentialManager)
    manager._keyring_backend = backend or _FakeBackend()
    manager._backend_available = True
    return manager


_c = _cm()
check("§1 a save WITHOUT a scope still stores the secret (the shipped unscoped callers)",
      _c.save_password("n119a", "S3cret!") is True and _c.load_password("n119a") == "S3cret!")
check("§1 ...and it is NOT bound: the next scope it meets is adopted (the defect's precondition)",
      _c.stored_scope("n119a") == "" and _c.load_password("n119a", scope="root@prod-db:22") == "S3cret!"
      and _c.stored_scope("n119a") == "root@prod-db:22")

_scoped = _cm()
_scope_a = CM.endpoint_scope("root", "prod-db", 22)
check("§1 a SCOPED save answers True and stores the endpoint",
      _scoped.save_password("n119b", "S3cret!", scope=_scope_a) is True
      and _scoped.stored_scope("n119b") == "root@prod-db:22")
check("§1 a credential saved for endpoint A is NOT handed to endpoint B",
      _scoped.load_password("n119b", scope=CM.endpoint_scope("root", "evil-host", 22)) is None
      and _scoped.load_password("n119b", scope=_scope_a) == "S3cret!")

_refused = _cm(_FakeBackend(refuse_scope=True))
check("§1 a scope write that FAILS answers False (never a silent success)",
      _refused.save_password("n119c", "S3cret!", scope=_scope_a) is False)
check("§1 ...and the unbound secret is ROLLED BACK — nothing can be adopted by another endpoint",
      _refused.load_password("n119c") is None
      and _refused.load_password("n119c", scope=CM.endpoint_scope("root", "evil-host", 22)) is None
      and _refused.stored_scope("n119c") == "")

# The dialog: `_on_worker_success()` saves through the DIALOG'S OWN FIELDS.
_calls = {"saved": [], "warned": []}
_orig_cm = CM.get_credential_manager
_orig_warning = SCD.QMessageBox.warning


class _RecordingManager:
    def __init__(self, answer=True):
        self.answer = answer

    def save_password(self, server_id, password, scope=""):
        _calls["saved"].append((server_id, password, scope))
        return self.answer


SCD.QMessageBox.warning = staticmethod(lambda *a, **k: _calls["warned"].append(a))
try:
    CM.get_credential_manager = lambda: _RecordingManager(True)
    _dlg = SCD.SSHConnectDialog(
        ServerData(id="n119dlg", alias="prod-db", host="prod-db", user="root", ssh_port=22))
    _dlg.user_edit.setText("deploy")
    _dlg.port_edit.setValue(2222)
    _dlg.password_edit.setText("FromUi!")
    _dlg._ssh_worker = None
    _dlg._on_worker_success("connected")
    app.processEvents()
    check("§1 the connect dialog saves with the scope of ITS OWN fields (user/host/port)",
          _calls["saved"] == [("n119dlg", "FromUi!", "deploy@prod-db:2222")], str(_calls["saved"]))
    check("§1 a saved credential is not reported as a failure",
          _calls["warned"] == [], str(_calls["warned"]))

    _calls["saved"].clear()
    _calls["warned"].clear()
    CM.get_credential_manager = lambda: _RecordingManager(False)
    _dlg2 = SCD.SSHConnectDialog(ServerData(id="n119fail", alias="db", host="db", user="root"))
    _dlg2.password_edit.setText("Nope!")
    _dlg2._on_worker_success("connected")
    app.processEvents()
    _expected = i18n.t("msg.credentials_save_failed", alias="db")
    check("§1 a refused save is REPORTED to the user with the shipped sentence",
          len(_calls["warned"]) == 1 and _calls["warned"][0][-1] == _expected,
          f"{_calls['warned']} != {_expected!r}")
    check("§1 the dialog passes the scope even when the store will refuse it",
          _calls["saved"] and _calls["saved"][0][2] == "root@db:22", str(_calls["saved"]))
finally:
    CM.get_credential_manager = _orig_cm
    SCD.QMessageBox.warning = _orig_warning


# ════════════════════════════════════════════════════════════════════════════
print("== §2 a replaced host key takes every other algorithm of the name with it ==")
# ════════════════════════════════════════════════════════════════════════════

STORE_PATH = os.path.join(WORK_TREE, "known_hosts")
_store = HKP.KnownHostsStore(STORE_PATH)
HKP.set_store(_store)
KEY_ECDSA = paramiko.ECDSAKey.generate()
try:
    KEY_SECOND = paramiko.Ed25519Key.generate()
except Exception:  # noqa: BLE001 — an old paramiko without Ed25519: RSA is the second algorithm
    KEY_SECOND = paramiko.RSAKey.generate(1024)
OLD_TYPE, NEW_TYPE = KEY_ECDSA.get_name(), KEY_SECOND.get_name()
check("§2 fixture: two DIFFERENT algorithms", OLD_TYPE != NEW_TYPE, f"{OLD_TYPE} | {NEW_TYPE}")

# The REVERSED fixture (N140): the algorithm that gets REPLACED is written FIRST. paramiko's
# `HostKeys.__delitem__` drops ONE matching line per call, so this order is the one the shipped
# check never built — with the old single `del` the sibling below survived the replacement.
check("§2 the first connection pins its own algorithm",
      _store.pin("h-replace", NEW_TYPE, KEY_SECOND) is True
      and set(_store.lookup("h-replace") or {}) == {NEW_TYPE},
      str(sorted(_store.lookup("h-replace") or {})))
check("§2 `pin()` stays ADDITIVE — a second algorithm of the same name is a legitimate entry",
      _store.pin("h-replace", OLD_TYPE, KEY_ECDSA) is True
      and set(_store.lookup("h-replace") or {}) == {OLD_TYPE, NEW_TYPE},
      str(sorted(_store.lookup("h-replace") or {})))
check("§2 the fixture really puts the REPLACED algorithm on the FIRST line",
      open(STORE_PATH, encoding="utf-8").read().splitlines()[0].split()[1] == NEW_TYPE,
      open(STORE_PATH, encoding="utf-8").read().splitlines()[:2])
_store.pin("h-neighbour", OLD_TYPE, KEY_ECDSA)
check("§2 ...and a SECOND host keeps a key of its own before the replacement",
      set(_store.lookup("h-neighbour") or {}) == {OLD_TYPE},
      str(sorted(_store.lookup("h-neighbour") or {})))
check("§2 `replace()` writes the ONE new key and RETIRES every other keytype in the same publish",
      _store.replace("h-replace", NEW_TYPE, KEY_SECOND) is True
      and set(_store.lookup("h-replace") or {}) == {NEW_TYPE},
      str(sorted(_store.lookup("h-replace") or {})))
_written = open(STORE_PATH, encoding="utf-8").read()
_replace_lines = [ln for ln in _written.splitlines() if ln.split()[:1] == ["h-replace"]]
check("§2 ...and the retired key is really gone from the FILE (one publish, not a second write)",
      len(_replace_lines) == 1 and NEW_TYPE in _replace_lines[0]
      and OLD_TYPE not in _replace_lines[0], str(_replace_lines))
check("§2 ...while the SECOND host's own key survives the replacement untouched",
      set(_store.lookup("h-neighbour") or {}) == {OLD_TYPE}
      and any(ln.split()[:1] == ["h-neighbour"] for ln in _written.splitlines()),
      str(sorted(_store.lookup("h-neighbour") or {})))

# The CONNECT flow: the changed-key answer goes through the same writer.
_store.pin("h-changed", OLD_TYPE, KEY_ECDSA)
_orig_ask = HKP._ask.ask
_answers = []


def _ask_changed(kind, **kwargs):
    _answers.append(kind)
    return True


HKP._ask.ask = _ask_changed
try:
    _exc = paramiko.BadHostKeyException("h-changed", KEY_SECOND, KEY_ECDSA)
    _replaced = HKP.resolve_changed_key(_exc, "h-changed", 22)
finally:
    HKP._ask.ask = _orig_ask
check("§2 the connect flow asks the changed-key question and answers True",
      _replaced is True and _answers and _answers[0] == HKP._ask.KIND_CHANGED_KEY, str(_answers))
check("§2 ...and the store holds ONLY the key the user accepted",
      set(_store.lookup("h-changed") or {}) == {NEW_TYPE},
      str(sorted(_store.lookup("h-changed") or {})))

_dialog_src = open(os.path.join(ROOT, "dialogs", "host_key_dialog.py"), encoding="utf-8").read()
check("§2 the MANAGER's replace goes through the same writer (no second replacement path)",
      "self.store.replace(" in _dialog_src and "self.store.pin(" not in _dialog_src)
check("§2 the connect flow has no `pin` fallback left (ONE writer for a replacement)",
      "get_store().replace(" in inspect.getsource(HKP.resolve_changed_key))


# ════════════════════════════════════════════════════════════════════════════
print("== §3 a handshake that outlives the pane's wait is not deleted while running ==")
# ════════════════════════════════════════════════════════════════════════════

class _StuckHandshake(QThread):
    """The REAL handshake's API over a `run()` that hangs until it is released (N121's trigger)."""

    ready = Signal(object, str)
    failed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StuckHandshake")
        self._release = threading.Event()
        self.deleted = False
        self.closed = False
        self.registered = 0

    def run(self):
        self._release.wait(10)

    def close(self):
        self.closed = True

    def shutdown(self, wait_ms=100):
        if self.isRunning():
            self.wait(wait_ms)
        if self.isRunning():
            self.registered += 1
            ELEVATION.register_orphan_handshake(self)

    def deleteLater(self):  # noqa: N802 — the Qt name; a live thread never reaches the C++ delete
        self.deleted = True

    def release(self):
        self._release.set()


class _Pane(PANE.SftpPaneElevatedMixin, QWidget):
    """The elevated mixin over a bare QObject host — the pane's state, no container."""

    def __init__(self):
        QWidget.__init__(self)
        self._handshake = None
        self._elevation_pending = True


clear_cfg()
ELEVATION._orphan_handshakes.clear()
_pane = _Pane()
_stuck = _StuckHandshake(parent=_pane)
_pane._handshake = _stuck
_stuck.start()
check("§3 fixture: the handshake really runs", _stuck.isRunning() is True)

_pane._drop_handshake()
check("§3 the pane forgets the handshake", _pane._handshake is None)
check("§3 a RUNNING handshake is NOT `deleteLater()`-ed (the qFatal trigger is gone)",
      _stuck.deleted is False and _stuck.isRunning() is True,
      f"deleted={_stuck.deleted} running={_stuck.isRunning()}")
check("§3 ...it is owned by the orphan registry instead",
      _stuck in ELEVATION._orphan_handshakes and _stuck.registered == 1,
      f"registry={len(ELEVATION._orphan_handshakes)} registered={_stuck.registered}")
check("§3 the pane closed what the handshake had opened", _stuck.closed is True)

# The queued DeferredDelete that aborts a process on a live QThread — processed here, nothing may die.
QCoreApplication.sendPostedEvents(None, int(QEvent.Type.DeferredDelete))
for _ in range(6):
    app.processEvents()
    time.sleep(0.05)
check("§3 an event-loop turn does not destroy the live thread (the process survives)",
      _stuck.isRunning() is True and _stuck.deleted is False)

_stuck.release()
check("§3 the registry self-cleans when the handshake finally ends",
      _stuck.wait(5000) is True
      and wait_for(lambda: _stuck not in ELEVATION._orphan_handshakes, timeout_ms=3000),
      f"registry={len(ELEVATION._orphan_handshakes)} running={_stuck.isRunning()}")

_finished = _StuckHandshake()
_finished.release()
_finished.start()
_finished.wait(5000)
_pane._handshake = _finished
_pane._drop_handshake()
check("§3 a FINISHED handshake takes the ordinary `deleteLater()` path (nothing is leaked)",
      _finished.deleted is True and _finished not in ELEVATION._orphan_handshakes)
check("§3 the guard is in the teardown itself (one predicate, the shipped method)",
      "if handshake.isRunning():" in inspect.getsource(PANE.SftpPaneElevatedMixin._drop_handshake))


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the exit gate: one aboutToQuit gate joins every registered thread ==")
# ════════════════════════════════════════════════════════════════════════════

_GATE_PROBE = r'''
import sys, threading
sys.path.insert(0, sys.argv[1])
from PySide6.QtCore import QCoreApplication, QThread, QTimer

class SlowThread(QThread):
    def __init__(self):
        super().__init__()
        self.setObjectName("GateProbe")
        self._stop = threading.Event()
    def stop(self):
        self._stop.set()
    def run(self):
        self._stop.wait(10)

app = QCoreApplication(sys.argv[:1])
from services import diagnostics as DG
if sys.argv[2] == "gate":
    from services.exit_gate import install_exit_gate
    install_exit_gate(app)
t = SlowThread()
DG._orphan_threads.append(t)   # the ONE registry table's own module attribute
t.start()
QTimer.singleShot(80, app.quit)
app.exec()
print("probe-after-loop running=%s" % t.isRunning())
'''


def _run_probe(name, mode):
    path = os.path.join(WORK_TREE, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(_GATE_PROBE)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run([sys.executable, path, ROOT, mode], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=90)


check("§4 fixture: no orphan thread is registered in this process",
      GATE.registered_threads() == [], str(len(GATE.registered_threads())))

_gated = _run_probe("gate_probe.py", "gate")
check("§4 the gate joins a registry-held thread at `aboutToQuit` and the process exits 0",
      _gated.returncode == 0 and "probe-after-loop" in _gated.stdout,
      f"exit={_gated.returncode} out={_gated.stdout[-200:]} err={_gated.stderr[-400:]}")
check("§4 ...and Qt never destroys a running QThread (no qFatal line)",
      "Destroyed while thread" not in (_gated.stdout + _gated.stderr),
      (_gated.stdout + _gated.stderr)[-400:])

_ungated = _run_probe("gate_probe_nogate.py", "nogate")
check("§4 the SAME probe WITHOUT the gate aborts — the defect is real, not theoretical",
      _ungated.returncode != 0, f"exit={_ungated.returncode}")
check("§4 ...with Qt's own message naming the destroyed thread",
      "Destroyed while thread" in (_ungated.stdout + _ungated.stderr),
      (_ungated.stdout + _ungated.stderr)[-300:])


class _Door(QThread):
    """A thread whose doors are RECORDED — the gate must ask its own door, not invent one."""

    def __init__(self):
        super().__init__()
        self.setObjectName("DoorProbe")
        self.asked = []
        self._release = threading.Event()

    def run(self):
        self._release.wait(10)

    def stop(self):
        self.asked.append("stop")
        self._release.set()

    def cancel(self):
        self.asked.append("cancel")

    def close(self):
        self.asked.append("close")


def _register(thread):
    DG._orphan_threads.append(thread)
    thread.start()
    return thread


_d = _register(_Door())
check("§4 `stop_thread()` asks the thread's OWN `stop()` first",
      GATE.stop_thread(_d) == "stop" and _d.asked == ["stop"], str(_d.asked))
_d.wait(3000)


class _CancelOnly(QThread):
    """A thread without `stop()` — the gate must find `cancel()`."""

    def __init__(self):
        super().__init__()
        self.asked = []
        self._release = threading.Event()

    def run(self):
        self._release.wait(10)

    def cancel(self):
        self.asked.append("cancel")
        self._release.set()


_ca = _register(_CancelOnly())
check("§4 a thread without `stop()` is asked its `cancel()`",
      GATE.stop_thread(_ca) == "cancel" and _ca.asked == ["cancel"], str(_ca.asked))
_ca.wait(3000)
DG._orphan_threads.remove(_d)
DG._orphan_threads.remove(_ca)

_dup = _Door()
DG._orphan_threads.append(_dup)
DG._orphan_threads.append(_dup)   # the SAME object in the SAME registry twice
_dup.start()
_seen = GATE.registered_threads()
check("§4 one thread registered TWICE is joined ONCE (a deduped snapshot)",
      [id(t) for t in _seen].count(id(_dup)) == 1, str(len(_seen)))
_report = GATE.join_all(budget_ms=800)
check("§4 `join_all()` stops the thread through its own door and JOINS it",
      _report["joined"] >= 1 and not _dup.isRunning() and _report["stopped"] == ["DoorProbe"],
      str(_report))
DG._orphan_threads.remove(_dup)

_main_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("§4 the entry point arms the gate on the application object (both launch modes)",
      "install_exit_gate" in _main_src and "aboutToQuit" in inspect.getsource(GATE.install_exit_gate))
check("§4 the budget is DECLARED in one place",
      GATE.EXIT_GATE_BUDGET_MS == 3000 and GATE.EXIT_GATE_TERMINATE_WAIT_MS == 500)
check("§4 the gate knows EVERY orphan registry the tree declares",
      set(name for name, _attr in GATE.REGISTRY_OWNERS) == {
          "services.diagnostics", "modules.ssh_terminal", "modules.sftp_worker",
          "modules.sftp_open", "modules.sftp_elevated", "modules.local_fs_worker"},
      str(sorted(name for name, _attr in GATE.REGISTRY_OWNERS)))
_registry_attrs_ok = all(
    hasattr(sys.modules.get(name) or __import__(name, fromlist=["x"]), attr)
    for name, attr in GATE.REGISTRY_OWNERS)
check("§4 every registry name in that table is the module's REAL attribute", _registry_attrs_ok)


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the probe round ends with the window (N123) ==")
# ════════════════════════════════════════════════════════════════════════════

from ui import main_window as MW  # noqa: E402

clear_cfg()
_win = MW.MainWindow()
_checker = _win._status_checker
check("§5 fixture: the window owns a StatusChecker", _checker is not None)
_checker.start()
check("§5 the checker armed its timer", _checker._timer.isActive() is True)
_win._shutdown_background_threads()
check("§5 the close path STOPS the checker (an explicit call — the timer is off)",
      _checker._timer.isActive() is False and not _checker.is_busy,
      f"timer={_checker._timer.isActive()} busy={_checker.is_busy}")


class _StubChecker:
    """Counts its `shutdown()` calls — the proof that the close path REACHES the checker."""

    def __init__(self):
        self.calls = 0

    def shutdown(self):
        self.calls += 1


_stub = _StubChecker()
_win._status_checker = _stub
_win._shutdown_background_threads()   # idempotent teardown, as a second close path would be
check("§5 the close path calls `_shutdown_status_checker()` explicitly (not via `destroyed`)",
      _stub.calls == 1, str(_stub.calls))
_win_src = open(os.path.join(ROOT, "ui", "main_window.py"), encoding="utf-8").read()
check("§5 the dead `destroyed` connection is GONE (PySide6 6.11 never invoked it)",
      "destroyed.connect(self._shutdown_status_checker)" not in _win_src)
check("§5 the call lives in `_shutdown_background_threads()` (the ONE close-path teardown)",
      "self._shutdown_status_checker()" in inspect.getsource(MW.MainWindow._shutdown_background_threads))
_win.close()


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the info batch shares ONE deadline (N124) ==")
# ════════════════════════════════════════════════════════════════════════════

class _StuckCollector(QObject):
    """A collector that refuses to end: `stop()` signals at once, `wait()` sleeps the budget."""

    info_ready = Signal(str, dict)
    info_failed = Signal(str, str)
    finished = Signal()

    def __init__(self, data):
        super().__init__()
        self.data = data
        self.stops = 0
        self.waits = []

    def start(self):
        pass

    def isRunning(self):  # noqa: N802 — the Qt name
        return True

    def stop(self):
        self.stops += 1

    def wait(self, ms):
        self.waits.append(int(ms))
        time.sleep(int(ms) / 1000.0)
        return False


def _data(sid):
    return ServerData(id=sid, alias=sid, host="192.0.2.1", user="root")


_batch = IB.InfoBatch(collector_factory=lambda d: _StuckCollector(d), max_parallel=4)
_batch.start([(f"c{i}", f"c{i}", _data(f"c{i}")) for i in range(4)])
_running = list(_batch._running.values())
check("§6 fixture: four collectors run at once", len(_running) == 4, str(len(_running)))
_t0 = time.monotonic()
_survivors = _batch.shutdown(wait_ms=300)
_elapsed = time.monotonic() - _t0
check("§6 the shutdown asks every collector's `stop()` (a SIGNAL, never the wait)",
      [c.stops for c in _running] == [1, 1, 1, 1], str([c.stops for c in _running]))
check("§6 the ONE deadline covers EVERY collector: four stuck collectors cost ONE budget",
      _elapsed < 1.0, f"{_elapsed:.3f}s")
check("§6 the waits SHARE the budget — no collector gets its own full slice",
      sum(sum(c.waits) for c in _running) <= 400,
      str([c.waits for c in _running]))
check("§6 the collectors that outlived it are REPORTED, not waited on again",
      len(_survivors) == 4, str(len(_survivors or [])))
check("§6 the batch is closed (nothing claims to run)", _batch.is_running is False)

# The collector's own `stop()` no longer blocks the caller for its channel timeout.
_collector = SIC.SystemInfoCollector(_data("stop-probe"))
_t1 = time.monotonic()
_collector.stop()
_stop_elapsed = time.monotonic() - _t1
check("§6 `SystemInfoCollector.stop()` returns at once (a signal, no 12 s wait)",
      _stop_elapsed < 0.5, f"{_stop_elapsed:.3f}s")
check("§6 ...and the WAIT is declared by the caller (`INFO_BATCH_SHUTDOWN_WAIT_MS`)",
      MWSSH.INFO_BATCH_SHUTDOWN_WAIT_MS == IB.SHUTDOWN_WAIT_MS
      and "wait_ms=INFO_BATCH_SHUTDOWN_WAIT_MS" in inspect.getsource(MWSSH.SshMixin._shutdown_info_batch)
      and "wait_ms" in inspect.signature(IB.InfoBatch.shutdown).parameters, str(IB.SHUTDOWN_WAIT_MS))


# ════════════════════════════════════════════════════════════════════════════
print("== §7 the release: no new key, no schema move, the four-component pin ==")
# ════════════════════════════════════════════════════════════════════════════

for _key in ("msg.credentials_save_failed", "ssh.credential_scope_mismatch", "hostkey.manager_replaced",
             "sftp.elevated.working", "status.info_batch_done"):
    check(f"§7 {_key} still carries a sentence in every language",
          all(str(data.get(_key) or "").strip() for data in LANGS.values()),
          str({code: bool(data.get(_key)) for code, data in LANGS.items()}))
check_i18n_parity(LANGS)
check_release_state(ROOT)
check("§7 the i18n pin is UNCHANGED — this patch adds no translation key",
      EXPECTED_I18N_KEYS == 1162 + 4 + 13 + 1 + 1 + 12 + 3, str(EXPECTED_I18N_KEYS))
check("§7 the pin names this patch's line", releases_at_least(EXPECTED_APP_VERSION, "1.13.4"),
      EXPECTED_APP_VERSION)
import version as VERSION_MODULE  # noqa: E402
check("§7 the JSON schema did NOT move (VERSION_FORMAT stays 0.9)",
      VERSION_MODULE.VERSION_FORMAT == "0.9", VERSION_MODULE.VERSION_FORMAT)
check("§7 no new dependency (requirements.txt keeps its four)",
      len([ln for ln in open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8")
           if ln.strip() and not ln.startswith("#")]) == 4)

finish()
