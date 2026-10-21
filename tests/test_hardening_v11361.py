# -*- coding: utf-8 -*-
"""The two defects a review of the shipped `v1.13.6` confirmed, each one REPRODUCED and fixed (v1.13.6.1).
§1 the host key that retires its SIBLINGS: `KnownHostsStore.replace()` empties EVERY line of the name in
one publish (N140); §2 the destructive path no backend may resolve on its own: a blank or relative trash
target is refused before any OS call (N141); §3 the release.
Rule — `AGENTS.md` §4.4.2, §4.3.6; mechanism — `DOCUMENTATION.md` §14f, §16.
"""
import inspect
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import paramiko  # noqa: E402

import modules.host_key_policy as HKP  # noqa: E402
import modules.local_fs_worker as LOCAL  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402

LANGS = load_i18n_langs(ROOT)
STORE_PATH = os.path.join(WORK, "known_hosts")
TREE = os.path.join(WORK, "trash")
os.makedirs(TREE, exist_ok=True)

# ════════════════════════════════════════════════════════════════════════════
print("== §1 the key that retires its siblings (N140) ==")
# ════════════════════════════════════════════════════════════════════════════

STORE = HKP.KnownHostsStore(STORE_PATH)
HKP.set_store(STORE)
KEY_A = paramiko.ECDSAKey.generate()
try:
    KEY_B = paramiko.Ed25519Key.generate()
except Exception:  # noqa: BLE001 — an old paramiko without Ed25519: RSA is the second algorithm
    KEY_B = paramiko.RSAKey.generate(1024)
TYPE_A, TYPE_B = KEY_A.get_name(), KEY_B.get_name()
check("§1 fixture: two DIFFERENT algorithms", TYPE_A != TYPE_B, f"{TYPE_A} | {TYPE_B}")

# The REVERSED fixture (N140): the algorithm that gets REPLACED is written FIRST. paramiko's
# `HostKeys.__delitem__` drops ONE matching line per call, so a single `del` retires the sibling
# and leaves the replaced one behind — the order the shipped check never built.
STORE.pin("n140", TYPE_B, KEY_B)
STORE.pin("n140", TYPE_A, KEY_A)
STORE.pin("n140-neighbour", TYPE_A, KEY_A)
_host_lines = [line.split()[:2] for line in open(STORE_PATH, encoding="utf-8").read().splitlines()
               if line.split()[:1] == ["n140"]]
check("§1 fixture: the replaced algorithm is the FIRST line of its host",
      _host_lines == [["n140", TYPE_B], ["n140", TYPE_A]], str(_host_lines))

_orig_publish = HKP._atomic.publish_atomic
_publishes = []


def _count_publish(path, write_temp):
    _publishes.append(path)
    return _orig_publish(path, write_temp)


HKP._atomic.publish_atomic = _count_publish
try:
    _replaced = STORE.replace("n140", TYPE_B, KEY_B)
finally:
    HKP._atomic.publish_atomic = _orig_publish
check("§1 `replace()` retires EVERY keytype of the name, not the first line only",
      _replaced is True and set(STORE.lookup("n140") or {}) == {TYPE_B},
      str(sorted(STORE.lookup("n140") or {})))
_lines_after = open(STORE_PATH, encoding="utf-8").read().splitlines()
_host_after = [line for line in _lines_after if line.split()[:1] == ["n140"]]
check("§1 ...and the file keeps ONE line of that host, of the accepted algorithm only",
      len(_host_after) == 1 and TYPE_B in _host_after[0] and TYPE_A not in _host_after[0],
      str(_host_after))
check("§1 ...in ONE publish — the retirement and the add are the same read-merge-publish",
      _publishes == [STORE_PATH], str(_publishes))
check("§1 ...while a SECOND host keeps its own key (the loop retires a NAME, never a file)",
      set(STORE.lookup("n140-neighbour") or {}) == {TYPE_A}
      and any(line.split()[:1] == ["n140-neighbour"] for line in _lines_after),
      str(sorted(STORE.lookup("n140-neighbour") or {})))

_client = paramiko.SSHClient()
try:
    HKP.SshKnownHostsPolicy("n140", 22).apply_to_client(_client)
    _handed = dict(_client.get_host_keys().lookup("n140") or {})
finally:
    _client.close()
check("§1 the retired key cannot reach a client — `apply_to_client()` hands over the accepted one only",
      set(_handed) == {TYPE_B}, str(sorted(_handed)))

_mech = paramiko.HostKeys()
_mech.add("n140-mech", TYPE_B, KEY_B)
_mech.add("n140-mech", TYPE_A, KEY_A)
del _mech["n140-mech"]
check("§1 the loop's reason: paramiko's `HostKeys.__delitem__` drops ONE matching line per call",
      set(_mech.lookup("n140-mech") or {}) == {TYPE_A},
      str(sorted(_mech.lookup("n140-mech") or {})))

