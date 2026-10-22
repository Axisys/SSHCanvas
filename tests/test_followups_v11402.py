# -*- coding: utf-8 -*-
"""The silence that says why: the swallowed-error audit's first batch (v1.14rc2).
§1 the FIXED sites of the credential store, the probe's parsing, the transfer bodies and the three
neighbours, each driven with an injected failure and each owing ONE log line; §2 the marker rule and the
ratchet of `tests/_except_budget.py` (the family is marked, every reason is words, the pins agree with the
measurement); §3 the release state.
Rule — `AGENTS.md` §12.2; mechanism — `tests/_except_budget.py`.
"""
import contextlib
import logging
import os
import sys
import time
import types

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least,
                     translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + offscreen + sys.path (BEFORE any app import)

import keyring.errors  # noqa: E402  — the store's own "there is no backend" answer

import _except_budget as EB  # noqa: E402
import i18n as I18N  # noqa: E402
import services.credential_manager as CM  # noqa: E402
import services.exit_gate as GATE  # noqa: E402
import services.status_checker as SC  # noqa: E402
import storage.atomic as ATOMIC  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import modules.local_fs_worker as LFW  # noqa: E402
import modules.plugin_runner as PR  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402
import _fakes as Fakes  # noqa: E402
from version import APP_NAME, APP_VERSION  # noqa: E402

LANGS = load_i18n_langs(ROOT)

CM_LOG = "sshmap.services.credential_manager"
SC_LOG = "sshmap.services.status_checker"
SW_LOG = "sshmap.modules.sftp_worker"
LFW_LOG = "sshmap.modules.local_fs_worker"
HKP_LOG = "sshmap.modules.host_key_policy"
PR_LOG = "sshmap.modules.plugin_runner"
GATE_LOG = "sshmap.services.exit_gate"
ATOMIC_LOG = "sshmap.storage.atomic"


class _Sink(logging.Handler):
    """The ONE record sink: the messages the named logger REALLY emitted, at the file log's level."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())

    def text(self):
        return " | ".join(self.lines)


@contextlib.contextmanager
def _records(*names):
    """Capture the records of `names` at DEBUG — the level `setup_logging()` gives the file log."""
    sink = _Sink()
    attached = []
    for name in names:
        logger = logging.getLogger(name)
        attached.append((logger, logger.level))
        logger.setLevel(logging.DEBUG)
        logger.addHandler(sink)
    try:
        yield sink
    finally:
        for logger, level in attached:
            logger.removeHandler(sink)
            logger.setLevel(level)


def _raise(factory=RuntimeError):
    """A callable that raises — the injected failure every probe of this file uses."""
    def _boom(*_args, **_kwargs):
        raise factory("injected by the probe")
    return _boom


def _read(*parts) -> str:
    """The text of one repository file that SHIPS (the release checks read the real tree)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


# ════════════════════════════════════════════════════════════════════════════
print("== §1a the credential store: the four silences speak ==")
# ════════════════════════════════════════════════════════════════════════════

# The store answers "there is no backend" with NoKeyringError, NOT with "no such entry" — the difference
# is the whole answer a user needs ("no password is stored" vs "no password CAN be stored here"), and
# before this release both read as the SAME silence: None / False / True with no line anywhere.
class _NoStore:
    """A backend whose every door answers NoKeyringError."""

    def get_password(self, *_a):
        raise keyring.errors.NoKeyringError("no backend")

    def set_password(self, *_a):
        raise keyring.errors.NoKeyringError("no backend")

    def delete_password(self, *_a):
        raise keyring.errors.NoKeyringError("no backend")


def _broken_keyring():
    """A `keyring` package whose backend lookup raises — a headless / half-installed platform."""
    package = types.ModuleType("keyring")
    errors = types.ModuleType("keyring.errors")

    class NoKeyringError(Exception):
        """The store's own "there is no backend" answer."""

    errors.NoKeyringError = NoKeyringError
    package.errors = errors
    package.get_keyring = _raise(RuntimeError)
    return package, errors


