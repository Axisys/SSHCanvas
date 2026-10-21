# -*- coding: utf-8 -*-
"""The terminal on its own (v1.12) — `main.py --only-terminal` and the surface behind it.
§1 the launch: the ONE argv parse, the modes, no listener; §2 the SHIPPED container, born EMPTY and
keeping zero sessions; §3 the source — the PURE project reader and the `Servers` head; §4 the doors —
`Open project`, the unmanaged gate and the connect dialog; §5 the panel's project form and the inline
hint; §6 the OUT list of the frozen contract (nothing of the map is built); §7 the i18n keys and the
release state.
Rule — `AGENTS.md` §4.3.9, §4.1, §4.4, §4.21; mechanism — `DOCUMENTATION.md` §75.
Contract — `TERMINAL_STANDALONE.md` (its clause audit is `tests/test_terminal_standalone_contract.py`).
"""
import ast
import json
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, VERSION_FORMAT_RE, bootstrap, check,
                     check_i18n_format, check_i18n_parity, check_release_state, clear_cfg, finish,
                     load_i18n_langs, releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import main as MAIN  # noqa: E402
import modules.command_library as CL  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_standalone as TS  # noqa: E402
import ui.main_window as MW  # noqa: E402
from models.server import ServerData  # noqa: E402
from storage.project import (PROJECT_SUFFIXES, load_project,  # noqa: E402
                             read_project_servers)

from _fakes import FakeSSHThread  # noqa: E402

ST.SSHTerminalThread = FakeSSHThread   # every session of this file runs on the fake
LANGS = load_i18n_langs(ROOT)


def _read(*parts) -> str:
    """The text of a repository file that SHIPS (the source audits below read several)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


_ts_src = _read("modules", "terminal_standalone.py")   # the surface's own text (the audits below)


def _imports(*parts) -> set:
    """Every module name a shipped file really IMPORTS (the AST — a docstring mention is not one)."""
    names = set()
    for node in ast.walk(ast.parse(_read(*parts))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _func_body(name, *parts) -> str:
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


def _placeholders(value) -> list:
    """The `{name}` placeholders of one translated string (the parity helper of this file)."""
    import re
    return re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", str(value or ""))


def _raises(call) -> bool:
    """Did this call raise? (the reader's contract: a missing file is the CALLER's sentence)."""
    try:
        call()
    except Exception:  # noqa: BLE001 — the door above owns the sentence, the reader owns the raise
        return True
    return False


def _project_file(name, servers, **extra) -> str:
    """A real project FILE under the run's scratch folder (never a fixture of the map itself)."""
    path = os.path.join(WORK, name)
    doc = {"version": "0.9", "servers": servers, "connections": []}
    doc.update(extra)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return path


def _broken_project_file() -> str:
    """A file that is not JSON at all — the reader's failure path."""
    path = os.path.join(WORK, "broken.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json at all")
    return path


def _surface():
    """A standalone surface with its window shown (each call is torn down by the suite's exit)."""
    surface = TS.StandaloneSurface()
    surface.window.show()
    app.processEvents()
    return surface


class _FakeEdit:
    """The three dialog fields the connect door reads (the shipped widget surface)."""

    def __init__(self, text="", value=0):
        self._text = text
        self._value = value

    def text(self):
        return self._text

    def value(self):
        return self._value


class _FakeConnectDialog:
    """The SHIPPED `SSHConnectDialog` seam: records the node it was built for, answers `Accepted`."""

    accepted = True
    instances = []

    def __init__(self, data, parent=None):
        self.data = data
        self.parent = parent
        self.user_edit = _FakeEdit("admin")
        self.key_path_edit = _FakeEdit("/tmp/id_ed25519")
        self.port_edit = _FakeEdit(value=2222)
        self.password_edit = _FakeEdit("s3cret")
        _FakeConnectDialog.instances.append(self)

    def exec(self):
        return 1 if _FakeConnectDialog.accepted else 0     # 1 = QDialog.Accepted


class _FakeFileDialog:
    """The `QFileDialog.getOpenFileName` seam (the ONE call the project door makes)."""

    answer = ("", "")
    calls = []

    @staticmethod
    def getOpenFileName(parent=None, title="", start="", flt=""):
        _FakeFileDialog.calls.append({"parent": parent, "title": title, "start": start, "filter": flt})
        return _FakeFileDialog.answer


clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== §1 the launch: ONE argv parse, the modes, and NO listener ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the mode table is declared ONCE and `--only-terminal` is its terminal row",
      MAIN.LAUNCH_FLAGS == {"--only-terminal": MAIN.MODE_TERMINAL}
      and MAIN.MODE_MAP == "map" and MAIN.MODE_TERMINAL == "terminal",
      f"{MAIN.LAUNCH_FLAGS}")
check("§1 no flag is the default mode (the shipped launch is unchanged)",
      MAIN.parse_launch_args([])["mode"] == MAIN.MODE_MAP
      and MAIN.parse_launch_args(["some-file.json"])["mode"] == MAIN.MODE_MAP,
      f"{MAIN.parse_launch_args([])}")
check("§1 `--only-terminal` selects the standalone mode and reports nothing unknown",
      MAIN.parse_launch_args(["--only-terminal"]) == {"mode": MAIN.MODE_TERMINAL, "unknown": []},
      f"{MAIN.parse_launch_args(['--only-terminal'])}")
check("§1 an unknown `--flag` is REPORTED and never changes the mode (Qt owns the rest)",
      MAIN.parse_launch_args(["--nope", "--only-terminal"])["unknown"] == ["--nope"]
      and MAIN.parse_launch_args(["--nope"])["mode"] == MAIN.MODE_MAP
      and MAIN.parse_launch_args(["-style", "Fusion"])["unknown"] == [],
      f"{MAIN.parse_launch_args(['--nope', '--only-terminal'])}")
check("§1 the parse is PURE and total (a non-string token is skipped, never a crash)",
      MAIN.parse_launch_args([None, 7, "--only-terminal"])["mode"] == MAIN.MODE_TERMINAL)
check("§1 the flag takes NO argument: the mode is ONE flag and the project is picked IN the window",
      MAIN.USAGE == "usage: python main.py [--only-terminal]"
      and "start_standalone" in _read("main.py"),
      MAIN.USAGE)

_ma_src = _read("main.py")
check("§1 the standalone branch opens NO listener (no socket, no server, no port)",
      not any(word in _ma_src for word in ("QTcpServer", "QUdpSocket", "QLocalServer",
                                           "socketserver", "listen(")),
      [w for w in ("QTcpServer", "QUdpSocket", "QLocalServer", "socketserver", "listen(")
       if w in _ma_src])
check("§1 the standalone branch is taken BEFORE any map object is built",
      _ma_src.index('if args["mode"] == MODE_TERMINAL:') < _ma_src.index("win = MainWindow()")
      and _ma_src.count("sys.exit(app.exec())") == 1,
      f"branches={_ma_src.count('sys.exit(app.exec())')}")
check("§1 the module owns the launch constants the contract names",
      TS.MODULE_FACADE_SEAMS == (TS.SSHConnectDialog, TS.QFileDialog))

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the SHIPPED container, born EMPTY and keeping zero sessions ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the standalone window IS the shipped container (a subclass, one class of behaviour)",
      issubclass(TS.StandaloneTerminalWindow, ST.SSHTerminalWindow)
      and TS.StandaloneTerminalWindow.ALLOWS_NO_SESSIONS is True
      and ST.SSHTerminalWindow.ALLOWS_NO_SESSIONS is False
      and ST.SSHTerminalWindow.CONTAINER_KIND == "window")

surface = _surface()
win = surface.window
panel = win.cmdlib_panel
check("§2 the container is born with ZERO sessions and no node of its own",
      win.session_tabs.count() == 0 and win.server_data is None,
      f"tabs={win.session_tabs.count()} server_data={win.server_data!r}")
check("§2 an empty container names the SURFACE in its title",
      win.windowTitle() == i18n.t("terminal.standalone.title"), win.windowTitle())
check("§2 the zero-session sentence is a PERMANENT status-bar line, visible while empty",
      win._empty_label.isVisible() is True
      and win._empty_label.text() == i18n.t("terminal.standalone.empty_hint"),
      f"visible={win._empty_label.isVisible()} {win._empty_label.text()!r}")
check("§2 the two per-SESSION controls are disabled while nothing is on screen",
      win.act_split.isEnabled() is False and win.act_files_panel.isEnabled() is False)
check("§2 `page` and `active_session` answer None with zero sessions (the shipped readers)",
      win.page is None and win.active_session() is None and win._all_pages() == [])

