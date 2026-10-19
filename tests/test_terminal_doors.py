# -*- coding: utf-8 -*-
"""The bottom row belongs to the `Servers` head (v1.12.2) — `Open map` / `Profiles` / `Open project`.
§1 the row is a control of ONE head (`_apply_panel_doors()`); §2 a map-backed window: `Commands`
first, the row with the `Servers` head; §3 the dock shows no row at all; §4 the standalone OPENS on
`Servers` with its `Open project` on screen; §5 the i18n and the release state (no new key).
Rule — `AGENTS.md` §4.3.8, §4.3.9; mechanism — `DOCUMENTATION.md` §14e, §75.
Contract — `TERMINAL_STANDALONE.md` §7 (its clause audit is `tests/test_terminal_standalone_contract.py`).
"""
import json
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least, translation_keys)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.command_library as CL  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_standalone as TS  # noqa: E402
import ui.main_window as MW  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.terminal_dock import TerminalDockContent  # noqa: E402

from _fakes import FakeSSHThread  # noqa: E402

ST.SSHTerminalThread = FakeSSHThread   # every session of this file runs on the fake
LANGS = load_i18n_langs(ROOT)
_windows = []


def _read(*parts) -> str:
    """The text of a repository file that SHIPS (the source audits below read two)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _body(name, *parts) -> str:
    """The source of ONE function — from its `def` to the next line that starts at column 0."""
    text = _read(*parts)
    start = text.find(f"def {name}(")
    if start < 0:
        return ""
    rest = text[start:].split("\n")
    out = [rest[0]]
    for line in rest[1:]:
        if line and not line[0].isspace():
            break
        out.append(line)
    return "\n".join(out)


def _project_file(name, servers) -> str:
    """A real project FILE under the run's scratch folder (never a fixture of the map itself)."""
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"version": "0.9", "servers": servers, "connections": []}, fh)
    return path


def _surface():
    """A standalone surface with its window shown (each call is torn down by the suite's exit)."""
    surface = TS.StandaloneSurface()
    surface.window.show()
    app.processEvents()
    return surface


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the bottom row is a control of ONE head ==")
# ════════════════════════════════════════════════════════════════════════════

_panel_src = _read("modules", "command_library.py")
check("§1 the row is ONE wrapper widget (a layout cannot be hidden) with the shipped buttons",
      "self.doors_row = QWidget()" in _panel_src
      and "bottom = QHBoxLayout(self.doors_row)" in _panel_src
      and "bl.addWidget(self.doors_row)" in _panel_src
      and "self.open_map_btn = QPushButton(" in _panel_src
      and "self.profiles_btn = QPushButton(" in _panel_src)
check("§1 `_apply_panel_doors()` is the ONE writer of its visibility",
      _panel_src.count("doors_row.setVisible(") == 1
      and "def _apply_panel_doors" in _panel_src
      and "self._apply_panel_doors()" in _body("_apply_head", "modules", "command_library.py"))
check("§1 the head is the ONLY switch: the row follows `_head`, never a config key",
      "servers = self._head == HEAD_SERVERS" in _body("_apply_panel_doors", "modules",
                                                      "command_library.py")
      and "ui_cmdlib_doors" not in _panel_src and "ui_cmdlib_head" not in _panel_src)
check("§1 the hint travels WITH the row (its text stays `_hint_text()`'s ONE answer)",
      "self.hint_label.setVisible(servers and bool(text))" in _body("_apply_panel_doors", "modules",
                                                                    "command_library.py")
      and "bl.addWidget(self.hint_label)" in _panel_src
      and "self.hint_label = QLabel(\"\")" in _panel_src)
check("§1 the wiring of the doors is untouched (the row moved, the doors did not)",
      "self.open_map_btn.clicked.connect(self._on_open_map)" in _panel_src
      and "self.profiles_btn.clicked.connect(self._on_profiles)" in _panel_src
      and "def set_map_doors" in _panel_src and "def set_project_door" in _panel_src
      and "def _on_open_map" in _panel_src and "def _on_profiles" in _panel_src)

clear_cfg()
mw = MW.MainWindow()
mw.show()
app.processEvents()
mw.scene.add_server(ServerData(id="td-1", alias="alpha", host="10.94.0.21", user="root"))
app.processEvents()

win = ST.SSHTerminalWindow(ServerData(id="tdw", alias="doors", host="10.94.9.9", user="root"),
                           mw, password="pw")
_windows.append(win)
win.show()
app.processEvents()
panel = win.cmdlib_panel