_saved = {name: sys.modules.get(name) for name in ("keyring", "keyring.errors")}
_package, _errors = _broken_keyring()
sys.modules["keyring"] = _package
sys.modules["keyring.errors"] = _errors
try:
    with _records(CM_LOG) as sink:
        _manager = CM.CredentialManager()
finally:
    for _name, _module in _saved.items():
        if _module is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _module
check("§1a an unusable keyring NAMES the reason (an unavailable store is an answer)",
      _manager.is_available is False and "keyring" in sink.text().lower(),
      f"available={_manager.is_available} log={sink.text()!r}")

_manager = CM.CredentialManager()
_manager._backend_available = True
_manager._keyring_backend = _NoStore()

with _records(CM_LOG) as sink:
    _answer = _manager.load_password("abcdef12")
check("§1a a read against NO store says why it answered nothing (never an empty slot)",
      _answer is None and "store" in sink.text().lower(), f"answer={_answer!r} log={sink.text()!r}")

with _records(CM_LOG) as sink:
    _saved_ok = _manager.save_password("abcdef12", "hunter2")
check("§1a a write NO store accepted says nothing was saved",
      _saved_ok is False and "store" in sink.text().lower(), f"saved={_saved_ok} log={sink.text()!r}")

with _records(CM_LOG) as sink:
    _dropped = _manager.delete_password("abcdef12")
check("§1a a delete NO store answered still reports the emptiness it found",
      _dropped is True and "store" in sink.text().lower(), f"deleted={_dropped} log={sink.text()!r}")


# ════════════════════════════════════════════════════════════════════════════
print("== §1b the probe's parsing: a corrupt value and a crashed probe say so ==")
# ════════════════════════════════════════════════════════════════════════════

_real_load_config = I18N.load_config
I18N.load_config = _raise(RuntimeError)
try:
    with _records(SC_LOG) as sink:
        SC.get_status_settings()
finally:
    I18N.load_config = _real_load_config
check("§1b an unreadable config names itself instead of silently answering the defaults",
      "config" in sink.text().lower(), f"log={sink.text()!r}")

I18N.load_config = lambda: {"status_probe_timeout_sec": "not-a-number"}
try:
    with _records(SC_LOG) as sink:
        _settings = SC.get_status_settings()
finally:
    I18N.load_config = _real_load_config
check("§1b a corrupt config VALUE is named with the value and the default that answered",
      _settings["probe_timeout_sec"] == SC.PROBE_TIMEOUT_S and "not-a-number" in sink.text(),
      f"settings={_settings} log={sink.text()!r}")

with _records(SC_LOG) as sink:
    _targets = SC._build_targets([("sid-1", "example.test", "not-a-port")])
check("§1b a target with an unreadable port falls back to 22 AND names the server",
      _targets and _targets[0][2] == 22 and "sid-1" in sink.text(),
      f"targets={_targets} log={sink.text()!r}")

with _records(SC_LOG) as sink:
    _thread = SC._ProbeThread([], max_parallel="many")
check("§1b an unreadable max_parallel falls back to the default AND says so",
      _thread._max_parallel == SC.DEFAULT_MAX_PARALLEL and "max_parallel" in sink.text().lower(),
      f"parallel={_thread._max_parallel} log={sink.text()!r}")

_real_probe = SC.probe_ssh
SC.probe_ssh = _raise(RuntimeError)
try:
    _thread = SC._ProbeThread([("sid-1", "example.test", 22)])
    with _records(SC_LOG) as sink:
        _answer = _thread._probe_one("sid-1", "example.test", 22)
finally:
    SC.probe_ssh = _real_probe
check("§1b a probe that RAISES is reported offline and the crash is kept",
      _answer == (SC.STATUS_OFFLINE, "") and "probe" in sink.text().lower(),
      f"answer={_answer} log={sink.text()!r}")

