# -*- coding: utf-8 -*-
"""The ONE RFC-4180 table writer — a report's TEXT form, no Qt and no i18n.

`list_table_text()` turns rows of strings into CSV/TSV text: RFC 4180 quoting (`"` doubled, a field
quoted when it carries the delimiter, a quote or a line break) and `\\r\\n` row endings, so a comma, a
quote or a newline inside a comment round-trips through any spreadsheet and through Python's own `csv`
module. `list_quote_cell()` is the per-cell half and `is_formula_cell()` the guard: a report is DATA,
never a program, so a cell whose FIRST character is `=` `+` `-` `@` TAB or CR is prefixed with the
spreadsheet's own "this is text" mark before the quoting runs — ONE writer, so the inventory, the
connection report and the attention report inherit the rule and the headless surface can print a table.
`ui/sidebar.py` re-exports it for its shipped surface; `AGENTS.md` §4.13, §4.35; mechanism —
`DOCUMENTATION.md` §37, §48.
"""
from typing import List

#: The delimiter of a format id — the two the reports are written in.
LIST_DELIMITERS = {"csv": ",", "tsv": "\t"}

#: RFC 4180: CRLF, and no translation on the way out.
ROW_END = "\r\n"

#: The six characters a spreadsheet READS as the start of a formula. Only the first character decides —
#: a `-` inside a name, a `+` mid-cell and a typed `22` stay as typed.
FORMULA_LEAD_CHARS = ("=", "+", "-", "@", "\t", "\r")


def list_delimiter(fmt: str) -> str:
    """The delimiter of a format id ("csv" / "tsv"); anything else = comma."""
    return LIST_DELIMITERS.get(str(fmt or "").strip().lower(), ",")


def is_formula_cell(value) -> bool:
    """True when a spreadsheet would READ this cell as a formula (the six leading characters)."""
    return str("" if value is None else value)[:1] in FORMULA_LEAD_CHARS


def list_quote_cell(value, delimiter: str = ",") -> str:
    """ONE field of the report: neutralised, then quoted only when it must be (RFC 4180)."""
    text = "" if value is None else str(value)
    if is_formula_cell(text):
        text = "'" + text
    if delimiter and delimiter in text:
        return '"' + text.replace('"', '""') + '"'
    if '"' in text or "\n" in text or "\r" in text:
        return '"' + text.replace('"', '""') + '"'
    return text


def list_table_text(rows, delimiter: str = ",") -> str:
    """The WHOLE table as CSV/TSV text — the header row first, `\\r\\n` endings.

    Pure: a list of rows of strings in, one string out. The header row is the caller's (it comes from
    the live tree, so it follows a language switch), which is what keeps this function free of i18n.
    """
    sep = str(delimiter or ",")
    return "".join(sep.join(list_quote_cell(cell, sep) for cell in row) + ROW_END
                   for row in rows)


def quote_row(cells: List[str], delimiter: str = ",") -> str:
    """ONE row of the table as text (no row ending) — the per-row door of `list_table_text()`."""
    sep = str(delimiter or ",")
    return sep.join(list_quote_cell(cell, sep) for cell in cells)
