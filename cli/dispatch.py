# -*- coding: utf-8 -*-
"""The verb table and the ONE dispatch — the door every verb of the surface goes through.

`VERBS` is the registry: ONE `Verb` row per verb (`name`, `summary`, `handler`, `render`, `verdict`), and
a verb its row does not hold is a USAGE error. A handler answers FACTS and the row's `render` draws the
same facts as text; `verdict(data)` is the process code a SUCCESSFUL report answers (`0` when absent, and
a `raw_code` row passes the REMOTE code straight through — the `exec` verb's own answer).
Before a verb runs, `--help`, `--version` and the declared argument count are applied here. A verb module
registers itself at import time and `register()` refuses a duplicate name.

`Context` is what a handler is handed: the resolved `--project`, the budget, the stream pair and the
`warn()` door — no verb reaches for `sys.stdout`. `AGENTS.md` §4.35; contract — `CLI.md`.
"""
import importlib
from dataclasses import dataclass, field
from typing import Callable, Dict

from . import args as ARGS
from . import envelope as ENV
from . import exit_codes
from . import output as OUT
from .errors import CliError, usage_error


@dataclass(frozen=True)
class Verb:
    """ONE row of the verb table: what it is called, what it does, how it draws and whether it writes."""

    name: str
    summary: str
    handler: Callable = None            # handler(context, arguments) -> dict (the envelope's data)
    render: Callable = None             # render(context, data) -> list[str] | str (the text form)
    mutating: bool = False              # does the verb change state the user owns?
    min_args: int = 0                   # the argument count this verb declares (a check, not a guess)
    max_args: int = 0
    verdict: Callable = None            # verdict(data) -> the process code (0 when the row has none)
    raw_code: bool = False              # the verdict IS the process code (a REMOTE exit status)

    def accepts(self, count) -> bool:
        """Is `count` arguments what this row declares?"""
        return int(self.min_args) <= int(count) <= int(self.max_args)


#: name → Verb. Filled by `register()`; a verb module calls it at import time.
VERBS: Dict[str, Verb] = {}

#: The verbs THIS build answers, in the order the help text lists them (a row without a handler is a
#: verb the line OWES and this build cannot run yet — it is refused by name, never half-run).
_REGISTERED_ORDER = []

#: The built-in verb modules — imported ONCE and LAZILY, so `--help`, `--version` and a usage answer never
#: pay for a project reader, and the entry module still parses argv before any of them loads.
BUILTIN_VERB_MODULES = ("cli.inventory", "cli.connections", "cli.status", "cli.doctor", "cli.exec")

_VERB_MODULES_LOADED = False


def load_verbs() -> None:
    """Import every built-in verb module once (each one registers its row at import time)."""
    global _VERB_MODULES_LOADED
    if _VERB_MODULES_LOADED:
        return
    _VERB_MODULES_LOADED = True      # set FIRST: a verb module asking the table mid-import sees no loop
    for module in BUILTIN_VERB_MODULES:
        importlib.import_module(module)


def register(verb) -> Verb:
    """Add ONE row to the table (refusing a duplicate name and a row without a handler)."""
    if not isinstance(verb, Verb):
        raise TypeError(f"register() takes a Verb, got {type(verb).__name__}")
    name = str(verb.name or "").strip()
    if not name:
        raise ValueError("a verb needs a name")
    if name in VERBS:
        raise ValueError(f"the verb {name!r} is already registered")
    if not callable(verb.handler):
        raise ValueError(f"the verb {name!r} has no handler")
    VERBS[name] = verb
    _REGISTERED_ORDER.append(name)
    return verb


def registered() -> list:
    """The `(name, summary)` pairs the help text lists — the table's own answer."""
    load_verbs()
    return [(name, VERBS[name].summary) for name in sorted(_REGISTERED_ORDER)]


@dataclass
class Context:
    """What a handler is handed: the options that apply to every verb and the two streams."""

    invocation: ARGS.Invocation
    out: object = None
    err: object = None
    notes: list = field(default_factory=list)

    @property
    def json(self) -> bool:
        """Does the run print the envelope?"""
        return bool(self.invocation.json)

    @property
    def project(self) -> str:
        """The RESOLVED `--project` path ("" — the verb's own default)."""
        return self.invocation.project

    @property
    def timeout(self) -> float:
        """The declared budget of this run's network work, in seconds."""
        return float(self.invocation.timeout)

    @property
    def arguments(self) -> tuple:
        """The verb's OWN arguments, verbatim."""
        return self.invocation.arguments

    def warn(self, message) -> None:
        """A diagnostic for stderr — collected, so a verb never writes to a stream itself."""
        self.notes.append(str(message))


