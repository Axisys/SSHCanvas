# -*- coding: utf-8 -*-
"""v1.15.3.1 — the review of the shipped jump host: the external chain and the diagnostics/i18n batch.
§1 the external `-J` chain and its bounds (`N192`); §2 the internal reader stays ONE hop (`N192`, `N196`);
§3 no space survives to the wire (`N195`); §4 the passphrase is asked ONCE (`N193`); §5 a bastion failure
belongs to the BASTION (`N194`); §6 the translated sentences reach every surface (`N196`) and the direct
test is labelled (`N197`); §7 the CLI's role-aware advice (`N198`); §8 the documents and the comments
(`N199`, `R23`); §9 the release, the ONE parity ledger and the ONE delegate (`R20`, `R22`).
Rule — `AGENTS.md` §4.4.2, §4.5; mechanism — `DOCUMENTATION.md` §16, §69.
Run: python tests/test_hardening_v11531.py
"""
import contextlib
import io
import json
import logging
import os
import re
import socket
import sys
import threading

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text, check,
                     check_i18n_parity, check_release_state, finish, load_i18n_langs, releases_at_least)

ROOT, WORK = bootstrap()  # HOME isolation + offscreen + sys.path (BEFORE any app import)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import paramiko  # noqa: E402

import i18n  # noqa: E402
import modules.external_terminal as ET  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import modules.interactive_ask as IA  # noqa: E402
import modules.jump_host as JH  # noqa: E402
import modules.ssh_connect as SCON  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.ssh_worker as SW  # noqa: E402
import version  # noqa: E402
from cli import exit_codes as EX  # noqa: E402
from cli.main import main as cli_main  # noqa: E402
from cli import exec as CLI_EXEC  # noqa: E402
from cli.hostkeys import CliHostKeyPolicy  # noqa: E402
from models.server import ServerData  # noqa: E402

LANGS = load_i18n_langs(ROOT)

#: The seven keys this patch ships — six refusal reasons and the direct-test label (`N196`, `N197`).
JUMP_KEYS = ("ssh.jump_host_invalid", "ssh.jump_user_invalid", "ssh.jump_port_invalid",
             "ssh.jump_host_brackets", "ssh.jump_host_whitespace", "ssh.jump_chain_internal")
NEW_KEYS = JUMP_KEYS + ("ssh.test_direct",)


