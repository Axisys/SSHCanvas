# -*- coding: utf-8 -*-
"""The exit-code table of the headless surface — the ONE declaration of what a process answer means.

The seven codes are the contract a script (cron, Task Scheduler, a systemd unit) checks instead of
reading a sentence: `0` ok, `1` usage, `2` refusal, `3` auth, `4` network, `5` not found, `6` timeout.
`EXIT_NAMES` is the same table as a mapping, so a message, a `--json` envelope and a test all spell a
class the same way. `AGENTS.md` §4.35; contract — `CLI.md`.
"""

EXIT_OK = 0          # the verb answered and its report is on stdout
EXIT_USAGE = 1       # the command line could not be carried out as asked
EXIT_REFUSAL = 2     # a declared policy refused the operation (the command guard, an unpinned key)
EXIT_AUTH = 3        # the endpoint refused the credential, or no credential could be resolved
EXIT_NETWORK = 4     # the endpoint did not answer as a network peer
EXIT_NOT_FOUND = 5   # the named thing (a project, a node, an entry) is not there
EXIT_TIMEOUT = 6     # the declared budget ran out before the operation finished

#: code → the machine NAME of the class (the `kind` field of a `--json` error record).
EXIT_NAMES = {
    EXIT_OK: "ok",
    EXIT_USAGE: "usage",
    EXIT_REFUSAL: "refusal",
    EXIT_AUTH: "auth",
    EXIT_NETWORK: "network",
    EXIT_NOT_FOUND: "not_found",
    EXIT_TIMEOUT: "timeout",
}

#: Every declared code, mildest first — the ONE list a table, a test or a help text walks.
EXIT_CODES = tuple(EXIT_NAMES)


def exit_name(code) -> str:
    """The machine name of a declared code ("unknown" for anything else — never an exception)."""
    try:
        return EXIT_NAMES.get(int(code), "unknown")
    except (TypeError, ValueError):
        return "unknown"


def is_declared(code) -> bool:
    """Is `code` one of the seven the contract declares?"""
    try:
        return int(code) in EXIT_NAMES
    except (TypeError, ValueError):
        return False