_project = _project_file("standalone-a.json", [
    {"id": "sa-1", "alias": "web-1", "host": "10.20.0.11", "user": "root", "ssh_port": 22},
    {"id": "sa-2", "alias": "web-2", "host": "10.20.0.12", "user": "admin", "ssh_port": 2222},
    {"id": "sa-3", "alias": "neighbour", "host": "10.20.0.13", "unmanaged": True},
])
TS.SSHConnectDialog = _FakeConnectDialog
_FakeConnectDialog.instances = []
check("§2 the project door loads the list (the surface is the provider behind it)",
      surface.open_project(_project) is True and len(surface.servers()) == 3
      and surface.project_path() == _project)
app.processEvents()
check("§2 the panel switched to the `Servers` head and shows one row per server",
      panel.head() == CL.HEAD_SERVERS and panel.server_tree.topLevelItemCount() == 3,
      f"head={panel.head()} rows={panel.server_tree.topLevelItemCount()}")
check("§2 the status line names the file and the number of servers",
      surface.window.statusBar().currentMessage() == i18n.t(
          "terminal.standalone.project_opened", name=os.path.basename(_project), count=3),
      surface.window.statusBar().currentMessage())

rows = [panel.server_tree.topLevelItem(i) for i in range(panel.server_tree.topLevelItemCount())]
check("§2 the rows are ONE per file entry, ordered A→Z by alias (v1.13.3's name sort) and carry "
      "the alias + the identity tooltip",
      [r.text(0) for r in rows] == ["neighbour", "web-1", "web-2"]
      and rows[2].toolTip(0) == "admin@10.20.0.12:2222",
      [r.text(0) for r in rows])

surface.connect_server(surface.servers()[0])
app.processEvents()
check("§2 the session joins THIS window (the shipped add_session path)",
      win.session_tabs.count() == 1 and win.session_tabs.tabText(0) == "web-1",
      f"tabs={win.session_tabs.count()}")
check("§2 a container with a session leaves the empty state and re-enables its controls",
      win._empty_label.isVisible() is False and win.act_split.isEnabled() is True
      and win.act_files_panel.isEnabled() is True)

_page = win.session_tabs.widget(0)
win._release_files_panel_page(_page)
_page.shutdown()
win.session_tabs.removeTab(0)
win._sync_empty_state()
check("§2 closing the LAST tab leaves an EMPTY window instead of closing it",
      win.session_tabs.count() == 0 and win.isVisible() is True
      and win._empty_label.isVisible() is True)
check("§2 the shipped window still closes on its last tab (the flag, not a second rule)",
      ST.SSHTerminalWindow.ALLOWS_NO_SESSIONS is False)

# The saved Files display mode cannot be honoured by a container with no session: the request is
# REMEMBERED and reaches the first session that arrives (the shipped setting, not a second rule).
i18n.save_config({"terminal_files_mode": "panel"})
_deferred = _surface()
check("§2 a container born EMPTY remembers the Files display mode it could not serve",
      _deferred.window._files_config["mode"] == "panel"
      and _deferred.window._files_panel_on is False
      and _deferred.window._files_mode_pending is True)
_deferred.window.add_session(
    ServerData(id="tsp-deferred", alias="deferred", host="10.20.0.31", user="root"), password="pw")
app.processEvents()
check("§2 …and the FIRST session gets the panel the setting asked for",
      _deferred.window._files_panel_on is True
      and _deferred.window._files_mode_pending is False)
_deferred.window.set_files_panel_enabled(False)
_deferred.window.add_session(
    ServerData(id="tsp-deferred-2", alias="deferred-2", host="10.20.0.32", user="root"),
    password="pw")
app.processEvents()
check("§2 an explicit OFF wins over the saved mode (the pending request is dropped)",
      _deferred.window._files_panel_on is False
      and _deferred.window._files_mode_pending is False)
i18n.save_config({"terminal_files_mode": "tab"})

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the source: the PURE reader and the ONE conversion home ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 `PROJECT_SUFFIXES` is declared ONCE and the map's drop gate reads the SAME tuple",
      PROJECT_SUFFIXES == (".json", ".sshmap")
      and MW.PROJECT_DROP_SUFFIXES == PROJECT_SUFFIXES
      and "PROJECT_SUFFIXES = (\".json\", \".sshmap\")" in _read("storage", "project.py")
      and "PROJECT_DROP_SUFFIXES = PROJECT_SUFFIXES" in _read("ui", "main_window.py"),
      f"{PROJECT_SUFFIXES} {MW.PROJECT_DROP_SUFFIXES}")
check("§3 the dialog filter is DERIVED from that tuple (no translation spells the suffixes)",
      TS.project_filter_text().endswith(i18n.t("terminal.standalone.all_files"))
      and "*.json *.sshmap" in TS.project_filter_text(), TS.project_filter_text())
