# -*- coding: utf-8 -*-
"""The module-size gate — an ALWAYS-ON ratchet: no pinned module grows, the band cannot be crossed silently.
§1 the measurement of the tree and the six checks of `tests/_size_budget.py`: an over-pin, an unpinned
module at or over the band, a pin left under the band and a pin past the slack all fail; a pin that
names no module fails too.
Rule — `AGENTS.md` §12.5; the pins and the band are `tests/_size_budget.py`'s own constants.
"""
import _size_budget as SB
from _common import bootstrap, check, finish

ROOT, WORK = bootstrap()

SB.report(check, root=ROOT, prefix="§1", enforce=True)
finish()
