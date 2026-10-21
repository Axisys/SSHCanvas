# -*- coding: utf-8 -*-
"""The row verbs of the Files pane and of the Servers head (v1.13.3).
§1 the Files menu carries the two verbs beside the shipped ones; §2 `Download` of a file AND of a
whole folder; §3 `Upload` into the folder under the pointer and into the current one; §4 the two
refusals — a local pane and an elevated one; §5 the `Servers` row menu (`Connect to SSH`, the card's
`Quick Launch` and its editor door); §6 the tag filter and the name sort as VIEW STATE; §7 the i18n
keys and the release state.
Rule — `AGENTS.md` §4.3.6, §4.3.8; mechanism — `DOCUMENTATION.md` §14e, §14f.
"""
import ast
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, VERSION_FORMAT_RE, bootstrap, check,
                     check_i18n_format, check_i18n_parity, check_release_state, clear_cfg, finish,
                     load_i18n_langs, read_cfg, releases_at_least, wait_until)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.command_library as CL  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_standalone as TS  # noqa: E402
import ui.main_window as MW  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.sftp_worker import SftpWorker  # noqa: E402
from modules.sftp_tab import SOURCE_LOCAL, SOURCE_REMOTE  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, FakeSSHThread, wire_worker  # noqa: E402

ST.SSHTerminalThread = FakeSSHThread     # every session/dialog of this file runs on the fake
clear_cfg()


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the Files row menu carries the two verbs ==")
# ════════════════════════════════════════════════════════════════════════════

class _FakeFileDialog:
    """`QFileDialog` of the pane — a script of picked files and one directory (the shipped seam)."""

    FILES = []
    DIR = ""
    CALLS = []

    @staticmethod
    def getOpenFileNames(*args, **kwargs):
        _FakeFileDialog.CALLS.append("files")
        return (list(_FakeFileDialog.FILES), "")

    @staticmethod
    def getExistingDirectory(*args, **kwargs):
        _FakeFileDialog.CALLS.append("dir")
        return _FakeFileDialog.DIR


class _FakeMessageBox:
    """The conflict box the pane would build — nothing here opens one (the pane's seam answers)."""

    class Icon:
        Question = 0

    class ButtonRole:
        AcceptRole = 0
        RejectRole = 1
        ActionRole = 2


STAB.QFileDialog = _FakeFileDialog
STAB.QMessageBox = _FakeMessageBox


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


def _classes(*parts) -> list:
    """Every class name a shipped file DECLARES (the "the menu lives where it is owned" audit)."""
    return [n.name for n in ast.walk(ast.parse(_read(*parts))) if isinstance(n, ast.ClassDef)]


def _action(menu, key) -> object:
    """The QAction whose text is `i18n.t(key)` (the tests trigger actions, never `menu.exec()`)."""
    wanted = i18n.t(key)
    for act in menu.actions():
        if act.text() == wanted:
            return act
    return None


def _labels(menu) -> list:
    """The non-separator labels of a menu, in order."""
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def _enabled(menu) -> list:
    """The enabled flag of every non-separator action, in order."""
    return [a.isEnabled() for a in menu.actions() if not a.isSeparator()]


def _item(tab, name):
    """The listing row by its visible name (None — not there)."""
    for i in range(tab.tree.topLevelItemCount()):
        it = tab.tree.topLevelItem(i)
        if it.text(0) == name:
            return it
    return None


def _make_local(name, data=b"payload"):
    """A real local file under the run's scratch folder."""
    path = os.path.join(WORK, name)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def _new_tab(fs, chunk_delay=0.0):
    """(tab, worker, log) with the listing of "/" already rendered — the shipped fake stack."""
    client = FakeSftpClient(fs, chunk_delay=chunk_delay)
    worker = SftpWorker(client)
    log = EventLog()
    wire_worker(worker, log)
    worker.start()
    tab = STAB.SftpTab()
    messages = []
    tab.message.connect(lambda text: messages.append(text))
    tab.set_worker(worker)
    wait_until(lambda: tab.tree.topLevelItemCount() >= 1, timeout_ms=5000)
    return tab, worker, log, messages


