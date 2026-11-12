# -*- coding: utf-8 -*-
"""The internal jump host: ONE `direct-tcpip` hop in `connect_client()`, its policy seam and its wiring.

§1 the PURE `[user@]host[:port]` reader (`modules/jump_host.py`): one hop, no secret, no chain; §2 the
hop itself over fake clients: the bastion authenticates with key/agent, the target gets `sock=`, both
endpoints get their OWN policy and the bastion dies with the target; §3 the CLI `exec` path: the two
policies, `--identity`, `--accept-new`, `--host-key`, and a malformed field refused before a socket;
§4 the GUI wiring and the no-password-to-the-bastion rule; §5 the release state.

Run: python tests/test_jump_host.py   (from the project root) or python tests/run_all.py"""
import json
import os
import threading

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text,
                     check, check_i18n_parity, check_release_state, finish, load_i18n_langs,
                     releases_at_least)

ROOT, WORK = bootstrap()  # HOME isolation + offscreen + sys.path (BEFORE any app import)

import cli.credentials as CREDENTIALS  # noqa: E402
import cli.exec as EXEC  # noqa: E402
import cli.exit_codes as EX  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import modules.jump_host as JH  # noqa: E402
import modules.ssh_connect as SCON  # noqa: E402
import paramiko  # noqa: E402
import version  # noqa: E402
from cli.main import main  # noqa: E402
from models.server import ServerData  # noqa: E402

LANGS = load_i18n_langs(ROOT)
KEY_OK = os.path.join(WORK, "id_jump")
with open(KEY_OK, "w", encoding="utf-8") as _handle:
    _handle.write("-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----\n")


def read(rel):
    """The text of one repository file."""
    with open(os.path.join(ROOT, rel.replace("/", os.sep)), encoding="utf-8") as handle:
        return handle.read()


def fixture(name, servers=()):
    """Write ONE synthetic project into the isolated work folder (never a real map file)."""
    payload = {"version": version.VERSION_FORMAT, "servers": list(servers), "connections": [],
               "notes": [], "groups": [], "background": None}
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def fixture_node(**extra):
    """ONE synthetic server record with a jump host."""
    record = {"id": "srv-web", "alias": "web-1", "host": "10.0.0.5", "ssh_port": 22,
              "user": "tester", "jump_host": "ops@bastion.example:2222"}
    record.update(extra)
    return record


MAP = fixture("jump-map.json", [fixture_node()])
BAD_JUMP = fixture("jump-bad.json", [fixture_node(jump_host="a,b")])