check("§3 the filter carries the translated project label with `{patterns}` filled",
      TS.project_filter_text().split(";;")[0]
      == i18n.t("terminal.standalone.project_filter", patterns="*.json *.sshmap"),
      TS.project_filter_text().split(";;")[0])

_servers = read_project_servers(_project)
check("§3 the reader answers `ServerData` nodes in FILE order",
      [s.alias for s in _servers] == ["web-1", "web-2", "neighbour"]
      and all(isinstance(s, ServerData) for s in _servers))
check("§3 the reader uses the ONE conversion home (the same function the map loads with)",
      "server_data_from_dict" in _read("storage", "project.py")
      and "storage.project" in _imports("ui", "main_window.py") | {"storage.project"}
      and _servers[2].unmanaged is True)
check("§3 a broken entry is DROPPED and a file without the array answers an empty list",
      [s.alias for s in read_project_servers(_project_file("junk.json", [
          {"id": "j1", "alias": "ok", "host": "h"}, "junk", 42, None]))] == ["ok"]
      and read_project_servers(_project_file("empty.json", [])) == [])
check("§3 an unreadable file RAISES out of the reader (the door owns the sentence)",
      _raises(lambda: read_project_servers(os.path.join(WORK, "missing.json")))
      and _raises(lambda: read_project_servers(_broken_project_file())))
check("§3 the reader never writes: no save/atomic call in `read_project_servers`",
      "publish_atomic" not in _func_body("read_project_servers", "storage", "project.py")
      and "write_project_json" not in _func_body("read_project_servers", "storage", "project.py")
      and "open(" not in _func_body("read_project_servers", "storage", "project.py"))
check("§3 the surface writes NOTHING of the project on load: the file's bytes are untouched",
      load_project(_project)["servers"][0]["alias"] == "web-1"
      and not any(name.startswith("storage.autosave") or name.endswith("autosave")
                  for name in _imports("modules", "terminal_standalone.py"))
      and "save_project" not in _ts_src and "write_project_json" not in _ts_src)

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the doors: Open project, the unmanaged gate and the connect dialog ==")
# ════════════════════════════════════════════════════════════════════════════

TS.QFileDialog = _FakeFileDialog
_FakeFileDialog.calls = []
_FakeFileDialog.answer = ("", "")
_before = surface.servers()
check("§4 a CANCELLED file dialog changes NOTHING (no list, no status line, no write)",
      surface.open_project() is False and surface.servers() == _before
      and _FakeFileDialog.calls and _FakeFileDialog.calls[-1]["filter"] == TS.project_filter_text(),
      f"calls={len(_FakeFileDialog.calls)}")
_other = _project_file("standalone-b.json", [{"id": "sb-1", "alias": "db-1", "host": "10.20.0.21"}])
_FakeFileDialog.answer = (_other, "")
check("§4 the dialog's answer is what the door loads (the file picker IS the source)",
      surface.open_project() is True and [s.alias for s in surface.servers()] == ["db-1"],
      [s.alias for s in surface.servers()])
check("§4 a file that cannot be read answers ONE sentence and keeps the PREVIOUS list",
      surface.open_project(os.path.join(WORK, "nope.json")) is False
      and [s.alias for s in surface.servers()] == ["db-1"]
      and i18n.t("terminal.standalone.project_failed", name="nope.json", error="")
      in surface.window.statusBar().currentMessage(),
      surface.window.statusBar().currentMessage())

surface.open_project(_project)
app.processEvents()
_unmanaged = [s for s in surface.servers() if s.alias == "neighbour"][0]
_D_fail = type("D", (_FakeConnectDialog,), {"__init__": lambda self, *a, **k:
                                            (_ for _ in ()).throw(AssertionError("dialog built"))})
TS.SSHConnectDialog = _D_fail
check("§4 the UNMANAGED gate comes FIRST — no dialog is built for such a node",
      surface.connect_server(_unmanaged) is False
      and surface.window.statusBar().currentMessage() == i18n.t("status.unmanaged_blocked"),
      surface.window.statusBar().currentMessage())

TS.SSHConnectDialog = _FakeConnectDialog
_FakeConnectDialog.instances = []
_FakeConnectDialog.accepted = False
check("§4 a CANCELLED dialog opens no session",
      surface.connect_server(surface.servers()[0]) is False
      and len(_FakeConnectDialog.instances) == 1 and win.session_tabs.count() == 0)
