# -*- coding: utf-8 -*-
"""The walked-tree bounds — ONE declaration of how large a recursive operation may get, no Qt.

`MAX_TREE_ENTRIES` / `MAX_TREE_DEPTH` are the ceiling of every bounded walk in the application: the
Files pane's copy, move, download and extract (`modules/sftp_worker.py`, `modules/local_fs_worker.py`),
the archive listing and extract (`modules/archive_view.py`, `modules/archive_extract.py`) and the
content search (`modules/sftp_search.py`). The walk is depth-first and every entry costs a round trip,
so a tree over a bound is REFUSED with a sentence before anything is transferred rather than half-copied.

The bounds live here, and not in the worker, because they are a POLICY a PURE layer must be able to read
(`AGENTS.md` §4.3.6, §4.35; mechanism — `DOCUMENTATION.md` §14f).
"""

#: The entries ONE walk may carry (a directory and a file count alike).
MAX_TREE_ENTRIES = 5000

#: The nesting ONE walk may reach (the root's level is 0).
MAX_TREE_DEPTH = 32