STORE.pin("n140-add", TYPE_A, KEY_A)
STORE.pin("n140-add", TYPE_B, KEY_B)
STORE.replace("n140-add", TYPE_B, KEY_B)
STORE.pin("n140-add", TYPE_A, KEY_A)
check("§1 `pin()` stays the ADDITIVE writer after a replacement (a second algorithm is legitimate)",
      set(STORE.lookup("n140-add") or {}) == {TYPE_A, TYPE_B},
      str(sorted(STORE.lookup("n140-add") or {})))

STORE.pin("n140-flow", TYPE_B, KEY_B)
STORE.pin("n140-flow", TYPE_A, KEY_A)
_orig_ask = HKP._ask.ask
HKP._ask.ask = lambda kind, **kwargs: True
try:
    _exc = paramiko.BadHostKeyException("n140-flow", KEY_B, KEY_A)
    _answered = HKP.resolve_changed_key(_exc, "n140-flow", 22)
finally:
    HKP._ask.ask = _orig_ask
check("§1 the changed-key flow replaces through the same writer and leaves ONE algorithm",
      _answered is True and set(STORE.lookup("n140-flow") or {}) == {TYPE_B},
      str(sorted(STORE.lookup("n140-flow") or {})))

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the trash that never resolves a path of its own (N141) ==")
# ════════════════════════════════════════════════════════════════════════════

_SENTINEL = os.path.join(TREE, "sentinel.txt")
with open(_SENTINEL, "wb") as handle:
    handle.write(b"alive\n")
_ABS = os.path.join(TREE, "victim.txt")
with open(_ABS, "wb") as handle:
    handle.write(b"bye\n")

check("§2 the guard is PURE and total: blank, whitespace, relative, None and `.` are refused",
      all(LOCAL.trash_path_problem(value) for value in ("", "   ", "file.txt", None, "."))
      and LOCAL.trash_path_problem(_ABS) == "", repr(LOCAL.trash_path_problem(_ABS)))

_orig_win32, _orig_gio, _orig_backend = LOCAL._trash_win32, LOCAL._trash_gio, LOCAL.trash_backend
_backends = []
_resolved = []
LOCAL._trash_win32 = lambda path: _backends.append((LOCAL.TRASH_BACKEND_WIN32, path))
LOCAL._trash_gio = lambda path: _backends.append((LOCAL.TRASH_BACKEND_GIO, path))
try:
    _raised = []
    try:
        LOCAL.trash_move("", LOCAL.TRASH_BACKEND_WIN32)
    except LOCAL._LocalRefusal as exc:
        _raised.append((exc.code, exc.error))
    try:
        LOCAL.trash_move("relative.txt", LOCAL.TRASH_BACKEND_GIO)
    except LOCAL._LocalRefusal as exc:
        _raised.append((exc.code, exc.error))
    check("§2 a blank OR relative path is refused with the ONE `trash_failed` code",
          [code for code, _detail in _raised] == [LOCAL.LOCAL_TRASH_FAILED] * 2,
          str(_raised))
    check("§2 ...BEFORE any backend runs — neither the win32 nor the gio branch is reached",
          _backends == [], str(_backends))
    check("§2 ...and the refusal carries its own reason (never an empty detail)",
          all(detail.strip() for _code, detail in _raised), str(_raised))

    LOCAL.trash_backend = lambda *a, **k: _resolved.append("asked") or LOCAL.TRASH_BACKEND_WIN32
    try:
        LOCAL.trash_move("", "")
    except LOCAL._LocalRefusal:
        pass
    check("§2 ...and the backend is not even RESOLVED for a path that can never be trashed",
          _resolved == [], str(_resolved))

    _scratch = os.path.join(WORK, "cwd-scratch")
    os.makedirs(_scratch, exist_ok=True)
    _marker = os.path.join(_scratch, "marker.txt")
    with open(_marker, "wb") as handle:
        handle.write(b"here\n")
    _cwd = os.getcwd()
    try:
        os.chdir(_scratch)
        try:
            LOCAL.trash_move("", LOCAL.TRASH_BACKEND_WIN32)
        except LOCAL._LocalRefusal:
            pass
        check("§2 the process's working directory SURVIVES a blank path (the defect's own probe)",
              os.path.isdir(_scratch) and os.path.isfile(_marker) and os.getcwd() == _scratch,
              f"cwd={os.getcwd()} exists={os.path.isdir(_scratch)}")
    finally:
        os.chdir(_cwd)

    _backends.clear()
    LOCAL.trash_move(_ABS, LOCAL.TRASH_BACKEND_WIN32)
    check("§2 an absolute path reaches the backend BYTE FOR BYTE (no re-resolution of its own)",
          _backends == [(LOCAL.TRASH_BACKEND_WIN32, _ABS)], str(_backends))

    _removed = []
    _orig_remove = os.remove
    os.remove = lambda *a, **k: _removed.append(a)
    try:
        try:
            LOCAL.trash_move("", LOCAL.TRASH_BACKEND_WIN32)
        except LOCAL._LocalRefusal:
            pass
    finally:
        os.remove = _orig_remove
    check("§2 a refusal never degrades into `os.remove()`", _removed == [], str(_removed))
