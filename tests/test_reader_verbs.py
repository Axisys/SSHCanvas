# -*- coding: utf-8 -*-
"""v1.14.1 — THE READER'S VERBS: the background hue, the find bar and the `Network ▸` row.

The topical test of the release: offscreen, no network (the fake SSH thread of `_fakes`). §1 the PURE
half — the hue reader with its refusal, the colour derivation and the presets; §2 the background of a
LIVE container (the key, the walk over the panes, the chip and the refused value); §3 the find bar
(`Ctrl+F`, the counter, next/previous with wraparound, `Esc`, a new file); §4 the KERNEL fact (`uname
-s` in the batch, the model field, the JSON round trip, the entry that writes it, the gate); §5 the
`Network ▸` row (the allowlist, its three commands, the Linux gate, the menu, the split's
`initial_command`, end to end); §6 i18n and the release state."""
import sys

from _common import (bootstrap, check, finish, wait_until, load_i18n_langs, check_i18n_parity,
                     check_i18n_format, check_release_state, clear_cfg, read_cfg, merge_cfg,
                     EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation + faulthandler)

from PySide6.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import models.server as MS  # noqa: E402
import modules.sftp_pane_helpers as PH  # noqa: E402
import modules.sftp_pane_verbs as SVV  # noqa: E402
import modules.sftp_tab as ST  # noqa: E402
import modules.terminal_split as SP  # noqa: E402
import services.system_info_collector as SIC  # noqa: E402
import ui.theme as theme  # noqa: E402
import ui.theme as theme_module  # noqa: E402 — the name the pane's chip reads
import ui.theme_qss as theme_qss  # noqa: E402
from models.server import ServerData  # noqa: E402
from _fakes import FakeSSHThread  # noqa: E402

ST.SSHTerminalThread = FakeSSHThread if hasattr(ST, "SSHTerminalThread") else None
import modules.ssh_terminal as SHT  # noqa: E402
import ui.main_window as MW  # noqa: E402

SHT.SSHTerminalThread = FakeSSHThread   # every page/window of this file — on the fake

LANGS = load_i18n_langs(ROOT)
NEW_KEYS = ("sftp.find.placeholder", "sftp.find.count", "sftp.find.prev", "sftp.find.next",
            "sftp.viewer.background", "sftp.viewer.background_theme",
            "sftp.viewer.background_applied", "sftp.viewer.background_refused",
            "sftp.network.menu", "sftp.network.ping", "sftp.network.trace", "sftp.network.reverse")


def make_pane():
    """A bare Files container with ONE pane (no worker, no session) — the widget-level seam."""
    tab = ST.SftpTab()
    return tab, tab._active_pane


def make_table(path, text):
    """Fill a pane's reader with `text` through the shipped show path (no worker needed)."""
    head, _, name = path.rpartition("/")
    pane = make_table.pane
    pane._show_viewer(path, len(text.encode("utf-8")), text)
    return pane


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the PURE half: the hue reader, the colour and the presets ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the key is the reader's own (`ui_viewer_background`)",
      PH.VIEWER_BACKGROUND_CONFIG == "ui_viewer_background")
check("§1 a hue in 0..359 is read as itself, with no refusal (a float rounds)",
      PH.viewer_background_hue(142) == (142, False)
      and PH.viewer_background_hue(0) == (0, False)
      and PH.viewer_background_hue(359.4) == (359, False),
      str([PH.viewer_background_hue(v) for v in (142, 0, 359.4)]))
check("§1 an ABSENT / null / blank value is the theme (no refusal — nothing was chosen)",
      all(PH.viewer_background_hue(v) == (None, False) for v in (None, "", "   ")),
      str([PH.viewer_background_hue(v) for v in (None, "", "   ")]))
check("§1 every other value is REFUSED, never clamped into a colour nobody chose",
      all(PH.viewer_background_hue(v) == (None, True)
          for v in ("abc", True, False, -1, 400, 360, [1], {"h": 3})),
      str([PH.viewer_background_hue(v) for v in ("abc", True, -1, 400, 360)]))
check("§1 the config reader resolves the key (a whole document with a foreign value refuses)",
      PH.resolve_viewer_background({"ui_viewer_background": 38}) == (38, False)
      and PH.resolve_viewer_background({"ui_viewer_background": "sky"}) == (None, True)
      and PH.resolve_viewer_background({}) == (None, False),
      str(PH.resolve_viewer_background({"ui_viewer_background": "sky"})))
