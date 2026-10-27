# -*- coding: utf-8 -*-
"""The tab-bar CORNER of a session container — the ONE owner of its composition (AGENTS.md §4.32.2).

A corner control is ICON-ONLY: a glyph, a tooltip and an accessible name, no label — the tab strip
pays for every pixel beside its tabs. This module owns the row, the declared MAX
(`CORNER_MAX_CONTROLS`), the shape a control is given and the theme / language walks. The CONTROLS
stay with their owners (`modules/terminal_split.py`, `modules/sftp_commander_corner.py`) and reach the
row as the keys of `CORNER_ROWS`, so a third control is a ROW here, never a second composition.
Mechanism — `DOCUMENTATION.md` §65.
"""
from typing import NamedTuple

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QWidget

try:  # the corner glyph in BOTH tones (ui/icons.py)
    from ..ui.icons import get_corner_icon
except ImportError:
    try:
        from ui.icons import get_corner_icon
    except ImportError:  # a stripped build — the control stays glyph-less
        def get_corner_icon(name):
            return QIcon()

try:  # the ONE registry of the widget stylesheets (the corner controls' feedback)
    from ..ui import theme_qss
except ImportError:
    try:
        from ui import theme_qss
    except ImportError:  # a stripped build — the global QPushButton rule stands
        theme_qss = None

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — a build without i18n keeps the keys, not a crash
    def _t(key, **kwargs):  # type: ignore
        return key


def _log():
    """The app logger (lazy — a stripped build logs nowhere)."""
    try:
        from .logger import get_logger
    except ImportError:
        try:
            from modules.logger import get_logger
        except ImportError:
            return None
    try:
        return get_logger("modules.terminal_corner")
    except Exception:  # noqa: BLE001 — a logger is never worth an exception
        return None


#: The declared budget of the corner: a control past it is REFUSED, so a row never grows silently.
CORNER_MAX_CONTROLS = 6
#: The window floor the budget is measured against (`MIN_WINDOW_WIDTH`, `ui/main_window_layout.py`):
#: the whole budget must stay under half of it, leaving the tab strip the other half.
CORNER_WINDOW_FLOOR_PX = 480
#: The square an icon-only control is drawn in, in pixels — the glyph plus its padding and its frame.
CORNER_BUTTON_PX = 28
#: The glyph's box inside that square (`ui/icons.py` draws on the same 20 px canvas).
CORNER_GLYPH_PX = 20
CORNER_SPACING_PX = 4


class CornerRow(NamedTuple):
    """ONE declared corner control: its key, its glyph and the two i18n keys it speaks."""

    key: str
    glyph: str
    label_key: str
    tooltip_key: str


#: The composition, in ROW order. A new per-session control is a row here (`AGENTS.md` §4.32.2).
CORNER_ROWS = (
    CornerRow("split", "split", "terminal.split", "terminal.split_tooltip"),
    CornerRow("commander", "files", "sftp.commander", "sftp.commander_tooltip"),
)


def corner_row(key):
    """The declared row of `key` (None — the corner does not know this control)."""
    for row in CORNER_ROWS:
        if row.key == key:
            return row
    return None


def corner_width(count) -> int:
    """The width `count` icon-only controls cost, in pixels — the PURE half of the budget."""
    count = max(0, int(count))
    if count <= 0:
        return 0
    return count * CORNER_BUTTON_PX + (count - 1) * CORNER_SPACING_PX


def corner_fits(count) -> bool:
    """Does a row of `count` controls stay inside the declared MAX?"""
    return 0 <= int(count) <= CORNER_MAX_CONTROLS


def corner_budget_ok() -> bool:
    """Does the DECLARED MAX fit the window floor's half? — the arithmetic of the budget.

    A budget is a promise about the strip, not about the row: what it costs has to leave a bare
    window (the floor every container may be squeezed to) with the other half for its tabs.
    """
    return corner_width(CORNER_MAX_CONTROLS) <= CORNER_WINDOW_FLOOR_PX // 2


def apply_corner_style(*buttons) -> int:
    """Apply the ONE corner-button stylesheet to the icon-only controls (never raises).

    The `ui/theme_qss.py` pattern: `refresh()` from a theme walk, so a QSS string is never a value
    captured once (`AGENTS.md` §4.6). Returns how many were styled.
    """
    if theme_qss is None:
        return 0
    done = 0
    for button in buttons:
        if button is None:
            continue
        try:
            theme_qss.refresh(button, "corner.button")
            done += 1
        except RuntimeError:
            continue  # Qt teardown — this button is already destroyed
    return done