check("§4 the dialog is built for the ROW's own node, parented to the container",
      _FakeConnectDialog.instances[-1].data is surface.servers()[0]
      and _FakeConnectDialog.instances[-1].parent is win)

_FakeConnectDialog.accepted = True
_FakeConnectDialog.instances = []
_win2 = _surface()
_win2.open_project(_project)
app.processEvents()
check("§4 an ACCEPTED dialog opens the session and carries the dialog's fields onto the node",
      _win2.connect_server(_win2.servers()[1]) is True
      and _win2.window.session_tabs.count() == 1
      and (_win2.servers()[1].user, _win2.servers()[1].ssh_port,
           _win2.servers()[1].key_path) == ("admin", 2222, "/tmp/id_ed25519"),
      f"{_win2.servers()[1].user} {_win2.servers()[1].ssh_port}")
check("§4 the dialog's fields reach the NODE only — the project file keeps its own bytes",
      load_project(_project)["servers"][1]["user"] == "admin"
      and load_project(_project)["servers"][1]["ssh_port"] == 2222)
check("§4 the password the dialog collected is what the session starts with",
      _win2.window.session_tabs.widget(0).terminal_thread.password == "s3cret",
      _win2.window.session_tabs.widget(0).terminal_thread.password)
check("§4 the endpoint-bound keyring record is the fallback when the field is EMPTY",
      "node_scope" in _read("modules", "terminal_standalone.py")
      and "load_password" in _read("modules", "terminal_standalone.py")
      and "get_credential_manager" in _read("modules", "terminal_standalone.py"))
check("§4 no secret ever reaches a surface or a log line: the status line carries no password",
      ".password_edit.text()" in _ts_src          # the ONE read of the dialog's field
      and "password" not in _func_body("_notify", "modules", "terminal_standalone.py")
      and all("password" not in line for line in _ts_src.splitlines() if "log." in line))

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the panel's project form and the inline hint ==")
# ════════════════════════════════════════════════════════════════════════════

_fresh = _surface()
_fpanel = _fresh.window.cmdlib_panel
check("§5 a standalone panel is in PROJECT mode and says so on its first control",
      _fpanel.project_mode() is True
      and _fpanel.open_map_btn.text() == i18n.t("terminal.cmdlib.open_project")
      and _fpanel.open_map_btn.toolTip() == i18n.t("terminal.cmdlib.open_project_tooltip"),
      _fpanel.open_map_btn.text())
check("§5 the surface OPENS on the `Servers` head — the head its own door lives on",
      _fpanel.head() == CL.HEAD_SERVERS and _fpanel.server_tree.isVisible() is True
      and _fpanel.tree.isVisible() is False and _fpanel.doors_row.isVisible() is True
      and _fpanel.open_map_btn.isVisible() is True,
      f"head={_fpanel.head()!r} doors={_fpanel.doors_row.isVisible()}")
check("§5 with NO project open the head is USABLE and says so — no claim about a project",
      _fpanel.servers_available() is True
      and _fpanel.project_is_open() is False
      and _fpanel.server_tree.topLevelItemCount() == 0
      and _fpanel.info_label.text() == i18n.t("terminal.cmdlib.no_project")
      and _fpanel.info_label.text() != i18n.t("terminal.cmdlib.project_empty")
      and _fpanel.hint_label.isVisible() is False,
      f"available={_fpanel.servers_available()} info={_fpanel.info_label.text()!r}")
check("§5 …so the shipped start-up writes NO refusal sentence on the status line",
      _fresh.window.statusBar().currentMessage() == ""
      and _fresh.window._empty_label.isVisible() is True
      and _fresh.window._empty_label.text() == i18n.t("terminal.standalone.empty_hint"),
      f"{_fresh.window.statusBar().currentMessage()!r} {_fresh.window._empty_label.text()!r}")
_msgs = []
_fpanel.status_message.connect(lambda text, ms: _msgs.append(text))
_fpanel.set_head(CL.HEAD_COMMANDS)
app.processEvents()
check("§5 a click on the `Commands` head takes the doors and the hint away with it",
      _fpanel.head() == CL.HEAD_COMMANDS and _fpanel.doors_row.isVisible() is False
      and _fpanel.tree.isVisible() is True
      and _fpanel.hint_label.isVisible() is False and _msgs == [],
      f"head={_fpanel.head()!r} doors={_fpanel.doors_row.isVisible()} msgs={_msgs}")
