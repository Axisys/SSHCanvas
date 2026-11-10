# -*- coding: utf-8 -*-
"""v1.15.1.1 — THE REVIEW OF THE SHIPPED `v1.15.1`: the nine defects, each with the probe that found it.
§1 the fingerprint spelling OpenSSH uses (`N182`); §2 the trust manager's PROBED row (`N183`); §3 the
ICMP stage's own ceiling (`N184`); §4 an unusable host name in the `status` round (`N185`); §5 a
non-finite `status_max_parallel` (`N186`); §6 a `config.json` that is not UTF-8 (`N187`); §7 `--json`
as an OPTION, never a value (`N188`); §8 the SSH library's records off the CLI's stderr (`N189`);
§9 the status checker's shutdown wait (`N190`); §10 the release pins.
Rule — `AGENTS.md` §4.4.2, §4.8.1, §4.35; mechanism — `DOCUMENTATION.md` §16, §19, §46, §71, §80.
Run: python tests/test_hardening_v11511.py
"""
import contextlib
import glob
import io
import json
import logging
import os
import socket
import sys
import threading
import time

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text, check,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least)

ROOT, WORK = bootstrap()  # HOME isolation + offscreen + sys.path (BEFORE any app import)

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import paramiko  # noqa: E402

import cli.args as ARGS  # noqa: E402
import cli.exec as EXEC  # noqa: E402
import cli.status as CLI_STATUS  # noqa: E402
import dialogs.host_key_dialog as HKD  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import services.diagnostics as DIAGNOSTICS  # noqa: E402
import services.exit_gate as EXIT_GATE  # noqa: E402
import services.reachability as REACH  # noqa: E402
import services.status_checker as SC  # noqa: E402
import services.status_probe as SP  # noqa: E402
import storage.app_config as APP_CONFIG  # noqa: E402
import version  # noqa: E402
from cli.hostkeys import CliHostKeyPolicy, normalize_fingerprint  # noqa: E402
from cli.main import main  # noqa: E402
from modules.host_key_policy import fingerprint  # noqa: E402

LANGS = load_i18n_langs(ROOT)

KEY_A = paramiko.ECDSAKey.generate()      # the pin that holds
KEY_B = paramiko.ECDSAKey.generate()      # the key a probe PRESENTS (another one of the same algorithm)
KEY_C = paramiko.ECDSAKey.generate()      # the pin of the OTHER row
FP_A = fingerprint(KEY_A)
KEYTYPE = KEY_A.get_name()


