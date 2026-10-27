# -*- coding: utf-8 -*-
"""v1.14.3 — THE CORNER ICONS: the tab-bar corner is icon-only, budgeted and owned by ONE module.
§1 the composition's ONE owner (`CornerBar`: its declared rows, both containers, the refusals);
§2 the icon-only shape (no label, the glyph, the tooltip, the accessible name, the two-tone QIcon);
§3 the declared MAX and the width budget (the pure arithmetic, the refusal past it, the label cost
it replaced); §4 the strip at the 480 px floor; §5 the two walks (a theme switch, a language switch
and the owner's alias); §6 the release pins.
Rule — `AGENTS.md` §4.32.2; mechanism — `DOCUMENTATION.md` §65.
Run: python tests/test_terminal_corner.py
"""
import glob
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     merge_cfg, placeholder_names, releases_at_least, translation_keys)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation and faulthandler inside)

from PySide6.QtCore import QObject, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget, QWidget  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_corner as TCORNER  # noqa: E402
import modules.terminal_dock as TD  # noqa: E402
import ui.icons as ICONS  # noqa: E402
import ui.theme as theme  # noqa: E402
from models.server import ServerData  # noqa: E402
import ui.main_window as MW  # noqa: E402

from _fakes import FakeSSHThread as _FakeThread  # noqa: E402

ST.SSHTerminalThread = _FakeThread   # every page/window of this file — on the fake
LANGS = load_i18n_langs(ROOT)


def make_main():
    """An offscreen MainWindow with a stopped autosave timer (determinism)."""
    window = MW.MainWindow()
    window._autosave_timer.stop()
    window.show()
    app.processEvents()
    return window


def make_window(main, alias, host):
    """A standalone terminal window (mode "windows") with ONE tab."""
    node = main.scene.add_server(ServerData(id=f"ci-{alias}", alias=alias, host=host, user="root"))
    win = main._spawn_terminal_window(node, password="pw")
    app.processEvents()
    return win


def src(folder, name):
    """The text of one module, for the "ONE owner" scans."""
    with open(os.path.join(ROOT, folder, name), encoding="utf-8") as fh:
        return fh.read()


