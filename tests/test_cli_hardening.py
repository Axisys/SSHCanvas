# -*- coding: utf-8 -*-
"""v1.15rc5 — the hardening patch: the two channels' BYTES, the wire's gates and the output ceiling.
§1 the channels as bytes (a redirected table is exactly CRLF, a redirected `--json` is UTF-8 on every
stream); §2 the wire's gates (stdin EOF before the streams, `--host-key` against the PRESENTED key on a
pinned host, the PURE guard classifier, the unmanaged node skipped and refused); §3 the output ceiling;
§4 the round's code-text findings; §5 the README budget gate lives in `tests/test_i18n_live.py` §6 and
the release state is read here. Rule — `AGENTS.md` §4.35; contract — `CLI.md` §3.3–§3.5, §4–§5.3.
Run: python tests/test_cli_hardening.py
"""
import ast
import contextlib
import csv
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

import cli.doctor as DOCTOR  # noqa: E402
import cli.envelope as ENV  # noqa: E402
import cli.errors as ERR  # noqa: E402
import cli.exec as EXEC  # noqa: E402
import cli.exit_codes as EX  # noqa: E402
import cli.output as OUT  # noqa: E402
import modules.command_guard as GUARD  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import storage.app_config as APP_CONFIG  # noqa: E402
import version  # noqa: E402
from cli.main import main  # noqa: E402

CLI_DIR = os.path.join(ROOT, "cli")
LANGS = load_i18n_langs(ROOT)

#: A project whose alias/comment carry the characters a Windows code page cannot: CJK, an em dash, é/ï.
CJK_ALIAS = "東京サーバー"
CJK_COMMENT = "café — naïve"


def read(path):
    """The text of one repository file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def run(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout BYTES, stderr BYTES)`.

    The pair is captured on a `BytesIO` so a run is read as the PROCESS would leave it — but the in-process
    door cannot exercise the stream preparation (`reconfigure()`), which is what `child()` is for.
    """
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue().encode("utf-8"), err.getvalue().encode("utf-8")


def child(argv, env_extra=None):
    """Run the CLI as a REAL process (`python -m cli.main`) and answer `(code, stdout, stderr)` BYTES."""
    env = dict(os.environ, PYTHONPATH=ROOT)
    env.pop("PYTHONIOENCODING", None)
    env.update(env_extra or {})
    done = subprocess.run([sys.executable, "-m", "cli", *argv], cwd=ROOT,
                          capture_output=True, timeout=180, env=env)
    return done.returncode, done.stdout or b"", done.stderr or b""


def document(raw):
    """The ONE `--json` document of a run; `{}` when the bytes are not one (a defect the check names)."""
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}


def node(nid, alias, port=22, host="127.0.0.1", user="tester", **extra):
    """ONE synthetic server record."""
    record = {"id": nid, "alias": alias, "host": host, "ssh_port": port, "user": user}
    record.update(extra)
    return record


def fixture(name, servers=(), connections=()):
    """Write ONE SYNTHETIC project into the isolated work folder (never a real map file)."""
    payload = {"version": version.VERSION_FORMAT, "servers": list(servers),
               "connections": list(connections), "notes": [], "groups": [], "background": None}
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def closed_port():
    """A port nobody listens on (bound once, then released) — a deterministic `offline`."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


UNICODE_MAP = fixture("hard-unicode.json", [
    node("srv-tokyo", CJK_ALIAS, comment=CJK_COMMENT, tags=["prod"]),
    node("srv-plain", "plain-1", 2222)])
UNMANAGED_MAP = fixture("hard-unmanaged.json", [
    node("srv-managed", "managed", closed_port()),
    node("srv-printer", "printer", closed_port(), unmanaged=True)])
UNMANAGED_ONLY = fixture("hard-unmanaged-only.json", [
    node("srv-printer", "printer", closed_port(), unmanaged=True)])
EXEC_MAP = fixture("hard-exec.json", [node("srv-web", "web-1")])


class _TTY:
    """A stream shaped like a CONSOLE: `isatty()` true and a code page of its own."""

    def __init__(self, encoding="cp1251"):
        self.encoding = encoding
        self.written = []
        self.buffer = io.BytesIO()

    def isatty(self):
        """The console predicate the preparation reads."""
        return True

    def write(self, text):
        """A text write — what a console path would do."""
        self.written.append(text)
        return len(text)


class _FakeText:
    """A redirected text stream with a `buffer`: the envelope's UTF-8 guarantee is checked on it."""

    def __init__(self, encoding="cp1251"):
        self.encoding = encoding
        self.buffer = io.BytesIO()
        self.written = []

    def isatty(self):
        """Not a console — a redirected file."""
        return False

    def write(self, text):
        """A text write (the path the envelope must NOT take)."""
        self.written.append(text)
        return len(text)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the two channels are UTF-8 BYTES with their own row endings ==")