check("§1 the writer stores the HUE and `null` for the theme (the merge-write of the family)",
      PH.save_viewer_background(38) is True
      and read_cfg().get("ui_viewer_background") == 38
      and PH.save_viewer_background(None) is True
      and "ui_viewer_background" in read_cfg()
      and read_cfg().get("ui_viewer_background") is None,
      str(read_cfg().get("ui_viewer_background")))
_BASE_DARK = theme.DARK.base_bg
_BASE_LIGHT = theme.LIGHT.base_bg
_DARK_GREEN = theme_qss.viewer_background_hex(142, _BASE_DARK)
_DARK_AMBER = theme_qss.viewer_background_hex(38, _BASE_DARK)
check("§1 the colour keeps the theme's LIGHTNESS and moves the HUE (the syntax ink stays readable)",
      _DARK_GREEN != _DARK_AMBER != _BASE_DARK
      and abs(theme_qss.QColor(_DARK_GREEN).lightness()
              - theme_qss.QColor(_BASE_DARK).lightness()) <= 2,
      f"{_DARK_GREEN} / {_DARK_AMBER} / base {_BASE_DARK}")
check("§1 ...and the LIGHT theme derives its own tone from ITS surface",
      theme_qss.viewer_background_hex(142, _BASE_LIGHT)
      != theme_qss.viewer_background_hex(142, _BASE_DARK)
      and theme_qss.QColor(theme_qss.viewer_background_hex(142, _BASE_LIGHT)).lightness() > 128,
      theme_qss.viewer_background_hex(142, _BASE_LIGHT))
check("§1 a foreign hue/base answers the base colour instead of raising",
      theme_qss.viewer_background_hex("nope", _BASE_DARK) == _BASE_DARK
      and theme_qss.viewer_background_hex(10, "not-a-colour") == "not-a-colour")
check("§1 eight presets, each named by an i18n key the Appearance tab already carries",
      len(PH.VIEWER_BACKGROUND_PRESETS) == 8
      and all(f"settings.appearance.accent.{name}" in LANGS["en"] for name, _h in
              PH.VIEWER_BACKGROUND_PRESETS),
      str([n for n, _h in PH.VIEWER_BACKGROUND_PRESETS]))
check("§1 the registry builds the reader's surface from that hue (the theme's own tone with none)",
      theme_qss.style("viewer.background")
      == f"QPlainTextEdit#SftpViewerText {{ background-color: {theme.DARK.base_bg}; }}"
      and merge_cfg({"ui_viewer_background": 142}) is None
      and "QPlainTextEdit#SftpViewerText" in theme_qss.style("viewer.background")
      and theme.DARK.base_bg not in theme_qss.style("viewer.background")
      and theme_qss.style("find_bar") == theme_qss.style("viewer_find_bar")
      and "TerminalFindBar" in theme_qss.style("viewer_find_bar"),
      theme_qss.style("viewer.background")[:70])
clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the background of a LIVE container (the key, both panes, the chip) ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
tab, pane = make_pane()
messages = []
pane.message.connect(messages.append)
check("§2 a fresh reader wears the theme (the registry's rule IS the theme's own surface)",
      pane.viewer_background_hue is None
      and pane.viewer_text.styleSheet() == theme_qss.style("viewer.background")
      and str(theme_module.THEME.base_bg) in pane.viewer_text.styleSheet()
      and pane.btn_viewer_background is not None,
      pane.viewer_text.styleSheet())
_applied = tab.apply_viewer_background(142, pane=pane)
check("§2 `apply_viewer_background()` writes the ONE key and returns the normalised hue",
      _applied == 142 and read_cfg().get("ui_viewer_background") == 142,
      str((_applied, read_cfg().get("ui_viewer_background"))))
check("§2 ...and walks EVERY pane of the container (the reader's surface follows)",
      all(p.viewer_text.styleSheet() == theme_qss.style("viewer.background")
          and p.viewer_background_hue == 142 for p in tab._panes),
      [p.viewer_text.styleSheet()[:40] for p in tab._panes])
check("§2 ...and answers the pane that asked with ONE sentence naming the choice",
      messages and messages[-1] == i18n.t("sftp.viewer.background_applied",
                                         name=i18n.t("settings.appearance.accent.green")),
      str(messages[-1:]))
check("§2 the chip shows the colour it installs (a themed chip, never a hardcoded one)",
      _DARK_GREEN or "#" in pane.btn_viewer_background.styleSheet()
      and "background-color" in pane.btn_viewer_background.styleSheet(),
      pane.btn_viewer_background.styleSheet()[:70])
