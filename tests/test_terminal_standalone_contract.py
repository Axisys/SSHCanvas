# -*- coding: utf-8 -*-
"""The clause audit of `TERMINAL_STANDALONE.md` (v1.12) against the SHIPPED code — one section per
clause group of the frozen contract: the launch, the surface, the read-only source, the IN list, the
OUT list, the zero-session container, the bottom row, the credentials, the sentences and the acceptance.
The audit reads the CONTRACT's own clauses and the code's own text; the live behaviour is driven by
`tests/test_terminal_standalone.py` (this file never opens a session).
Run: python tests/test_terminal_standalone_contract.py   (from the project root) or python tests/run_all.py
"""
import ast
import os
import re
import sys

from _common import (bootstrap, check, check_release_state, clear_cfg, docs_mode, finish,
                     load_i18n_langs, rep_doc_text)

ROOT, WORK = bootstrap()  # BEFORE the app imports (the HOME isolation)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import main as MAIN  # noqa: E402
import modules.command_library as CL  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_standalone as TS  # noqa: E402
import storage.project as SP  # noqa: E402


def _text(*parts) -> str:
    """The text of a shipped file (the audit reads several of them)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


CONTRACT_TEXT = _text("TERMINAL_STANDALONE.md") if os.path.isfile(
    os.path.join(ROOT, "TERMINAL_STANDALONE.md")) else ""
TS_SRC = _text("modules", "terminal_standalone.py")
MAIN_SRC = _text("main.py")
PANEL_SRC = _text("modules", "command_library.py")
WINDOW_SRC = _text("modules", "ssh_terminal.py")
SPLIT_SRC = _text("modules", "terminal_split.py")
MAIN_WINDOW_SRC = _text("ui", "main_window.py")
PROJECT_SRC = _text("storage", "project.py")
README_SRC = _text("README.md")
LANGS = load_i18n_langs(ROOT)
TS_IMPORTS = None   # filled below (the AST of the surface)


def clause(section, needle) -> bool:
    """Does the contract's §section contain this phrase? (the frozen text is the specification).

    Whitespace is flattened on BOTH sides, so a clause may be quoted the way it wraps in the file.
    """
    if not CONTRACT_TEXT:
        return False
    start = CONTRACT_TEXT.find(f"## {section}.")
    if start < 0:
        return False
    rest = CONTRACT_TEXT[start + 1:]
    end = rest.find("\n## ")
    body = rest if end < 0 else rest[:end]
    return re.sub(r"\s+", " ", needle) in re.sub(r"\s+", " ", body)


def imports_of(text) -> set:
    """Every module name a source text imports (the AST — prose is not an import)."""
    names = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _body(name, source=None) -> str:
    """The source of ONE function — from its `def` to the next line that starts at column 0."""
    text = TS_SRC if source is None else source
    start = text.find(f"def {name}(")
    if start < 0:
        return ""
    lines = text[start:].split("\n")
    out = [lines[0]]
    for line in lines[1:]:
        if line and not line[0].isspace():
            break
        out.append(line)
    return "\n".join(out)


def _door_order() -> list:
    """The ORDER of the three steps of the connect door (the §8 clause) — the CODE, not the prose."""
    for node in ast.walk(ast.parse(TS_SRC)):
        if isinstance(node, ast.FunctionDef) and node.name == "connect_server":
            statements = [n for n in node.body
                          if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                                  and isinstance(n.value.value, str))]
            order = []
            for statement in statements:
                dumped = ast.dump(statement)
                order += [needle for needle in ("is_unmanaged", "SSHConnectDialog", "add_session")
                          if needle in dumped]
            return order
    return []


def _code_of(name) -> str:
    """ONE function's source WITHOUT its docstring (a name in a docstring is not a call)."""
    for node in ast.walk(ast.parse(TS_SRC)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body = body[1:]
            first = body[0].lineno if body else node.lineno
            return "\n".join(TS_SRC.splitlines()[first - 1:node.end_lineno])
    return ""


TS_IMPORTS = imports_of(TS_SRC)
clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== 1. the launch — ONE flag, and NO socket (TERMINAL_STANDALONE.md §1) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the contract is present and frozen before the code (the file the release implements)",
      bool(CONTRACT_TEXT) and "frozen contract" in CONTRACT_TEXT
      and "`v1.12`" in CONTRACT_TEXT and "TERMINAL_STANDALONE.md" in CONTRACT_TEXT)
