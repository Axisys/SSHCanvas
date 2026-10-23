# -*- coding: utf-8 -*-
"""The swallowed-error budget: the FAMILY rule, the marker reader and the MEASUREMENT behind
`tests/test_except_budget.py`.

A handler whose body is exactly `pass` swallows its error. The ONE exempt family is the Qt teardown — a
handler that declares `RuntimeError` / `AttributeError` only, where a destroyed C++ object is the NORMAL
case; every other `pass` carries `# noqa: BLE001 — <reason>` or is FIXED into a `log.debug` /
`log.warning` line, so the next reader knows the silence was a DECISION.

The counters are a RATCHET — `TARGET_PIN` (the family, marked and unmarked) and `UNMARKED_PIN` go DOWN
only. Measure with `python tests/_except_budget.py` and paste the block it prints. Rule and vocabulary —
`AGENTS.md` §12.2.
"""
import ast
import os
import re

# ── The family (the rule AGENTS.md §12.2 states) ───────────────────────────────────────────────
#: A `pass`-only handler declaring ONLY these is the teardown family: a destroyed C++ object is normal.
TEARDOWN_EXCEPTIONS = ("RuntimeError", "AttributeError")

# ── The marker (the ONE vocabulary of a declared silence) ──────────────────────────────────────
#: The marker's fixed head; the reason follows it (an em dash or a colon, then the words).
MARKER = "noqa: BLE001"

#: The canonical reasons of the ledger. A site may add its own clause after the reason it chooses.
REASONS = (
    "teardown of a dead object",
    "optional import",
    "best effort (declared)",
    "the caller owns the fallback",
    "the OS refuses a path we only probe",
)

_MARKER_RE = re.compile(r"noqa:\s*BLE001\b\s*(.*)$")
_REASON_RE = re.compile(r"^(?:—|–|--|-|:)\s*(\S.*)$")

# ── The pins (a ratchet: measure and paste, never raise by hand) ──────────────────────────────
TARGET_PIN = 315       # pass-only handlers OUTSIDE the teardown family — marked or not
UNMARKED_PIN = 0       # of them, the ones that carry no marker — the goal state
REASONLESS_PIN = 0     # markers with an EMPTY reason — the goal state

_SKIP_DIRS = {"third_party", "tests", "examples", "docs", "__pycache__", ".git", "build", "dist",
              "test-results"}


