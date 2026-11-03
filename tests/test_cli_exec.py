# -*- coding: utf-8 -*-
"""v1.15rc4 — `exec`: the three policies (guard, credential, host key) and the REMOTE exit code.
§1 the grammar and the registry (the five flags, the node/command pair, the flood stop); §2 the GUARD —
a destructive token refuses without its opt-in and `--dry-run` opens nothing; §3 the CREDENTIAL policy
(key file / endpoint-scoped keyring / agent, the missing-secret refusals, no stdin, no argv, no env);
§4 the HOST KEY — refusal by default, `--accept-new` pins through `replace()`, `--host-key` names one,
a CHANGED key is refused by every flag; §5 the wire and the code (the remote status IS the process code,
the pinned `--json` payload, the two streams); §6 the quiet no-Qt import and the release state.
Rule — `AGENTS.md` §4.35; contract — `CLI.md` §3.5, §5.1–§5.3; mechanism — `DOCUMENTATION.md` §80.
Run: python tests/test_cli_exec.py
"""
import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import threading

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least,
                     translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + sys.path (BEFORE any app import)

import paramiko  # noqa: E402

import cli.args as ARGS  # noqa: E402
import cli.credentials as CREDENTIALS  # noqa: E402
import cli.dispatch as DISPATCH  # noqa: E402
import cli.envelope as ENV  # noqa: E402
import cli.errors as ERR  # noqa: E402
import cli.exec as EXEC  # noqa: E402
import cli.exit_codes as EX  # noqa: E402
import cli.hostkeys as CLI_HOSTKEYS  # noqa: E402
import cli.verb_args as VERB_ARGS  # noqa: E402
import modules.command_guard as GUARD  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import modules.ssh_connect as SSH_CONNECT  # noqa: E402
import storage.app_config as APP_CONFIG  # noqa: E402
import version  # noqa: E402
from cli.main import main  # noqa: E402
from models.server import ServerData  # noqa: E402

CLI_MD = os.path.join(ROOT, "CLI.md")
CLI_DIR = os.path.join(ROOT, "cli")
LANGS = load_i18n_langs(ROOT)


def read(path):
    """The text of one repository file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def cli_sources():
    """`{file name: source}` of every module of `cli/` — the gate's own scan, no import."""
    out = {}
    for name in sorted(os.listdir(CLI_DIR)):
        if name.endswith(".py"):
            out[name] = read(os.path.join(CLI_DIR, name))
    return out


