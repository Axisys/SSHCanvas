# -*- coding: utf-8 -*-
"""The ONE failure type of the headless surface — a message, its exit class and an optional hint.

A verb raises `CliError`; the dispatcher turns it into the `--json` error record or one stderr line and
exits with `code`. Nothing here prints: a surface that formats its own failure cannot be tested without
capturing a process, and the exit code IS the contract (`cli/exit_codes.py`, `CLI.md`).
"""
from .exit_codes import (EXIT_AUTH, EXIT_NETWORK, EXIT_NOT_FOUND, EXIT_REFUSAL, EXIT_TIMEOUT,
                         EXIT_USAGE, exit_name)


class CliError(Exception):
    """A declared failure: `message` for a human, `code` for the process, `hint` for the next step."""

    def __init__(self, message, code=EXIT_USAGE, hint="", detail=""):
        self.message = str(message or "")
        self.code = int(code)
        self.hint = str(hint or "")
        self.detail = str(detail or "")
        super().__init__(self.message)

    @property
    def kind(self) -> str:
        """The machine class of the failure (`usage`, `refusal`, …) — see `EXIT_NAMES`."""
        return exit_name(self.code)

    def record(self) -> dict:
        """The failure as the `--json` envelope's `error` object."""
        return {"code": self.code, "kind": self.kind,
                "message": self.message, "hint": self.hint}

    def sentence(self) -> str:
        """The one stderr line: the message, and the hint only when there is one."""
        return f"{self.message} ({self.hint})" if self.hint else self.message


def usage_error(message, hint="") -> CliError:
    """The command line itself is wrong (`--help` names the accepted forms)."""
    return CliError(message, EXIT_USAGE, hint or "see --help")


def refusal(message, hint="") -> CliError:
    """A declared policy refused the operation — never a partial run."""
    return CliError(message, EXIT_REFUSAL, hint)


def not_found(message, hint="") -> CliError:
    """The named project / node / entry is not there (the message names what was looked for)."""
    return CliError(message, EXIT_NOT_FOUND, hint)


def auth_error(message, hint="") -> CliError:
    """The endpoint refused the credential, or no credential could be completed (`--identity` here)."""
    return CliError(message, EXIT_AUTH, hint)


def network_error(message, hint="") -> CliError:
    """The endpoint did not answer as a network peer (a refused port, a bad banner, no route)."""
    return CliError(message, EXIT_NETWORK, hint)


def timeout_error(message, hint="") -> CliError:
    """`--timeout` ran out before the operation finished (the connect or the command)."""
    return CliError(message, EXIT_TIMEOUT, hint)