tab.apply_viewer_background(None)
check("§2 choosing the THEME clears the key and returns the reader to the theme's tone",
      read_cfg().get("ui_viewer_background") is None
      and pane.viewer_text.styleSheet() == theme_qss.style("viewer.background")
      and str(theme_module.THEME.base_bg) in pane.viewer_text.styleSheet()
      and pane.viewer_background_hue is None,
      pane.viewer_text.styleSheet())
tab.release()

merge_cfg({"ui_viewer_background": "not-a-hue"})
tab2, pane2 = make_pane()
refusals = []
pane2.message.connect(refusals.append)
pane2._apply_stored_viewer_background()
check("§2 a stored value that is not a hue is REFUSED with ONE sentence (the theme stays)",
      i18n.t("sftp.viewer.background_refused") in refusals
      and pane2.viewer_background_hue is None
      and str(theme_module.THEME.base_bg) in pane2.viewer_text.styleSheet(),
      str(refusals[-1:]))
tab2.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the find bar: Ctrl+F, the counter, the wraparound, Esc ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
tab, pane = make_pane()
TEXT = "alpha one\nbeta two\nALPHA three\ngamma\n"
pane._show_viewer("/tmp/notes.txt", len(TEXT), TEXT)
check("§3 a closed reader has no bar (nothing is built until `Ctrl+F`)",
      pane.viewer_find_active is False and pane._viewer_find_bar is None)
check("§3 the TEXT owns the key (`ViewerTextView` accepts the ShortcutOverride; no `QShortcut`)",
      isinstance(pane.viewer_text, SVV.ViewerTextView)
      and not hasattr(pane, "_viewer_find_shortcut"),
      type(pane.viewer_text).__name__)
pane.open_viewer_find()
check("§3 `Ctrl+F` opens the bar as a ROW of the reader panel (never a floating child)",
      pane.viewer_find_active and pane._viewer_find_bar.parent() is pane.viewer
      and pane.viewer.layout().indexOf(pane._viewer_find_bar) == 1,
      str(pane.viewer.layout().indexOf(pane._viewer_find_bar)))
pane._on_viewer_find_query("alpha")
check("§3 the counter counts the WHOLE document, case-insensitively (2 of 3 lines)",
      pane.viewer_find_state() == {"query": "alpha", "current": 1, "total": 2},
      str(pane.viewer_find_state()))
check("§3 the first match is REVEALED (the selection is the highlight)",
      pane.viewer_text.textCursor().selectedText().lower() == "alpha")
check("§3 the counter's sentence is the bar's own key",
      pane._viewer_find_bar.count_label.text() == i18n.t("sftp.find.count", cur=1, total=2),
      pane._viewer_find_bar.count_label.text())
check("§3 Enter steps forward and WRAPS around",
      pane.viewer_find_next() and pane.viewer_find_state()["current"] == 2
      and pane.viewer_find_next() and pane.viewer_find_state()["current"] == 1,
      str(pane.viewer_find_state()))
check("§3 Shift+Enter steps BACKWARD with the same wraparound",
      pane.viewer_find_prev() and pane.viewer_find_state()["current"] == 2,
      str(pane.viewer_find_state()))
pane._on_viewer_find_query("nothing-like-it")
check("§3 a query with no hit says so (`search.no_results`), the run stays at zero",
      pane._viewer_find_bar.count_label.text() == i18n.t("search.no_results")
      and pane.viewer_find_state()["total"] == 0,
      pane._viewer_find_bar.count_label.text())
check("§3 ...and `Enter` answers False instead of moving",
      pane.viewer_find_next() is False and pane.viewer_find_prev() is False)
_MAX = SVV.VIEWER_FIND_MATCH_MAX
try:
    SVV.VIEWER_FIND_MATCH_MAX = 2
    pane._on_viewer_find_query("a")
    check("§3 the counter says the DECLARED bound (`2+`) instead of a number it stopped at",
          pane._viewer_find_bar.count_label.text().endswith("2+")
          and len(pane._viewer_find_matches) == 2,
          pane._viewer_find_bar.count_label.text())
finally:
    SVV.VIEWER_FIND_MATCH_MAX = _MAX
pane.close_viewer_find()
check("§3 Esc closes the bar and drops the matches",
      pane.viewer_find_active is False and pane.viewer_find_state()["total"] == 0)
