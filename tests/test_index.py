# -*- coding: utf-8 -*-
"""The generated suite map — `tests/INDEX.md` is fresh and every test file carries its docstring.

This is the ONE guard the documentation regime does NOT own: `INDEX.md` is GENERATED from the code
(`python tests/_gen_index.py`), it ships in the repository, and it goes stale the moment a test file
is added or renamed — a rule about the suite, not about a document. It therefore runs on EVERY suite
run, while the audit of the hand-written documents lives in `tests/test_docs.py` (`run_all.py --docs`).
"""
import os
import sys

from _common import bootstrap, check, finish

ROOT, WORK = bootstrap()  # HOME isolation + offscreen + sys.path (BEFORE any app import)

sys.path.insert(0, os.path.join(ROOT, "tests"))   # _gen_index imports run_all from its own folder
import _gen_index as GI  # noqa: E402
from run_all import collect_files  # noqa: E402

_names = [n for n in collect_files() if n.startswith("test_")]
_block, _problems = GI.build_block(_names)
check("every test file carries a module docstring (the INDEX table needs it)",
      not _problems, _problems[:3])
check("tests/INDEX.md is fresh (update: python tests/_gen_index.py)",
      GI.extract_block(open(GI.INDEX_PATH, encoding="utf-8").read()) == _block,
      f"the «Suite files» block differs ({len(_names)} files)")
check("the suite map lists THIS guard (a generated map that forgot its own guard is stale)",
      "test_index" in _block)

finish()
