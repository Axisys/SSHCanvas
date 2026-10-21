# -*- coding: utf-8 -*-
"""The module-size ratchet: the declared band and the line pins behind `tests/test_size_budget.py`.

A module's size is a correctness property of THIS tree: the facades are read WHOLE by a maintainer
and by an agent, and a file that grows a few lines per release reaches the point where every edit
pays for the whole file. The band is the DECLARATION — a module at or over it is pinned at its
measured size and the pin only goes DOWN — while the two release contracts (`ui/main_window.py` <
2 000 lines, `modules/sftp_tab.py` < 3 000) stay the wider bands above it. The gate is ALWAYS ON:
it reads the CODE, so it belongs to the default run (`AGENTS.md` §8.2) and never to `--docs`.
Rule — `AGENTS.md` §12.5.
"""
import os

# ── The band and the ratchet (the numbers `AGENTS.md` §12.5 states) ────────────────────────────
BUDGET_BAND_LINES = 900   # at or over it a module is PINNED; under it a module is free up to it

# How far a pin may sit ABOVE its module before it is STALE: a compression that leaves the ratchet
# where it was hides the next regression, so the block this module prints is applied after every
# shrink. A pin BELOW its module is always an error (the over-pin check below).
PIN_SLACK_LINES = 60

# {module path relative to the root: max lines} — measured AFTER the release's own compression,
# paste-ready from `python tests/_size_budget.py`. A pin only ever goes DOWN; a module at or over
# the band that has NO line here is a module the release had to pin.
LINE_PINS = {
    "modules/sftp_tab.py": 2938,
    "modules/ssh_terminal.py": 2469,
    "ui/settings_dialog.py": 2452,
    "modules/command_library.py": 2362,
    "modules/terminal_page.py": 2017,
    "graphics/server_node.py": 2009,
    "modules/sftp_worker.py": 1879,
    "modules/sftp_pane_viewer.py": 1808,
    "ui/main_window.py": 1778,
    "graphics/map_view.py": 1622,
    "ui/main_window_node_ops.py": 1482,
    "modules/plugin_manager.py": 1462,
    "ui/sidebar.py": 1447,
    "ui/main_window_ssh.py": 1437,
    "modules/command_history.py": 1368,
    "graphics/node_group.py": 1327,
    "modules/terminal_widget.py": 1299,
    "graphics/map_scene.py": 1250,
    "ui/plugins_panel.py": 1141,
    "modules/terminal_diff.py": 1128,
    "modules/local_fs_worker.py": 1106,
    "ui/main_window_project_io.py": 1087,
    "ui/theme.py": 1071,
    "modules/undo_commands.py": 969,
    "modules/sftp_pane_transfer.py": 901,
}

# The application tree the band governs — the same set `ROADMAP.md`'s total measures: the suite and
# the vendored fork are code about the code, the example plugins ship as examples, never as modules.
_SKIP_DIRS = {"tests", "third_party", "examples", "docs", "__pycache__", ".git", "build", "dist",
              "test-results", "_tmp_testdata"}


def default_root():
    """The repository root (this file lives in `<root>/tests/`)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iter_modules(root):
    """Every module of the application tree, as paths relative to `root` (sorted)."""
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith("_tmp_testdata")]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            out.append(os.path.relpath(os.path.join(base, name), root).replace("\\", "/"))
    return sorted(out)


def line_count(path):
    """The lines of ONE module — the same count a plan's figure and a pin speak (0 — unreadable)."""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return len(fh.read().splitlines())
    except OSError:
        return 0


def measure(root=None):
    """The size footprint of the tree: every module, its pin, and the four ways a pin can be wrong."""
    root = root or default_root()
    rows = []
    for rel in iter_modules(root):
        lines = line_count(os.path.join(root, rel))
        rows.append({"module": rel, "lines": lines, "pin": LINE_PINS.get(rel)})
    pinned = [r for r in rows if r["pin"] is not None]
    measured = {r["module"] for r in rows}
    return {
        "root": root, "rows": rows, "files": len(rows),
        "lines": sum(r["lines"] for r in rows), "pinned": len(pinned),
        "over_pin": [r for r in pinned if r["lines"] > r["pin"]],
        "unpinned": [r for r in rows if r["lines"] >= BUDGET_BAND_LINES
                     and r["pin"] is None],
        "below_band": [r for r in pinned if r["lines"] < BUDGET_BAND_LINES],
        "stale": [r for r in pinned if r["pin"] - r["lines"] > PIN_SLACK_LINES],
        "phantom": sorted(set(LINE_PINS) - measured),
    }


