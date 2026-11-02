# -*- coding: utf-8 -*-
"""The project a verb reads — the resolved path, the parsed document and the read-only views of it.

ONE door for every verb: an explicit `--project` wins, otherwise the last project the GUI opened
(`storage/project_recent.last_project_path()`), and a run with neither is the `not_found` class. A file that
is not there is `not_found` too; a file that does not PARSE is a USAGE failure, because a report over a
broken file must never read as an empty one. `select_servers()` is the ONE node selection (id first, an
alias second, an unknown token a `5` before any probe). Nothing here writes: `storage/project.load_project()`
is the shipped reader and the views on top of it are pure. `AGENTS.md` §4.35; contract — `CLI.md` §2, §8.
"""
import json
import os

from storage.project import load_project, servers_from_project
from storage.project_recent import last_project_path

from .args import OPTION_PROJECT
from .errors import not_found, usage_error


def resolve_path(explicit="") -> str:
    """The project path this run reads — the option, else the last one the GUI opened.

    A path that is not there answers `not_found` (the message names the path, the hint names the door),
    so a script sees the difference between "nothing was ever opened" and "the file moved".
    """
    wanted = str(explicit or "").strip()
    if wanted:
        return _existing(wanted)
    remembered = last_project_path()
    if not remembered:
        raise not_found("no project given and no project has been opened yet",
                        f"pass {OPTION_PROJECT} PATH")
    return _existing(remembered)


def _existing(path) -> str:
    """`path` when it is a file, else the `not_found` refusal that names it."""
    try:
        present = os.path.isfile(path)
    except (TypeError, ValueError):
        present = False
    if not present:
        raise not_found(f"project file not found: {path}", f"pass {OPTION_PROJECT} PATH")
    return path


def load(path) -> dict:
    """The parsed project document of `path` — an unreadable or broken file is a USAGE failure."""
    try:
        return load_project(path)
    except FileNotFoundError:
        raise not_found(f"project file not found: {path}", f"pass {OPTION_PROJECT} PATH")
    except json.JSONDecodeError as exc:
        raise usage_error(f"the project file is not valid JSON: {exc}", "check the file")
    except (OSError, ValueError) as exc:
        raise usage_error(f"the project file cannot be read: {exc}", "check the file")


def read_servers(path) -> list:
    """The `ServerData` list of a project file — the shipped reader over the ONE parsed document."""
    return servers_from_project(load(path))


def select_servers(servers, tokens=()) -> list:
    """The nodes a run NAMES — every server for no token, else the id first and an alias second.

    READ-ONLY and order-preserving: a token that matches an id selects that server whatever its alias
    says, an alias selects every server that carries it, and a node selected twice is kept ONCE. A token
    that matches nothing answers `not_found` (5) BEFORE any probe, so a typo costs no network work.
    """
    nodes = list(servers or ())
    wanted = [str(token or "").strip() for token in (tokens or ())]
    if not wanted:
        return nodes
    selected, seen = [], set()
    for token in wanted:
        matches = [node for node in nodes if str(getattr(node, "id", "")) == token]
        if not matches:
            matches = [node for node in nodes if str(getattr(node, "alias", "")) == token]
        if not matches:
            raise not_found(f"node not found: {token}", "pass an id or an alias (see `inventory`)")
        for node in matches:
            key = str(getattr(node, "id", "")) or id(node)
            if key not in seen:
                selected.append(node)
                seen.add(key)
    return selected
