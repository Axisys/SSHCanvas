# -*- coding: utf-8 -*-
"""The ONE connect builder — every site that opens an SSH session goes through it (AGENTS.md §4.4).

`build_connect_kwargs()` is the PURE branch table: a KEY authenticates first with a password (or a
verification code) as the LAST method paramiko tries, a PASSWORD alone refuses to poll the local keys or
the ssh-agent, and neither falls back to the shipped key/agent pair. `connect_client()` is the live half —
the application's known-hosts policy, the ANSWERING transport (a second factor is answered by the user,
never the process's stdin) and the ONE retry after a CHANGED host key was replaced. A non-empty `jump`
adds ONE internal hop: the bastion's own client and a `direct-tcpip` channel handed to the target as
`sock=`; the bastion uses the KEY/AGENT sources only and its OWN host-key policy.
A caller keeps its own timeouts and error handling: the builder owns the ARGUMENTS, never the failure,
and a password, a passphrase or a code never reaches a log, a file or an argv.
Tests — `tests/test_ssh_connect.py`, `tests/test_jump_host.py`; mechanism — §16."""

import os

import paramiko

try:
    from . import host_key_policy as _host_key_policy
    from . import interactive_ask as _ask
    from . import jump_host as _jump
    from .local_paths import resolve_local_path
except ImportError:  # flat launch from the project root
    import host_key_policy as _host_key_policy
    import interactive_ask as _ask
    import jump_host as _jump
    from local_paths import resolve_local_path

#: The role a policy factory is asked about — the TARGET endpoint or the bastion of the hop.
ROLE_TARGET = "target"
ROLE_JUMP = "jump"

#: The jump reader's own vocabulary is re-exported here, where the hop opens.
JumpSpec = _jump.JumpSpec
JumpSpecError = _jump.JumpSpecError
parse_jump = _jump.parse_jump

#: The timeout of the two INTERACTIVE sites — the terminal session and the worker beside it.
CONNECT_TIMEOUT_S = 15

#: ONE connect + ONE retry: the retry exists for a CHANGED host key the user chose to replace.
KEY_RETRY_ATTEMPTS = 2


def _t(key, **kwargs) -> str:
    """A translated sentence — the builder reports a rejection the user must be able to read."""
    try:
        from i18n import t as _translate
    except Exception:  # noqa: BLE001
        return key
    try:
        return _translate(key, **kwargs) if kwargs else _translate(key)
    except Exception:  # noqa: BLE001
        return key


class ConnectionCancelled(paramiko.SSHException):
    """The connection was cancelled BY THE USER — a refused host key, or an unanswered prompt.

    It is an `SSHException`, so the shipped branches of the four call sites already handle it, and its
    message is a finished translated sentence (the caller shows it, it does not re-wrap it).
    """


#: The refusal `missing_host_key()` raises — re-exported so a call site gets both from ONE import.
HostKeyRejected = _host_key_policy.HostKeyRejected


def build_connect_kwargs(host, user, port, password="", key_path="", passphrase="",
                         verification_code="", timeout=CONNECT_TIMEOUT_S,
                         banner_timeout=None, auth_timeout=None, transport_factory=None) -> dict:
    """The `paramiko.SSHClient.connect()` arguments of ONE endpoint (PURE).

    THREE branches, and they are the whole contract:
    * a KEY (`key_path`, resolved through `modules/local_paths.py`) → `key_filename` beside
      `look_for_keys=False` / `allow_agent=True`, with the password passed as well (`None` when there is
      none — paramiko tries it LAST, so a host that refuses the key alone still authenticates, and a
      key-only host is untouched). `verification_code` WINS over the password there: a code is collected
      only on the user's word that the host demands a second factor, and `password is not None` is what
      keeps paramiko away from its stdin-reading handler. `passphrase` travels only when it was given.
    * a PASSWORD without a key → `look_for_keys=False` / `allow_agent=False`: no local key and no
      agent is polled before the attempt;
    * neither → the shipped key/agent fallback (`True` / `True`).
    `banner_timeout` / `auth_timeout` and `transport_factory` travel ONLY when the caller declares
    them: the diagnostic paths bound a black-holed host with all three, the interactive ones ship
    `timeout` alone.
    """
    kwargs = {"hostname": host, "username": user, "port": port, "timeout": timeout}
    if banner_timeout is not None:
        kwargs["banner_timeout"] = banner_timeout
    if auth_timeout is not None:
        kwargs["auth_timeout"] = auth_timeout
    if transport_factory is not None:
        kwargs["transport_factory"] = transport_factory
    resolved_key = resolve_local_path(key_path) if key_path else ""
    if resolved_key:
        kwargs.update(key_filename=resolved_key,
                      password=(verification_code or password or None),
                      look_for_keys=False, allow_agent=True)
        if passphrase:
            kwargs["passphrase"] = passphrase
    elif password:
        kwargs.update(password=password, look_for_keys=False, allow_agent=False)
    else:
        kwargs.update(look_for_keys=True, allow_agent=True)
    return kwargs