def run(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout text, stderr text)`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def fresh(code):
    """Run a snippet in a FRESH process rooted at the repository (the no-Qt gate's own shape)."""
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, env=env)


def document(text):
    """The ONE `--json` document of a run (a second document on stdout is a defect)."""
    stripped = str(text or "").strip()
    return json.loads(stripped) if stripped.startswith("{") else {}


def cost(arguments, reader=None):
    """The `CliError` ONE `exec` tail costs (`None` — it parsed cleanly)."""
    try:
        (reader or VERB_ARGS.read_exec)(arguments)
    except ERR.CliError as exc:
        return exc
    return None


def fixture(name, servers=()):
    """Write ONE SYNTHETIC project into the isolated work folder (never a real map file)."""
    payload = {"version": version.VERSION_FORMAT, "servers": list(servers), "connections": [],
               "notes": [], "groups": [], "background": None}
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def node(nid, alias, port=22, host="127.0.0.1", user="tester", **extra):
    """ONE synthetic server record."""
    record = {"id": nid, "alias": alias, "host": host, "ssh_port": port, "user": user}
    record.update(extra)
    return record


def data_of(text):
    """ONE field of a run's `data` payload (`{}` when the run answered an error instead)."""
    return document(text).get("data") or {}


def clear_cfg():
    """Drop the isolated `config.json` — the guard's policy returns to its declared default."""
    try:
        os.remove(APP_CONFIG.CONFIG_FILE)
    except OSError:
        pass


# ── The `paramiko.SSHClient` seam ───────────────────────────────────────────────
class FakeChannel:
    """The status surface of ONE fake channel: the exit code and the event `recv_exit_status()` waits on."""

    def __init__(self, code=0):
        self.exit_status = int(code)
        self.status_event = threading.Event()
        self.status_event.set()

    def recv_exit_status(self):
        """Answer the configured remote code (the real one waits on `status_event`)."""
        return self.exit_status


class FakeStream:
    """One fake stdout/stderr: the bytes and the channel that carries the status."""

    def __init__(self, payload, channel):
        self._payload = payload
        self.channel = channel

    def read(self, size=None):
        """Answer the configured bytes ONCE (a bounded reader asks again and gets EOF)."""
        payload, self._payload = self._payload, b""
        return payload


class BlockedStream(RuntimeError):
    """A stream read SEQUENTIALLY — the partner never started, which the pair forbids."""


class PairedStream:
    """A stream that only answers once its PARTNER is being read too (`Session.run()` reads both).

    It is the deadlock probe: paramiko's window is per CHANNEL, so reading one stream to EOF while the
    other fills its buffer stalls the remote. A sequential reader is REFUSED here rather than answered.
    """

    def __init__(self, payload, channel):
        self._payload = payload
        self.channel = channel
        self.started = threading.Event()
        self.peer = None

    def read(self, size=None):
        """Wait for the partner's own `read()` (2 s), then answer the bytes ONCE."""
        self.started.set()
        if not self.peer.started.wait(2.0):
            raise BlockedStream("the other stream was never read")
        payload, self._payload = self._payload, b""
        return payload


class FakeClient:
    """The `paramiko.SSHClient` seam: records what the verb asked and answers what the test set."""

    instances = []
    answer = (0, b"", b"")      # (exit code, stdout bytes, stderr bytes)
    on_connect = None           # callable(client) — may raise, or pin a key through the policy
    on_command = None           # callable() — may raise (the timeout/IO failures of a read)
    streams = None              # callable(channel) -> (stdout, stderr) — the deadlock probe

    def __init__(self):
        self.host_keys = paramiko.hostkeys.HostKeys()
        self.policy = None
        self.kwargs = {}
        self.commands = []
        self.closed = False
        FakeClient.instances.append(self)

    def set_missing_host_key_policy(self, policy):
        """Keep the policy paramiko would consult (the shipped `apply_to_client()` calls this)."""
        self.policy = policy

    def get_host_keys(self):
        """The client's known-hosts map (a real `HostKeys`, so a pin loaded from the store lands)."""
        return self.host_keys

    def connect(self, **kwargs):
        """Record the built kwargs and run the configured hook (which may raise)."""
        self.kwargs = dict(kwargs)
        if FakeClient.on_connect is not None:
            FakeClient.on_connect(self)

    def exec_command(self, command, timeout=None):
        """Answer the configured streams for ONE command (the hook may raise first)."""
        self.commands.append((command, timeout))
        if FakeClient.on_command is not None:
            FakeClient.on_command()
        code, out, err = FakeClient.answer
        channel = FakeChannel(code)
        if FakeClient.streams is not None:
            return (FakeStream(b"", channel),) + tuple(FakeClient.streams(channel))
        return FakeStream(b"", channel), FakeStream(out, channel), FakeStream(err, channel)

    def close(self):
        """Mark the client closed (the verb closes it on every path)."""
        self.closed = True


def reset_clients(answer=(0, b"", b""), on_connect=None, on_command=None, streams=None):
    """Return the seam to a known state for the next run."""
    FakeClient.instances.clear()
    FakeClient.answer = answer
    FakeClient.on_connect = on_connect
    FakeClient.on_command = on_command
    FakeClient.streams = streams
    EXEC.CLIENT_FACTORY = FakeClient


MAP = fixture("exec-map.json", [node("srv-web", "web-1"), node("srv-db", "db-1", 2222)])
EMPTY = fixture("exec-empty.json")
TWINS = fixture("exec-twins.json", [node("srv-1", "twin"), node("srv-2", "twin")])
KEY_OK = os.path.join(WORK, "id_test")
with open(KEY_OK, "w", encoding="utf-8") as _handle:
    _handle.write("-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----\n")
KEY_GONE = os.path.join(WORK, "id_missing")


# ════════════════════════════════════════════════════════════════════════════
# §1 The grammar and the registry
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the `exec` grammar and the registry ==")

_ROWS = dict(DISPATCH.registered())
check("§1 the lazy load registers the SIX verbs of this build (the exec row included)",
      set(_ROWS) == {"inventory", "connections", "status", "doctor", "exec", "hostkey"},
      str(sorted(_ROWS)))
check("§1 `cli.exec` is the fifth built-in module (ONE declaration of that load)",
      DISPATCH.BUILTIN_VERB_MODULES == ("cli.inventory", "cli.connections", "cli.status",
                                        "cli.doctor", "cli.exec", "cli.hostkey"),
      str(DISPATCH.BUILTIN_VERB_MODULES))
check("§1 the row declares 2..MAX_ARGUMENTS, a verdict and the `raw_code` passthrough",
      DISPATCH.VERBS["exec"].min_args == 2
      and DISPATCH.VERBS["exec"].max_args == VERB_ARGS.MAX_ARGUMENTS == 32
      and callable(DISPATCH.VERBS["exec"].verdict) and DISPATCH.VERBS["exec"].raw_code is True)
check("§1 `exec` declares the verb's OWN grammar, apart from the flag table and the positional pair",
      VERB_ARGS.EXEC_VERBS == ("exec",) and set(VERB_ARGS.ARGUMENT_TABLE) == {"inventory",
                                                                            "connections"}
      and VERB_ARGS.POSITIONAL_VERBS == ("status", "doctor"),
      f"{VERB_ARGS.EXEC_VERBS} / {VERB_ARGS.ARGUMENT_TABLE}")

_PARSED = VERB_ARGS.read_exec(["web-1", "uptime", "--identity", KEY_OK, "--accept-new",
                               "--host-key", "SHA256:abc", "--allow-destructive", "--dry-run"])
check("§1 `<node> \"<command>\"` is read as the pair, and the FIVE policy flags beside it",
      (_PARSED.node, _PARSED.command) == ("web-1", "uptime")
      and _PARSED.identity == KEY_OK and _PARSED.accept_new is True
      and _PARSED.host_key == "SHA256:abc" and _PARSED.allow_destructive is True
      and _PARSED.dry_run is True, str(_PARSED))
check("§1 an UNQUOTED command is the words after the node, joined by ONE space (taken verbatim)",
      VERB_ARGS.read_exec(["web-1", "ls", "/var/tmp"]).command == "ls /var/tmp"
      and VERB_ARGS.read_exec(["web-1", "uptime -p"]).command == "uptime -p")
check("§1 ...while a flag-shaped word INSIDE the command must be quoted (it is a flag otherwise)",
      VERB_ARGS.read_exec(["web-1", "df -h"]).command == "df -h"
      and (lambda exc: exc is not None and exc.code == EX.EXIT_USAGE and "<command>" in exc.hint)(
          cost(["web-1", "df", "-h"])), str(cost(["web-1", "df", "-h"])))