# ════════════════════════════════════════════════════════════════════════════

_CODE, _OUT_B, _ERR_B = child(["--project", UNICODE_MAP, "inventory", "--format", "csv"],
                              {"PYTHONIOENCODING": "cp1251"})
_TEXT = _OUT_B.decode("utf-8", "replace")
_ROWS = list(csv.reader(io.StringIO(_TEXT, newline="")))
check("§1 a redirected table ends every row with the writer's OWN `\\r\\n` (never `\\r\\r\\n`)",
      _CODE == EX.EXIT_OK and b"\r\r\n" not in _OUT_B
      and _OUT_B.count(b"\r\n") == _OUT_B.count(b"\n") and _OUT_B.count(b"\r\n") >= 2,
      f"{_CODE} / {_OUT_B[:120]!r}")
check("§1 ...so a standard parser reads the report rows and no empty record between them",
      len(_ROWS) == 3 and all(len(row) == 13 for row in _ROWS), f"{len(_ROWS)} rows / {_ROWS[:2]}")
check("§1 ...and a character the code page cannot carry leaves as its UTF-8 bytes",
      CJK_ALIAS.encode("utf-8") in _OUT_B and CJK_COMMENT.encode("utf-8") in _OUT_B,
      _OUT_B[:160])

_CODE, _OUT_B, _ERR_B = child(["--json", "--project", UNICODE_MAP, "inventory"],
                              {"PYTHONIOENCODING": "cp1251"})
_DOC = document(_OUT_B)
_INVENTORY_DATA = _DOC.get("data") or {}
_COLUMNS = [str(column) for column in _INVENTORY_DATA.get("columns") or ()]
_ALIASES = []
if "alias" in _COLUMNS:
    _ALIAS_COLUMN = _COLUMNS.index("alias")
    _ALIASES = [str(row[_ALIAS_COLUMN]) for row in _INVENTORY_DATA.get("rows") or ()
                if isinstance(row, list) and _ALIAS_COLUMN < len(row)]
check("§1 a redirected `--json` is ONE UTF-8 document (RFC 8259 §8.1), no BOM, one trailing `\\n`",
      _CODE == EX.EXIT_OK and _OUT_B.startswith(b"{") and not _OUT_B.startswith(b"\xef\xbb\xbf")
      and _OUT_B.endswith(b"}\n") and not _OUT_B.endswith(b"\r\n"), _OUT_B[:120])
check("§1 ...and its non-ASCII survives BYTE for byte (a code page never decides a report)",
      CJK_ALIAS in _ALIASES and CJK_COMMENT in json.dumps(_DOC, ensure_ascii=False), str(_ALIASES))
check("§1 ...with the diagnostics channel empty (the report is stdout alone)", _ERR_B == b"", _ERR_B[:120])

_REDIRECTED = getattr(OUT, "redirected", lambda stream: False)
check("§1 a stream without `isatty()` counts as REDIRECTED, a console does not",
      _REDIRECTED(io.StringIO()) and not _REDIRECTED(_TTY()))
check("§1 the encoder is ONE declaration (UTF-8, no BOM)",
      getattr(OUT, "CHANNEL_ENCODING", "") == "utf-8", getattr(OUT, "CHANNEL_ENCODING", None))

_FAKE = _FakeText()
OUT.report(ENV.build("inventory", data={"alias": CJK_ALIAS}), (), True, out=_FAKE, err=io.StringIO())
check("§1 the envelope leaves as UTF-8 BYTES on EVERY stream (the text layer is not asked)",
      not _FAKE.written and CJK_ALIAS in _FAKE.buffer.getvalue().decode("utf-8"),
      _FAKE.buffer.getvalue()[:120])


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the wire's gates: EOF, the presented key, the classifier, the unmanaged node ==")
# ════════════════════════════════════════════════════════════════════════════

