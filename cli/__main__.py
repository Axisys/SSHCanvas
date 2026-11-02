# -*- coding: utf-8 -*-
"""`python -m cli` — the headless surface without installing it (the console scripts are the shipped door).

The body is deliberately ONE call: the entry point is `cli.main:main`, so the argv parse, the dispatch and
the exit code stay owned by that module (`CLI.md` §1). The `__name__` guard keeps this file IMPORTABLE for
the Qt-free gate (`tests/test_cli.py` §2 imports every module of the package) while `python -m cli` still
runs it.
"""
import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
