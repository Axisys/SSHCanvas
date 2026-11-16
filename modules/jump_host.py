# -*- coding: utf-8 -*-
"""The ONE reader of the internal jump host: `[user@]host[:port]`, exactly ONE hop.

`ServerData.jump_host` is REQUEST data (`models/server.py`): the external terminal hands it to `ssh -J`
verbatim (a comma chain included), while the internal path parses it here into ONE `JumpSpec` for the
`direct-tcpip` channel of `modules/ssh_connect.py`. It is an ADDRESS, never a credential: a password, a
chain, a space or a `ProxyCommand` is refused before a socket exists; an omitted user is the target's,
an omitted port is 22, and a refusal carries a `REASON_*` code (`jump_error_text()` translates it).
Tests — `tests/test_jump_host.py`; rule — `AGENTS.md` §4.4.2; mechanism — `DOCUMENTATION.md` §16."""

import re
from dataclasses import dataclass
from typing import Optional

try:
    from .external_terminal import host_problem, user_problem
except ImportError:  # flat launch from the project root
    from external_terminal import host_problem, user_problem

#: A port is ASCII digits only — `str.isdigit()` would also accept a non-ASCII numeral.
_PORT_RE = re.compile(r"[0-9]+")
#: A space inside the value is a refusal: the predicates `.strip()` their own input, so an inner space
#: would survive into the socket (`ops @bastion`, `ops@ bastion`) and fail as a DNS/auth error (`N195`).
_SPACE_RE = re.compile(r"\s")
_DEFAULT_PORT = 22
_PORT_MIN, _PORT_MAX = 1, 65535

#: The reason codes a refusal carries — `JUMP_ERROR_KEYS` names their ONE translated sentence.
REASON_HOST = "host"              # empty, option-shaped or outside the address allowlist
REASON_USER = "user"              # option-shaped or outside the login allowlist
REASON_PORT = "port"              # not ASCII digits, or outside 1..65535
REASON_BRACKETS = "brackets"      # a broken/missing bracket of an IPv6 literal
REASON_WHITESPACE = "whitespace"  # a space inside the value
REASON_CHAIN = "chain"            # a comma chain: the external `-J` carries it, this reader is ONE hop

#: reason → the i18n key of its sentence (`ssh_connect.jump_error_text()` is the reader).
JUMP_ERROR_KEYS = {
    REASON_HOST: "ssh.jump_host_invalid",
    REASON_USER: "ssh.jump_user_invalid",
    REASON_PORT: "ssh.jump_port_invalid",
    REASON_BRACKETS: "ssh.jump_host_brackets",
    REASON_WHITESPACE: "ssh.jump_host_whitespace",
    REASON_CHAIN: "ssh.jump_chain_internal",
}


class JumpSpecError(ValueError):
    """The jump field cannot become a hop — the caller refuses BEFORE opening a socket.

    `reason` is one of the `REASON_*` codes; the message is English for the log and the CLI, while a
    surface shows `ssh_connect.jump_error_text()` (`AGENTS.md` §4.5).
    """

    def __init__(self, message, reason=REASON_HOST):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class JumpSpec:
    """ONE internal hop: the bastion endpoint, never a credential."""

    host: str
    port: int = _DEFAULT_PORT
    user: str = ""

    @property
    def label(self) -> str:
        """`user@host:port` (or `host:port`) — the ONE spelling an error and a log line share."""
        return f"{self.user}@{self.host}:{self.port}" if self.user else f"{self.host}:{self.port}"


def _endpoint(hostport: str):
    """`(host, port)` from the bracketed/unbracketed host part — a bad bracket or port raises."""
    if hostport.startswith("["):
        end = hostport.find("]")
        if end < 0:
            raise JumpSpecError(
                "the jump host has an unmatched '[' — write an IPv6 literal as [addr]:port",
                REASON_BRACKETS)
        host = hostport[1:end]
        rest = hostport[end + 1:]
        if not rest:
            return host, _DEFAULT_PORT
        if not rest.startswith(":"):
            raise JumpSpecError("the jump host has text after the bracketed address", REASON_BRACKETS)
        return host, _port(rest[1:])
    if hostport.count(":") > 1:
        raise JumpSpecError("an IPv6 jump host must be bracketed: [addr]:port", REASON_BRACKETS)
    host, separator, port_text = hostport.rpartition(":")
    if not separator:
        return hostport, _DEFAULT_PORT
    return host, _port(port_text)


def _port(text: str) -> int:
    """The declared port — ASCII digits in 1..65535, everything else is a refusal."""
    if not _PORT_RE.fullmatch(text or ""):
        raise JumpSpecError(f"the jump host port must be a number, got {text!r}", REASON_PORT)
    port = int(text)
    if not (_PORT_MIN <= port <= _PORT_MAX):
        raise JumpSpecError(f"the jump host port must be {_PORT_MIN}..{_PORT_MAX}, got {port}",
                            REASON_PORT)
    return port


def _refusal(problem: str, what: str, reason: str) -> JumpSpecError:
    """The one sentence a refused predicate answers (the predicate's own code is the branch)."""
    if problem == "empty":
        text = f"the jump {what} is empty"
    elif problem == "option":
        text = f"the jump {what} may not start with '-'"
    else:
        text = f"the jump {what} contains a character this hop cannot carry"
    return JumpSpecError(text, reason)


def _no_space(host: str, user: str) -> None:
    """A space that survived the outer strip is a value no socket can carry (`N195`)."""
    if _SPACE_RE.search(host) or _SPACE_RE.search(user):
        raise JumpSpecError("the jump host contains whitespace — write it without spaces",
                            REASON_WHITESPACE)


def parse_jump(text, default_user: str = "") -> Optional[JumpSpec]:
    """`ServerData.jump_host` → ONE `JumpSpec`, or `None` when the field is empty (PURE).

    `default_user` answers when the value carries no `user@` — the map card's own login, the
    documented fallback. A comma chain, a password (`user:secret@host`), a space and a value outside
    the shipped address alphabet are `JumpSpecError`s: an internal hop is ONE bastion, and a secret
    never travels in this field.
    """
    if isinstance(text, JumpSpec):
        host, user = str(text.host or "").strip(), str(text.user or "").strip()
        _no_space(host, user)
        problem = host_problem(host)
        if problem:
            raise _refusal(problem, "host", REASON_HOST)
        problem = user_problem(user)
        if problem:
            raise _refusal(problem, "user", REASON_USER)
        try:
            number = int(text.port)
        except (TypeError, ValueError):
            raise JumpSpecError(f"the jump host port must be a number, got {text.port!r}", REASON_PORT)
        if not (_PORT_MIN <= number <= _PORT_MAX):
            raise JumpSpecError(f"the jump host port must be {_PORT_MIN}..{_PORT_MAX}, got {number}",
                                REASON_PORT)
        return JumpSpec(host, number, user or str(default_user or "").strip())
    raw = str(text if text is not None else "").strip()
    if not raw:
        return None
    _no_space(raw, "")
    if "," in raw:
        raise JumpSpecError("the internal jump host takes ONE host; a comma-separated chain belongs "
                            "to the external terminal (`ssh -J`)", REASON_CHAIN)
    user, separator, hostport = raw.rpartition("@")
    if separator:
        problem = user_problem(user)
        if problem:
            raise _refusal(problem, "user", REASON_USER)
    else:
        user = ""
    host, port = _endpoint(hostport)
    problem = host_problem(host)
    if problem:
        raise _refusal(problem, "host", REASON_HOST)
    return JumpSpec(host=host, port=port, user=(user or str(default_user or "").strip()))