def run(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout text, stderr text)`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def raw_cfg(text):
    """A config.json written BYTE for byte — the hand-edited (and hostile) shapes `write_cfg()` cannot."""
    path = APP_CONFIG.CONFIG_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def statuses():
    """The three probe figures of the current config file (`get_status_settings()`, the ONE reader)."""
    return SP.get_status_settings()


# ════════════════════════════════════════════════════════════════════════════
print("== §1 N182 — the fingerprint is the OpenSSH spelling (no base64 padding) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 `fingerprint()` carries no base64 padding and equals paramiko's OWN `PKey.fingerprint`",
      not FP_A.endswith("=") and FP_A == KEY_A.fingerprint, f"{FP_A} vs {KEY_A.fingerprint}")
check("§1 ...it is the 43-character base64 body of a 32-byte SHA-256 digest (44 padded is the defect)",
      FP_A.startswith("SHA256:") and len(FP_A) == len("SHA256:") + 43, str(len(FP_A)))
check("§1 the ONE row model answers the same spelling, so the manager's table moves with the report",
      HKP.host_key_rows({"h": {KEYTYPE: KEY_A}}) == [
          {"host": "h", "keytype": KEYTYPE, "fingerprint": FP_A}],
      str(HKP.host_key_rows({"h": {KEYTYPE: KEY_A}})))

check("§1 a value an operator pastes from `ssh-keygen -lf` is normalised to the canonical spelling",
      normalize_fingerprint(FP_A) == FP_A
      and normalize_fingerprint(" " + FP_A + " ") == FP_A
      and normalize_fingerprint("sha256:" + FP_A[7:]) == FP_A, normalize_fingerprint(" " + FP_A + " "))
check("§1 ...and the PADDED spelling an older record carries normalises onto the same string",
      normalize_fingerprint(FP_A + "=") == FP_A
      and normalize_fingerprint("SHA256:" + FP_A[7:] + "=") == FP_A,
      normalize_fingerprint(FP_A + "="))
check("§1 a bare base64 body is taken as the body, padding and all — and \"\" is \"none named\"",
      normalize_fingerprint(FP_A[7:] + "=") == FP_A[7:]
      and normalize_fingerprint("") == "" and normalize_fingerprint(None) == "",
      normalize_fingerprint(FP_A[7:] + "="))


class _TempStore:
    """A temp `known_hosts` installed as THE store — `HKP.set_store()` is the ONE seam."""

    def __init__(self, name):
        self.store = HKP.KnownHostsStore(os.path.join(str(WORK), name))
        self.previous = None

    def __enter__(self):
        self.previous = HKP.get_store()
        HKP.set_store(self.store)
        return self.store

    def __exit__(self, *_exc):
        HKP.set_store(self.previous)
        return False


def refusal(policy, key):
    """The `HostKeyRejected` sentence a policy answers for one key (`""` — it accepted)."""
    try:
        policy.missing_host_key(None, "h", key)
    except HKP.HostKeyRejected as exc:
        return str(exc)
    return ""


with _TempStore("known_hosts_v11511_policy") as _store:
    _pin = CliHostKeyPolicy("h", 22, expected=FP_A)
    _pin_sentence = refusal(_pin, KEY_A)
    _pinned = _store.lookup("h") or {}
    check("§1 `--host-key` (an `ssh-keygen -lf` value) ACCEPTS the key it names — the probe's own "
          "refusal is gone", _pin_sentence == "" and _pin.pinned and KEYTYPE in _pinned,
          f"{_pin_sentence!r} pinned={_pin.pinned} {sorted(_pinned)}")
    _padded = CliHostKeyPolicy("h", 22, expected=FP_A + "=")
    check("§1 ...and the padded spelling of the same value accepts it too (both on input)",
          refusal(_padded, KEY_A) == "", refusal(_padded, KEY_A))
    _mismatch = CliHostKeyPolicy("h", 22, expected=FP_A)
    check("§1 a DIFFERENT key is still refused, and the sentence prints the canonical pair unpadded",
          bool(refusal(_mismatch, KEY_B)) and FP_A in refusal(_mismatch, KEY_B)
          and fingerprint(KEY_B) in refusal(_mismatch, KEY_B),
          refusal(_mismatch, KEY_B))


class _Transport:
    def __init__(self, key):
        self.key = key

    def get_remote_server_key(self):
        return self.key


class _Presented:
    def __init__(self, key):
        self.transport = _Transport(key)

    def get_transport(self):
        return self.transport


def presented_refusal(key, expected):
    """The `HostKeyRejected` sentence of `verify_presented_key()` (`""` — it passed)."""
    try:
        EXEC.verify_presented_key(_Presented(key), expected)
    except HKP.HostKeyRejected as exc:
        return str(exc)
    return ""


check("§1 the post-handshake check reads the same spelling: the standard value PASSES",
      presented_refusal(KEY_A, FP_A) == "" and presented_refusal(KEY_A, FP_A + "=") == "",
      presented_refusal(KEY_A, FP_A))
check("§1 ...and a foreign key still refuses through it",
      bool(presented_refusal(KEY_B, FP_A)) and "not the" in presented_refusal(KEY_B, FP_A),
      presented_refusal(KEY_B, FP_A))

# ════════════════════════════════════════════════════════════════════════════
print("== §2 N183 — the trust manager replaces the key of the row it PROBED ==")
# ════════════════════════════════════════════════════════════════════════════


class _ManagerStore:
    """The manager dialog's store seam: the pins of two hosts, and every operation recorded."""

    path = "<known_hosts>"
    load_failed = False

    def __init__(self):
        self.pins = {HKP.entry_name_for("127.0.0.1", 2201): {KEYTYPE: KEY_A},
                     HKP.entry_name_for("127.0.0.1", 2202): {KEYTYPE: KEY_C}}
        self.replaced = []

    def entries(self):
        return self.pins

    def replace(self, host, keytype, key):
        self.replaced.append((host, keytype))
        return True

    def remove(self, host, keytype):
        return True


class _StubProbe(QObject):
    """The dialog's probe seam: `start()` does nothing, the test emits the answer it chooses."""

    probed = Signal(object, str)
    finished = Signal()

    def __init__(self, host, port, parent=None):
        super().__init__(parent)
        self.host, self.port = host, port
        self.started = False
        self.deleted = False

    def start(self):
        self.started = True

    def isRunning(self):
        return False

    def deleteLater(self):
        self.deleted = True


_probes = []
_REAL_PROBE = HKD._HostKeyProbe
HKD._HostKeyProbe = lambda host, port, parent=None: (_probes.append(_StubProbe(host, port, parent)),
                                                    _probes[-1])[1]
_real_question = QMessageBox.question
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
try:
    _store = _ManagerStore()
    _dialog = HKD.KnownHostsManagerDialog(store=_store)
    check("§2 the table lists both pins in the row model's own order (2201 first)",
          [_row["host"] for _row in _dialog.rows]
          == [HKP.entry_name_for("127.0.0.1", 2201), HKP.entry_name_for("127.0.0.1", 2202)],
          str([_row["host"] for _row in _dialog.rows]))
    _dialog.table.setCurrentCell(0, 0)
    _dialog._on_replace()
    _probe = _probes[-1]
    check("§2 the click starts ONE probe, for the SELECTED row's endpoint, and blocks the table",
          _probe.started and _probe.host == "127.0.0.1" and _probe.port == 2201
          and not _dialog.table.isEnabled() and not _dialog.btn_replace.isEnabled(),
          f"{_probe.host}:{_probe.port} table={_dialog.table.isEnabled()}")
    _dialog.table.setCurrentCell(1, 0)
    check("§2 a selection moved WHILE the probe runs leaves `Replace`/`Delete` disabled",
          not _dialog.btn_replace.isEnabled() and not _dialog.btn_delete.isEnabled(),
          f"replace={_dialog.btn_replace.isEnabled()}")
    _dialog._on_replace()
    check("§2 ...and a second click cannot start a second probe over the first thread",
          len(_probes) == 1, str(len(_probes)))
    _probe.probed.emit(KEY_B, "")
    check("§2 the answer replaces the pin of the PROBED row — never the row selected when it lands",
          _store.replaced == [(HKP.entry_name_for("127.0.0.1", 2201), KEYTYPE)],
          str(_store.replaced))
    _probe.finished.emit()
    check("§2 the finished thread is released and the table is usable again",
          _probe.deleted and _dialog._probe is None and _dialog._probe_row is None
          and _dialog.table.isEnabled(), f"deleted={_probe.deleted}")
    _store.replaced.clear()
    _probe.probed.emit(KEY_B, "")
    check("§2 an answer that belongs to no probe changes NOTHING (no question, no store write)",
          _store.replaced == [], str(_store.replaced))
    _dialog.deleteLater()
finally:
    QMessageBox.question = _real_question
    HKD._HostKeyProbe = _REAL_PROBE

# ════════════════════════════════════════════════════════════════════════════
print("== §3 N184 — the ICMP stage spends its OWN ceiling, not the caller's budget ==")
# ════════════════════════════════════════════════════════════════════════════

_pinged, _connected = [], []
_report = REACH.diagnose_reachability(
    "127.0.0.1", 22, 300.0,
    connector=lambda host, port, budget: (_connected.append(budget), (None, "[Errno 61] refused"))[1],
    pinger=lambda host, budget: (_pinged.append(budget), False)[1])
check("§3 `--timeout 300` still governs the TCP stage (the flag is not dropped anywhere)",
      _connected == [300.0], str(_connected))
check("§3 ...and the ICMP stage is capped by `PING_BUDGET_S`, never 300 s",
      _pinged == [REACH.PING_BUDGET_S] and REACH.PING_BUDGET_S == 4.0, str(_pinged))
check("§3 the report keeps its verdict and its ping evidence",
      _report.kind == REACH.KIND_TCP_REFUSED and _report.ping == "failed",
      f"{_report.kind} {_report.ping}")
_small = []
REACH.diagnose_reachability("127.0.0.1", 22, 1.0,
                            connector=lambda h, p, t: (None, "refused"),
                            pinger=lambda h, b: (_small.append(b), False)[1])
check("§3 a caller who asks for LESS keeps the smaller budget (the cap is a ceiling, not a floor)",
      _small == [1.0], str(_small))

# ════════════════════════════════════════════════════════════════════════════
print("== §4 N185 — one unusable host name is offline, never the whole report ==")
# ════════════════════════════════════════════════════════════════════════════


def probed(host, port=22, timeout=0.2):
    """`probe_ssh()`'s answer — the exception name when it escapes (which is the defect)."""
    try:
        return SP.probe_ssh(host, port, timeout)
    except Exception as exc:  # noqa: BLE001 — the check reports the escape it reproduces
        return f"raised {type(exc).__name__}"


check("§4 a DNS label over 63 characters answers `offline` (the idna `UnicodeError` is caught)",
      probed("x" * 64) == SP.STATUS_OFFLINE, probed("x" * 64))
check("§4 ...and so does a name carrying a NUL — an unusable ADDRESS is not a crashed round",
      probed("bad\x00name") == SP.STATUS_OFFLINE, probed("bad\x00name"))


class _Node:
    """The CLI's node seam: the four fields `set_servers` / `probe_ssh` read."""

    def __init__(self, host, port=22):
        self.id, self.alias, self.host, self.ssh_port = host or "id", "alias", host, port


_cli_rows = CLI_STATUS.probe_nodes([_Node("x" * 64), _Node("127.0.0.1", "not-a-port")], 0.2)
check("§4 the `status` round answers ONE record per node, in order, and never raises",
      [status for _node, status in _cli_rows] == [SP.STATUS_OFFLINE, SP.STATUS_OFFLINE],
      str([status for _node, status in _cli_rows]))
check("§4 ...the per-node guard covers a record whose PORT is not a number (the probe itself would raise)",
      CLI_STATUS._probe(_Node("127.0.0.1", "not-a-port"), 0.2) == SP.STATUS_OFFLINE)

# ════════════════════════════════════════════════════════════════════════════
print("== §5 N186 — a non-finite `status_max_parallel` answers the DEFAULT ==")
# ════════════════════════════════════════════════════════════════════════════

_default = SP.DEFAULT_MAX_PARALLEL
for _payload in ('{"status_max_parallel": 1e999}', '{"status_max_parallel": Infinity}',
                 '{"status_max_parallel": NaN}', '{"status_max_parallel": -Infinity}'):
    raw_cfg(_payload)
    try:
        _settings = statuses()
        _answer = _settings["max_parallel"]
    except Exception as exc:  # noqa: BLE001 — a raise IS the reproduced defect
        _answer = f"raised {type(exc).__name__}"
    check(f"§5 {_payload} → {_default} (the finite gate, never `int(inf)`)",
          _answer == _default, str(_answer))
for _payload, _expected in (('{"status_max_parallel": 32}', 32),
                            ('{"status_max_parallel": "48"}', 48),
                            ('{"status_max_parallel": true}', _default),
                            ('{"status_max_parallel": "abc"}', _default),
                            ('{"status_max_parallel": 9999}', SP.MAX_PARALLEL_LIMIT)):
    raw_cfg(_payload)
    check(f"§5 {_payload} → {_expected} (the shipped clamp still reads an ordinary value)",
          statuses()["max_parallel"] == _expected, str(statuses()["max_parallel"]))
raw_cfg('{"status_probe_timeout_sec": 1e999}')
check("§5 the second finite float of the same reader answers its default too",
      statuses()["probe_timeout_sec"] == SP.PROBE_TIMEOUT_S,
      str(statuses()["probe_timeout_sec"]))
raw_cfg("{}")
check("§5 a MISSING config keeps the shipped defaults",
      statuses() == {"interval_sec": SP.DEFAULT_INTERVAL_SEC, "manual": False,
                     "probe_timeout_sec": SP.PROBE_TIMEOUT_S, "max_parallel": _default},
      str(statuses()))

# ════════════════════════════════════════════════════════════════════════════
print("== §6 N187 — a `config.json` that is not UTF-8 is `{}`, never an exception ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
os.makedirs(os.path.dirname(APP_CONFIG.CONFIG_FILE), exist_ok=True)
with open(APP_CONFIG.CONFIG_FILE, "wb") as handle:
    handle.write(b'{"language": "\xff\xfe"}')
try:
    _loaded = APP_CONFIG.load_config()
except Exception as exc:  # noqa: BLE001 — the escaped `UnicodeDecodeError` is the defect
    _loaded = f"raised {type(exc).__name__}"
check("§6 the non-UTF-8 store answers `{}` (every reader already assumes it)",
      _loaded == {}, str(_loaded))
check("§6 ...and the file is still there, byte for byte (a READ never destroys a file)",
      open(APP_CONFIG.CONFIG_FILE, "rb").read() == b'{"language": "\xff\xfe"}')
_repaired = APP_CONFIG.save_config({"ui_font_size": 11})
_kept = glob.glob(APP_CONFIG.CONFIG_FILE + ".bad-*")
check("§6 a MERGE over that file copies it aside first and publishes the new document",
      _repaired and len(_kept) == 1 and APP_CONFIG.load_config().get("ui_font_size") == 11
      and open(_kept[0], "rb").read() == b'{"language": "\xff\xfe"}',
      f"saved={_repaired} copies={_kept}")
clear_cfg(*_kept)

# ════════════════════════════════════════════════════════════════════════════
print("== §7 N188 — `--json` is an OPTION, never a value or a verb's tail ==")
# ════════════════════════════════════════════════════════════════════════════

_grammar = (
    (["--json"], True),
    (["--json", "inventory"], True),
    (["inventory", "--json"], False),          # the verb's own tail
    (["--project", "--json"], False),          # `--json` consumed as the project VALUE
    (["--timeout", "--json"], False),          # ...or as the timeout's
    (["--project=x", "--json"], True),         # the `=` spelling leaves it a real option
    (["--bad", "--", "--json"], False),        # after `--` everything is the verb's
    (["--", "--json"], False),
    (["inventory"], False),
    ([], False),
)
check("§7 the PURE reader walks the grammar (values, `--` and the verb boundary)",
      all(ARGS.json_requested(line) is expected for line, expected in _grammar),
      str([(line, ARGS.json_requested(line)) for line, _e in _grammar if ARGS.json_requested(line)]))
_accepted = [(line, ARGS.parse_argv(line)) for line in
             (["--json", "inventory"], ["--project", "p.json", "--json", "status"], [], ["inventory"])]
check("§7 ...and it agrees with the ONE parse on every line the grammar ACCEPTS",
      all(invocation.json == ARGS.json_requested(line) for line, invocation in _accepted),
      str([(line, invocation.json) for line, invocation in _accepted]))

_code, _out, _err = run(["--project", "--json", "--timeout", "0"])
check("§7 a failure whose `--json` was an option VALUE answers the TEXT sentence",
      _code == 1 and not _out.strip().startswith("{") and "--timeout takes" in _err,
      f"{_code} out={_out!r} err={_err!r}")
_code, _out, _err = run(["--bad", "--", "--json"])
check("§7 ...and so does a `--json` written after `--`",
      _code == 1 and not _out.strip().startswith("{") and "--bad" in _err,
      f"{_code} out={_out!r} err={_err!r}")
_code, _out, _err = run(["--json", "--bad"])
_document = json.loads(_out) if _out.strip().startswith("{") else {}
check("§7 a REAL `--json` option still selects the failure envelope",
      _code == 1 and _document.get("ok") is False
      and _document.get("error", {}).get("kind") == "usage" and _err.strip() == "",
      f"{_code} out={_out!r} err={_err!r}")

# ════════════════════════════════════════════════════════════════════════════
print("== §8 N189 — the SSH library's records never reach the CLI's stderr ==")
# ════════════════════════════════════════════════════════════════════════════

_library = logging.getLogger("paramiko")
check("§8 the surface installs a `NullHandler` on the library's logger and stops its propagation",
      any(isinstance(handler, logging.NullHandler) for handler in _library.handlers)
      and _library.propagate is False, f"{_library.handlers} propagate={_library.propagate}")

_server = socket.socket()
_server.bind(("127.0.0.1", 0))
_server.listen(1)
_PORT = _server.getsockname()[1]


def _serve_silently():
    """Accept ONE connection and send NOTHING — the handshake that makes the library log a line."""
    try:
        connection, _address = _server.accept()
        try:
            time.sleep(3)
        finally:
            connection.close()
    except OSError:
        pass


threading.Thread(target=_serve_silently, daemon=True).start()
_previous_store = HKP.get_store()
_probe_store = HKP.KnownHostsStore(os.path.join(str(WORK), "known_hosts_v11511"))
_probe_store.replace(HKP.entry_name_for("127.0.0.1", _PORT), KEYTYPE, KEY_A)
HKP.set_store(_probe_store)
try:
    _code, _out, _err = run(["--timeout", "1", "hostkey", "verify"])
finally:
    HKP.set_store(_previous_store)
    _server.close()
check("§8 the run prints its OWN report — one row per pin, the stored fingerprint unpadded",
      _code == 4 and _out.startswith(HKP.entry_name_for("127.0.0.1", _PORT)) and FP_A in _out
      and "\tunreachable\t" in _out, f"{_code} out={_out!r}")
check("§8 ...and the library's raw line is NOT on the diagnostics channel",
      _err.strip() == "" and "Exception (client)" not in _err, f"err={_err!r}")

# ════════════════════════════════════════════════════════════════════════════
print("== §9 N190 — the shutdown waits for the IN-FLIGHT batch, not the whole map ==")
# ════════════════════════════════════════════════════════════════════════════


class _FakeThread(QObject):
    """The checker's thread seam: it records every `wait()` and answers what the test asks."""

    finished = Signal()

    def __init__(self, ends=True, parent=None):
        super().__init__(parent)
        self.waits, self._ends = [], ends
        self.detached = False

    def isRunning(self):
        return True

    def wait(self, ms=0):
        self.waits.append(int(ms))
        return self._ends

    def setParent(self, parent):
        self.detached = parent is None
        super().setParent(parent)


_map = SC.StatusChecker(probe_timeout=3.0, max_parallel=16)
_map._targets = [(f"id{index}", "host", 22) for index in range(256)]
_busy = _FakeThread()
_map._thread = _busy
_map.stop()
check("§9 256 targets still buy ONE probe timeout + 2 s (the in-flight batch alone)",
      _busy.waits == [int(3.0 * 1000) + 2000], str(_busy.waits))
check("§9 ...never the old `ceil(N / max_parallel) × timeout` margin (the 50 s freeze)",
      bool(_busy.waits) and _busy.waits[0] < 50000, str(_busy.waits))
check("§9 the round is really cancelled before the wait (the checker's own flag)",
      _map._cancel.is_set() and _map._enabled is False and not _map._timer.isActive())

_late = _FakeThread(ends=False, parent=_map)
_late_map = SC.StatusChecker(probe_timeout=1.0, max_parallel=16)
_late_map._thread = _late
_late_map.stop()
check("\u00a79 a thread that outlives the wait goes to the SHIPPED orphan registry",
      _late.waits == [int(1.0 * 1000) + 2000]
      and _late in DIAGNOSTICS._orphan_threads
      and _late in EXIT_GATE.registered_threads(), str(_late.waits))
check("\u00a79 ...DETACHED from its parent first (a parented QThread dies with it) and self-cleaning",
      _late.detached and _late.parent() is None)
_late.finished.emit()
check("\u00a79 ...so the gate never joins a round that ended, and the registry drops it by itself",
      _late not in EXIT_GATE.registered_threads()
      and _late not in DIAGNOSTICS._orphan_threads)

print("== §10 the release — no new key, no schema move, the pins ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_release_state(ROOT)
check(f"§10 the patch adds NO key — the parity stays {EXPECTED_I18N_KEYS}",
      EXPECTED_I18N_KEYS == 1256, str(EXPECTED_I18N_KEYS))
check("§10 the pin names this release's line",
      releases_at_least(EXPECTED_APP_VERSION, "1.15.1.1"), EXPECTED_APP_VERSION)
check("§10 the project schema did NOT move", version.VERSION_FORMAT == "0.9", version.VERSION_FORMAT)
_family = changelog_family_text(ROOT)
check("§10 the changelog family carries the release",
      not _family or "## v1.15.1.1" in _family)

finish()