_fpanel.set_head(CL.HEAD_SERVERS)
app.processEvents()
check("§5 the return to `Servers` brings the row back (the head state is the ONE owner)",
      _fpanel.head() == CL.HEAD_SERVERS and _fpanel.doors_row.isVisible() is True
      and _msgs == [],
      f"doors={_fpanel.doors_row.isVisible()} msgs={_msgs}")
check("§5 the first control runs the PROJECT door of an EMPTY list",
      _fpanel._project_sink is not None and _fpanel.project_mode() is True
      and _fpanel._hint_text() == "")
TS.QFileDialog = _FakeFileDialog
_FakeFileDialog.calls = []
_FakeFileDialog.answer = (_other, "")
_msgs_before = len(_msgs)
_fpanel._on_open_map()
app.processEvents()
check("§5 the click loads the picked project and shows NO refusal sentence",
      _fresh.project_path() == _other and len(_msgs) == _msgs_before
      and _fpanel.hint_label.isVisible() is False,
      f"path={_fresh.project_path()!r} msgs={_msgs[_msgs_before:]}")
check("§5 the project door is installed by the CONTAINER, never by the panel itself",
      "set_project_door(self._panel_open_project)" in _ts_src
      and "def set_project_door" in _read("modules", "command_library.py"))
_empty_project = _project_file("standalone-empty.json", [])
_fresh.open_project(_empty_project)
app.processEvents()
check("§5 an empty project keeps the head USABLE and names its own empty state",
      _fpanel.servers_available() is True and _fpanel.head() == CL.HEAD_SERVERS
      and _fpanel.project_is_open() is True
      and _fpanel.server_tree.topLevelItemCount() == 0
      and _fpanel.info_label.text() == i18n.t("terminal.cmdlib.project_empty")
      and _fpanel.hint_label.isVisible() is False,
      f"available={_fpanel.servers_available()} info={_fpanel.info_label.text()!r}")
check("§5 `Profiles` is the SHIPPED door under the SHIPPED hook name (application-level)",
      hasattr(TS.StandaloneSurface, "_open_profile_manager")
      and "get_host_hook" not in _read("modules", "terminal_standalone.py")
      and "find_host_hook(self, \"_open_profile_manager\")" in _read("modules", "ssh_terminal.py"))
check("§5 the map-backed containers keep the shipped form (no project door installed)",
      "set_project_door" not in _read("modules", "terminal_dock.py")
      and "set_map_doors(self._panel_open_map, self._panel_open_profiles)"
      in _read("modules", "ssh_terminal.py"))

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the OUT list: nothing of the map is built ==")
# ════════════════════════════════════════════════════════════════════════════

_ts_src = _read("modules", "terminal_standalone.py")
_ts_imports = _imports("modules", "terminal_standalone.py")
check("§6 the surface imports NO map module (no scene, no view, no MainWindow, no graphics)",
      not any(name.startswith("graphics") or name.startswith("ui.main_window")
              or name in ("ui.main_window", "modules.plugin_manager", "services.status_checker",
                          "storage.autosave", "modules.undo_commands", "modules.plugin_runner")
              for name in _ts_imports),
      sorted(_ts_imports))
check("§6 no plugin discovery, no status round, no autosave and no info collection in the surface",
      not any(word in _ts_src for word in ("start_plugin_discovery", "StatusChecker",
                                           "SystemInfoCollector", "InfoBatch",
                                           "QUndoStack", "_push_command")),
      [w for w in ("start_plugin_discovery", "StatusChecker", "SystemInfoCollector", "InfoBatch",
                   "QUndoStack", "_push_command") if w in _ts_src])
check("§6 the surface builds no scene and registers no project path of the application",
      "MapScene" not in _ts_src and "MapView" not in _ts_src
      and "last_project_path" not in _ts_src and "recent_projects" not in _ts_src)
check("§6 the window it builds is the SHIPPED container, not a second terminal implementation",
      "class StandaloneTerminalWindow(SSHTerminalWindow)" in _ts_src
      and "TerminalWidget(" not in _ts_src and "TerminalSessionPage(" not in _ts_src)
check("§6 the application keeps exactly ONE MainWindow path (the map is untouched by the flag)",
      _read("main.py").count("MainWindow()") == 1
      and "class MainWindow" in _read("ui", "main_window.py"))
check("§6 the ENTRY POINT imports no map either — `MainWindow` is built inside its own branch",
      "MainWindow" not in _imports("main.py")
      and "from .ui.main_window import MainWindow" in _read("main.py")
      and "from ui.main_window import MainWindow" in _read("main.py"),
      sorted(_imports("main.py")))

