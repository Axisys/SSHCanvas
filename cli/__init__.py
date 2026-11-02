# -*- coding: utf-8 -*-
"""The headless surface of SSHCanvas — a SECOND console entry point over the shipped layers, no Qt.

`sshcanvas-cli` (and its `sshmap-cli` alias) parses ONE command line, dispatches ONE verb and prints ONE
machine contract: the report on stdout, the diagnostics on stderr, the `--json` envelope when asked, and the
process exit code of the class the run ended in. The GUI is untouched and imports nothing from here; this
package imports nothing of the GUI — `tests/test_cli.py` §2 enforces that in a fresh process per module.

The submodules are the API (`cli.main:main` is the console script's target, `cli.dispatch.VERBS` the verb
table; `python -m cli` is the uninstalled door) — `cli.main`/`cli.dispatch` stay MODULES, never functions.

Contract — `CLI.md`; rules — `AGENTS.md` §4.35; mechanism — `DOCUMENTATION.md` §80.
"""
from . import args, dispatch, envelope, errors, exit_codes, main, output
from .dispatch import VERBS, Context, Verb, register
from .errors import CliError
from .exit_codes import (EXIT_AUTH, EXIT_NAMES, EXIT_NETWORK, EXIT_NOT_FOUND, EXIT_OK,
                         EXIT_REFUSAL, EXIT_TIMEOUT, EXIT_USAGE)

__all__ = [
    # the submodules (a name only, so `cli.main:main` and `cli.dispatch.VERBS` are reachable)
    "args", "dispatch", "envelope", "errors", "exit_codes", "main", "output",
    # the API a verb module imports
    "VERBS", "Context", "Verb", "register", "CliError",
    "EXIT_OK", "EXIT_USAGE", "EXIT_REFUSAL", "EXIT_AUTH", "EXIT_NETWORK", "EXIT_NOT_FOUND",
    "EXIT_TIMEOUT", "EXIT_NAMES",
]
