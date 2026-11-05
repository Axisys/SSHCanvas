# -*- coding: utf-8 -*-
"""The argv grammar of the headless surface — the OPTION TABLE, the ONE parse and the help text.

The grammar is deliberately tiny: `sshcanvas-cli [options] [verb [arguments…]]`. Every option is
declared ONCE in `OPTIONS` (`--json`, `--project`, `--timeout`, `--help`, `--version`), so the parse, the
help text and the contract cannot drift; `--option=value` and `--option value` are the same thing. The
first bare token is the VERB and everything after it belongs to that verb — the surface never guesses at
a verb's own flags. Nothing is imported for a verb here: this module is pure argv and the standard library,
which is what lets `cli/main.py` parse before anything else loads (`AGENTS.md` §4.35; contract — `CLI.md`).
"""
import os
from dataclasses import dataclass, field

from .errors import usage_error

OPTION_JSON = "--json"
OPTION_PROJECT = "--project"
OPTION_TIMEOUT = "--timeout"
OPTION_HELP = "--help"
OPTION_VERSION = "--version"
HELP_ALIASES = ("-h",)
VERSION_ALIASES = ("-V",)

#: (option, takes a value, metavar) — the ONE option table: the parse and the help text read it.
OPTIONS = (
    (OPTION_JSON, False, ""),
    (OPTION_PROJECT, True, "PATH"),
    (OPTION_TIMEOUT, True, "SECONDS"),
    (OPTION_HELP, False, ""),
    (OPTION_VERSION, False, ""),
)

#: The declared budget of a verb's network work, in seconds — the DEFAULT, the floor and the ceiling.
TIMEOUT_DEFAULT_S = 10.0
TIMEOUT_MIN_S = 1.0
TIMEOUT_MAX_S = 300.0

#: The one-line form every diagnostic and the help text start with.
PROGRAM = "sshcanvas-cli"
USAGE = f"usage: {PROGRAM} [options] [verb [arguments...]]"

#: Every LONG GLOBAL option — one written after the verb is refused with this table as its hint. The
#: short aliases stay out: `-h` is a flag of many commands (`df -h`), so the verb's own hint speaks.
GLOBAL_TOKENS = frozenset(name for name, _takes, _meta in OPTIONS if name.startswith("--"))


def late_option_hint(name) -> str:
    """The hint of a GLOBAL option written after the verb — it names the grammar, never a second rule.

    PURE. "" for a token this surface does not declare globally: the caller's own sentence is the whole
    answer then (a verb's flags are the verb's business, `cli/verb_args.py`).
    """
    if str(name or "") not in GLOBAL_TOKENS:
        return ""
    return f"global options go BEFORE the verb ({USAGE})"


@dataclass(frozen=True)
class Invocation:
    """ONE parsed command line: the verb and its arguments beside the options that apply to any verb."""

    verb: str = ""
    arguments: tuple = field(default=())
    json: bool = False
    project: str = ""          # the RESOLVED path ("" — the verb's own default)
    timeout: float = TIMEOUT_DEFAULT_S
    help: bool = False
    version: bool = False

    @property
    def has_verb(self) -> bool:
        """Was a verb actually named on the command line?"""
        return bool(self.verb)


def resolve_project_path(text, base_dir=None) -> str:
    """The project path a value names: `~` expanded and the result made ABSOLUTE ("" — no path).

    A relative path is joined to `base_dir` (the caller's, otherwise the process's directory), so a
    `--project` given from a script's own folder means what the script meant, and the same string in a
    `--json` envelope names the ONE file every run reads. Never raises: an unusable value is "".
    """
    try:
        raw = str(text or "").strip()
    except Exception:  # noqa: BLE001 — a __str__ that raises is not a path
        return ""
    if not raw:
        return ""
    try:
        expanded = os.path.expanduser(raw)
    except Exception:  # noqa: BLE001 — a platform without a home directory
        expanded = raw
    base = base_dir
    if base is None:
        try:
            base = os.getcwd()
        except Exception:  # noqa: BLE001 — a process without a current directory
            base = ""
    try:
        if not os.path.isabs(expanded) and base:
            expanded = os.path.join(base, expanded)
        return os.path.normpath(expanded)
    except Exception:  # noqa: BLE001 — the caller owns the fallback: the expanded path is usable
        return expanded


def parse_timeout(text) -> float:
    """The `--timeout` value as the declared budget — a non-number or an out-of-range one is USAGE."""
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        raise usage_error(f"{OPTION_TIMEOUT} takes a number of seconds, got {text!r}")
    if not (TIMEOUT_MIN_S <= value <= TIMEOUT_MAX_S):
        raise usage_error(f"{OPTION_TIMEOUT} takes {TIMEOUT_MIN_S:g}..{TIMEOUT_MAX_S:g} seconds, "
                          f"got {value:g}")
    return value


def _split_option(token):
    """`--opt=value` → `("--opt", "value")`; a bare option answers `(token, None)`."""
    name, sep, value = str(token).partition("=")
    return (name, value) if sep else (token, None)