pane.open_viewer_find()
pane._on_viewer_find_query("beta")
pane._show_viewer("/tmp/other.txt", 4, "beta")
check("§3 a NEW file resets the run (the matches indexed the previous document)",
      pane.viewer_find_state()["total"] == 0 and pane.viewer_find_state()["query"] == "",
      str(pane.viewer_find_state()))
pane._on_viewer_find_query("beta")
pane.close_viewer()
check("§3 closing the panel closes its bar too",
      pane.viewer_find_active is False and pane.viewer_find_state()["total"] == 0)
tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the KERNEL fact: `uname -s` in the batch, the field, the gate ==")
# ════════════════════════════════════════════════════════════════════════════

check("§4 the batch asks `uname` (the ONE line the fact comes from)",
      "uname -srmo" in SIC.INFO_BATCH)
check("§4 the parser reads the KERNEL name of that line",
      SIC.parse_kernel_name("Linux 5.15.0-91-generic x86_64 GNU/Linux\n"
                            'PRETTY_NAME="Ubuntu 24.04 LTS"') == "Linux"
      and SIC.parse_kernel_name("Darwin 23.4.0 arm64") == "Darwin"
      and SIC.parse_kernel_name("FreeBSD 14.0-RELEASE amd64") == "FreeBSD",
      SIC.parse_kernel_name("Linux 5.15.0-91-generic x86_64 GNU/Linux"))
check("§4 ...and never guesses one from `/etc/os-release` or an empty output",
      SIC.parse_kernel_name('PRETTY_NAME="Ubuntu 24.04 LTS"\nNAME="Ubuntu"') == ""
      and SIC.parse_kernel_name("") == "" and SIC.parse_kernel_name(None) == "")
_BATCH = ("---OS---\nLinux 6.8.0-31-generic x86_64 GNU/Linux\n"
          'PRETTY_NAME="Ubuntu 24.04 LTS"\n---CPU---\n4\nmodel name\t: AMD Ryzen\n'
          "---END---")
_info = SIC.parse_info_output(_BATCH)
check("§4 the collection carries BOTH facts (the PRETTY_NAME and the kernel)",
      _info.get("kernel_name") == "Linux" and _info.get("os_name") == "Ubuntu 24.04 LTS",
      str(_info))
check("§4 the model field is additive: absent = '', a foreign value loads as ''",
      ServerData(id="k1", alias="a", host="h", user="u").kernel_name == ""
      and MS.server_data_from_dict({"id": "k1", "kernel_name": 42}).kernel_name == ""
      and MS.server_data_from_dict({"id": "k1", "kernel_name": "  Linux "}).kernel_name == "Linux")
check("§4 ...and the JSON keeps the file as it was while nothing was measured",
      "kernel_name" not in MS.server_data_to_dict(ServerData(id="k1", alias="a", host="h",
                                                             user="u"))
      and MS.server_data_to_dict(ServerData(id="k1", alias="a", host="h", user="u",
                                            kernel_name="Linux"))["kernel_name"] == "Linux")
check("§4 the KERNEL gate: `Linux` opens it, everything else (and 'unknown') does not",
      MS.is_linux_host(ServerData(id="k1", alias="a", host="h", user="u", kernel_name="Linux"))
      and not MS.is_linux_host(ServerData(id="k2", alias="a", host="h", user="u",
                                          kernel_name="Darwin"))
      and not MS.is_linux_host(ServerData(id="k3", alias="a", host="h", user="u"))
      and MS.is_linux_host(ServerData(id="k4", alias="a", host="h", user="u",
                                      kernel_name="linux ")))
_win = MW.MainWindow()
_win._autosave_timer.stop()
_node = _win.scene.add_server(ServerData(id="kv1", alias="kernel", host="10.99.0.9", user="root"))
check("§4 the ONE write path stores it beside `os_name`",
      _win._apply_info_result("kv1", _info) is True
      and _node.data.kernel_name == "Linux" and _node.data.os_name == "Ubuntu 24.04 LTS",
      str((_node.data.kernel_name, _node.data.os_name)))
_win._apply_info_result("kv1", {"os_name": "Debian 12"})
check("§4 a collection that does not carry the fact leaves the stored one alone (a legacy batch)",
      _node.data.kernel_name == "Linux" and _node.data.os_name == "Debian 12",
      _node.data.kernel_name)
_win._dirty = False
_win._undo_baseline_dirty = False
_win.close()
app.processEvents()

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the `Network ▸` row: the allowlist, the commands, the gate, the split ==")
# ════════════════════════════════════════════════════════════════════════════

