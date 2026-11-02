# -*- coding: utf-8 -*-
"""`inventory` — one row per server of the project, through the shipped reader and the report schema.

The rows are `storage/export_inventory`'s cells (the LIST mode's own columns), narrowed by `--tag` (every
named tag must match), and `cli/report.py` writes the SAME cells as the envelope's `data` and as the
CSV/TSV table. READ-ONLY: the project file is opened, never written, and no probe touches the network. A
project with no server answers an EMPTY table (its header row, `count: 0`) and exit `0`.
`AGENTS.md` §4.13, §4.35; contract — `CLI.md` §3.1.
"""
from storage.export_inventory import inventory_cell_values, inventory_column_ids

from . import project as PROJECT_SOURCE
from . import report, verb_args
from .dispatch import Verb, register

NAME = "inventory"
SUMMARY = "one row per server (--tag TAG, --format csv|tsv)"


def handle(context, arguments):
    """The verb's FACTS — the project, the row count and the rows a tag filter narrowed."""
    options = verb_args.read(NAME, arguments)
    path = PROJECT_SOURCE.resolve_path(context.project)
    servers = PROJECT_SOURCE.read_servers(path)
    if options.tags:
        servers = [data for data in servers if options.matches(getattr(data, "tags", None))]
    return report.data(path, inventory_column_ids(),
                       [inventory_cell_values(data) for data in servers])


def render(context, payload):
    """The table itself — the SAME cells as CSV/TSV, written by the shipped writer."""
    return report.text(payload, verb_args.read(NAME, context.arguments).format)


register(Verb(NAME, SUMMARY, handler=handle, render=render,
              min_args=0, max_args=verb_args.MAX_ARGUMENTS))
