# -*- coding: utf-8 -*-
"""v1.10rc1 — the leftovers of the closed line and the auto-open option.
The ledger batch (`N85`–`N97`) driven end to end: §1 the command guard's quoted COMMAND and the
`init`/`telinit` family; §2 the UI font before the first widget and the columns MEASURED from it;
§3 the session's state before its channel; §4 `rows(BOTH)`; §5 the repository's closed world;
§6 the option itself (`ui_reopen_last_project`); §7 `TERM` on the wire; §8 the release state.
Rule — `AGENTS.md` §4.1, §4.3, §4.30, §4.32, §13; mechanism — `DOCUMENTATION.md` §14, §15, §41, §74.
"""
import fnmatch
import os
import subprocess
import sys
import types

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, docs_mode, finish,
                     load_i18n_langs, releases_at_least, rep_doc_text, write_cfg)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.activity_log as AL  # noqa: E402
import modules.command_guard as CG  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
from models.server import ServerData  # noqa: E402
from modules.terminal_page import (SESSION_STATE_OFFLINE, SESSION_STATE_ONLINE, session_mark_status)  # noqa: E402
from ui.server_menu import BOTH, CARD, SIDEBAR  # noqa: E402
from ui import server_menu as SM  # noqa: E402


def _read(*parts) -> str:
    """The text of a repository file that SHIPS (the source audits below read several)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the command guard sees the command a quoted argument hides (N85, N86) ==")
# ════════════════════════════════════════════════════════════════════════════

_POSITIONAL = [('bash -c "rm -rf /tmp/x"', "rm -rf"),
               ('sudo sh -c "shutdown -h now"', "shutdown"),
               ('bash -lc "mkfs.ext4 /dev/sda1"', "mkfs.ext4"),
               ('dash -c "wipefs -a /dev/sdb"', "wipefs"),
               ('eval "rm -rf /"', "rm -rf"),
               ("eval dd of=/dev/sda", "dd"),
               ("ssh prod 'sudo systemctl reboot'", "reboot"),
               ('ssh -p 2222 host "kill -9 1"', "kill -9"),
               ('bash -c "echo hi; rm -rf /"', "rm -rf"),
               ("sh -c 'init 6'", "init")]
check("§1 the POSITIONAL interpreter table is declared once (a shell's `-c`, `eval`, `ssh host '…'`)",
      CG.INTERPRETER_WORDS == ("sh", "bash", "dash", "zsh", "ksh") and CG.SSH_WORD == "ssh"
      and CG.COMMAND_FLAG == "c" and CG.MAX_NESTED_DEPTH == 2,
      f"{CG.INTERPRETER_WORDS} {CG.SSH_WORD} {CG.COMMAND_FLAG} {CG.MAX_NESTED_DEPTH}")
check("§1 ...and every shape of it is classified by the family the payload names",
      [CG.dangerous_token(c) for c, _w in _POSITIONAL] == [w for _c, w in _POSITIONAL],
      str([CG.dangerous_token(c) for c, _w in _POSITIONAL]))
check("§1 the table is POSITIONAL: a quoted argument that is NOT one stays an argument",
      [CG.dangerous_token(c) for c in ('echo "rm -rf /"', 'echo reboot',
                                       'printf "%s" "mkfs /dev/sdb"')] == ["", "reboot", ""],
      str([CG.dangerous_token(c) for c in ('echo "rm -rf /"', 'echo reboot',
                                           'printf "%s" "mkfs /dev/sdb"')]))
check("§1 ...and the nested pass is BOUNDED by the declared depth (the header says so)",
      CG.dangerous_token("sh -c 'bash -c \"rm -rf /\"'") == "rm -rf"
      and CG.MAX_NESTED_DEPTH == 2
      and "if depth >= MAX_NESTED_DEPTH" in _read("modules", "command_guard.py"),
      repr(CG.dangerous_token("sh -c 'bash -c \"rm -rf /\"'")))
check("§1 the two shapes a string classifier CANNOT see stay DECLARED blind spots",
      CG.dangerous_token("echo 'rm -rf /' > run.sh && sh run.sh") == ""
      and CG.dangerous_token('python -c "import shutil; shutil.rmtree(chr(47))"') == ""
      and CG.dangerous_token("sh run.sh") == "",
      "a FILE indirection and a foreign payload")
check("§1 the runlevel family needs its TARGET (`0` / `6` / `-r`), never a bare word",
      [CG.dangerous_token(c) for c in ("init 0", "telinit 6", "sudo init -r", "/sbin/telinit 0",
                                       "init 3", "init 1", "init", "init --help", "initscript 0")]
      == ["init", "telinit", "init", "telinit", "", "", "", "", ""],
      str([CG.dangerous_token(c) for c in ("init 0", "telinit 6", "sudo init -r",
                                           "/sbin/telinit 0", "init 3", "init 1", "init",
                                           "init --help", "initscript 0")]))
check("§1 the declared families carry the runlevel spelling and nothing else moved",
      CG.FAMILIES == ("reboot", "init", "rm", "remove", "mkfs", "dd", "wipefs", "partition",
                      "userdel", "kill", "fork_bomb") and CG.INIT_TARGETS == ("0", "6", "-r"),
      str(CG.FAMILIES))
check("§1 the classifier still never raises and stays bounded (a payload included)",
      CG.dangerous_token(None) == "" and CG.dangerous_token(5) == ""
      and CG.dangerous_token('bash -c "rm -rf /' + "y" * 100000 + '"') == CG.TOKEN_OVER_LONG
      and CG.dangerous_token("x" * 200000) == CG.TOKEN_OVER_LONG)


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the UI font before the first widget, and the columns measured from it (N89–N91) ==")
# ════════════════════════════════════════════════════════════════════════════

from ui.activity_panel import ActivityPanel  # noqa: E402
from ui.plugins_panel import PluginsPanel  # noqa: E402
import ui.plugins_panel as PP  # noqa: E402
from ui.main_window_settings import apply_saved_ui_font  # noqa: E402

check("§2 ONE stamp reader owns the format, its floor and its padding (both panels call it)",
      AL.STAMP_COLUMN_FLOOR == 152 and AL.STAMP_COLUMN_PADDING == 10
      and AL.stamp_column_width(None) == 152
      and AL.stamp_column_width(types.SimpleNamespace(horizontalAdvance=lambda _t: 228)) == 238
      and "STAMP_COLUMN_WIDTH" not in _read("ui", "plugins_panel.py")
      and "AL.stamp_column_width" in _read("ui", "plugins_panel.py")
      and "AL.stamp_column_width" in _read("ui", "activity_panel.py"),
      str(AL.stamp_column_width(types.SimpleNamespace(horizontalAdvance=lambda _t: 228))))

clear_cfg()
_panel = ActivityPanel()
check("§2 the Activity panel's stamp column is MEASURED at construction (a literal cuts it)",
      _panel.tree.columnWidth(0) == _panel.stamp_column_width()
      and _panel.tree.columnWidth(0) >= _panel.tree.fontMetrics().horizontalAdvance(
          AL.stamp_text(0.0))
      and _panel.tree.columnWidth(0) >= AL.STAMP_COLUMN_FLOOR,
      f"{_panel.tree.columnWidth(0)} px")
_pp = PluginsPanel(manager=None)
check("§2 ...and so is the Plugins window's (the SAME reader, no second literal)",
      _pp.event_tree.columnWidth(0) == AL.stamp_column_width(_pp.event_tree.fontMetrics())
      and _pp.event_tree.columnWidth(0) >= _pp.event_tree.fontMetrics().horizontalAdvance(
          AL.stamp_text(0.0)),
      f"{_pp.event_tree.columnWidth(0)} px")

_base = QFont(app.font())
_bigger = QFont(app.font())
_bigger.setPointSize(max(6, int(_base.pointSize() or 9)) + 4)
# A SENTINEL width first: `refresh_theme()` is what a live font change runs, so the check is that the
# walk RE-MEASURES the column (the value it leaves is the live one, never the constructor's).
_panel.tree.setColumnWidth(0, 7)
_pp.event_tree.setColumnWidth(0, 7)
app.setFont(_bigger)
app.processEvents()
try:
    _panel.refresh_theme()
    _pp.refresh_theme()
    check("§2 a FONT change re-measures every measured column (the walk both panels opt into)",
          _panel.tree.columnWidth(0) == _panel.stamp_column_width() != 7
          and _pp.event_tree.columnWidth(0)
          == AL.stamp_column_width(_pp.event_tree.fontMetrics()) != 7
          and _pp.plugin_tree.columnWidth(0) > 0 and _pp.server_tree.columnWidth(0) > 0,
          f"activity={_panel.tree.columnWidth(0)} plugins={_pp.event_tree.columnWidth(0)}")
    check("§2 the reader is a function of the font (a wider size needs more room, never less)",
          AL.stamp_column_width(types.SimpleNamespace(horizontalAdvance=lambda _t: 300)) == 310
          and AL.stamp_column_width(types.SimpleNamespace(horizontalAdvance=lambda _t: 10)) == 152
          and "STAMP_COLUMN_FLOOR" in _read("modules", "activity_log.py")
          and PP.MEASURED_COLUMN_MAX == 240
          and "_fit_measured_columns()" in _read("ui", "plugins_panel.py")
          and "_fit_name_column()" in _read("modules", "command_library.py").split(
              "def refresh_theme")[1].split("def retranslate")[0],
          str(_panel.stamp_column_width()))
finally:
    app.setFont(_base)
    app.processEvents()
    _panel.refresh_theme()
    _pp.deleteLater()

check("§2 the font is applied through ONE helper, called BEFORE the first widget exists",
      callable(apply_saved_ui_font)
      and "apply_saved_ui_font(app)" in _read("main.py")
      and "apply_saved_ui_font()" in _read("ui", "main_window.py")
      and "apply_saved_ui_font()" in _read("ui", "main_window_settings.py"))
clear_cfg()
check("§2 ...and a config WITHOUT the font keys leaves the application font alone",
      apply_saved_ui_font(app) is False)


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the session's state before its channel is up (N87) ==")
# ════════════════════════════════════════════════════════════════════════════

import modules.terminal_page as TP  # noqa: E402
from _fakes import FakeSSHThread  # noqa: E402

_stub = types.SimpleNamespace(_connected=False, _session_ended=False, last_error="", _shut_down=False)
check("§3 a page that has not connected is the EMPTY slot (`_connected` is the third state)",
      session_mark_status(_stub) == "" and TP.SESSION_STATE_ONLINE == "online"
      and TP.SESSION_STATE_WARN == "warn" and TP.SESSION_STATE_OFFLINE == "offline")
_stub._connected = True
check("§3 ...`online` once the channel is up, `offline`/warn by their own facts",
      session_mark_status(_stub) == SESSION_STATE_ONLINE
      and (setattr(_stub, "_session_ended", True), session_mark_status(_stub))[-1]
      == SESSION_STATE_OFFLINE
      and (setattr(_stub, "_session_ended", False), setattr(_stub, "last_error", "auth failed"),
           session_mark_status(_stub))[-1] == TP.SESSION_STATE_WARN
      and (setattr(_stub, "_shut_down", True), session_mark_status(_stub))[-1] == "")

_orig_thread_cls = ST.SSHTerminalThread
ST.SSHTerminalThread = FakeSSHThread
try:
    _page = TP.TerminalSessionPage(ServerData(id="v110-state", alias="state", host="10.99.7.1",
                                              user="root"))
    check("§3 a REAL page built without a connect wears no dot at all",
          session_mark_status(_page) == "", repr(session_mark_status(_page)))
    _page._on_connected_state()
    check("§3 ...`connected_signal` is what turns it into the live state (and clears the failure)",
          session_mark_status(_page) == SESSION_STATE_ONLINE and _page.last_error == "")
    _page._on_closed()
    check("§3 ...and the close takes the state away again (offline, never a stale dot)",
          session_mark_status(_page) == SESSION_STATE_OFFLINE and _page._connected is False)
    _page._session_ended = False
    _page.shutdown()
    check("§3 a torn-down page answers nothing (shutdown clears the flag as well)",
          _page._connected is False and session_mark_status(_page) == "")
finally:
    ST.SSHTerminalThread = _orig_thread_cls


# ════════════════════════════════════════════════════════════════════════════
print("== §4 `rows(BOTH)` answers the rows every surface carries (N88) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§4 BOTH (and an unknown surface) drop the surface-only rows",
      "collapse" not in SM.keys(BOTH) and "duplicate" not in SM.keys(BOTH)
      and "reveal" not in SM.keys(BOTH)
      and SM.keys(BOTH) == SM.keys("weird") == SM.keys("")
      and set(SM.keys(BOTH)) < set(SM.keys(CARD)) and set(SM.keys(BOTH)) < set(SM.keys(SIDEBAR)),
      f"{SM.keys(BOTH)}")
check("§4 ...and the two real surfaces are untouched by the condition",
      set(SM.keys(CARD)) - set(SM.keys(BOTH)) == {"collapse", "duplicate"}
      and set(SM.keys(SIDEBAR)) - set(SM.keys(BOTH)) == {"reveal"}
      and set(SM.keys(SIDEBAR)) < set(SM.keys(CARD)) | set(SM.keys(SIDEBAR)),
      f"card={SM.keys(CARD)} sidebar={SM.keys(SIDEBAR)}")


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the repository's closed world (N94) ==")
# ════════════════════════════════════════════════════════════════════════════

_ignore = _read(".gitignore")
_agents = rep_doc_text("AGENTS.md")
check("§5 the two internal documents are NAMED by .gitignore (a `git add -A` cannot publish them)",
      all(line.strip() in _ignore.splitlines() for line in ("TOOLS.md", "UI_UX_AUDIT.md")),
      [n for n in ("TOOLS.md", "UI_UX_AUDIT.md") if n not in _ignore.splitlines()])
if docs_mode():
    check("§5 ...and the §13 internal list names them too (the list and the file agree)",
          "`TOOLS.md`" in _agents and "`UI_UX_AUDIT.md`" in _agents)
_root_md = sorted(n for n in os.listdir(ROOT)
                  if n.endswith(".md") and os.path.isfile(os.path.join(ROOT, n)))
# The ignore file carries GLOBS (`CHANGELOG_HISTORY*.md`), so a name is "ignored" when it matches a
# pattern — the same question `git check-ignore` answers.
_patterns = [line.strip() for line in _ignore.splitlines() if line.strip().endswith(".md")]
_uncovered = [n for n in _root_md
              if n not in {"README.md", "PLUGINS.md"}
              and not any(fnmatch.fnmatch(n, pat) for pat in _patterns)]
# A fresh clone keeps only the two PUBLIC pages (`README.md`, `PLUGINS.md`): the count of five is the
# LOCAL tree's, so the "the class is closed" half is what a public checkout can answer.
check("§5 every root-level *.md is a DECLARED public file or ignored (the class is closed)",
      not _uncovered and (len(_root_md) >= 5 or not _agents),
      f"{len(_root_md)} files, uncovered={_uncovered}")
try:
    _tracked = subprocess.run(["git", "ls-files", "--", "TOOLS.md", "UI_UX_AUDIT.md"], cwd=ROOT,
                              capture_output=True, text=True, timeout=60).stdout.strip()
except (OSError, subprocess.SubprocessError):
    _tracked = ""
check("§5 ...and neither of them is TRACKED by git (untracked + ignored, the declared state)",
      _tracked == "", repr(_tracked))


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the auto-open option (the feature of the release) ==")
# ════════════════════════════════════════════════════════════════════════════

import ui.main_window as MW  # noqa: E402
from ui.main_window_project_io import (LAST_PROJECT_PATH_KEY, REOPEN_LAST_PROJECT_KEY,
                                       last_project_path, reopen_last_project_enabled)  # noqa: E402
from ui.settings_dialog import SettingsDialog, load_ui_settings  # noqa: E402

check("§6 the two keys are declared ONCE and the policy defaults to OFF",
      REOPEN_LAST_PROJECT_KEY == "ui_reopen_last_project"
      and LAST_PROJECT_PATH_KEY == "last_project_path"
      and reopen_last_project_enabled({}) is False
      and reopen_last_project_enabled({REOPEN_LAST_PROJECT_KEY: True}) is True
      and reopen_last_project_enabled({REOPEN_LAST_PROJECT_KEY: "yes"}) is False
      and reopen_last_project_enabled(None) is False)
check("§6 the stored path is read as a trimmed string (a foreign value restores nothing)",
      last_project_path({LAST_PROJECT_PATH_KEY: "  C:/maps/a.json  "}) == "C:/maps/a.json"
      and last_project_path({LAST_PROJECT_PATH_KEY: 7}) == ""
      and last_project_path({}) == "" and last_project_path(None) == "")

_project = os.path.join(WORK, "v110_auto_open.json")
clear_cfg()
_win = MW.MainWindow()
_win.show()
app.processEvents()
_win.scene.add_server(ServerData(id="v110-a", alias="auto", host="10.99.7.2", user="root"))
check("§6 a NAMELESS project records an EMPTY path (a new/demo map has nothing to restore)",
      (_win._remember_last_project(), last_project_path())[-1] == "",
      repr(last_project_path()))


class _SaveAs:
    """The `QFileDialog` seam of the window (the shipped `getSaveFileName` substitution point)."""

    @staticmethod
    def getSaveFileName(*_args, **_kwargs):
        return _project, ""


import ui.main_window_project_io as _PIO  # noqa: E402

_orig_save_dialog = _PIO.QFileDialog.getSaveFileName
_PIO.QFileDialog.getSaveFileName = staticmethod(_SaveAs.getSaveFileName)  # the shipped seam pattern
try:
    _saved = _win._save_project_as()
finally:
    _PIO.QFileDialog.getSaveFileName = _orig_save_dialog
check("§6 a saved project records its ABSOLUTE path (the MRU's own rule)",
      _saved is True and os.path.isfile(_project)
      and (_win._remember_last_project(), last_project_path())[-1] == os.path.abspath(_project),
      repr(last_project_path()))
check("§6 ...and the path it remembers is the OPEN document, never a guess",
      _win._project_file == _project and last_project_path() == os.path.abspath(_win._project_file))
_win._dirty = False
_win.close()
app.processEvents()
check("§6 ...and `closeEvent` is the ONE writer (the path survives the close)",
      last_project_path() == os.path.abspath(_project)
      and "_remember_last_project()" in _read("ui", "main_window.py"), repr(last_project_path()))

_second = MW.MainWindow()          # the option is OFF: nothing is loaded
_second.show()
app.processEvents()
check("§6 with the option OFF a new window opens EMPTY (the default is a surprise-free start)",
      _second.scene.nodes() == [] and _second._project_file is None)
_second._dirty = False
_second.close()
app.processEvents()

# The close above recorded ITS OWN (nameless) project — the ON case therefore states the path the
# option is about, which is exactly the pair `closeEvent` + the startup call exchange.
write_cfg({REOPEN_LAST_PROJECT_KEY: True, LAST_PROJECT_PATH_KEY: os.path.abspath(_project)})
_third = MW.MainWindow()           # the option is ON: the ordinary load path runs
_third.show()
app.processEvents()
check("§6 with the option ON the window reopens the project it was CLOSED on",
      _third._project_file == os.path.abspath(_project)
      and [n.data.id for n in _third.scene.nodes()] == ["v110-a"]
      and _third._dirty is False,
      f"{_third._project_file} {[n.data.id for n in _third.scene.nodes()]}")
check("§6 ...and the startup call is the LAST stage of `__init__` (everything a load needs exists)",
      "_reopen_last_project_at_startup()" in _read("ui", "main_window.py")
      and "skip_autosave_prompt=True" in _read("ui", "main_window_project_io.py"))
_third._dirty = False
_third.close()
app.processEvents()

write_cfg({REOPEN_LAST_PROJECT_KEY: True, LAST_PROJECT_PATH_KEY: os.path.join(WORK, "gone.json")})
_fourth = MW.MainWindow()
check("§6 a project MOVED or deleted between two runs is a quiet no-op (no dialog, empty window)",
      _fourth.scene.nodes() == [] and _fourth._project_file is None
      and _fourth._reopen_last_project_at_startup() is False)
_fourth._dirty = False
_fourth.close()
app.processEvents()

write_cfg({REOPEN_LAST_PROJECT_KEY: True})
_hub = SettingsDialog(None)
check("§6 the `General` tab carries the checkbox, prefilled from the config",
      _hub.reopen_last_chk.isChecked() is True
      and _hub.collect()[REOPEN_LAST_PROJECT_KEY] is True
      and load_ui_settings()["reopen_last_project"] is True,
      str(_hub.reopen_last_chk.text()))
_hub.reopen_last_chk.setChecked(False)
check("§6 ...and `collect()` is the ONE writer of the policy (unchecking it writes `false`)",
      _hub.collect()[REOPEN_LAST_PROJECT_KEY] is False
      and i18n.t("settings.general.reopen_last_project") != "settings.general.reopen_last_project")
_hub.close()
clear_cfg()
check("§6 the store is back to the declared default after the probe",
      reopen_last_project_enabled() is False and last_project_path() == "")
if os.path.isfile(_project):
    os.remove(_project)


# ════════════════════════════════════════════════════════════════════════════
print("== §7 `TERM` on the wire (N97) ==")
# ════════════════════════════════════════════════════════════════════════════

_term_src = _read("modules", "ssh_terminal.py")
check("§7 the PTY asks for the entry that DECLARES 256 colours (the canvas renders them)",
      ST.TERMINAL_TYPE == "xterm-256color" and _term_src.count("client.invoke_shell(") == 1
      and "client.invoke_shell(term=term" in _term_src
      and "term='xterm'" not in _term_src,
      ST.TERMINAL_TYPE)
_doc = rep_doc_text("DOCUMENTATION.md")
if docs_mode():
    check("§7 ...and the reference names the same literal in its two places (the doc follows the code)",
          _doc.count("term='xterm-256color'") >= 2
          and "term='xterm'" not in _doc.replace("term='xterm-256color'", ""),
          str(_doc.count("term='xterm-256color'")))


# ════════════════════════════════════════════════════════════════════════════
print("== §8 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check("§8 the pin names this line's release or a later one (the rc slots ride on the same code)",
      releases_at_least(EXPECTED_APP_VERSION, "1.10")
      and releases_at_least(EXPECTED_APP_VERSION, "1.9.8"),
      EXPECTED_APP_VERSION)
check("§8 the schema did NOT move (no project format change) and no new dependency arrived",
      __import__("version").VERSION_FORMAT == "0.9"
      and all(f"{d}>=" in _read("requirements.txt")
              for d in ("PySide6", "paramiko", "keyring", "wcwidth")))
_langs = load_i18n_langs(ROOT)
check("§8 the ONE new key of the release is present and non-empty in every language",
      EXPECTED_I18N_KEYS == 1092 + 1 + 1 + 10 + 10 + 3 + 1 + 4 + 3 + 2 + 8 + 9 + 18 + 4 + 13 + 1 + 1 + 12
      and all(str(data.get("settings.general.reopen_last_project") or "").strip()
              for data in _langs.values()),
      str({c: d.get("settings.general.reopen_last_project") for c, d in _langs.items()}))
check_i18n_parity(_langs)
check_i18n_format(_langs)
check("§8 the topical file is listed by the suite map (tests/INDEX.md regenerated)",
      "test_leftovers_v110" in _read("tests", "INDEX.md"))
_ledger = rep_doc_text("AUDIT_PENDING.md")
if docs_mode():
    check("§8 the ledger batch this release paid has LEFT the ledger (a fixed defect is not pending)",
          all(f"### N{n} —" not in _ledger for n in range(85, 98))
          or "The entries above are the `1.10` line's first batch" not in _ledger)

finish()