class FakeChannel:
    """The status surface of ONE fake channel; `shutdown_write()` is the EOF the run must send."""

    def __init__(self, code=0):
        self.exit_status = int(code)
        self.status_event = threading.Event()
        self.status_event.set()
        self.eof_sent = False

    def recv_exit_status(self):
        """Answer the configured remote code."""
        return self.exit_status

    def shutdown_write(self):
        """Record the EOF (paramiko's `ChannelStdinFile.close()` calls exactly this)."""
        self.eof_sent = True


class FakeStdin:
    """The stdin handle of a fake channel — `close()` IS the EOF, and it is LOGGED."""

    def __init__(self, channel, log):
        self.channel = channel
        self.log = log

    def close(self):
        """Send the EOF the remote command waits for."""
        self.log.append("stdin-close")
        self.channel.shutdown_write()


class FakeStream:
    """One fake stdout/stderr: reads answer at most `size` bytes, and REFUSE a read before the EOF."""

    def __init__(self, payload, channel, log):
        self.payload = payload
        self.channel = channel
        self.log = log

    def read(self, size=None):
        """Answer the next chunk; the probe is red when the stream is read before stdin's EOF."""
        if "stdin-close" not in self.log:
            raise AssertionError("a stream was read before stdin got its EOF")
        self.log.append("read")
        size = len(self.payload) if size is None else max(0, int(size))
        chunk, self.payload = self.payload[:size], self.payload[size:]
        return chunk


class FakeTransport:
    """The transport surface `--host-key` verification reads the PRESENTED key from."""

    def __init__(self, key):
        self.key = key

    def get_remote_server_key(self):
        """The key this connection presented."""
        return self.key


class FakeClient:
    """The `paramiko.SSHClient` seam: records what the verb asked and answers what the test set."""

    instances = []
    answer = (0, b"", b"")
    on_connect = None
    remote_key = None

    def __init__(self):
        self.host_keys = paramiko.hostkeys.HostKeys()
        self.policy = None
        self.kwargs = {}
        self.commands = []
        self.closed = False
        self.log = []
        self.stdin = None
        self.channel = None
        FakeClient.instances.append(self)

    def set_missing_host_key_policy(self, policy):
        """Keep the policy a real client would consult."""
        self.policy = policy

    def get_host_keys(self):
        """The client's known-hosts map (a real `HostKeys`, so a loaded pin lands)."""
        return self.host_keys

    def connect(self, **kwargs):
        """Record the built kwargs and run the configured hook (which may raise)."""
        self.kwargs = dict(kwargs)
        if FakeClient.on_connect is not None:
            FakeClient.on_connect(self)

    def get_transport(self):
        """The transport of THIS connection (the presented key)."""
        return FakeTransport(FakeClient.remote_key)

    def exec_command(self, command, timeout=None):
        """Answer the configured streams for ONE command."""
        self.commands.append((command, timeout))
        code, out, err = FakeClient.answer
        self.channel = FakeChannel(code)
        self.stdin = FakeStdin(self.channel, self.log)
        return (self.stdin, FakeStream(out, self.channel, self.log),
                FakeStream(err, self.channel, self.log))

    def close(self):
        """Mark the client closed (the verb closes it on every path)."""
        self.closed = True


def reset_clients(answer=(0, b"", b""), on_connect=None, remote_key=None):
    """Return the seam to a known state for the next run."""
    FakeClient.instances.clear()
    FakeClient.answer = answer
    FakeClient.on_connect = on_connect
    FakeClient.remote_key = remote_key
    EXEC.CLIENT_FACTORY = FakeClient


def clear_cfg():
    """Drop the isolated `config.json` — the config store returns to its declared default."""
    try:
        os.remove(APP_CONFIG.CONFIG_FILE)
    except OSError:
        pass


reset_clients(answer=(0, b"done\n", b""))
_CODE, _OUT_B, _ERR_B = run(["--project", EXEC_MAP, "exec", "web-1", "cat"])
_EXECUTED = FakeClient.instances[-1] if FakeClient.instances else None
check("§2 `exec` sends EOF on stdin BEFORE it reads a stream (a reading command ends, not the budget)",
      _CODE == EX.EXIT_OK and _OUT_B == b"done\n" and _EXECUTED is not None
      and _EXECUTED.channel.eof_sent is True
      and _EXECUTED.log[:1] == ["stdin-close"] and "read" in _EXECUTED.log[1:],
      f"{_CODE} / {_EXECUTED.log if _EXECUTED else None} / {_ERR_B[:120]!r}")