_thread = SC._ProbeThread([("sid-1", "example.test", 22)], status_provider=_raise(RuntimeError))
with _records(SC_LOG) as sink:
    _answer = _thread._probe_one("sid-1", "example.test", 22)
check("§1b a status provider that raises is skipped and the skip is recorded",
      _answer == (SC.STATUS_OFFLINE, "") and "provider" in sink.text().lower(),
      f"answer={_answer} log={sink.text()!r}")

_thread = SC._ProbeThread([("sid-1", "example.test", 22)], status_provider=lambda *_a: 42)
with _records(SC_LOG) as sink:
    _answer = _thread._probe_one("sid-1", "example.test", 22)
check("§1b a provider answering a FOREIGN shape is recorded, not dropped in silence",
      _answer == (SC.STATUS_OFFLINE, "") and sink.lines, f"answer={_answer} log={sink.text()!r}")

_real_one = SC._ProbeThread._probe_one
SC._ProbeThread._probe_one = _raise(RuntimeError)
try:
    _thread = SC._ProbeThread([("sid-1", "example.test", 22)])
    _seen = []
    _thread.probed.connect(lambda sid, status: _seen.append((sid, status)))
    with _records(SC_LOG) as sink:
        _thread.run()
finally:
    SC._ProbeThread._probe_one = _real_one
check("§1b a probe FUTURE that raises is reported offline and named (a dead node, not a dead round)",
      _seen == [("sid-1", SC.STATUS_OFFLINE)] and "sid-1" in sink.text(),
      f"seen={_seen} log={sink.text()!r}")


# ════════════════════════════════════════════════════════════════════════════
print("== §1c the transfer bodies: a handle that will not close still says so ==")
# ════════════════════════════════════════════════════════════════════════════


class _Finished:
    """The worker's `finished` signal, as much of it as the orphan registry asks."""

    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)


class _Orphan:
    """A worker-shaped stub: the orphan registry's own seam."""

    def __init__(self):
        self.finished = _Finished()


_orphan = _Orphan()
SW.register_orphan_sftp_worker(_orphan)
_drop = _orphan.finished.slots[0]
_drop()
with _records(SW_LOG) as sink:
    _drop()
check("§1c a DOUBLE finished of the orphan registry is recorded, not swallowed",
      "orphan" in sink.text().lower(), f"log={sink.text()!r}")


class _V3Server:
    """A server WITHOUT posix-rename@openssh.com: the v3 fallback is the shipped path."""

    def __init__(self):
        self.renamed = []

    def posix_rename(self, source, target):
        raise IOError("no such extension")

    def rename(self, source, target):
        self.renamed.append((source, target))


_v3 = _V3Server()
_v3._sftp = _v3
with _records(SW_LOG) as sink:
    SW.SftpWorker._commit_upload(_v3, "/srv/x.part", "/srv/x")
check("§1c a refused posix-rename names the v3 fallback it took",
      _v3.renamed == [("/srv/x.part", "/srv/x")] and "posix" in sink.text().lower(),
      f"renamed={_v3.renamed} log={sink.text()!r}")


class _BadClose:
    """A remote handle whose close() fails — the state a half-dropped transport leaves behind."""

    def __init__(self, inner):
        self._inner = inner

    def read(self, size=-1):
        return self._inner.read(size)

    def prefetch(self, size=None):
        return self._inner.prefetch(size)

    def set_pipelined(self, pipelined):
        return self._inner.set_pipelined(pipelined)

    def write(self, data):
        return self._inner.write(data)

    def close(self):
        raise IOError("the channel is closed")


_fs = Fakes.FakeSftpFS()
_fs.files["/srv/report.txt"] = bytearray(b"hello sftp")
_client = Fakes.FakeSftpClient(_fs)
_real_open = _client.open
_client.open = lambda path, mode="rb": _BadClose(_real_open(path, mode))
_worker = SW.SftpWorker(_client)   # a QThread object; the test NEVER starts it
_local = os.path.join(WORK, "report.txt")
_task = SW._SftpTask(1, SW.KIND_DOWNLOAD, "report.txt", "/srv/report.txt", _local, total_size=10)
with _records(SW_LOG) as sink:
    _done = _worker._download_file(_task, "/srv/report.txt", _local, 10, 0,
                                   base_dir=WORK, local_name="report.txt")
