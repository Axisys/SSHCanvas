# -*- coding: utf-8 -*-
"""The reader and the panel (v1.12.2.2) — the second hardening patch of the released `v1.12.2`.
§1 the profiles store refuses to overwrite a file it cannot parse (`N102`); §2 the project reader
regenerates a duplicate id (`N106`); §3 the `Servers` row key is its POSITION (`N106`); §4 the list
re-reads its provider and the door re-checks the node (`N105`); §5 a refused close keeps autosave
(`N107`); §6 the standalone names the project it does not have (`N108`) and `--only-terminal` imports
no map at the entry point (`N109`); §7 the corrected comments of `N110`; §8 the release state.
Rule — `AGENTS.md` §4.3.8, §4.3.9, §4.4.2; mechanism — `DOCUMENTATION.md` §3, §14e, §15, §75.
"""
import ast
import json
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least, translation_keys, window_func_body)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import main as MAIN  # noqa: E402
import models.profile as PROFILE  # noqa: E402
import modules.command_library as CL  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_standalone as TS  # noqa: E402
import ui.main_window as MW  # noqa: E402
from dialogs.profile_manager_dialog import ProfileEditDialog, ProfileManagerDialog  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.undo_commands import CmdAddRemoveNode  # noqa: E402
from storage.project import read_project_servers  # noqa: E402

from _fakes import FakeSSHThread  # noqa: E402

ST.SSHTerminalThread = FakeSSHThread   # every session of this file runs on the fake
LANGS = load_i18n_langs(ROOT)


def _read(*parts) -> str:
    """The text of a repository file that SHIPS (the audits below read several)."""
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


def _project_file(name, servers) -> str:
    """A real project FILE under the run's scratch folder (never a fixture of the map itself)."""
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"version": "0.9", "servers": servers, "connections": []}, fh)
    return path


