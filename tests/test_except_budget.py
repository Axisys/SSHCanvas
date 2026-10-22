# -*- coding: utf-8 -*-
"""The swallowed-error gate — an ALWAYS-ON ratchet: a `pass` that can hide a logic error says why it does.
§1 the measurement of `tests/_except_budget.py`: the scan read the tree, every handler outside the Qt
teardown family carries `# noqa: BLE001 — <reason>`, the reason is non-empty, the family is at or under
its pins, the per-file weights are printed and add up, and the teardown family is not counted.
Rule and vocabulary — `AGENTS.md` §12.2; the family and the pins are `_except_budget.py`'s own constants.
"""
import _except_budget as EB
from _common import bootstrap, check, finish

ROOT, WORK = bootstrap()

EB.report(check, root=ROOT, prefix="§1", enforce=True)
finish()
