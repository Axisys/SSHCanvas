# -*- coding: utf-8 -*-
"""The report of a table verb — the column ids, the rows and the TWO shapes of one run.

`data()` is the `--json` payload the envelope carries (`project`, `count`, `columns`, `rows`) and `text()`
is the SAME cells through the shipped RFC-4180 writer (`storage/table_text.list_table_text()`), so the
machine document and the printed table cannot disagree: a renderer draws, it never computes. The header row
is the column IDS — the CLI speaks English and adds no translation key, and an id never moves with a
language, which is what keeps `--json` stable. The rows arrive as strings, built ONCE by the verb.
`AGENTS.md` §4.35; contract — `CLI.md` §3.0, §3.1, §4.
"""
from storage.table_text import list_delimiter, list_table_text

from .verb_args import DEFAULT_FORMAT

#: The keys of a table verb's `data` payload, in order — the pinned machine contract.
DATA_KEYS = ("project", "count", "columns", "rows")


def data(project, columns, rows) -> dict:
    """The `--json` payload of a table report — the cells as strings, the column ids as the vocabulary."""
    ordered = [list(row) for row in (rows or ())]
    return {"project": str(project or ""),
            "count": len(ordered),
            "columns": [str(column) for column in (columns or ())],
            "rows": ordered}


def text(payload, fmt=DEFAULT_FORMAT) -> str:
    """The SAME cells as CSV/TSV text — the header row first, the shipped writer's own row endings."""
    payload = payload if isinstance(payload, dict) else {}
    columns = [str(column) for column in (payload.get("columns") or ())]
    if not columns:
        return ""
    rows = [list(row) for row in (payload.get("rows") or ())]
    return list_table_text([columns] + rows, list_delimiter(fmt))