class _Question:
    """The `QMessageBox.question` seam: one canned answer, every call recorded."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def install(self):
        self._orig = QMessageBox.question

        def _stub(parent, title, text, *args, **kwargs):
            self.calls.append((title, text))
            return self.answer
        QMessageBox.question = staticmethod(_stub)
        return self

    def restore(self):
        QMessageBox.question = self._orig


class _Warning:
    """The `QMessageBox.warning` seam: every box recorded (the profile dialogs' one visible answer)."""

    def __init__(self):
        self.calls = []

    def install(self):
        self._orig = QMessageBox.warning

        def _stub(parent, title, text, *args, **kwargs):
            self.calls.append((title, text))
            return QMessageBox.Ok
        QMessageBox.warning = staticmethod(_stub)
        return self

    def restore(self):
        QMessageBox.warning = self._orig


class _FileDialog:
    """The `QFileDialog.getOpenFileName` seam of the standalone's `Open project`."""

    calls = []
    answer = ("", "")

    @classmethod
    def getOpenFileName(cls, *args, **kwargs):
        cls.calls.append({"parent": args[0] if args else None,
                          "filter": args[3] if len(args) > 3 else kwargs.get("filter", "")})
        return cls.answer


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the profiles store: a file that cannot be parsed is never overwritten ==")
# ════════════════════════════════════════════════════════════════════════════

_prof_path = os.path.join(WORK, "sshmap_profiles.json")
PROFILE._profiles_path = lambda: _prof_path   # the store of this file only (never the user's)

check("§1 a missing file is its own state, not a failed read",
      PROFILE.read_store() == (PROFILE.STORE_MISSING, [], _prof_path, "")
      and PROFILE.load_profiles() == []
      and PROFILE.unreadable_profiles_error() is None,
      str(PROFILE.read_store()))

_one = PROFILE.add_profile(name="ONE", user="one")
_two = PROFILE.add_profile(name="TWO", user="two")
check("§1 a healthy store reads back and is the state `ok`",
      [p.name for p in PROFILE.load_profiles()] == ["ONE", "TWO"]
      and PROFILE.read_store()[0] == PROFILE.STORE_OK
      and PROFILE.unreadable_profiles_error() is None)

_healthy = open(_prof_path, encoding="utf-8").read()
with open(_prof_path, "w", encoding="utf-8") as fh:
    fh.write(_healthy[:20])          # a half-written file — exactly what a crash leaves
_state, _profiles, _path, _reason = PROFILE.read_store()
check("§1 a file that exists and cannot be parsed is the DECLARED `unreadable` state",
      _state == PROFILE.STORE_UNREADABLE and _profiles == [] and _path == _prof_path
      and "JSON" in _reason,
      f"{_state} {_reason!r}")
check("§1 …and reading it still answers the empty list a caller expects (with one log line)",
      PROFILE.load_profiles() == []
      and PROFILE.unreadable_profiles_error() is not None)

for _label, _call in (("add_profile", lambda: PROFILE.add_profile(name="NEW", user="n")),
                      ("save_profiles", lambda: PROFILE.save_profiles([_one]))):
    _raised = None
    try:
        _call()
    except PROFILE.ProfileStoreError as e:
        _raised = e
    check(f"§1 `{_label}()` REFUSES to overwrite it",
          isinstance(_raised, PROFILE.ProfileStoreError)
          and _raised.path == _prof_path and _prof_path in str(_raised),
          repr(_raised))

check("§1 an id the store cannot answer is a quiet no-op, never a write",
      PROFILE.update_profile(_one.id, "X", "x") is None
      and PROFILE.delete_profile(_one.id) is False)
_orig_load = PROFILE.load_profiles
PROFILE.load_profiles = lambda: [_two]     # an id still in memory while the FILE is broken
try:
    _refused = []
    for _label, _call in (("update_profile", lambda: PROFILE.update_profile(_two.id, "X", "x")),
                          ("delete_profile", lambda: PROFILE.delete_profile(_two.id))):
        try:
            _call()
            _refused.append((_label, None))
        except PROFILE.ProfileStoreError as e:
            _refused.append((_label, e))
finally:
    PROFILE.load_profiles = _orig_load
check("§1 a writer that FOUND its record still refuses at the publish (the last line of defence)",
      all(isinstance(e, PROFILE.ProfileStoreError) for _l, e in _refused)
      and "unreadable_profiles_error()" in _func_body("save_profiles", "models", "profile.py")
      and _func_body("save_profiles", "models", "profile.py").index("raise refusal")
      < _func_body("save_profiles", "models", "profile.py").index("publish_atomic"),
      str(_refused))

check("§1 the file keeps its bytes: the last surviving profiles are still on disk",
      open(_prof_path, encoding="utf-8").read() == _healthy[:20])

with open(_prof_path, "w", encoding="utf-8") as fh:
    fh.write(_healthy)
check("§1 the store is usable again the moment the file is repaired",
      [p.name for p in PROFILE.load_profiles()] == ["ONE", "TWO"]
      and PROFILE.add_profile(name="THREE", user="three").name == "THREE"
      and [p.name for p in PROFILE.load_profiles()] == ["ONE", "TWO", "THREE"])

# ── the visible half: the profile dialogs answer with the REAL path ──
_warn = _Warning().install()
try:
    _mgr = ProfileManagerDialog(None)
    _mgr.refresh_table()
    _edit = ProfileEditDialog(None, existing=None)
    _edit.name_edit.setText("BLOCKED")
    _edit.user_edit.setText("blocked")
    with open(_prof_path, "w", encoding="utf-8") as fh:
        fh.write("{ broken")
    _edit._on_ok()
    app.processEvents()
finally:
    _warn.restore()
check("§1 the edit form warns with the file's OWN path and stays open (nothing is lost)",
      len(_warn.calls) == 1 and _prof_path in _warn.calls[0][1]
      and _edit.result() != QDialog.DialogCode.Accepted,
      str(_warn.calls[:1]))
check("§1 …and the warning is the box the profile family already uses (`msg.error_title`)",
      bool(_warn.calls) and _warn.calls[0][0] == i18n.t("msg.error_title"),
      str(_warn.calls[:1]))
with open(_prof_path, "w", encoding="utf-8") as fh:
    fh.write(_healthy)
_mgr.close()

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the project reader regenerates a duplicate id ==")
# ════════════════════════════════════════════════════════════════════════════

_dup = _project_file("v11222-duplicate.json", [
    {"id": "web01", "alias": "ALPHA", "host": "10.30.0.1", "user": "root"},
    {"id": "web01", "alias": "BRAVO", "host": "10.30.0.2", "user": "root"},
    {"id": "web01", "alias": "CHARLIE", "host": "10.30.0.3", "user": "root"},
])
_servers = read_project_servers(_dup)
check("§2 the reader keeps FILE order and answers one node per entry",
      [s.alias for s in _servers] == ["ALPHA", "BRAVO", "CHARLIE"],
      str([s.alias for s in _servers]))
check("§2 a repeated id is REGENERATED — the answer carries no duplicate",
      [s.id for s in _servers][0] == "web01"
      and len({s.id for s in _servers}) == 3
      and all(s.id for s in _servers),
      str([s.id for s in _servers]))
check("§2 the rule has ONE home (`models/server.py`) and the map's load asks the same one",
      "def unique_id(" in _read("models", "server.py")
      and "unique_id(data, self._nodes)" in _read("graphics", "map_scene.py")
      and "unique_id(data, taken)" in _func_body("read_project_servers", "storage", "project.py")
      and "uuid" not in _func_body("read_project_servers", "storage", "project.py"))

mw = MW.MainWindow()
mw.show()
app.processEvents()
mw._autosave_timer.stop()
for _s in _servers:
    mw.scene.add_server(_s)
app.processEvents()
check("§2 …so the MAP of the same file holds three distinct cards (no silent clobber)",
      len(mw.scene.nodes()) == 3
      and len({n.data.id for n in mw.scene.nodes()}) == 3
      and sorted(n.data.alias for n in mw.scene.nodes()) == ["ALPHA", "BRAVO", "CHARLIE"],
      str([(n.data.alias, n.data.id) for n in mw.scene.nodes()]))
check("§2 the reader still never writes: no save, no publish and no `open()` for writing",
      "publish_atomic" not in _func_body("read_project_servers", "storage", "project.py")
      and "write_project_json" not in _func_body("read_project_servers", "storage", "project.py")
      and "open(" not in _func_body("read_project_servers", "storage", "project.py"))

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the row key is its POSITION in the answer ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 `server_row_keys()` is PURE and answers one distinct key per ROW",
      CL.server_row_keys(["a", "b"]) == ["a@0", "b@1"]
      and CL.server_row_keys(["web01", "web01"]) == ["web01@0", "web01@1"]
      and CL.server_row_keys(["", "x", ""]) == ["_@0", "x@1", "_@2"]
      and len(set(CL.server_row_keys(["d", "d", "d"]))) == 3,
      str(CL.server_row_keys(["web01", "web01"])))