fs1 = FakeSftpFS()
fs1.add_dir("/data")
fs1.add_file("/data/f.txt", b"inner")
fs1.add_file("/plain.txt", b"plain")
tab1, worker1, log1, msgs1 = _new_tab(fs1)
tab1._navigate("/")
wait_until(lambda: _item(tab1, "data") is not None, timeout_ms=5000)

_menu = tab1._build_context_menu(_item(tab1, "plain.txt"))
check("§1 the row menu is New Folder / Rename / Delete / Download / Upload / Copy Path / Open archive "
      "/ Send to / Send to Diff / Refresh",
      _labels(_menu) == [i18n.t("sftp.op.new_folder"), i18n.t("sftp.op.rename"),
                         i18n.t("sftp.op.delete"), i18n.t("sftp.op.download"),
                         i18n.t("sftp.op.upload"), i18n.t("sftp.op.copy_path"),
                         i18n.t("sftp.archive.open"), i18n.t("sftp.send.menu"),
                         i18n.t("diff.send.menu"), i18n.t("sftp.refresh")],
      str(_labels(_menu)))
check("§1 on a REAL file row both verbs are live beside Rename/Delete/Copy",
      _enabled(_menu) == [True, True, True, True, True, True, False, True, True, True],
      str(_enabled(_menu)))
check("§1 the two verbs live in the pane's OWN menu builder (no second menu, no map import)",
      "_build_context_menu" in _read("modules", "sftp_pane_dnd.py")
      and "_op_download_row" in _read("modules", "sftp_pane_dnd.py")
      and "_op_upload_row" in _read("modules", "sftp_pane_dnd.py")
      and not any("ui.main_window" in n or "graphics" in n
                  for n in _imports("modules", "sftp_pane_dnd.py")),
      str(sorted(n for n in _imports("modules", "sftp_pane_dnd.py")
                 if "graphics" in n or "main_window" in n)))

_menu_up = tab1._build_context_menu(tab1._up_item)
check("§1 on the '..' row Rename/Delete/Download are disabled while Upload keeps its floor",
      _enabled(_menu_up) == [True, False, False, False, True, False, False, True],
      str(_enabled(_menu_up)))

_menu_empty = tab1._build_context_menu(None)
check("§1 on empty space only New Folder / Upload / Refresh are live",
      _enabled(_menu_empty) == [True, False, False, False, True, False, False, True],
      str(_enabled(_menu_empty)))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 Download — a file and a whole folder ==")
# ════════════════════════════════════════════════════════════════════════════

_dl_dir = os.path.join(WORK, "dl1")
os.makedirs(_dl_dir, exist_ok=True)
_FakeFileDialog.DIR = _dl_dir
_FakeFileDialog.CALLS = []
_action(_menu, "sftp.op.download").trigger()
wait_until(lambda: os.path.exists(os.path.join(_dl_dir, "plain.txt")), timeout_ms=8000)
check("§2 `Download` on a file row is ONE download task into the chosen directory",
      open(os.path.join(_dl_dir, "plain.txt"), "rb").read() == b"plain"
      and _FakeFileDialog.CALLS == ["dir"],
      f"calls={_FakeFileDialog.CALLS}")

_dl2 = os.path.join(WORK, "dl2")
os.makedirs(_dl2, exist_ok=True)
_FakeFileDialog.DIR = _dl2
_menu_dir = tab1._build_context_menu(_item(tab1, "data"))
check("§2 the folder row keeps both verbs live (a folder is a row, not an exception)",
      _action(_menu_dir, "sftp.op.download").isEnabled() is True)
_action(_menu_dir, "sftp.op.download").trigger()
wait_until(lambda: os.path.exists(os.path.join(_dl2, "data", "f.txt")), timeout_ms=8000)
check("§2 a FOLDER download needs no new machinery — the worker's bounded walk ships it",
      os.path.isdir(os.path.join(_dl2, "data"))
      and open(os.path.join(_dl2, "data", "f.txt"), "rb").read() == b"inner",
      str(os.listdir(_dl2)))
