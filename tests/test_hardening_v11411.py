# -*- coding: utf-8 -*-
"""v1.14.1.1 — THE FACTS THAT MUST NOT LIE: the six defects of the shipped `v1.14.1` (N146–N150, N155).
§1 the reader OWNS `Ctrl+F` (`ViewerTextView` + `QEvent.ShortcutOverride`, no `QShortcut`, a live
window in BOTH display modes); §2 the properties dialog round-trips the five collected facts it has
no widget for; §3 the ONE `finite_number()` gate over the four readers that turn a stored value into
a colour, a brightness or a byte cap; §4 the applied background answers the ASKING pane; §5 the
build-time refusal waits until a receiver exists; §6 `uname -s` as its OWN fact; §7 the release pins.
Rule — `AGENTS.md` §4.3.4, §4.15; mechanism — `DOCUMENTATION.md` §38, §14a.
Run: python tests/test_hardening_v11411.py
"""
import json
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     merge_cfg, read_cfg, releases_at_least, wait_for, write_cfg)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QAction, QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import models.server as MS  # noqa: E402
import modules.sftp_pane_helpers as PH  # noqa: E402
import modules.sftp_pane_verbs as SVV  # noqa: E402
import modules.sftp_tab as ST  # noqa: E402
import modules.terminal_background as TB  # noqa: E402
import services.system_info_collector as SIC  # noqa: E402
import ui.main_window as MW  # noqa: E402
import ui.theme as theme_module  # noqa: E402
import ui.theme_qss as theme_qss  # noqa: E402
from _fakes import FakeSSHThread  # noqa: E402
from dialogs.add_server_dialog import AddServerDialog  # noqa: E402
from models.server import ServerData  # noqa: E402

import modules.ssh_terminal as SHT  # noqa: E402

SHT.SSHTerminalThread = FakeSSHThread   # every page/window of this file — on the fake
if hasattr(ST, "SSHTerminalThread"):
    ST.SSHTerminalThread = FakeSSHThread

LANGS = load_i18n_langs(ROOT)


def make_pane():
    """A bare Files container with ONE pane (no worker, no session) — the widget-level seam."""
    tab = ST.SftpTab()
    return tab, tab._active_pane


def key_event(kind, key=Qt.Key.Key_F, modifiers=Qt.KeyboardModifier.ControlModifier):
    """ONE synthetic key event of the reader's own gesture (the class under test reads it)."""
    return QKeyEvent(QEvent.Type(kind), key, modifiers)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 N146 — the reader OWNS `Ctrl+F` (no shortcut, no ambiguity) ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
tab, pane = make_pane()
check("§1 the reader's text IS the subclass that owns the key (the shipped `QPlainTextEdit` is not)",
      isinstance(pane.viewer_text, SVV.ViewerTextView)
      and isinstance(pane.viewer_text, ST.REEXPORTED_QT[5]),   # QPlainTextEdit — the same widget
      type(pane.viewer_text).__name__)
check("§1 ...and the widget-scoped shortcut object is GONE (it made Qt 6.11 ambiguous with "
      "`view.find_on_map`)", not hasattr(pane, "_viewer_find_shortcut")
      and not hasattr(pane.viewer_text, "activated"), type(pane.viewer_text).__name__)
_override = key_event(QEvent.Type.ShortcutOverride)
QApplication.sendEvent(pane.viewer_text, _override)
check("§1 the text ACCEPTS the ShortcutOverride of its own `Ctrl+F` (the key is taken OUT of the "
      "shortcut map's way)", _override.isAccepted())
_other = key_event(QEvent.Type.ShortcutOverride, Qt.Key.Key_S)
QApplication.sendEvent(pane.viewer_text, _other)
check("§1 ...and refuses nothing else — a foreign key keeps the window's own shortcut",
      not _other.isAccepted())

TEXT = "alpha one\nbeta two\nALPHA three\ngamma\n"
pane._show_viewer("/tmp/notes.txt", len(TEXT), TEXT)
_requests = []
pane.viewer_text.find_requested.connect(lambda: _requests.append(1))
QApplication.sendEvent(pane.viewer_text, key_event(QEvent.Type.KeyPress))
check("§1 the key press reaches the pane as `find_requested` and opens the bar over the document",
      _requests == [1] and pane.viewer_find_active is True, str(_requests))
