# -*- coding: utf-8 -*-
"""The v1.12.2.1 hardening patch: the five ledger entries whose failure is a WRITE or a TRUST decision.
tags: slow

Offscreen, no network. One section per ledger entry, each check reproducing the PROBE of the entry
against the shipped code: the tree download's destination (N98), the project reader (N104), the host
key an unanswered question must not pin (N100, decision R14(a)), the command guard's input bound
(N99) and the client a failed connect must close (N101).
Contract — `AGENTS.md` §4.4.3, §4.4.2, §4.30; `DOCUMENTATION.md` §16, §74.

Run: python tests/test_hardening_v11221.py   (from the project root) or python tests/run_all.py"""

import os
import sys
import threading
import time

from _common import (bootstrap, check, finish, wait_for, load_i18n_langs, check_i18n_parity,
                     check_release_state, EXPECTED_APP_VERSION, releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import paramiko  # noqa: E402

import modules.command_guard as CG  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import modules.interactive_ask as ASK  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402
import modules.ssh_connect as SCON  # noqa: E402
import storage.project as PRJ  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

print("== release pins ==")
check_release_state(ROOT)
check("the release this file describes is v1.12.2.1",
      releases_at_least(EXPECTED_APP_VERSION, "1.12.2.1"), EXPECTED_APP_VERSION)


# ════════════════════════════════════════════════════════════
# 1. N98 — the destination the tree download really WRITES
# ════════════════════════════════════════════════════════════
print("== 1. N98: the download destination ==")

_SIBLING = os.path.join(os.path.dirname(WORK.rstrip("\\/")), "n98_beside")
os.makedirs(_SIBLING, exist_ok=True)
check("N98 the belt judges the path it is GIVEN (the same path the caller opens)",
      SW.local_containment_problem(os.path.join(WORK, "..", "n98_beside", "pwned.txt"), WORK) == "outside"
      and SW.local_containment_problem(os.path.join(WORK, "sub", "pwned.txt"), WORK) is None)
check("N98 a path that resolves ONTO the folder is outside it too (the file would land beside it)",
      SW.local_containment_problem(os.path.join(WORK, "sub", ".."), WORK) == "outside"
      and SW.local_containment_problem(os.path.join(WORK, "sub", "..", "."), WORK) == "outside")
check("N98 a name with a separator is NOT a name-rule failure by itself",
      SW.local_name_problem("..\\..\\pwned.txt", windows=False) is None
      and SW.local_name_problem("a\\b.txt", windows=False) is None
      and SW.local_name_problem("\\") == "characters")
check("N98 ...so a name that leaves the folder is refused (the backslash spelling on Windows)",
      SW.local_destination_problem("..\\..\\pwned.txt", WORK)
      == ("outside" if os.name == "nt" else None))
check("N98 ...and the POSIX spelling is refused on every platform",
      SW.local_destination_problem(os.path.join("..", "..", "pwned.txt"), WORK) == "outside")
check("N98 a nested but CONTAINED entry passes",
      SW.local_destination_problem(os.path.join("sub", "a.txt"), WORK) is None)
check("N98 the file-list rule of a single entry is unchanged (N40 stays fixed)",
      SW.local_destination_problem("a.txt", WORK) is None
      and SW.local_destination_problem("bad:name.csv", WORK) in (None, "characters"))

_fs = FakeSftpFS()
_fs.add_dir("/tree")
_fs.add_dir("/tree/sub")
# The walk is SORTED by name, so an ASCII name is copied BEFORE the hostile one is met: the tree
# therefore really stops halfway, which is the `_SftpPartial` shape this section asserts.
_fs.add_file("/tree/a_ok.txt", b"ok")
_fs.add_file("/tree/sub/nested.txt", b"nested")
_fs.add_file("/tree/zz\\..\\..\\pwned.txt", b"payload")
_outer = os.path.join(WORK, "n98_outer")
_dl = os.path.join(_outer, "dl")
os.makedirs(_dl, exist_ok=True)
_worker = SW.SftpWorker(FakeSftpClient(_fs))
_log = EventLog()
wire_worker(_worker, _log)
_worker.start()
_tid = _worker.queue_download("/tree", _dl)
_done = wait_for(lambda: bool(_log.of_kind("done", _tid) or _log.of_kind("error", _tid)
                              or _log.of_kind("cancelled", _tid)), timeout_ms=15000)

check("N98 the tree task STOPS on the hostile entry (a partial, never a silent escape)",
      _done and bool(_log.of_kind("error", _tid)), str([e[0] for e in _log.events]))
_payload = SW.parse_task_payload(str(_log.of_kind("error", _tid)[0][3])) if _log.of_kind("error", _tid) else {}
check("N98 ...and the payload still CARRIES the refused name with its machine code",
      SW.parse_task_payload(str(_payload.get("error") or ""), SW.NAME_ERROR_UNSAFE) is not None
      and (SW.parse_task_payload(str(_payload.get("error") or ""), SW.NAME_ERROR_UNSAFE)
           or {}).get("name") == "pwned.txt"
      and (SW.parse_task_payload(str(_payload.get("error") or ""), SW.NAME_ERROR_UNSAFE)
           or {}).get("reason") == "outside", str(_payload))
check("N98 ...and the tree record names the ENTRY it stopped at",
      str(_payload.get("path") or "").endswith("pwned.txt")
      and int(_payload.get("copied") or 0) >= 1, str(_payload))
check("N98 NOTHING was written outside the chosen folder",
      not os.path.exists(os.path.join(_outer, "pwned.txt"))
      and not os.path.exists(os.path.join(_outer, "zz\\..\\..\\pwned.txt"))
      and sorted(os.listdir(_outer)) == ["dl"], str(sorted(os.listdir(_outer))))
check("N98 ...and nothing was written above the tree either",
      not os.path.exists(os.path.join(WORK, "pwned.txt"))
      and not os.path.exists(os.path.join(_dl, "pwned.txt")))
check("N98 the entry that really was reachable is on the disk (the tree is stopped, not rolled back)",
      open(os.path.join(_dl, "tree", "a_ok.txt"), "rb").read() == b"ok")
check("N98 ...and no provisional litter is left anywhere in the tree",
      [os.path.join(dp, n) for dp, _d, files in os.walk(_dl) for n in files
       if n.endswith(SW.PART_SUFFIX)] == [])
_worker.shutdown(wait_ms=2000)

_fs2 = FakeSftpFS()
_fs2.add_dir("/t2")
_fs2.add_dir("/t2/sub")
_fs2.add_file("/t2/sub/plain.txt", b"plain")
_w2 = SW.SftpWorker(FakeSftpClient(_fs2))
_log2 = EventLog()
wire_worker(_w2, _log2)
_w2.start()
_tid2 = _w2.queue_download("/t2", os.path.join(WORK, "n98_clean"))
_ok2 = wait_for(lambda: bool(_log2.of_kind("done", _tid2) or _log2.of_kind("error", _tid2)),
                timeout_ms=15000)
check("N98 a tree of ORDINARY nested names still lands whole (the fix refuses nothing legal)",
      _ok2 and bool(_log2.of_kind("done", _tid2)),
      str(_log2.of_kind("error", _tid2)[0][3]) if _log2.of_kind("error", _tid2) else "no error")
check("N98 ...with its subdirectory in place",
      os.path.exists(os.path.join(WORK, "n98_clean", "t2", "sub", "plain.txt")))
_w2.shutdown(wait_ms=2000)

check("N98 the tree walk hands the destination it WRITES to the gate (the one-file signature)",
      "local_name=rel" in open(os.path.join(ROOT, "modules", "sftp_worker.py"),
                               encoding="utf-8").read()
      and "local_name=os.path.basename(dest)" not in
      open(os.path.join(ROOT, "modules", "sftp_worker.py"), encoding="utf-8").read())


# ════════════════════════════════════════════════════════════
# 2. N104 — the project reader answers its DECLARED empty answer
# ════════════════════════════════════════════════════════════
print("== 2. N104: the project reader ==")


def _write_project(name, text):
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


_p_null = _write_project("n104_null.json", '{"servers": null}')
_p_array = _write_project("n104_array.json", "[1, 2]")
_p_empty = _write_project("n104_empty.json", "{}")
_p_text = _write_project("n104_text.json", '"just a string"')
_p_ok = _write_project("n104_ok.json", '{"servers": [{"alias": "web-1", "host": "10.0.0.1"}]}')
_p_bad = _write_project("n104_bad.json", "{not json at all")

check("N104 `servers: null` reads as no servers (the TypeError is gone)",
      PRJ.read_project_servers(_p_null) == [])
check("N104 a JSON ARRAY is the same declared answer",
      PRJ.read_project_servers(_p_array) == [] and PRJ.load_project(_p_array) == {})
check("N104 a JSON string is the same declared answer",
      PRJ.read_project_servers(_p_text) == [] and PRJ.load_project(_p_text) == {})
check("N104 an empty object stays an empty project",
      PRJ.read_project_servers(_p_empty) == [] and PRJ.load_project(_p_empty) == {})
check("N104 a real project still reads its servers, in FILE order",
      [s.alias for s in PRJ.read_project_servers(_p_ok)] == ["web-1"]
      and PRJ.load_project(_p_ok).get("servers") is not None)
check("N104 the log COUNT of a half-written file no longer raises",
      len(PRJ.load_project(_p_null).get("servers") or []) == 0
      and len(PRJ.load_project(_p_array).get("connections") or []) == 0)
try:
    PRJ.load_project(_p_bad)
    _raised = None
except Exception as exc:  # noqa: BLE001 — the failure IS the contract here
    _raised = type(exc).__name__
check("N104 a MISSING file and unparseable JSON still raise (the caller recovers)",
      _raised == "JSONDecodeError", str(_raised))
try:
    PRJ.load_project(os.path.join(WORK, "n104_no_such_file.json"))
    _missing = None
except Exception as exc:  # noqa: BLE001
    _missing = type(exc).__name__
check("N104 ...and a missing file raises FileNotFoundError",
      _missing == "FileNotFoundError", str(_missing))


# ════════════════════════════════════════════════════════════
# 3. N100 + R14(a) — an unanswered question may not pin a host key
# ════════════════════════════════════════════════════════════
print("== 3. N100: the host key of an unanswered question ==")

HKP.set_store(HKP.KnownHostsStore(path=os.path.join(WORK, "n100_known_hosts")))
_default_budget = HKP.HOST_KEY_ASK_TIMEOUT_S


class _Key:
    """The paramiko `PKey` surface the policy reads: a name and a fingerprint."""

    def get_name(self):
        return "ssh-ed25519"

    def asbytes(self):
        return b"the-key-bytes"

    def get_base64(self):
        return "AAAAB3NzaC1lZDI1NTE5"


def _ask_new(answerer, budget=0.4, host="n100.example"):
    """`ask_new_host_key()` on a WORKER thread — the way a connect asks it — with a short budget."""
    ASK.set_answerer(answerer)
    HKP.HOST_KEY_ASK_TIMEOUT_S = budget
    HKP.get_store().remove(HKP.entry_name_for(host, 22), "ssh-ed25519")
    box = {}
    started = time.monotonic()

    def _call():
        try:
            box["answer"] = HKP.ask_new_host_key(host, 22, _Key())
        except Exception as exc:  # noqa: BLE001 — the answer IS the observation
            box["answer"] = "%s: %s" % (type(exc).__name__, exc)

    thread = threading.Thread(target=_call, name="n100-ask")
    thread.start()
    thread.join(budget + 2)
    box["seconds"] = time.monotonic() - started
    box["pinned"] = bool(HKP.get_store().lookup(HKP.entry_name_for(host, 22)))
    HKP.get_store().remove(HKP.entry_name_for(host, 22), "ssh-ed25519")
    thread.join(5)          # the answerer's own delay: one scenario at a time
    return box


def _never(_request):
    time.sleep(3)
    return True


def _late_yes(_request):
    time.sleep(1.5)
    return True


def _raises(_request):
    raise RuntimeError("the dialog could not be built")


_never_answer = _ask_new(_never)
check("N100 a surface that does NOT answer within the budget is a REFUSAL",
      _never_answer["answer"] is False, str(_never_answer))
check("N100 ...and the asker gave up at the DECLARED budget, not at the answerer's own time",
      _never_answer["seconds"] < 2.0, "%.1f s" % _never_answer["seconds"])
check("N100 ...and NOTHING was pinned by the late answer",
      _never_answer["pinned"] is False)
_late = _ask_new(_late_yes)
check("N100 a dialog the user is still reading cannot pin the key behind their back (the RACE)",
      _late["answer"] is False and _late["pinned"] is False, str(_late))
_none_answer = _ask_new(lambda _r: None)
check("N100 a surface that answers None is a refusal",
      _none_answer["answer"] is False and _none_answer["pinned"] is False, str(_none_answer))
_raised_answer = _ask_new(_raises)
check("N100 a surface that RAISES is a refusal",
      _raised_answer["answer"] is False and _raised_answer["pinned"] is False, str(_raised_answer))
_tofu = _ask_new(None)
check("N100 with NO surface at all the declared TOFU fallback still accepts",
      _tofu["answer"] is True and _tofu["seconds"] < 1.0, str(_tofu))
HKP.HOST_KEY_ASK_TIMEOUT_S = _default_budget
ASK.set_answerer(None)

check("N100 has_answerer() is the ONE predicate that separates the two situations",
      ASK.has_answerer() is False and "has_answerer" in
      open(os.path.join(ROOT, "modules", "host_key_policy.py"), encoding="utf-8").read())
check("N100 a policy REFUSES the connection when the question went unanswered",
      "HostKeyRejected" in open(os.path.join(ROOT, "modules", "host_key_policy.py"),
                                encoding="utf-8").read())


# ════════════════════════════════════════════════════════════
# 4. N99 — the guard's input bound is a REFUSAL, and both bomb spellings count
# ════════════════════════════════════════════════════════════
print("== 4. N99: the command guard's bound ==")

check("N99 a line over MAX_COMMAND_CHARS is REFUSED, whatever it carries",
      CG.dangerous_token("echo " + "x" * (CG.MAX_COMMAND_CHARS + 100)) == CG.TOKEN_OVER_LONG
      and CG.needs_confirmation("echo " + "x" * (CG.MAX_COMMAND_CHARS + 100), {})
      == CG.TOKEN_OVER_LONG)
check("N99 ...and the danger that used to hide past the bound is refused with it",
      all(CG.dangerous_token("echo " + "x" * pad + tail) == CG.TOKEN_OVER_LONG
          for pad, tail in ((4090, "; rm -rf /"), (4200, "; reboot"),
                            (4200, "; dd if=/dev/zero of=/dev/sda"), (5000, "; rm -rf /"))))
check("N99 a NESTED payload is bound by the same rule (no silent truncation)",
      CG.dangerous_token('bash -c "echo ' + "x" * 5000 + '; rm -rf /"') == CG.TOKEN_OVER_LONG)
check("N99 the bound is exclusive: the LINE of exactly MAX_COMMAND_CHARS is still classified",
      CG.dangerous_token("echo " + "x" * (CG.MAX_COMMAND_CHARS - len("echo ; rm -rf /"))
                         + "; rm -rf /") == "rm -rf")
check("N99 a legal line inside the bound is untouched",
      CG.dangerous_token("echo " + "x" * 4000 + "; rm -rf /") == "rm -rf"
      and CG.dangerous_token("uptime") == "")
check("N99 the guard is still switchable off (the refusal is a POLICY, not a lock)",
      CG.needs_confirmation("echo " + "x" * 5000, {"guard_commands": False}) == "")
check("N99 bash's `function name { … }` spelling of the bomb is caught",
      CG.dangerous_token("function bomb { bomb|bomb& }; bomb") == CG.TOKEN_FORK_BOMB)
check("N99 ...and the two spellings that were already caught still are",
      CG.dangerous_token(":(){ :|:& };:") == CG.TOKEN_FORK_BOMB
      and CG.dangerous_token("bomb(){ bomb|bomb& }; bomb") == CG.TOKEN_FORK_BOMB)
check("N99 a benign function definition is NOT a bomb",
      CG.dangerous_token("function greet { echo hello; }; greet") == ""
      and CG.dangerous_token("f() { echo hi; }") == "")
check("N99 the shipped false positive stays closed",
      CG.dangerous_token('echo "rm -rf /"') == "" and CG.dangerous_token("") == ""
      and CG.dangerous_token(None) == "")
check("N99 the buffer's own cap and the classifier's bound are the SAME declaration",
      __import__("modules.terminal_widget_input", fromlist=["x"]).GUARD_LINE_MAX_CHARS
      == CG.MAX_COMMAND_CHARS)


# ════════════════════════════════════════════════════════════
# 5. N101 — the client a failed connect created is CLOSED
# ════════════════════════════════════════════════════════════
print("== 5. N101: the client of a failed connect ==")

_created = []


class _CountingClient:
    """The paramiko `SSHClient` surface `connect_client()` uses, counting every `close()`."""

    def __init__(self):
        self.closed = False
        self.close_calls = 0
        self.policy = None
        _created.append(self)

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, **kwargs):
        raise paramiko.AuthenticationException("Authentication failed.")

    def close(self):
        self.close_calls += 1
        self.closed = True