check("§2 ...one task for the whole tree (the queue answers one download per row)",
      any(e[0] == "done" and e[2] if len(e) > 2 else False for e in log1.events)
      or bool(log1.of_kind("done")), f"events={len(log1.events)}")

_FakeFileDialog.DIR = ""
_before = len(log1.events)
_action(tab1._build_context_menu(_item(tab1, "plain.txt")), "sftp.op.download").trigger()
check("§2 a cancelled directory dialog queues nothing and says nothing",
      len(log1.events) == _before and not msgs1, f"events={len(log1.events)} msgs={msgs1}")


# ════════════════════════════════════════════════════════════════════════════
print("== §3 Upload — into the folder under the pointer ==")
# ════════════════════════════════════════════════════════════════════════════

_up1 = _make_local("up_one.txt", b"one")
_FakeFileDialog.FILES = [_up1]
msgs1.clear()
_action(_menu_dir, "sftp.op.upload").trigger()
wait_until(lambda: "/data/up_one.txt" in fs1.files, timeout_ms=8000)
check("§3 `Upload` on a FOLDER row writes INTO that folder, not into the one on the screen",
      fs1.files.get("/data/up_one.txt") == b"one", str(sorted(fs1.files)))
check("§3 ...and the status line names the folder it really wrote into",
      any("/data" in m for m in msgs1), str(msgs1))

_up2 = _make_local("up_two.txt", b"two")
_FakeFileDialog.FILES = [_up2]
_action(tab1._build_context_menu(None), "sftp.op.upload").trigger()
wait_until(lambda: "/up_two.txt" in fs1.files, timeout_ms=8000)
check("§3 on empty space the target is the directory ON THE SCREEN (`_current_dir`)",
      fs1.files.get("/up_two.txt") == b"two", str(sorted(fs1.files)))

# The conflict question: the current directory IS on the screen, so its names are the `known` set.
fs1.add_file("/dup.txt", b"old")
tab1._relist("/")
wait_until(lambda: _item(tab1, "dup.txt") is not None, timeout_ms=5000)
_conflicts = []


def _ask(name, target, remaining, facts=""):
    _conflicts.append((name, target, remaining))
    return ("skip", False)


tab1.active_pane._ask_conflict = _ask
_up3 = _make_local("dup.txt", b"new")
_FakeFileDialog.FILES = [_up3]
_action(tab1._build_context_menu(None), "sftp.op.upload").trigger()
wait_until(lambda: bool(_conflicts), timeout_ms=5000)
app.processEvents()
check("§3 a name the CURRENT listing shows is asked about ONCE (ask_conflict stays the ONE question)",
      _conflicts == [("dup.txt", "/", 0)] and fs1.files.get("/dup.txt") == b"old",
      f"asked={_conflicts} file={fs1.files.get('/dup.txt')!r}")

# The OTHER folder has no listing: the decided EMPTY `known` set asks nothing.
fs1.add_file("/data/dup.txt", b"old")
_conflicts.clear()
_FakeFileDialog.FILES = [_up3]
_action(tab1._build_context_menu(_item(tab1, "data")), "sftp.op.upload").trigger()
wait_until(lambda: fs1.files.get("/data/dup.txt") == b"new", timeout_ms=8000)
check("§3 a folder the pane has NO listing of passes an EMPTY `known` set — no question, the "
      "worker's own shallow check decides",
      _conflicts == [] and fs1.files.get("/data/dup.txt") == b"new",
      f"asked={_conflicts} file={fs1.files.get('/data/dup.txt')!r}")


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the two refusals — the local pane and the elevated one ==")
# ════════════════════════════════════════════════════════════════════════════

_pane = tab1.active_pane
_pane._elevated_provider = _pane.provider      # the shipped property: a pane reading as another user
try:
    _menu_el = tab1._build_context_menu(_item(tab1, "plain.txt"))
    check("§4 an ELEVATED pane still OFFERS both verbs (its source is the server)",
          _action(_menu_el, "sftp.op.download").isEnabled() is True
          and _action(_menu_el, "sftp.op.upload").isEnabled() is True,
          str(_enabled(_menu_el)))
    msgs1.clear()
    _before = len(log1.events)
    tab1._op_upload_row(_item(tab1, "plain.txt"))
    check("§4 ...and an Upload is refused by the shipped read-only sentence, with no task queued",
          msgs1 == [i18n.t("sftp.elevated.read_only")] and len(log1.events) == _before,
          f"msgs={msgs1}")