check("§5 a bare IPv4 is a target (the port is 0 — no port was selected)",
      PH.parse_network_target("10.0.0.5") == ("10.0.0.5", 0)
      and PH.parse_network_target("  192.168.1.1  ") == ("192.168.1.1", 0))
check("§5 `IPv4:PORT` is a target and keeps its port",
      PH.parse_network_target("10.0.0.5:22") == ("10.0.0.5", 22)
      and PH.parse_network_target("10.0.0.5:65535") == ("10.0.0.5", 65535))
check("§5 every other text is REFUSED before a command can exist",
      all(PH.parse_network_target(v) is None for v in
          ("10.0.0.300", "010.0.0.1", "10.0.0", "10.0.0.5.6", "10.0.0.5:0", "10.0.0.5:70000",
           "10.0.0.5:", "example.com", "http://10.0.0.5", "10.0.0.5 ; rm -rf /",
           "line one\n10.0.0.5", "", None)),
      str([PH.parse_network_target(v) for v in ("10.0.0.300", "10.0.0.5:70000", "example.com")]))
check("§5 the three verbs build ONE literal command from the VALIDATED address",
      PH.network_command("ping", "10.0.0.5") == "ping -c 4 -W 2 10.0.0.5"
      and PH.network_command("trace", "10.0.0.5") ==
      "traceroute -n 10.0.0.5 2>/dev/null || tracepath -n 10.0.0.5"
      and PH.network_command("reverse", "10.0.0.5:22") == "getent hosts 10.0.0.5",
      str([PH.network_command(v, "10.0.0.5") for v in PH.NETWORK_VERBS]))
check("§5 a foreign verb or a foreign address builds NOTHING (the builder is no second door)",
      PH.network_command("rm", "10.0.0.5") == ""
      and PH.network_command("ping", "10.0.0.5; whoami") == ""
      and PH.network_command("ping", "") == "")
_split_widget = QWidget()
_split_widget.split = type("SplitDouble", (), {"set_enabled": lambda self, on, **kw: True})()
_child = QWidget(_split_widget)
check("§5 the split of a container is found through the parent chain (a Files pane is a child)",
      SP.find_split(_child) is _split_widget.split and SP.find_split(QWidget()) is None)
check("§5 a pane that is ALREADY open receives the command through the shipped `send_macro()`",
      SP.TerminalSplit.send_to_pane is not None)

def select_text(pane, needle):
    """Select the FIRST occurrence of `needle` in the reader (the row reads the selection)."""
    cursor = pane.viewer_text.document().find(needle)
    pane.viewer_text.setTextCursor(cursor)
    return cursor.selectedText()


def submenu_of(menu, text):
    """The submenu a menu carries under `text` (None — no such row).

    The wrapper is BOUND once per action: a temporary `QAction.menu()` wrapper may take its `QMenu`
    down with it (Qt gotcha #9), and a reader's menu is rebuilt on every right click.
    """
    for action in menu.actions():
        sub = action.menu()
        if sub is not None and action.text() == text:
            return sub
    return None


clear_cfg()
tab, pane = make_pane()
pane._show_viewer("/etc/app.conf", 52, "db 10.0.0.5:5432\nweb 192.168.1.1\nname example.com\n")
_linux = ServerData(id="nw1", alias="nw", host="10.0.0.5", user="root", kernel_name="Linux")
_not_linux = ServerData(id="nw2", alias="nw2", host="10.0.0.5", user="root", kernel_name="Darwin")
tab.set_session_info(key="k", label="nw", host="10.0.0.5", port=22, user="root", data=_linux)
check("§5 the session's LIVE node is what the gate reads (never a copy)",
      tab.session_data() is _linux)
select_text(pane, "10.0.0.5:5432")
check("§5 the reader hands its selection over (stripped, untrusted)",
      pane.viewer_selection() == "10.0.0.5:5432", repr(pane.viewer_selection()))
_menu = pane._build_viewer_menu()
_network = submenu_of(_menu, i18n.t("sftp.network.menu"))
check("§5 the menu carries the `Network ▸` row with its THREE verbs",
      _network is not None and len(_network.actions()) == 3
      and [a.text() for a in _network.actions()] ==
      [i18n.t(f"sftp.network.{verb}", host="10.0.0.5") for verb in PH.NETWORK_VERBS],
      str([a.text() for a in (_network.actions() if _network is not None else [])]))
_ran = []
pane._container.run_network_command = lambda command: _ran.append(command) or True
_network.actions()[0].trigger()
check("§5 ...and a verb hands the ONE command to the container's split door",
      _ran == ["ping -c 4 -W 2 10.0.0.5"], str(_ran))