check("§1 a flag may stand BEFORE the node as well as after the command (the tail is ONE table)",
      (lambda r: (r.node, r.command, r.dry_run))(
          VERB_ARGS.read_exec(["--dry-run", "web-1", "ls"])) == ("web-1", "ls", True))
check("§1 `--option=value` is the same thing for both value flags, and a repeat takes the LAST",
      VERB_ARGS.read_exec(["n", "c", f"--identity={WORK}"]).identity == WORK
      and VERB_ARGS.read_exec(["n", "c", "--identity", "a", "--identity", "b"]).identity == "b")
check("§1 a missing node, a missing command and a value-less flag are USAGE errors",
      all(cost(tail) is not None and cost(tail).code == EX.EXIT_USAGE
          for tail in ([], ["--dry-run"], ["web-1"], ["web-1", "ls", "--identity"],
                       ["web-1", "ls", "--host-key"], ["web-1", "ls", "--identity="])))
check("§1 an UNDECLARED flag is refused by name, and a switch refuses a `=value`",
      (lambda exc: exc is not None and exc.code == EX.EXIT_USAGE and "--bogus" in exc.message)(
          cost(["web-1", "ls", "--bogus"]))
      and cost(["web-1", "ls", "--dry-run=1"]) is not None
      and cost(["web-1", "ls", "--accept-new=yes"]) is not None)
check("§1 the help text lists `exec` with its summary (the registry's own row)",
      any(line.strip().startswith("exec") and "<command>" in line
          for line in ARGS.usage_text(DISPATCH.registered()).splitlines()),
      [line for line in ARGS.usage_text(DISPATCH.registered()).splitlines() if "exec" in line])
_CODE, _OUT, _ERR = run(["exec", "--json"])
check("§1 the row's argument count refuses a bare `exec` BEFORE the handler runs",
      _CODE == EX.EXIT_USAGE and "exec takes 2..32" in _ERR, f"{_CODE} / {_ERR!r}")


# ════════════════════════════════════════════════════════════════════════════
# §2 The GUARD policy
# ════════════════════════════════════════════════════════════════════════════
print("== §2 the command guard is ASKED, not skipped ==")

reset_clients()
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "rm -rf /var/tmp/x"])
check("§2 a DESTRUCTIVE command is refused (2) without its opt-in — and no client was ever built",
      _CODE == EX.EXIT_REFUSAL and "rm -rf" in _ERR and not FakeClient.instances,
      f"{_CODE} / {_ERR!r} / built={len(FakeClient.instances)}")
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "reboot"])
_GUARD_DOC = document(_OUT)
check("§2 ...`--json` answers the refusal record with the TOKEN and the command it matched",
      _CODE == EX.EXIT_REFUSAL and _GUARD_DOC.get("ok") is False and _GUARD_DOC.get("data") is None
      and _GUARD_DOC.get("error", {}).get("kind") == "refusal"
      and "reboot" in _GUARD_DOC.get("error", {}).get("message", "")
      and "--allow-destructive" in _GUARD_DOC.get("error", {}).get("hint", ""),
      _OUT[:160])

reset_clients(answer=(0, b"done\n", b""))
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "uptime", "--allow-destructive"])
check("§2 `--allow-destructive` IS the human's answer: the command runs and its stdout is the report",
      _CODE == EX.EXIT_OK and _OUT == "done\n" and len(FakeClient.instances) == 1,
      f"{_CODE} / {_OUT!r}")

reset_clients()
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "rm -rf /var/tmp/x", "--dry-run"])
check("§2 `--dry-run` prints the verdict and the command it WOULD run, and exits 0",
      _CODE == EX.EXIT_OK and _OUT.splitlines() == ["guard: rm -rf", "command: rm -rf /var/tmp/x"]
      and not FakeClient.instances, f"{_CODE} / {_OUT!r} / built={len(FakeClient.instances)}")
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "rm -rf /x", "--dry-run"])
_DRY = data_of(_OUT)
check("§2 ...and under `--json` the same verdict is `data.guard`, with a null exit code",
      _CODE == EX.EXIT_OK and document(_OUT).get("ok") is True and _DRY.get("guard") == "rm -rf"
      and _DRY.get("dry_run") is True and _DRY.get("exit_code") is None
      and _DRY.get("stdout") == "" and _DRY.get("stderr") == "", _OUT[:200])
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "uptime", "--dry-run"])
check("§2 a CLEAN command's dry run says `none` (the verdict is always printed)",
      _CODE == EX.EXIT_OK and _OUT.splitlines() == ["guard: none", "command: uptime"], repr(_OUT))
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "uptime", "--dry-run",
                         "--identity", KEY_GONE])
check("§2 ...and the guard is asked BEFORE the credential (a dry run needs no secret at all)",
      _CODE == EX.EXIT_OK and "guard: none" in _OUT, f"{_CODE} / {_ERR!r}")

clear_cfg()
APP_CONFIG.save_config({"guard_commands": False})
try:
    reset_clients(answer=(0, b"ok\n", b""))
    _CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "reboot"])
    check("§2 the guard is the PURE classifier: `guard_commands: false` does NOT disarm the CLI",
          _CODE == EX.EXIT_REFUSAL and "reboot" in _ERR and not FakeClient.instances,
          f"{_CODE} / {_OUT!r} / {_ERR!r} / built={len(FakeClient.instances)}")