check("§1 the flag is declared ONCE, as a MODE ROW (a future subcommand is one more row)",
      MAIN.LAUNCH_FLAGS == {"--only-terminal": MAIN.MODE_TERMINAL}
      and clause(1, 'LAUNCH_FLAGS = {"--only-terminal": MODE_TERMINAL}')
      and "MODE_MAP" in MAIN_SRC and "MODE_TERMINAL" in MAIN_SRC)
check("§1 the parse is PURE and answers the two keys the contract names",
      callable(MAIN.parse_launch_args)
      and set(MAIN.parse_launch_args([])) == {"mode", "unknown"}
      and clause(1, '{"mode", "unknown"}'))
check("§1 `python main.py` is the shipped launch (the default mode is the map)",
      MAIN.parse_launch_args([])["mode"] == MAIN.MODE_MAP
      and MAIN.parse_launch_args(["-style", "Fusion"])["mode"] == MAIN.MODE_MAP
      and clause(1, "`MODE_MAP` is the default"))
check("§1 the flag takes NO argument (the project is picked IN the window)",
      MAIN.parse_launch_args(["--only-terminal", "/tmp/p.json"])["mode"] == MAIN.MODE_TERMINAL
      and "start_standalone()" in MAIN_SRC
      and clause(1, "takes **NO** argument"))
check("§1 an unknown `--flag` is ONE warning and never stops the launch",
      "Unknown launch option(s) ignored" in MAIN_SRC
      and MAIN.parse_launch_args(["--nope"])["unknown"] == ["--nope"]
      and clause(1, "reported as ONE warning in the log"))
check("§1 the standalone mode opens NO listener (no socket of any kind)",
      not any(word in (MAIN_SRC + TS_SRC) for word in ("QTcpServer", "QUdpSocket", "QLocalServer",
                                                       "bind(", "listen("))
      and clause(1, "the flag opens **NO** listener"))
check("§1 the exit code stays the shipped contract (a fatal startup exits 1)",
      "sys.exit(1)" in MAIN_SRC and "sys.exit(app.exec())" in MAIN_SRC
      and clause(1, "a fatal startup error exits **1**"))

# ════════════════════════════════════════════════════════════════════════════
print("== 2. the surface — the window without a map (§2) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the module owns the host, the window and the ONE entry point",
      "class StandaloneSurface" in TS_SRC
      and "class StandaloneTerminalWindow" in TS_SRC
      and callable(TS.start_standalone))
check("§2 the window IS the shipped container (a subclass), so every session feature is the shipped one",
      issubclass(TS.StandaloneTerminalWindow, ST.SSHTerminalWindow)
      and TS.StandaloneTerminalWindow.CONTAINER_KIND == "window"
      and clause(2, "The window IS `SSHTerminalWindow`"))
check("§2 the panel's hooks answer the HOST: `project_nodes()` and `connect_server()`",
      "def project_nodes" in TS_SRC and "def connect_server" in TS_SRC
      and "project_nodes" in _body("_panel_server_nodes")
      and "connect_server" in _body("_panel_connect_server"))
check("§2 no map hook is faked: the surface never answers a map name",
      all(name not in TS_SRC for name in ("def map_server_nodes", "def _run_ssh_connect",
                                          "def _raise_map_window")))
check("§2 the profile manager keeps the SHIPPED hook name (an application-level door)",
      "def _open_profile_manager" in TS_SRC
      and 'find_host_hook(self, "_open_profile_manager")' in WINDOW_SRC
      and clause(2, "`_open_profile_manager()` keeps the SHIPPED name"))
check("§2 the surface holds the ONE window it created and the run is a single-window one",
      "self.window" in TS_SRC and "quit_on_close" in WINDOW_SRC
      and "surface.window.show()" in _body("start_standalone"))