check("§1c a remote handle that refuses close() is recorded and the download still lands",
      _done == 10 and os.path.isfile(_local) and "close" in sink.text().lower(),
      f"done={_done} landed={os.path.isfile(_local)} log={sink.text()!r}")

_read_task = SW._SftpTask(2, SW.KIND_READ, "/srv/report.txt", "/srv/report.txt",
                          total_size=10, max_bytes=SW.READ_CAP_NONE)
with _records(SW_LOG) as sink:
    _worker._do_read(_read_task)
check("§1c a read whose handle will not close still publishes its bytes and the failure",
      "close" in sink.text().lower(), f"log={sink.text()!r}")

_blocker = os.path.join(WORK, "blocker.txt")
with open(_blocker, "w", encoding="utf-8") as _fh:
    _fh.write("not a folder")
with _records(LFW_LOG) as sink:
    _made = LFW.LocalFsWorker._mkdir_quiet(os.path.join(_blocker, "sub"))
check("§1c a local directory the OS refuses is reported (its parent is a file, not a folder)",
      _made is False and "blocker.txt" in sink.text(), f"made={_made} log={sink.text()!r}")


# ════════════════════════════════════════════════════════════════════════════
print("== §1d the writer and the gate: a refusal is never a silent False ==")
# ════════════════════════════════════════════════════════════════════════════

with _records(ATOMIC_LOG) as sink:
    ATOMIC._remove(_blocker + os.sep + "sub")
check("§1d a provisional path the OS refuses to remove is recorded (the caller's answer stands)",
      "blocker.txt" in sink.text(), f"log={sink.text()!r}")

with _records(ATOMIC_LOG) as sink:
    _written = ATOMIC.write_json_atomic(os.path.join(_blocker, "x.json"), {"a": 1})
check("§1d a write the OS refuses answers False AND says what was refused",
      _written is False and "refused" in sink.text().lower(),
      f"written={_written} log={sink.text()!r}")


class _DeadDoor:
    """A thread whose stop door raises — the gate must try no further and must SAY so."""

    def stop(self):
        raise ValueError("the door died")


with _records(GATE_LOG) as sink:
    _door = GATE.stop_thread(_DeadDoor())
check("§1d a stop door that raises is named, and the gate keeps walking the other doors",
      _door == "" and "stop" in sink.text(), f"door={_door!r} log={sink.text()!r}")


class _DeadChannel:
    """A channel whose close() raises — the state a dropped transport leaves."""

    def close(self):
        raise IOError("the channel is gone")


with _records(PR_LOG) as sink:
    PR._close_quiet(_DeadChannel())
check("§1d closing a dead channel is recorded instead of vanishing (the plugin run's teardown)",
      "gone" in sink.text(), f"log={sink.text()!r}")


class _NoTimeoutStream:
    """A channel that cannot bound its own recv: settimeout raises, the loop must still end."""

    def __init__(self):
        self.channel = self

    def recv(self, _size):
        return b""

    def settimeout(self, _value):
        raise IOError("no timeout on this channel")

    def read(self, _size):
        return b""


with _records(PR_LOG) as sink:
    _text, _complete = PR._read_capped(_NoTimeoutStream(), limit=64,
                                       deadline=time.monotonic() + 5.0)
check("§1d a channel that cannot bound its recv is recorded, and the read still ends at EOF",
      (_text, _complete) == ("", True) and "timeout" in sink.text().lower(),
      f"answer={(_text, _complete)} log={sink.text()!r}")