#: Every global option that CONSUMES the next token — the walk of `json_requested()` skips its value.
TAKES_VALUE = frozenset(name for name, takes, _meta in OPTIONS if takes)


def json_requested(tokens) -> bool:
    """True when `--json` is an OPTION of the line, never a VALUE or a verb's argument (PURE).

    The failure path answers before `parse_argv()` can hand back an `Invocation`, so the question "was
    the envelope asked for?" is asked of the raw tokens — by walking the SAME grammar: an option that
    takes a value consumes the next token (`--project --json` names a file), `--` ends the options and
    the first bare token is the VERB, whose tail belongs to the verb.
    """
    tokens = [t for t in (tokens if tokens is not None else ()) if isinstance(t, str)]
    index, asked = 0, False
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token == "--":
            return asked          # everything after it is the verb's tail
        if token in HELP_ALIASES or token in VERSION_ALIASES:
            continue
        if token.startswith("--"):
            name, value = _split_option(token)
            if name == OPTION_JSON and value in (None, ""):
                asked = True
            elif name in TAKES_VALUE and value is None:
                index += 1        # its VALUE — a token that spells `--json` is data here
            continue
        if token.startswith("-") and token != "-":
            continue
        return asked              # the first bare token is the VERB: the parse STOPS there
    return asked


def parse_argv(tokens, base_dir=None) -> Invocation:
    """The ONE parse: options, the verb and its arguments — or a USAGE error naming what is wrong.

    A flag this surface does not declare is a USAGE error (a launched GUI tolerates one; a scripted tool
    that silently ignored `--jsno` would run a report nobody reads), a repeated option takes its LAST
    value, and `--` ends the options: everything after it belongs to the verb verbatim. The FIRST bare
    token is the verb and the parse STOPS there: every later token is that verb's argument, flags
    included, so `inventory --tag prod` reaches the verb's own declared table (`cli/verb_args.py`) instead
    of being refused by the global one.
    """
    tokens = [t for t in (tokens if tokens is not None else ()) if isinstance(t, str)]
    wanted = {name for name, _takes, _meta in OPTIONS}
    options = {"json": False, "project": "", "timeout": TIMEOUT_DEFAULT_S,
               "help": False, "version": False}
    verb, arguments = "", []
    index, bare = 0, False

    while index < len(tokens):
        token = tokens[index]
        index += 1
        if verb:
            arguments.append(token)
            continue
        if bare:
            verb = token
            continue
        if token == "--":
            bare = True
            continue
        if token in HELP_ALIASES:
            options["help"] = True
            continue
        if token in VERSION_ALIASES:
            options["version"] = True
            continue
        if token.startswith("--"):
            name, value = _split_option(token)
            if name not in wanted:
                raise usage_error(f"unknown option {name!r}")
            if name == OPTION_HELP:
                options["help"] = True
                continue
            if name == OPTION_VERSION:
                options["version"] = True
                continue
            if name == OPTION_JSON:
                if value not in (None, ""):
                    raise usage_error(f"{OPTION_JSON} takes no value")
                options["json"] = True
                continue
            if value is None:
                if index >= len(tokens):
                    raise usage_error(f"{name} needs a value")
                value = tokens[index]
                index += 1
            if name == OPTION_PROJECT:
                options["project"] = resolve_project_path(value, base_dir)
            elif name == OPTION_TIMEOUT:
                options["timeout"] = parse_timeout(value)
            continue
        if token.startswith("-") and token != "-":
            raise usage_error(f"unknown option {token!r}")
        verb = token
    return Invocation(verb=verb, arguments=tuple(arguments), **options)


def usage_text(verbs=()) -> str:
    """The help text: the one-line usage, every declared option and the verb rows the caller passes.

    `verbs` is the registry's own table (`(name, summary)` pairs), so the help and the dispatch read ONE
    declaration — a verb that is added to the registry appears here without a second edit.
    """
    lines = [USAGE, "", "options:"]
    for name, takes, metavar in OPTIONS:
        spelled = f"{name} {metavar}" if takes else name
        lines.append(f"  {spelled:<18} {OPTION_HELP_TEXT[name]}")
    lines += ["", "verbs:"]
    rows = list(verbs or ())
    if not rows:
        lines.append("  (this build declares none)")
    for name, summary in rows:
        lines.append(f"  {name:<18} {summary}")
    lines += ["", "exit codes: 0 ok, 1 usage, 2 refusal, 3 auth, 4 network, 5 not found, 6 timeout"]
    return "\n".join(lines)


#: The ONE description of every option (the help text reads THIS table, never a second sentence).
OPTION_HELP_TEXT = {
    OPTION_JSON: "print the JSON envelope instead of text",
    OPTION_PROJECT: "the project file the verb reads (default: the last opened one)",
    OPTION_TIMEOUT: f"the budget of a verb's network work, {TIMEOUT_MIN_S:g}..{TIMEOUT_MAX_S:g} s",
    OPTION_HELP: "print this text and exit 0",
    OPTION_VERSION: "print the application version and exit 0",
}