_alpha = ServerData(id="web01", alias="ALPHA", host="10.30.0.1", user="root")
_bravo = ServerData(id="web01", alias="BRAVO", host="10.30.0.2", user="root")
_asked = []
panel = CL.CommandLibraryPanel(None, store=CL.CommandLibraryStore(path=os.path.join(WORK, "cl.json")))
panel.set_server_sources(lambda: [_alpha, _bravo], lambda node: _asked.append(node))
panel.set_head(CL.HEAD_SERVERS)
app.processEvents()
check("§3 two entries sharing ONE id produce TWO rows (the panel assumes no uniqueness)",
      panel.server_tree.topLevelItemCount() == 2
      and [panel.server_tree.topLevelItem(i).text(0) for i in range(2)] == ["ALPHA", "BRAVO"],
      str([panel.server_tree.topLevelItem(i).text(0) for i in range(2)]))
check("§3 the rows carry DISTINCT keys, and each one resolves to its OWN server",
      panel._server_for_item(panel.server_tree.topLevelItem(0)) is _alpha
      and panel._server_for_item(panel.server_tree.topLevelItem(1)) is _bravo,
      f"{panel._server_for_item(panel.server_tree.topLevelItem(0))} / "
      f"{panel._server_for_item(panel.server_tree.topLevelItem(1))}")