#: The THREE branches of the table above, as NAMES — what a caller records about its own connect.
AUTH_KEY = "key"
AUTH_PASSWORD = "password"
AUTH_FALLBACK = "fallback"


def resolve_auth_branch(password="", key_path="") -> str:
    """Which of the THREE branches `build_connect_kwargs()` takes for this pair (PURE).

    A usable key FILE is `AUTH_KEY` (the password rides beside it only as the LAST method), a
    password alone is `AUTH_PASSWORD` and neither is the shipped key/agent `AUTH_FALLBACK`, which
    opens a session with NO secret of ours.
    """
    if key_path and resolve_local_path(key_path):
        return AUTH_KEY
    return AUTH_PASSWORD if password else AUTH_FALLBACK


def rearm_credential_missing(branch, password="", key_path="") -> bool:
    """Does a re-arm of a session built on `branch` lack the credential that opened it? (PURE)

    Only a branch that really used a secret of OURS can miss it: `AUTH_KEY` holds its credential in
    the FILE (still present — the keyring is not consulted at all), `AUTH_PASSWORD` is missing once
    the keyring and the caller's own memory answer nothing, and `AUTH_FALLBACK` authenticated through
    the ssh-agent or the user's default keys, so it is re-armed with the very arguments of its first
    connect and never refused.
    """
    if branch == AUTH_KEY:
        return not (key_path or password)
    if branch == AUTH_PASSWORD:
        return not password
    return False


def key_needs_passphrase(key_path) -> bool:
    """Is this private key file ENCRYPTED — i.e. does opening it demand a passphrase? Never raises.

    It is the pre-flight of the ask: the file is opened WITHOUT a passphrase right here, so the user is
    asked only when the answer is really needed, and a readable key (or a missing one) costs nothing.
    """
    path = resolve_local_path(key_path) if key_path else ""
    if not path:
        return False
    try:
        if not os.path.isfile(path):
            return False
    except OSError:  # noqa: BLE001 — an unusable path is not an encrypted key
        return False
    # Each key class is asked in turn (paramiko's own `_auth` order): the one that matches the file
    # either loads it or answers the ONE exception that means "encrypted".
    for loader in (paramiko.RSAKey, paramiko.ECDSAKey, paramiko.Ed25519Key):
        try:
            loader.from_private_key_file(path)
            return False
        except paramiko.PasswordRequiredException:
            return True
        except Exception:  # noqa: BLE001 — the wrong class for this file: try the next one
            continue
    return False


def resolve_passphrase(host, user, port, key_path, passphrase="", password="", verification_code=""):
    """The passphrase the connect will use: the caller's, or the user's answer, or none.

    The ask happens ONLY where paramiko's own `passphrase = password` alias cannot help — no
    passphrase, no password and no code were given AND the key file is encrypted. A `None` answer (a
    cancelled dialog, or a build without a surface) is the declared refusal, not a silent no-op:
    without it the connection dies inside paramiko with a `PasswordRequiredException` nobody explains.
    """
    if passphrase or password or verification_code:
        return passphrase
    if not key_needs_passphrase(key_path):
        return passphrase
    answer = _ask.ask(_ask.KIND_KEY_PASSPHRASE, host=host, user=user, port=port,
                      key_path=resolve_local_path(key_path))
    if answer is None:
        raise ConnectionCancelled(_t("ssh.key_passphrase_required", host=host))
    return str(answer)


