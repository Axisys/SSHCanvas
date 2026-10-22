# -*- coding: utf-8 -*-
"""The plan pointers — an ALWAYS-ON gate: the app tree names no plan, and a decision names its OWNER.

§1 the scan of the app tree (`main.py`, `version.py` + `models/`, `graphics/`, `modules/`, `storage/`,
`services/`, `dialogs/`, `ui/`, `i18n/`): zero `ROADMAP` references, zero `(task N)` forms, zero
`tasks N/M` forms.
A DECISION pointer is re-pointed, never deleted — the rule belongs to `AGENTS.md` §4.x, the mechanism
to `DOCUMENTATION.md` §N, the change story to the changelog family: a plan is never an owner (the
SSOT map of `AGENTS.md`). The suite's own labels are NOT scanned — a test may name the plan it guards
(`ROADMAP.md` is read by `tests/test_docs.py`), so the gate reads the CODE alone (`AGENTS.md` §8.2).
Rule — `AGENTS.md` §12.4.
"""
import collections
import os
import re

from _common import bootstrap, check, finish

ROOT, WORK = bootstrap()

APP_TREES = ("main.py", "version.py", "models", "graphics", "modules", "storage", "services",
             "dialogs", "ui", "i18n")
_SKIP_DIRS = {"__pycache__", "_tmp_testdata"}

# The THREE pointer forms the transform removed, plus the decision form (`ROADMAP.md`) whose only
# legal replacement is a named owner. `\bROADMAP\b` catches the bare mention and the file name alike.
ROADMAP_RE = re.compile(r"\bROADMAP\b", re.I)
PAREN_TASK_RE = re.compile(r"\(\s*tasks?\s+\d", re.I)
SLASH_TASK_RE = re.compile(r"\btasks?\s+\d+\s*/\s*\d+", re.I)
DECISION_RE = re.compile(r"ROADMAP\.md", re.I)

OWNER_RULE = ("a decision pointer names its OWNER — the rule in `AGENTS.md` §4.x, the mechanism in "
              "`DOCUMENTATION.md` §N, the change story in the changelog family")

# The patterns' own control: a guard that cannot see a pointer is a guard over nothing.
_SAMPLE_POINTER = "the release (ROADMAP task 4), the row (task 5) and tasks 2/3"
_SAMPLE_DECISION = "the wording of `ROADMAP.md`"


def _sources():
    """Every Python source of the app tree, repository-relative and sorted."""
    out = []
    for tree in APP_TREES:
        path = os.path.join(ROOT, tree)
        if os.path.isfile(path):
            out.append(tree)
            continue
        for base, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
            for name in sorted(names):
                if name.endswith(".py"):
                    out.append(os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/"))
    return sorted(out)


def _scan():
    """(files, lines, rows): the tree read once; `rows` = [(path, line number, the hit line)]."""
    files = _sources()
    lines = 0
    rows = []
    for rel in files:
        with open(os.path.join(ROOT, rel), encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
        for number, line in enumerate(text.splitlines(), 1):
            lines += 1
            if (ROADMAP_RE.search(line) or PAREN_TASK_RE.search(line)
                    or SLASH_TASK_RE.search(line) or DECISION_RE.search(line)):
                rows.append((rel, number, line.strip()))
    return files, lines, rows


_files, _lines, _rows = _scan()
_by_file = collections.Counter(row[0] for row in _rows)
_kind = {
    "`ROADMAP`": [r for r in _rows if ROADMAP_RE.search(r[2])],
    "`(task N)`": [r for r in _rows if PAREN_TASK_RE.search(r[2])],
    "`tasks N/M`": [r for r in _rows if SLASH_TASK_RE.search(r[2])],
    "`ROADMAP.md`": [r for r in _rows if DECISION_RE.search(r[2])],
}


def _show(label, rows):
    """The detail of one family: the first three sites, then the count."""
    sites = ", ".join(f"{path}:{number}" for path, number, _ in rows[:3]) or "none"
    return f"{label}={len(rows)} — {sites}"


check("§1 the scan really read the app tree, and its patterns recognise a plan pointer "
      "(a guard over nothing is useless)",
      len(_files) > 100 and _lines > 50_000
      and bool(ROADMAP_RE.search(_SAMPLE_POINTER) and PAREN_TASK_RE.search(_SAMPLE_POINTER)
               and SLASH_TASK_RE.search(_SAMPLE_POINTER) and DECISION_RE.search(_SAMPLE_DECISION)),
      f"files={len(_files)} lines={_lines}")
check("§2 the app tree names no plan — zero `ROADMAP` references "
      "(a version tag is a bare tag; a task number is never cited)",
      not _kind["`ROADMAP`"], _show("hits", _kind["`ROADMAP`"]))
check("§3 no plan task number sits in a parenthetical — zero `(task N)` / `(tasks N/M)` forms",
      not _kind["`(task N)`"], _show("hits", _kind["`(task N)`"]))
check("§4 no plan task list survives — zero `tasks N/M` forms",
      not _kind["`tasks N/M`"], _show("hits", _kind["`tasks N/M`"]))
check("§5 a DECISION pointer names its owner, never the plan: " + OWNER_RULE,
      not _kind["`ROADMAP.md`"], _show("hits", _kind["`ROADMAP.md`"]) + f" — {OWNER_RULE}")
check("§6 the report counts the hits per file, so a new habit is visible at once",
      sum(_by_file.values()) == len(_rows)
      and set(_by_file) == {row[0] for row in _rows},
      f"{len(_by_file)} file(s), {len(_rows)} hit(s)")
for _rel, _count in sorted(_by_file.items()):
    print(f"    {_count:3}  {_rel}")
for _row in _rows:
    print(f"    {_row[0]}:{_row[1]}: {_row[2][:100]}")

finish()