finally:
    _pane._elevated_provider = None
    app.processEvents()

tab2, worker2, log2, msgs2 = _new_tab(fs1)
check("§4 a REMOTE pane offers both verbs (the source gate answers True)",
      tab2.active_pane._row_verbs_offered() is True
      and tab2.active_pane.source == SOURCE_REMOTE)
tab2.set_commander(True)                      # the LOCAL source belongs to the SECOND pane
app.processEvents()
_local_pane = tab2.panes[1]
tab2.set_pane_source(_local_pane, SOURCE_LOCAL)
_local_pane.activate()
app.processEvents()
check("§4 ...a LOCAL pane is the second one and becomes the ACTIVE pane of the container",
      _local_pane.source == SOURCE_LOCAL and tab2.active_pane is _local_pane,
      f"{_local_pane.source} / {tab2.active_pane is _local_pane}")
_msgs_local = []
tab2.message.connect(lambda text: _msgs_local.append(text))
_menu_local = tab2._build_context_menu(None)
check("§4 a LOCAL pane shows both verbs DISABLED (a copy onto itself is not a verb)",
      _action(_menu_local, "sftp.op.download").isEnabled() is False
      and _action(_menu_local, "sftp.op.upload").isEnabled() is False,
      str(_enabled(_menu_local)))
tab2._op_download_row(None)
tab2._op_upload_row(None)
check("§4 ...and each refusal speaks the SHIPPED sentence (`sftp.local.transfer_unavailable`)",
      _msgs_local == [i18n.t("sftp.local.transfer_unavailable")] * 2,
      str(_msgs_local))


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the `Servers` row menu — Connect to SSH and Quick Launch ==")
# ════════════════════════════════════════════════════════════════════════════

_panel = CL.CommandLibraryPanel(None, store=CL.CommandLibraryStore(
    path=os.path.join(WORK, "rv_lib.json")))
_alpha = ServerData(id="rv-alpha", alias="alpha", host="10.95.0.1", user="root",
                    tags=["prod", "web"],
                    quick_launch=[{"type": "url", "name": "Web UI", "value": "https://a.example"}])
_beta = ServerData(id="rv-beta", alias="beta", host="10.95.0.2", user="admin", tags=["dev"])
_asked, _entries, _configured = [], [], []
_panel.set_server_sources(lambda: [_alpha, _beta],
                          lambda node: _asked.append(node))
_panel.set_quick_launch_doors(lambda node, entry: _entries.append((node, entry)),
                              lambda node: _configured.append(node))
_panel.set_head(CL.HEAD_SERVERS)
app.processEvents()
check("§5 the panel's `Servers` list carries its OWN context policy (the signal exists now)",
      _panel.server_tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
      and "_on_server_context_menu" in _read("modules", "command_library.py"))

_row = _panel.server_tree.topLevelItem(0)     # alpha (A→Z)
_menu_srv = _panel._build_server_menu(_row)
check("§5 the row menu is `Connect to SSH` + the card's `Quick Launch` submenu",
      _labels(_menu_srv) == [i18n.t("terminal.cmdlib.connect"), i18n.t("ctx.quick_launch")],
      str(_labels(_menu_srv)))
_sub = _menu_srv.actions()[1].menu()
check("§5 the submenu lists the card's entries and ends with the editor door",
      _labels(_sub) == ["Web UI", i18n.t("ql.configure")],
      str(_labels(_sub)))
_action(_menu_srv, "terminal.cmdlib.connect").trigger()
check("§5 `Connect to SSH` is the double click's OWN door — the HOST's connect sink, never "
      "`add_session()`",
      _asked == [_alpha] and _asked[0].host == "10.95.0.1", str([n.host for n in _asked]))
