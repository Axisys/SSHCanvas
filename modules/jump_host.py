# -*- coding: utf-8 -*-
"""The ONE reader of the internal jump host: `[user@]host[:port]`, exactly ONE hop.

`ServerData.jump_host` is REQUEST data (`models/server.py`): the external terminal hands it to
`ssh -J` verbatim, while the internal path parses it here and turns it into a `JumpSpec` for the
`direct-tcpip` channel of `modules/ssh_connect.py`. The value is an ADDRESS, never a credential: a
password, a chain (`-J a,b`) or a `ProxyCommand` is refused here, before a socket exists. An omitted
user falls back to the target's user (the map card's own account); an omitted port is 22.
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
_DEFAULT_PORT = 22
_PORT_MIN, _PORT_MAX = 1, 65535


class JumpSpecError(ValueError):
    """The jump field cannot become a hop — the caller refuses BEFORE opening a socket."""


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
    """`(host, port)` from the bracketed/unbracketed host part — a bad port raises."""
    if hostport.startswith("["):
        end = hostport.find("]")
        if end < 0:
            raise JumpSpecError("the jump host has an unmatched '[' — write an IPv6 literal as [addr]:port")
        host = hostport[1:end]
        rest = hostport[end + 1:]
        if not rest:
            return host, _DEFAULT_PORT
        if not rest.startswith(":"):
            raise JumpSpecError("the jump host has text after the bracketed address")
        return host, _port(rest[1:])
    if hostport.count(":") > 1:
        raise JumpSpecError("an IPv6 jump host must be bracketed: [addr]:port")
    host, separator, port_text = hostport.rpartition(":")
    if not separator:
        return hostport, _DEFAULT_PORT
    return host, _port(port_text)


def _port(text: str) -> int:
    """The declared port — ASCII digits in 1..65535, everything else is a refusal."""
    if not _PORT_RE.fullmatch(text or ""):
        raise JumpSpecError(f"the jump host port must be a number, got {text!r}")
    port = int(text)
    if not (_PORT_MIN <= port <= _PORT_MAX):
        raise JumpSpecError(f"the jump host port must be {_PORT_MIN}..{_PORT_MAX}, got {port}")
    return port


def _reason(problem: str, what: str) -> str:
    """The one sentence a refused predicate answers (the predicate's own code is the branch)."""
    if problem == "empty":
        return f"the jump {what} is empty"
    if problem == "option":
        return f"the jump {what} may not start with '-'"
    return f"the jump {what} contains a character this hop cannot carry"


def parse_jump(text, default_user: str = "") -> Optional[JumpSpec]:
    """`ServerData.jump_host` → ONE `JumpSpec`, or `None` when the field is empty (PURE).

    `default_user` answers when the value carries no `user@` — the map card's own login, the
    documented fallback. A comma chain, a password (`user:secret@host`) and a value outside the
    shipped address alphabet are `JumpSpecError`s: an internal hop is ONE bastion, and a secret
    never travels in this field.
    """
    if isinstance(text, JumpSpec):
        host, user = str(text.host or "").strip(), str(text.user or "").strip()
        problem = host_problem(host)
        if problem:
            raise JumpSpecError(_reason(problem, "host"))
        problem = user_problem(user)
        if problem:
            raise JumpSpecError(_reason(problem, "user"))
        try:
            number = int(text.port)
        except (TypeError, ValueError):
            raise JumpSpecError(f"the jump host port must be a number, got {text.port!r}")
        if not (_PORT_MIN <= number <= _PORT_MAX):
            raise JumpSpecError(f"the jump host port must be {_PORT_MIN}..{_PORT_MAX}, got {number}")
        return JumpSpec(host, number, user or str(default_user or "").strip())
    raw = str(text if text is not None else "").strip()
    if not raw:
        return None
    if "," in raw:
        raise JumpSpecError("the internal jump host takes ONE host; a comma-separated chain belongs "
                            "to the external terminal (`ssh -J`)")
    user, separator, hostport = raw.rpartition("@")
    if separator:
        problem = user_problem(user)
        if problem:
            raise JumpSpecError(_reason(problem, "user"))
    else:
        user = ""
    host, port = _endpoint(hostport)
    problem = host_problem(host)
    if problem:
        raise JumpSpecError(_reason(problem, "host"))
    return JumpSpec(host=host, port=port, user=(user or str(default_user or "").strip()))