class _BadHostKeyClient(_CountingClient):
    """A client whose `connect()` refuses the key — the changed-key path's own failure."""

    def connect(self, **kwargs):
        raise paramiko.BadHostKeyException("n101.example", _Key(), _Key())


class _ExplodingClose(_CountingClient):
    """A half-open client whose `close()` also fails: the cleanup must not replace the real error."""

    def close(self):
        self.close_calls += 1
        raise RuntimeError("the transport is already gone")


_real_client_class = paramiko.SSHClient
try:
    for label, client_class, expected in (("a refused login", _CountingClient,
                                           paramiko.AuthenticationException),
                                          ("a refused key", _BadHostKeyClient,
                                           paramiko.BadHostKeyException),
                                          ("a close() that raises", _ExplodingClose,
                                           paramiko.AuthenticationException)):
        _created.clear()
        paramiko.SSHClient = client_class
        try:
            SCON.connect_client("n101.example", "bob", 22, password="pw")
            answer = "no exception"
        except Exception as exc:  # noqa: BLE001 — the raise IS the contract
            answer = type(exc).__name__
        check("N101 %s closes the client this function created" % label,
              len(_created) == 1 and _created[0].close_calls == 1,
              "created=%d close_calls=%s" % (len(_created), [c.close_calls for c in _created]))
        check("N101 ...and the caller still sees the ORIGINAL failure (%s)" % label,
              answer == expected.__name__, answer)

    _created.clear()
    paramiko.SSHClient = _CountingClient
    _handed = _CountingClient()
    _created.clear()
    try:
        SCON.connect_client("n101.example", "bob", 22, password="pw", client=_handed)
    except Exception:  # noqa: BLE001 — the point is WHOSE client was closed
        pass
    check("N101 a client handed IN belongs to its caller and is NEVER closed here",
          _handed.closed is False and _created == [], str([c.closed for c in _created]))
finally:
    paramiko.SSHClient = _real_client_class

check("N101 the ONE close helper is the only close in the connect path",
      "def _close_quiet(" in open(os.path.join(ROOT, "modules", "ssh_connect.py"),
                                  encoding="utf-8").read())
check("N101 a replaced key still reconnects on a FRESH client (the N48 flow is intact)",
      "_key_replaced" in open(os.path.join(ROOT, "modules", "ssh_connect.py"), encoding="utf-8").read())


check_i18n_parity(load_i18n_langs(ROOT))

finish()