def _names(rows, limit=4):
    return ", ".join(f"{r['module']} ({r['lines']})" for r in rows[:limit]) or "none"


def report(check, root=None, prefix="§1", enforce=True):
    """The size measurement: every pin printed beside its module, then the six checks of the gate.

    `enforce=True` (the default) is the GATE — an over-pin, an unpinned module at the band and a
    stale pin all fail the suite. The scan control is a check either way (`AGENTS.md` §12.5).
    """
    m = measure(root)
    print(f"  {prefix} module sizes: {m['files']} modules, {m['lines']} lines, "
          f"band {BUDGET_BAND_LINES}, {m['pinned']} pinned")
    for row in sorted(m["rows"], key=lambda r: -r["lines"])[:12]:
        pin = "—" if row["pin"] is None else str(row["pin"])
        mark = "" if row["pin"] is None or row["lines"] <= row["pin"] else "  OVER PIN"
        print(f"    {row['lines']:>6}  {row['module']:44} pin {pin:>6}{mark}")
    if m["unpinned"]:
        print(f"    note: at or over the band with NO pin = {_names(m['unpinned'])}")
    if m["stale"]:
        print(f"    note: pins more than {PIN_SLACK_LINES} lines above their module = "
              f"{_names(m['stale'])} — paste the block `python tests/_size_budget.py` prints")
    check(f"{prefix} the scan really read the module tree (a guard over nothing is useless)",
          m["files"] > 100, f"modules={m['files']} lines={m['lines']}")
    if enforce:
        check(f"{prefix} no pinned module is over its pin",
              not m["over_pin"],
              f"{_names(m['over_pin'])} — a version that needs lines in a pinned file pays for "
              f"them in the SAME change")
        check(f"{prefix} every module at or over the band ({BUDGET_BAND_LINES} lines) has a pin",
              not m["unpinned"], f"{_names(m['unpinned'])}")
        check(f"{prefix} no pin is left under the band (a pin that outlives its size is stale)",
              not m["below_band"], f"{_names(m['below_band'])}")
        check(f"{prefix} no pin sits more than {PIN_SLACK_LINES} lines above its module",
              not m["stale"], f"{_names(m['stale'])}")
    check(f"{prefix} every pin names a module this tree holds "
          f"(the report prints each pin beside its measurement)",
          not m["phantom"], f"phantom={m['phantom']}")
    return m


def pin_block(m):
    """The paste-ready `LINE_PINS` table of a measurement (the maintainer lowers it by hand)."""
    return "\n".join(f'    "{row["module"]}": {row["lines"]},'
                     for row in sorted(m["rows"], key=lambda r: -r["lines"])
                     if row["lines"] >= BUDGET_BAND_LINES)


def _main():
    m = measure()
    print(f"{m['files']} modules, {m['lines']} lines; band {BUDGET_BAND_LINES} lines, "
          f"{m['pinned']} pinned, slack {PIN_SLACK_LINES}")
    print(f"\n{'lines':>6}  {'pin':>6}  module")
    for row in sorted(m["rows"], key=lambda r: -r["lines"]):
        if row["lines"] < BUDGET_BAND_LINES and row["pin"] is None:
            continue
        pin = "—" if row["pin"] is None else str(row["pin"])
        state = "" if row["pin"] is None or row["lines"] <= row["pin"] else "  OVER PIN"
        print(f"{row['lines']:>6}  {pin:>6}  {row['module']}{state}")
    print(f"\nover the pin: {_names(m['over_pin'], 10)}")
    print(f"unpinned at the band: {_names(m['unpinned'], 10)}")
    print(f"stale pins: {_names(m['stale'], 10)}")
    print(f"phantom pins: {m['phantom'] or 'none'}")
    print("\n--- the paste-ready pins (lower them as you compress) ---")
    print(pin_block(m))


if __name__ == "__main__":
    _main()
