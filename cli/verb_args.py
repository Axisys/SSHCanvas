# -*- coding: utf-8 -*-
"""The argument grammar of ONE verb — the flags and node tokens its row accepts, read from its tail.

The global parse stops at the verb (`cli/args.py`), so a verb's arguments arrive verbatim and THIS is the
ONE reader of that tail. A TABLE verb declares its flags (`ARGUMENT_TABLE`: `--tag` repeats, `--format`
takes its LAST value) and refuses a bare token; a POSITIONAL verb (`POSITIONAL_VERBS`: `status`, `doctor`)
declares node tokens and refuses a flag-shaped one; an EXEC verb (`EXEC_VERBS`: `exec`) declares the five
flags of the command policy beside a node and a VERBATIM command; a SUBCOMMAND verb (`SUBCOMMANDS`:
`hostkey`) declares the ONE token its tail names. An undeclared token is a USAGE error in every shape —
the strictness the global parse already applies. The format ids come from the shipped writer
(`storage/table_text.LIST_DELIMITERS`), never a second list. `AGENTS.md` §4.35; `CLI.md` §2, §3.1, §3.5,
§3.6.
"""
from dataclasses import dataclass

from storage.table_text import LIST_DELIMITERS

from .args import late_option_hint
from .errors import usage_error

TAG_OPTION = "--tag"
FORMAT_OPTION = "--format"
IDENTITY_OPTION = "--identity"
HOST_KEY_OPTION = "--host-key"
ACCEPT_NEW_OPTION = "--accept-new"
ALLOW_DESTRUCTIVE_OPTION = "--allow-destructive"
DRY_RUN_OPTION = "--dry-run"

#: The formats a table report is written in — the writer's OWN ids, in its own order.
TABLE_FORMATS = tuple(LIST_DELIMITERS)

#: The table a report is written in when `--format` is not given (the GUI's default file too).
DEFAULT_FORMAT = "csv"

#: The flood stop a verb row declares in `max_args`: the FLAGS are this module's table, and this is the
#: count a line may not cross before the row refuses it (a repeated `--tag` is the reason it is not 2).
MAX_ARGUMENTS = 32

#: verb name → the flags it accepts. A verb without a row here takes no flag at all.
ARGUMENT_TABLE = {
    "inventory": (TAG_OPTION, FORMAT_OPTION),
    "connections": (FORMAT_OPTION,),
}

#: The verbs that take NODE arguments (bare tokens, never a flag): their selection is positional, and an
#: argument that starts with `-` is a USAGE error rather than a node nobody could name.
POSITIONAL_VERBS = ("status", "doctor")

#: The flood stop a positional verb declares in `max_args`: a node SELECTION is bounded, and the
#: no-argument form names the whole map without a list.
MAX_NODES = 256

#: The ONE verb that runs a command: `<node> "<command>"` and the FIVE policy flags of `CLI.md` §3.5.
EXEC_VERBS = ("exec",)

#: The exec flags that carry a VALUE (`--identity PATH`, `--host-key FINGERPRINT`); a repeated one keeps
#: its LAST value, the rule the global option table already follows.
EXEC_VALUE_FLAGS = (IDENTITY_OPTION, HOST_KEY_OPTION)

#: The exec flags that carry NONE — a `=value` on one of them is a USAGE error, never a silent pass.
EXEC_SWITCHES = (ACCEPT_NEW_OPTION, ALLOW_DESTRUCTIVE_OPTION, DRY_RUN_OPTION)

#: verb name → the SUBCOMMAND tokens its tail may name. A subcommand verb takes exactly ONE token and no
#: flag of its own: the flags of a family belong to the subcommand that would use them, and `verify`
#: declares none (`CLI.md` §3.6).
SUBCOMMANDS = {"hostkey": ("verify",)}


@dataclass(frozen=True)
class ExecRequest:
    """What one `exec` tail asked for: the node, the command VERBATIM and the five policy flags."""

    node: str = ""
    command: str = ""
    identity: str = ""
    host_key: str = ""
    accept_new: bool = False
    allow_destructive: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class VerbArguments:
    """What one verb's tail asked for: the table format and the tag filter (every tag must match)."""

    format: str = DEFAULT_FORMAT
    tags: tuple = ()

    def matches(self, tags) -> bool:
        """Does a server's tag list carry EVERY tag this run asked for?"""
        present = [str(tag).strip() for tag in (tags or ())]
        return all(tag in present for tag in self.tags)


def resolve_format(text) -> str:
    """The table format id a value names — an id the writer does not declare is a USAGE error."""
    wanted = str(text or "").strip().lower()
    if wanted not in TABLE_FORMATS:
        raise usage_error(f"{FORMAT_OPTION} takes {' or '.join(TABLE_FORMATS)}, got {text!r}")
    return wanted