finally:
    clear_cfg()
check("§2 ...and the store is back to the declared default (the guard is ARMED again)",
      GUARD.needs_confirmation("reboot") == "reboot")
_SRC = cli_sources()
check("§2 the CLI asks the PURE classifier, never the dialog's `needs_confirmation()` door",
      "dangerous_token" in _SRC.get("exec.py", "")
      and "needs_confirmation" not in _SRC.get("exec.py", ""),
      [line.strip() for line in _SRC.get("exec.py", "").splitlines()
       if "dangerous_token" in line or "needs_confirmation" in line])
check("§2 the CLI never ANSWERS its own guard question (no dialog call anywhere in `cli/`)",
      not [name for name, source in _SRC.items() if "confirm(" in source.replace("_confirmation(", "")
           .replace("needs_confirmation(", "")],
      [name for name, source in _SRC.items() if "confirm(" in source])


# ════════════════════════════════════════════════════════════════════════════
# §3 The CREDENTIAL policy
# ════════════════════════════════════════════════════════════════════════════
print("== §3 the credential: key file / keyring / agent ==")


class FakeStore:
    """The credential store seam: one secret and one stored scope, keyed by node id."""

    def __init__(self, secret=None, scope="", fail=False):
        self.secret = secret
        self.scope = scope
        self.fail = fail
        self.asked = []

    def load_password(self, server_id, scope=None):
        """The scoped read — the shipped rule: a secret bound to ANOTHER endpoint answers `None`."""
        self.asked.append(("load", server_id, scope))
        if self.fail:
            raise RuntimeError("the keyring is gone")
        if self.secret is None:
            return None
        return self.secret if not scope or not self.scope or scope == self.scope else None

    def stored_scope(self, server_id):
        """The endpoint the secret was saved for."""
        self.asked.append(("scope", server_id))
        if self.fail:
            raise RuntimeError("the keyring is gone")
        return self.scope


_BARE = ServerData(id="srv-bare", alias="bare", host="127.0.0.1", user="tester", ssh_port=22)
check("§3 no key file and no stored secret resolves to the AGENT — the third declared source",
      CREDENTIALS.resolve(_BARE, manager=FakeStore()).branch == CREDENTIALS.CRED_AGENT)
check("§3 the scope it resolved against is the shipped `node_scope()` spelling",
      CREDENTIALS.resolve(_BARE, manager=FakeStore()).scope == "tester@127.0.0.1:22")
check("§3 a keyring secret bound to the endpoint is the PASSWORD branch, and travels with it",
      (lambda c: (c.branch, c.password))(CREDENTIALS.resolve(
          _BARE, manager=FakeStore(secret="s3cret", scope="tester@127.0.0.1:22")))
      == (CREDENTIALS.CRED_PASSWORD, "s3cret"))
check("§3 `--identity PATH` selects the key branch over everything else",
      (lambda c: (c.branch, c.key_path))(CREDENTIALS.resolve(
          _BARE, identity=KEY_OK, manager=FakeStore(secret="pw", scope="tester@127.0.0.1:22")))
      == (CREDENTIALS.CRED_KEY, KEY_OK))
check("§3 the node's OWN `key_path` is the second door (no flag needed)",
      (lambda c: (c.branch, c.key_path))(CREDENTIALS.resolve(
          ServerData(id="k", alias="k", host="h", user="u", key_path=KEY_OK),
          manager=FakeStore(secret="pw", scope="u@h:22"))) == (CREDENTIALS.CRED_KEY, KEY_OK))

def refusal_of(*args, **kwargs):
    """The `CliError` a resolution raises (`None` — it resolved a credential instead)."""
    try:
        CREDENTIALS.resolve(*args, **kwargs)
    except ERR.CliError as exc:
        return exc
    return None


_KEYLESS = ServerData(id="k", alias="k", host="h", user="u", key_path=KEY_GONE)
check("§3 a missing secret is a REFUSAL (2): an `--identity` that names no file",
      (lambda exc: exc is not None and exc.code == EX.EXIT_REFUSAL
       and KEY_GONE in exc.message)(refusal_of(_BARE, identity=KEY_GONE, manager=FakeStore())))
check("§3 a missing secret is a REFUSAL (2): the node's own key file that is gone",
      (lambda exc: exc is not None and exc.code == EX.EXIT_REFUSAL
       and KEY_GONE in exc.message)(refusal_of(_KEYLESS, manager=FakeStore())))
_MISSING = refusal_of(_BARE, manager=FakeStore(secret="pw", scope="other@elsewhere:22"))
check("§3 a missing secret is a REFUSAL (2): a secret stored for ANOTHER endpoint",
      _MISSING is not None and _MISSING.code == EX.EXIT_REFUSAL, repr(_MISSING))
check("§3 ...and its sentence names BOTH endpoints and the door that stores the right one",
      _MISSING is not None and "other@elsewhere:22" in _MISSING.message
      and "tester@127.0.0.1:22" in _MISSING.message and "sshcanvas" in _MISSING.hint,
      f"{_MISSING.sentence() if _MISSING else ''}")
check("§3 a broken store degrades to the agent branch, never a traceback",
      CREDENTIALS.resolve(_BARE, manager=FakeStore(fail=True)).branch == CREDENTIALS.CRED_AGENT
      and CREDENTIALS.resolve(_BARE, manager=None).branch == CREDENTIALS.CRED_AGENT)
check("§3 the three sources are the declared ones, and nothing else",
      CREDENTIALS.CRED_SOURCES == ("key", "password", "agent"))
