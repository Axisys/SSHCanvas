# -*- coding: utf-8 -*-
"""v1.14rc4 — the container as a FACADE: the pane's assembly and the three `SftpTab` mixins.

§1 the MRO and the facade; §2 all 82 container names still answer on `SftpTab` (a table, not a
sample); §3 the forwarding pair and the QWidget overrides; §4 the className seams and the live
`host_attr` substitution; §5 the moved bodies are the shipped ones; §6 the behaviour the split must
not change and the release state.
"""
import ast
import os

from _common import (bootstrap, check, clear_cfg, finish, check_i18n_parity, check_i18n_format,
                     check_release_state, load_i18n_langs, pane_family_sources, pane_func_body,
                     pane_func_owner, EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

import modules.sftp_tab as ST  # noqa: E402
import modules.sftp_container_panes as SCP  # noqa: E402
import modules.sftp_container_session as SCS  # noqa: E402
import modules.sftp_container_viewer as SCV  # noqa: E402
import modules.sftp_pane_assembly as PASM  # noqa: E402
import modules.sftp_send as SEND  # noqa: E402
from ui.mixin_support import host_attr  # noqa: E402
from version import APP_VERSION, VERSION_FORMAT  # noqa: E402

LANGS = load_i18n_langs(ROOT)

#: the 82 names of the container, per owner — the ONE table this file audits (the plan's mapping)
FACADE = ["__init__", "release", "retranslate", "refresh_theme", "close_viewer", "resizeEvent",
          "_on_pane_splitter_moved", "_pane_for_widget", "eventFilter", "_pane_under_drag",
          "_forward_drag", "dragEnterEvent", "dragMoveEvent", "dropEvent", "__getattr__",
          "__setattr__"]
PANES = ["panes", "active_pane", "commander", "other_pane", "set_active_pane", "focus_pane",
         "focus_other_pane", "_sync_active_ring", "can_use_local", "can_elevate", "pane_source",
         "set_pane_source", "pane_for_provider", "relist_dir", "relist_pane", "_new_pane",
         "_destroy_pane", "_ensure_second_pane", "_close_viewer_of", "_sync_hint_rows",
         "set_commander", "commander_ratio", "_on_commander_moved", "_apply_commander_sizes",
         "commander_extra_config"]
SESSION = ["set_session_info", "session_key", "session_label", "session_user", "session_host",
           "session_data",   # v1.14.1: the LIVE node the reader's `Network ▸` gate reads
           "_sync_pane_headers", "set_worker", "worker", "set_transport", "transport",
           "remember_dir", "remembered_dir", "merge_dirs_into", "send_targets", "start_send",
           "_source_endpoint", "_send_asker", "_progress_reporter", "_finish_send", "cancel_sends",
           "_set_follow_checkbox", "_sync_follow_availability", "_on_follow_toggled",
           "set_follow_cwd", "follow_directory", "current_dir"]
VIEWER = ["preview_pane", "preview_source", "preview_in_other_pane", "preview_allowed",
          "present_viewer", "close_preview", "_restore_borrowed_viewer", "apply_viewer_wrap",
          "apply_viewer_encoding", "apply_viewer_max_bytes",
          # v1.14.1: the reader's verbs — the background walk and the `Network ▸` row
          "apply_viewer_background", "append_network_menu", "run_network_command",
          # v1.14.1.2: the hue the readers wear NOW — the answer of a write that was not STORED
          "_reader_hue"]
OWNERS = {"modules/sftp_container_panes.py": ("SftpContainerPanesMixin", SCP.SftpContainerPanesMixin,
                                              PANES),
          "modules/sftp_container_session.py": ("SftpContainerSessionMixin",
                                                SCS.SftpContainerSessionMixin, SESSION),
          "modules/sftp_container_viewer.py": ("SftpContainerViewerMixin",
                                               SCV.SftpContainerViewerMixin, VIEWER)}
#: the container's own MRO — the facade, its three mixins, `QWidget`, and the extract family after it
PLANNED_MRO = ["SftpTab", "SftpContainerPanesMixin", "SftpContainerSessionMixin",
               "SftpContainerViewerMixin", "QWidget"]
#: the QWidget overrides the container DELEGATES — each must be found before `QWidget` in the MRO
QT_OVERRIDES = ("eventFilter", "dragEnterEvent", "dragMoveEvent", "dropEvent", "resizeEvent")

_FAMILY = pane_family_sources(ROOT)
_FACADE_SRC = _FAMILY["modules/sftp_tab.py"]


def _owner_of(obj):
    """The `__qualname__` of a function OR of a property's getter."""
    return getattr(obj.fget if isinstance(obj, property) else obj, "__qualname__", "")


def _class_method_names(rel, cls):
    """Every method NAME a family file defines on `cls` (a property counts once)."""
    out = []
    for node in ast.parse(_FAMILY[rel]).body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            out.extend(sub.name for sub in node.body
                       if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return out


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the MRO, the facade and the three owners ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the container's MRO is the planned one (facade → three mixins → QWidget → the extract family)",
      [c.__name__ for c in ST.SftpTab.__mro__][:5] == PLANNED_MRO
      and "SftpExtractMixin" in [c.__name__ for c in ST.SftpTab.__mro__],
      str([c.__name__ for c in ST.SftpTab.__mro__]))
check("§1 the facade keeps its SIXTEEN names in its OWN dict (never a mixin's copy)",
      all(name in ST.SftpTab.__dict__ for name in FACADE),
      str([name for name in FACADE if name not in ST.SftpTab.__dict__]))
check("§1 ...and none of them is defined by a mixin as well (a second truth is a defect)",
      not [name for name in FACADE
           for _rel, (_n, cls, methods) in OWNERS.items() if name in cls.__dict__],
      str([name for name in FACADE
           for _rel, (_n, cls, methods) in OWNERS.items() if name in cls.__dict__]))
check("§1 the three mixins own the plan's 25 + 27 + 14 methods and define nothing else (v1.14.1 adds "
      "the session's `session_data` and the reader's three verbs; v1.14.1.2 the hue a failed write keeps)",
      [len(methods) for _r, (_n, _c, methods) in OWNERS.items()] == [25, 27, 14]
      and all(sorted(_class_method_names(rel, name)) == sorted(methods)
              for rel, (name, _cls, methods) in OWNERS.items()),
      str({rel: (len(_class_method_names(rel, name)), len(methods))
           for rel, (name, _cls, methods) in OWNERS.items()}))
check("§1 the facade's own class body holds exactly the 16 names the table declares",
      sorted(_class_method_names("modules/sftp_tab.py", "SftpTab")) == sorted(FACADE),
      str(sorted(set(_class_method_names("modules/sftp_tab.py", "SftpTab")) - set(FACADE)))
      + str(sorted(set(FACADE) - set(_class_method_names("modules/sftp_tab.py", "SftpTab")))))
check("§1 the plan's total is 82 methods — the number the release names (77 + v1.14.1's four + "
      "v1.14.1.2's one)",
      len(FACADE) + len(PANES) + len(SESSION) + len(VIEWER) == 82,
      str(len(FACADE) + len(PANES) + len(SESSION) + len(VIEWER)))
check("§1 the pane's assembly is the SEVENTH pane mixin and `__init__` is the assembly CALL",
      isinstance(PASM.SftpPaneAssemblyMixin, type)
      and issubclass(ST._SftpPane, PASM.SftpPaneAssemblyMixin)
      and "_build_pane_ui" not in ST._SftpPane.__dict__
      and "_build_pane_ui()" in pane_func_body("__init__", ROOT)
      and len(pane_func_body("__init__", ROOT).splitlines()) <= 6,
      pane_func_body("__init__", ROOT)[:160])


# ════════════════════════════════════════════════════════════════════════════
print("== §2 every one of the 82 names still answers on `SftpTab` ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
TAB = ST.SftpTab()
TAB.resize(900, 520)
TAB.show()
app.processEvents()
TAB.message.connect(lambda *_a: None)

_answered = []
for name in FACADE + PANES + SESSION + VIEWER:
    try:
        getattr(TAB, name)
        _answered.append(name)
    except AttributeError:
        continue
check(f"§2 all 82 container names ANSWER on the instance ({len(_answered)}/82)", len(_answered) == 82,
      str([n for n in FACADE + PANES + SESSION + VIEWER if n not in _answered]))
check("§2 ...and `hasattr` is honest about a name nobody owns",
      not hasattr(TAB, "_there_is_no_such_name_v114rc4"))
_owner_problems = []
for name in PANES + SESSION + VIEWER:
    fn = getattr(ST.SftpTab, name, None)
    if fn is None:
        _owner_problems.append(f"{name}: missing")
        continue
    owner = _owner_of(fn).split(".")[0]
    declared = [cls.__name__ for _rel, (_n, cls, methods) in OWNERS.items() if name in methods]
    if [owner] != declared:
        _owner_problems.append(f"{name}: owner {owner} != {declared}")
check("§2 ...each one resolves to its DECLARED mixin, method by method (the table, not a sample)",
      not _owner_problems, "; ".join(_owner_problems[:8]))
check("§2 ...and the AST reader of the family finds each body where it now lives",
      all(pane_func_owner(name, ROOT) for name, _rel in
          [(n, rel) for rel, (_n, _c, methods) in OWNERS.items() for n in methods]),
      str([n for rel, (_n, _c, methods) in OWNERS.items() for n in methods
           if not pane_func_owner(n, ROOT)][:6]))


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the forwarding pair and the QWidget overrides ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 `__getattr__` / `__setattr__` stay in the FACADE — the pair a mixin may never define",
      "__getattr__" in ST.SftpTab.__dict__ and "__setattr__" in ST.SftpTab.__dict__
      and not any("__getattr__" in cls.__dict__ or "__setattr__" in cls.__dict__
                  for _rel, (_n, cls, _m) in OWNERS.items()))
check("§3 ...and they are BEHIND the mixins in the MRO, so a moved name is found before forwarding",
      ST.SftpTab.__mro__.index(SCP.SftpContainerPanesMixin) < ST.SftpTab.__mro__.index(QWidget)
      and ST.SftpTab.__mro__.index(QWidget) < ST.SftpTab.__mro__.index(
          __import__("modules.sftp_extract", fromlist=["SftpExtractMixin"]).SftpExtractMixin))
check("§3 a shipped single-pane read resolves on the ACTIVE pane (`tab.tree`, `tab.path_label`)",
      TAB.tree is TAB.panes[0].tree and TAB.path_label is TAB.panes[0].path_label
      and TAB.splitter is TAB.panes[0].splitter)
_marker = {"probe": True}
TAB._blocked = _marker
check("§3 ...and a PANE-owned write lands on the pane, never on the container (one truth)",
      TAB.panes[0]._blocked is _marker and "_blocked" not in TAB.__dict__)
check("§3 every QWidget override is DELEGATED, and found BEFORE QWidget in the MRO",
      all(getattr(ST.SftpTab, name) is not getattr(QWidget, name) for name in QT_OVERRIDES),
      str([name for name in QT_OVERRIDES
           if getattr(ST.SftpTab, name) is getattr(QWidget, name)]))
check("§3 the container's own chrome answers the ACTIVE pane's drag family (the shipped seam)",
      TAB._pane_for_widget(TAB.tree.viewport()) is TAB.panes[0]
      and TAB._pane_for_widget(TAB.chk_follow_cwd) is TAB.active_pane)


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the declared seams and the live substitution ==")
# ════════════════════════════════════════════════════════════════════════════

_seams_raw = tuple(getattr(ST, "MODULE_FACADE_SEAMS", ()))
_NEW_SEAMS = ("_SftpPane", "_SftpTree", "_ButtonRow", "_SourceSwitch", "_sync_source_switch",
              "SORT_DEFAULT_COLUMN", "resolve_viewer_max_bytes", "focus_ring", "syntax",
              "COMMANDER_RATIO_MIN", "COMMANDER_RATIO_MAX", "COMMANDER_MIN_PANE_PX",
              "COMMANDER_CONFIG_BOOL", "COMMANDER_CONFIG_RATIO", "DIRS_CONFIG",
              "load_remembered_dirs", "remember_dir", "remembered_dir_for")
check("§4 the container's seams are DECLARED on the facade, by identity",
      all(any(seam is getattr(ST, name) for seam in _seams_raw) for name in _NEW_SEAMS),
      str([name for name in _NEW_SEAMS
           if not any(seam is getattr(ST, name) for seam in _seams_raw)]))
_SEAM_SRC = "".join(_FAMILY[rel] for rel in list(OWNERS) + ["modules/sftp_pane_assembly.py"])
check("§4 ...and each is REALLY resolved through `host_attr` where the mixin uses it",
      all(f'host_attr(self, "{name}")' in _SEAM_SRC
          or f'host_attr(self, "{name}",' in _SEAM_SRC for name in _NEW_SEAMS),
      str([name for name in _NEW_SEAMS
           if f'host_attr(self, "{name}")' not in _SEAM_SRC
           and f'host_attr(self, "{name}",' not in _SEAM_SRC]))
_sentinel = type("_Sentinel", (), {})
_orig_size = ST.format_size
try:
    ST.format_size = _sentinel
    check("§4 a swap on the facade is what the mixin sees (the test seam survives the move)",
          host_attr(TAB, "format_size") is _sentinel)
finally:
    ST.format_size = _orig_size
check("§4 the relay and the dirs memory are the SHIPPED objects the mixins resolve",
      SCS.send is SEND and callable(SCS.find_host_hook)
      and ST.DIRS_CONFIG == "ui_sftp_dirs" and callable(ST.remember_dir))
check("§4 no container mixin imports the facade (the cycle gate, on the two new globs)",
      all("sftp_tab import" not in _FAMILY[rel] and "import sftp_tab" not in _FAMILY[rel]
          for rel in list(OWNERS) + ["modules/sftp_pane_assembly.py"]))
check("§4 the Qt classes the assembly builds with stay readable on THIS module (the shipped path)",
      len(ST.REEXPORTED_QT) == 9
      and all(getattr(ST, cls.__name__) is cls for cls in ST.REEXPORTED_QT)
      and ST.QPlainTextEdit.LineWrapMode.NoWrap is not None,
      str([cls.__name__ for cls in ST.REEXPORTED_QT
           if getattr(ST, cls.__name__, None) is not cls]))


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the moved bodies are the shipped ones ==")
# ════════════════════════════════════════════════════════════════════════════

#: the two names the CONTAINER and the PANE both legitimately carry (the pane reads its session's
#: identity and its worker through the SAME spellings) — a `def` of them in the facade is not a copy
SHARED_WITH_THE_PANE = ("worker", "session_key")
check("§5 the three clusters landed in their own module (the facade defines none of them)",
      pane_func_owner("set_commander", ROOT) == "modules/sftp_container_panes.py"
      and pane_func_owner("set_worker", ROOT) == "modules/sftp_container_session.py"
      and pane_func_owner("apply_viewer_max_bytes", ROOT) == "modules/sftp_container_viewer.py"
      and not any(f"def {name}(" in _FACADE_SRC for name in PANES + SESSION + VIEWER
                  if name not in SHARED_WITH_THE_PANE),
      str([name for name in PANES + SESSION + VIEWER
           if name not in SHARED_WITH_THE_PANE and f"def {name}(" in _FACADE_SRC]))
check("§5 the bodies carry the shipped decisions, not a rewritten copy",
      "COMMANDER_RATIO_MIN" in pane_func_body("commander_extra_config", ROOT)
      and "ONE send per session pair" in pane_func_body("start_send", ROOT, docstring=True)
      and "panel_in_slot" not in pane_func_body("preview_pane", ROOT)
      and "self.pane_splitter.setSizes" in pane_func_body("_apply_commander_sizes", ROOT)
      and "_dirs_touched" in pane_func_body("merge_dirs_into", ROOT))
check("§5 the assembly body is the WHOLE of the old `__init__` (state, widgets, drag wiring)",
      all(marker in pane_func_body("_build_pane_ui", ROOT) for marker in
          ("_current_dir = ", "path_completer", "buttons_bar", "findChildren",
           "setAcceptDrops", "_build_pane_shortcuts", "_ring.apply()")))
check("§5 the pane facade keeps its OWN `__init__` and the container keeps its identity",
      pane_func_owner("bind_worker", ROOT) == "modules/sftp_tab.py"
      and pane_func_owner("__setattr__", ROOT) == "modules/sftp_tab.py"
      and "PANES_STATE_PLACEHOLDER" not in _FACADE_SRC)


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the behaviour the split must not change ==")
# ════════════════════════════════════════════════════════════════════════════

check("§6 a fresh tab is the ONE-pane container of the shipped listing",
      len(TAB.panes) == 1 and TAB.active_pane is TAB.panes[0] and TAB.commander is False)
check("§6 the two-pane mode puts the SECOND pane beside the first, in ITS directory",
      TAB.set_commander(True) and len(TAB.panes) == 2 and TAB._pane_b is TAB.panes[1]
      and TAB.panes[1].current_dir == TAB.panes[0].current_dir,
      f"panes={len(TAB.panes)}")
check("§6 the source gate answers the SECOND pane alone (the Commander's one question)",
      TAB.can_use_local(TAB.panes[1]) is True and TAB.can_use_local(TAB.panes[0]) is False
      and TAB.can_elevate(TAB.panes[1]) is True and TAB.can_elevate(TAB.panes[0]) is False)
check("§6 the preview slot routes in the two-pane mode (ONE preview, asked of the OWNER)",
      TAB.preview_pane() is None and TAB.preview_allowed(TAB.panes[0]) is True
      and TAB.preview_allowed(TAB.panes[1]) is True and TAB.close_preview() is False)
check("§6 the follow is REFUSED in the two-pane mode and forwarded in the single one",
      TAB.follow_directory("/tmp") is False)
check("§6 the live settings walk reaches EVERY pane (the settings hub's ONE call)",
      TAB.apply_viewer_encoding("cp1251") == "cp1251"
      and all(pane.viewer_encoding_choice == "cp1251" for pane in TAB.panes)
      and TAB.apply_viewer_max_bytes(4 * 1024 * 1024) == 4 * 1024 * 1024
      and all(pane.viewer_cap() == 4 * 1024 * 1024 for pane in TAB.panes))
check("§6 the Commander's config payload is the shipped pair of keys",
      set(TAB.commander_extra_config()) == {ST.COMMANDER_CONFIG_BOOL, ST.COMMANDER_CONFIG_RATIO})
_ratio = TAB.commander_ratio()
check("§6 ...and its ratio reader answers a real proportion (never 0 on a hidden member)",
      _ratio is None or 0.0 < _ratio < 1.0, str(_ratio))
check("§6 leaving the mode tears the second pane down and keeps the first",
      TAB.set_commander(False) and len(TAB.panes) == 1 and TAB._pane_b is None
      and TAB.active_pane is TAB.panes[0])
TAB.set_worker(None)
check("§6 the waiting state is the container's (`set_worker(None)` unbinds every pane)",
      TAB.worker is None and TAB.panes[0]._waiting is True)
TAB.release()
check("§6 `release()` is the ONE idempotent teardown (a second call is a no-op)",
      TAB.release() is None and TAB._released is True)

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check("§7 the split adds NO i18n key and NO schema move (1180 / 0.9)",
      EXPECTED_I18N_KEYS == 1180 + 1 + 12 + 3 and VERSION_FORMAT == "0.9",
      f"{EXPECTED_I18N_KEYS} / {VERSION_FORMAT}")
check("§7 the pin names this milestone", releases_at_least(EXPECTED_APP_VERSION, "1.14"),
      EXPECTED_APP_VERSION)
check("§7 the shipped version is the one the pin names", APP_VERSION == EXPECTED_APP_VERSION,
      f"{APP_VERSION} / {EXPECTED_APP_VERSION}")
check("§7 the facade is under 1 200 lines after the second part (2 297 before it)",
      len(_FACADE_SRC.splitlines()) < 1200, f"{len(_FACADE_SRC.splitlines())} lines")
check("§7 ...and the three mixins and the assembly stay under the 900-line band",
      all(len(_FAMILY[rel].splitlines()) < 900
          for rel in list(OWNERS) + ["modules/sftp_pane_assembly.py"]),
      str({rel: len(_FAMILY[rel].splitlines()) for rel in OWNERS}))
TAB.deleteLater()
finish()