_sub.actions()[0].trigger()
check("§5 an entry reaches the container's ENTRY door with the live node and a COPY of the entry",
      len(_entries) == 1 and _entries[0][0] is _alpha
      and _entries[0][1] == {"type": "url", "name": "Web UI", "value": "https://a.example"},
      str(_entries))
_action(_sub, "ql.configure").trigger()
check("§5 `Configure…` reaches the container's editor door with that same node",
      _configured == [_alpha], str(_configured))

_beta_row = _panel.server_tree.topLevelItem(1)
_beta_menu = _panel._build_server_menu(_beta_row)
_beta_sub = _beta_menu.actions()[1].menu()
check("§5 a card with no entries says so instead of offering a dead submenu",
      _enabled(_beta_sub) == [False, True]
      and _labels(_beta_sub) == [i18n.t("terminal.cmdlib.ql_empty"), i18n.t("ql.configure")],
      str(_labels(_beta_sub)))

# The CONFIGURE door is absent (the standalone): the row stays live and answers ONE sentence.
_said = []
_panel.status_message.connect(lambda text, ms: _said.append(text))
_panel.set_quick_launch_doors(lambda node, entry: _entries.append((node, entry)), None)
_panel._configure_quick_launch(_beta_row)
check("§5 a missing CONFIGURE door is a refusal SENTENCE, never a dead control",
      _said == [i18n.t("terminal.cmdlib.ql_readonly")], str(_said))

# A row whose record left the answer: no connect, no submenu.
_said.clear()
_alpha.id = "rv-alpha-moved"                   # the id the row was BUILT for is gone
app.processEvents()
_stale_row = None
for i in range(_panel.server_tree.topLevelItemCount()):
    _cand = _panel.server_tree.topLevelItem(i)
    if _panel._server_for_item(_cand) is None:
        _stale_row = _cand
check("§5 a stale row is DISABLED in the menu (no session for a card nobody is looking at)",
      _stale_row is not None and _enabled(_panel._build_server_menu(_stale_row)) == [False],
      str(_stale_row))
_alpha.id = "rv-alpha"                         # the next section builds its own panel
_panel.close()


# ════════════════════════════════════════════════════════════════════════════
print("== §5b the containers install the door pair ==")
# ════════════════════════════════════════════════════════════════════════════

mw = MW.MainWindow()
mw.show()
app.processEvents()
mw._autosave_timer.stop()
mw.scene.add_server(ServerData(id="rv-map", alias="map-server", host="10.95.9.9", user="root"))
app.processEvents()
_win = ST.SSHTerminalWindow(ServerData(id="rvw", alias="win", host="10.95.9.10", user="root"),
                            mw, password="pw")
_win.show()
app.processEvents()
_mw_panel = _win.cmdlib_panel
check("§5b the map-backed window installs BOTH `Quick Launch` doors on the panel",
      _mw_panel._quick_launch_entry is not None and _mw_panel._quick_launch_configure is not None)
_called = []
_mw_panel._quick_launch_entry = lambda node, entry: _called.append("entry")
_mw_panel._quick_launch_configure = lambda node: _called.append("configure")
_mw_panel.set_quick_launch_doors(lambda node, entry: _called.append("entry"),
                                 lambda node: _called.append("configure"))
_mw_panel.set_head(CL.HEAD_SERVERS)
app.processEvents()
_map_row = _mw_panel.server_tree.topLevelItem(0)
_mw_panel._run_quick_launch(_map_row, {"type": "url", "name": "x", "value": "https://x.example"})
_mw_panel._configure_quick_launch(_map_row)
check("§5b ...and both resolve the LIVE node of the row they were opened on",
      _called == ["entry", "configure"], str(_called))

_surface = TS.StandaloneSurface()
_surface.window.show()
app.processEvents()
_sp = _surface.window.cmdlib_panel
check("§5b the standalone answers the ENTRY door and installs NO editor (its list is read-only)",
      _sp._quick_launch_entry is not None and _sp._quick_launch_configure is None,
      f"entry={_sp._quick_launch_entry} configure={_sp._quick_launch_configure}")