check("§2 closing the surface's window ENDS the run (the container is a child widget, not a window)",
      "quit_on_close = True" in TS_SRC
      and "if event.isAccepted() and self.quit_on_close:" in WINDOW_SRC
      and clause(2, "closing it ENDS the run"))
check("§2 the surface is HELD for the life of the run (a top-level widget nobody references dies early)",
      "app.standalone_surface = start_standalone()" in MAIN_SRC
      and "return surface" in _body("start_standalone")
      and clause(2, "**The surface is HELD for the life of the run.**"))

# ════════════════════════════════════════════════════════════════════════════
print("== 3. the source — a project file, read-only (§3) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 `PROJECT_SUFFIXES` is the ONE declaration and the map reads the SAME tuple",
      SP.PROJECT_SUFFIXES == (".json", ".sshmap")
      and 'PROJECT_SUFFIXES = (".json", ".sshmap")' in PROJECT_SRC
      and "PROJECT_DROP_SUFFIXES = PROJECT_SUFFIXES" in MAIN_WINDOW_SRC
      and clause(3, "`PROJECT_SUFFIXES` (`storage/project.py`) is the ONE declaration"))
check("§3 the reader is PURE, Qt-free and lives in `storage/project.py`",
      callable(SP.read_project_servers)
      and not any(name.startswith("PySide6") for name in imports_of(PROJECT_SRC)))
check("§3 the node conversion keeps ONE home (`server_data_from_dict`)",
      "server_data_from_dict(entry)" in _body("read_project_servers", PROJECT_SRC)
      and "ServerData(" not in _body("read_project_servers", PROJECT_SRC))
check("§3 the FILE ORDER is kept and a junk entry is DROPPED (never repaired)",
      "for entry in entries" in _body("read_project_servers", PROJECT_SRC)
      and "isinstance(entry, dict)" in _body("read_project_servers", PROJECT_SRC)
      and clause(3, "an entry that is not a JSON object is DROPPED"))
check("§3 a file without the array answers `[]` (an empty list is not an error)",
      "isinstance(entries, (list, tuple))" in _body("read_project_servers", PROJECT_SRC)
      and clause(3, "answers `[]` and is not an error"))
check("§3 READ-ONLY: the reader writes nothing and the surface never saves the project",
      "publish_atomic" not in _body("read_project_servers", PROJECT_SRC)
      and not any(name.endswith("autosave") for name in TS_IMPORTS)
      and all(word not in TS_SRC for word in ("save_project", "write_project_json",
                                              "serialize_scene", "last_project_path"))
      and clause(3, "**READ-ONLY**"))
check("§3 the list is re-read ONCE per `Open project` (no watcher, no polling)",
      "def open_project" in TS_SRC and "QFileSystemWatcher" not in TS_SRC
      and "QTimer" not in TS_SRC and clause(3, "ONCE per `Open project`"))

# ════════════════════════════════════════════════════════════════════════════
print("== 4. what is IN — the shipped terminal, untouched (§4) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§4 the contract carries the IN list as bullets (the shipped feature families)",
      all(needle in CONTRACT_TEXT for needle in ("The session:", "The containers:", "The files:",
                                                 "The input:", "The guards:", "The doors:")))
check("§4 the container keeps the shipped features (the split, the Files panel, the multi-input hub)",
      ST.SSHTerminalWindow.ALLOWS_NO_SESSIONS is False
      and "self.split = TerminalSplit(self)" in WINDOW_SRC
      and "self.files_panel = _FilesPanel(self)" in WINDOW_SRC
      and "multi_input" in WINDOW_SRC)
check("§4 the connect dialog and the profile manager are the SHIPPED ones (no second implementation)",
      "SSHConnectDialog" in TS_SRC and "ProfileManagerDialog" in TS_SRC
      and "production_guard" not in TS_SRC and "command_guard" not in TS_SRC)
check("§4 the surface adds NO terminal code of its own (no canvas, no page, no screen)",
      all(name not in TS_SRC for name in ("TerminalWidget(", "TerminalSessionPage(", "TerminalScreen(",
                                          "SSHTerminalThread(")))