check("§3 NO secret channel but the three: no stdin, no getpass, no environment, no argv flag",
      not any(token in "".join(_SRC.values())
              for token in ("sys.stdin", "input(", "getpass", "os.environ", "os.getenv",
                            "--password", "PASSWORD=")),
      [token for token in ("sys.stdin", "input(", "getpass", "os.environ", "os.getenv",
                           "--password", "PASSWORD=")
       if token in "".join(_SRC.values())])

reset_clients(answer=(0, b"ok\n", b""))
_ORIGINAL_MANAGER = CREDENTIALS.get_credential_manager
CREDENTIALS.get_credential_manager = lambda: FakeStore(secret="S3cr3t!",
                                                       scope="tester@127.0.0.1:22")
try:
    _CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "uptime"])
    _CRED_DOC = data_of(_OUT)
    check("§3 the PASSWORD branch reaches the builder as the connect password",
          _CODE == EX.EXIT_OK and _CRED_DOC.get("auth") == "password"
          and FakeClient.instances[0].kwargs.get("password") == "S3cr3t!"
          and FakeClient.instances[0].kwargs.get("look_for_keys") is False,
          f"{_CODE} / {_CRED_DOC.get('auth')} / {FakeClient.instances[0].kwargs.keys()}")
    check("§3 ...and the secret reaches NO report: not stdout, not stderr, not the envelope",
          "S3cr3t!" not in _OUT and "S3cr3t!" not in _ERR, _OUT[:160])
finally:
    CREDENTIALS.get_credential_manager = _ORIGINAL_MANAGER

reset_clients(answer=(0, b"ok\n", b""))
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "uptime", "--identity", KEY_OK])
check("§3 `--identity PATH` reaches the builder as `key_filename` (the key branch)",
      _CODE == EX.EXIT_OK and FakeClient.instances[0].kwargs.get("key_filename") == KEY_OK
      and FakeClient.instances[0].kwargs.get("allow_agent") is True,
      str(FakeClient.instances[0].kwargs))
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "uptime"])
check("§3 the AGENT branch is the shipped fallback (look_for_keys + allow_agent, no secret of ours)",
      _CODE == EX.EXIT_OK and FakeClient.instances[-1].kwargs.get("look_for_keys") is True
      and FakeClient.instances[-1].kwargs.get("allow_agent") is True
      and "password" not in FakeClient.instances[-1].kwargs,
      str(FakeClient.instances[-1].kwargs))
check("§3 ...and the transport factory is the shipped one (a stdin prompt can never fire)",
      callable(FakeClient.instances[-1].kwargs.get("transport_factory")))


# ════════════════════════════════════════════════════════════════════════════
# §4 The HOST-KEY policy
# ════════════════════════════════════════════════════════════════════════════
print("== §4 the host key: refused by default, pinned on an opt-in ==")

HKP.set_store(HKP.KnownHostsStore(os.path.join(WORK, "known_hosts_cli")))
_STORE = HKP.get_store()
KEY_A = paramiko.ECDSAKey.generate()
KEY_B = paramiko.ECDSAKey.generate()
KEY_RSA = paramiko.RSAKey.generate(1024)


def policy_verdict(policy, key, name="h-cli"):
    """Call the policy's `missing_host_key()` and answer `(raised message, policy)`."""
    try:
        policy.missing_host_key(None, name, key)
    except HKP.HostKeyRejected as exc:
        return str(exc), policy
    return "", policy


_MESSAGE, _POLICY = policy_verdict(CLI_HOSTKEYS.CliHostKeyPolicy("h-cli", 22), KEY_A)
check("§4 an UNKNOWN key is a REFUSAL — the policy never asks and never pins",
      _MESSAGE and "not pinned" in _MESSAGE and _POLICY.pinned is False
      and _STORE.lookup("h-cli") is None, f"{_MESSAGE!r}")
check("§4 ...and the refusal prints the fingerprint the box presented, for an out-of-band check",
      HKP.fingerprint(KEY_A) in _MESSAGE and KEY_A.get_name() in _MESSAGE, _MESSAGE)

_NOTES = []
_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-accept", 22, accept_new=True, note=_NOTES.append), KEY_A)
check("§4 `--accept-new` pins the key and says so on the diagnostics channel",
      not _MESSAGE and _POLICY.pinned is True and _POLICY.accepted_new_key is True
      and len(_NOTES) == 1 and "pinned the host key of h-accept" in _NOTES[0], repr(_NOTES))
check("§4 ...through the ONE replacement writer: the store really holds it now",
      _STORE.lookup("h-accept") is not None
      and HKP.fingerprint(_STORE.lookup("h-accept")[KEY_A.get_name()])
      == HKP.fingerprint(KEY_A))

_STORE.pin("h-swap", KEY_RSA.get_name(), KEY_RSA)
_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-swap", 22, accept_new=True), KEY_A)
_RECORDED = dict(_STORE.lookup("h-swap") or {})
check("§4 ...and every OTHER algorithm of that name leaves in the SAME publish (replace(), N120)",
      not _MESSAGE and set(_RECORDED) == {KEY_A.get_name()}, str(sorted(_RECORDED)))

_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-pin", 22, expected=HKP.fingerprint(KEY_B)), KEY_A)
check("§4 `--host-key FP` refuses a key that is not the one it names",
      _MESSAGE and "not the" in _MESSAGE and HKP.fingerprint(KEY_B) in _MESSAGE
      and _STORE.lookup("h-pin") is None, f"{_MESSAGE!r}")