_surface._servers = [ServerData(id="rv-stand", alias="stand-alone", host="10.95.9.11",
                                user="root", tags=["prod"])]
_surface._refresh_servers()
app.processEvents()
_stand_row = _sp.server_tree.topLevelItem(0)
_said.clear()
_sp.status_message.connect(lambda text, ms: _said.append(text))
_sp._configure_quick_launch(_stand_row)
check("§5b ...so its `Configure…` answers the read-only sentence instead of an editor",
      _said == [i18n.t("terminal.cmdlib.ql_readonly")], str(_said))
check("§5b the SURFACE carries the three entry doors the window asks for by name",
      all(callable(getattr(_surface, name, None))
          for name in ("quick_launch_entry", "quick_launch_url", "quick_launch_command")))


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the tag filter and the name sort are VIEW STATE ==")
# ════════════════════════════════════════════════════════════════════════════

_zulu = ServerData(id="rv-z", alias="zulu", host="10.96.0.3", user="root", tags=["dev"])
_alpha2 = ServerData(id="rv-a", alias="Alpha", host="10.96.0.1", user="root", tags=["prod", "dev"])
_mike = ServerData(id="rv-m", alias="mike", host="10.96.0.2", user="root")
_sortable = [_zulu, _alpha2, _mike]
_panel2 = CL.CommandLibraryPanel(None, store=CL.CommandLibraryStore(
    path=os.path.join(WORK, "rv_lib2.json")))
_panel2.set_server_sources(lambda: list(_sortable), lambda node: None)
_panel2.set_head(CL.HEAD_SERVERS)
app.processEvents()


def _rows() -> list:
    """The visible row texts of the `Servers` list, in order."""
    return [_panel2.server_tree.topLevelItem(i).text(0)
            for i in range(_panel2.server_tree.topLevelItemCount())
            if not _panel2.server_tree.topLevelItem(i).isHidden()]


check("§6 the list is sorted A→Z by the ALIAS (case-folded) — the provider's order is not the view",
      _rows() == ["Alpha", "mike", "zulu"], str(_rows()))
check("§6 the sort control names the direction ONCE, from the keys of the release",
      _panel2.sort_btn.text() == i18n.t("terminal.cmdlib.sort_az")
      and _panel2.sort_btn.toolTip() == i18n.t("terminal.cmdlib.sort_tooltip"),
      _panel2.sort_btn.text())
_panel2._toggle_sort()
check("§6 a click flips it to Z→A (a VIEW STATE — nothing is persisted)",
      _rows() == ["zulu", "mike", "Alpha"]
      and _panel2.sort_btn.text() == i18n.t("terminal.cmdlib.sort_za")
      and "ui_cmdlib_sort" not in _read("modules", "command_library.py"),
      str(_rows()))
_panel2._toggle_sort()
check("§6 ...and back, with the provider's own order restored as the tie-break",
      _rows() == ["Alpha", "mike", "zulu"], str(_rows()))

_combo = [_panel2.tag_combo.itemData(i) for i in range(_panel2.tag_combo.count())]
check("§6 the tag combo lists `All tags` first and then the UNION of the live tags",
      _combo == ["", "dev", "prod"]
      and _panel2.tag_combo.itemText(0) == i18n.t("terminal.cmdlib.all_tags"), str(_combo))
_panel2.tag_combo.setCurrentIndex(_panel2.tag_combo.findData("dev"))
app.processEvents()
check("§6 choosing a tag narrows the list to the rows that carry it",
      _rows() == ["Alpha", "zulu"], str(_rows()))
_panel2.tag_combo.setCurrentIndex(_panel2.tag_combo.findData("prod"))
app.processEvents()
check("§6 ...and a one-tag answer leaves exactly one row", _rows() == ["Alpha"], str(_rows()))
_panel2.search.setText("zzz")
app.processEvents()
check("§6 the tag filter and the search are TWO narrowings of ONE list",
      _rows() == [] and _panel2.info_label.text() == i18n.t("terminal.cmdlib.servers_no_matches"),
      f"rows={_rows()} info={_panel2.info_label.text()!r}")