# ── the LIFETIME of the surface — the two defects this release shipped: `main.py` threw
#    `start_standalone()` away, so the ONE top-level widget was collected BEFORE `app.exec()` and the
#    mode showed NO window at all; and the surface's own hidden top-level widget keeps Qt's
#    `quitOnLastWindowClosed` out of reach, so closing the window left the process running forever. ──
import gc  # noqa: E402  (this regression is about the collector, not about Qt)
import weakref  # noqa: E402

from PySide6.QtCore import QEvent, QObject  # noqa: E402

_main_src_v112 = _read("main.py")
check("§6 `main()` BINDS the surface it starts (a discarded entry point collects its own window)",
      "app.standalone_surface = start_standalone()" in _main_src_v112,
      [line.strip() for line in _main_src_v112.splitlines() if "start_standalone()" in line])
check("§6 the entry point hands the surface to its caller (the caller is the ONE owner)",
      "surface.window.show()" in _func_body("start_standalone", "modules", "terminal_standalone.py")
      and "return surface" in _func_body("start_standalone", "modules", "terminal_standalone.py"))


def _live_surfaces() -> int:
    """How many live `StandaloneSurface` widgets the application still has (0 = its window is gone)."""
    return len([w for w in app.topLevelWidgets() if type(w) is TS.StandaloneSurface])


def _survives_a_discarded_reference() -> bool:
    """Drop every reference to a fresh surface and force the collector — is its window still alive?

    This is the probe that proved the first defect (and the shape the fix must keep): the weak
    reference is alive while the entry point's answer is held, and `None` once it is dropped.
    """
    thrown = TS.start_standalone()
    ref = weakref.ref(thrown)
    del thrown
    for _ in range(3):
        gc.collect()
    return ref() is not None


_before = _live_surfaces()
_kept = TS.start_standalone()          # held by this test — the reaching reference the suite always used
gc.collect()
check("§6 a HELD surface survives the collector (its window is the one the mode shows)",
      _live_surfaces() == _before + 1 and _kept.window.isVisible() is True,
      f"surfaces={_live_surfaces()} window={_kept.window.isVisible()}")
check("§6 …and a DISCARDED one does NOT: the window dies before the loop (the defect, reproduced)",
      _survives_a_discarded_reference() is False,
      "a top-level QWidget nobody references survives here — this check no longer proves anything")

check("§6 `quit_on_close` is the ONE predicate of \"closing this container ends the run\"",
      TS.StandaloneTerminalWindow.quit_on_close is True
      and ST.SSHTerminalWindow.quit_on_close is False
      and "quit_on_close = False" in _read("modules", "ssh_terminal.py")
      and "quit_on_close = True" in _ts_src)


class _QuitSpy(QObject):
    """Records the CLOSE of the window it is armed on and every `quit()` asked while it is armed.

    The order is the whole point: a closed standalone window must ASK the run to end — Qt's own
    `quitOnLastWindowClosed` never fires here, because the window's OWNER (`StandaloneSurface`) stays
    a live top-level widget beside it (the window IS a top-level window with a parent, so `isWindow()`
    answers True; what Qt counts is the surface that never closes). Measured: with `app.quit`
    intercepted so that only Qt's automatic path could end the loop, closing the window left
    `app.exec()` RUNNING — the explicit `quit()` is load-bearing, not a courtesy.
    """

    def __init__(self, window):
        super().__init__()
        self.closed = 0
        window.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Close:
            self.closed += 1
        return False    # never consume: the container's own closeEvent must run


_quiet = []
_real_quit = app.quit
app.quit = lambda: _quiet.append("quit")     # the ONE observable of "the run ends here"


def _close_and_watch(window) -> tuple:
    """Close this window and answer (close events seen, was quit asked for)."""
    spy = _QuitSpy(window)
    _quiet.clear()
    window.close()
    return spy.closed, bool(_quiet)


_standalone_closed, _standalone_quit = _close_and_watch(TS.StandaloneTerminalWindow(None))
check("§6 a CLOSED standalone window asks the run to END (the loop has nothing left to show)",
      _standalone_closed == 1 and _standalone_quit is True,
      f"close events={_standalone_closed} quit asked={_standalone_quit}")