def default_root():
    """The repository root (this file lives in `<root>/tests/`)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iter_sources(root):
    """Every Python source of the APPLICATION tree (the suite, the fork and the examples excluded)."""
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith("_tmp_testdata")]
        for name in sorted(files):
            if name.endswith(".py"):
                out.append(os.path.join(base, name))
    return sorted(out)


def pass_only_handlers(tree):
    """Every `except` handler of ONE parse whose body is exactly `pass` (AST order)."""
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler)
            and len(node.body) == 1 and isinstance(node.body[0], ast.Pass)]


def declared_names(handler):
    """The exception names a handler declares — a frozenset; None for a bare `except:`."""
    return _names_of(handler.type)


def _names_of(node):
    """The declared names of ONE exception expression (`Name`, `Attribute`, a tuple of them)."""
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return frozenset([node.id])
    if isinstance(node, ast.Attribute):
        return frozenset([node.attr])
    if isinstance(node, ast.Tuple):
        names = set()
        for element in node.elts:
            names |= set(_names_of(element) or ())
        return frozenset(names)
    return frozenset([ast.dump(node)])


def is_teardown_family(handler) -> bool:
    """The predicate: declares RuntimeError / AttributeError and NOTHING else (bare `except:` is not)."""
    names = declared_names(handler)
    if not names:
        return False
    return names <= frozenset(TEARDOWN_EXCEPTIONS)


def handler_marker(lines, handler):
    """The marker of ONE handler: `(present, reason)`; read over its own span, `except` line included."""
    first = handler.lineno
    last = handler.body[0].end_lineno or handler.body[0].lineno
    text = " ".join(lines[i - 1] for i in range(first, min(last, len(lines)) + 1))
    match = _MARKER_RE.search(text)
    if not match:
        return False, ""
    tail = _REASON_RE.match(match.group(1).strip())
    return True, (tail.group(1).strip() if tail else "")


def _enclosing_name(tree):
    """{handler node: the nearest enclosing function's name} — the weight report names the owner."""
    owners = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            owners.setdefault(child, node.name)
    return owners


def measure(root=None):
    """The swallowed-error footprint of the tree: the families, the markers and the ownering names."""
    root = root or default_root()
    out = {"root": root, "files": 0, "handlers": 0, "teardown": 0, "target": 0,
           "marked": 0, "unmarked": 0, "reasonless": 0,
           "sites": [], "per_file": {}, "unmarked_by_file": {}, "reasonless_sites": []}
    for path in iter_sources(root):
        rel = os.path.relpath(path, root).replace("\\", "/")
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as fh:
                source = fh.read()
        except OSError:
            continue
        out["files"] += 1
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        owners = _enclosing_name(tree)
        lines = source.splitlines()
        for handler in pass_only_handlers(tree):
            out["handlers"] += 1
            if is_teardown_family(handler):
                out["teardown"] += 1
                continue
            out["target"] += 1
            present, reason = handler_marker(lines, handler)
            out["per_file"][rel] = out["per_file"].get(rel, 0) + 1
            if present:
                out["marked"] += 1
                if not reason:
                    out["reasonless"] += 1
                    out["reasonless_sites"].append(f"{rel}:{handler.lineno}")
            else:
                out["unmarked"] += 1
                out["unmarked_by_file"][rel] = out["unmarked_by_file"].get(rel, 0) + 1
            out["sites"].append({"file": rel, "line": handler.lineno,
                                 "owner": owners.get(handler, "<module>"),
                                 "declared": sorted(declared_names(handler) or ()),
                                 "marked": present, "reason": reason})
    return out


def _top(rows, limit=5):
    return ", ".join(f"{name} ({n})" for name, n in sorted(rows.items(), key=lambda kv: -kv[1])[:limit]) \
        or "none"


def report(check, root=None, prefix="§1", enforce=True):
    """The measurement: every figure printed beside its pin, then the SIX checks of the gate.

    `enforce=True` (the default) is the GATE: an unmarked handler, an empty reason and a family over its
    pin all fail the suite (`AGENTS.md` §12.2). The scan control and the teardown predicate are checks
    either way — they prove the numbers below them mean something.
    """
    m = measure(root)
    print(f"  {prefix} swallowed errors: {m['handlers']} pass-only handlers — {m['teardown']} teardown "
          f"(declared exempt), {m['target']} in the target family (pin {TARGET_PIN})")
    print(f"    marked {m['marked']}, UNMARKED {m['unmarked']} (pin {UNMARKED_PIN}), "
          f"markers without a reason {m['reasonless']} (pin {REASONLESS_PIN})")
    print(f"    the family by file: {_top(m['per_file'], 8)}")
    if m["unmarked_by_file"]:
        print(f"    UNMARKED by file: {_top(m['unmarked_by_file'], 8)}")
    if m["reasonless_sites"]:
        print(f"    reasonless markers: {', '.join(m['reasonless_sites'][:8])}")
    check(f"{prefix} the scan really read the sources (a guard over nothing is useless)",
          m["files"] > 100, f"files={m['files']} handlers={m['handlers']}")
    if enforce:
        check(f"{prefix} every pass-only handler outside the teardown family carries the marker "
              f"({MARKER})", m["unmarked"] == 0,
              f"unmarked={m['unmarked']} — {_top(m['unmarked_by_file'], 5)}: add `# noqa: BLE001 — "
              f"<reason>` or FIX the swallow into a log line")
        check(f"{prefix} every marker carries a reason (the vocabulary of {len(REASONS)} declared "
              f"reasons)", m["reasonless"] == 0,
              f"reasonless={m['reasonless']}: {', '.join(m['reasonless_sites'][:5])}")
        check(f"{prefix} the family stays at or under its pins (target {TARGET_PIN}, "
              f"unmarked {UNMARKED_PIN})",
              m["target"] <= TARGET_PIN and m["unmarked"] <= UNMARKED_PIN,
              f"target={m['target']} unmarked={m['unmarked']} — the pins only go DOWN")
    check(f"{prefix} the per-file weights add up to the family it printed",
          sum(m["per_file"].values()) == m["target"] and m["target"] + m["teardown"] == m["handlers"],
          f"weights={sum(m['per_file'].values())} target={m['target']} teardown={m['teardown']} "
          f"all={m['handlers']}")
    check(f"{prefix} the teardown family is NOT counted (the predicate reads the declared names)",
          _predicate_holds(), _predicate_detail())
    return m


#: The synthetic handlers the predicate is proven on: ONLY the RuntimeError/AttributeError pair is exempt.
_PREDICATE_CASES = (
    ("except RuntimeError:", True),
    ("except (RuntimeError, AttributeError):", True),
    ("except (AttributeError, RuntimeError):", True),
    ("except Exception:", False),
    ("except OSError:", False),
    ("except (RuntimeError, OSError):", False),
    ("except:", False),
)


def _predicate_holds() -> bool:
    for source, expected in _PREDICATE_CASES:
        tree = ast.parse(f"try:\n    x = 1\n{source}\n    pass\n")
        handler = pass_only_handlers(tree)[0]
        if is_teardown_family(handler) is not expected:
            return False
    return True


def _predicate_detail() -> str:
    return ", ".join(f"{src} → {want}" for src, want in _PREDICATE_CASES)


def pin_block(m):
    """The paste-ready constants of a measurement (the maintainer lowers them by hand)."""
    return "\n".join((
        f"TARGET_PIN = {m['target']}",
        f"UNMARKED_PIN = {m['unmarked']}",
        f"REASONLESS_PIN = {m['reasonless']}",
    ))


def _main():
    m = measure()
    print(f"files read                : {m['files']}")
    print(f"pass-only handlers        : {m['handlers']}")
    print(f"  teardown (exempt)       : {m['teardown']}")
    print(f"  target family           : {m['target']}  (pin {TARGET_PIN})")
    print(f"    marked                : {m['marked']}")
    print(f"    UNMARKED              : {m['unmarked']}  (pin {UNMARKED_PIN})")
    print(f"    reasonless markers    : {m['reasonless']}  (pin {REASONLESS_PIN})")
    print("\n--- the family by file ---")
    for rel, n in sorted(m["per_file"].items(), key=lambda kv: -kv[1]):
        print(f"{n:5}  {rel}")
    if m["sites"]:
        print("\n--- the unmarked sites ---")
        for site in m["sites"]:
            if not site["marked"]:
                print(f"{site['file']}:{site['line']}  {site['owner']}  {site['declared']}")
    print("\n--- the pin block ---")
    print(pin_block(m))


if __name__ == "__main__":
    _main()