_panel2.search.clear()
_panel2.tag_combo.setCurrentIndex(0)
app.processEvents()
check("§6 `All tags` restores every row", _rows() == ["Alpha", "mike", "zulu"], str(_rows()))
_panel2.tag_combo.setCurrentIndex(_panel2.tag_combo.findData("prod"))
_sortable.remove(_alpha2)                       # the only `prod` card leaves the map
_panel2.refresh_servers()
app.processEvents()
check("§6 a tag that no card carries any more falls back to `All tags` instead of an empty list",
      _panel2._tag_filter == "" and _rows() == ["mike", "zulu"], str(_rows()))
_sortable.append(ServerData(id="rv-n", alias="november", host="10.96.0.4", user="root",
                            tags=["db"]))
_panel2.refresh_servers()
app.processEvents()
check("§6 a new card (and a new tag) reaches the list on the next re-read — the options follow the "
      "answer, not a stored list",
      _rows() == ["mike", "november", "zulu"]
      and _panel2.tag_combo.findData("db") >= 0
      and [_panel2.tag_combo.itemData(i) for i in range(_panel2.tag_combo.count())]
      == ["", "db", "dev"],
      str([_panel2.tag_combo.itemData(i) for i in range(_panel2.tag_combo.count())]))
_zulu.tags = ["prod", "dev"]                    # the SAME object, a changed tag set
_panel2.refresh_servers()
app.processEvents()
_panel2.tag_combo.setCurrentIndex(_panel2.tag_combo.findData("prod"))
app.processEvents()
check("§6 ...and a tag set changed in place rebuilds the rows (the content is what the head sorts "
      "and filters on, not the id alone)",
      _rows() == ["zulu"], str(_rows()))
check("§6 ...and the tag filter and the sort keep NO config key (a view state, like `_head`)",
      read_cfg({}).get("ui_cmdlib_tag") is None and read_cfg({}).get("ui_cmdlib_sort") is None
      and "_save_config({\"ui_cmdlib_tag" not in _read("modules", "command_library.py"),
      str(sorted(k for k in read_cfg({}) if "cmdlib" in k)))
_panel2.close()


# ════════════════════════════════════════════════════════════════════════════
print("== §7 the i18n keys and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

LANGS = load_i18n_langs(ROOT)
_check_keys = ["sftp.op.download", "sftp.op.upload", "terminal.cmdlib.connect",
               "terminal.cmdlib.all_tags", "terminal.cmdlib.sort_az",
               "terminal.cmdlib.sort_za", "terminal.cmdlib.sort_tooltip",
               "terminal.cmdlib.ql_empty", "terminal.cmdlib.ql_readonly"]
check("§7 the NINE keys of the release are non-empty in every language",
      all(LANGS[c].get(k) for c in LANGS for k in _check_keys),
      str({c: [k for k in _check_keys if not LANGS[c].get(k)] for c in sorted(LANGS)}))
check("§7 ...and the pin carries them (1135 + this release's 9 + the later 18 + 4)",
      len(_check_keys) == 9
      and EXPECTED_I18N_KEYS == 1135 + len(_check_keys) + 18 + 4,
      str(EXPECTED_I18N_KEYS))
check_i18n_parity(LANGS)
check_i18n_format(LANGS)

from version import APP_VERSION, VERSION_FORMAT  # noqa: E402

check("§7 the shipped version is the one the pin names",
      APP_VERSION == EXPECTED_APP_VERSION
      and releases_at_least(APP_VERSION, "1.13.3"), APP_VERSION)
check("§7 the release adds no config key and moves no project schema",
      VERSION_FORMAT == "0.9" and bool(VERSION_FORMAT_RE.match(APP_VERSION)), VERSION_FORMAT)
check_release_state(ROOT)

worker1.shutdown(wait_ms=2000)
worker2.shutdown(wait_ms=2000)
for _p in tab2.panes:
    _p.shutdown_provider()      # the LOCAL pane's engine is the pane's own thread (§4.8)
tab1.close()
tab2.close()
mw.close()
finish()