def _ask_for_second_factor(host, user, port):
    """The handler of the keyboard-interactive prompt: the USER answers, never the process's stdin.

    Returns the list paramiko expects. Raising is the honest answer for "nobody could answer": it
    reaches the caller as this module's `ConnectionCancelled` (`None` on the ask means a cancelled
    dialog, and no installed surface means the build cannot ask at all).
    """
    def handler(title, instructions, prompt_list):
        if not prompt_list:
            return []
        if not _ask.has_answerer():
            raise ConnectionCancelled(_t("ssh.second_factor_unsupported", host=host, port=port))
        answers = []
        for prompt, show_input in prompt_list:
            value = _ask.ask(_ask.KIND_SECOND_FACTOR, host=host, user=user, port=port,
                             title=title or "", instructions=instructions or "",
                             prompt=prompt or "", secret=not bool(show_input))
            if value is None:
                raise ConnectionCancelled(_t("ssh.auth_cancelled", host=host, port=port))
            answers.append(str(value))
        return answers

    return handler


def interactive_transport_factory(host, user, port):
    """A `transport_factory` whose keyboard-interactive prompt is OUR handler. THE handler contract.

    `SSHClient.connect()` exposes no handler, and paramiko's own fallback prints the prompt to stdout
    and reads the process's stdin — an `EOFError` under a GUI and a prompt in the wrong window in a
    console. Substituting the transport is the ONE seam that closes it: the handler runs on the
    transport thread and marshals its question through `modules/interactive_ask.py`.
    """
    class _AnsweringTransport(paramiko.Transport):
        """A transport that never lets a second factor reach the process's stdin."""

        def auth_interactive_dumb(self, username, handler=None, submethods=""):
            if handler is None:
                handler = _ask_for_second_factor(host, user, port)
            return super().auth_interactive_dumb(username, handler, submethods)

        def auth_interactive(self, username, handler=None, submethods=""):
            if handler is None:
                handler = _ask_for_second_factor(host, user, port)
            return paramiko.Transport.auth_interactive(self, username, handler, submethods)

    def factory(sock, disabled_algorithms=None):
        return _AnsweringTransport(sock, disabled_algorithms=disabled_algorithms)

    return factory


class _JumpSocket:
    """A `direct-tcpip` channel that also closes the bastion client when the target closes it.

    The target's `Transport.close()` closes its socket; closing that socket is the ONLY deterministic
    teardown of the bastion, so the wrapper delegates every channel method and owns the bastion's life.
    """

    def __init__(self, channel, owner):
        self._channel = channel
        self._owner = owner
        self._closed = False

    def send(self, data):
        return self._channel.send(data)

    def recv(self, size):
        return self._channel.recv(size)

    def settimeout(self, timeout):
        return self._channel.settimeout(timeout)

    def close(self):
        if self._closed:
            return
        self._closed = True
        _close_quiet(self._channel)
        _close_quiet(self._owner)

    def __getattr__(self, name):
        return getattr(self._channel, name)


def _make_policy(policy_factory, hostname, port, role):
    """The host-key policy of ONE endpoint — the caller's factory, otherwise the GUI's own policy."""
    if policy_factory is None:
        return _host_key_policy.SshKnownHostsPolicy(hostname=hostname, port=port)
    return policy_factory(hostname, port, role)


def _jump_policy_factory(policy_factory):
    """The bastion's policy factory: the caller's factory, always asked about the JUMP role."""
    if policy_factory is None:
        return None
    return lambda hostname, port, _role: policy_factory(hostname, port, ROLE_JUMP)


def _open_jump_socket(spec, jump_key_path, timeout, banner_timeout, auth_timeout,
                      client_factory, policy_factory, target_host, target_port):
    """Authenticate to the bastion and open ONE `direct-tcpip` channel to the target.

    The bastion is a CONNECT like any other (`connect_client()` with its own policy and the picking
    transport), then one channel is opened and wrapped; a failure closes the bastion client before it
    reaches the caller.
    """
    jump_client, _jump_policy = connect_client(
        spec.host, spec.user, spec.port, password="", key_path=jump_key_path,
        timeout=timeout, banner_timeout=banner_timeout, auth_timeout=auth_timeout,
        transport_factory=interactive_transport_factory(spec.host, spec.user, spec.port),
        client_factory=client_factory, policy_factory=_jump_policy_factory(policy_factory))
    try:
        transport = jump_client.get_transport()
        if transport is None:
            raise paramiko.SSHException("the jump host answered no transport")
        channel = transport.open_channel("direct-tcpip", (target_host, target_port),
                                         ("127.0.0.1", 0), timeout=timeout)
    except Exception:
        _close_quiet(jump_client)
        raise
    return _JumpSocket(channel, jump_client)


