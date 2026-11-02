# -*- coding: utf-8 -*-
"""`connections` — one row per declared link, over the project's own `connections` array.

The rows are `storage/export_connections`' cells: each link's id references are resolved against the
SERVERS OF THE SAME FILE, the direction is the shipped `source → target` text and the flag column carries
the machine spelling (`true` / `false`). `cli/report.py` writes the same cells as the envelope's `data` and
as the CSV/TSV table. READ-ONLY, and a project with no link answers an EMPTY table (its header row,
`count: 0`) and exit `0` — nothing is broken. `AGENTS.md` §4.35; contract — `CLI.md` §3.2.
"""
from storage.export_connections import (connection_column_ids, connection_records_from_project,
                                        connection_rows_from_records)

from . import project as PROJECT_SOURCE
from . import report, verb_args
from .dispatch import Verb, register

NAME = "connections"
SUMMARY = "one row per declared link (--format csv|tsv)"


def handle(context, arguments):
    """The verb's FACTS — the project, the row count and one row per declared link."""
    verb_args.read(NAME, arguments)
    path = PROJECT_SOURCE.resolve_path(context.project)
    records = connection_records_from_project(PROJECT_SOURCE.load(path))
    return report.data(path, connection_column_ids(), connection_rows_from_records(records))


def render(context, payload):
    """The table itself — the SAME cells as CSV/TSV, written by the shipped writer."""
    return report.text(payload, verb_args.read(NAME, context.arguments).format)


register(Verb(NAME, SUMMARY, handler=handle, render=render,
              min_args=0, max_args=verb_args.MAX_ARGUMENTS))