def ink_of(pixmap):
    """The mean RGB of the OPAQUE pixels of a rendered glyph (antialiasing excluded)."""
    image = pixmap.toImage()
    red = green = blue = 0
    count = 0
    for x in range(image.width()):
        for y in range(image.height()):
            colour = image.pixelColor(x, y)
            if colour.alpha() > 200:
                red += colour.red()
                green += colour.green()
                blue += colour.blue()
                count += 1
    if not count:
        return None
    return QColor(red // count, green // count, blue // count)


def distance(one, two):
    """How far apart two colours are, as the largest channel gap."""
    return max(abs(one.red() - two.red()), abs(one.green() - two.green()),
               abs(one.blue() - two.blue()))


# ════════════════════════════════════════════════════════════
# 1. The composition's ONE owner
# ════════════════════════════════════════════════════════════
print("== 1. the one owner of the composition ==")

clear_cfg()
mw = make_main()
win = make_window(mw, "alpha", "10.99.0.1")
merge_cfg({"terminal_mode": "tabs"})   # the second container is the DOCK (the same owner)
dock = mw._spawn_terminal_window(mw.scene.add_server(
    ServerData(id="ci-beta", alias="beta", host="10.99.0.2", user="root")), password="pw")
app.processEvents()

check("the corner's rows are DECLARED once (`CORNER_ROWS`: the key, the glyph and the two keys)",
      [row.key for row in TCORNER.CORNER_ROWS] == ["split", "commander"]
      and [row.glyph for row in TCORNER.CORNER_ROWS] == ["split", "files"]
      and all(row.label_key in LANGS["en"] and row.tooltip_key in LANGS["en"]
              for row in TCORNER.CORNER_ROWS))
check("`corner_row()` answers the declared row and nothing else (a typo is no row)",
      TCORNER.corner_row("split") is TCORNER.CORNER_ROWS[0]
      and TCORNER.corner_row("split_button") is None and TCORNER.corner_row("") is None)
check("the window's corner IS the bar (not a control, not a wrapper the controls build)",
      win.session_tabs.cornerWidget(Qt.Corner.TopRightCorner) is win.corner
      and isinstance(win.corner, TCORNER.CornerBar)
      and win.corner.keys() == ["split", "commander"]
      and win.corner.controls() == [win.btn_split, win.commander.btn])
check("the dock builds the SAME composition (one owner, two containers)",
      dock.content.session_tabs.cornerWidget(Qt.Corner.TopRightCorner) is dock.content.corner
      and dock.content.corner.keys() == ["split", "commander"]
      and type(dock.content.corner) is type(win.corner))
check("the controls are ROWS of the bar (the row's layout is their parent, not a second row)",
      win.btn_split.parentWidget() is win.corner
      and win.commander.btn.parentWidget() is win.corner
      and win.corner.layout().count() == 2)
check("the Commander control is NOT a widget (it owns an action and a button; the ROW is the bar's)",
      isinstance(win.commander, QObject) and not isinstance(win.commander, QWidget))
check("the bar answers the budget and nothing was refused while the rows are legal",
      win.corner.budget() == (2, TCORNER.CORNER_MAX_CONTROLS)
      and win.corner.refused() == ())
check("an UNDECLARED key is refused (the composition cannot be extended from outside the table)",
      win.corner.add_control("split_button", QPushButton()) is False
      and win.corner.add_control("", QPushButton()) is False
      and win.corner.keys() == ["split", "commander"])
check("a SECOND author of a declared key is refused (one row per control)",
      win.corner.add_control("split", QPushButton()) is False
      and win.corner.keys() == ["split", "commander"]
      and len(win.corner.controls()) == 2)
check("`apply_corner_style()` / `shape_control()` have ONE home (the corner module)",
      "def apply_corner_style" in src("modules", "terminal_corner.py")
      and "def shape_control" in src("modules", "terminal_corner.py")
      and "def apply_corner_style" not in src("modules", "terminal_split.py")
      and "def apply_corner_style" not in src("modules", "sftp_commander_corner.py"))
_corner_calls = []
for _path in glob.glob(os.path.join(ROOT, "modules", "*.py")) + glob.glob(
        os.path.join(ROOT, "ui", "*.py")):
    with open(_path, encoding="utf-8") as _fh:
        _text = _fh.read()
    for _line in _text.splitlines():
        _stripped = _line.strip()
        if _stripped.startswith("self.") and "setCornerWidget(" in _stripped:
            _corner_calls.append((os.path.basename(_path), _stripped))
check("every container hands the SAME owner to `setCornerWidget()` (no third composition)",
      len(_corner_calls) == 2
      and all("setCornerWidget(self.corner," in line for _name, line in _corner_calls),
      str(_corner_calls))


# ════════════════════════════════════════════════════════════
# 2. The icon-only shape
# ════════════════════════════════════════════════════════════
print("== 2. the icon-only shape ==")

check("every corner control is LABEL-LESS (the v1.14.3 policy)",
      all(button.text() == "" for button in win.corner.controls()))
check("...and every one wears its declared glyph (a real, inked QIcon)",
      not win.btn_split.icon().isNull() and not win.commander.btn.icon().isNull()
      and ink_of(win.btn_split.icon().pixmap(TCORNER.CORNER_GLYPH_PX, TCORNER.CORNER_GLYPH_PX,
                                             QIcon.Mode.Normal, QIcon.State.Off)) is not None)
check("...on a FIXED square, so the row's width is the budget's and not the style's",
      all(button.size() == QSize(TCORNER.CORNER_BUTTON_PX, TCORNER.CORNER_BUTTON_PX)
          and button.iconSize() == QSize(TCORNER.CORNER_GLYPH_PX, TCORNER.CORNER_GLYPH_PX)
          for button in win.corner.controls()),
      str([b.size().toTuple() for b in win.corner.controls()]))
check("...keeps its checkable feedback (the state a label would have carried)",
      all(button.isCheckable() for button in win.corner.controls())
      and all(button.isChecked() is False for button in win.corner.controls()))
check("...the TOOLTIP is the teacher the label left (the sentence of its own key)",
      win.btn_split.toolTip() == LANGS["en"]["terminal.split_tooltip"]
      and win.commander.btn.toolTip() == LANGS["en"]["sftp.commander_tooltip"])
check("...and the ACCESSIBLE NAME says what the glyph means (a screen reader has no glyph)",
      win.btn_split.accessibleName()
      == LANGS["en"]["terminal.corner_accessible"].format(action=LANGS["en"]["terminal.split"])
      and win.commander.btn.accessibleName()
      == LANGS["en"]["terminal.corner_accessible"].format(
          action=LANGS["en"]["sftp.commander"]),
      f"{win.btn_split.accessibleName()!r} / {win.commander.btn.accessibleName()!r}")
check("the ACTION keeps its word — the context-menu row is not an icon",
      win.act_split.text() == LANGS["en"]["terminal.split"]
      and win.commander.act.text() == LANGS["en"]["sftp.commander"])
check("the bar itself names its budget (the MAX hint, its own key)",
      win.corner.toolTip()
      == LANGS["en"]["terminal.corner_tooltip"].format(max=TCORNER.CORNER_MAX_CONTROLS))
_off = ink_of(ICONS.get_corner_icon("split").pixmap(
    TCORNER.CORNER_GLYPH_PX, TCORNER.CORNER_GLYPH_PX, QIcon.Mode.Normal, QIcon.State.Off))
_on = ink_of(ICONS.get_corner_icon("split").pixmap(
    TCORNER.CORNER_GLYPH_PX, TCORNER.CORNER_GLYPH_PX, QIcon.Mode.Normal, QIcon.State.On))
check("the glyph carries TWO tones: the rest ink and the CHECKED one (`QIcon.State.On`)",
      _off is not None and _on is not None and distance(_off, _on) > 60,
      f"off={_off.name() if _off else None} on={_on.name() if _on else None}")
check("...and the checked tone IS the label's ink on the strong fill (`canvas_bg`)",
      _on is not None and distance(_on, QColor(theme.CANVAS_BG)) <= 12,
      f"on={_on.name() if _on else None} canvas={theme.CANVAS_BG}")
check("...while the rest tone is the shipped outline (`icon_color`)",
      _off is not None and distance(_off, QColor(theme.ICON_COLOR)) <= 12,
      f"off={_off.name() if _off else None} icon={theme.ICON_COLOR}")
check("the QSS keeps the two states the label used to carry (:hover / :checked)",
      ":hover" in __import__("ui.theme_qss", fromlist=["style"]).style("corner.button")
      and ":checked" in __import__("ui.theme_qss", fromlist=["style"]).style("corner.button"))


# ════════════════════════════════════════════════════════════
# 3. The declared MAX and the width budget
# ════════════════════════════════════════════════════════════
print("== 3. the MAX and the width budget ==")

check("the MAX is DECLARED, not implied by today's two rows",
      TCORNER.CORNER_MAX_CONTROLS == 6 and isinstance(TCORNER.CORNER_MAX_CONTROLS, int))
check("`corner_width()` is the pure arithmetic of the row (the squares + the gaps)",
      TCORNER.corner_width(0) == 0
      and TCORNER.corner_width(1) == TCORNER.CORNER_BUTTON_PX
      and TCORNER.corner_width(2) == 2 * TCORNER.CORNER_BUTTON_PX + TCORNER.CORNER_SPACING_PX
      and TCORNER.corner_width(6) == 6 * TCORNER.CORNER_BUTTON_PX + 5 * TCORNER.CORNER_SPACING_PX,
      str([TCORNER.corner_width(n) for n in range(7)]))
check("the shipped pair costs SIXTY pixels, where the plan measured two labels of 90–150",
      TCORNER.corner_width(2) == 60 and TCORNER.corner_width(2) < 2 * 90)
check("eight icon controls would cost ~256 px (the figure the slot was decided on)",
      abs(TCORNER.corner_width(8) - 256) <= 8, f"{TCORNER.corner_width(8)} px")
check("`corner_fits()` is the ONE budget predicate (the MAX inside, MAX + 1 outside)",
      TCORNER.corner_fits(0) and TCORNER.corner_fits(TCORNER.CORNER_MAX_CONTROLS)
      and not TCORNER.corner_fits(TCORNER.CORNER_MAX_CONTROLS + 1)
      and not TCORNER.corner_fits(-1))
check("the whole budget stays under HALF the 480 px window floor",
      TCORNER.corner_budget_ok()
      and TCORNER.corner_width(TCORNER.CORNER_MAX_CONTROLS)
      <= TCORNER.CORNER_WINDOW_FLOOR_PX // 2,
      f"{TCORNER.corner_width(TCORNER.CORNER_MAX_CONTROLS)} of "
      f"{TCORNER.CORNER_WINDOW_FLOOR_PX}")

# The refusal needs a table BIGGER than the budget: the declaration is the module's, so the probe
# swaps it for its own and puts the shipped one back in the same `finally`.
_shipped_rows = TCORNER.CORNER_ROWS
_probe = TCORNER.CornerBar()
try:
    TCORNER.CORNER_ROWS = tuple(
        TCORNER.CornerRow(f"probe-{n}", "split", "terminal.split", "terminal.split_tooltip")
        for n in range(TCORNER.CORNER_MAX_CONTROLS + 1))
    for _n in range(TCORNER.CORNER_MAX_CONTROLS):
        _probe.add_control(f"probe-{_n}", QPushButton())
    _cap = _probe.budget()
    _overflow = _probe.add_control(f"probe-{TCORNER.CORNER_MAX_CONTROLS}", QPushButton())
finally:
    TCORNER.CORNER_ROWS = _shipped_rows
check("the bar REFUSES the control past the budget and names it",
      _cap == (TCORNER.CORNER_MAX_CONTROLS, TCORNER.CORNER_MAX_CONTROLS)
      and _overflow is False
      and _probe.refused() == (f"probe-{TCORNER.CORNER_MAX_CONTROLS}",)
      and len(_probe.controls()) == TCORNER.CORNER_MAX_CONTROLS,
      f"budget={_cap} refused={_probe.refused()}")
_probe.deleteLater()


# ════════════════════════════════════════════════════════════
# 4. The strip at the 480 px floor
# ════════════════════════════════════════════════════════════
print("== 4. the strip at 480 px ==")

STRIP_PX = TCORNER.CORNER_WINDOW_FLOOR_PX   # the narrowest window the policy may assume
strip = QTabWidget()
strip.addTab(QWidget(), "alpha")
strip.addTab(QWidget(), "beta")
strip_corner = TCORNER.CornerBar(strip)
strip_corner.add_control("split", QPushButton())
strip_corner.add_control("commander", QPushButton())
strip.setCornerWidget(strip_corner, Qt.Corner.TopRightCorner)
strip.show()
strip.resize(STRIP_PX, 220)
app.processEvents()
_tabs_bar = strip.tabBar()
check("at 480 px the strip really is 480 px wide (the measurement is not a guess)",
      strip.width() == STRIP_PX, f"{strip.width()}")
check("the corner takes its declared width there and no more",
      strip_corner.width() == TCORNER.corner_width(2),
      f"corner={strip_corner.width()} declared={TCORNER.corner_width(2)}")
check("...which leaves the tabs over 400 px of the strip (the labels used to take ~376)",
      STRIP_PX - strip_corner.width() >= 400,
      f"{STRIP_PX - strip_corner.width()} px left")
check("...the two tabs still fit BESIDE the corner (no row wrapped, no tab hidden)",
      _tabs_bar.tabRect(1).right() <= STRIP_PX - strip_corner.width()
      and strip.count() == 2,
      f"tab1 right={_tabs_bar.tabRect(1).right()} corner starts="
      f"{STRIP_PX - strip_corner.width()}")
check("...and the whole declared budget would still leave half the floor to the tabs",
      STRIP_PX - TCORNER.corner_width(TCORNER.CORNER_MAX_CONTROLS) >= STRIP_PX // 2,
      f"{STRIP_PX - TCORNER.corner_width(TCORNER.CORNER_MAX_CONTROLS)} px")
_check_label = QPushButton("Split Terminal")
check("the LABEL the policy removed is wider than the whole shipped icon PAIR",
      _check_label.sizeHint().width() > TCORNER.corner_width(2),
      f"label={_check_label.sizeHint().width()} pair={TCORNER.corner_width(2)}")
check("the live window's corner is the declared pair of squares",
      win.corner.width() == TCORNER.corner_width(2) and win.corner.width() > 0,
      f"{win.corner.width()} px")
strip.close()
strip.deleteLater()
app.processEvents()


# ════════════════════════════════════════════════════════════
# 5. The two walks (theme, language, the owner's alias)
# ════════════════════════════════════════════════════════════
print("== 5. the walks ==")

win.refresh_theme()
app.processEvents()
check("`refresh_theme()` re-applies the shape without losing it (the theme walk)",
      all(button.text() == "" and not button.icon().isNull()
          for button in win.corner.controls())
      and win.btn_split.toolTip() == LANGS["en"]["terminal.split_tooltip"])

win.act_split.trigger()
app.processEvents()
_alias = win.session_tabs.widget(0).server_data.alias
check("the split's tooltip names the pane's OWNER while it is open (the second channel)",
      win.btn_split.toolTip() == f"{LANGS['en']['terminal.split_tooltip']} — {_alias}",
      repr(win.btn_split.toolTip()))
win.corner.retranslate()
check("...and the bar's own walk re-reads that sentence instead of shortening it",
      win.btn_split.toolTip() == f"{LANGS['en']['terminal.split_tooltip']} — {_alias}")
win.act_split.trigger()
app.processEvents()
check("...which goes back to the plain sentence when the pane closes",
      win.btn_split.toolTip() == LANGS["en"]["terminal.split_tooltip"])

i18n.set_language("ru")
win.retranslate()
win.refresh_theme()
app.processEvents()
check("a LANGUAGE switch re-texts the tooltips and the accessible names (no stale label)",
      win.btn_split.toolTip() == LANGS["ru"]["terminal.split_tooltip"]
      and win.commander.btn.toolTip() == LANGS["ru"]["sftp.commander_tooltip"]
      and win.btn_split.accessibleName()
      == LANGS["ru"]["terminal.corner_accessible"].format(action=LANGS["ru"]["terminal.split"])
      and win.corner.toolTip()
      == LANGS["ru"]["terminal.corner_tooltip"].format(max=TCORNER.CORNER_MAX_CONTROLS),
      f"{win.btn_split.toolTip()!r}")
i18n.set_language("en")
win.retranslate()
app.processEvents()
check("...and back: the English sentences return (the walk is not one-way)",
      win.btn_split.toolTip() == LANGS["en"]["terminal.split_tooltip"]
      and win.corner.toolTip()
      == LANGS["en"]["terminal.corner_tooltip"].format(max=TCORNER.CORNER_MAX_CONTROLS))

win.commander.set_enabled(False)
check("the Commander's rows still answer `set_enabled()` in step (a session with no Files tab)",
      win.commander.act.isEnabled() is False and win.commander.btn.isEnabled() is False)
win.commander.set_enabled(True)
check("...and the action is the ONE source of truth of the checkmark",
      win.commander.act.isCheckable() and win.commander.btn.isCheckable()
      and win.commander.is_commander() is False)
win.commander.set_state(True)
check("`set_state()` shows a session's mode WITHOUT re-entering the container",
      win.commander.is_commander() is True and win.commander.btn.isChecked() is True)
win.commander.set_state(False)


# ════════════════════════════════════════════════════════════
# 6. The release pins
# ════════════════════════════════════════════════════════════
print("== 6. the release pins ==")

check_release_state(ROOT)
check("this file describes v1.14.3 (the corner-icons slot, or a later release)",
      releases_at_least(EXPECTED_APP_VERSION, "1.14.3"),
      EXPECTED_APP_VERSION)
check(f"the parity pin counts the two new keys ({EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1196 + 2, str(EXPECTED_I18N_KEYS))
check("both new keys exist in EVERY language, with the same placeholders",
      all(key in LANGS[code] for code in LANGS
          for key in ("terminal.corner_tooltip", "terminal.corner_accessible"))
      and all(placeholder_names(LANGS[code]["terminal.corner_tooltip"]) == {"max"}
              and placeholder_names(LANGS[code]["terminal.corner_accessible"]) == {"action"}
              for code in LANGS),
      str({code: sorted(set(LANGS[code]) & {"terminal.corner_tooltip",
                                            "terminal.corner_accessible"}) for code in LANGS}))
check("the two keys are USED by the corner (no dead string)",
      "terminal.corner_tooltip" in src("modules", "terminal_corner.py")
      and "terminal.corner_accessible" in src("modules", "terminal_corner.py"))
check("every language file carries the same key count as `en`",
      all(len(translation_keys(LANGS[code])) == EXPECTED_I18N_KEYS for code in LANGS),
      str({code: len(translation_keys(LANGS[code])) for code in LANGS}))
check("VERSION_FORMAT stays `0.9` (the corner is UI, not a schema change)",
      __import__("version").VERSION_FORMAT == "0.9")
check_i18n_parity(LANGS)
check_i18n_format(LANGS)

mw._shutdown_background_threads()
app.processEvents()
finish()