panel._activate_server_item(panel.server_tree.topLevelItem(0))
check("§3 a click on the FIRST row reaches the FIRST server (the wrong-host outcome is closed)",
      _asked == [_alpha] and _asked[0].host == "10.30.0.1",
      str([n.host for n in _asked]))
_asked.clear()
panel._activate_server_item(panel.server_tree.topLevelItem(1))
check("§3 …and the second row reaches the second server",
      _asked == [_bravo] and _asked[0].host == "10.30.0.2",
      str([n.host for n in _asked]))
panel.close()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the live list: the panel re-reads, the door re-checks ==")
# ════════════════════════════════════════════════════════════════════════════

_victim = mw.scene.add_server(ServerData(id="v11222-victim", alias="victim",
                                         host="10.30.9.9", user="root"))
_keeper = mw.scene.add_server(ServerData(id="v11222-keeper", alias="keeper",
                                         host="10.30.9.10", user="root"))
app.processEvents()
_win = ST.SSHTerminalWindow(_keeper.data, mw, password="pw")
_win.show()
app.processEvents()
_vpanel = _win.cmdlib_panel
_vpanel.set_head(CL.HEAD_SERVERS)
app.processEvents()
check("§4 the map-backed window lists the map's live cards (the provider pair is installed)",
      _vpanel.servers_available() is True
      and _vpanel.server_tree.topLevelItemCount() == len(mw.scene.nodes())
      and _vpanel._servers_provider is not None,
      f"rows={_vpanel.server_tree.topLevelItemCount()} map={len(mw.scene.nodes())}")

_stale_key = None
_removed_row = None
for _i in range(_vpanel.server_tree.topLevelItemCount()):
    _cand = _vpanel.server_tree.topLevelItem(_i)
    _node = _vpanel._server_for_item(_cand)
    if _node is not None and _node.data.id == _victim.data.id:
        _removed_row = _cand
        _stale_key = _cand.data(0, Qt.ItemDataRole.UserRole)
check("§4 the card that is about to leave HAS its own row (the defect's precondition)",
      _removed_row is not None and _stale_key is not None
      and _victim.data.id in [n.data.id for n in mw.scene.nodes()],
      f"rows={_vpanel.server_tree.topLevelItemCount()} key={_stale_key!r}")

mw._push_command(CmdAddRemoveNode(mw, mw.scene, _victim.data, mode="remove"))
app.processEvents()
check("§4 an undo command that REMOVES a card re-reads the panel with the sidebar (`N105`)",
      _victim.data.id not in [n.data.id for n in mw.scene.nodes()]
      and _victim.data.id not in [CL.server_row_facts(n)[0] for n in _vpanel._server_nodes]
      and _vpanel.server_tree.topLevelItemCount() == len(mw.scene.nodes()),
      f"rows={_vpanel.server_tree.topLevelItemCount()} map={len(mw.scene.nodes())}")
check("§4 …the row the list held for it is GONE from its memory (`N105`, the one window)",
      _stale_key not in _vpanel._row_position
      and _vpanel._server_for_item(_removed_row) is None
      and _stale_key not in [CL.server_row_keys([CL.server_row_facts(n)[0]
                                                 for n in _vpanel._server_nodes])[i]
                             for i in range(len(_vpanel._server_nodes))],
      f"key={_stale_key!r} position={_vpanel._row_position.get(_stale_key)!r}")
_asked.clear()
_orig_dlg = MW.SSHConnectDialog
MW.SSHConnectDialog = lambda data, parent=None: _asked.append(data)
try:
    _vpanel._activate_server_item(_removed_row)
    app.processEvents()
finally:
    MW.SSHConnectDialog = _orig_dlg
check("§4 …so the activation door builds NO dialog for it (the window is closed)",
      _asked == [], str(_asked))

_win.close()
app.processEvents()

# ── the source audit of the ONE re-read and the ONE door ──
_relist_body = window_func_body("_refresh_server_lists", ROOT)
check("§4 the re-read belongs to `_post_undo_refresh()` (the sidebar's own place)",
      "_refresh_server_lists()" in _func_body("_post_undo_refresh", "ui", "main_window.py")
      and callable(getattr(mw, "_refresh_server_lists", None))
      and "panel.refresh_servers()" in _relist_body,
      _relist_body)