check("§2 ...so the command's own answer is what the run reads, never a refusal about a dead stdin",
      _EXECUTED is not None and _EXECUTED.commands == [("cat", 10.0)], str(_EXECUTED.commands))

HKP.set_store(HKP.KnownHostsStore(os.path.join(WORK, "known_hosts_hardening")))
_STORE = HKP.get_store()
KEY_A = paramiko.ECDSAKey.generate()
KEY_B = paramiko.ECDSAKey.generate()
_STORE.pin("127.0.0.1", KEY_A.get_name(), KEY_A)


def pinned_host(client):
    """The transport ACCEPTED the pinned key, so the policy is never asked — the N176 shape."""
    assert client.host_keys.lookup("127.0.0.1") is not None


reset_clients(answer=(0, b"hi\n", b""), on_connect=pinned_host, remote_key=KEY_A)
_CODE, _OUT_B, _ERR_B = run(["--project", EXEC_MAP, "exec", "web-1", "echo hi",
                             "--host-key", HKP.fingerprint(KEY_B)])
check("§2 `--host-key` names the FOREIGN key of a PINNED host: the presented key is what decides",
      _CODE == EX.EXIT_REFUSAL and "presented host key" in _ERR_B.decode("utf-8", "replace")
      and HKP.fingerprint(KEY_B) in _ERR_B.decode("utf-8", "replace"),
      f"{_CODE} / {_ERR_B[:200]!r}")
check("§2 ...and the refusal closes the client without running the command",
      FakeClient.instances[-1].closed is True and FakeClient.instances[-1].commands == [])

reset_clients(answer=(0, b"hi\n", b""), on_connect=pinned_host, remote_key=KEY_A)
_CODE, _OUT_B, _ERR_B = run(["--project", EXEC_MAP, "exec", "web-1", "echo hi",
                             "--host-key", "sha256:" + HKP.fingerprint(KEY_A)[7:]])
check("§2 ...while the key it really names passes (the `SHA256:` head is matched either way)",
      _CODE == EX.EXIT_OK and _OUT_B == b"hi\n" and _ERR_B == b"", f"{_CODE} / {_ERR_B[:160]!r}")

reset_clients(answer=(0, b"hi\n", b""), on_connect=pinned_host, remote_key=None)
_CODE, _OUT_B, _ERR_B = run(["--json", "--project", EXEC_MAP, "exec", "web-1", "echo hi",
                             "--host-key", HKP.fingerprint(KEY_A)])
check("§2 ...and a presented key that cannot be READ is a refusal, never a passed check",
      _CODE == EX.EXIT_REFUSAL
      and document(_OUT_B).get("error", {}).get("kind") == "refusal",
      f"{_CODE} / {_OUT_B[:160]!r}")

clear_cfg()
APP_CONFIG.save_config({"guard_commands": False})
try:
    reset_clients(answer=(0, b"ok\n", b""))
    _CODE, _OUT_B, _ERR_B = run(["--project", EXEC_MAP, "exec", "web-1", "reboot"])
    check("§2 the guard's classifier is ASKED whatever the map's dialog preference says",
          _CODE == EX.EXIT_REFUSAL and b"reboot" in _ERR_B and not FakeClient.instances,
          f"{_CODE} / {_ERR_B[:160]!r} / built={len(FakeClient.instances)}")
finally:
    clear_cfg()
check("§2 ...and the preference itself still governs the map's dialogs (the store is the same key)",
      GUARD.guard_enabled({GUARD.GUARD_COMMANDS_KEY: False}) is False
      and GUARD.dangerous_token("reboot") == "reboot")

reset_clients()
_CODE, _OUT_B, _ERR_B = run(["--json", "--project", UNMANAGED_MAP, "--timeout", "1", "status"])
_DATA = document(_OUT_B).get("data") or {}
check("§2 `status` SKIPS an unmanaged node and names it in the additive `data.skipped`",
      _CODE == EX.EXIT_NETWORK and _DATA.get("count") == 1 and _DATA.get("skipped") == ["srv-printer"]
      and [record.get("id") for record in _DATA.get("nodes") or ()] == ["srv-managed"],
      f"{_CODE} / {_DATA}")