_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-pin", 22, expected="sha256" + HKP.fingerprint(KEY_A)[6:]), KEY_A)
check("§4 ...and pins the one it DOES name (the `SHA256:` head is matched either way)",
      not _MESSAGE and _POLICY.pinned is True and _STORE.lookup("h-pin") is not None,
      f"{_MESSAGE!r}")
check("§4 the fingerprint normaliser is ONE reader",
      CLI_HOSTKEYS.normalize_fingerprint("") == ""
      and CLI_HOSTKEYS.normalize_fingerprint(" sha256:abc ") == "SHA256:abc"
      and CLI_HOSTKEYS.normalize_fingerprint("SHA256:abc") == "SHA256:abc"
      and CLI_HOSTKEYS.normalize_fingerprint("abc") == "abc")

reset_clients(on_connect=lambda client: client.policy.missing_host_key(
    client, "127.0.0.1", KEY_A))
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "uptime"])
check("§4 the WIRING holds: an unknown key on a real run is a `refusal` (2), and the pin stays empty",
      _CODE == EX.EXIT_REFUSAL and document(_OUT).get("error", {}).get("kind") == "refusal"
      and HKP.get_store().lookup("127.0.0.1") is None, f"{_CODE} / {_OUT[:160]!r}")
check("§4 ...and the client is CLOSED on that path (no half-open socket survives a refusal)",
      FakeClient.instances[0].closed is True)

reset_clients(on_connect=lambda client: client.policy.missing_host_key(
    client, "127.0.0.1", KEY_A))
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "uptime", "--accept-new"])
check("§4 `--accept-new` on a real run pins the key and reports it on stderr",
      _CODE == EX.EXIT_OK and "pinned the host key of 127.0.0.1" in _ERR
      and HKP.get_store().lookup("127.0.0.1") is not None, f"{_CODE} / {_ERR!r}")

reset_clients(on_connect=lambda client: (_ for _ in ()).throw(
    paramiko.BadHostKeyException("127.0.0.1", KEY_B, KEY_A)))
for _flag in ((), ("--accept-new",)):
    _CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "uptime", *_flag])
    check(f"§4 a CHANGED key is refused by `--accept-new` too{'' if _flag else ' (and by default)'}",
          _CODE == EX.EXIT_REFUSAL
          and "CHANGED" in document(_OUT).get("error", {}).get("message", ""),
          f"{_CODE} / {_OUT[:160]!r}")

_BROKEN = os.path.join(WORK, "known_hosts_broken")
with open(_BROKEN, "w", encoding="utf-8") as _handle:
    _handle.write("h-broken ssh-rsa NOT-A-KEY\n")
HKP.set_store(HKP.KnownHostsStore(_BROKEN))
_MESSAGE, _POLICY = policy_verdict(
    CLI_HOSTKEYS.CliHostKeyPolicy("h-broken", 22, accept_new=True), KEY_A)
check("§4 a store that cannot be READ refuses the run rather than accepting an unremembered key",
      _MESSAGE and "refuses" in _MESSAGE and _POLICY.pinned is False
      and open(_BROKEN, encoding="utf-8").read().endswith("NOT-A-KEY\n"), f"{_MESSAGE!r}")
HKP.set_store(HKP.KnownHostsStore(os.path.join(WORK, "known_hosts_cli")))


# ════════════════════════════════════════════════════════════════════════════
# §5 The wire, the exit code and the two streams
# ════════════════════════════════════════════════════════════════════════════
print("== §5 the remote exit code IS the process code ==")

reset_clients(answer=(7, b"hello\n", b"warning: x\n"))
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "uptime"])
check("§5 the process exits with the REMOTE code, and the remote stdout IS the text form",
      _CODE == 7 and _OUT == "hello\n", f"{_CODE} / {_OUT!r}")
check("§5 ...the remote stderr goes to the diagnostics channel, never to the report",
      _ERR.strip() == "warning: x" and "warning" not in _OUT, f"{_ERR!r}")
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "uptime"])
_EXEC_DOC = document(_OUT)
_EXEC_DATA = _EXEC_DOC.get("data") or {}
check("§5 ...and `--json` answers ONE envelope after the same run (ok true, the code in `data`)",
      _CODE == 7 and tuple(_EXEC_DOC) == ENV.ENVELOPE_KEYS and _EXEC_DOC.get("ok") is True
      and _EXEC_DOC.get("error") is None and _EXEC_DOC.get("verb") == "exec"
      and _OUT.strip().count("\n}") == 1, _OUT[:120])
check("§5 the payload's keys are the PINNED ones, in the pinned order",
      tuple(_EXEC_DATA) == EXEC.DATA_KEYS
      == ("project", "node", "command", "dry_run", "guard", "auth", "exit_code", "stdout",
          "stderr", "truncated"), str(tuple(_EXEC_DATA)))
check("§5 ...carrying the project, the node's identity, the command and the remote answer",
      _EXEC_DATA.get("project") == MAP and _EXEC_DATA.get("command") == "uptime"
      and _EXEC_DATA.get("exit_code") == 7 and _EXEC_DATA.get("stdout") == "hello\n"
      and _EXEC_DATA.get("stderr") == "warning: x\n" and _EXEC_DATA.get("dry_run") is False
      and _EXEC_DATA.get("guard") == "" and _EXEC_DATA.get("truncated") is False,
      str(_EXEC_DATA))
