# -*- coding: utf-8 -*-
"""The terminal panel that holds both lists (v1.11) — the `Commands | Servers` heads and the close path.
§1 the two heads and the exclusive head state; §2 the `Servers` rows and their ONE provider pair;
§3 a click goes through the HOST's connect door, never `add_session()`; §4 the bottom row, the ONE
dock predicate and the inline hint; §5 the containers install the pair; §6 the `retranslate()` /
`refresh_theme()` walks and the i18n; §7 the close path — the question precedes the teardown and the
last project is remembered after the save; §8 the release state.
Rule — `AGENTS.md` §4.1, §4.3, §4.6, §4.26; mechanism — `DOCUMENTATION.md` §14, §14c, §14e, §64.
"""
import ast
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     read_cfg, releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.command_library as CL  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import ui.main_window as MW  # noqa: E402
import ui.theme_qss as TQ  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.terminal_dock import TerminalDockContent  # noqa: E402
from ui.main_window_project_io import last_project_path  # noqa: E402

from _fakes import FakeSSHThread  # noqa: E402


def _read(*parts) -> str:
    """The text of a repository file that SHIPS (the source audits below read several)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _imports(*parts) -> set:
    """Every module name a shipped file really IMPORTS (the AST — a docstring mention is not one)."""
    names = set()
    for node in ast.walk(ast.parse(_read(*parts))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _calls(*parts, attr: str) -> list:
    """Every `<something>.<attr>(…)` CALL in a shipped file (a mention in prose is not a call)."""
    return [n for n in ast.walk(ast.parse(_read(*parts)))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == attr]


ST.SSHTerminalThread = FakeSSHThread   # every page/window of this file runs on the fake

_windows = []


def new_node(alias, host="10.94.0.1", node_id=None, **kw):
    mw.scene.add_server(ServerData(id=node_id or f"tp-{alias}", alias=alias, host=host,
                                   user=kw.pop("user", "root"), **kw))
    app.processEvents()
    return mw.scene.get_node(node_id or f"tp-{alias}")


def make_window():
    """A standalone terminal window, parented to the map (the shipped spawn shape)."""
    win = ST.SSHTerminalWindow(
        ServerData(id="tpw-main", alias="panel", host="10.94.9.9", user="root"), mw, password="pw")
    _windows.append(win)
    win.show()
    app.processEvents()
    return win


clear_cfg()
mw = MW.MainWindow()
mw.show()
app.processEvents()

# ════════════════════════════════════════════════════════════════════════════
print("== §1 the two heads and the exclusive head state ==")
# ════════════════════════════════════════════════════════════════════════════

_src = _read("modules", "command_library.py")
check("§1 the two heads are declared ONCE as a VIEW STATE (never a config key)",
      CL.HEAD_COMMANDS == "commands" and CL.HEAD_SERVERS == "servers"
      and "ui_cmdlib_head" not in _src
      and 'HEAD_COMMANDS = "commands"' in _src and 'HEAD_SERVERS = "servers"' in _src,
      f"{CL.HEAD_COMMANDS} {CL.HEAD_SERVERS}")

alpha = new_node("alpha", "10.94.0.11")
beta = new_node("beta", "10.94.0.12", user="admin", ssh_port=2222)
win = make_window()
panel = win.cmdlib_panel
check("§1 a window opened from the application shows the `Commands` head",
      panel.head() == CL.HEAD_COMMANDS and panel.head_commands_btn.isChecked() is True
      and panel.head_servers_btn.isChecked() is False
      and panel.tree.isVisible() is True and panel.server_tree.isVisible() is False,
      f"head={panel.head()!r}")

panel.set_head(CL.HEAD_SERVERS)
app.processEvents()
check("§1 the `Servers` head shows the server list and hides the commands surface",
      panel.head() == CL.HEAD_SERVERS and panel.server_tree.isVisible() is True
      and panel.tree.isVisible() is False
      and panel.cmd_buttons.isVisible() is False and panel._file_btn.isVisible() is False
      and panel.head_servers_btn.isChecked() is True
      and panel.search.placeholderText() == i18n.t("terminal.cmdlib.servers_search"),
      f"head={panel.head()!r} placeholder={panel.search.placeholderText()!r}")
check("§1 the bottom row `Open map` / `Profiles` belongs to the `Servers` head alone",
      panel.doors_row.isVisible() is True and panel.open_map_btn.isVisible() is True
      and panel.profiles_btn.isVisible() is True,
      f"doors={panel.doors_row.isVisible()}")

msgs_head = []
panel.status_message.connect(lambda text, ms: msgs_head.append((text, ms)))
panel.set_head(CL.HEAD_SERVERS)     # a click on the ACTIVE head
app.processEvents()
check("§1 a click on the ACTIVE head changes nothing and says nothing",
      panel.head() == CL.HEAD_SERVERS and msgs_head == [] and panel.head_servers_btn.isChecked(),
      f"head={panel.head()!r} msgs={msgs_head}")

panel.set_head(CL.HEAD_COMMANDS)
app.processEvents()
check("§1 Add/Edit/Delete and the library-file menu belong to the `Commands` head alone",
      panel.cmd_buttons.isVisible() and panel._file_btn.isVisible()
      and panel.tree.isVisible() and not panel.server_tree.isVisible()
      and panel.search.placeholderText() == i18n.t("terminal.cmdlib.search_placeholder"))
check("§1 …and the bottom row LEFT with the other head (the `Commands` head is its own list)",
      panel.doors_row.isVisible() is False and panel.open_map_btn.isVisible() is False
      and panel.profiles_btn.isVisible() is False,
      f"doors={panel.doors_row.isVisible()}")

panel.set_collapsed(True)
app.processEvents()
check("§1 the collapse keeps its own control and the ONE shipped key (a head adds none)",
      panel.is_collapsed() is True and panel._strip.isVisible() and not panel._body.isVisible()
      and read_cfg({}).get("ui_cmdlib_collapsed") is True
      and read_cfg({}).get("ui_cmdlib_head") is None,
      str(sorted(k for k in read_cfg({}) if "cmdlib" in k)))
panel.set_collapsed(False)
app.processEvents()
check("§1 ...and the head state survives a collapse/expand round trip",
      panel.head() == CL.HEAD_COMMANDS and panel._body.isVisible())


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the `Servers` rows and the ONE provider pair ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the row facts are a PURE duck-typed reader (the panel imports no `graphics/`)",
      CL.server_row_facts(alpha) == ("tp-alpha", "alpha", "root@10.94.0.11:22", ())
      and CL.server_row_facts(beta) == ("tp-beta", "beta", "admin@10.94.0.12:2222", ())
      and CL.server_row_facts(ServerData(id="plain", alias="p", host="h", user="")) ==
      ("plain", "p", "h:22", ())
      and CL.server_row_facts(object()) == ("", "", ":22", ())
      and CL.server_row_facts(ServerData(id="t", alias="t", host="h", user="u",
                                         tags=["prod", "web", "prod"])) ==
      ("t", "t", "u@h:22", ("prod", "web"))
      and not any("graphics" in n for n in _imports("modules", "command_library.py")),
      f"{CL.server_row_facts(alpha)} | {CL.server_row_facts(object())} "
      f"| {sorted(n for n in _imports('modules', 'command_library.py') if 'graphics' in n)}")
check("§2 the panel NEVER calls a container's `add_session()` (the door belongs to the HOST)",
      _calls("modules", "command_library.py", attr="add_session") == []
      and "set_server_sources" in _src and "set_map_doors" in _src)

panel.set_head(CL.HEAD_SERVERS)
app.processEvents()
rows = [panel.server_tree.topLevelItem(i).text(0)
        for i in range(panel.server_tree.topLevelItemCount())]
check("§2 the rows are the map's aliases, in the map's own order",
      rows == ["alpha", "beta"], str(rows))
check("§2 a row carries its row KEY as its data and the identity as its tooltip",
      str(panel.server_tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole)).startswith("tp-alpha@")
      and panel.server_tree.topLevelItem(0).toolTip(0) == "root@10.94.0.11:22"
      and panel._server_for_item(panel.server_tree.topLevelItem(1)) is beta,
      str(panel.server_tree.topLevelItem(1).toolTip(0)))

panel.search.setText("adm")
app.processEvents()
check("§2 the search filters the rows by alias OR identity (case-insensitive)",
      [panel.server_tree.topLevelItem(i).isHidden()
       for i in range(panel.server_tree.topLevelItemCount())] == [True, False])
panel.search.setText("10.94.0.11")
app.processEvents()
check("§2 ...and the identity half is searched too (the host is not in the row text)",
      [panel.server_tree.topLevelItem(i).isHidden()
       for i in range(panel.server_tree.topLevelItemCount())] == [False, True])
panel.search.setText("zzz_no_such")
app.processEvents()
check("§2 no match: the rows are hidden and the label says so",
      panel.info_label.text() == i18n.t("terminal.cmdlib.servers_no_matches"),
      panel.info_label.text())
panel.search.setText("")
app.processEvents()
check("§2 a cleared search brings every row back",
      [panel.server_tree.topLevelItem(i).isHidden()
       for i in range(panel.server_tree.topLevelItemCount())] == [False, False]
      and panel.info_label.text() == "")

gamma = new_node("gamma", "10.94.0.13")
panel.refresh_servers()
app.processEvents()
check("§2 `refresh_servers()` re-reads the provider (a card added after the build shows up)",
      [panel.server_tree.topLevelItem(i).text(0)
       for i in range(panel.server_tree.topLevelItemCount())] == ["alpha", "beta", "gamma"])
panel._servers_provider = lambda: []
panel.refresh_servers()
app.processEvents()
check("§2 an empty map answers the `servers_empty` sentence, not a blank panel",
      panel.server_tree.topLevelItemCount() == 0
      and panel.info_label.text() == i18n.t("terminal.cmdlib.servers_empty"),
      panel.info_label.text())

panel.set_server_sources(win._panel_server_nodes, win._panel_connect_server)
app.processEvents()
check("§2 the provider pair is installed as ONE pair (both halves or neither)",
      panel.servers_available() is True and panel._connect_sink is not None
      and panel.server_tree.topLevelItemCount() == 3)
panel.set_server_sources(None, None)
app.processEvents()
check("§2 a missing provider pair leaves the head inactive (no rows, no door)",
      panel.servers_available() is False and panel._servers_provider is None
      and panel.server_tree.topLevelItemCount() == 0)
panel.set_server_sources(win._panel_server_nodes, win._panel_connect_server)
app.processEvents()


# ════════════════════════════════════════════════════════════════════════════
print("== §3 a click goes through the HOST's connect door ==")
# ════════════════════════════════════════════════════════════════════════════

_asked = []


class _RefusingDialog:
    """The `SSHConnectDialog` seam: it records who was asked and refuses (no session is opened)."""

    def __init__(self, data, parent=None):
        _asked.append(data)

    def exec(self):
        from PySide6.QtWidgets import QDialog
        return QDialog.DialogCode.Rejected


_orig_dlg = MW.SSHConnectDialog
MW.SSHConnectDialog = _RefusingDialog
try:
    sessions_before = len(mw._terminal_windows)
    panel.set_head(CL.HEAD_SERVERS)
    app.processEvents()
    panel._activate_server_item(panel.server_tree.topLevelItem(1))
    app.processEvents()
    check("§3 a server click builds the SAME `SSHConnectDialog` the map builds (the host's door)",
          len(_asked) == 1 and _asked[0] is beta.data and _asked[0].alias == "beta",
          str([d.alias for d in _asked]))
    check("§3 ...and a refused dialog opens no session (the panel never calls `add_session()`)",
          len(mw._terminal_windows) == sessions_before,
          f"{sessions_before} -> {len(mw._terminal_windows)}")

    # The unmanaged gate is asked by the DOOR itself — the panel inherits it for free (§4.21).
    mw.scene.add_server(ServerData(id="tp-unm", alias="no-ssh", host="10.94.0.99", user="root",
                                   unmanaged=True))
    app.processEvents()
    panel.refresh_servers()
    app.processEvents()
    row = None
    for i in range(panel.server_tree.topLevelItemCount()):
        cand = panel.server_tree.topLevelItem(i)
        if panel._server_for_item(cand) is not None \
                and panel._server_for_item(cand).data.id == "tp-unm":
            row = cand
    _asked.clear()
    panel._activate_server_item(row)
    app.processEvents()
    check("§3 an UNMANAGED card is refused by the shared door (no dialog is built at all)",
          row is not None and _asked == []
          and mw.statusBar().currentMessage()
          == i18n.t("unmanaged.blocked", action=i18n.t("ctx.ssh_connect")),
          f"asked={len(_asked)} status={mw.statusBar().currentMessage()!r}")
    mw.scene.remove_server("tp-unm")
    app.processEvents()
finally:
    MW.SSHConnectDialog = _orig_dlg

panel.set_head(CL.HEAD_COMMANDS)
app.processEvents()


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the bottom row, the ONE dock predicate and the inline hint ==")
# ════════════════════════════════════════════════════════════════════════════

check("§4 the container predicate reads `CONTAINER_KIND` off the parent chain",
      CL.container_kind_of(panel) == "window"
      and CL.container_kind_of("not-a-widget") == ""
      and CL.container_kind_of(None) == ""
      and panel.map_is_this_window() is False,
      f"{CL.container_kind_of(panel)!r}")
check("§4 a window with a map behind it has NOTHING to explain (the hint stays hidden)",
      panel.hint_label.text() == "" and panel.hint_label.isHidden() is True)

_doors = []
win._panel_open_map = lambda: (_doors.append("map"), True)[1]
win._panel_open_profiles = lambda: (_doors.append("profiles"), True)[1]
panel.set_map_doors(win._panel_open_map, win._panel_open_profiles)
app.processEvents()
check("§4 the bottom row is a control OF the `Servers` head (the `Commands` head hides it)",
      panel.head() == CL.HEAD_COMMANDS and panel.doors_row.isVisible() is False)
panel.set_head(CL.HEAD_SERVERS)
app.processEvents()
panel._on_open_map()
panel._on_profiles()
check("§4 the `Servers` head shows the row again and BOTH doors fire (the map and the profiles)",
      panel.doors_row.isVisible() is True and _doors == ["map", "profiles"], str(_doors))
check("§4 the bottom row wears the shipped keys in every language",
      panel.open_map_btn.text() == i18n.t("terminal.cmdlib.open_map")
      and panel.profiles_btn.text() == i18n.t("terminal.cmdlib.profiles")
      and panel.open_map_btn.toolTip() == i18n.t("terminal.cmdlib.open_map_tooltip")
      and panel.profiles_btn.toolTip() == i18n.t("terminal.cmdlib.profiles_tooltip"),
      f"{panel.open_map_btn.text()!r} {panel.profiles_btn.text()!r}")

dock = TerminalDockContent(mw)
app.processEvents()
dpanel = dock.cmdlib_panel
check("§4 the DOCK is the ONE predicate's other answer (the map IS that window)",
      dpanel.container_kind() == "dock" and dpanel.map_is_this_window() is True
      and dpanel.servers_available() is False,
      f"{dpanel.container_kind()!r}")
check("§4 the dock shows NO bottom row at all (it lives with the head it belongs to)",
      dpanel.head() == CL.HEAD_COMMANDS and dpanel.doors_row.isHidden() is True
      and dpanel.hint_label.isHidden() is True,
      f"doors={dpanel.doors_row.isHidden()} hint={dpanel.hint_label.isHidden()}")
check("§4 …and the sentence of its inactive `Servers` head waits with the row it explains",
      dpanel._hint_text() == i18n.t("terminal.cmdlib.map_is_here")
      and dpanel.hint_label.text() == i18n.t("terminal.cmdlib.map_is_here")
      and dpanel._servers_provider is None,
      repr(dpanel.hint_label.text()))

dmsgs = []
dpanel.status_message.connect(lambda text, ms: dmsgs.append((text, ms)))
dpanel.set_head(CL.HEAD_SERVERS)
app.processEvents()
check("§4 a click on the inactive head refuses the switch and answers in the status line",
      dpanel.head() == CL.HEAD_COMMANDS
      and dmsgs == [(i18n.t("terminal.cmdlib.map_is_here"), 4000)]
      and dpanel.head_commands_btn.isChecked() is True
      and dpanel.head_servers_btn.isChecked() is False
      and dpanel.doors_row.isHidden() is True,
      f"head={dpanel.head()!r} msgs={dmsgs} doors={dpanel.doors_row.isHidden()}")

docked_doors = []
dpanel.set_map_doors(None, lambda: (docked_doors.append("profiles"), True)[1])
app.processEvents()
dpanel._on_profiles()
app.processEvents()
check("§4 a refused head keeps the dock on `Commands` — and its dead `Open map` with it",
      dpanel.head() == CL.HEAD_COMMANDS and dpanel.doors_row.isHidden() is True
      and docked_doors == ["profiles"],
      f"head={dpanel.head()!r} doors={dpanel.doors_row.isHidden()}")
dpanel._on_open_map()
app.processEvents()
check("§4 the refusal path of the `Open map` door is untouched (one sentence, no crash)",
      docked_doors == ["profiles"]
      and dmsgs[-1] == (i18n.t("terminal.cmdlib.map_is_here"), 4000),
      f"doors={docked_doors} msgs={len(dmsgs)}")

_calls = []
_orig_profiles = mw._open_profile_manager
mw._open_profile_manager = lambda: _calls.append("profiles")
try:
    check("§4 the dock's `Profiles` door resolves the host hook on the parent chain",
          dock._panel_open_profiles() is True and _calls == ["profiles"], str(_calls))
finally:
    mw._open_profile_manager = _orig_profiles


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the containers install the pair (no `ui.main_window` import either way) ==")
# ════════════════════════════════════════════════════════════════════════════

_winsrc = _read("modules", "ssh_terminal.py")
_docksrc = _read("modules", "terminal_dock.py")
check("§5 the window installs the provider pair and both doors at construction",
      "set_server_sources(self._panel_server_nodes, self._panel_connect_server)" in _winsrc
      and "set_map_doors(self._panel_open_map, self._panel_open_profiles)" in _winsrc)
check("§5 the dock installs the `Profiles` door ONLY (its map is the window it lives in)",
      "set_map_doors(None, self._panel_open_profiles)" in _docksrc
      and "set_server_sources" not in _docksrc)
check("§5 neither container imports `ui.main_window` (the pair is duck-typed, §4.1)",
      not any(n.endswith("main_window") for n in _imports("modules", "ssh_terminal.py"))
      and not any(n.endswith("main_window") for n in _imports("modules", "terminal_dock.py"))
      and not any(n.endswith("main_window") for n in _imports("modules", "command_library.py"))
      and "find_host_hook" in _winsrc and "find_host_hook" in _docksrc,
      str(sorted(n for n in _imports("modules", "ssh_terminal.py") if "main" in n)))
check("§5 the map side is a pair of duck-typed hooks on the facade (the source and the raise)",
      callable(getattr(mw, "map_server_nodes", None))
      and callable(getattr(mw, "_raise_map_window", None))
      and [n.data.id for n in mw.map_server_nodes()] == ["tp-alpha", "tp-beta", "tp-gamma"],
      str([n.data.id for n in mw.map_server_nodes()]))
check("§5 `map_server_nodes()` is the map's OWN accessor (`MapScene.nodes()`), never a copy",
      "return list(self.scene.nodes())" in _read("ui", "main_window_ssh.py"))
check("§5 a hook nobody answers is an EMPTY source, not an exception",
      ST.SSHTerminalWindow._panel_server_nodes(object()) is None
      and ST.SSHTerminalWindow._panel_connect_server(object(), alpha) is False
      and ST.SSHTerminalWindow._panel_open_map(object()) is False
      and ST.SSHTerminalWindow._panel_open_profiles(object()) is False)
MW.SSHConnectDialog = _RefusingDialog      # the real door, asked without a modal dialog
try:
    check("§5 ...while the real window resolves the map and all three doors on its parent chain",
          [n.data.id for n in win._panel_server_nodes()] == ["tp-alpha", "tp-beta", "tp-gamma"]
          and win._panel_connect_server(alpha) is True and win._panel_open_map() is True
          and win._panel_open_profiles() is True)
finally:
    MW.SSHConnectDialog = _orig_dlg


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the `retranslate()` / `refresh_theme()` walks and the i18n ==")
# ════════════════════════════════════════════════════════════════════════════

check("§6 the two heads wear the ONE declared exclusive-toggle look (a shared registry body)",
      "panel.head" in TQ.style_names() and TQ.style("panel.head") == TQ.style("sftp.source_button")
      and "QToolButton:checked" in TQ.style("panel.head")
      and 'theme_qss.refresh(button, "panel.head")' in _src,
      f"{len(TQ.style_names())} registry names")

_saved_lang = i18n.load_config().get("language", "en")
try:
    i18n.set_language("ru")
    win.retranslate()
    app.processEvents()
    check("§6 `retranslate()` reaches BOTH heads, the server list and the bottom row",
          panel.head_commands_btn.text() == i18n.t("terminal.cmdlib.title")
          and panel.head_servers_btn.text() == i18n.t("terminal.cmdlib.head_servers")
          and panel.server_tree.headerItem().text(0) == i18n.t("terminal.cmdlib.head_servers")
          and panel.open_map_btn.text() == i18n.t("terminal.cmdlib.open_map")
          and panel.profiles_btn.text() == i18n.t("terminal.cmdlib.profiles"),
          f"{panel.head_servers_btn.text()!r} {panel.open_map_btn.text()!r}")
    check("§6 ...and the inline hint is re-texted with them (the dock's sentence is a key)",
          (dock.retranslate(), app.processEvents(),
           dpanel.hint_label.text() == i18n.t("terminal.cmdlib.map_is_here")
           and dpanel.hint_label.isHidden() is True)[-1],
          repr(dpanel.hint_label.text()))
    dpanel.set_head(CL.HEAD_COMMANDS)
    app.processEvents()
    panel.set_head(CL.HEAD_SERVERS)
    app.processEvents()
    check("§6 the servers placeholder follows the language too",
          panel.search.placeholderText() == i18n.t("terminal.cmdlib.servers_search"),
          panel.search.placeholderText())
finally:
    i18n.set_language(_saved_lang)
win.retranslate()
panel.set_head(CL.HEAD_COMMANDS)
app.processEvents()

win.refresh_theme()
app.processEvents()
check("§6 `refresh_theme()` walks the panel without raising and re-applies the head style",
      panel.head_commands_btn.styleSheet().strip() == TQ.style("panel.head").strip()
      and panel.hint_label.styleSheet() == f"color: {CL.theme.TEXT_MUTED};",
      repr(panel.head_commands_btn.styleSheet()[:40]))

_langs = load_i18n_langs(ROOT)
check_i18n_parity(_langs)
check_i18n_format(_langs)
_new_keys = ["terminal.cmdlib.head_servers", "terminal.cmdlib.servers_search",
             "terminal.cmdlib.servers_empty", "terminal.cmdlib.servers_no_matches",
             "terminal.cmdlib.open_map", "terminal.cmdlib.open_map_tooltip",
             "terminal.cmdlib.profiles", "terminal.cmdlib.profiles_tooltip",
             "terminal.cmdlib.map_is_here", "terminal.cmdlib.no_map"]
check("§6 the TEN keys of the release are non-empty in every language",
      all(_langs[c].get(k) for c in _langs for k in _new_keys)
      # this release's TEN, read off the LIVE pin: the 1094 baseline + v1.11's ten + the later
      # releases' own additions (v1.12's TEN, v1.12.3's THREE, v1.12.4.1's ONE, v1.13's FOUR,
      # v1.13.1's THREE, the fifth read's TWO, v1.13.2's EIGHT, v1.13.3's NINE, v1.13.4's
      # EIGHTEEN, v1.13.5's FOUR, v1.13.6's THIRTEEN (the search's eleven, the trash's two),
      # v1.13.6.2's ONE and v1.14.1's TWELVE: the reader's verbs).
      and len(_new_keys) == EXPECTED_I18N_KEYS - 1094 - 10 - 3 - 1 - 4 - 3 - 2 - 8 - 9 - 18 - 4 - 13 - 1 - 1 - 12 - 3,
      str({c: len(_langs[c]) for c in sorted(_langs)}))


# ════════════════════════════════════════════════════════════════════════════
print("== §7 the close path — the question precedes the teardown ==")
# ════════════════════════════════════════════════════════════════════════════

_answer = {"value": QMessageBox.Cancel}
_orig_question = QMessageBox.question
QMessageBox.question = staticmethod(lambda *a, **k: _answer["value"])
mw.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
_session_win = None
try:
    _session_win = mw._spawn_terminal_window(alpha, password="pw")
    app.processEvents()
    page = _session_win.page
    mw._dirty = True

    _ev = QCloseEvent()
    mw.closeEvent(_ev)
    app.processEvents()
    check("§7 `Cancel` on the unsaved-changes question leaves the window WHOLE",
          _ev.isAccepted() is False and mw._dirty is True
          and page._shut_down is False and page.terminal_thread.stop_calls == 0
          and page in mw._terminal_windows,
          f"accepted={_ev.isAccepted()} shut={page._shut_down} "
          f"stops={page.terminal_thread.stop_calls}")

    _answer["value"] = QMessageBox.Discard
    _ev2 = QCloseEvent()
    mw.closeEvent(_ev2)
    app.processEvents()
    check("§7 `Discard` closes the window AND tears every session down (the shipped deal)",
          _ev2.isAccepted() is True and page.terminal_thread.stop_calls >= 1
          and page not in mw._terminal_windows,
          f"accepted={_ev2.isAccepted()} stops={page.terminal_thread.stop_calls}")

    # `Save` picks the path IN its dialog — the memory is written AFTER the answer, never before.
    clear_cfg()
    _target = os.path.join(WORK, "v111_first_save.json")
    mw._dirty = True
    mw._project_file = None
    _orig_save = mw._save_project
    mw._save_project = lambda: (setattr(mw, "_project_file", _target),
                                setattr(mw, "_dirty", False), True)[2]
    _answer["value"] = QMessageBox.Save
    try:
        _ev3 = QCloseEvent()
        mw.closeEvent(_ev3)
        app.processEvents()
    finally:
        mw._save_project = _orig_save
    check("§7 the last project is recorded AFTER the answer, so a FIRST `Save` is not lost",
          _ev3.isAccepted() is True and mw._project_file == _target
          and last_project_path() == os.path.abspath(_target),
          f"accepted={_ev3.isAccepted()} path={last_project_path()!r}")

    mw._dirty = True
    _answer["value"] = QMessageBox.Cancel
    _ev4 = QCloseEvent()
    mw.closeEvent(_ev4)
    app.processEvents()
    check("§7 a CANCELLED close does not rewrite the memory (the window is not closing)",
          _ev4.isAccepted() is False
          and last_project_path() == os.path.abspath(_target),
          repr(last_project_path()))

    _answer["value"] = QMessageBox.Save
    _orig_save2 = mw._save_project
    mw._save_project = lambda: False          # a save that FAILED keeps the window alive
    try:
        _ev5 = QCloseEvent()
        mw.closeEvent(_ev5)
        app.processEvents()
    finally:
        mw._save_project = _orig_save2
    check("§7 a FAILED save still refuses the close (and writes no memory)",
          _ev5.isAccepted() is False
          and last_project_path() == os.path.abspath(_target),
          f"accepted={_ev5.isAccepted()}")
finally:
    QMessageBox.question = _orig_question
    mw._dirty = False

_main_src = _read("ui", "main_window.py")
_close_at = _main_src.index("def closeEvent")
_ask_at = _main_src.index("if self._has_unsaved_changes:", _close_at)
_shut_at = _main_src.index("self._shutdown_background_threads()", _close_at)
check("§7 the close path asks BEFORE it tears anything down (one documented order)",
      _ask_at < _shut_at < _main_src.index("event.accept()", _shut_at),
      f"ask={_ask_at} shutdown={_shut_at}")
check("§7 ...and `_remember_last_project()` follows the question, not the geometry block",
      _main_src.index("self._remember_last_project()", _close_at) > _ask_at
      and _main_src.index("self._remember_last_project()", _close_at) < _shut_at)
check("§7 the theme fallback of the startup path logs through `get_logger` (no bare `print`)",
      "print(f\"[theme]" not in _main_src
      and "def _bootstrap_log()" in _main_src
      and "from modules.logger import get_logger" in _main_src
      and 'The saved theme was not applied' in _main_src
      and "flush=True" not in _main_src.split("def _bootstrap_log()")[1][:200])


# ════════════════════════════════════════════════════════════════════════════
print("== §8 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

for _w in list(_windows):
    try:
        _w.close()
    except RuntimeError:
        pass
_windows.clear()
dock.close()
dock.deleteLater()
app.processEvents()
if os.path.isfile(os.path.join(WORK, "v111_first_save.json")):
    os.remove(os.path.join(WORK, "v111_first_save.json"))

check_release_state(ROOT)
check("§8 the pin names this line's release or a later one (the rc slots ride on the same code)",
      releases_at_least(EXPECTED_APP_VERSION, "1.11"), EXPECTED_APP_VERSION)
check("§8 the schema did NOT move (no project format change) and no new dependency arrived",
      'VERSION_FORMAT = "0.9"' in _read("version.py")
      and "pyte" in _read("requirements.txt")
      # pyte is VENDORED, so no line of the file may DECLARE it (a trailing comment is not a dependency).
      and not any(ln.split("#", 1)[0].strip().lower().startswith("pyte")
                  for ln in _read("requirements.txt").splitlines()))
check("§8 the topical file is listed by the suite map (tests/INDEX.md regenerated)",
      "test_terminal_panel.py" in _read("tests", "INDEX.md"))

finish()