def connect_client(host, user, port, password="", key_path="", client=None,
                   timeout=CONNECT_TIMEOUT_S, banner_timeout=None, auth_timeout=None,
                   passphrase="", verification_code="", transport_factory=None,
                   jump=None, jump_key_path="", client_factory=None, policy_factory=None):
    """A CONNECTED client with the application's known-hosts policy applied.

    Answers `(client, policy)`: the caller keeps the policy, because a FIRST connection is the one
    that reports what it trusted (`accepted_new_key`, `last_fingerprint`) and whether the key really
    reached the store (`pinned` — an unreadable file remembers nothing, and the caller says so).
    `client` may be handed IN — the two sites that close their client in a `finally:` build it before
    the `try` — otherwise it is created through `client_factory` (default: the `paramiko` ATTRIBUTE),
    so a suite that substitutes either sees the very client the application would use.

    A non-empty `jump` (the raw `ServerData.jump_host` or a `JumpSpec`) adds ONE internal hop: a
    bastion client and a `direct-tcpip` channel to this endpoint, handed over as `sock=`. The bastion
    authenticates with `jump_key_path` or the key/agent fallback — NEVER the target's password — and
    gets its OWN policy from `policy_factory(hostname, port, role)`, so both endpoints are judged and
    reported separately. The channel and the bastion client die with the target's `close()`.

    A CHANGED host key is ONE question, not a failure: `resolve_changed_key()` asks the user, and a yes
    replaces the stored entry and reconnects on a FRESH client and a FRESH hop (the failed ones are
    closed here, so a caller that closes what it got back never leaks one). A no re-raises the original
    exception. A FAILED `connect()` closes the client THIS FUNCTION created and the hop it opened — a
    client handed IN belongs to its caller, so it is never closed here (`N101`).
    """
    spec = parse_jump(jump, default_user=user) if jump else None
    kwargs = build_connect_kwargs(
        host, user, port, password, key_path,
        passphrase=resolve_passphrase(host, user, port, key_path, passphrase,
                                      password=password, verification_code=verification_code),
        verification_code=verification_code, timeout=timeout,
        banner_timeout=banner_timeout, auth_timeout=auth_timeout,
        transport_factory=(transport_factory or interactive_transport_factory(host, user, port)))
    attempts_left = KEY_RETRY_ATTEMPTS
    factory = client_factory or paramiko.SSHClient
    while True:
        ours = client is None
        if ours:
            client = factory()
        jump_socket = None
        try:
            policy = _make_policy(policy_factory, host, port, ROLE_TARGET)
            policy.apply_to_client(client)
            if spec is not None:
                jump_socket = _open_jump_socket(
                    spec, jump_key_path, timeout, banner_timeout, auth_timeout,
                    client_factory, policy_factory, host, port)
                kwargs["sock"] = jump_socket
            client.connect(**kwargs)
            return client, policy
        except paramiko.BadHostKeyException as exc:
            _close_quiet(jump_socket)
            attempts_left -= 1
            # ONE question, and only while attempts remain: the decision is asked OUTSIDE the failure
            # handler, so a raising ask cannot be mistaken for the connection's own failure.
            replaced = attempts_left > 0 and _key_replaced(exc, host, port)
            if replaced:
                _close_quiet(client)
                client = None
                continue
            _close_quiet(client if ours else None)
            raise
        except Exception:
            # EVERY other failure — the refused login, the timeout, the prompt that never answered —
            # would leave a client nobody can close: the caller never received it. (`N101`)
            _close_quiet(jump_socket)
            _close_quiet(client if ours else None)
            raise


def _key_replaced(exc, host, port) -> bool:
    """`resolve_changed_key()`'s answer as a decision: a raising question REFUSES the replacement.

    The user is asked whether the stored key may be replaced; a surface that blows up, a store that
    cannot be written and a plain "no" all mean the same thing here — the original exception stands.
    """
    try:
        return bool(_host_key_policy.resolve_changed_key(exc, host, port))
    except Exception:  # noqa: BLE001 — a failed question is a refusal, never the caller's exception
        return False


def _close_quiet(client) -> None:
    """Close a client/channel this module owns; a `None` is a no-op and a failing `close()` is not the news.

    The failure the caller is about to see is the CONNECTION's, never the clean-up's — a half-open
    client that refuses to close must not replace the real exception on its way out.
    """
    if client is None:
        return
    try:
        client.close()
    except Exception:  # noqa: BLE001 — the cleanup never masks the connection failure
        pass