def _apply_notes(context) -> None:
    """Every diagnostic a verb left goes to stderr — in BOTH modes (stdout is the report alone)."""
    for note in context.notes:
        OUT.write_line(context.err, note)


def _version_data() -> dict:
    """The facts of `--version`: the application's own name and release (`version.py`)."""
    from version import APP_NAME, APP_VERSION
    return {"name": APP_NAME, "version": APP_VERSION}


def _answer_version(context) -> int:
    """`--version`: one text line, or the envelope of the same two facts — exit 0 either way."""
    data = _version_data()
    envelope = ENV.build("", data=data)
    lines = [f"{data['name']} {data['version']}"]
    OUT.report(envelope, lines, context.json, out=context.out, err=context.err)
    return 0


def _answer_help(context) -> int:
    """`--help`: the usage text (never the envelope — a machine asked for help, not for data)."""
    OUT.write_line(context.out, ARGS.usage_text(registered()))
    return 0


def _answer_code(verb, data) -> int:
    """The process code of a SUCCESSFUL run — the row's verdict, or `0` when it declares none.

    A `raw_code` row (the `exec` verb) answers a REMOTE exit status: any 0..255 is a legal answer there,
    because the remote command's own code is the contract. Every other row answers one of the seven
    declared classes, and anything else — a foreign type, a raising verdict, an undeclared number — is
    the USAGE class: the table declares no home for a bug.
    """
    if not callable(getattr(verb, "verdict", None)):
        return 0
    try:
        code = int(verb.verdict(data))
    except (TypeError, ValueError):
        return exit_codes.EXIT_USAGE
    if getattr(verb, "raw_code", False):
        return code if 0 <= code <= 255 else exit_codes.EXIT_USAGE
    return code if exit_codes.is_declared(code) else exit_codes.EXIT_USAGE


def dispatch(invocation, out=None, err=None) -> int:
    """Run ONE invocation and answer the process's exit code — the surface's only entry into a verb.

    `CliError` is the declared failure (its record goes into the envelope, its sentence to stderr); an
    UNEXPECTED exception is reported as `internal error:` and answered with the usage class, because the
    seven declared codes have no class for a bug and a caller must still see a non-zero answer. A verb's
    `verdict` is asked only after its report is written: the report is the answer either way.
    """
    context = Context(invocation=invocation,
                      out=out if out is not None else OUT.stream("stdout"),
                      err=err if err is not None else OUT.stream("stderr"))
    try:
        if invocation.help:
            return _answer_help(context)
        if invocation.version:
            return _answer_version(context)
        if not invocation.has_verb:
            raise usage_error("no verb given")
        load_verbs()
        verb = VERBS.get(invocation.verb)
        if verb is None:
            raise usage_error(f"unknown verb {invocation.verb!r}")
        if not verb.accepts(len(invocation.arguments)):
            raise usage_error(f"{verb.name} takes {verb.min_args}..{verb.max_args} arguments, "
                              f"got {len(invocation.arguments)}")
        data = verb.handler(context, invocation.arguments) or {}
        rendered = verb.render(context, data) if callable(verb.render) else ()
        lines = rendered if isinstance(rendered, str) else list(rendered or ())
        _apply_notes(context)
        OUT.report(ENV.build(verb.name, data=data), lines, context.json,
                   out=context.out, err=context.err)
        return _answer_code(verb, data)
    except CliError as exc:
        _apply_notes(context)
        OUT.report(ENV.build(invocation.verb, error=exc.record()), (), context.json,
                   out=context.out, err=context.err)
        return exc.code
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 — a bug is reported, never a traceback on stdout
        _apply_notes(context)
        internal = CliError(f"internal error: {type(exc).__name__}: {exc}")
        OUT.report(ENV.build(invocation.verb, error=internal.record()), (), context.json,
                   out=context.out, err=context.err)
        return internal.code
