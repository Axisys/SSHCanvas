# -*- coding: utf-8 -*-
"""v1.14.1.2 — THE READER, FOLLOWED: the state, the bounds and the vocabulary of the shipped reader.
§1 the bar follows the DOCUMENT it counts (N151: `_show_viewer()`, a new file, a closed bar);
§2 the counter says `+` only when a FURTHER hit exists (N152); §3 the reveal counts Qt's UTF-16 units
(N153); §4 the scan is bounded in TIME (the debounce, a keystroke burst over a 1 MB document);
§5 ONE painter for the reader's surface and its chip (N154, a failed write changes neither); §6 the
eight preset hues have ONE PURE home; §7 `needs_info_collection()` and the connect condition; §8 the
release pins. Rule — `AGENTS.md` §4.6, §4.15; mechanism — `DOCUMENTATION.md` §38, §14f.
Run: python tests/test_followups_v11412.py
"""
import re
import sys
import time

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     merge_cfg, releases_at_least, wait_until)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import models.server as MS  # noqa: E402
import modules.sftp_pane_helpers as PH  # noqa: E402
import modules.sftp_pane_verbs as SVV  # noqa: E402
import modules.sftp_pane_viewer as PV  # noqa: E402
import modules.sftp_tab as ST  # noqa: E402
import ui.accent_presets as AP  # noqa: E402
import ui.main_window as MW  # noqa: E402
import ui.settings_dialog as SD  # noqa: E402
import ui.theme as theme  # noqa: E402
import ui.theme_qss as theme_qss  # noqa: E402
from _fakes import FakeLineEdit, FakeSpinBox, FakeSSHThread, FakeTermWin  # noqa: E402
from models.server import ServerData  # noqa: E402

import modules.ssh_terminal as SHT  # noqa: E402

SHT.SSHTerminalThread = FakeSSHThread   # every page/window of this file — on the fake
if hasattr(ST, "SSHTerminalThread"):
    ST.SSHTerminalThread = FakeSSHThread

LANGS = load_i18n_langs(ROOT)
_EMOJI = "\U0001F600"


def make_pane():
    """A bare Files container with ONE pane (no worker, no session) — the widget-level seam."""
    tab = ST.SftpTab()
    return tab, tab._active_pane


def fill(pane, text, path="/tmp/notes.txt"):
    """Put `text` in the reader through the shipped show path (no worker needed)."""
    pane._show_viewer(path, len(text.encode("utf-8")), text)


def label(pane):
    """The counter's text (`""` — no query at all)."""
    return pane._viewer_find_bar.count_label.text()


def chip_fill(pane):
    """The hex the header's chip paints itself with (None — no chip style)."""
    found = re.search(r"background-color:\s*(#[0-9A-Fa-f]{6})",
                      pane.btn_viewer_background.styleSheet() or "")
    return found.group(1).lower() if found else None


def surface_fill(pane):
    """The hex the reader's surface is painted with (None — no surface rule)."""
    found = re.search(r"background-color:\s*(#[0-9A-Fa-f]{6})",
                      pane.viewer_text.styleSheet() or "")
    return found.group(1).lower() if found else None