def read(verb, arguments) -> VerbArguments:
    """Read ONE verb's arguments against its declared table — a token it does not declare is USAGE."""
    name_of_verb = str(verb or "")
    allowed = ARGUMENT_TABLE.get(name_of_verb, ())
    tokens = [str(token) for token in (arguments or ())]
    fmt, tags = DEFAULT_FORMAT, []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        name, separator, value = token.partition("=")
        if name not in allowed:
            if name.startswith("-"):
                raise usage_error(f"{name_of_verb} does not take {name!r}", late_option_hint(name))
            raise usage_error(f"{name_of_verb} takes no bare argument, got {token!r}")
        if not separator:
            if index >= len(tokens):
                raise usage_error(f"{name} needs a value")
            value = tokens[index]
            index += 1
        if name == TAG_OPTION:
            tag = str(value).strip()
            if not tag:
                raise usage_error(f"{name} takes a tag name")
            tags.append(tag)
        else:
            fmt = resolve_format(value)
    return VerbArguments(format=fmt, tags=tuple(tags))


def read_nodes(verb, arguments) -> tuple:
    """The NODE tokens of a positional verb — a flag-shaped or empty token is a USAGE error."""
    name = str(verb or "")
    if name not in POSITIONAL_VERBS:
        raise usage_error(f"{name} takes no node arguments")
    tokens = []
    for token in (arguments or ()):
        text = str(token or "").strip()
        if not text or text.startswith("-"):
            raise usage_error(f"{name} takes node ids or aliases, got {str(token)!r}")
        tokens.append(text)
    return tuple(tokens)


def read_subcommand(verb, arguments) -> str:
    """The ONE subcommand token a SUBCOMMAND verb's tail names — anything else is a USAGE error (PURE).

    A subcommand verb takes its token and nothing else: a second token, a flag-shaped one or a name the
    family does not declare is refused BEFORE any work (the grammar's own strictness), and the refusal
    names the declared set, which is what a caller with a typo needs.
    """
    name = str(verb or "")
    declared = SUBCOMMANDS.get(name)
    if not declared:
        raise usage_error(f"{name} takes no subcommand")
    tokens = [str(token or "").strip() for token in (arguments or ())]
    if len(tokens) != 1:
        raise usage_error(f"{name} takes 1 subcommand ({' | '.join(declared)}), "
                          f"got {len(tokens)} arguments")
    if tokens[0] not in declared:
        raise usage_error(f"{name} does not take {tokens[0]!r} — it takes {' | '.join(declared)}",
                          late_option_hint(tokens[0]))
    return tokens[0]


def _exec_value(name, value, next_token) -> str:
    """The value of ONE exec flag — a missing or empty one is a USAGE error naming the flag."""
    text = str(value if value is not None else (next_token or "")).strip()
    if not text:
        raise usage_error(f"{name} needs a value")
    return text


def read_exec(arguments) -> ExecRequest:
    """Read the `exec` tail: the node, the command VERBATIM and the five policy flags.

    The global parse stopped at the verb, so the tail is read HERE — and a flag is read WHEREVER it
    stands among the tokens, which is what lets `CLI.md` §3.5's `<node> "<cmd>" [flags…]` order keep the
    command in front. The FIRST bare token is the node and the REST are joined with ONE space: an
    unquoted `exec web-1 df -h` means what it looks like, while a QUOTED command stays the single token
    the shell handed over (it is never re-split and never interpreted here).
    """
    flags = {"identity": "", "host_key": "", "accept_new": False, "allow_destructive": False,
             "dry_run": False}
    bare = []
    tokens = [str(token if token is not None else "") for token in (arguments or ())]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        name, separator, value = token.partition("=")
        if name in EXEC_VALUE_FLAGS:
            taken = _exec_value(name, value if separator else None,
                                tokens[index] if index < len(tokens) else None)
            if not separator:
                index += 1
            flags["identity" if name == IDENTITY_OPTION else "host_key"] = taken
            continue
        if name in EXEC_SWITCHES:
            if separator:
                raise usage_error(f"{name} takes no value")
            flags[{"--accept-new": "accept_new", "--allow-destructive": "allow_destructive",
                   "--dry-run": "dry_run"}[name]] = True
            continue
        if token.startswith("-") and token != "-":
            raise usage_error(f"exec does not take {name!r}",
                              late_option_hint(name)
                              or 'quote the whole command: exec <node> "<command>"')
        bare.append(token)
    if not bare:
        raise usage_error("exec needs a node and a command")
    command = " ".join(part for part in bare[1:]).strip()
    if not command:
        raise usage_error("exec needs a command")
    return ExecRequest(node=bare[0].strip(), command=command, **flags)
