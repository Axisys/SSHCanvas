# -*- coding: utf-8 -*-
"""`exec` — one command on one node: the gates, the wire, and the REMOTE exit code.

Every policy is asked BEFORE the command and a refusal costs no command: the NODE gate (an unmanaged
card refuses) → the GUARD (`dangerous_token()`, the PURE classifier — never the dialog's preference) →
the CREDENTIAL → the HOST KEY (`cli/hostkeys.py` at the handshake, then verified against the key the
server PRESENTED). `--dry-run` stops after the guard and opens nothing. stdin gets EOF before the
streams are read; both are DRAINED but kept only up to `OUTPUT_MAX_BYTES`. The remote stdout is the text
form written VERBATIM, its stderr the diagnostics and its exit code the process's own answer.
Rule — `AGENTS.md` §4.35; contract — `CLI.md` §3.5, §5.1–§5.3; mechanism — `DOCUMENTATION.md` §80.
"""
import concurrent.futures
import socket

import paramiko
from paramiko.ssh_exception import NoValidConnectionsError

from models.server import is_unmanaged
from modules.command_guard import dangerous_token, excerpt
from modules.ssh_connect import (ConnectionCancelled, build_connect_kwargs,
                                 interactive_transport_factory)

from . import credentials, hostkeys
from . import project as PROJECT_SOURCE
from . import verb_args
from .dispatch import Verb, register
from .errors import CliError, auth_error, network_error, refusal, timeout_error, usage_error
from .hostkeys import HostKeyRejected

NAME = "exec"
SUMMARY = 'one command on one node (exec <node> "<command>"; flags after the command)'

#: The `data` keys of a run, in order — the pinned machine payload of `CLI.md` §3.5, §4.
DATA_KEYS = ("project", "node", "command", "dry_run", "guard", "auth", "exit_code", "stdout",
             "stderr", "truncated")

#: The client CLASS the verb builds — the ONE seam a test replaces (None = `paramiko.SSHClient`).
CLIENT_FACTORY = None

#: The encoding a remote stream is decoded with; a byte it cannot carry REPLACES, never raises.
OUTPUT_ENCODING = "utf-8"

#: The ceiling of ONE remote stream, in bytes — a stream over it keeps its HEAD and says so (`CLI.md` §3.5).
OUTPUT_MAX_BYTES = 64 * 1024 * 1024

#: The chunk one bounded read takes between two checks of that ceiling.
READ_CHUNK_BYTES = 64 * 1024


def node_port(node) -> int:
    """The SSH port of a node record, coerced to the declared 1..65535 range (PURE)."""
    try:
        return max(1, min(65535, int(getattr(node, "ssh_port", 22) or 22)))
    except (TypeError, ValueError):
        return 22


def endpoint(node) -> str:
    """`user@host:port` of a node — the ONE spelling a failure sentence and `data.node` share."""
    user = str(getattr(node, "user", "") or "")
    host = str(getattr(node, "host", "") or "")
    return f"{user}@{host}:{node_port(node)}"


def label(node) -> str:
    """The name a refusal prints: the alias, else the id — never a bare endpoint."""
    return str(getattr(node, "alias", "") or getattr(node, "id", "") or endpoint(node))


def classify(exc, where="") -> CliError:
    """The ONE table of a failed connect/run: the exception answers its exit class (PURE).

    The specific types are named FIRST — paramiko's own failures subclass `SSHException`, so a generic
    branch placed earlier would swallow the difference between a refused credential (`3`), a refused host
    key (`2`) and an unreachable box (`4`). A foreign exception is the network class with its own text:
    a socket error the table does not know is still a network answer, never a traceback.
    """
    prefix = f"{where}: " if where else ""
    if isinstance(exc, paramiko.BadHostKeyException):
        got = getattr(exc, "key", None) or getattr(exc, "got_key", None)
        return refusal(f"{prefix}the host key CHANGED (now {hostkeys.fingerprint(got) if got else '?'}) "
                       f"— verify the box before trusting it; --accept-new never covers a moved pin",
                       "repair ~/.sshmap/known_hosts with `sshcanvas`")
    if isinstance(exc, HostKeyRejected):
        return refusal(f"{prefix}{exc}")
    if isinstance(exc, paramiko.PasswordRequiredException):
        return auth_error(f"{prefix}the private key is encrypted and this surface cannot ask for its "
                          f"passphrase", "load the key in the agent (ssh-add), or use an unencrypted key")
    if isinstance(exc, ConnectionCancelled):
        return auth_error(f"{prefix}{exc}",
                          "run `sshcanvas` once for the interactive path")
    if isinstance(exc, paramiko.AuthenticationException):
        return auth_error(f"{prefix}the endpoint refused the credential", credentials.DOOR)
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return timeout_error(f"{prefix}the budget ran out before the operation finished",
                             "raise --timeout")
    if isinstance(exc, (socket.gaierror, NoValidConnectionsError)):
        return network_error(f"{prefix}{exc}")
    if isinstance(exc, (paramiko.SSHException, OSError)):
        return network_error(f"{prefix}{exc}")
    return network_error(f"{prefix}{type(exc).__name__}: {exc}")