def run_cli(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout text, stderr text)`."""
    import contextlib
    import io
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


# ── The `paramiko.SSHClient` seams ──────────────────────────────────────────────
class FakeChannel:
    """A fake `direct-tcpip` channel: records its close and answers bounded stream reads."""

    def __init__(self):
        self.closed = False

    def send(self, data):
        return len(data)

    def recv(self, size):
        return b""

    def settimeout(self, timeout):
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
    """A fake transport: one `direct-tcpip` record and the remote key `--host-key` compares."""

    def __init__(self, key=None):
        self.opened = []
        self.channel = FakeChannel()
        self.key = key or paramiko.ECDSAKey.generate()

    def open_channel(self, kind, destination, source, timeout=None):
        self.opened.append((kind, destination, source, timeout))
        return self.channel

    def get_remote_server_key(self):
        return self.key


class FakeClient:
    """The `paramiko.SSHClient` seam: records what the builder asked and answers the command."""

    made = []
    fail_host = None          # a hostname whose `connect()` raises (None — none)
    failure = None            # the exception the named host raises
    remote_key = None         # the key every transport presents (None — a fresh one)

    def __init__(self):
        self.host_keys = paramiko.hostkeys.HostKeys()
        self.policy = None
        self.kwargs = {}
        self.closed = False
        self.commands = []
        self.transport = FakeTransport(FakeClient.remote_key)
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
        self.commands.append((command, timeout))
        return FakeStream(), FakeStream(b"ok\n"), FakeStream()

    def close(self):
        self.closed = True
        sock = self.kwargs.get("sock")
        if sock is not None:
            sock.close()


def reset(**flags):
    """Return the seam to a known state for the next run."""
    FakeClient.made.clear()
    FakeClient.fail_host = flags.get("fail_host")
    FakeClient.failure = flags.get("failure")
    FakeClient.remote_key = flags.get("remote_key")
    EXEC.CLIENT_FACTORY = FakeClient
    return FakeClient


def by_host(name):
    """The first fake client whose `connect()` named this host (`None` — not built)."""
    return next((client for client in FakeClient.made if client.kwargs.get("hostname") == name), None)


def by_policy(name):
    """The first fake client whose policy names this endpoint (`None` — never built that far)."""
    return next((client for client in FakeClient.made
                 if client.policy is not None and getattr(client.policy, "hostname", "") == name), None)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the PURE jump reader ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 an empty field is NO hop", JH.parse_jump("") is None and JH.parse_jump(None) is None)
check("§1 `host` takes the target user and port 22",
      JH.parse_jump("bastion.example", "tester") == JH.JumpSpec("bastion.example", 22, "tester"),
      str(JH.parse_jump("bastion.example", "tester")))
check("§1 `user@host:port` is read as the three facts",
      JH.parse_jump("  ops@bastion.example:2222  ") == JH.JumpSpec("bastion.example", 2222, "ops"),
      str(JH.parse_jump(" ops@bastion.example:2222 ")))
check("§1 a bracketed IPv6 literal is one host (port optional)",
      JH.parse_jump("[2001:db8::1]:2200", "tester") == JH.JumpSpec("2001:db8::1", 2200, "tester")
      and JH.parse_jump("user@[::1]", "") == JH.JumpSpec("::1", 22, "user"),
      str((JH.parse_jump("[2001:db8::1]:2200"), JH.parse_jump("user@[::1]"))))
check("§1 an omitted user falls back to the target's login and an explicit one wins",
      JH.parse_jump("bastion", "root").user == "root"
      and JH.parse_jump("ops@bastion", "root").user == "ops")
check("§1 the label is the ONE spelling of the hop",
      JH.JumpSpec("h", 2222, "ops").label == "ops@h:2222"
      and JH.JumpSpec("h").label == "h:22")


def refused(text):
    """The message a malformed jump field costs (`""` — accepted)."""
    try:
        JH.parse_jump(text, "tester")
    except JH.JumpSpecError as exc:
        return str(exc)
    return ""


check("§1 a comma chain is refused (ONE hop), and names the external `-J` as its home",
      "ONE host" in refused("a,b") and "-J" in refused("a,b"), refused("a,b"))
check("§1 a secret-shaped `user:secret@host` is refused by the user alphabet",
      "user" in refused("user:secret@bastion"), refused("user:secret@bastion"))
check("§1 a non-numeric, empty or out-of-range port is refused",
      "port" in refused("h:abc") and "port" in refused("h:") and "1..65535" in refused("h:65536"),
      str((refused("h:abc"), refused("h:"), refused("h:65536"))))
check("§1 an unbracketed IPv6, an option-shaped host and an empty host are refused",
      "bracketed" in refused("2001:db8::1") and "may not start" in refused("-bad")
      and "empty" in refused("[]"), str((refused("2001:db8::1"), refused("-bad"), refused("[]"))))
check("§1 a `JumpSpec` handed in is validated like text (no unvalidated back door)",
      refused(JH.JumpSpec("-bad", 22, "ops")) != ""
      and "port" in refused(JH.JumpSpec("h", 0, "ops")), refused(JH.JumpSpec("-bad")))
check("§1 `JumpSpec` is immutable and carries NO secret field",
      JH.JumpSpec.__dataclass_params__.frozen is True
      and set(JH.JumpSpec.__dataclass_fields__) == {"host", "port", "user"},
      str(JH.JumpSpec.__dataclass_fields__))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the direct-tcpip hop ==")
# ════════════════════════════════════════════════════════════════════════════

reset()
_client, _policy = SCON.connect_client(
    "target.example", "root", 22, password="target-pw",
    jump="ops@bastion.example:2222", client_factory=FakeClient)
_target = by_host("target.example")
_bastion = by_host("bastion.example")
check("§2 the hop builds TWO clients: the target and the bastion",
      len(FakeClient.made) == 2 and _target is not None and _bastion is not None,
      str([c.kwargs.get("hostname") for c in FakeClient.made]))
check("§2 the bastion is authenticated FIRST with the KEY/AGENT sources, never the password",
      _bastion.kwargs.get("look_for_keys") is True and _bastion.kwargs.get("allow_agent") is True
      and "password" not in _bastion.kwargs and "key_filename" not in _bastion.kwargs,
      str(_bastion.kwargs))
check("§2 ...while the target keeps its own password branch",
      _target.kwargs.get("password") == "target-pw" and _target.kwargs.get("look_for_keys") is False,
      str(_target.kwargs))
check("§2 ONE `direct-tcpip` channel is opened to the target over the bastion transport",
      _bastion.transport.opened == [("direct-tcpip", ("target.example", 22),
                                     ("127.0.0.1", 0), 15)]
      and not _target.transport.opened, str(_bastion.transport.opened))
check("§2 the channel reaches the target `connect()` as `sock=`",
      isinstance(_target.kwargs.get("sock"), SCON._JumpSocket)
      and _bastion.kwargs.get("sock") is None,
      str(type(_target.kwargs.get("sock"))))
check("§2 EACH endpoint gets its OWN host-key policy",
      _target.policy.hostname == "target.example" and _target.policy.port == 22
      and _bastion.policy.hostname == "bastion.example" and _bastion.policy.port == 2222,
      str((_target.policy.hostname, _bastion.policy.hostname)))
check("§2 the returned policy is the TARGET's (the caller reports the target it reached)",
      _policy is _target.policy)
reset()
SCON.connect_client("target.example", "root", 22, password="target-pw", key_path=KEY_OK,
                    jump="ops@bastion.example:2222", jump_key_path=KEY_OK,
                    client_factory=FakeClient)
_target, _bastion = by_host("target.example"), by_host("bastion.example")
check("§2 ...the same key file reaches the target and the bastion",
      _target.kwargs.get("key_filename") == KEY_OK
      and _bastion.kwargs.get("key_filename") == KEY_OK
      and _bastion.kwargs.get("password") is None,
      str((_target.kwargs.get("key_filename"), _bastion.kwargs.get("key_filename"))))

reset()
_given = FakeClient()
SCON.connect_client("target.example", "root", 22, password="pw", client=_given,
                    jump="bastion.example", client_factory=FakeClient)
check("§2 a client handed IN is the target, and the hop is still opened",
      _given.kwargs.get("hostname") == "target.example"
      and isinstance(_given.kwargs.get("sock"), SCON._JumpSocket)
      and len(FakeClient.made) == 2, str([c.kwargs.get("hostname") for c in FakeClient.made]))
_given.close()
check("§2 closing the target closes the bastion client and the channel",
      _given.closed and by_host("bastion.example").closed
      and by_host("bastion.example").transport.channel.closed)

reset()
_roles = []


def _recording_factory(hostname, port, role):
    """A policy factory that records the endpoints and the roles it was asked about."""
    _roles.append((hostname, port, role))
    return HKP.SshKnownHostsPolicy(hostname=hostname, port=port)


SCON.connect_client("target.example", "root", 22, password="pw", jump="bastion.example",
                    client_factory=FakeClient, policy_factory=_recording_factory)
check("§2 `policy_factory` is asked for BOTH endpoints, each with its OWN role",
      set(_roles) == {("bastion.example", 22, SCON.ROLE_JUMP),
                      ("target.example", 22, SCON.ROLE_TARGET)} and len(_roles) == 2, str(_roles))
check("§2 the two roles are the declared vocabulary",
      (SCON.ROLE_TARGET, SCON.ROLE_JUMP) == ("target", "jump"))


def _refused_hop(text):
    """The exception a malformed hop raises before any client exists."""
    try:
        SCON.connect_client("target.example", "root", 22, jump=text, client_factory=FakeClient)
    except SCON.JumpSpecError as exc:
        return str(exc)
    return ""


reset()
check("§2 a malformed hop is refused BEFORE a client is built",
      _refused_hop("a,b") != "" and not FakeClient.made, str(len(FakeClient.made)))
check("§2 a `JumpSpec` is accepted by the builder as its parsed form",
      (reset(), SCON.connect_client("t.example", "u", 22, jump=SCON.JumpSpec("b.example"),
                                    client_factory=FakeClient)) and len(FakeClient.made) == 2)

reset(fail_host="bastion.example", failure=paramiko.AuthenticationException("bastion refused"))
try:
    SCON.connect_client("target.example", "root", 22, password="pw", jump="bastion.example",
                        client_factory=FakeClient)
    _hop_error = ""
except Exception as exc:  # noqa: BLE001 — the test reads the propagated class
    _hop_error = type(exc).__name__
check("§2 a failed bastion closes the bastion and the target client it never reached",
      _hop_error == "AuthenticationException"
      and by_policy("bastion.example").closed and by_policy("target.example").closed, _hop_error)

reset(fail_host="target.example", failure=paramiko.AuthenticationException("target refused"))
try:
    SCON.connect_client("target.example", "root", 22, password="pw", jump="bastion.example",
                        client_factory=FakeClient)
    _hop_error_2 = ""
except Exception as exc:  # noqa: BLE001
    _hop_error_2 = type(exc).__name__
check("§2 a failed target closes the hop it opened (no live bastion survives the refusal)",
      _hop_error_2 == "AuthenticationException"
      and by_host("bastion.example").closed and by_host("target.example").closed, _hop_error_2)


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the CLI `exec` path ==")
# ════════════════════════════════════════════════════════════════════════════

_STORE_PATH = os.path.join(WORK, "known_hosts_jump")
HKP.set_store(HKP.KnownHostsStore(_STORE_PATH))

reset()
_code, _out, _err = run_cli(["--project", MAP, "exec", "web-1", "uptime"])
_target, _bastion = by_host("10.0.0.5"), by_host("bastion.example")
check("§3 the CLI run reaches the target THROUGH the bastion and answers the remote stdout",
      _code == EX.EXIT_OK and _out == "ok\n"
      and _target is not None and _bastion is not None, f"{_code} / {_out!r} / {_err!r}")
check("§3 ...the hop is the ONE channel to the target, and the command runs on the TARGET",
      _bastion.transport.opened == [("direct-tcpip", ("10.0.0.5", 22), ("127.0.0.1", 0), 10.0)]
      and _target.kwargs.get("sock") is not None, str(_bastion.transport.opened))
check("§3 ...the bastion receives no command and no target password",
      not _bastion.commands and "password" not in _bastion.kwargs, str(_bastion.kwargs))
check("§3 the CLI closes the target, which closes the hop",
      _target.closed and _bastion.closed
      and _bastion.transport.channel.closed)

reset()
_code, _out, _err = run_cli(["--project", MAP, "exec", "web-1", "uptime", "--identity", KEY_OK])
_target, _bastion = by_host("10.0.0.5"), by_host("bastion.example")
check("§3 `--identity` is the operator's explicit key for BOTH endpoints",
      _code == EX.EXIT_OK and _target.kwargs.get("key_filename") == KEY_OK
      and _bastion.kwargs.get("key_filename") == KEY_OK
      and _bastion.kwargs.get("password") is None,
      str((_target.kwargs.get("key_filename"), _bastion.kwargs.get("key_filename"))))

reset()
_code, _out, _err = run_cli(["--project", MAP, "exec", "web-1", "uptime", "--accept-new"])
_target, _bastion = by_host("10.0.0.5"), by_host("bastion.example")
check("§3 `--accept-new` is the ONE pin opt-in for BOTH endpoints",
      _code == EX.EXIT_OK and _target.policy.accept_new is True
      and _bastion.policy.accept_new is True
      and _bastion.policy.expected == "",
      str((_target.policy.accept_new, _bastion.policy.accept_new)))

_named_key = paramiko.ECDSAKey.generate()
reset(remote_key=_named_key)
_fingerprint = HKP.fingerprint(_named_key)
_code, _out, _err = run_cli(["--project", MAP, "exec", "web-1", "uptime",
                             "--host-key", _fingerprint])
_target, _bastion = by_host("10.0.0.5"), by_host("bastion.example")
check("§3 `--host-key` names the TARGET alone; the bastion's policy carries no expected key",
      _code == EX.EXIT_OK and _target.policy.expected == _fingerprint
      and _bastion.policy.expected == "",
      f"{_code} / {_target.policy.expected} / {_bastion.policy.expected}")

reset()
_code, _out, _err = run_cli(["--project", BAD_JUMP, "exec", "web-1", "uptime"])
check("§3 a malformed jump field is a REFUSAL (2) and costs no connection",
      _code == EX.EXIT_REFUSAL and not FakeClient.made
      and "ONE host" in _err and "external terminal" in _err, f"{_code} / {_err!r}")


class _SecretStore:
    """The keyring seam: one secret bound to the target's endpoint."""

    def load_password(self, server_id, scope=None):
        return "target-secret"

    def stored_scope(self, server_id):
        return "tester@10.0.0.5:22"


_ORIGINAL_STORE = CREDENTIALS.get_credential_manager
CREDENTIALS.get_credential_manager = lambda: _SecretStore()
try:
    reset()
    _code, _out, _err = run_cli(["--project", MAP, "exec", "web-1", "uptime"])
    _target, _bastion = by_host("10.0.0.5"), by_host("bastion.example")
    check("§3 a PASSWORD target never hands that password to the bastion",
          _code == EX.EXIT_OK and _target.kwargs.get("password") == "target-secret"
          and "password" not in _bastion.kwargs
          and _bastion.kwargs.get("look_for_keys") is True,
          f"{_target.kwargs.get('password')!r} / {_bastion.kwargs.keys()}")
    check("§3 ...and the secret reaches no report",
          "target-secret" not in _out and "target-secret" not in _err)
finally:
    CREDENTIALS.get_credential_manager = _ORIGINAL_STORE

reset(fail_host="bastion.example", failure=paramiko.AuthenticationException("no"))
_code, _out, _err = run_cli(["--project", MAP, "exec", "web-1", "uptime"])
check("§3 a refused bastion is `auth` (3) and both halves are closed",
      _code == EX.EXIT_AUTH and by_policy("bastion.example").closed
      and by_policy("10.0.0.5").closed, f"{_code} / {_err!r}")
check("§3 the CLI keeps its credential policy: no stdin, no argv password",
      "sys.stdin" not in read("cli/exec.py") and "--password" not in read("cli/exec.py"))


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the GUI wiring and the no-password rule ==")
# ════════════════════════════════════════════════════════════════════════════

_TERMINAL = read("modules/ssh_terminal.py")
_PAGE = read("modules/terminal_page.py")
_WORKER = read("modules/ssh_worker.py")
_COLLECTOR = read("services/system_info_collector.py")
_DIALOG = read("dialogs/ssh_connect_dialog.py")
_SERVER = read("models/server.py")
_CONNECT = read("modules/ssh_connect.py")
check("§4 `ServerData.jump_host` names the internal hop and the external chain's home",
      "direct-tcpip" in _SERVER and "external" in _SERVER)
check("§4 the terminal thread carries the field and hands it to the ONE builder",
      "jump_host=" in _TERMINAL and "jump=self.jump_host" in _TERMINAL
      and "jump_key_path=self.key_path" in _TERMINAL)
check("§4 the session page builds the thread from its node's field",
      "jump_host=getattr(self.server_data, \"jump_host\", \"\")" in _PAGE)
check("§4 the one-shot worker carries the field, and the connect dialog passes it",
      "jump_host: str = \"\"" in _WORKER and "jump=self.jump_host" in _WORKER
      and "jump_host=getattr(self.server_data, \"jump_host\", \"\")" in _DIALOG)
check("§4 the info collector (its OWN connection) mirrors the session's hop",
      "jump=getattr(self.data, \"jump_host\", \"\")" in _COLLECTOR
      and "jump_key_path=self.data.key_path" in _COLLECTOR)
check("§4 the plugin runner follows it too, over the internal facts (a plugin never sees the field)",
      "jump=jump_host" in read("modules/plugin_runner.py")
      and "jump_key_path=key_path" in read("modules/plugin_runner.py")
      and "jump_host" in read("ui/main_window_plugins.py"))
check("§4 the bastion is built with `password=\"\"` — a target password is never offered to it",
      "password=\"\", key_path=jump_key_path" in _CONNECT
      and "jump_key_path=credential.key_path" in read("cli/exec.py"))