# ════════════════════════════════════════════════════════════════════════════
print("== 5. what is OUT — the frozen list (§5) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§5 the OUT list is written as the frozen list (the specification, not a wish)",
      "**The standalone builds NO map.**" in CONTRACT_TEXT
      and "The list is the specification, not a wish" in CONTRACT_TEXT)
check("§5 the OUT list is enforced by the IMPORTS: no engine of the map is even reachable",
      not any(name.split(".")[-1] in {"plugin_manager", "status_checker", "autosave",
                                      "system_info_collector", "undo_commands", "plugin_runner",
                                      "export_problems", "export_connections", "export_drawio",
                                      "main_window", "autosave"}
              or name.startswith("graphics") or name.startswith("ui.main_window")
              for name in TS_IMPORTS), sorted(TS_IMPORTS))
check("§5 no plugin discovery and no Plugins window are named by the surface",
      "start_plugin_discovery" not in TS_SRC and "PluginManager" not in TS_SRC
      and "plugins_panel" not in TS_SRC and clause(5, "no plugin discovery"))
check("§5 no status probe, no reachability check and no info collection exist on this surface",
      all(word not in TS_SRC for word in ("StatusChecker", "probe_ssh", "SystemInfoCollector",
                                          "InfoBatch"))
      and clause(5, "no status probes") and clause(5, "no info collection"))
check("§5 no autosave, no backup ring and no project recovery",
      clause(5, "no autosave, no backup ring and no project recovery")
      and not any(name.endswith("autosave") for name in TS_IMPORTS))
check("§5 no undo stack: the ONE in-memory edit is the connect dialog's own fields",
      "undo_commands" not in TS_IMPORTS
      and all(word not in _code_of("connect_server") + _code_of("_apply_dialog_fields")
              for word in ("QUndoStack", "_push_command", "CmdEditNodeData"))
      and clause(5, "no undo/redo stack"))
check("§5 no MRU and no `last_project_path` (the surface remembers ONE file, in memory only)",
      "recent_projects" not in TS_SRC and "last_project_path" not in TS_SRC
      and clause(5, "no MRU"))
check("§5 no map export and no inventory surface is imported",
      not any(name.startswith("storage.export") for name in TS_IMPORTS)
      and "export_problems" not in TS_SRC and clause(5, "no map exports"))
check("§5 the §4.1 cycle rule holds: no graphics/ and no ui.main_window import anywhere",
      not any(name.startswith("graphics") or name.startswith("ui.main_window")
              for name in TS_IMPORTS))

# ════════════════════════════════════════════════════════════════════════════
print("== 6. the window — zero sessions, and the last tab (§6) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§6 `server_data` is OPTIONAL on the container (None = a window with no node)",
      'def __init__(self, server_data: "ServerData | None" = None' in WINDOW_SRC
      and "if server_data is not None:" in WINDOW_SRC
      and clause(6, "`SSHTerminalWindow.server_data` is **OPTIONAL**"))
check("§6 `ALLOWS_NO_SESSIONS` is the ONE predicate of the empty container",
      "ALLOWS_NO_SESSIONS = False" in WINDOW_SRC
      and TS.StandaloneTerminalWindow.ALLOWS_NO_SESSIONS is True
      and WINDOW_SRC.count("ALLOWS_NO_SESSIONS") >= 3
      and clause(6, "**`ALLOWS_NO_SESSIONS`**"))
check("§6 the LAST tab closes the window only where the flag is False",
      "if self.session_tabs.count() == 0 and not self.ALLOWS_NO_SESSIONS:" in WINDOW_SRC
      and clause(6, "the LAST tab closes it"))
check("§6 a zero-session window names the surface and carries the permanent sentence",
      "terminal.standalone.title" in WINDOW_SRC
      and "terminal.standalone.empty_hint" in WINDOW_SRC
      and "addPermanentWidget(self._empty_label)" in WINDOW_SRC
      and clause(6, "the title is `terminal.standalone.title`"))
check("§6 the empty state is written by ONE method (the two ends of a session's life call it)",
      "def _sync_empty_state" in WINDOW_SRC
      and WINDOW_SRC.count("self._sync_empty_state()") >= 3
      and "act_split" in _body("_sync_empty_state", WINDOW_SRC)
      and clause(6, "The panel keeps its OWN tail"))