def _text(raw) -> str:
    """ONE stream as text: bytes decoded with the declared encoding (a bad byte REPLACES, never raises)."""
    if isinstance(raw, bytes):
        return raw.decode(OUTPUT_ENCODING, "replace")
    return str(raw if raw is not None else "")


def read_bounded(stream_, limit=None) -> tuple:
    """Read ONE stream to its END, keeping only its HEAD — `(bytes, truncated)`.

    The stream is DRAINED past the ceiling on purpose: the remote command must never block on a full
    window because the reader stopped, so every chunk is still read and only the bytes over the bound are
    dropped. A `str` chunk (a fake, a foreign stream) is encoded with the declared encoding first.
    """
    limit = OUTPUT_MAX_BYTES if limit is None else max(0, int(limit))
    kept, held, truncated = [], 0, False
    while True:
        chunk = stream_.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        if isinstance(chunk, str):
            chunk = chunk.encode(OUTPUT_ENCODING, "replace")
        room = limit - held
        if room > 0:
            kept.append(chunk[:room])
            held += min(len(chunk), room)
        if len(chunk) > room:
            truncated = True
    return b"".join(kept), truncated


def close_stdin(stream_) -> bool:
    """Send EOF to the remote command BEFORE its streams are read — paramiko's `close()` IS the EOF.

    `ChannelStdinFile.close()` calls `channel.shutdown_write()`, while the channel itself stays open, so a
    command that waits for input (`cat`) ends instead of spending the budget and its status stays
    readable. A stdin that cannot close is not the news the run is about; the budget bounds the rest.
    """
    if stream_ is None:
        return False
    close = getattr(stream_, "close", None)
    if not callable(close):
        return False
    try:
        close()
        return True
    except Exception as exc:  # noqa: BLE001 — the command's own answer outranks the clean-up's
        log = _log()
        if log:
            log.debug("Closing the exec stdin failed: %s", exc)
        return False


def _exit_status(channel, timeout) -> int:
    """The remote exit code, waited for no longer than `timeout` (a silent command is a `6`)."""
    event = getattr(channel, "status_event", None)
    if event is not None and not event.wait(timeout):
        raise timeout_error(f"the command did not exit within {float(timeout):g} s",
                            "raise --timeout")
    try:
        return int(channel.recv_exit_status())
    except (AttributeError, TypeError, ValueError):  # noqa: BLE001 — a channel without a status
        return 0


class Session:
    """ONE authenticated client — the ONLY object of the surface that talks to the wire."""

    def __init__(self, client):
        self._client = client

    def run(self, command, timeout) -> tuple:
        """Run ONE command and answer `(exit_code, stdout, stderr, truncated)`; every wait is bounded.

        The two streams are read CONCURRENTLY: paramiko's window is per CHANNEL, so a command that fills
        its stderr buffer while the caller is still reading stdout would block the remote process and
        turn a finished run into a timeout — the pair of readers is what keeps both windows moving. Each
        reader drains its stream and keeps the head up to `OUTPUT_MAX_BYTES`; the caller announces a cut.
        """
        try:
            stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            close_stdin(stdin)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                pending = [pool.submit(read_bounded, stdout), pool.submit(read_bounded, stderr)]
                out, out_cut = pending[0].result()
                err, err_cut = pending[1].result()
            return (_exit_status(getattr(stdout, "channel", None), timeout),
                    _text(out), _text(err), bool(out_cut or err_cut))
        except CliError:
            raise
        except Exception as exc:  # noqa: BLE001 — the ONE table answers the class, the verb raises
            raise classify(exc) from exc

    def close(self) -> None:
        """Close the client; a close that fails is not the news the caller is about to hear."""
        try:
            self._client.close()
        except Exception as exc:  # noqa: BLE001 — the run's own answer outranks the clean-up's
            log = _log()
            if log:
                log.debug("Closing the exec client failed: %s", exc)


def _client_class():
    """The client class this run builds (a test's factory, otherwise paramiko's own)."""
    return CLIENT_FACTORY or paramiko.SSHClient


def _log():
    """The application log, or None — the surface works without it (`modules/logger.py`)."""
    try:
        from modules.logger import get_logger
        return get_logger("cli.exec")
    except Exception:  # noqa: BLE001 — optional import: a run without a log is not a failed run
        return None