# ════════════════════════════════════════════════════════════════════════════
print("== §2 a map-backed window: `Commands` first, the row with `Servers` ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the window opens on `Commands` — a container with a map keeps the shipped head",
      panel.head() == CL.HEAD_COMMANDS and panel.tree.isVisible() is True
      and panel.server_tree.isVisible() is False,
      f"head={panel.head()!r}")
check("§2 the `Commands` head is its own list + Add/Edit/Delete (no door row, no hint)",
      panel.cmd_buttons.isVisible() is True and panel._file_btn.isVisible() is True
      and panel.doors_row.isHidden() is True and panel.hint_label.isHidden() is True,
      f"doors={panel.doors_row.isHidden()} hint={panel.hint_label.isHidden()}")

panel.set_head(CL.HEAD_SERVERS)
app.processEvents()
check("§2 the `Servers` head carries the row, and the row carries both doors",
      panel.head() == CL.HEAD_SERVERS and panel.doors_row.isVisible() is True
      and panel.open_map_btn.isVisible() is True and panel.profiles_btn.isVisible() is True
      and panel.cmd_buttons.isHidden() is True and panel._file_btn.isHidden() is True,
      f"doors={panel.doors_row.isVisible()}")
check("§2 a working surface still explains NOTHING (a hint under a working control is noise)",
      panel.hint_label.isHidden() is True and panel._hint_text() == "",
      repr(panel.hint_label.text()))

_doors = []
panel.set_map_doors(lambda: (_doors.append("map"), True)[1],
                    lambda: (_doors.append("profiles"), True)[1])
app.processEvents()
panel._on_open_map()
panel._on_profiles()
check("§2 both doors fire from THEIR head", _doors == ["map", "profiles"], str(_doors))

panel.set_head(CL.HEAD_COMMANDS)
app.processEvents()
check("§2 a round trip leaves nothing behind (the head state survives the switch back)",
      panel.head() == CL.HEAD_COMMANDS and panel.doors_row.isHidden() is True
      and panel.tree.isVisible() is True and panel.server_tree.isVisible() is False,
      f"head={panel.head()!r}")

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the dock: the map IS that window, so it shows no row at all ==")
# ════════════════════════════════════════════════════════════════════════════

dock = TerminalDockContent(mw)
app.processEvents()
dpanel = dock.cmdlib_panel
check("§3 the dock's `Servers` head stays unavailable (the ONE predicate, unchanged)",
      dpanel.container_kind() == "dock" and dpanel.map_is_this_window() is True
      and dpanel.servers_available() is False and dpanel.head() == CL.HEAD_COMMANDS,
      f"{dpanel.container_kind()!r} available={dpanel.servers_available()}")
check("§3 …so its whole bottom row is gone (no dead `Open map` to explain)",
      dpanel.doors_row.isHidden() is True and dpanel.hint_label.isHidden() is True,
      f"doors={dpanel.doors_row.isHidden()} hint={dpanel.hint_label.isHidden()}")
check("§3 the sentence is still the ONE answer of the head (a refusal speaks it)",
      dpanel._hint_text() == i18n.t("terminal.cmdlib.map_is_here")
      and dpanel.hint_label.text() == i18n.t("terminal.cmdlib.map_is_here"),
      repr(dpanel.hint_label.text()))

_dmsgs = []
dpanel.status_message.connect(lambda text, ms: _dmsgs.append((text, ms)))
dpanel.set_head(CL.HEAD_SERVERS)
app.processEvents()
check("§3 a click on the dead head is refused in ONE sentence and moves no row",
      dpanel.head() == CL.HEAD_COMMANDS
      and _dmsgs == [(i18n.t("terminal.cmdlib.map_is_here"), 4000)]
      and dpanel.doors_row.isHidden() is True
      and dpanel.head_servers_btn.isChecked() is False,
      f"head={dpanel.head()!r} msgs={_dmsgs}")

_docked = []
dpanel.set_map_doors(None, lambda: (_docked.append("profiles"), True)[1])
app.processEvents()
dpanel._on_profiles()
dpanel._on_open_map()
app.processEvents()
check("§3 `Profiles` stays reachable (`_on_profiles()` answers) while `Open map` only speaks",
      _docked == ["profiles"] and _dmsgs[-1] == (i18n.t("terminal.cmdlib.map_is_here"), 4000),
      f"calls={_docked} msgs={len(_dmsgs)}")

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the standalone OPENS on `Servers` with `Open project` on screen ==")
# ════════════════════════════════════════════════════════════════════════════