finally:
    LOCAL._trash_win32, LOCAL._trash_gio, LOCAL.trash_backend = \
        _orig_win32, _orig_gio, _orig_backend

_win32_src = inspect.getsource(LOCAL._trash_win32)
check("§2 the Windows branch hands over the validated ABSOLUTE path — it never calls `abspath()`",
      'operation.pFrom = str(path) + "\\x00"' in _win32_src
      and "operation.pFrom = os.path.abspath" not in _win32_src)

# The PUBLIC queue door: the refusal is a task_error payload, never a silent no-op.
WORKER = LOCAL.LocalFsWorker(root=TREE)
_errors, _dones = [], []
WORKER.task_error.connect(lambda tid, kind, message: _errors.append((tid, kind, message)))
WORKER.task_done.connect(lambda tid, detail: _dones.append((tid, detail)))
WORKER.start()
_backends.clear()
LOCAL._trash_win32 = lambda path: _backends.append((LOCAL.TRASH_BACKEND_WIN32, path))
LOCAL._trash_gio = lambda path: _backends.append((LOCAL.TRASH_BACKEND_GIO, path))
try:
    _blank_id = WORKER.queue_trash("", LOCAL.TRASH_BACKEND_WIN32)
    _blank_seen = wait_for(lambda: any(tid == _blank_id for tid, _k, _m in _errors),
                           timeout_ms=5000)
    _blank_payload = next((message for tid, _k, message in _errors if tid == _blank_id), "")
    _blank_data = SW.parse_task_payload(_blank_payload) or {}
    check("§2 `queue_trash()` refuses a blank path with the SAME `trash_failed` payload",
          _blank_seen is True and _blank_data.get("code") == LOCAL.LOCAL_TRASH_FAILED,
          f"{_blank_seen} {_blank_payload!r}")
    check("§2 ...the task is the shipped `trash` kind and the backend never ran",
          any(kind == SW.KIND_TRASH for tid, kind, _m in _errors if tid == _blank_id)
          and _backends == [], f"{_backends}")
    _relative_id = WORKER.queue_trash("relative.txt", LOCAL.TRASH_BACKEND_GIO)
    _relative_seen = wait_for(lambda: any(tid == _relative_id for tid, _k, _m in _errors),
                              timeout_ms=5000)
    _relative_payload = next((message for tid, _k, message in _errors
                              if tid == _relative_id), "")
    _relative_data = SW.parse_task_payload(_relative_payload) or {}
    check("§2 ...and so does a relative one — on the gio branch of the guard too",
          _relative_seen is True and _relative_data.get("code") == LOCAL.LOCAL_TRASH_FAILED
          and _backends == [], f"{_relative_seen} {_relative_payload!r} {_backends}")
    _done_id = WORKER.queue_trash(_ABS, LOCAL.TRASH_BACKEND_WIN32)
    _done_seen = wait_for(lambda: any(tid == _done_id for tid, _detail in _dones),
                          timeout_ms=5000)
    check("§2 the ABSOLUTE row of a listing still moves through the trash task (`task_done`)",
          _done_seen is True and _backends == [(LOCAL.TRASH_BACKEND_WIN32, _ABS)],
          f"{_dones} {_backends}")
finally:
    WORKER.shutdown()
    LOCAL._trash_win32, LOCAL._trash_gio = _orig_win32, _orig_gio
check("§2 the refusal reuses the SHIPPED sentence `sftp.local.trash_failed` (no new i18n key)",
      LOCAL.LOCAL_ERROR_KEYS[LOCAL.LOCAL_TRASH_FAILED] == "sftp.local.trash_failed"
      and all(str(data.get("sftp.local.trash_failed") or "").strip() for data in LANGS.values()))
check("§2 the trash stays an OPERATION kind (the page stays silent, the pane reports)",
      LOCAL.KIND_TRASH in SW.OP_KINDS and LOCAL.KIND_TRASH not in SW.LOGGED_KINDS)

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the release ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_release_state(ROOT)
check("§3 this patch adds NO translation key (the parity pin does not move)",
      EXPECTED_I18N_KEYS == 1179, str(EXPECTED_I18N_KEYS))
check("§3 the JSON schema did NOT move (`VERSION_FORMAT` stays 0.9)",
      __import__("version").VERSION_FORMAT == "0.9")
check("§3 the pin names this patch's line", EXPECTED_APP_VERSION == "1.13.6.1",
      EXPECTED_APP_VERSION)
finish()