class _DeadClosers:
    """The probe's transport and socket refuse close() — the key is already read, the rest is best effort."""

    def __init__(self, _sock=None):
        pass

    def start_client(self, timeout=None):
        return None

    def get_remote_server_key(self):
        return object()

    def close(self):
        raise IOError("the connection is gone")


_real_connect = HKP.socket.create_connection
_real_transport = HKP.paramiko.Transport
HKP.socket.create_connection = lambda *_a, **_k: _DeadClosers()
HKP.paramiko.Transport = _DeadClosers
try:
    with _records(HKP_LOG) as sink:
        _key, _error = HKP.read_server_host_key("example.test", 22)
finally:
    HKP.socket.create_connection = _real_connect
    HKP.paramiko.Transport = _real_transport
check("§1d a host-key probe whose connection will not close still answers, and logs the drop",
      _error == "" and "gone" in sink.text(), f"error={_error!r} log={sink.text()!r}")


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the marker rule and the ratchet (`tests/_except_budget.py`) ==")
# ════════════════════════════════════════════════════════════════════════════

_family = EB.measure(ROOT)

check("§2 every `pass` outside the Qt-teardown family carries the marker `# noqa: BLE001`",
      _family["unmarked"] == 0,
      f"unmarked={_family['unmarked']} of {_family['target']} — "
      f"{sorted(_family['unmarked_by_file'].items(), key=lambda kv: -kv[1])[:4]}")

check("§2 every marker says WHY (a bare `# noqa` is not a reason)",
      _family["reasonless"] == 0, f"reasonless={_family['reasonless']}")

check("§2 the five canonical reasons are declared once and every one is words",
      len(EB.REASONS) == 5 and all(r.strip() == r and r for r in EB.REASONS)
      and len(set(EB.REASONS)) == 5, repr(EB.REASONS))

check("§2 the pins and the measurement agree (a stale pin is pasted from `_except_budget.py`)",
      EB.pin_block(_family).splitlines()
      == [f"TARGET_PIN = {EB.TARGET_PIN}", f"UNMARKED_PIN = {EB.UNMARKED_PIN}",
          f"REASONLESS_PIN = {EB.REASONLESS_PIN}"],
      EB.pin_block(_family).replace("\n", " / "))

# The family predicate is what the whole gate rests on: a bare `except:` and a mixed tuple must be
# COUNTED (they can hide a logic error), only the RuntimeError/AttributeError pair is exempt.
import ast  # noqa: E402  — the predicate's own input, a parsed handler

_CASES = (("except RuntimeError:", True), ("except (RuntimeError, AttributeError):", True),
          ("except Exception:", False), ("except OSError:", False),
          ("except (RuntimeError, OSError):", False), ("except:", False))
_wrong = [source for source, expected in _CASES
          if EB.is_teardown_family(
              EB.pass_only_handlers(ast.parse(f"try:\n    x = 1\n{source}\n    pass\n"))[0])
          is not expected]
check("§2 the teardown family is the DECLARED PAIR only (a bare `except:` is counted)",
      not _wrong, f"wrong={_wrong}")


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check("§3 the audit adds no key to ANY language (the parity pin is untouched)",
      all(len(translation_keys(LANGS[c])) == EXPECTED_I18N_KEYS for c in LANGS),
      f"{EXPECTED_I18N_KEYS} / "
      + str({c: len(translation_keys(LANGS[c])) for c in sorted(LANGS)}))

check_release_state(ROOT)
check("§3 the pin names this line's release or a later one",
      releases_at_least(EXPECTED_APP_VERSION, "1.14"), EXPECTED_APP_VERSION)
check("§3 the project JSON schema did NOT move, and no dependency came with the audit",
      'VERSION_FORMAT = "0.9"' in _read("version.py")
      and "pytest" not in _read("requirements.txt").lower()
      and APP_VERSION == EXPECTED_APP_VERSION, APP_VERSION)
check("§3 the topical file is listed by the suite map (tests/INDEX.md regenerated)",
      "test_followups_v11402.py" in _read("tests", "INDEX.md"))

finish()