def shape_control(button, glyph, tooltip, label) -> bool:
    """Give ONE corner control the label-less shape: glyph, tooltip, accessible name, square size.

    The word is NOT drawn (`AGENTS.md` §4.32.2): the tooltip and the accessible name are what is
    left to teach the control, and the square is FIXED so the row's width is the budget's own and
    not the platform style's. Never raises — the corner is chrome.
    """
    if button is None:
        return False
    try:
        button.setText("")
        button.setIcon(QIcon())
        button.setIcon(get_corner_icon(glyph))
        button.setIconSize(QSize(CORNER_GLYPH_PX, CORNER_GLYPH_PX))
        button.setToolTip(str(tooltip or ""))
        button.setAccessibleName(_t("terminal.corner_accessible", action=str(label or "")))
        button.setFixedSize(CORNER_BUTTON_PX, CORNER_BUTTON_PX)
    except RuntimeError:
        return False  # Qt teardown — the button is already gone
    apply_corner_style(button)
    return True


class CornerBar(QWidget):
    """The corner itself: the row of icon-only controls, its budget and its two walks.

    The CONTAINER constructs it once, adds the declared controls through `add_control()` and hands it
    to `session_tabs.setCornerWidget(...)`; `refresh_theme()` and `retranslate()` are the ONE walks a
    theme or a language switch makes over them. The controls answer their own state (`act` / `btn`),
    so the bar holds NO session knowledge. Never raises — the corner is chrome.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("terminalCornerBar")
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(CORNER_SPACING_PX)
        #: [(CornerRow, button, tooltip provider or None)] — the DECLARED order of the composition.
        self._controls = []
        self._refused = []
        self.refresh_text()

    def add_control(self, key, button, tooltip=None) -> bool:
        """Add ONE declared control to the row; a full budget or an unknown key REFUSES it.

        `tooltip` is the control's OWN sentence provider (the split's names the pane's owner), so a
        sentence that changes with the session is re-read by `retranslate()` from ONE place.
        """
        row = corner_row(key)
        if row is None or button is None:
            return False
        if key in self.keys():
            return False        # ONE row per declared control — a second author is a defect
        if not corner_fits(len(self._controls) + 1):
            self._refused.append(key)
            log = _log()
            if log is not None:
                log.warning("corner budget %d refused the control '%s'", CORNER_MAX_CONTROLS, key)
            return False
        control = [row, button, tooltip]
        self._controls.append(control)
        self._shape(control)
        self._row.addWidget(button)
        return True

    def controls(self):
        """The buttons of the row, in the declared ORDER (the composition's read seam)."""
        return [button for _row, button, _tooltip in self._controls]

    def keys(self):
        """The keys this bar carries, in order."""
        return [row.key for row, _button, _tooltip in self._controls]

    def budget(self):
        """(used, max) — the ONE answer of the corner's budget."""
        return len(self._controls), CORNER_MAX_CONTROLS

    def refused(self):
        """The keys the budget refused (empty while the composition is legal)."""
        return tuple(self._refused)

    def refresh_theme(self) -> int:
        """Re-apply every control's glyph and stylesheet (a theme switch). Never raises."""
        for control in self._controls:
            self._shape(control)
        return len(self._controls)

    def retranslate(self):
        """Re-text the bar's MAX hint and every control's tooltip and accessible name."""
        self.refresh_text()
        for control in self._controls:
            self._shape(control)

    def refresh_text(self):
        """The bar's own sentence — the MAX hint the label-less corner owes the user."""
        try:
            self.setToolTip(_t("terminal.corner_tooltip", max=CORNER_MAX_CONTROLS))
        except RuntimeError:
            pass  # Qt teardown — the bar is already destroyed

    def _shape(self, control):
        """(Re-)apply ONE control's shape, its tooltip included."""
        row, button, provider = control
        tooltip = _t(row.tooltip_key)
        if callable(provider):
            try:
                tooltip = provider() or tooltip
            except RuntimeError:
                pass  # a dead control answers the declared sentence
        shape_control(button, row.glyph, tooltip, _t(row.label_key))