pane.close_viewer_find()
QApplication.sendEvent(pane.viewer_text, key_event(QEvent.Type.KeyPress))
check("§1 ...and the SAME key opens it again (`Esc` closed it; the bar starts empty, never stale)",
      _requests == [1, 1] and pane.viewer_find_active is True and pane.viewer_find_state()["query"] == "",
      str((_requests, pane.viewer_find_state())))
tab.release()

# ── the LIVE window: the gesture really opens the bar and the map search stays silent ──
clear_cfg()
_mw = MW.MainWindow()
_mw._autosave_timer.stop()
_mw.show()
app.processEvents()
_node = _mw.scene.add_server(ServerData(id="cf1", alias="cf", host="10.99.1.1", user="root"))
_win = _mw._spawn_terminal_window(_node, password="pw")
app.processEvents()


def map_search_actions():
    """The window's `Find on Map…` actions (the exact text the menubar built)."""
    return [action for action in _mw.findChildren(QAction)
            if action.text() == i18n.t("view.find_on_map")]


def ctrl_f(window_reader):
    """Focus the reader and press `Ctrl+F` through the window's REAL key path."""
    fired = []
    for action in map_search_actions():
        action.triggered.connect(lambda _checked=False: fired.append(action))
    window_reader.viewer_text.setFocus()
    QTest.keyClick(window_reader.viewer_text, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    return fired


check("§1 the live window's reader is the owning subclass",
      isinstance(_win.page.sftp_tab._active_pane.viewer_text, SVV.ViewerTextView))
_reader = _win.page.sftp_tab._active_pane
_reader._show_viewer("/etc/app.conf", 24, "alpha beta\nALPHA gamma\n")
_fired = ctrl_f(_reader)
check("§1 a live window: `Ctrl+F` opens the reader's find bar (tabs/windows mode)", 
      _reader.viewer_find_active is True, str(_reader.viewer_find_state()))
check("§1 ...and the map search does NOT fire for it (no `Ambiguous shortcut overload`)",
      _fired == [], f"find_on_map fired {len(_fired)}×")
_reader.close_viewer_find()
_mw._dirty = False
_mw._undo_baseline_dirty = False
_mw.close()
app.processEvents()

# ── the DOCKED variant: the same key in the "tabs" display mode ──
clear_cfg()
merge_cfg({"terminal_mode": "tabs"})
_mw2 = MW.MainWindow()
_mw2._autosave_timer.stop()
_mw2.show()
app.processEvents()
_node2 = _mw2.scene.add_server(ServerData(id="cf2", alias="cf2", host="10.99.1.2", user="root"))
_dock = _mw2._spawn_terminal_window(_node2, password="pw")
app.processEvents()
_page = _dock.content.session_tabs.currentWidget()
_docked = _page.sftp_tab._active_pane
_docked._show_viewer("/etc/docked.conf", 12, "alpha beta\n")
_fired2 = ctrl_f(_docked)
check("§1 the DOCKED Files tab owns `Ctrl+F` too (the mode the shipped release broke)",
      _docked.viewer_find_active is True and _fired2 == [],
      f"active={_docked.viewer_find_active} fired={len(_fired2)}")
_docked.close_viewer_find()
_mw2._dirty = False
_mw2._undo_baseline_dirty = False
_mw2.close()
app.processEvents()
clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== §2 N147 — the properties dialog carries the five collected facts ==")
# ════════════════════════════════════════════════════════════════════════════

_FACTS = ServerData(id="dl1", alias="facts", host="10.0.0.7", user="root", ssh_port=2222,
                    os_name="Ubuntu 24.04 LTS", cpu_model="Xeon", cpu="4", ram="8 gb",
                    disk="100 gb", disk_path="/opt", kernel_name="Linux", disk_inodes="12%",
                    disk_note="missing", disk_device_note="device-missing",
                    info_collected_at=1700000000.0)
_dialog = AddServerDialog(edit_data=_FACTS)
_round = _dialog.get_data()
check("§2 the KERNEL fact survives a properties edit (the `Network ▸` row's ONE gate)",
      _round.kernel_name == "Linux", repr(_round.kernel_name))
check("§2 the inode fact, the two refusal NOTES and the DATE survive it too",
      (_round.disk_inodes, _round.disk_note, _round.disk_device_note) == ("12%", "missing",
                                                                         "device-missing")
      and _round.info_collected_at == 1700000000.0,
      str((_round.disk_inodes, _round.disk_note, _round.disk_device_note,
           _round.info_collected_at)))
check("§2 ...beside the facts the dialog DOES show (an edit changes only what it edits)",
      (_round.os_name, _round.cpu_model, _round.disk_path, _round.ssh_port)
      == ("Ubuntu 24.04 LTS", "Xeon", "/opt", 2222),
      str((_round.os_name, _round.cpu_model, _round.disk_path, _round.ssh_port)))
check("§2 the date is the LAST collection's — the edit never re-dates a measured figure",
      _round.info_collected_at != 0.0 and _round.info_collected_at == _FACTS.info_collected_at)
_fresh = AddServerDialog().get_data()
check("§2 a NEW card carries no phantom facts (a field with no widget starts empty)",
      _fresh.kernel_name == "" and _fresh.disk_inodes == "" and _fresh.disk_note == ""
      and _fresh.disk_device_note == "" and _fresh.info_collected_at == 0.0,
      str((_fresh.kernel_name, _fresh.disk_inodes, _fresh.info_collected_at)))
check("§2 the dialog keeps the object it was given (no half-written copy)",
      _dialog._data is _FACTS)

# ════════════════════════════════════════════════════════════════════════════
print("== §3 N148 — ONE finite-number gate over the four readers ==")
# ════════════════════════════════════════════════════════════════════════════

_INF, _NAN = float("inf"), float("nan")
check("§3 `finite_number()` refuses NaN, ±inf, a bool and every foreign value — never raises",
      all(MS.finite_number(value) is None
          for value in (_INF, -_INF, _NAN, True, False, "abc", None, [1], {"v": 2})),
      str([MS.finite_number(value) for value in (_INF, _NAN, True, "abc", None)]))
check("§3 ...and answers the number itself (a numeric string included — the readers judge the range)",
      MS.finite_number(142) == 142.0 and MS.finite_number("142") == 142.0
      and MS.finite_number(359.4) == 359.4 and MS.finite_number(0) == 0.0,
      str([MS.finite_number(value) for value in (142, "142", 359.4, 0)]))
check("§3 `json.load()` really hands a hand-edited `1e999` over as an infinity (the way in)",
      json.loads('{"ui_viewer_background": 1e999}')["ui_viewer_background"] == _INF
      and json.loads('{"ui_viewer_background": Infinity}')["ui_viewer_background"] == _INF)
check("§3 reader 1 — a non-finite hue is REFUSED (never an `OverflowError` out of the Files tab)",
      PH.viewer_background_hue(_INF) == (None, True)
      and PH.viewer_background_hue(-_INF) == (None, True)
      and PH.viewer_background_hue(_NAN) == (None, True)
      and PH.resolve_viewer_background({"ui_viewer_background": _INF}) == (None, True),
      str(PH.viewer_background_hue(_INF)))
check("§3 ...and the shipped hue rule is unchanged (a refused range, a rounded float)",
      PH.viewer_background_hue(142) == (142, False) and PH.viewer_background_hue(359.4) == (359, False)
      and PH.viewer_background_hue(400) == (None, True) and PH.viewer_background_hue(True) == (None, True))
check("§3 reader 2 — the colour derivation answers the BASE instead of raising",
      theme_qss.viewer_background_hex(_INF, theme_module.DARK.base_bg) == theme_module.DARK.base_bg
      and theme_qss.viewer_background_hex(_NAN, theme_module.DARK.base_bg)
      == theme_module.DARK.base_bg
      and theme_qss.viewer_background_hex("nope", theme_module.DARK.base_bg)
      == theme_module.DARK.base_bg)
check("§3 reader 3 — the read cap refuses an infinity with the DECLARED floor",
      ST.clamp_viewer_max_bytes(_INF) == ST.VIEWER_MAX_BYTES_MIN
      and ST.clamp_viewer_max_bytes(-_INF) == ST.VIEWER_MAX_BYTES_MIN
      and ST.clamp_viewer_max_bytes(_NAN) == ST.VIEWER_MAX_BYTES_MIN
      and ST.resolve_viewer_max_bytes({"ui_viewer_max_bytes": _INF}) == ST.VIEWER_MAX_BYTES_MIN,
      str(ST.clamp_viewer_max_bytes(_INF)))
check("§3 ...and the shipped cap rule is unchanged (a clamp, a floor, a default)",
      ST.clamp_viewer_max_bytes(10 ** 12) == ST.VIEWER_MAX_BYTES_MAX
      and ST.clamp_viewer_max_bytes(0) == ST.VIEWER_MAX_BYTES_MIN
      and ST.clamp_viewer_max_bytes("nonsense") == ST.VIEWER_MAX_BYTES_MIN
      and ST.clamp_viewer_max_bytes(True) == ST.VIEWER_MAX_BYTES_MIN)
check("§3 reader 4 — the wallpaper opacity refuses an infinity with the DECLARED default",
      TB.resolve_background_opacity(_INF) == TB.BACKGROUND_OPACITY_DEFAULT
      and TB.resolve_background_opacity(-_INF) == TB.BACKGROUND_OPACITY_DEFAULT
      and TB.resolve_background_opacity(_NAN) == TB.BACKGROUND_OPACITY_DEFAULT
      and TB.load_background_settings({"terminal_background_opacity": _INF})["opacity"]
      == TB.BACKGROUND_OPACITY_DEFAULT)
check("§3 ...and the shipped opacity rule is unchanged (clamped, rounded, foreign → default)",
      TB.resolve_background_opacity(150) == TB.BACKGROUND_OPACITY_MAX
      and TB.resolve_background_opacity(33.6) == 34
      and TB.resolve_background_opacity("50") == TB.BACKGROUND_OPACITY_DEFAULT
      and TB.resolve_background_opacity(True) == TB.BACKGROUND_OPACITY_DEFAULT)
write_cfg({"ui_viewer_background": _INF, "ui_viewer_max_bytes": _INF,
           "terminal_background_opacity": _INF})
_tab_inf, _pane_inf = make_pane()
check("§3 the Files tab BUILDS over a config of infinities (the shipped defect aborted the session)",
      _pane_inf.viewer_background_hue is None
      and _pane_inf._viewer_cap == ST.VIEWER_MAX_BYTES_MIN
      and str(theme_module.THEME.base_bg) in _pane_inf.viewer_text.styleSheet(),
      str((_pane_inf.viewer_background_hue, _pane_inf._viewer_cap)))
_tab_inf.release()
clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 N149 — the applied background answers the pane that ASKED ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
tab, pane = make_pane()
_messages = []
pane.message.connect(_messages.append)
_menu = pane._build_background_menu()
_cyan = [action for action in _menu.actions()
         if action.text() == i18n.t("settings.appearance.accent.cyan")]
_cyan[0].trigger()   # a preset row — the chip's OWN door
app.processEvents()
_CYAN_HUE = int(round(dict(PH.VIEWER_BACKGROUND_PRESETS)["cyan"]))
check("§4 the chip writes the ONE key and repaints the surface",
      read_cfg().get("ui_viewer_background") == _CYAN_HUE
      and pane.viewer_background_hue == _CYAN_HUE,
      str((read_cfg().get("ui_viewer_background"), pane.viewer_background_hue)))
check("§4 ...and the asking pane is ANSWERED with the ONE applied sentence",
      len(_messages) == 1
      and _messages[0] == i18n.t("sftp.viewer.background_applied",
                                 name=i18n.t("settings.appearance.accent.cyan")),
      str(_messages[-1:]))
check("§4 the sentence names the hue the surface really wears (ONE source, never two)",
      str(pane._viewer_background) == str(pane.viewer_background_hue))
_theme_row = _menu.actions()[0]
_theme_row.trigger()
app.processEvents()
check("§4 choosing the THEME answers the same one sentence (the refusal path is not the only one)",
      len(_messages) == 2 and read_cfg().get("ui_viewer_background") is None, str(_messages[-1:]))
tab.release()
clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== §5 N150 — the build-time refusal waits until a receiver exists ==")
# ════════════════════════════════════════════════════════════════════════════

write_cfg({"ui_viewer_background": "not-a-hue"})
_tab_bad = ST.SftpTab()
_refused = []
_tab_bad.message.connect(_refused.append)
_pane_bad = _tab_bad._active_pane
check("§5 the theme's own surface is what a refused value leaves behind (the paint is immediate)",
      _pane_bad.viewer_background_hue is None
      and str(theme_module.THEME.base_bg) in _pane_bad.viewer_text.styleSheet(),
      _pane_bad.viewer_text.styleSheet()[:60])
_felexed = wait_for(lambda: bool(_refused), timeout_ms=2000)
check("§5 the ONE refusal sentence reaches the container's listener (it was said before the wiring)",
      _felexed and _refused[-1] == i18n.t("sftp.viewer.background_refused"), str(_refused[-1:]))
check("§5 ...once — a second event-loop turn repeats nothing",
      (app.processEvents(), len(_refused))[-1] == 1, str(_refused))
_pane_bad._apply_stored_viewer_background()
check("§5 a RE-READ still answers synchronously (the seam a suite drives, unchanged)",
      len(_refused) == 2, str(_refused))
_tab_bad.release()
clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== §6 N155 — `uname -s` is its OWN fact, never a release name ==")
# ════════════════════════════════════════════════════════════════════════════

check("§6 the batch marks the kernel in its OWN section", "echo ---KERNEL---" in SIC.INFO_BATCH
      and "uname -srmo" in SIC.INFO_BATCH)
_kernel_index = SIC.INFO_BATCH.index("---KERNEL---")
_os_index = SIC.INFO_BATCH.index("---OS---")
check("§6 ...BEFORE the OS section, so the `uname` line never lands inside the release text",
      _kernel_index < _os_index)
check("§6 the KERNEL reader answers the first word of ITS OWN line",
      SIC.parse_kernel_name("Linux") == "Linux"
      and SIC.parse_kernel_name("Linux 6.8.0-31-generic x86_64 GNU/Linux") == "Linux"
      and SIC.parse_kernel_name('Linux\nPRETTY_NAME="Ubuntu 24.04 LTS"') == "Linux"
      and SIC.parse_kernel_name('PRETTY_NAME="Ubuntu 24.04 LTS"\nNAME="Ubuntu"') == ""
      and SIC.parse_kernel_name("") == "" and SIC.parse_kernel_name(None) == "",
      str([SIC.parse_kernel_name(v) for v in ("Linux", "Linux 6.8.0 x86_64 GNU/Linux",
                                              'PRETTY_NAME="Ubuntu 24.04 LTS"')]))
check("§6 a batch WITH the marker stores the kernel the marker answered",
      SIC.parse_info_output("---KERNEL---\nLinux 6.8.0-40-generic x86_64 GNU/Linux\n---OS---\n"
                            "Ubuntu 24.04 LTS\n---CPU---\n4\n").get("kernel_name") == "Linux")
check("§6 the SHIPPED shape (the `uname` line on top of `---OS---`) still answers — "
      "`test_reader_verbs.py` §4's batch",
      SIC.parse_uname_line("Linux 6.8.0-31-generic x86_64 GNU/Linux\n"
                           'PRETTY_NAME="Ubuntu 24.04 LTS"') == "Linux"
      and SIC.parse_info_output('---OS---\nLinux 6.8.0-31-generic x86_64 GNU/Linux\n'
                                'PRETTY_NAME="Ubuntu 24.04 LTS"\n---CPU---\n4\n---END---'
                                ).get("kernel_name") == "Linux")
_lsb = SIC.parse_info_output("---OS---\nUbuntu 24.04.1 LTS\n---CPU---\n4\n")
check("§6 the `lsb_release -ds` fallback is an OS NAME, never a kernel (N155's probe)",
      "kernel_name" not in _lsb and _lsb.get("os_name") == "Ubuntu 24.04.1 LTS", str(_lsb))
check("§6 ...and the shape gate is what refuses it (a release name matches the first two fields)",
      SIC.parse_uname_line("Ubuntu 24.04.1 LTS") == ""
      and SIC.parse_uname_line("junk") == ""
      and SIC.parse_uname_line("Darwin 23.4.0 arm64") == "Darwin"
      and SIC.parse_uname_line("FreeBSD 14.0-RELEASE amd64") == "FreeBSD")
check("§6 a node built from that collection is NOT Linux (the `Network ▸` gate reads the kernel)",
      not MS.is_linux_host(ServerData(id="k9", alias="a", host="h", user="u",
                                      **{k: v for k, v in _lsb.items() if k == "os_name"}))
      and MS.is_linux_host(ServerData(id="k10", alias="a", host="h", user="u",
                                      **{k: v for k, v in SIC.parse_info_output(
                                          "---KERNEL---\nLinux\n---OS---\nDebian 12\n").items()})))

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the release — no new key, no schema move, the pins ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§7 the patch adds NO key — the parity stays {EXPECTED_I18N_KEYS}",
      EXPECTED_I18N_KEYS == 1181 + 12, str(EXPECTED_I18N_KEYS))
check("§7 the pin names this release's line",
      releases_at_least(EXPECTED_APP_VERSION, "1.14.1"),
      EXPECTED_APP_VERSION)
check("§7 the schema did NOT move (the kernel fact is ONE additive field)",
      __import__("version").VERSION_FORMAT == "0.9")
check("§7 the reused sentences are still the shipped keys (the patch invents no message)",
      all(key in LANGS["en"] for key in ("sftp.viewer.background_applied",
                                         "sftp.viewer.background_refused")))

finish()