surface = _surface()
spanel = surface.window.cmdlib_panel
check("§4 the container moves the head at construction — the row is there from the first second",
      spanel.head() == CL.HEAD_SERVERS and spanel.doors_row.isVisible() is True
      and spanel.open_map_btn.isVisible() is True
      and spanel.open_map_btn.text() == i18n.t("terminal.cmdlib.open_project"),
      f"head={spanel.head()!r} doors={spanel.doors_row.isVisible()}")
check("§4 the head is LIVE before a project exists (an empty list is a real answer)",
      surface.project_nodes() == [] and spanel.servers_available() is True
      and spanel.project_is_open() is False
      and spanel.server_tree.topLevelItemCount() == 0
      and spanel.info_label.text() == i18n.t("terminal.cmdlib.no_project"),
      f"available={spanel.servers_available()} info={spanel.info_label.text()!r}")
check("§4 …and the sentence names the PROJECT it does not have, not one that has no servers",
      spanel.info_label.text() != i18n.t("terminal.cmdlib.project_empty")
      and i18n.t("terminal.cmdlib.no_project") in spanel.info_label.text(),
      repr(spanel.info_label.text()))
check("§4 …so nothing is explained away and no status line is written at start-up",
      spanel.hint_label.isHidden() is True and spanel._hint_text() == ""
      and surface.window.statusBar().currentMessage() == "",
      repr(surface.window.statusBar().currentMessage()))

_project = _project_file("doors-project.json", [
    {"id": "tdp-1", "alias": "web-1", "host": "10.20.0.11", "user": "root", "ssh_port": 22},
    {"id": "tdp-2", "alias": "web-2", "host": "10.20.0.12", "user": "admin", "ssh_port": 2222},
])
check("§4 the door loads the file and the SAME head keeps the row",
      surface.open_project(_project) is True and spanel.head() == CL.HEAD_SERVERS
      and spanel.server_tree.topLevelItemCount() == 2
      and spanel.doors_row.isVisible() is True,
      f"rows={spanel.server_tree.topLevelItemCount()} doors={spanel.doors_row.isVisible()}")
check("§4 the loaded list answers rows, not an empty state (the info label clears)",
      spanel.info_label.text() == "" and spanel.hint_label.isHidden() is True,
      repr(spanel.info_label.text()))

spanel.set_head(CL.HEAD_COMMANDS)
app.processEvents()
check("§4 the standalone's `Commands` head is the library alone (the row leaves with the head)",
      spanel.head() == CL.HEAD_COMMANDS and spanel.doors_row.isHidden() is True
      and spanel.tree.isVisible() is True and spanel.cmd_buttons.isVisible() is True,
      f"doors={spanel.doors_row.isHidden()}")

for _w in list(_windows):
    try:
        _w.close()
    except RuntimeError:
        pass
_windows.clear()
dock.close()
dock.deleteLater()
surface.window.close()
app.processEvents()

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the i18n and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check("§5 this release adds NO key (the row changed its head, not its words)",
      all(len(translation_keys(LANGS[c])) == EXPECTED_I18N_KEYS for c in LANGS)
      # the 1114 the panel release left + the keys the LATER follow-ups of the line added
      # (v1.12.3's THREE: the jump host's label, its hint and the import picker's column).
      and EXPECTED_I18N_KEYS == 1114 + 3 + 1 + 4 + 3 + 2 + 8,
      str({c: len(translation_keys(LANGS[c])) for c in sorted(LANGS)}))
check("§5 the sentences the row shows are the SHIPPED keys of v1.11 / v1.12",
      all(LANGS["en"].get(k) for k in ("terminal.cmdlib.open_map", "terminal.cmdlib.profiles",
                                       "terminal.cmdlib.open_project", "terminal.cmdlib.map_is_here",
                                       "terminal.cmdlib.project_empty"))
      and all(k in _panel_src for k in ("terminal.cmdlib.open_map", "terminal.cmdlib.profiles",
                                        "terminal.cmdlib.open_project")))

check_release_state(ROOT)
check("§5 the pin names this line's release or a later one (the rc slots ride on the same code)",
      releases_at_least(EXPECTED_APP_VERSION, "1.12"), EXPECTED_APP_VERSION)
check("§5 the schema did NOT move (no project format change)",
      'VERSION_FORMAT = "0.9"' in _read("version.py"))
check("§5 the topical file is listed by the suite map (tests/INDEX.md regenerated)",
      "test_terminal_doors.py" in _read("tests", "INDEX.md"))

finish()
