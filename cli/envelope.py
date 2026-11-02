# -*- coding: utf-8 -*-
"""The `--json` envelope — ONE stable machine contract in front of every verb.

The envelope has five keys and no others: `schema` (ITS OWN version, independent of the project JSON
format), `verb` ("" when the run answered an option instead of a verb), `ok`, `data` (a verb's payload,
`null` on a failure) and `error` (`null`, or `{code, kind, message, hint}` — the table of
`cli/exit_codes.py`). A `--json` run prints exactly ONE such document on stdout and keeps the diagnostics
on stderr; a verb may ADD a field, never remove or rename one. `AGENTS.md` §4.35; contract — `CLI.md`.
"""
import json

#: The envelope's OWN schema version (the project format has its own, `VERSION_FORMAT`).
SCHEMA_VERSION = 1

#: The five keys, in the order they are written — a reader may rely on the names, never on the order.
ENVELOPE_KEYS = ("schema", "verb", "ok", "data", "error")


def build(verb, data=None, error=None) -> dict:
    """The envelope of ONE run: `error` None = success, an error record (a `dict`) = failure."""
    return {"schema": SCHEMA_VERSION,
            "verb": str(verb or ""),
            "ok": error is None,
            "data": data if error is None else None,
            "error": None if error is None else dict(error)}


def dumps(envelope, indent=2) -> str:
    """The envelope as JSON text (UTF-8, one document); a foreign payload degrades to its `str`."""
    try:
        return json.dumps(envelope, ensure_ascii=False, indent=indent, sort_keys=False)
    except (TypeError, ValueError):
        safe = dict(envelope)
        safe["data"] = str(safe.get("data"))
        return json.dumps(safe, ensure_ascii=False, indent=indent)
