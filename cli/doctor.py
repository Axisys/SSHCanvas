# -*- coding: utf-8 -*-
"""`doctor` — the reachability report of ONE node, over the GUI's own PURE diagnostics core.

`services.reachability.diagnose_reachability()` walks DNS → TCP → SSH banner (→ ICMP) and names the FIRST
failing step, so the CLI's answer and the map's "Why is it offline?" dialog are one computation. The
report is the verb's DATA even when the node is broken: the process exits with the verdict's class (`0`
ok, `4` network, `6` timeout) while the envelope keeps `ok: true` — the run answered, the node failed.
The TEXT form rounds `elapsed` for a human; the envelope keeps its full float. `AGENTS.md` §4.35;
contract — `CLI.md` §3.4.
"""
from services.reachability import KIND_DNS_TIMEOUT, KIND_OK, KIND_TCP_TIMEOUT, diagnose_reachability

from . import project as PROJECT_SOURCE
from . import verb_args
from .dispatch import Verb, register
from .errors import usage_error
from .exit_codes import EXIT_NETWORK, EXIT_TIMEOUT

NAME = "doctor"
SUMMARY = "the reachability report of one node (id or alias)"

#: The `data` keys — the report's own fields, in order (the machine contract of `CLI.md` §3.4).
DATA_KEYS = ("host", "port", "kind", "ip", "detail", "ping", "elapsed")

#: kind → the exit class. A timeout is `6`; every other failure is `4` (`network`), `ok` is `0`.
KIND_EXIT_CODES = {KIND_OK: 0, KIND_DNS_TIMEOUT: EXIT_TIMEOUT, KIND_TCP_TIMEOUT: EXIT_TIMEOUT}
DEFAULT_EXIT_CODE = EXIT_NETWORK

#: The decimals the TEXT form keeps of `elapsed` — the envelope keeps the measured float.
ELAPSED_DECIMALS = 3


def exit_code_for_kind(kind) -> int:
    """The process code a verdict decides (a foreign kind is a network failure, never a crash)."""
    return KIND_EXIT_CODES.get(str(kind or ""), DEFAULT_EXIT_CODE)


def handle(context, arguments):
    """The verb's FACTS — the ONE report's own fields."""
    tokens = verb_args.read_nodes(NAME, arguments)
    if not tokens:
        raise usage_error(f"{NAME} needs a node", "pass an id or an alias (see --help)")
    nodes = PROJECT_SOURCE.select_servers(
        PROJECT_SOURCE.read_servers(PROJECT_SOURCE.resolve_path(context.project)), tokens)
    if len(nodes) != 1:
        raise usage_error(f"{tokens[0]!r} names {len(nodes)} nodes", "pass an id (see --help)")
    node = nodes[0]
    report = diagnose_reachability(str(getattr(node, "host", "") or ""),
                                   int(getattr(node, "ssh_port", 22) or 22), context.timeout)
    return {"host": report.host, "port": report.port, "kind": report.kind, "ip": report.ip,
            "detail": report.detail, "ping": report.ping, "elapsed": report.elapsed}


def verdict(payload) -> int:
    """The report's OWN verdict decides the process code (`ok` 0, a timeout 6, else 4)."""
    return exit_code_for_kind((payload or {}).get("kind"))


def text_value(key, value) -> str:
    """ONE report field as text (PURE) — `elapsed` is rounded HERE, and only the TEXT form."""
    if key == "elapsed":
        try:
            return f"{float(value):.{ELAPSED_DECIMALS}f}"
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def render(context, payload) -> list:
    """The same facts, one `key: value` line each (English, no i18n key)."""
    payload = payload or {}
    return [f"{key}: {text_value(key, payload.get(key, ''))}" for key in DATA_KEYS]


register(Verb(NAME, SUMMARY, handler=handle, render=render, verdict=verdict,
              min_args=1, max_args=1))