check("§5 ...and the node is the five public facts, never a credential",
      _EXEC_DATA.get("node") == {"id": "srv-web", "alias": "web-1", "user": "tester",
                                 "host": "127.0.0.1", "port": 22},
      str(_EXEC_DATA.get("node")))
check("§5 the timeout budget travels to BOTH waits (the connect and the command)",
      FakeClient.instances[-1].kwargs.get("timeout") == 10.0
      and FakeClient.instances[-1].commands[-1][1] == 10.0,
      f"{FakeClient.instances[-1].kwargs.get('timeout')} / {FakeClient.instances[-1].commands}")
_CODE, _OUT, _ERR = run(["--timeout", "5", "--project", MAP, "exec", "web-1", "sleep 1"])
check("§5 `--timeout` moves both of them (one declaration, one budget)",
      FakeClient.instances[-1].kwargs.get("timeout") == 5.0
      and FakeClient.instances[-1].commands[-1][1] == 5.0)

reset_clients(answer=(0, b"", b""))


def paired_streams(channel):
    """Two streams that only answer when BOTH are being read (`Session.run()`'s pair of readers)."""
    out, err = PairedStream(b"paired-out\n", channel), PairedStream(b"paired-err\n", channel)
    out.peer, err.peer = err, out
    return out, err


reset_clients(streams=paired_streams)
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "noisy"])
check("§5 the two streams are read CONCURRENTLY (a full window on one never deadlocks the other)",
      _CODE == EX.EXIT_OK and _OUT == "paired-out\n" and _ERR.strip() == "paired-err",
      f"{_CODE} / {_OUT!r} / {_ERR!r}")
reset_clients(answer=(0, b"", b""))

_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "true"])
check("§5 a silent, successful command prints not one line and exits 0",
      _CODE == EX.EXIT_OK and _OUT == "" and _ERR == "", f"{_CODE} / {_OUT!r} / {_ERR!r}")
reset_clients(answer=(255, b"", b""))
_CODE, _OUT, _ERR = run(["--project", MAP, "exec", "web-1", "exit 255"])
check("§5 the passthrough keeps the width of an exit status (255 stays 255, never 1)",
      _CODE == 255, str(_CODE))
check("§5 a `raw_code` row passes a remote code through; every other row keeps the seven classes",
      DISPATCH._answer_code(DISPATCH.Verb("probe-raw", "s", handler=lambda c, a: {},
                                          verdict=lambda d: 7, raw_code=True), {}) == 7
      and DISPATCH._answer_code(DISPATCH.Verb("probe-plain", "s", handler=lambda c, a: {},
                                              verdict=lambda d: 7), {}) == EX.EXIT_USAGE
      and DISPATCH._answer_code(DISPATCH.Verb("probe-wide", "s", handler=lambda c, a: {},
                                              verdict=lambda d: 999, raw_code=True),
                                {}) == EX.EXIT_USAGE)
check("§5 the row's own verdict reads the payload and answers 0 for a dry run",
      EXEC.verdict({"exit_code": 7}) == 7 and EXEC.verdict({"exit_code": None}) == 0
      and EXEC.verdict({}) == 0 and EXEC.verdict({"exit_code": "x"}) == 0)

_CLASSES = (
    (paramiko.AuthenticationException("bad login"), EX.EXIT_AUTH),
    (paramiko.PasswordRequiredException("encrypted"), EX.EXIT_AUTH),
    (SSH_CONNECT.ConnectionCancelled("no surface for a second factor"), EX.EXIT_AUTH),
    (paramiko.ssh_exception.SSHException("no method left"), EX.EXIT_NETWORK),
    (paramiko.BadHostKeyException("h", KEY_A, KEY_B), EX.EXIT_REFUSAL),
    (HKP.HostKeyRejected("not pinned"), EX.EXIT_REFUSAL),
    (paramiko.ssh_exception.NoValidConnectionsError(
        errors={("127.0.0.1", 22): "refused"}), EX.EXIT_NETWORK),
    (socket.gaierror("no such host"), EX.EXIT_NETWORK),
    (ConnectionRefusedError("refused"), EX.EXIT_NETWORK),
    (socket.timeout("slow"), EX.EXIT_TIMEOUT),
    (TimeoutError("slow"), EX.EXIT_TIMEOUT),
)
check("§5 every failure answers its DECLARED class (one table, ten exception types)",
      all(EXEC.classify(exc).code == code for exc, code in _CLASSES),
      [(type(exc).__name__, EXEC.classify(exc).code, code) for exc, code in _CLASSES])
check("§5 ...and a foreign exception is the network class with its own text, never a traceback",
      isinstance(EXEC.classify(ValueError("strange")), ERR.CliError)
      and EXEC.classify(ValueError("strange")).code == EX.EXIT_NETWORK)

for _exc, _code, _tail in ((paramiko.AuthenticationException("nope"), EX.EXIT_AUTH, ()),
                           (paramiko.BadHostKeyException("h", KEY_B, KEY_A), EX.EXIT_REFUSAL, ())):
    reset_clients(on_connect=lambda client, e=_exc: (_ for _ in ()).throw(e))
    _CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "uptime", *_tail])
    check(f"§5 a {type(_exc).__name__} on the wire answers {_code} — a bad secret is never a refusal",
          _CODE == _code and document(_OUT).get("error", {}).get("code") == _code,
          f"{_CODE} / {_OUT[:140]!r}")