check("§6 every shipped bridge handles \"no current page\" (page / active_session answer None)",
      "def page(self)" in WINDOW_SRC
      and "def active_session(self)" in WINDOW_SRC
      and "self.session_tabs.currentChanged.connect(self._on_current_tab_changed)" in WINDOW_SRC
      and clause(6, "`page` / `active_session` answer `None`"))
check("§6 the split refuses an EMPTY container instead of building a node-less pane",
      "if data is None:" in SPLIT_SRC and "an EMPTY container" in SPLIT_SRC
      and clause(6, "closing the last tab never closes the standalone"))

# ════════════════════════════════════════════════════════════════════════════
print("== 7. the bottom row — `Open project` / `Profiles` (§7) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§7 `set_project_door()` is the ONE installation point of the first control's project form",
      "def set_project_door" in PANEL_SRC and "def project_mode" in PANEL_SRC
      and "set_project_door(self._panel_open_project)" in TS_SRC
      and clause(7, "`CommandLibraryPanel.set_project_door(open_project)`"))
check("§7 the project form WINS over an installed map door (ONE predicate, ONE route)",
      "if self.project_mode():" in _body("_on_open_map", PANEL_SRC)
      and "project_mode" in _body("_apply_container_door", PANEL_SRC)
      and clause(7, "**WINS** over whatever map door"))
check("§7 the dock predicate is unchanged (`CONTAINER_KIND is CONTAINER_DOCK`)",
      "def map_is_this_window" in PANEL_SRC
      and "return self.container_kind() == CONTAINER_DOCK" in PANEL_SRC
      and clause(7, "The dock predicate is unchanged"))
check("§7 `Open project` goes through `QFileDialog` and a cancelled dialog changes NOTHING",
      "QFileDialog.getOpenFileName" in TS_SRC and "if not chosen:" in _body("open_project")
      and clause(7, "A cancelled dialog changes NOTHING"))
check("§7 a loaded project answers ONE status line and a failed file keeps the PREVIOUS list",
      "terminal.standalone.project_opened" in TS_SRC
      and "terminal.standalone.project_failed" in TS_SRC
      and "return False" in _body("open_project")
      and clause(7, "leaves the previous list ALONE"))
check("§7 an inactive `Servers` head explains itself inline with the project sentence",
      "terminal.cmdlib.no_project" in PANEL_SRC
      and "self.project_mode()" in _body("_hint_text", PANEL_SRC)
      and "if not self.servers_available():" in _body("_hint_text", PANEL_SRC)
      and clause(7, "INLINE with `terminal.cmdlib.no_project`"))
check("§7 an EMPTY project keeps the head usable and shows its own empty state",
      "terminal.cmdlib.project_empty" in PANEL_SRC
      and "self.project_mode()" in _body("_apply_filter", PANEL_SRC)
      and clause(7, "`terminal.cmdlib.project_empty`"))
check("§7 a provider that answers `None` is \"nothing to list YET\" — the ONE availability question",
      "self._servers_ready" in PANEL_SRC
      and "and self._servers_ready" in _body("servers_available", PANEL_SRC)
      and "if answer is not None:" in _body("_rebuild_servers", PANEL_SRC)
      and clause(7, "there is nothing to list YET"))

# ════════════════════════════════════════════════════════════════════════════
print("== 8. the credentials — the keyring binding, never a file (§8) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§8 the unmanaged gate comes FIRST — no dialog is built for such a node",
      _door_order() == ["is_unmanaged", "SSHConnectDialog", "add_session"]
      and "status.unmanaged_blocked" in TS_SRC
      and clause(8, "the unmanaged gate FIRST"))
check("§8 the door builds the SHIPPED `SSHConnectDialog` for the ROW's own node",
      "SSHConnectDialog(data, self.window)" in TS_SRC
      and clause(8, "the SHIPPED `SSHConnectDialog` for the row's own `ServerData`"))
check("§8 a refused or cancelled dialog opens NO session and writes NOTHING",
      "if dlg.exec() != QDialog.DialogCode.Accepted:" in TS_SRC
      and "return False" in _body("connect_server")
      and clause(8, "opens NO session and writes NOTHING"))