check("§4 the hop is ONE level: `_open_jump_socket()` does not forward a `jump`",
      "jump=" not in _CONNECT.split("def _open_jump_socket", 1)[1].split("def connect_client", 1)[0])
check("§4 the target's `sock` is the wrapping channel, so `close()` tears both halves down",
      "kwargs[\"sock\"] = jump_socket" in _CONNECT and "class _JumpSocket" in _CONNECT)
check("§4 the pure reader lives in ONE module and is re-exported where the hop opens",
      SCON.parse_jump is JH.parse_jump and SCON.JumpSpec is JH.JumpSpec
      and "tests/test_jump_host.py" in (SCON.__doc__ or ""))


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check("§5 this release is v1.15.3 (the internal jump host slot)",
      EXPECTED_APP_VERSION == "1.15.3" and releases_at_least(EXPECTED_APP_VERSION, "1.15.3"),
      EXPECTED_APP_VERSION)
check("§5 the slot adds NO i18n key (the parity pin stays 1256)",
      EXPECTED_I18N_KEYS == 1256
      and all(len({k for k in data if k not in ("name", "partial")}) == EXPECTED_I18N_KEYS
              for data in LANGS.values()),
      {code: len(data) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
check("§5 the family carries v1.15.3",
      "v1.15.3" in changelog_family_text(ROOT)
      and "v1.15.3" in changelog_family_text(ROOT, "DETAILS"))
check("§5 the project format and the dependency list did not move",
      version.VERSION_FORMAT == "0.9"
      and len([line for line in read("requirements.txt").splitlines()
               if line.strip() and not line.strip().startswith("#")]) == 4)
check("§5 the README quotes the real test-file count", "201 test files" in read("README.md"))


finish()
