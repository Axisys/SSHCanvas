# -*- coding: utf-8 -*-
"""The user configuration store (`~/.sshmap/config.json`) — the ONE reader and the ONE writer.

`load_config()` answers the JSON object and NOTHING else: a missing file, a broken file and a root that is
not an object all answer `{}`, because the declared default of every key is its reader's. `save_config()`
merges a partial update through `storage/atomic.write_json_atomic()`, so two writers cannot publish each
other's stale snapshot. The path is declared HERE, so the window, the terminal and the headless surface
read the same file; this module imports the standard library and `storage/atomic` only, which is what lets
a process with no QApplication answer it. `AGENTS.md` §4.4.4, §4.35; mechanism — `DOCUMENTATION.md` §71.
"""
import json
import os

try:  # the ONE atomic-write mechanism (`AGENTS.md` §4.4, `DOCUMENTATION.md` §71)
    from . import atomic
except ImportError:  # flat launch from the project root
    from storage import atomic

#: The config directory and its ONE file — the user's own data, never the package's.
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".sshmap")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def ensure_config_dir() -> bool:
    """Create `~/.sshmap` when it is not there (a writer's precondition; False on an I/O failure)."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        return True
    except OSError:
        return False


def load_config() -> dict:
    """The user config as a dict — `{}` for a missing, unreadable or non-object file. Never raises.

    "Unreadable" includes a file that is not UTF-8: `UnicodeDecodeError` is a `ValueError`, so an
    editor that saved the file in another encoding degrades to the defaults instead of escaping every
    reader of this store.
    """
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, UnicodeDecodeError, IOError, OSError):
        return {}
    return {}


def save_config(partial_update: dict) -> bool:
    """Atomically merge a partial update into `config.json` — False on any I/O failure.

    Existing keys are preserved: only the keys of `partial_update` are overwritten, and the WHOLE
    read-merge-write runs under the lock of the atomic writer, so a concurrent writer's keys survive.
    """
    if not ensure_config_dir():
        return False
    return atomic.write_json_atomic(CONFIG_FILE, dict(partial_update or {}), merge=True,
                                    reader=load_config)