_CODE, _OUT_B, _ERR_B = run(["--project", UNMANAGED_MAP, "--timeout", "1", "status"])
check("§2 ...and the text form carries the probed node alone (the skip is a machine fact)",
      _CODE == EX.EXIT_NETWORK and b"managed" in _OUT_B and b"printer" not in _OUT_B,
      _OUT_B[:160])
_CODE, _OUT_B, _ERR_B = run(["--json", "--project", UNMANAGED_ONLY, "--timeout", "1", "status"])
_DATA = document(_OUT_B).get("data") or {}
check("§2 ...a round over unmanaged nodes only is `count: 0`, exit 0 and the ids in `skipped`",
      _CODE == EX.EXIT_OK and _DATA.get("count") == 0 and _DATA.get("nodes") == []
      and _DATA.get("skipped") == ["srv-printer"], f"{_CODE} / {_DATA}")

reset_clients(answer=(0, b"x\n", b""))
_CODE, _OUT_B, _ERR_B = run(["--json", "--project", UNMANAGED_MAP, "exec", "printer", "uptime"])
_DOC = document(_OUT_B)
check("§2 `exec` REFUSES an unmanaged node (2) before it builds a client",
      _CODE == EX.EXIT_REFUSAL and _DOC.get("error", {}).get("kind") == "refusal"
      and "unmanaged" in _DOC.get("error", {}).get("message", "")
      and not FakeClient.instances, f"{_CODE} / {_OUT_B[:200]!r}")
_CODE, _OUT_B, _ERR_B = run(["--project", UNMANAGED_MAP, "exec", "printer", "uptime", "--dry-run"])
check("§2 ...a `--dry-run` still describes the command (it opens nothing at all)",
      _CODE == EX.EXIT_OK and _OUT_B.splitlines() == [b"guard: none", b"command: uptime"],
      f"{_CODE} / {_OUT_B[:160]!r}")

_CODE, _OUT_B, _ERR_B = run(["--json", "--project", UNMANAGED_MAP, "--timeout", "1",
                             "doctor", "printer"])
_DOC = document(_OUT_B)
check("§2 `doctor` still REPORTS an unmanaged node — reachability is what the flag is there for",
      _CODE in (EX.EXIT_NETWORK, EX.EXIT_TIMEOUT) and _DOC.get("ok") is True
      and (_DOC.get("data") or {}).get("kind") not in (None, "", "ok"),
      f"{_CODE} / {_OUT_B[:200]!r}")


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the remote output has a ceiling, and a cut is announced ==")
# ════════════════════════════════════════════════════════════════════════════

_LIMIT = getattr(EXEC, "OUTPUT_MAX_BYTES", None)
check("§3 the ceiling is ONE declaration: 64 MiB per stream", _LIMIT == 64 * 1024 * 1024, str(_LIMIT))
_BOUNDED_READ = getattr(EXEC, "read_bounded", None)
_BIG = b"x" * 10000
_KEPT, _CUT = _BOUNDED_READ(io.BytesIO(_BIG), 4096) if _BOUNDED_READ else (b"", None)
check("§3 a stream over the bound keeps its HEAD, drains to its end and reports the cut",
      _KEPT == b"x" * 4096 and _CUT is True and len(_KEPT) == 4096, f"{len(_KEPT)} / {_CUT}")
_KEPT, _CUT = _BOUNDED_READ(io.BytesIO(b"y" * 4096), 4096) if _BOUNDED_READ else (b"", None)
check("§3 ...a stream exactly at the bound is NOT truncated", _KEPT == b"y" * 4096 and _CUT is False)