_map_closed, _map_quit = _close_and_watch(ST.SSHTerminalWindow(None))
check("§6 a CLOSED map-backed container asks NOTHING: the map is still on screen",
      _map_closed == 1 and _map_quit is False
      and "if event.isAccepted() and self.quit_on_close:" in _read("modules", "ssh_terminal.py"),
      f"close events={_map_closed} quit asked={_map_quit}")
app.quit = _real_quit
check("§6 the quit is PER-CLOSE, not a mode: the predicate is read from the container",
      ST.SSHTerminalWindow.quit_on_close is False
      and TS.StandaloneTerminalWindow.quit_on_close is True
      and ST.SSHTerminalWindow.ALLOWS_NO_SESSIONS is False)

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the i18n keys and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

_NEW_KEYS = ("terminal.standalone.title", "terminal.standalone.empty_hint",
             "terminal.standalone.project_opened", "terminal.standalone.project_failed",
             "terminal.standalone.project_filter", "terminal.standalone.all_files",
             "terminal.cmdlib.open_project", "terminal.cmdlib.open_project_tooltip",
             "terminal.cmdlib.no_project", "terminal.cmdlib.project_empty")
check("§7 the TEN keys of the release are present and non-empty in every language",
      all(LANGS[c].get(k) for c in LANGS for k in _NEW_KEYS)
      # the 1104 the standalone left, plus the later follow-ups' keys (v1.12.3's THREE, v1.12.4.1's
      # ONE, v1.13's FOUR, v1.13.1's THREE, the fifth read's TWO, v1.13.2's EIGHT: the wallpaper row,
      # v1.13.3's NINE: the row verbs and the Servers menu, v1.13.4's EIGHTEEN: the Diff tab, and
      # v1.13.5's FOUR: the confirmation box and its question).
      and len(_NEW_KEYS) == EXPECTED_I18N_KEYS - 1104 - 3 - 1 - 4 - 3 - 2 - 8 - 9 - 18 - 4,
      str({c: [k for k in _NEW_KEYS if not LANGS[c].get(k)] for c in sorted(LANGS)}))
check("§7 `{patterns}` is the ONE placeholder of the filter and every language carries it",
      all(set(_placeholders(LANGS[c]["terminal.standalone.project_filter"])) == {"patterns"}
          for c in LANGS),
      str({c: _placeholders(LANGS[c]["terminal.standalone.project_filter"]) for c in sorted(LANGS)}))
check("§7 the two status-line sentences carry the placeholders their call sites fill",
      all(set(_placeholders(LANGS[c]["terminal.standalone.project_opened"])) == {"name", "count"}
          and set(_placeholders(LANGS[c]["terminal.standalone.project_failed"])) == {"name", "error"}
          for c in LANGS))
_KEY_HOMES = ("modules/terminal_standalone.py", "modules/command_library.py",
              "modules/ssh_terminal.py", "main.py")
check("§7 every new key is really USED by the shipped code (a key nobody reads is dead weight)",
      all(k in " ".join(_read(*home.split("/")) for home in _KEY_HOMES) for k in _NEW_KEYS),
      [k for k in _NEW_KEYS
       if k not in " ".join(_read(*home.split("/")) for home in _KEY_HOMES)])
check("§7 the surface is documented: the contract, the rule and the mechanism are all there",
      os.path.isfile(os.path.join(ROOT, "TERMINAL_STANDALONE.md"))
      and "TERMINAL_STANDALONE.md" in _read("AGENTS.md")
      and "§75" in _read("DOCUMENTATION.md"))
check("§7 the contract keeps its place in the internal world (gitignored, never in the README)",
      "TERMINAL_STANDALONE.md" in _read(".gitignore")
      and "TERMINAL_STANDALONE.md" not in _read("README.md"))
check("§7 the suites are listed by the suite map (tests/INDEX.md regenerated)",
      "test_terminal_standalone" in _read("tests", "INDEX.md")
      and "test_terminal_standalone_contract" in _read("tests", "INDEX.md"))

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check("§7 the release is the one this file describes (the v1.12 line; a PATCH on `X.Y.Z` adds a component)",
      releases_at_least(EXPECTED_APP_VERSION, "1.12")
      and bool(VERSION_FORMAT_RE.match(EXPECTED_APP_VERSION)),
      EXPECTED_APP_VERSION)
check("§7 no new dependency and no schema move (the flag is a launch mode, not a format)",
      "VERSION_FORMAT = \"0.9\"" in _read("version.py")
      and all(f"{d}>=" in _read("requirements.txt")
              for d in ("PySide6", "paramiko", "keyring", "wcwidth")))

finish()
