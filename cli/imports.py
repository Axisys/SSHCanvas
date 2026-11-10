# -*- coding: utf-8 -*-
"""`import` — one import SOURCE previewed as draft rows, through the pure row model both surfaces share.

The sources are `ssh-config`, `drawio` and `profiles` (`services/import_drafts.SOURCES`); each row is a
`Draft` with a verdict (`add` / `skip`) and a reason code, so a script can ask what an import WOULD bring
before a human applies it in the GUI. READ-ONLY by contract: no project file, no config, no keyring and no
profile store is written — the GUI's preview applies the same rows (`CLI.md` §3.7, §7).
`AGENTS.md` §4.35, §4.36; contract — `CLI.md` §3.7.
"""
from services import import_drafts

from . import project as PROJECT_SOURCE
from . import report, verb_args
from .dispatch import Verb, register
from .errors import CliError, not_found, usage_error

NAME = "import"
SUMMARY = "preview an import source: ssh-config, drawio or profiles (read-only)"

#: The `data` keys of the report, in order — the table verbs' pinned shape over the draft rows.
DATA_KEYS = ("source", "path", "count", "columns", "rows")


def _project_keys(context):
    """The `(host, port, user)` keys the project already carries — `None` when there is no project.

    The preview compares against the map when one is open and says nothing when none is: an import of a
    SOURCE never fails because this run has no project (`CLI.md` §3.7).
    """
    try:
        path = PROJECT_SOURCE.resolve_path(context.project)
        servers = PROJECT_SOURCE.read_servers(path)
    except CliError:
        return None
    return {(str(getattr(server, "host", "")).strip().lower(),
             int(getattr(server, "ssh_port", 22) or 22),
             str(getattr(server, "user", "")).strip().lower()) for server in servers}


def _store_names():
    """The profile NAMES the store already holds — the merge key of `profiles` (never an id)."""
    from models.profile import load_profiles
    return {str(profile.name or "").strip().lower() for profile in load_profiles()}


def handle(context, arguments):
    """The verb's FACTS — the source's draft rows as the pinned table payload."""
    options = verb_args.read_import(NAME, arguments, import_drafts.SOURCES)
    try:
        drafts = import_drafts.collect(options.source, options.path,
                                       project_keys=_project_keys(context),
                                       store_names=_store_names())
    except import_drafts.SourceError as exc:
        raise _source_failure(exc)
    if not drafts.count():
        context.warn(f"{options.source} holds no draft row ({drafts.path})")
    return drafts.payload()


def _source_failure(exc) -> CliError:
    """The exit class of a source that cannot be read: a missing file is `5`, a broken one `1`."""
    if exc.code == import_drafts.ERROR_MISSING:
        return not_found(exc.detail or "the source file is not there",
                         "pass the file path after the source")
    return usage_error(exc.detail or "the source file cannot be read", "check the file")


def render(context, payload):
    """The table itself — the SAME cells as CSV/TSV, written by the shipped writer."""
    options = verb_args.read_import(NAME, context.arguments, import_drafts.SOURCES)
    return report.text(payload, options.format)


register(Verb(NAME, SUMMARY, handler=handle, render=render,
              min_args=1, max_args=verb_args.MAX_ARGUMENTS))