# ════════════════════════════════════════════════════════════════════════════
print("== §1 a visible find bar is the truth about the CURRENT document (N151) ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
tab, pane = make_pane()
fill(pane, "alpha one\nbeta two\nALPHA three\ngamma\n")
pane.open_viewer_find()
pane._viewer_find_bar.query_edit.setText("alpha")
pane._on_viewer_find_query("alpha")
check("§1 the bar counts the file on the screen (the shipped state, before the new document)",
      pane.viewer_find_active and pane.viewer_find_state()["total"] == 2, str(pane.viewer_find_state()))
fill(pane, "ALPHA wins\nalpha again on the second line\n", path="/tmp/other.txt")
check("§1 a NEW file keeps the bar VISIBLE — the widget's own state, not only the state dict",
      pane.viewer_find_active and not pane._viewer_find_bar.isHidden(),
      f"active={pane.viewer_find_active}")
check("§1 ...and re-runs its query over the new document (no stale count, no leftover \"No matches\")",
      pane.viewer_find_state() == {"query": "alpha", "current": 1, "total": 2}
      and label(pane) == i18n.t("sftp.find.count", cur=1, total=2),
      f"{pane.viewer_find_state()} label={label(pane)!r}")
check("§1 ...and Enter really steps through the new matches (the shipped defect: it answered False)",
      pane.viewer_find_next() and pane.viewer_find_state()["current"] == 2
      and pane.viewer_text.textCursor().selectedText().lower() == "alpha",
      f"{pane.viewer_find_state()} sel={pane.viewer_text.textCursor().selectedText()!r}")
fill(pane, "nothing to find here\n", path="/tmp/third.txt")
check("§1 a document WITHOUT a hit says `No matches` — the truth about THAT file, said again",
      pane.viewer_find_state()["total"] == 0
      and label(pane) == i18n.t("search.no_results"), repr(label(pane)))
check("§1 the field carries the query it counted (the bar never shows a query the list ignores)",
      pane._viewer_find_bar.query_edit.text() == "alpha",
      repr(pane._viewer_find_bar.query_edit.text()))
pane.close_viewer_find()
fill(pane, "alpha again\n", path="/tmp/fourth.txt")
check("§1 a CLOSED bar stays closed and its field stays empty (nothing was searched)",
      pane.viewer_find_active is False and pane._viewer_find_bar.query_edit.text() == ""
      and pane.viewer_find_state()["total"] == 0)
_seen = []
pane._viewer_find_bar.query_changed.connect(_seen.append)
pane._viewer_find_bar.set_query("")
check("§1 `set_query()` re-seeds the field with the signals BLOCKED (no query is launched by it)",
      _seen == [] and pane._viewer_find_bar.query_edit.text() == "", str(_seen))
check("§1 ...and `_reset_viewer_find()` says NOTHING — an empty field is not \"No matches\"",
      label(pane) == "" and pane._viewer_find_bar._count == (0, None), repr(label(pane)))
tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the counter's `+` is a FURTHER hit, never a hit at the bound (N152) ==")
# ════════════════════════════════════════════════════════════════════════════

_MAX = SVV.VIEWER_FIND_MATCH_MAX
tab, pane = make_pane()
fill(pane, "a a\n", path="/tmp/two.txt")
pane.open_viewer_find()
try:
    SVV.VIEWER_FIND_MATCH_MAX = 2
    fill(pane, "a a\n", path="/tmp/two.txt")
    pane._on_viewer_find_query("a")
    check("§2 EXACTLY the bound of hits is reported as N, not `N+`",
          pane.viewer_find_state()["total"] == 2 and label(pane).endswith("/ 2")
          and pane._viewer_find_more is False, f"{pane.viewer_find_state()} {label(pane)!r}")
    fill(pane, "a a a\n", path="/tmp/three.txt")
    pane._on_viewer_find_query("a")
    check("§2 ONE hit past the bound says `N+` (a further match really exists)",
          pane.viewer_find_state()["total"] == 2 and label(pane).endswith("/ 2+")
          and pane._viewer_find_more is True, f"{pane.viewer_find_state()} {label(pane)!r}")
    fill(pane, "a\nb\na\nc\n", path="/tmp/two-again.txt")
    pane._on_viewer_find_query("a")
    check("§2 the flag is RE-COMPUTED (a narrower document answers `N` again, never a stale `+`)",
          label(pane).endswith("/ 2") and pane._viewer_find_more is False, label(pane))
    fill(pane, "xyz qqq\n", path="/tmp/none.txt")
    pane._on_viewer_find_query("a")
    check("§2 a query with no hit keeps the shipped empty state (`search.no_results`)",
          label(pane) == i18n.t("search.no_results") and pane._viewer_find_more is False,
          repr(label(pane)))
finally:
    SVV.VIEWER_FIND_MATCH_MAX = _MAX
fill(pane, "alpha beta alpha\n", path="/tmp/below.txt")
pane._on_viewer_find_query("alpha")
check(f"§2 the declared bound is the shipped one ({_MAX}) and a count below it is exact",
      _MAX == 2000 and pane.viewer_find_state()["total"] == 2 and label(pane).endswith("/ 2")
      and pane._viewer_find_more is False, f"{_MAX} {label(pane)!r}")
tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the reveal counts Qt's UTF-16 units, never Python code points (N153) ==")
# ════════════════════════════════════════════════════════════════════════════

tab, pane = make_pane()
pane.open_viewer_find()
TEXT = f"first {_EMOJI} line\nsecond {_EMOJI} line\nplain alpha line\n"
fill(pane, TEXT, path="/tmp/emoji.txt")
pane._on_viewer_find_query(_EMOJI)
check("§3 a non-BMP query is counted (two emoji) and the match selects ITSELF",
      pane.viewer_find_state()["total"] == 2
      and pane.viewer_text.textCursor().selectedText() == _EMOJI,
      f"{pane.viewer_find_state()} sel={pane.viewer_text.textCursor().selectedText()!r}")
check("§3 a match stores the (selectionStart, selectionEnd) PAIR of the cursor it found",
      len(pane._viewer_find_matches) == 2
      and all(isinstance(pair, tuple) and len(pair) == 2 for pair in pane._viewer_find_matches)
      and pane._viewer_find_matches[0][1] - pane._viewer_find_matches[0][0] == 2,
      str(pane._viewer_find_matches))
check("§3 ...the pair is UTF-16 (2 units for the astral glyph, 5 for a BMP word)",
      pane._viewer_find_matches[0][1] - pane._viewer_find_matches[0][0]
      == len(_EMOJI.encode("utf-16-le")) // 2 == 2)
check("§3 Enter steps to the SECOND emoji and wraps back to the first",
      pane.viewer_find_next() and pane.viewer_find_state()["current"] == 2
      and pane.viewer_text.textCursor().selectedText() == _EMOJI
      and pane.viewer_find_next() and pane.viewer_find_state()["current"] == 1,
      f"{pane.viewer_find_state()}")
pane._on_viewer_find_query("alpha")
check("§3 a BMP query is unchanged by the pair (the shipped reveal still selects the word)",
      pane.viewer_find_state()["total"] == 1
      and pane.viewer_text.textCursor().selectedText() == "alpha",
      repr(pane.viewer_text.textCursor().selectedText()))
tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the scan is bounded in TIME — one pass per pause (a keystroke burst) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§4 the debounce is DECLARED inside the 150..250 ms window",
      150 <= SVV.VIEWER_FIND_DEBOUNCE_MS <= 250, str(SVV.VIEWER_FIND_DEBOUNCE_MS))
tab, pane = make_pane()
BIG = ("filler line of a large document, nothing special here at all\n" * 20000)
fill(pane, BIG, path="/tmp/big.log")
pane.open_viewer_find()
check("§4 the measured document really is the 1 MB case",
      len(BIG) > 1_000_000, str(len(BIG)))
_passes = []
_orig_refresh = pane._refresh_viewer_find_matches
pane._refresh_viewer_find_matches = lambda: (_passes.append(1), _orig_refresh())[1]
try:
    pane._viewer_find_bar.set_query("")
    pane.open_viewer_find()
    _t0 = time.monotonic()
    for _char in "needle":
        pane._viewer_find_bar.query_edit.setText(pane._viewer_find_bar.query_edit.text() + _char)
    check("§4 a burst of six keystrokes runs ZERO passes while it is still being typed",
          _passes == [] and pane._viewer_find_timer.isActive(), f"passes={len(_passes)}")
    wait_until(lambda: not pane._viewer_find_timer.isActive(), timeout_ms=3000, tick_ms=20)
    _cost = time.monotonic() - _t0
    check("§4 ...and exactly ONE pass runs once the pause is reached (the burst is COALESCED)",
          len(_passes) == 1, f"passes={len(_passes)}")
    check("§4 the one pass is bounded (a 1 MB document is walked once, not once per character)",
          _cost < 10.0 and pane.viewer_find_state()["query"] == "needle",
          f"{_cost:.2f}s state={pane.viewer_find_state()}")
    _passes.clear()
    pane._viewer_find_bar.query_edit.setText("fill")
    pane._on_viewer_find_query("fill")
    check("§4 a door (`_on_viewer_find_query()`) searches NOW and drops the pending pass",
          pane._viewer_find_timer.isActive() is False and pane.viewer_find_state()["total"] >= 1
          and len(_passes) == 1, f"passes={len(_passes)} total={pane.viewer_find_state()['total']}")
finally:
    pane._refresh_viewer_find_matches = _orig_refresh
check("§4 the timer is SINGLE-SHOT (one pass per pause, never a repeating scan)",
      pane._viewer_find_timer.isSingleShot())
tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §5 ONE painter for the reader's surface and its chip (N154) ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
check("§5 the PURE builder takes the HUE argument (the config is persistence only)",
      theme_qss.viewer_background_qss(142, theme.DARK.base_bg)
      == f"QPlainTextEdit#SftpViewerText {{ background-color: "
         f"{theme_qss.viewer_background_hex(142, theme.DARK.base_bg)}; }}"
      and theme_qss.viewer_background_qss(None, theme.DARK.base_bg)
      == f"QPlainTextEdit#SftpViewerText {{ background-color: {theme.DARK.base_bg}; }}")
merge_cfg({"ui_viewer_background": 38})
tab, pane = make_pane()
tab2, pane2 = make_pane()
check("§5 both containers were built from the SAME stored hue",
      pane.viewer_background_hue == 38 and pane2.viewer_background_hue == 38,
      f"{pane.viewer_background_hue} {pane2.viewer_background_hue}")
tab.apply_viewer_background(142, pane=pane)
check("§5 the pane that took the choice wears the SAME colour on the surface and on its chip",
      surface_fill(pane) == chip_fill(pane) is not None
      and surface_fill(pane) == theme_qss.viewer_background_hex(142, theme.THEME.base_bg).lower(),
      f"surface={surface_fill(pane)} chip={chip_fill(pane)}")
pane2._refresh_viewer_verbs()
check("§5 a SECOND container that did not take it keeps its own hue — and both halves agree (N154)",
      surface_fill(pane2) == chip_fill(pane2) is not None
      and surface_fill(pane2) == theme_qss.viewer_background_hex(38, theme.THEME.base_bg).lower(),
      f"surface={surface_fill(pane2)} chip={chip_fill(pane2)}")
check("§5 ...which is what the config alone could not answer (it already says 142)",
      i18n.load_config().get("ui_viewer_background") == 142,
      str(i18n.load_config().get("ui_viewer_background")))
_log = []
_orig_log = SVV.log
SVV.log = type("_Log", (), {"warning": lambda self, *a, **k: _log.append(a)})()
_orig_save = ST.save_viewer_background
ST.save_viewer_background = lambda hue: False
try:
    kept = pane.set_viewer_background(25)
    kept2 = tab.apply_viewer_background(25, pane=pane)
finally:
    ST.save_viewer_background = _orig_save
    SVV.log = _orig_log
check("§5 a write that FAILS leaves the pane at its old hue (and answers it)",
      kept == 142 and pane.viewer_background_hue == 142
      and surface_fill(pane) == theme_qss.viewer_background_hex(142, theme.THEME.base_bg).lower(),
      f"kept={kept} hue={pane.viewer_background_hue}")
check("§5 ...the container's walk answers the old hue too and applies nothing",
      kept2 == 142 and surface_fill(pane) == chip_fill(pane)
      and i18n.load_config().get("ui_viewer_background") == 142, f"kept2={kept2}")
check("§5 ...and the failure is said ONCE per call, in the log",
      len(_log) == 2 and all("not stored" in str(args[0]) for args in _log), str(_log))
tab.release()
tab2.release()
clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the eight preset hues have ONE PURE home ==")
# ════════════════════════════════════════════════════════════════════════════

check("§6 `ui/accent_presets.py` holds eight (name, hue) pairs",
      len(AP.ACCENT_PRESETS) == 8
      and all(isinstance(name, str) and isinstance(hue, float)
              for name, hue in AP.ACCENT_PRESETS), str(AP.ACCENT_PRESETS))
check("§6 sky is FIRST and IS `theme.DEFAULT_ACCENT_HUE` (the default look is one click away)",
      AP.ACCENT_PRESETS[0] == ("sky", theme.DEFAULT_ACCENT_HUE),
      f"{AP.ACCENT_PRESETS[0]} vs {theme.DEFAULT_ACCENT_HUE}")
check("§6 the Appearance tab reads that table (no second list in the dialog)",
      SD.accent_swatches() == [(name, hue, theme.accent_hex(hue))
                               for name, hue in AP.ACCENT_PRESETS],
      str(SD.accent_swatches()[:2]))
check("§6 the reader's chip reads the SAME table (one object, not a copy)",
      PH.VIEWER_BACKGROUND_PRESETS is AP.ACCENT_PRESETS,
      f"{id(PH.VIEWER_BACKGROUND_PRESETS)} vs {id(AP.ACCENT_PRESETS)}")
check("§6 every preset is named by an i18n key every language already carries",
      all(f"settings.appearance.accent.{name}" in LANGS[code]
          for name, _hue in AP.ACCENT_PRESETS for code in LANGS),
      str([name for name, _h in AP.ACCENT_PRESETS]))
import _size_budget as _SB  # noqa: E402 - the line pin this check guards

check("§6 `ui/theme.py` was not touched by the new module (its LINE PIN holds)",
      theme.__file__.endswith("theme.py")
      and len(open(theme.__file__, encoding="utf-8").read().splitlines())
      <= _SB.LINE_PINS["ui/theme.py"],
      f"{len(open(theme.__file__, encoding='utf-8').read().splitlines())} of the pin")
check("§6 `modules/sftp_pane_helpers.py` is UNDER the band (the tuple left, the alias arrived)",
      len(open(PH.__file__, encoding="utf-8").read().splitlines()) < 900,
      str(len(open(PH.__file__, encoding="utf-8").read().splitlines())))

# ════════════════════════════════════════════════════════════════════════════
print("== §7 `needs_info_collection()` and the connect condition ==")
# ════════════════════════════════════════════════════════════════════════════

def node(**kw):
    """A duck-typed card (`data` attribute) — the predicate takes it like `is_linux_host()`."""
    return type("_Node", (), {"data": ServerData(id="p1", alias="p", host="10.0.0.9", user="u",
                                                 **kw)})()


check("§7 a node with NEITHER fact still needs the collection (never measured)",
      MS.needs_info_collection(node()) is True)
check("§7 a node with the OS but no kernel needs it — a project from before the kernel fact",
      MS.needs_info_collection(node(os_name="Ubuntu 24.04 LTS")) is True)
check("§7 a node with the kernel but no OS needs it too (the batch answers both)",
      MS.needs_info_collection(node(kernel_name="Linux")) is True)
check("§7 BOTH facts answer False (measured once is enough)",
      MS.needs_info_collection(node(os_name="Ubuntu 24.04 LTS", kernel_name="Linux")) is False)
check("§7 a blank / whitespace fact is NOT a fact",
      MS.needs_info_collection(node(os_name="   ", kernel_name="Linux")) is True
      and MS.needs_info_collection(node(os_name="Debian 12", kernel_name=" \t")) is True)
check("§7 the predicate is PURE and duck-typed (a bare ServerData answers it directly)",
      MS.needs_info_collection(ServerData(id="p2", alias="a", host="h", user="u",
                                          os_name="Debian 12", kernel_name="Linux")) is False)

_FAKE_SPAWNED = []
_real_win_cls = MW.SSHTerminalWindow
MW.SSHTerminalWindow = FakeTermWin


def run_connect(nod):
    """Drive the ONE connect door with a dialog that is immediately accepted."""
    class _FakeDialog:
        def __init__(self, data, parent=None):
            self.user_edit, self.key_path_edit = FakeLineEdit("root"), FakeLineEdit("")
            self.port_edit, self.password_edit = FakeSpinBox(22), FakeLineEdit("pw")

        def exec(self):
            return QDialog.Accepted

    calls = []
    win = MW.MainWindow()
    win._autosave_timer.stop()
    card = win.scene.add_server(nod)
    win._collect_node_info = lambda node, password="", auto=False: calls.append(
        (node.data.id, password, auto))
    win._spawn_terminal_window = lambda *a, **k: None
    original = MW.SSHConnectDialog
    MW.SSHConnectDialog = _FakeDialog
    try:
        win._run_ssh_connect(card)
    finally:
        MW.SSHConnectDialog = original
    win._dirty = False
    win._undo_baseline_dirty = False
    win.close()
    app.processEvents()
    return calls


try:
    _old = run_connect(ServerData(id="nc-old", alias="old", host="10.99.0.21", user="root",
                                  os_name="Ubuntu 24.04 LTS"))
    check("§7 a shipped project (OS only) IS collected on connect — the `Network ▸` row becomes reachable",
          _old == [("nc-old", "pw", True)], str(_old))
    _new = run_connect(ServerData(id="nc-new", alias="new", host="10.99.0.22", user="root",
                                  os_name="Ubuntu 24.04 LTS", kernel_name="Linux"))
    check("§7 a node whose facts are complete is NOT collected again (one collection per connect)",
          _new == [], str(_new))
finally:
    MW.SSHTerminalWindow = _real_win_cls

# ════════════════════════════════════════════════════════════════════════════
print("== §8 i18n and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§8 the patch adds NO i18n key (parity stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1193 + 3, str(EXPECTED_I18N_KEYS))
check("§8 the pin names this release's line and the schema did NOT move",
      releases_at_least(EXPECTED_APP_VERSION, "1.14.1.2")
      and __import__("version").VERSION_FORMAT == "0.9", EXPECTED_APP_VERSION)
check("§8 the two pinned modules of the slot stay within their pins",
      len(open(SVV.__file__, encoding="utf-8").read().splitlines()) < 900
      and len(open(PV.__file__, encoding="utf-8").read().splitlines()) <= 1808,
      f"{SVV.__file__} / {PV.__file__}")
finish()