check("§4 …and finds the panels by their METHOD — the facade imports no `modules/` (§4.1)",
      "getattr(panel, 'refresh_servers', None)" in _relist_body
      and "CommandLibraryPanel" not in _relist_body
      and "findChildren" in _relist_body,
      _relist_body)   # the docstring already stripped (CODE only — `window_func_body`)
check("§4 the door re-checks the node BEFORE it asks for a dialog",
      "node = self._server_for_item(item)" in _func_body("_activate_server_item", "modules",
                                                         "command_library.py")
      and "self._connect_sink(node)" in _func_body("_activate_server_item", "modules",
                                                   "command_library.py"))
check("§4 `refresh_servers()` answers at once when the provider says nothing changed",
      "self._servers_changed()" in _func_body("refresh_servers", "modules", "command_library.py")
      and callable(getattr(CL.CommandLibraryPanel, "_servers_changed", None)))

# ════════════════════════════════════════════════════════════════════════════
print("== §5 a refused close keeps the autosave it had ==")
# ════════════════════════════════════════════════════════════════════════════

mw.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
_autosave_on = mw._autosave_enabled
mw._autosave_enabled = True
mw._autosave_timer.start()
check("§5 the window starts its autosave (the state the refused close must restore)",
      mw._autosave_timer.isActive() is True)

_answer = _Question(QMessageBox.Cancel).install()
try:
    mw._dirty = True
    _ev = QCloseEvent()
    mw.closeEvent(_ev)
    app.processEvents()
finally:
    _answer.restore()
check("§5 `Cancel` leaves the window open (the shipped half of the contract)",
      _ev.isAccepted() is False and mw._dirty is True)
check("§5 …and the autosave timer is RUNNING again (`N107`)",
      mw._autosave_timer.isActive() is True,
      f"active={mw._autosave_timer.isActive()} enabled={mw._autosave_enabled}")

_answer = _Question(QMessageBox.Save).install()
_orig_save = mw._save_project
mw._save_project = lambda: False            # a save that FAILED keeps the window alive too
try:
    _ev2 = QCloseEvent()
    mw.closeEvent(_ev2)
    app.processEvents()
finally:
    mw._save_project = _orig_save
    _answer.restore()
check("§5 a FAILED save refuses the close and restores the service as well",
      _ev2.isAccepted() is False and mw._autosave_timer.isActive() is True,
      f"accepted={_ev2.isAccepted()} active={mw._autosave_timer.isActive()}")

mw._autosave_enabled = False
mw._autosave_timer.stop()
_answer = _Question(QMessageBox.Cancel).install()
try:
    _ev3 = QCloseEvent()
    mw.closeEvent(_ev3)
    app.processEvents()
finally:
    _answer.restore()
check("§5 an autosave switched OFF is NOT started by the refusal (the ONE predicate)",
      _ev3.isAccepted() is False and mw._autosave_timer.isActive() is False,
      f"active={mw._autosave_timer.isActive()}")
mw._autosave_enabled = _autosave_on
mw._dirty = False
check("§5 the restart is ONE method, asked by every refused branch of the question",
      "def _restart_autosave(" in _read("ui", "main_window.py")
      and _read("ui", "main_window.py").count("self._restart_autosave()") == 1
      and "if refused:" in _read("ui", "main_window.py"))

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the standalone's empty state and the entry point ==")
# ════════════════════════════════════════════════════════════════════════════

TS.QFileDialog = _FileDialog
_surface = TS.start_standalone()
_spanel = _surface.window.cmdlib_panel
app.processEvents()
check("§6 with NO project open the standalone does NOT claim a project has no servers (`N108`)",
      _spanel.project_mode() is True and _spanel.project_is_open() is False
      and _spanel.servers_available() is True
      and _spanel.info_label.text() == i18n.t("terminal.cmdlib.no_project")
      and _spanel.info_label.text() != i18n.t("terminal.cmdlib.project_empty"),
      f"open={_spanel.project_is_open()} info={_spanel.info_label.text()!r}")