tab.set_session_info(key="k", label="nw2", host="10.0.0.5", port=22, user="root",
                     data=_not_linux)
_menu2 = pane._build_viewer_menu()
check("§5 a NON-Linux session is offered no row at all (the kernel fact, not a string guess)",
      submenu_of(_menu2, i18n.t("sftp.network.menu")) is None)
tab.set_session_info(key="k", label="nw", host="10.0.0.5", port=22, user="root", data=_linux)
select_text(pane, "example.com")
_menu3 = pane._build_viewer_menu()
check("§5 a selection that is NOT an address offers no row (`example.com` is refused)",
      submenu_of(_menu3, i18n.t("sftp.network.menu")) is None, repr(pane.viewer_selection()))
check("§5 a container with no node identified offers no row either",
      tab.append_network_menu(_menu3, pane=pane) == 0)
tab.release()

# ── the split's ONE new argument, end to end through a real window ───────────
clear_cfg()
_mw = MW.MainWindow()
_mw._autosave_timer.stop()
_mw.show()
app.processEvents()
_node = _mw.scene.add_server(ServerData(id="nv1", alias="verbs", host="10.99.0.10", user="root",
                                        kernel_name="Linux"))
_win = _mw._spawn_terminal_window(_node, password="pw")
app.processEvents()
_page = _win.page
check("§5 the page TOLD its Files container who the session is (the LIVE node travels)",
      _page.sftp_tab.session_data() is _node.data
      and MS.is_linux_host(_page.sftp_tab.session_data()))
_reader = _page.sftp_tab._active_pane
_reader._show_viewer("/etc/db.conf", 26, "host 10.20.30.40 port 5432\n")
select_text(_reader, "10.20.30.40")
_net = submenu_of(_reader._build_viewer_menu(), i18n.t("sftp.network.menu"))
check("§5 the live window's reader offers the row over its own selection",
      _net is not None and _reader.viewer_selection() == "10.20.30.40",
      repr(_reader.viewer_selection()))
_net.actions()[0].trigger()
app.processEvents()
check("§5 the verb opens a normal SPLIT of the SAME node",
      _win.split.pane is not None and _win.split.owner_page is _page,
      str(_win.split.pane))
check("§5 ...and the pane's OWN session carries the command as its `initial_command`",
      "ping -c 4 -W 2 10.20.30.40" in str(getattr(_win.split.pane, "_session_command", "")),
      repr(getattr(_win.split.pane, "_session_command", None)))
check("§5 the second session is the same node with the same credential (no new question)",
      getattr(_win.split.pane, "server_data", None) is _node.data)
try:
    _win.split.set_enabled(False)
except Exception:  # noqa: BLE001 — a fake thread that already ended
    pass
_mw._dirty = False
_mw._undo_baseline_dirty = False
_mw.close()
app.processEvents()
try:
    wait_until(lambda: not getattr(_win.split.pane, "isRunning", lambda: False)(), timeout_ms=2000)
except Exception:  # noqa: BLE001 — nothing left to wait for
    pass

# ════════════════════════════════════════════════════════════════════════════
print("== §6 i18n and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§6 the release adds its TWELVE keys (the reader's find bar four, the background four and "
      f"the `Network ▸` four) in EVERY language",
      len(NEW_KEYS) == 12
      and all(all(key in LANGS[code] for key in NEW_KEYS) for code in LANGS),
      str([c for c in LANGS if not all(k in LANGS[c] for k in NEW_KEYS)]))
check(f"§6 the pin is the sum of the line's chain ({EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1181 + 12, str(EXPECTED_I18N_KEYS))
check("§6 the placeholders travel with their sentence in every language",
      all(set(__import__("re").findall(r"\{(\w+)\}", LANGS[c]["sftp.network.ping"])) == {"host"}
          and set(__import__("re").findall(r"\{(\w+)\}", LANGS[c]["sftp.find.count"]))
          == {"cur", "total"}
          and set(__import__("re").findall(r"\{(\w+)\}", LANGS[c]["sftp.viewer.background_applied"]))
          == {"name"} for c in LANGS))
check("§6 the pin names this release's line",
      releases_at_least(EXPECTED_APP_VERSION, "1.14.1")
      and __import__("version").VERSION_FORMAT == "0.9",
      EXPECTED_APP_VERSION)
check("the schema did NOT move (the kernel fact is ONE additive field)",
      __import__("version").VERSION_FORMAT == "0.9")

finish()