_ORIGINAL_LIMIT = getattr(EXEC, "OUTPUT_MAX_BYTES", 64 * 1024 * 1024)
try:
    EXEC.OUTPUT_MAX_BYTES = 2048
    reset_clients(answer=(0, b"z" * 5000, b"e" * 3000))
    _CODE, _OUT_B, _ERR_B = run(["--json", "--project", EXEC_MAP, "exec", "web-1", "cat big"])
    _DATA = document(_OUT_B).get("data") or {}
    check("§3 the ceiling reaches the payload: `data.truncated` is true and stdout keeps the head",
          _CODE == EX.EXIT_OK and _DATA.get("truncated") is True
          and len(_DATA.get("stdout") or "") == 2048 and len(_DATA.get("stderr") or "") == 2048,
          f"{_CODE} / {len(_DATA.get('stdout') or '')} / {len(_DATA.get('stderr') or '')}")
    check("§3 ...and ONE stderr line says so (a truncated report is never silent)",
          _ERR_B.decode("utf-8", "replace").splitlines().count(
              "the remote output was truncated at 2048 bytes per stream") == 1,
          _ERR_B[-200:])
finally:
    EXEC.OUTPUT_MAX_BYTES = _ORIGINAL_LIMIT
check("§3 ...and the declaration is back (the ceiling is a module constant, not a run's state)",
      EXEC.OUTPUT_MAX_BYTES == 64 * 1024 * 1024)


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the round's code-text findings ==")
# ════════════════════════════════════════════════════════════════════════════


def placeholderless_fstrings(source):
    """Line numbers of the f-strings that carry NO placeholder (a lint defect pyflakes reports).

    A FORMAT SPEC is a `JoinedStr` of its own (`f"{value:g}"`), so the specs are collected first and
    skipped — the finding is a string whose whole text is literal while it still wears the prefix.
    """
    tree = ast.parse(source)
    specs = {id(node.format_spec) for node in ast.walk(tree)
             if isinstance(node, ast.FormattedValue) and node.format_spec is not None}
    return [node.lineno for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)
            and id(node) not in specs
            and not any(isinstance(value, ast.FormattedValue) for value in node.values)]


_OFFENDERS = {}
for _name in sorted(os.listdir(CLI_DIR)):
    if _name.endswith(".py"):
        _LINES = placeholderless_fstrings(read(os.path.join(CLI_DIR, _name)))
        if _LINES:
            _OFFENDERS[_name] = _LINES
check("§4 no module of `cli/` carries a placeholder-less f-string (the round's pyflakes finding)",
      not _OFFENDERS, str(_OFFENDERS))

try:
    DOCTOR.handle(None, ())
    _DOCTOR_COST = None
except ERR.CliError as exc:
    _DOCTOR_COST = exc
except Exception as exc:  # noqa: BLE001 — the defect WAS an IndexError, and the check names it
    _DOCTOR_COST = exc
check("§4 `doctor`'s DIRECT handler call with no node is a USAGE error, never an IndexError",
      isinstance(_DOCTOR_COST, ERR.CliError) and _DOCTOR_COST.code == EX.EXIT_USAGE
      and "node" in _DOCTOR_COST.message, repr(_DOCTOR_COST))
_ROUNDED = DOCTOR.render(None, {"host": "h", "port": 22, "kind": "ok", "ip": "1.2.3.4",
                                "detail": "banner", "ping": "", "elapsed": 0.031000000002677552})
check("§4 the doctor TEXT form rounds `elapsed` (the envelope keeps the measured float)",
      _ROUNDED[-1] == "elapsed: 0.031", _ROUNDED[-1])

_CODE, _OUT_B, _ERR_B = run(["--project", UNICODE_MAP, "inventory", "--project", "elsewhere"])
_ERR_TEXT = _ERR_B.decode("utf-8", "replace")
check("§4 a GLOBAL option after the verb names the GRAMMAR in its hint, not only the verb",
      _CODE == EX.EXIT_USAGE and "inventory does not take '--project'" in _ERR_TEXT
      and "BEFORE the verb" in _ERR_TEXT, _ERR_TEXT[:200])
_CODE, _OUT_B, _ERR_B = run(["--project", UNICODE_MAP, "exec", "web-1", "uptime", "--json"])
_ERR_TEXT = _ERR_B.decode("utf-8", "replace")
check("§4 ...and the same rule holds in the exec tail (a declared global option is never a command word)",
      _CODE == EX.EXIT_USAGE and "exec does not take '--json'" in _ERR_TEXT
      and "BEFORE the verb" in _ERR_TEXT, _ERR_TEXT[:200])


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check(f"§5 this release is v{EXPECTED_APP_VERSION} (the line's base release or a later one)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15")
      and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§5 the milestone adds NO i18n key (the parity pin stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1205
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)

finish()