check("§6 the predicate asks the SURFACE's own `project_path()` (no map hook, no new key)",
      "def project_is_open(" in _read("modules", "command_library.py")
      and "project_path" in _func_body("project_is_open", "modules", "command_library.py")
      and "project_path" in _read("modules", "terminal_standalone.py")
      and _spanel.project_is_open() is False)
_empty_project = _project_file("v11222-empty.json", [])
_surface.open_project(_empty_project)
app.processEvents()
check("§6 an OPEN project with no servers keeps the project's own sentence",
      _spanel.project_is_open() is True
      and _spanel.info_label.text() == i18n.t("terminal.cmdlib.project_empty")
      and _spanel.hint_label.isVisible() is False,
      f"open={_spanel.project_is_open()} info={_spanel.info_label.text()!r}")
_surface.window.close()
app.processEvents()

_main_imports = _imports("main.py")
_main_src = _read("main.py")
_branch_at = _main_src.index('if args["mode"] == MODE_TERMINAL:')
_map_import_at = _main_src.index("from .ui.main_window import MainWindow")
check("§6 `--only-terminal` imports NO map at the entry point either (`N109`)",
      _map_import_at > _branch_at
      and _main_src.index("MainWindow()") > _map_import_at
      and "ui.main_window" in _main_imports,
      f"branch={_branch_at} import={_map_import_at} imports={sorted(_main_imports)}")
check("§6 …and the map branch still builds exactly one MainWindow",
      _main_src.count("MainWindow()") == 1
      and "from ui.main_window import MainWindow" in _main_src)

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the comments that explained the standalone's quit ==")
# ════════════════════════════════════════════════════════════════════════════

_window_src = _read("modules", "ssh_terminal.py")
_quit_at = _window_src.index("quit_on_close = False")
_quit_comment = _window_src[max(0, _quit_at - 700):_quit_at]
check("§7 the container's comment no longer claims it is a child that is not a window (`N110`)",
      "CHILD of its surface" not in _quit_comment
      and "isWindow()` is False" not in _quit_comment
      and "top-level" in _quit_comment,
      _quit_comment[-200:])
check("§7 …and names the REAL reason the explicit `quit()` is load-bearing",
      "StandaloneSurface" in _quit_comment and "quitOnLastWindowClosed" in _quit_comment)
_spec_src = _read("tests", "test_terminal_standalone.py")
check("§7 the topical file's own comment was corrected with it",
      "CHILD of its surface (`isWindow()` False)" not in _spec_src
      and "StandaloneSurface" in _spec_src)

# ════════════════════════════════════════════════════════════════════════════
print("== §8 the i18n and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check("§8 this release adds NO key — the patch moved predicates, not words",
      # the patch left the pin at 1114; the LATER follow-ups of the line add their own keys
      # (v1.12.3's THREE: the jump host's label, its hint and the import picker's column).
      EXPECTED_I18N_KEYS == 1114 + 3 + 1 + 4
      and all(len(translation_keys(LANGS[c])) == EXPECTED_I18N_KEYS for c in LANGS),
      str({c: len(translation_keys(LANGS[c])) for c in sorted(LANGS)}))
check("§8 the sentences the patch re-uses are the SHIPPED ones",
      all(LANGS["en"].get(k) for k in ("terminal.cmdlib.no_project", "terminal.cmdlib.project_empty",
                                       "terminal.cmdlib.servers_empty", "msg.error_title")))

check_release_state(ROOT)
check("§8 the pin names this line's release or a later one",
      releases_at_least(EXPECTED_APP_VERSION, "1.12.2"), EXPECTED_APP_VERSION)
check("§8 the schema did NOT move (no project format change)",
      'VERSION_FORMAT = "0.9"' in _read("version.py"))
check("§8 the topical file is listed by the suite map (tests/INDEX.md regenerated)",
      "test_hardening_v11222.py" in _read("tests", "INDEX.md"))

for _w in (mw,):
    try:
        _w.close()
    except RuntimeError:
        pass

finish()
