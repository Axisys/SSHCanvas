# -*- coding: utf-8 -*-
"""The console entry point of the headless surface — the channels first, argv second, everything else last.

`main()` calls `cli/output.prepare_streams()` (a REDIRECTED stdout/stderr becomes UTF-8 with no newline
translation; a console keeps its own) and THEN parses argv, so a run that only needs `--help` or a usage
answer never loads the report layers; `cli/` imports nothing of the GUI and no module of it touches
PySide6, which is the gate the suite runs in a fresh process (`tests/test_cli.py` §2). This module is
what `pyproject.toml` names: `sshcanvas-cli = "cli.main:main"` and its `sshmap-cli` alias. A launcher
must not swallow the code: `main()` answers the integer and the console script exits with it.
`AGENTS.md` §4.35; contract — `CLI.md`.
"""
import sys

from . import output as OUT
from .args import parse_argv
from .errors import CliError


def main(argv=None) -> int:
    """Run the command line in `argv` (default: `sys.argv[1:]`) and answer the process's exit code."""
    OUT.prepare_streams()
    tokens = list(sys.argv[1:] if argv is None else argv)
    try:
        invocation = parse_argv(tokens)
    except CliError as exc:
        # The line itself is wrong: nothing is dispatched, and the answer still has the ONE shape a
        # caller parses — the envelope when `--json` was on the line, a stderr sentence otherwise. The
        # verb is not named: a line this module could not read has no verb it can trust.
        from . import envelope as ENV
        OUT.report(ENV.build("", error=exc.record()), (), "--json" in tokens)
        return exc.code
    from .dispatch import dispatch
    return dispatch(invocation)


if __name__ == "__main__":  # pragma: no cover — `python -m cli.main` is a debugging door
    sys.exit(main())