def read(*parts):
    """The text of one repository file."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def thrown(text):
    """`(reason, message)` of a refused jump value — `(None, "")` when it was accepted."""
    try:
        JH.parse_jump(text, "tester")
    except JH.JumpSpecError as exc:
        return exc.reason, str(exc)
    return None, ""


def fixture(name, servers):
    """ONE synthetic project (never a real map file) in the isolated work folder."""
    payload = {"version": version.VERSION_FORMAT, "servers": list(servers), "connections": [],
               "notes": [], "groups": [], "background": None}
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


MAP = fixture("jump-map.json", [{"id": "srv-web", "alias": "web-1", "host": "10.0.0.5",
                                "ssh_port": 22, "user": "tester",
                                "jump_host": "ops@bastion.example:2222"}])


def run_cli(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout, stderr)`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main(list(argv))
    return code, out.getvalue(), err.getvalue()


# ── the `paramiko.SSHClient` seam ─────────────────────────────────────────────
class FakeChannel:
    """A fake `direct-tcpip` channel: records its close and the methods the wrapper delegates."""

    def __init__(self):
        self.closed = False
        self.calls = []

    def send(self, data):
        self.calls.append("send")
        return len(data)

    def recv(self, size):
        self.calls.append("recv")
        return b""

    def settimeout(self, timeout):
        self.calls.append("settimeout")
        return None

    def close(self):
        self.closed = True


class FakeStream:
    """One fake stdout/stderr with the channel status `Session.run()` waits on."""

    def __init__(self, payload=b""):
        self._payload = payload
        self.channel = self
        self.status_event = threading.Event()
        self.status_event.set()

    def read(self, size=None):
        payload, self._payload = self._payload, b""
        return payload

    def recv_exit_status(self):
        return 0


class FakeTransport:
    """A fake transport: one `direct-tcpip` record and the remote key a policy compares."""

    def __init__(self):
        self.opened = []
        self.channel = FakeChannel()
        self.key = paramiko.ECDSAKey.generate()

    def open_channel(self, kind, destination, source, timeout=None):
        self.opened.append((kind, destination, source, timeout))
        return self.channel

    def get_remote_server_key(self):
        return self.key


class FakeClient:
    """The `paramiko.SSHClient` seam: records what the builder asked and answers the command."""

    made = []
    fail_host = None
    failure = None

    def __init__(self):
        self.host_keys = paramiko.hostkeys.HostKeys()
        self.policy = None
        self.kwargs = {}
        self.closed = False
        self.transport = FakeTransport()
        FakeClient.made.append(self)

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def get_host_keys(self):
        return self.host_keys

    def connect(self, **kwargs):
        self.kwargs = dict(kwargs)
        if FakeClient.fail_host and kwargs.get("hostname") == FakeClient.fail_host:
            raise FakeClient.failure

    def get_transport(self):
        return self.transport

    def exec_command(self, command, timeout=None):
        return FakeStream(), FakeStream(b"ok\n"), FakeStream()

    def close(self):
        self.closed = True


def reset(fail_host=None, failure=None):
    """Return the fake to a known state for the next run."""
    FakeClient.made.clear()
    FakeClient.fail_host = fail_host
    FakeClient.failure = failure
    CLI_EXEC.CLIENT_FACTORY = FakeClient
    return FakeClient


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the external `-J` chain and its bounds ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 a comma chain PASSES the external door (`N192` — the model always promised it)",
      ET.jump_problem("ops@a:22,b,[::1]:2200") is None
      and ET.validate_target("10.0.0.1", "root", "a,b") is None,
      str(ET.jump_problem("a,b")))
check("§1 the value reaches `ssh -J` VERBATIM",
      ET.build_ssh_args("h", "u", 22, jump="a,b") ==
      ["ssh", "-J", "a,b", "-o", "ConnectTimeout=10", "--", "u@h"],
      str(ET.build_ssh_args("h", "u", 22, jump="a,b")))
check("§1 the bounds are declared and enforced",
      ET.MAX_JUMP_HOPS == 8 and ET.MAX_JUMP_CHARS == 1024
      and ET.jump_problem(",".join(f"h{index}" for index in range(9))) == "characters"
      and ET.jump_problem("a" * 1025) == "characters",
      f"{ET.MAX_JUMP_HOPS}/{ET.MAX_JUMP_CHARS}")
check("§1 an empty hop, a metacharacter and an option-shaped hop are refused",
      ET.jump_problem("a,,b") == "characters"
      and ET.jump_problem("a,b;calc") == "characters"
      and ET.jump_problem("-oProxyCommand=calc,b") == "characters")
check("§1 the door's refusal code is unchanged (`bad_jump` → `ssh_ext.bad_jump`)",
      ET.validate_target("h", "u", "a,b;calc") == ET.TARGET_BAD_JUMP
      and ET.validate_target("h", "u", "") is None)

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the internal reader stays ONE hop ==")
# ════════════════════════════════════════════════════════════════════════════

_reason, _message = thrown("a,b")
check("§2 a chain is the `chain` reason of the internal reader", _reason == JH.REASON_CHAIN, _reason)
check("§2 ...and its sentence still names the external terminal (the CLI keeps its words)",
      "ONE host" in _message and "-J" in _message, _message)
check("§2 ONE hop is still ONE hop",
      JH.parse_jump("ops@bastion.example:2222", "tester") == JH.JumpSpec("bastion.example", 2222, "ops"))
check("§2 every refusal carries ONE declared reason",
      set(JH.JUMP_ERROR_KEYS) == {JH.REASON_HOST, JH.REASON_USER, JH.REASON_PORT,
                                  JH.REASON_BRACKETS, JH.REASON_WHITESPACE, JH.REASON_CHAIN},
      str(sorted(JH.JUMP_ERROR_KEYS)))
check("§2 each reason is answered by its OWN translated key",
      JH.JUMP_ERROR_KEYS[JH.REASON_CHAIN] == "ssh.jump_chain_internal"
      and JH.JUMP_ERROR_KEYS[JH.REASON_WHITESPACE] == "ssh.jump_host_whitespace"
      and JH.JUMP_ERROR_KEYS[JH.REASON_HOST] == "ssh.jump_host_invalid")

# ════════════════════════════════════════════════════════════════════════════
print("== §3 no space survives to the wire ==")
# ════════════════════════════════════════════════════════════════════════════

for _bad in ("ops @bastion", "ops@ bastion", "host :22", "[ ::1 ]", "a, b"):
    _reason, _message = thrown(_bad)
    check(f"§3 {_bad!r} is the `whitespace` reason (`N195`)", _reason == JH.REASON_WHITESPACE,
          f"{_reason} / {_message}")
check("§3 the JumpSpec branch refuses an inner space too",
      thrown(JH.JumpSpec("bast ion"))[0] == JH.REASON_WHITESPACE
      and thrown(JH.JumpSpec("h", 22, "op s"))[0] == JH.REASON_WHITESPACE)
check("§3 the external door refuses the space as well",
      ET.jump_problem("a, b") == "characters" and ET.jump_problem("ops@bast ion") == "characters")
check("§3 ...so no unstripped part reaches a `JumpSpec` (the old defect: `ops ` as the user)",
      thrown("ops @bastion")[0] == JH.REASON_WHITESPACE
      and JH.parse_jump(" ops@bastion.example:2222 ", "t") == JH.JumpSpec("bastion.example", 2222, "ops"))

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the passphrase is asked ONCE ==")
# ════════════════════════════════════════════════════════════════════════════

_ENCRYPTED = os.path.join(WORK, "id_encrypted")
paramiko.RSAKey.generate(1024).write_private_key_file(_ENCRYPTED, password="secret")
_asked = []


def _answer(request):
    """The interactive surface of the probe: answers the passphrase and records every ask."""
    _asked.append(request.kind)
    return "secret"


IA.set_answerer(_answer)
try:
    reset()
    SCON.connect_client("target.example", "root", 22, key_path=_ENCRYPTED,
                        jump="ops@bastion.example:2222", jump_key_path=_ENCRYPTED,
                        client_factory=FakeClient)
finally:
    IA.set_answerer(None)
_bastion = next(client for client in FakeClient.made if client.kwargs.get("hostname") == "bastion.example")
_target = next(client for client in FakeClient.made if client.kwargs.get("hostname") == "target.example")
check("§4 an encrypted key with a jump host asks for its passphrase ONCE (`N193`)",
      _asked == [IA.KIND_KEY_PASSPHRASE], str(_asked))
check("§4 ...and the SAME resolved value reaches both endpoints",
      _target.kwargs.get("passphrase") == "secret" and _bastion.kwargs.get("passphrase") == "secret",
      str((_target.kwargs.get("passphrase"), _bastion.kwargs.get("passphrase"))))
check("§4 ...while the target's password never reaches the bastion (`password` stays None)",
      _bastion.kwargs.get("password") is None and _bastion.kwargs.get("key_filename") == _ENCRYPTED,
      str(_bastion.kwargs))
IA.set_answerer(None)
try:
    reset()
    SCON.connect_client("target.example", "root", 22, key_path=_ENCRYPTED,
                        jump="bastion.example", jump_key_path=_ENCRYPTED, client_factory=FakeClient)
    _cancelled = ""
except Exception as exc:  # noqa: BLE001 — the test reads the propagated class
    _cancelled = type(exc).__name__
check("§4 an UNANSWERED passphrase is the declared refusal, not a socket",
      _cancelled == "ConnectionCancelled" and not FakeClient.made, _cancelled)
os.remove(_ENCRYPTED)

# ════════════════════════════════════════════════════════════════════════════
print("== §5 a bastion failure belongs to the BASTION ==")
# ════════════════════════════════════════════════════════════════════════════

HKP.set_store(HKP.KnownHostsStore(os.path.join(WORK, "known_hosts_probe")))
reset(fail_host="bastion.example", failure=paramiko.AuthenticationException("bastion refused"))
_code, _out, _err = run_cli(["--project", MAP, "exec", "web-1", "uptime"])
check("§5 a refused bastion is still the `auth` class (`N194`)", _code == EX.EXIT_AUTH, f"{_code} / {_err!r}")
check("§5 ...and the sentence names the HOP, never the target's endpoint",
      "ops@bastion.example:2222" in _err and "tester@10.0.0.5:22:" not in _err, _err.strip())
reset(fail_host="bastion.example", failure=OSError("connection refused"))
_code, _out, _err = run_cli(["--project", MAP, "exec", "web-1", "uptime"])
check("§5 a bastion network failure is the `network` class", _code == EX.EXIT_NETWORK, f"{_code} / {_err!r}")
check("§5 ...and it is attributed to the hop as well",
      "ops@bastion.example:2222" in _err and "tester@10.0.0.5:22:" not in _err, _err.strip())
_channel_failure = SCON.JumpHopError(JH.JumpSpec("bastion.example", 2222, "ops"),
                                     paramiko.SSHException("channel not opened"))
_cli_error = CLI_EXEC.classify(_channel_failure, "tester@10.0.0.5:22")
check("§5 the CLI keeps the cause's class and adds the hop's label",
      _cli_error.code == EX.EXIT_NETWORK and _cli_error.message.startswith("ops@bastion.example:2222: "),
      _cli_error.sentence())
check("§5 the GUI sentence maps the cause through the shipped keys (`ssh.auth_failed`)",
      SCON.jump_error_text(_channel_failure) == i18n.t("ssh.connection_failed",
                                                       host="bastion.example", port=2222))
_hop_auth = SCON.JumpHopError(JH.JumpSpec("bastion.example", 2222, "ops"),
                              paramiko.AuthenticationException("no"))
check("§5 ...and an auth cause names the hop beside the shipped sentence",
      SCON.jump_error_text(_hop_auth) == f"{i18n.t('ssh.auth_failed')} — ops@bastion.example:2222",
      SCON.jump_error_text(_hop_auth))
check("§5 `HostKeyRejected` / `ConnectionCancelled` keep their finished sentence (never wrapped)",
      "HostKeyRejected" in read("modules", "ssh_connect.py")
      and "except (HostKeyRejected, ConnectionCancelled):" in read("modules", "ssh_connect.py"))

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the translated sentences reach every surface ==")
# ════════════════════════════════════════════════════════════════════════════

for _code in LANGS:
    for _key in NEW_KEYS:
        check(f"§6 i18n/{_code}.json carries {_key}", str(LANGS[_code].get(_key) or "").strip() != "")
check("§6 the seven keys are the patch's whole parity move",
      EXPECTED_I18N_KEYS >= 1263 and all(len({k for k in LANGS[c] if k not in ("name", "partial")})
                                         == EXPECTED_I18N_KEYS for c in LANGS))
check_i18n_parity(LANGS)

for _reason in (JH.REASON_HOST, JH.REASON_USER, JH.REASON_PORT, JH.REASON_BRACKETS,
                JH.REASON_WHITESPACE, JH.REASON_CHAIN):
    _sentence = SCON.jump_error_text(JH.JumpSpecError("parser English", _reason))
    check(f"§6 the {_reason} refusal is TRANSLATED, never the parser's English",
          _sentence == i18n.t(JH.JUMP_ERROR_KEYS[_reason]) and _sentence != "parser English", _sentence)
_EN_CHAIN = SCON.jump_error_text(JH.JumpSpecError("x", JH.REASON_CHAIN))
i18n.set_language("ru")
try:
    _ru = SCON.jump_error_text(JH.JumpSpecError("x", JH.REASON_CHAIN))
finally:
    i18n.set_language("en")
check("§6 a language switch reaches the jump sentence (the key, not a fallback literal)",
      _ru != "" and _ru != _EN_CHAIN and _ru != "x", f"ru={_ru!r} en={_EN_CHAIN!r}")

_collected = []
_thread = ST.SSHTerminalThread("target.example", "tester", 22, jump_host="a,b")
_thread.error_signal.connect(_collected.append)
_thread.run()
check("§6 the TERMINAL shows the translated chain sentence (`N196`)",
      _collected and _collected[-1] == i18n.t("ssh.jump_chain_internal"), str(_collected))
_worker_errors = []
_worker = SW.SSHWorker("target.example", "tester", 22, jump_host=" ops@bast ion ")
_worker.error.connect(_worker_errors.append)
_worker.run()
check("§6 the WORKER shows the translated whitespace sentence too",
      _worker_errors and _worker_errors[-1] == i18n.t("ssh.jump_host_whitespace"), str(_worker_errors))
def function_body(source, header):
    """The text of ONE method/function, up to the next class-level `def` (a source probe)."""
    start = source.index(header)
    following = source.find("\n    def ", start)
    return source[start:following if following > 0 else len(source)]


check("§6 the TERMINAL's jump branch precedes its generic handler",
      function_body(read("modules", "ssh_terminal.py"), "def run(self):").index("except JUMP_ERRORS")
      < function_body(read("modules", "ssh_terminal.py"), "def run(self):").rindex("except Exception"))
check("§6 the WORKER's jump branch lives in its CONNECT path (never left to `run()`'s generic)",
      "except JUMP_ERRORS" in function_body(read("modules", "ssh_worker.py"),
                                           "def _run_ssh_connect(self):"))
check("§6 ...and the worker shows the jump sentence, not `str(e)`",
      "self._emit_error(jump_error_text(e))" in read("modules", "ssh_worker.py"))

_DIALOG = read("dialogs", "ssh_connect_dialog.py")
check("§6 the dialog's test button is the DIRECT probe (`N197`)",
      'QPushButton(self.t("ssh.test_direct"))' in _DIALOG
      and 'setToolTip(self.t("ssh.test_direct"))' in _DIALOG)
check("§6 ...the shipped `ssh.test` key is kept (keys are additive only)",
      all("ssh.test" in LANGS[_code] for _code in LANGS))
check("§6 ...and the probe itself is still a DIRECT socket connect",
      "socket.create_connection((self.host, self.port), timeout=5)"
      in read("modules", "ssh_worker.py"))
try:
    from dialogs.ssh_connect_dialog import SSHConnectDialog
    _dialog = SSHConnectDialog(ServerData(id="srv-web", alias="web-1", host="10.0.0.5",
                                          user="tester", jump_host="ops@bastion.example:2222"))
    _label, _tip = _dialog.test_btn.text(), _dialog.test_btn.toolTip()
    _dialog.deleteLater()
    check("§6 the built dialog really carries the new label and tooltip",
          _label == i18n.t("ssh.test_direct") and _tip == i18n.t("ssh.test_direct"),
          f"{_label!r} / {_tip!r}")
except Exception as exc:  # noqa: BLE001 — a headless build that refuses the dialog is reported, not hidden
    check("§6 the built dialog really carries the new label and tooltip", False, repr(exc))

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the CLI's role-aware advice ==")
# ════════════════════════════════════════════════════════════════════════════

_unknown_key = paramiko.ECDSAKey.generate()


def _refusal(policy):
    """The sentence of ONE unknown-key refusal."""
    try:
        policy.missing_host_key(object(), policy.hostname, _unknown_key)
    except Exception as exc:  # noqa: BLE001 — the refusal IS the answer under test
        return str(exc)
    return ""


_TARGET_REFUSAL = _refusal(CliHostKeyPolicy("target.example", 22))
_BASTION_REFUSAL = _refusal(CliHostKeyPolicy("bastion.example", 2222, bastion=True))
check("§7 the TARGET's refusal advises `--host-key` (it names the target alone)",
      "--host-key" in _TARGET_REFUSAL and "--accept-new" in _TARGET_REFUSAL, _TARGET_REFUSAL)
check("§7 the BASTION's refusal NEVER advises `--host-key` (`N198`)",
      "--host-key" not in _BASTION_REFUSAL, _BASTION_REFUSAL)
check("§7 ...it names the store to pre-pin and `--accept-new`",
      "known_hosts" in _BASTION_REFUSAL and "--accept-new" in _BASTION_REFUSAL, _BASTION_REFUSAL)
check("§7 the CLI wires the ROLE into the policy (`bastion=(role == ROLE_JUMP)`)",
      "bastion=(role == ROLE_JUMP)" in read("cli", "exec.py")
      and "ROLE_JUMP" in read("cli", "exec.py").split("classify", 1)[0])
reset()
DECLARED = CliHostKeyPolicy("h-cli", 22)
check("§7 a non-bastion policy is the shipped default",
      DECLARED.bastion is False and CliHostKeyPolicy("h", 22, bastion=True).bastion is True)

# ════════════════════════════════════════════════════════════════════════════
print("== §8 the documents and the comments state the split ==")
# ════════════════════════════════════════════════════════════════════════════

_MWS = read("ui", "main_window_ssh.py")
_IMPORTER = read("services", "ssh_config_importer.py")
_EXTERNAL_DOC = read("DOCUMENTATION.md") if os.path.exists(os.path.join(ROOT, "DOCUMENTATION.md")) else ""
check("§8 the external door's comment no longer says the internal path stays OUT (`N199`)",
      "INTERNAL path stays out of it" not in _MWS
      and "the built-in path reads ONE hop" in _MWS)
check("§8 the importer describes the field as BOTH doors'",
      "comma\nchain for the external terminal, ONE hop for the built-in path" in _IMPORTER
      or "chain for the external terminal, ONE hop for the built-in path" in _IMPORTER)
check("§8 `jump_problem()`'s docstring no longer claims both doors refuse the same alphabet",
      "both doors refuse the same alphabet" not in read("modules", "external_terminal.py"))
check("§8 ...and the external terminal's code carries the chain and its bounds",
      "MAX_JUMP_HOPS" in read("modules", "external_terminal.py")
      and "MAX_JUMP_CHARS" in read("modules", "external_terminal.py"))
check("§8 the connect builder's docstring owns the hop's mechanism (the docs point at it)",
      "jump_error_text" in (SCON.__doc__ or ""), (SCON.__doc__ or "")[:80])
if _EXTERNAL_DOC:
    check("§8 DOCUMENTATION.md states the internal/external split and the bounds",
          "comma chain" in _EXTERNAL_DOC and "MAX_JUMP_HOPS" in _EXTERNAL_DOC)
    check("§8 DOCUMENTATION.md no longer claims the reader refuses the chain without the split",
          "a comma chain refused" not in _EXTERNAL_DOC)
    check("§8 DOCUMENTATION.md's `connect_client()` paragraph is compressed (`R23`)",
          "ONE `connect()`: the client through `client_factory`" in _EXTERNAL_DOC
          and "A CHANGED host key is ONE question and ONE retry" in _EXTERNAL_DOC)

# ════════════════════════════════════════════════════════════════════════════
print("== §9 the release, the ONE ledger and the ONE delegate ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check("§9 this patch is v1.15.3.1 or a later one",
      releases_at_least(EXPECTED_APP_VERSION, "1.15.3.1"), EXPECTED_APP_VERSION)
check("§9 the project format and the dependency list did not move",
      version.VERSION_FORMAT == "0.9"
      and len([line for line in read("requirements.txt").splitlines()
               if line.strip() and not line.strip().startswith("#")]) == 4)
check("§9 the changelog family carries the patch",
      "## v1.15.3.1" in changelog_family_text(ROOT)
      and "## Details — v1.15.3.1" in changelog_family_text(ROOT, "DETAILS"))

_I18N_LIVE = read("tests", "test_i18n_live.py")
check("§9 the parity arithmetic lives in ONE ledger (`R20`)",
      "KEY_LEDGER_BASE" in _I18N_LIVE and "KEY_LEDGER" in _I18N_LIVE
      and "the ledger sums to the shipped pin" in _I18N_LIVE)
check("§9 ...and a gate rejects a new topical equality",
      "_PIN_EQUALITY_RE" in _I18N_LIVE and "no topical test file re-sums the parity pin" in _I18N_LIVE)
_SELF = os.path.basename(__file__)
_LEDGER_OWNER = "test_i18n_live.py"       # the ONE file the ledger and its gate live in
_offenders = [name for name in sorted(os.listdir(os.path.join(ROOT, "tests")))
              if name.startswith("test_") and name.endswith(".py")
              and name not in (_SELF, _LEDGER_OWNER)
              and re.search(r"EXPECTED_I18N_KEYS\s*==", read("tests", name))]
check("§9 no OTHER topical file re-sums the pin (the state the patch left)", not _offenders, _offenders)

_WRAPPER = SCON._JumpSocket(FakeChannel(), object())
check("§9 `_JumpSocket` owns ONLY `close` and the ONE delegate (`R22`)",
      set(SCON._JumpSocket.__dict__) == {"__init__", "close", "__getattr__", "__module__",
                                         "__doc__", "__dict__", "__weakref__"},
      str(sorted(SCON._JumpSocket.__dict__)))
check("§9 ...and `send`/`recv`/`settimeout` are DELEGATED, not copied",
      _WRAPPER.send(b"x") == 1 and _WRAPPER.recv(1) == b"" and _WRAPPER.settimeout(1) is None
      and _WRAPPER._channel.calls == ["send", "recv", "settimeout"], str(_WRAPPER._channel.calls))
_WRAPPER.close()
check("§9 `close()` is idempotent and still owns the bastion's life",
      _WRAPPER._closed is True and _WRAPPER._channel.closed is True)


class _RealChannel:
    """One end of a real socketpair, exposing the channel methods paramiko asks for."""

    def __init__(self, sock):
        self.sock = sock
        self.calls = set()

    def send(self, data):
        self.calls.add("send")
        return self.sock.send(data)

    def recv(self, size):
        self.calls.add("recv")
        return self.sock.recv(size)

    def settimeout(self, timeout):
        self.calls.add("settimeout")
        return self.sock.settimeout(timeout)

    def close(self):
        self.calls.add("close")
        self.sock.close()


_left, _right = socket.socketpair()
_quiet = logging.getLogger("paramiko.transport")
_level = _quiet.level
_quiet.setLevel(logging.CRITICAL)
try:
    _channel = _RealChannel(_left)
    _real = SCON._JumpSocket(_channel, None)
    _transport = paramiko.Transport(_real)
    try:
        _transport.start_client(timeout=1.0)      # sends its banner, then waits for the peer's
    except Exception:  # noqa: BLE001 — the probe is the BANNER the wrapper carried, not the handshake
        pass
    _right.settimeout(3.0)
    try:
        _banner = _right.recv(64)
    except OSError:
        _banner = b""
    _transport.close()
finally:
    _quiet.setLevel(_level)
    for _sock in (_left, _right):
        try:
            _sock.close()
        except OSError:
            pass
check("§9 a REAL paramiko Transport runs over the wrapper (send/recv/settimeout delegate)",
      _banner.startswith(b"SSH-") and {"send", "recv", "settimeout"} <= _channel.calls,
      f"{_banner!r} / {sorted(_channel.calls)}")

finish()