def verify_presented_key(client, expected) -> None:
    """Refuse when the key the server PRESENTED is not the one `--host-key` names (`CLI.md` §5.2).

    `missing_host_key()` runs for an UNKNOWN host alone: a host the store already holds is accepted by
    the transport before the policy is consulted, so this ONE check is the other half — and it reads the
    presented key of THIS connection, never the store's record. An unreadable key REFUSES: a check that
    cannot be made is never a pass.
    """
    wanted = hostkeys.normalize_fingerprint(expected)
    if not wanted:
        return
    try:
        key = client.get_transport().get_remote_server_key()
    except Exception as exc:  # noqa: BLE001 — an unreadable key is a refusal, never a passed check
        raise HostKeyRejected(f"the presented host key could not be read, so --host-key cannot verify "
                              f"it ({exc})")
    presented = hostkeys.fingerprint(key) if key is not None else ""
    if not presented:
        raise HostKeyRejected("the presented host key could not be read, so --host-key cannot verify it")
    if presented != wanted:
        raise HostKeyRejected(f"the presented host key is {presented}, not the {wanted} --host-key named")


def open_session(node, credential, options, timeout, note=None) -> Session:
    """Open ONE authenticated client through the SHIPPED builder and the CLI's host-key policy.

    The builder owns the arguments (`build_connect_kwargs()`: Key → Password → Agent) and this function
    owns only WHAT it hands over: the credential `cli/credentials.py` resolved, the timeout, and the
    answering transport — the shipped factory whose keyboard-interactive handler REFUSES instead of
    reading the process's stdin (`AGENTS.md` §4.4.1). After the handshake the presented key is compared
    with `--host-key` on EVERY path (pinned host included). Every failure goes through `classify()`.
    """
    host = str(getattr(node, "host", "") or "")
    user = str(getattr(node, "user", "") or "")
    port = node_port(node)
    client = _client_class()()
    policy = hostkeys.CliHostKeyPolicy(host, port, accept_new=options.accept_new,
                                       expected=options.host_key, note=note)
    policy.apply_to_client(client)
    kwargs = build_connect_kwargs(host, user, port, password=credential.password,
                                  key_path=credential.key_path, timeout=timeout,
                                  banner_timeout=timeout, auth_timeout=timeout,
                                  transport_factory=interactive_transport_factory(host, user, port))
    try:
        client.connect(**kwargs)
        verify_presented_key(client, options.host_key)
    except Exception as exc:  # noqa: BLE001 — the ONE table answers the class, the verb raises
        Session(client).close()
        raise classify(exc, endpoint(node)) from exc
    return Session(client)


def _record(path, node, request, token) -> dict:
    """The `data` payload BEFORE the wire — the dry run answers exactly this and stops."""
    return {"project": str(path),
            "node": {"id": str(getattr(node, "id", "") or ""),
                     "alias": str(getattr(node, "alias", "") or ""),
                     "user": str(getattr(node, "user", "") or ""),
                     "host": str(getattr(node, "host", "") or ""),
                     "port": node_port(node)},
            "command": request.command,
            "dry_run": bool(request.dry_run),
            "guard": str(token),
            "auth": "",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "truncated": False}


def handle(context, arguments):
    """The verb's FACTS — the node gate, the guard's verdict, the credential and the remote answer."""
    request = verb_args.read_exec(arguments)
    path = PROJECT_SOURCE.resolve_path(context.project)
    nodes = PROJECT_SOURCE.select_servers(PROJECT_SOURCE.read_servers(path), (request.node,))
    if len(nodes) != 1:
        raise usage_error(f"{request.node!r} names {len(nodes)} nodes", "pass an id (see `inventory`)")
    node = nodes[0]
    token = dangerous_token(request.command)
    payload = _record(path, node, request, token)
    if request.dry_run:
        return payload
    if is_unmanaged(node):
        raise refusal(f"{label(node)} is an unmanaged node — no session is opened to it",
                      "clear the card's `unmanaged` flag in the map (`sshcanvas`), then run again")
    if token and not request.allow_destructive:
        raise refusal(f"the command guard refused {token!r}: {excerpt(request.command)!r}",
                      "pass --allow-destructive to run it anyway")
    credential = credentials.resolve(node, request.identity)
    payload["auth"] = credential.branch
    session = open_session(node, credential, request, context.timeout, note=context.warn)
    try:
        code, out, err, truncated = session.run(request.command, context.timeout)
    finally:
        session.close()
    payload.update(exit_code=code, stdout=out, stderr=err, truncated=truncated)
    for line in str(err).splitlines():
        context.warn(line)
    if truncated:
        context.warn(f"the remote output was truncated at {OUTPUT_MAX_BYTES} bytes per stream")
    return payload


def verdict(payload) -> int:
    """The REMOTE exit code, or `0` for a run that opened nothing (`--dry-run`)."""
    code = (payload or {}).get("exit_code")
    if code is None:
        return 0
    try:
        return int(code)
    except (TypeError, ValueError):
        return 0


def render(context, payload) -> object:
    """The text form: the remote stdout VERBATIM, or the guard's verdict and the command of a dry run."""
    payload = payload or {}
    if payload.get("dry_run"):
        return [f"guard: {payload.get('guard') or 'none'}", f"command: {payload.get('command', '')}"]
    return str(payload.get("stdout") or "")


register(Verb(NAME, SUMMARY, handler=handle, render=render, verdict=verdict, raw_code=True,
              min_args=2, max_args=verb_args.MAX_ARGUMENTS))