reset_clients(answer=(0, b"", b""), on_command=lambda: (_ for _ in ()).throw(socket.timeout("slow")))
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "web-1", "sleep 99"])
check("§5 a command that outlives the budget is `timeout` (6), never a hang and never a traceback",
      _CODE == EX.EXIT_TIMEOUT and document(_OUT).get("error", {}).get("kind") == "timeout",
      f"{_CODE} / {_OUT[:140]!r}")

reset_clients(answer=(0, b"x\n", b""))
_CODE, _OUT, _ERR = run(["--json", "--project", MAP, "exec", "db-1", "hostname"])
check("§5 the node is selected by id OR alias over the SHIPPED reader (a port above 22 included)",
      _CODE == EX.EXIT_OK and data_of(_OUT).get("node", {}).get("port") == 2222
      and data_of(_OUT).get("node", {}).get("alias") == "db-1", _OUT[:160])
_CODE, _OUT, _ERR = run(["--json", "--project", TWINS, "exec", "twin", "uptime"])
check("§5 a duplicated alias is an ambiguous selection: USAGE, with the id door in the hint",
      _CODE == EX.EXIT_USAGE and "names 2 nodes" in document(_OUT).get("error", {}).get("message",
                                                                                    ""), _OUT[:160])
reset_clients()
_CODE, _OUT, _ERR = run(["--json", "--project", EMPTY, "exec", "web-1", "uptime"])
check("§5 ...and a node the project does not hold is `not_found` (5) BEFORE any connection",
      _CODE == EX.EXIT_NOT_FOUND and not FakeClient.instances, _OUT[:140])
_BEFORE = open(MAP, "rb").read()
reset_clients(answer=(0, b"ok\n", b""))
run(["--project", MAP, "exec", "web-1", "uptime", "--dry-run"])
run(["--json", "--project", MAP, "exec", "web-1", "uptime"])
check("§5 a run NEVER writes its project (the bytes are unchanged)",
      open(MAP, "rb").read() == _BEFORE)


# ════════════════════════════════════════════════════════════════════════════
# §6 The quiet no-Qt import and the release state
# ════════════════════════════════════════════════════════════════════════════
print("== §6 the quiet no-Qt import and the release state ==")

_MODULES = sorted("cli" if name == "__init__.py" else f"cli.{name[:-3]}"
                  for name in _SRC if name.endswith(".py"))
_LOUD, _QT = [], []
for _module in _MODULES:
    _DONE = fresh(f"import importlib\nimportlib.import_module({_module!r})\n"
                  f"import sys\nprint('QT', 'PySide6' in sys.modules)\n")
    if _DONE.returncode != 0 or _DONE.stdout.strip() not in ("QT True", "QT False"):
        _LOUD.append(f"{_module}: {(_DONE.stdout or '')[-120:]!r} {(_DONE.stderr or '')[-160:]}")
    elif _DONE.stdout.strip() == "QT True":
        _QT.append(_module)
check("§6 the gate really scans the package", len(_MODULES) >= 19, str(_MODULES))
check("§6 importing every module of `cli/` prints NOTHING on stdout (a report is the only document)",
      not _LOUD, _LOUD[:2])
check("§6 ...and leaves PySide6 out of `sys.modules` (the rc1 gate, extended to the new modules)",
      not _QT, f"these modules load Qt: {_QT}")
check("§6 no module of `cli/` even IMPORTS PySide6",
      not [name for name, source in _SRC.items() if "import PySide6" in source
           or "from PySide6" in source])
_RUN = fresh("import sys\nfrom cli.main import main\n"
             f"rc = main(['--project', {MAP!r}, 'exec', 'web-1', 'rm -rf /x', '--dry-run'])\n"
             "print('QT', 'PySide6' in sys.modules, file=sys.stderr)\nsys.exit(rc)\n")
check("§6 a FRESH process answers ONE `exec` run with Qt absent (and the dry run's two lines)",
      _RUN.returncode == EX.EXIT_OK and "QT False" in (_RUN.stderr or "")
      and _RUN.stdout.splitlines()[:1] == ["guard: rm -rf"], f"{_RUN.stdout!r} / {_RUN.stderr!r}")

check_release_state(ROOT)
check(f"§6 this release is v{EXPECTED_APP_VERSION} (the line's base release or a later one)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15")
      and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§6 the milestone adds NO i18n key (the parity pin stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1205
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
check("§6 no new dependency: requirements.txt keeps its four pins",
      len([line for line in read(os.path.join(ROOT, "requirements.txt")).splitlines()
           if line.strip() and not line.strip().startswith("#")]) == 4)
check("§6 the JSON project format did NOT move (`VERSION_FORMAT` stays 0.9)",
      version.VERSION_FORMAT == "0.9")
_CONTRACT = read(CLI_MD)
check("§6 the contract states the exec verb, its five flags and the three policies (the frozen text)",
      '`exec <node> "<command>"' in _CONTRACT
      and all(f"`{flag}" in _CONTRACT for flag in VERB_ARGS.EXEC_VALUE_FLAGS + VERB_ARGS.EXEC_SWITCHES)
      and "The REMOTE exit code is the process's own answer" in _CONTRACT
      and "An unpinned host key is a REFUSAL" in _CONTRACT
      and "The command guard is ASKED, not skipped" in _CONTRACT
      and "`sshcanvas`, connect once" in _CONTRACT and "let the GUI store it" in _CONTRACT
      and "GUARD → CREDENTIAL → HOST KEY" in _CONTRACT,
      [flag for flag in VERB_ARGS.EXEC_VALUE_FLAGS + VERB_ARGS.EXEC_SWITCHES
       if f"`{flag}" not in _CONTRACT])

finish()
