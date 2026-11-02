# -*- coding: utf-8 -*-
"""The project MEMORY — the config keys of the recent list and of the file the window was CLOSED on.

Three keys are CONFIG data, never project data: `recent_projects` (newest first, capped), the auto-open
option `ui_reopen_last_project` and `last_project_path`. This module declares them and their two PURE
readers, so the window, the standalone terminal and the headless surface ask ONE home; the WRITERS stay
with the lifecycle (`ui/main_window_project_io.py`). A missing key, a foreign type and an unreadable store
are the DECLARED default ("" / False), never an exception — a hint is not a promise, and the caller
checks that the file is still there. `AGENTS.md` §4.1, §4.35; mechanism — `DOCUMENTATION.md` §15.
"""
try:  # the ONE config store (`storage/app_config.py`) — no i18n, no Qt
    from .app_config import load_config
except ImportError:  # flat launch from the project root
    from app_config import load_config  # type: ignore

#: The MRU list: newest first, deduplicated by the normalized absolute path, missing files pruned on read.
RECENT_PROJECTS_KEY = "recent_projects"
RECENT_PROJECTS_MAX = 10

#: The AUTO-OPEN option (a config boolean, OFF by default) and the path the window was closed on ("" for
#: a nameless project). They are the MRU's siblings: the option decides whether the GUI reopens the file,
#: the path answers "which project is the last one" to any other reader.
REOPEN_LAST_PROJECT_KEY = "ui_reopen_last_project"
LAST_PROJECT_PATH_KEY = "last_project_path"


def reopen_last_project_enabled(cfg=None) -> bool:
    """Is the auto-open option ON? — the PURE reader of `ui_reopen_last_project`, OFF by default.

    CONFIG and never the project (the `guard_commands` rule): a missing key, a foreign type and an
    unreadable store all answer False, so only a real JSON `true` asks for the restore.
    """
    if cfg is None:
        try:
            cfg = load_config()
        except Exception:  # noqa: BLE001 — an unreadable store is the declared default
            return False
    try:
        return cfg.get(REOPEN_LAST_PROJECT_KEY) is True
    except Exception:  # noqa: BLE001 — a foreign config object is "off"
        return False


def last_project_path(cfg=None) -> str:
    """The path the application was CLOSED on ("" — nothing recorded, or a nameless project). PURE.

    A HINT, not a promise: the caller checks that the file is still there, so a project moved or
    deleted between two runs is a quiet "nothing to reopen" instead of a dialog at startup.
    """
    if cfg is None:
        try:
            cfg = load_config()
        except Exception:  # noqa: BLE001 — an unreadable store restores nothing
            return ""
    try:
        value = cfg.get(LAST_PROJECT_PATH_KEY)
    except Exception:  # noqa: BLE001 — a foreign config object restores nothing
        return ""
    return value.strip() if isinstance(value, str) else ""