check("§8 the dialog's fields go onto the node DIRECTLY (no undo stack on this surface)",
      "def _apply_dialog_fields" in TS_SRC
      and "data.user = user" in TS_SRC and "data.ssh_port = port" in TS_SRC
      and clause(8, "**directly**"))
check("§8 the password: the dialog's field first, the endpoint-bound keyring record after",
      "password_edit.text()" in TS_SRC and "or self._stored_password(data)" in TS_SRC
      and "node_scope" in TS_SRC and "load_password" in TS_SRC
      and clause(8, "the endpoint-bound keyring record is read"))
check("§8 a password is NEVER serialized, logged or shown (the §4.4 rule)",
      "password" not in _body("_notify")
      and '"password"' not in TS_SRC
      and all("password" not in line for line in TS_SRC.splitlines() if "log." in line)
      and clause(8, "**A project file never carries a password**"))

# ════════════════════════════════════════════════════════════════════════════
print("== 9. the sentences and the keys (§9) ==")
# ════════════════════════════════════════════════════════════════════════════

_KEYS = ("terminal.standalone.title", "terminal.standalone.empty_hint",
         "terminal.standalone.project_opened", "terminal.standalone.project_failed",
         "terminal.standalone.project_filter", "terminal.standalone.all_files",
         "terminal.cmdlib.open_project", "terminal.cmdlib.open_project_tooltip",
         "terminal.cmdlib.no_project", "terminal.cmdlib.project_empty")
check("§9 the TEN keys of the contract are the keys the code really reads",
      all(k in (TS_SRC + PANEL_SRC + WINDOW_SRC + MAIN_SRC) for k in _KEYS)
      and CONTRACT_TEXT.count("`terminal.") >= len(_KEYS))
check("§9 every key exists in EVERY language (the strict parity of §4.5)",
      all(LANGS[c].get(k) for c in LANGS for k in _KEYS),
      str({c: [k for k in _KEYS if not LANGS[c].get(k)] for c in sorted(LANGS)}))
check("§9 the filter's suffixes come from the CODE, never from a translation",
      "PROJECT_SUFFIXES" in _body("project_filter_text")
      and all("*.json" not in str(LANGS[c].get("terminal.standalone.project_filter")) for c in LANGS)
      and clause(9, "`{patterns}` is filled from `PROJECT_SUFFIXES`"))
check("§9 the shipped sentences the contract names are the ones the code uses",
      all(key in TS_SRC for key in ("terminal.session_new_tab", "status.unmanaged_blocked",
                                    "status.profile_updated"))
      and "terminal.window_title" in WINDOW_SRC)

# ════════════════════════════════════════════════════════════════════════════
print("== 10. acceptance (§10) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§10 the topical file and this clause audit both ship",
      os.path.isfile(os.path.join(ROOT, "tests", "test_terminal_standalone.py"))
      and clause(10, "tests/test_terminal_standalone.py"))
check("§10 0 changes to the project format and no new dependency",
      __import__("version").VERSION_FORMAT == "0.9"
      and all(f"{d}>=" in _text("requirements.txt")
              for d in ("PySide6", "paramiko", "keyring", "wcwidth"))
      and clause(10, "**0 changes to the project format**"))
check("§10 the documents the contract promises exist and name the surface",
      "TERMINAL_STANDALONE.md" in _text("AGENTS.md")
      and "standalone" in README_SRC.lower()
      and clause(10, "`README.md` §Features"))
check("§10 the internal documents stay internal (the closed world of §13)",
      "TERMINAL_STANDALONE.md" in _text(".gitignore")
      and "TERMINAL_STANDALONE.md" not in README_SRC)
check_release_state(ROOT)

if docs_mode():
    check("§10 the mechanism section of `DOCUMENTATION.md` is the LAST one and names this surface",
          "#### 75." in rep_doc_text("DOCUMENTATION.md")
          and "TERMINAL_STANDALONE.md" in rep_doc_text("DOCUMENTATION.md"))
else:
    print("  SKIP  the mechanism section is audited under --docs "
          "(python tests/run_all.py --docs)")

finish()
