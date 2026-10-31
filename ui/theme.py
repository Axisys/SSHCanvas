# -*- coding: utf-8 -*-
"""Central UI theme — the ``Theme`` object: the single source of every colour, radius and font.

PURE DATA — nothing outside the standard library is imported (no PySide6, so it is importable
without a QApplication; the PySide6 half of the switch is ``ui/theme_qss.py``). The READING side
resolves at ACCESS time: a value captured at import time never follows ``set_theme()``, so a
consumer asks for ``theme.NODE_BG`` (the live proxy) or reads a live descriptor inside ``paint()``.
``Theme`` is frozen and ``DARK`` / ``LIGHT`` are the two instances; the accent shades, the declared
``ARROW_TYPE_STYLES`` / ``STATUS_SHAPES`` and the dict views (``STATUS_COLORS``, ``TAG_COLORS``,
``SYNTAX_COLORS``) all resolve against the ACTIVE instance. Out of scope: the terminal output
palettes, the draw.io colours and ``TerminalWidget.CURSOR_COLOR``. The cache rule, the numbers and
the gates — ``DOCUMENTATION.md`` (the "Central UI theme" chapter) and ``AGENTS.md`` §4.6."""

import copy
import dataclasses
import importlib
import importlib.util
from dataclasses import dataclass
from typing import Dict, List, Optional

# The default accent hue: the sky accent `#38bdf8`, whose HSL coordinates are the three numbers
# below. The HSL↔RGB formulas round 0.5 up, so the pair is pinned by the acceptance test as VALUES
# rather than as a claim: 198.4/93/59.6 reproduces the colour to the byte, while the obvious reading
# 198/92/60 gives `#3bbbf7` — three channels off, which is why it is written out.
DEFAULT_ACCENT_HUE = 198.4

# The saturation/lightness of the accent shades. They are FIXED so that the
# three shades of one hue stay a family; only the lightness moves (0 = base,
# ±5 = the natural hover / selection pair).
ACCENT_SATURATION = 93
ACCENT_LIGHTNESS = 59.6
ACCENT_HOVER_DELTA = 5      # the brighter/hover shade   (59.6 → 64.6)
ACCENT_SELECTED_DELTA = -5  # the darker/selection shade (59.6 → 54.6)

# The theme-mode ids of the "Appearance" tab / of the ``theme.mode`` key
# (v1.5rc1: `MODE_AUTO` joins them — the platform's own colour scheme decides).
MODE_DARK = "dark"
MODE_LIGHT = "light"
MODE_AUTO = "auto"
MODES = (MODE_DARK, MODE_LIGHT, MODE_AUTO)

# ── The CARD DENSITY ──────────────────────────────────────────────────────────
# The SECOND non-colour flag of the nested ``theme`` config object (the `motion` precedent):
# how much of a card the map paints. NOT a Theme field, but read live like every other datum
# here.   * ``normal``  — alias, host, the info plaque and the two badges (the DEFAULT,
# byte-identical to the pre-1.6 card);   * ``compact`` — alias, host and the status marks only.
DENSITY_NORMAL = "normal"
DENSITY_COMPACT = "compact"
DENSITIES = (DENSITY_NORMAL, DENSITY_COMPACT)

#: The ACTIVE density — module state, set by the "Appearance" tab and applied at startup
#: (`apply_density_setting`). Read through `card_density()`, never imported as a value.
_CARD_DENSITY = DENSITY_NORMAL


def resolve_density(value) -> str:
    """A stored density value → one of ``DENSITIES`` (a broken value = ``normal``).

    PURE validation: the config is hand-editable, so an unknown string, a number or
    ``None`` means the historical card, never an error.
    """
    text = str(value or "").strip().lower()
    return text if text in DENSITIES else DENSITY_NORMAL


def card_density() -> str:
    """The ACTIVE card density (``normal`` | ``compact``) — read by the cards."""
    return _CARD_DENSITY


def set_card_density(value) -> str:
    """Install the density and return the value that is now active (never raises)."""
    global _CARD_DENSITY
    _CARD_DENSITY = resolve_density(value)
    return _CARD_DENSITY

# ── THE SELECTION FRAME (v1.9.7) ──────────────────────────────────────────────
#: A selected card and a selected group share ONE frame decision: the amber `selection_amber` at
#: `SELECTION_FRAME_WIDTH`, DASHED at this pattern — the channel that survives greyscale, a
#: colour-vision deficiency and the print palette. The pattern is deliberately NOT either of the
#: scene's provisional dashes: Qt's `DashLine` (4, 2) of the rubber band, the note anchor's (4, 3).
SELECTION_DASH_PATTERN = (2.0, 3.0)
SELECTION_FRAME_WIDTH = 3

# The EXPORT palettes (v1.5rc2). An export is a different medium
# from the screen: it must not print a dark page, so the DEFAULT is `print` — the
# LIGHT instance (a white page with the high-contrast lines) — and `theme` is the
# opt-out that keeps the current look. The two ids are the vocabulary of
# `MapScene.render_to_*` / `export_scene_to_drawio` and of the export dialog.
PALETTE_PRINT = "print"
PALETTE_THEME = "theme"
EXPORT_PALETTES = (PALETTE_PRINT, PALETTE_THEME)

# ── the STRONG accent ─────────────────────────────────────────────────────────
# The second role of the same hue: the tone for TEXT on a surface and for a FILL that
# carries text, so it clears the AA threshold on the surfaces of its mode. In DARK it IS
# the decorative tone (the DARK look does not move a pixel); in LIGHT its hover/selected
# pair only ever goes DARKER. Numbers, roles and the gate — `DOCUMENTATION.md`, §4.6.
ACCENT_STRONG_LIGHTNESS = {MODE_DARK: ACCENT_LIGHTNESS, MODE_LIGHT: 34.0}
ACCENT_STRONG_HOVER_DELTA = {MODE_DARK: ACCENT_HOVER_DELTA, MODE_LIGHT: -4.0}
ACCENT_STRONG_SELECTED_DELTA = {MODE_DARK: ACCENT_SELECTED_DELTA, MODE_LIGHT: -8.0}



# ── The accent generator (pure: no Qt, no state) ──────────────────────────────

def hsl_hex(hue, saturation: float, lightness: float) -> str:
    """HSL → "#rrggbb" — PURE, no Qt. 198.4/93/59.6 is the default accent ``#38bdf8`` exactly."""
    h = (float(hue) % 360.0) / 360.0
    s = min(max(float(saturation), 0.0), 100.0) / 100.0
    li = min(max(float(lightness), 0.0), 100.0) / 100.0

    if s <= 0.0:
        v = int(round(li * 255))
        return "#{:02x}{:02x}{:02x}".format(v, v, v)
    q = li * (1.0 + s) if li < 0.5 else li + s - li * s
    p = 2.0 * li - q

    def channel(t: float) -> int:
        t = t % 1.0
        if t < 1.0 / 6.0:
            value = p + (q - p) * 6.0 * t
        elif t < 0.5:
            value = q
        elif t < 2.0 / 3.0:
            value = p + (q - p) * (2.0 / 3.0 - t) * 6.0
        else:
            value = p
        return int(round(value * 255))

    return "#{:02x}{:02x}{:02x}".format(channel(h + 1.0 / 3.0),
                                        channel(h), channel(h - 1.0 / 3.0))


def hex_hue(hex_color: str) -> float:
    """The hue (degrees, 1 decimal) of a "#rrggbb" colour — the reverse of :func:`hsl_hex`."""
    value = (hex_color or "").strip().lstrip("#")
    if len(value) != 6:
        return float(DEFAULT_ACCENT_HUE)
    try:
        r, g, b = (int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return float(DEFAULT_ACCENT_HUE)
    mx, mn = max(r, g, b), min(r, g, b)
    delta = mx - mn
    if delta <= 1e-9:
        return 0.0
    if mx == r:
        h = ((g - b) / delta) % 6.0
    elif mx == g:
        h = (b - r) / delta + 2.0
    else:
        h = (r - g) / delta + 4.0
    return round((h * 60.0) % 360.0, 1)


def accent_hex(hue=None) -> str:
    """The BASE accent of a hue (v1.4.3) — 199 → today's ``#38bdf8``."""
    return hsl_hex(DEFAULT_ACCENT_HUE if hue is None else hue,
                   ACCENT_SATURATION, ACCENT_LIGHTNESS)


def accent_hover_hex(hue=None) -> str:
    """The HOVER/brighter accent shade of a hue (60 → 70 lightness)."""
    return hsl_hex(DEFAULT_ACCENT_HUE if hue is None else hue,
                   ACCENT_SATURATION, ACCENT_LIGHTNESS + ACCENT_HOVER_DELTA)


def accent_selected_hex(hue=None) -> str:
    """The SELECTION/darker accent shade of a hue (60 → 50 lightness)."""
    return hsl_hex(DEFAULT_ACCENT_HUE if hue is None else hue,
                   ACCENT_SATURATION, ACCENT_LIGHTNESS + ACCENT_SELECTED_DELTA)


# ── The STRONG accent generator (v1.5rc1) ─────────────────────────────────────
# Same hue, same saturation — a different LIGHTNESS per mode, because the job of
# this tone is contrast rather than decoration (see the constants at the top).
# The mode argument is the RESOLVED mode ("dark"/"light"), never "auto".

def _strong_lightness(mode: str, delta: float = 0.0) -> float:
    """The lightness of a strong shade for a resolved mode (an unknown mode → DARK)."""
    base = ACCENT_STRONG_LIGHTNESS.get(mode, ACCENT_STRONG_LIGHTNESS[MODE_DARK])
    return base + delta


def accent_strong_hex(hue=None, mode: str = MODE_DARK) -> str:
    """The STRONG accent — text on a surface, a fill under text; DARK equals ``accent_hex()``."""
    return hsl_hex(DEFAULT_ACCENT_HUE if hue is None else hue,
                   ACCENT_SATURATION, _strong_lightness(mode))


def accent_strong_hover_hex(hue=None, mode: str = MODE_DARK) -> str:
    """The HOVER shade of the strong accent (+5 lightness in DARK, −4 in LIGHT)."""
    return hsl_hex(DEFAULT_ACCENT_HUE if hue is None else hue, ACCENT_SATURATION,
                   _strong_lightness(mode, ACCENT_STRONG_HOVER_DELTA.get(
                       mode, ACCENT_STRONG_HOVER_DELTA[MODE_DARK])))


def accent_strong_selected_hex(hue=None, mode: str = MODE_DARK) -> str:
    """The SELECTED shade of the strong accent (−5 lightness in DARK, −8 in LIGHT)."""
    return hsl_hex(DEFAULT_ACCENT_HUE if hue is None else hue, ACCENT_SATURATION,
                   _strong_lightness(mode, ACCENT_STRONG_SELECTED_DELTA.get(
                       mode, ACCENT_STRONG_SELECTED_DELTA[MODE_DARK])))


# ── The NOTE TONE (v1.14.2) ───────────────────────────────────────────────────
# ONE tone for every note of the map (AGENTS.md §4.6): the user's HUE shaded through the shipped
# sticky note's own three measures — its paper, the frame around it and the ink on it. A tone moves
# the hue of the family and nothing else, so the ink reads on whatever paper it is given.
NOTE_TONE_PAPER = (70.0, 78.0)    # the paper: the shipped yellow's paleness
NOTE_TONE_BORDER = (47.0, 45.0)   # the frame — the note's separation channel on a light canvas
NOTE_TONE_INK = (19.6, 21.0)      # the text and the header band's glyphs


def note_tone_colors(hue) -> tuple:
    """The ``(paper, frame, ink)`` of ONE note tone — PURE: a hue in, three "#rrggbb" out."""
    return (hsl_hex(hue, *NOTE_TONE_PAPER), hsl_hex(hue, *NOTE_TONE_BORDER),
            hsl_hex(hue, *NOTE_TONE_INK))


def resolve_note_tone(value):
    """A stored ``theme.note_tone`` → the hue of the note family, or None for the shipped one.

    ``None`` / ``""`` answer None — every instance keeps its OWN ``note_bg``/``note_border``/
    ``note_text``, so "no tone chosen" is byte-identical to the shipped note. A colour is accepted as
    the ``"#rrggbb"`` the settings tab stores (only its HUE is used) and a bare hue as a number.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        return hex_hue(value) if is_valid_hex(value) else None
    try:
        return round(float(value) % 360.0, 1)
    except (TypeError, ValueError):
        return None


def resolve_accent_hue(value):
    """A stored accent hue → a rounded hue, or None when there is no usable value."""
    if value is None:
        return None
    try:
        return round(float(value) % 360.0, 1)
    except (TypeError, ValueError):
        return None


# ── The second channel: per-type pen styles + status shapes ───────────────────
# OWNED HERE, next to the palettes they accompany, so a consumer (the arrow, the card dot,
# the sidebar row, the legend, the exports, the topical test) reads ONE source and a mark
# cannot drift from the map. A dash pattern and a shape are geometry, identical in DARK and
# LIGHT — but they are still reached through the ACTIVE theme (the §4.6 reading rule).

@dataclass(frozen=True)
class ArrowStyle:
    """How ONE connection type is DRAWN — the channel next to its colour.

    ``dash`` (a QPen dash pattern in pen widths, empty = solid), ``width`` (the stroke at rest; the
    hover adds ``ARROW_HOVER_WIDTH_DELTA``) and ``double`` (TWO rails — the stroke plus a narrower
    surface-coloured stroke over its centre, ``ARROW_CASING_RATIO`` wide).
    """

    dash: tuple = ()
    width: float = 2.2
    double: bool = False

    def is_solid(self) -> bool:
        """True for a plain unbroken stroke (the "no second channel here" case)."""
        return not self.dash and not self.double


# The hover widens the stroke instead of replacing its width, so a wide type stays the widest one.
ARROW_HOVER_WIDTH_DELTA = 0.6
# The share of the outer width the casing takes: 0.45 leaves two rails of ~1.1 px on the declared 4.0.
ARROW_CASING_RATIO = 0.45

# The SIX declared styles — pairwise distinct (the topical gate proves it) and
# readable at 100 % zoom: a solid line, three dash rhythms, a dense dot line and a
# double rail. The keys ARE the connection type ids of `arrow_type_colors`.
ARROW_TYPE_STYLES: Dict[str, ArrowStyle] = {
    "ssh": ArrowStyle(),                                   # solid — the default type
    "vpn": ArrowStyle(dash=(7.0, 4.0)),                    # dash
    "http": ArrowStyle(dash=(1.2, 3.0)),                   # dots
    "database": ArrowStyle(dash=(9.0, 3.0, 1.5, 3.0)),     # dash-dot
    "nfs": ArrowStyle(width=4.0, double=True),             # double rail
    "kubernetes": ArrowStyle(dash=(14.0, 5.0), width=2.4),  # long dash
}

DEFAULT_ARROW_STYLE = ARROW_TYPE_STYLES.get("ssh") or ArrowStyle()


def arrow_type_style(ctype: str) -> ArrowStyle:
    """The declared style of a connection type — an unknown type gets the default's."""
    return ARROW_TYPE_STYLES.get(ctype, DEFAULT_ARROW_STYLE)


# ── The declared STATUS SHAPES ──────────────────────
# The pinned set: a filled dot / a ring / a triangle — one shape per availability status, drawn by the
# card's status dot, the sidebar row's marker and the legend, so a status is readable in greyscale and
# for colour-vision deficiencies. The WORDS stay in the tooltips (`node.status.*`), which is what makes
# the shape a second channel rather than a replacement (`AGENTS.md` §4.6).
STATUS_SHAPE_DOT = "dot"
STATUS_SHAPE_RING = "ring"
STATUS_SHAPE_TRIANGLE = "triangle"
STATUS_SHAPE_IDS = (STATUS_SHAPE_DOT, STATUS_SHAPE_RING, STATUS_SHAPE_TRIANGLE)

STATUS_SHAPES: Dict[str, str] = {
    "online": STATUS_SHAPE_DOT,       # a full dot: the machine answers
    "warn": STATUS_SHAPE_RING,        # hollow: something is off, but it is alive
    "offline": STATUS_SHAPE_TRIANGLE,  # a warning sign: unreachable
}
# The shape of an UNCHECKED status (the idle grey marker).
DEFAULT_STATUS_SHAPE = STATUS_SHAPE_DOT


def status_shape(status) -> str:
    """The declared shape of an availability status — an unknown/empty one gets the dot."""
    return STATUS_SHAPES.get(status, DEFAULT_STATUS_SHAPE)


# ── "Auto (system)" ───────────────────────────────────────────────────────────
# The third mode reads the PLATFORM's colour scheme through `QStyleHints.colorScheme()`; the import
# is LAZY, which is how this module keeps its "no PySide6 at import time" contract. A platform without
# the hint (or a PySide6 that does not know the enum) behaves like the dark theme, never an error.

def system_color_scheme() -> str:
    """The platform's colour scheme as a mode id — DARK when unknown (never raises)."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
    except Exception:  # noqa: BLE001 — the module stays usable without Qt
        return MODE_DARK
    try:
        app = QGuiApplication.instance()
        if app is None:
            return MODE_DARK
        scheme = app.styleHints().colorScheme()
    except Exception:  # noqa: BLE001 — an old/limited platform has no hint
        return MODE_DARK
    try:
        if scheme == Qt.ColorScheme.Light:
            return MODE_LIGHT
    except Exception:  # noqa: BLE001
        return MODE_DARK
    return MODE_DARK


def resolve_mode(mode) -> str:
    """A mode id → a RESOLVED mode id ("dark"/"light") — never "auto", never an unknown value.

    "auto" asks the platform (``system_color_scheme()``); an unknown / missing / non-string value
    falls back to DARK, because a broken config must never leave the app themeless.
    """
    key = mode.strip().lower() if isinstance(mode, str) else MODE_DARK
    if key == MODE_AUTO:
        return system_color_scheme()
    return key if key in _MODES else MODE_DARK


def is_valid_hex(value) -> bool:
    """Is ``value`` a usable "#rrggbb" colour (the config.json validator)?"""
    if not isinstance(value, str):
        return False
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


# ── The Theme object ──────────────────────────────────────────────────────────
# Field names are the snake_case form of the historical constant names (CANVAS_BG → canvas_bg); the
# module proxies at the bottom restore the historical spelling for every existing consumer.

@dataclass(frozen=True)
class Theme:
    """Every colour, radius and font of the application UI, plus the two CHOICES that generate them.

    Frozen: a switch REPLACES the active instance (``set_theme()``), it never mutates one. The
    semantic dicts (``status_colors`` / ``tag_colors`` / ``tag_palette`` / ``arrow_type_colors`` /
    ``syntax_colors``) are DERIVED properties, not fields, so a value is declared exactly once. The
    choices — ``accent_hue`` and ``note_tone`` — are FIELDS, because a resolved instance carries the
    value it was generated from and a second resolution reads it back (``export_theme()``).
    """

    # ── Surfaces ─────────────────────────────────────────────────────────────
    canvas_bg: str         # canvas background: MapView + MapScene.drawBackground (visible in export too)
    render_bg: str         # initial pixmap fill in render_to_pixmap (drawBackground paints canvas_bg + grid on top)
    window_bg: str         # QPalette Window; minor grid lines; search bar card
    base_bg: str           # QPalette Base; node card background; major grid lines; collapse strip
    surface_alt: str       # QPalette AlternateBase/Button; dialog separators; hover strip

    # ── Text and icons ───────────────────────────────────────────────────────
    text_primary: str      # QPalette WindowText/Text/ButtonText, node text, dialog titles
    text_muted: str        # node labels, status-bar counters, terminal UI status labels
    icon_color: str        # vector icon outlines (ui/icons.py) + collapse-strip rhombi

    # ── Accent and selection ─────────────────────────────────────────────────
    accent_hue: Optional[float]  # the ONE accent source (None = DEFAULT_ACCENT_HUE)
    accent: str                 # the DECORATIVE accent (reveal flash, search frame, rubber band, borders)
    accent_hover: str           # the brighter decorative accent shade
    accent_selected: str        # the darker decorative accent shade
    accent_strong: str          # THE accent for text on a surface / a fill under text (v1.5rc1)
    accent_strong_hover: str    # the hover shade of the strong accent (v1.5rc1)
    accent_strong_selected: str  # the selected shade of the strong accent (v1.5rc1)
    selection_amber: str        # amber selection: selected node/group, multi-select badge/frame

    # ── Server node (card) ───────────────────────────────────────────────────
    node_bg: str
    node_border: str
    node_hover: str
    node_icon_bg: str
    node_text: str
    node_label: str
    dot_idle: str          # status/SSH dots before checking; @host label tone

    # ── Availability statuses (StatusChecker) ────────────────────────────────
    status_online: str
    status_warn: str
    status_offline: str

    # ── Tags / environment roles ─────────────────────────────────────────────
    tag_test: str
    tag_backup: str
    tag_dmz: str
    tag_pink: str

    # ── Groups (clusters/folders) ────────────────────────────────────────────
    group_border: str
    group_hover: str
    group_title: str
    group_title_selected: str
    group_title_hover: str

    # ── Connection arrows: types ─────────────────────────────────────────────
    arrow_ssh: str
    arrow_http: str
    arrow_nfs: str
    arrow_kubernetes: str
    arrow_hover_compat: str

    # ── Notes (stickies) ─────────────────────────────────────────────────────
    note_bg: str
    note_border: str
    note_text: str
    note_tone: Optional[float]  # the ONE tone's hue (None = this instance's own shipped family)

    # ── Syntax highlighting of the SFTP viewer ──────────────────────
    # A palette of its OWN, like the terminal output palettes of `modules/terminal_screen.py` — these
    # tones colour the READ-ONLY preview of `modules/sftp_tab.py` and nothing else. The names are the
    # ROLE names of `modules/syntax_highlight.py` (`syntax_<role>`), and the reader is the
    # `syntax_colors` property below (`DOCUMENTATION.md` §38).
    syntax_number: str
    syntax_string: str
    syntax_key: str
    syntax_keyword: str
    syntax_comment: str
    syntax_tag: str
    syntax_attribute: str
    syntax_punctuation: str

    # ── Corner radii (px) ────────────────────────────────────────────────────
    radius_node: float
    radius_note: float
    radius_group: float
    radius_search_bar: int      # integer px (QSS border-radius)
    radius_arrow_label: float
    radius_resize_mark: float
    radius_node_glyph_unit: float

    # ── Font families ────────────────────────────────────────────────────────
    font_ui: str
    font_mono: str

    # ── The semantic dicts (derived — declared once, above) ──────────────────

    @property
    def status_colors(self) -> Dict[str, str]:
        """Border colours by availability status (the v0.7.1 semantics)."""
        return {"online": self.status_online,
                "warn": self.status_warn,
                "offline": self.status_offline}

    @property
    def tag_colors(self) -> Dict[str, str]:
        """Known roles — the fixed colours (the v0.9.4 order)."""
        return {"prod": self.status_offline,   # red — production environment
                "staging": self.status_warn,   # yellow — staging
                "dev": self.status_online,     # green — development
                "test": self.tag_test,         # purple — test perimeter
                "backup": self.tag_backup,     # cyan — backup replica
                "dmz": self.tag_dmz}           # orange — demilitarized zone

    @property
    def tag_palette(self) -> List[str]:
        """Hash palette for arbitrary tags (crc32(name) % len): order fixed."""
        return [self.status_online, self.node_border, self.tag_test,
                self.tag_dmz, self.tag_backup, self.tag_pink]

    @property
    def arrow_type_colors(self) -> Dict[str, str]:
        """id → base arrow colour; declaration order = the connection dialog's combo."""
        return {"ssh": self.arrow_ssh,             # green — default
                "vpn": self.node_hover,            # blue (same value as the node hover border)
                "http": self.arrow_http,           # amber
                "database": self.group_hover,      # violet (same value as the group hover border)
                "nfs": self.arrow_nfs,             # pink
                "kubernetes": self.arrow_kubernetes}  # turquoise (Kubernetes)

    @property
    def arrow_type_styles(self) -> Dict[str, "ArrowStyle"]:
        """id → the declared PEN style of the connection type (v1.5rc2).

        The second channel next to :attr:`arrow_type_colors`: same keys, same
        declaration order, and the ONLY place a dash pattern / stroke width /
        "double line" is written down. Identical in DARK and LIGHT (geometry, not
        a colour), returned as a fresh dict so a consumer cannot mutate the map.
        """
        return dict(ARROW_TYPE_STYLES)

    @property
    def status_shapes(self) -> Dict[str, str]:
        """status → the declared SHAPE beside its colour (v1.5rc2).

        The second channel of the three availability statuses: the card's status dot, the sidebar row
        marker and the legend draw it, so a status survives greyscale / colour-vision deficiencies —
        in the SAME colour the status has always had (`status_colors`), never in a new tone.
        """
        return dict(STATUS_SHAPES)

    @property
    def sftp_preview_blocked(self) -> str:
        """A row the SFTP viewer refuses to preview (a binary / an over-limit file)."""
        return self.status_warn

    @property
    def syntax_colors(self) -> Dict[str, str]:
        """The SFTP viewer's syntax palette by ROLE (v1.4.7).

        The role vocabulary is ``modules/syntax_highlight.py``'s; the field of a role is
        ``syntax_<role>``, which is what ``syntax_highlight.syntax_field()`` answers and what the
        topical test pins against this dict — the two halves cannot drift.
        """
        return {"number": self.syntax_number,
                "string": self.syntax_string,
                "key": self.syntax_key,
                "keyword": self.syntax_keyword,
                "comment": self.syntax_comment,
                "tag": self.syntax_tag,
                "attribute": self.syntax_attribute,
                "punctuation": self.syntax_punctuation}

    def hue(self) -> float:
        """The resolved accent hue (``accent_hue`` or the default 198.4).

        A float on purpose: the default IS fractional, and rounding it here would move the default
        accent off ``#38bdf8``. A broken value falls back to the default.
        """
        value = self.accent_hue
        if value is None:
            return float(DEFAULT_ACCENT_HUE)
        try:
            return round(float(value) % 360.0, 1)
        except (TypeError, ValueError):
            return float(DEFAULT_ACCENT_HUE)

    def replace(self, **changes) -> "Theme":
        """A copy with the given fields replaced (the same contract as dataclasses.replace)."""
        return dataclasses.replace(self, **changes)


# ── DARK — the default; the pre-v1.4.3 constants, value for value ─────────────

DARK = Theme(
    # Surfaces (slate scale)
    canvas_bg="#020617",
    render_bg="#0b1220",
    window_bg="#0f172a",
    base_bg="#1e293b",
    surface_alt="#334155",

    # Text and icons
    text_primary="#e2e8f0",
    text_muted="#94a3b8",
    icon_color="#cbd5e1",

    # Accent: DARK's base accent IS #38bdf8; the STRONG family resolves to the same three values
    # (the role is new, the bytes are not — the literal snapshot test proves it).
    accent_hue=DEFAULT_ACCENT_HUE,
    accent=accent_hex(DEFAULT_ACCENT_HUE),
    accent_hover=accent_hover_hex(DEFAULT_ACCENT_HUE),
    accent_selected=accent_selected_hex(DEFAULT_ACCENT_HUE),
    accent_strong=accent_strong_hex(DEFAULT_ACCENT_HUE, MODE_DARK),
    accent_strong_hover=accent_strong_hover_hex(DEFAULT_ACCENT_HUE, MODE_DARK),
    accent_strong_selected=accent_strong_selected_hex(DEFAULT_ACCENT_HUE, MODE_DARK),
    selection_amber="#f59e0b",

    # Server node (card)
    node_bg="#1e293b",
    node_border="#3b82f6",
    node_hover="#60a5fa",
    node_icon_bg="#2563eb",
    node_text="#e2e8f0",
    node_label="#94a3b8",
    dot_idle="#64748b",

    # Availability statuses
    status_online="#22c55e",
    status_warn="#facc15",
    status_offline="#ef4444",

    # Tags / environment roles
    tag_test="#a855f7",
    tag_backup="#06b6d4",
    tag_dmz="#f97316",
    tag_pink="#ec4899",

    # Groups
    group_border="#7c3aed",
    group_hover="#a78bfa",
    group_title="#c4b5fd",
    group_title_selected="#fde68a",
    group_title_hover="#e9d5ff",

    # Connection arrows
    arrow_ssh="#34d399",
    arrow_http="#fbbf24",
    arrow_nfs="#f472b6",
    arrow_kubernetes="#22d3ee",
    arrow_hover_compat="#6ee7b7",

    # Notes — the muted yellow palette (kept by LIGHT too: it reads on a light background).
    # `note_tone = None` is the SHIPPED family: a chosen tone replaces all three (theme_for_mode).
    note_bg="#eedd9f",
    note_border="#a9853d",
    note_text="#403a2b",
    note_tone=None,

    # Syntax highlighting of the SFTP viewer: a SECOND ROLE SET over values DARK already ships. All
    # eight are distinct and none is the "no preview" tone (`status_warn`) — the topical test pins it.
    syntax_number="#fbbf24",        # the HTTP-arrow amber
    syntax_string="#34d399",        # the SSH-arrow green
    syntax_key="#22d3ee",           # the Kubernetes turquoise
    syntax_keyword="#a78bfa",       # the group-hover violet
    syntax_comment="#94a3b8",       # the muted text tone
    syntax_tag="#f472b6",           # the NFS-arrow pink
    syntax_attribute="#60a5fa",     # the node-hover blue
    syntax_punctuation="#cbd5e1",   # the icon outline tone

    # Corner radii
    radius_node=10.0,
    radius_note=10.0,
    radius_group=12.0,
    radius_search_bar=8,
    radius_arrow_label=5.0,
    radius_resize_mark=3.0,
    radius_node_glyph_unit=2.0,

    # Fonts
    font_ui="Segoe UI",
    font_mono="Consolas",
)


# ── LIGHT — the slate-100 counterpart ─────────────────────────────────────────
# The SAME field set as DARK (a one-sided field is refused by the completeness test); only what a light
# background really changes moves, and every number below is pinned by `tests/test_theme_contrast.py`.

LIGHT = Theme(
    # Surfaces (slate-100 scale)
    canvas_bg="#f8fafc",
    render_bg="#ffffff",
    window_bg="#f1f5f9",
    base_bg="#e2e8f0",
    surface_alt="#cbd5e1",

    # Text and icons — `text_muted` reaches AA on EVERY surface it is drawn on (5.57 / 5.17).
    text_primary="#0f172a",
    text_muted="#556070",
    icon_color="#475569",

    # Accent — the same hue generator as DARK (the user's hue survives a mode switch); the STRONG
    # shade is generated at the light lightness (34.0 → #0676a7: 4.83 on the canvas, 4.61 on the window).
    accent_hue=DEFAULT_ACCENT_HUE,
    accent=accent_hex(DEFAULT_ACCENT_HUE),
    accent_hover=accent_hover_hex(DEFAULT_ACCENT_HUE),
    accent_selected=accent_selected_hex(DEFAULT_ACCENT_HUE),
    accent_strong=accent_strong_hex(DEFAULT_ACCENT_HUE, MODE_LIGHT),
    accent_strong_hover=accent_strong_hover_hex(DEFAULT_ACCENT_HUE, MODE_LIGHT),
    accent_strong_selected=accent_strong_selected_hex(DEFAULT_ACCENT_HUE, MODE_LIGHT),
    # The selection amber is TEXT too (the status-bar selection lines) and a mark
    # on the canvas: amber-700 clears AA on the window (4.58) and 3:1 as a mark.
    selection_amber="#b45309",

    # Server node (card): the card is WHITE on the light canvas — that is what separates a node from the
    # background now (the halo shadow still works). The blues are ordered by strength: the resting
    # outline, the hover outline (also the `vpn` arrow) and the icon PLATE — which inverts with the
    # theme (a pale plate under the near-black glyph; the deep one left the glyph at 2.05:1).
    node_bg="#ffffff",
    node_border="#2563eb",
    node_hover="#1d4ed8",
    node_icon_bg="#93c5fd",
    node_text="#0f172a",
    node_label="#556070",
    # the "not checked yet" dot: LIGHT's own pale slate (3.46:1 on the white card,
    # where the v1.4.3 value measured 2.56 — and it is not DARK's own grey)
    dot_idle="#7c8ba1",

    # Availability statuses — deeper than the dark theme's (a dot sits on the
    # WHITE card, so the card is the surface that decides, not the canvas)
    status_online="#16a34a",
    status_warn="#a16207",
    status_offline="#dc2626",

    # Tags / environment roles (the two hash tones darkened a step as well)
    tag_test="#9333ea",
    tag_backup="#0891b2",
    tag_dmz="#ea580c",
    tag_pink="#db2777",

    # Groups — the violet family keeps its declaration order; the hover tone is
    # deepened so the `database` arrow (derived from it) clears 4.5 on the canvas
    group_border="#7c3aed",
    group_hover="#5b21b6",
    group_title="#6d28d9",
    group_title_selected="#92400e",
    group_title_hover="#7c3aed",

    # Connection arrows — re-tuned to the AA target of a 2 px stroke on the light
    # canvas (the review measured 3.04 … 4.39); `vpn` and `database` ARE
    # `node_hover` and `group_hover` — the derivation is kept, the two fields it
    # reads were re-tuned instead of being bypassed with a second table.
    arrow_ssh="#047857",
    arrow_http="#b45309",
    arrow_nfs="#be185d",
    arrow_kubernetes="#155e75",
    arrow_hover_compat="#065f46",

    # Notes — LIGHT's OWN sticky tone (v1.5rc1): the fill stays a paper colour by
    # design, so the note's separation channel is its BORDER (4.66:1 on the canvas)
    # and the cached halo shadow, which is what the gate pins.
    note_bg="#ecd284",
    note_border="#8a6d2f",
    note_text="#403a2b",
    note_tone=None,

    # Syntax highlighting of the SFTP viewer: the SAME role set, tuned for the light viewer background
    # (`base_bg` — the QPlainTextEdit surface the global QSS gives it), re-tuned to AA on THAT surface
    # (the first set measured 2.58 … 4.48 there). Again: eight distinct values, none of them the light
    # "no preview" tone (#a16207), every one of them a value this instance already ships elsewhere.
    syntax_number="#92400e",        # the group-title-selected amber
    syntax_string="#065f46",        # the arrow-hover green
    syntax_key="#155e75",           # the Kubernetes deep cyan
    syntax_keyword="#6d28d9",       # the group-title violet
    syntax_comment="#556070",       # the muted text tone
    syntax_tag="#be185d",           # the NFS-arrow pink
    syntax_attribute="#1d4ed8",     # the node-hover blue
    syntax_punctuation="#475569",   # the icon outline tone

    # Corner radii — geometry, identical in both instances
    radius_node=10.0,
    radius_note=10.0,
    radius_group=12.0,
    radius_search_bar=8,
    radius_arrow_label=5.0,
    radius_resize_mark=3.0,
    radius_node_glyph_unit=2.0,

    # Fonts — identical in both instances
    font_ui="Segoe UI",
    font_mono="Consolas",
)


# ── The active instance and the switch ───────────────────────────────────────

DARK_MODE = MODE_DARK     # the default mode: the dark theme stays the default
THEME: Theme = DARK       # THE ACTIVE instance — swapped by set_theme()

_MODES: Dict[str, Theme] = {MODE_DARK: DARK, MODE_LIGHT: LIGHT}


# ── The PACK REGISTRY ────────────────────────────────────────────────────────
# A pack is a FILE of declared overrides over ONE base mode (its schema, guard and discovery are
# `ui/theme_store.py`). ``PACKS`` is the registry the LOADER fills — never a hand-written dict — and
# `theme_for_mode(..., pack=…)` is the ONE resolution order: a pack is a `replace()` over one mode.

PACKS: Dict[str, object] = {}
PACK_PROBLEMS: List[object] = []      # the skipped files of the last load (the Appearance row says ONE)
_PACK_CACHE: Dict[tuple, Theme] = {}


def _pack_store():
    """`ui/theme_store.py` — imported LAZILY, so this module stays pure data at import time."""
    name = (__package__ + "." if __package__ else "") + "theme_store"
    if importlib.util.find_spec(name) is None:   # a stripped build: no packs, never a crash
        return None
    return importlib.import_module(name)


def packs(reload: bool = False) -> Dict[str, object]:
    """The loaded pack registry (id → pack): the loader runs ONCE; ``reload`` re-reads both folders."""
    if reload or not PACKS:
        PACKS.clear()
        del PACK_PROBLEMS[:]
        _PACK_CACHE.clear()
        store = _pack_store()
        if store is not None:
            loaded, problems = store.discover()
            PACKS.update(loaded)
            PACK_PROBLEMS.extend(problems)
    return PACKS


def pack_by_id(pack_id):
    """The pack of a stored id — a blank / foreign / unsafe id is NO pack (the mode's own look)."""
    store = _pack_store()
    if store is None or not store.is_safe_pack_id(pack_id):
        return None
    return packs().get(pack_id.strip())


def packs_for(mode) -> List[object]:
    """Every pack whose base IS the resolved mode, by display name — a dark pack never crosses over."""
    key = resolve_mode(mode)
    found = [pack for pack in packs().values() if getattr(pack, "base", None) == key]
    return sorted(found, key=lambda pack: str(pack.display()).lower())


def _pack_of(request, mode: str):
    """The pack a resolution names, or None — an unknown id and a FOREIGN base answer None."""
    entry = request if request is None or not isinstance(request, str) else pack_by_id(request)
    return entry if getattr(entry, "base", None) == mode else None


def theme_for_mode(mode, accent_hue=None, note_tone=None, pack=None) -> Theme:
    """The instance of a mode id with the pack's overrides, the accent hue and the note tone applied.

    The order is the DECLARED one: the base MODE is resolved first (``auto`` asks the platform), the
    pack's `colors` are a `dataclasses.replace()` over it, and only THEN the accent hue and the note
    tone — the user's two choices WIN over the file, and a pack's own `accent_hue` is the DEFAULT of an
    absent choice. Nothing to change answers the SHARED instance (the identity the tests and the caches
    rely on); a resolved pack is cached by its id AND its content (the shadowing rule).
    """
    key = resolve_mode(mode)
    base = _MODES.get(key) or DARK
    entry = _pack_of(pack, key)
    hue = resolve_accent_hue(accent_hue)
    if hue is None and entry is not None:
        hue = resolve_accent_hue(getattr(entry, "accent_hue", None))
    tone = resolve_note_tone(note_tone)
    if entry is None and (hue is None or hue == base.hue()) and tone is None:
        return base
    # An id is NOT a content: a user file SHADOWS the shipped pack under the same id, so the key names
    # the override set too — else the shipped instance answers for the user's file.
    cache_key = (key, hue, tone, getattr(entry, "id", None),
                 tuple(sorted((getattr(entry, "colors", None) or {}).items())))
    if len(_PACK_CACHE) > 128:            # a slider never grows the cache without a bound
        _PACK_CACHE.clear()
    if cache_key not in _PACK_CACHE:
        changes: Dict[str, object] = dict(getattr(entry, "colors", None) or {})
        if hue is not None and hue != base.hue():
            changes.update(
                accent_hue=hue, accent=accent_hex(hue), accent_hover=accent_hover_hex(hue),
                accent_selected=accent_selected_hex(hue),
                accent_strong=accent_strong_hex(hue, key),
                accent_strong_hover=accent_strong_hover_hex(hue, key),
                accent_strong_selected=accent_strong_selected_hex(hue, key))
        if tone is not None:
            paper, frame, ink = note_tone_colors(tone)
            changes.update(note_tone=tone, note_bg=paper, note_border=frame, note_text=ink)
        _PACK_CACHE[cache_key] = dataclasses.replace(base, **changes) if changes else base
    return _PACK_CACHE[cache_key]


def set_theme(instance: Theme) -> Theme:
    """Make ``instance`` the ACTIVE theme and return it (v1.4.3).

    Every live proxy / descriptor resolves against this pointer at ACCESS time, so a switch is visible
    immediately: no widget is rebuilt, no signal is emitted (the repaint is `ui/theme_qss.py`'s half).
    A non-Theme argument is IGNORED rather than raising, so a broken caller cannot leave the app
    half-switched.
    """
    global THEME
    if not isinstance(instance, Theme):
        return THEME
    THEME = instance
    return THEME


def current_theme() -> Theme:
    """The ACTIVE instance (the explicit form of ``THEME``)."""
    return THEME


# ── The export palette ────────────────────────────────────────────────────────
# An export renders PRINT-FRIENDLY by default and "print-friendly" is not a third palette: it IS
# `LIGHT`, asked for with the ACTIVE theme's accent hue. `theme` keeps the current look; both are
# addressed by the two ids above — ONE vocabulary. A theme PACK never reaches this resolver.

def resolve_export_palette(palette) -> str:
    """An export palette id → a KNOWN id (an unknown / missing value → `print`)."""
    key = palette.strip().lower() if isinstance(palette, str) else PALETTE_PRINT
    return key if key in EXPORT_PALETTES else PALETTE_PRINT


def export_theme(palette=PALETTE_PRINT, accent_hue=None) -> Theme:
    """The instance an EXPORT renders with (v1.5rc2) — a pack is never asked for here.

    ``print``  → the LIGHT instance with the ACTIVE theme's hue and note tone (the same instance
                 object whenever neither is the default one, so the common case costs nothing);
    ``theme``  → the ACTIVE instance, i.e. exactly what is on screen now.
    An unknown palette id resolves to ``print`` (``resolve_export_palette``).
    """
    if resolve_export_palette(palette) == PALETTE_THEME:
        return THEME
    hue = THEME.hue() if accent_hue is None else accent_hue
    return theme_for_mode(MODE_LIGHT, hue, THEME.note_tone)


def theme_snapshot() -> dict:
    """Every field of the ACTIVE instance as a plain dict (the config writer)."""
    return {f.name: copy.deepcopy(getattr(THEME, f.name)) for f in dataclasses.fields(Theme)}


# ── Live descriptors for CLASS-LEVEL constants (the `DOCUMENTATION.md` theme chapter) ──
# A class attribute CACHING a colour (``ServerNode.COLOR_BG = QColor(theme.NODE_BG)``) would capture
# the value at IMPORT time and keep the old theme forever, so the class-level constants are the three
# descriptors below — a FRESH QColor per access (Qt implicit sharing is the trap).

class ThemeColor:
    """``QColor(theme.<field>)`` of the ACTIVE theme — a theme field or a derived name.

    A class read returns the colour WITHOUT storing it, so a switch is picked up on the next paint.
    """

    __slots__ = ("_field", "_alpha")

    def __init__(self, field_name: str, alpha: int = 255):
        self._field = field_name
        self._alpha = int(alpha)

    def __get__(self, obj, objtype=None):
        from PySide6.QtGui import QColor  # lazy: the module stays Qt-free until used
        color = QColor(getattr(THEME, self._field))
        if self._alpha != 255:
            color.setAlpha(self._alpha)
        return color

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<ThemeColor {self._field!r} alpha={self._alpha}>"


class ThemeMap:
    """A class attribute that is a map (or a list) of one theme field.

    ``QColor`` values by default (``STATUS_COLORS`` / ``TAG_COLORS`` / ``TAG_PALETTE`` — the way the
    paint code and the tests read them); with ``as_hex=True`` the values stay the raw ``"#rrggbb"``.
    """

    __slots__ = ("_field", "_as_list", "_as_hex")

    def __init__(self, field_name: str, as_list: bool = False, as_hex: bool = False):
        self._field = field_name
        self._as_list = as_list
        self._as_hex = as_hex

    def __get__(self, obj, objtype=None):
        source = getattr(THEME, self._field)
        if self._as_hex:
            return list(source) if self._as_list else dict(source)
        from PySide6.QtGui import QColor  # lazy: the module stays Qt-free until used
        if self._as_list:
            return [QColor(value) for value in source]
        return {key: QColor(value) for key, value in source.items()}

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<ThemeMap {self._field!r} list={self._as_list} hex={self._as_hex}>"


class ThemeValue:
    """A class attribute computed from the ACTIVE theme on every access.

    The escape hatch for a colour that is not a plain field (a tinted fill, a value derived from
    another module). The factory is called LAZILY, so it may name a module constant declared later.
    """

    __slots__ = ("_factory",)

    def __init__(self, factory):
        self._factory = factory

    def __get__(self, obj, objtype=None):
        return self._factory()

    def __repr__(self):  # pragma: no cover - debugging aid
        name = getattr(self._factory, "__name__", repr(self._factory))
        return f"<ThemeValue {name}>"


# ── Live module-level constants ───────────────────────────────────────────────
# Every historical name (`theme.NODE_BG`, `theme.RADIUS_NODE`, …) is resolved by the PEP-562
# hook BELOW against the ACTIVE instance, on every access — that is what makes the switch
# reach a consumer that only wrote `theme.NODE_BG`. `THEME` stays a real `Theme` object, and
# a `from ui.theme import NODE_BG` would capture ONE value, so the project imports the module.

_LIVE_FIELDS: Dict[str, str] = {name: name.lower() for name in (
    # surfaces, text and icons
    "CANVAS_BG", "RENDER_BG", "WINDOW_BG", "BASE_BG", "SURFACE_ALT",
    "TEXT_PRIMARY", "TEXT_MUTED", "ICON_COLOR",
    # accent and selection
    "ACCENT", "ACCENT_HOVER", "ACCENT_SELECTED", "ACCENT_STRONG", "ACCENT_STRONG_HOVER",
    "ACCENT_STRONG_SELECTED", "SELECTION_AMBER",
    # server node (card)
    "NODE_BG", "NODE_BORDER", "NODE_HOVER", "NODE_ICON_BG", "NODE_TEXT", "NODE_LABEL", "DOT_IDLE",
    # availability statuses, tags, groups
    "STATUS_ONLINE", "STATUS_WARN", "STATUS_OFFLINE",
    "TAG_TEST", "TAG_BACKUP", "TAG_DMZ", "TAG_PINK",
    "GROUP_BORDER", "GROUP_HOVER", "GROUP_TITLE", "GROUP_TITLE_SELECTED", "GROUP_TITLE_HOVER",
    # connection arrows and notes
    "ARROW_SSH", "ARROW_HTTP", "ARROW_NFS", "ARROW_KUBERNETES", "ARROW_HOVER_COMPAT",
    "NOTE_BG", "NOTE_BORDER", "NOTE_TEXT",
    # syntax highlighting of the SFTP viewer
    "SYNTAX_NUMBER", "SYNTAX_STRING", "SYNTAX_KEY", "SYNTAX_KEYWORD", "SYNTAX_COMMENT",
    "SYNTAX_TAG", "SYNTAX_ATTRIBUTE", "SYNTAX_PUNCTUATION",
    # corner radii and fonts
    "RADIUS_NODE", "RADIUS_NOTE", "RADIUS_GROUP", "RADIUS_SEARCH_BAR", "RADIUS_ARROW_LABEL",
    "RADIUS_RESIZE_MARK", "RADIUS_NODE_GLYPH_UNIT",
    "FONT_UI", "FONT_MONO",
    # derived single values
    "SFTP_PREVIEW_BLOCKED")}

# The DERIVED dict/list names — a fresh object per access (so a consumer that
# holds one sees the values of the theme it asked of; a consumer that re-reads
# `theme.STATUS_COLORS` follows the switch). `is` is deliberately NOT identity
# here: `theme.ARROW_TYPE_COLORS == another_dict` is the contract (v1.4.3).
_LIVE_DERIVED: Dict[str, str] = {
    "STATUS_COLORS": "status_colors",
    "TAG_COLORS": "tag_colors",
    "TAG_PALETTE": "tag_palette",
    "ARROW_TYPE_COLORS": "arrow_type_colors",
    "SYNTAX_COLORS": "syntax_colors",
    # v1.5rc2: the two declared ENCODINGS (the pen styles and the status shapes)
    "ARROW_TYPE_STYLES": "arrow_type_styles",
    "STATUS_SHAPES": "status_shapes",
}


def __getattr__(name: str):
    """PEP-562 hook: resolve the historical constants against the ACTIVE theme.

    Anything not in the two mappings keeps its ordinary module semantics (an
    AttributeError), so `theme.does_not_exist` still fails loudly.
    """
    field_name = _LIVE_FIELDS.get(name)
    if field_name is not None:
        return getattr(THEME, field_name)
    prop_name = _LIVE_DERIVED.get(name)
    if prop_name is not None:
        return getattr(THEME, prop_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Include the live names in `dir(theme)` / the module's autocompletion."""
    return sorted(set(globals()) | set(_LIVE_FIELDS) | set(_LIVE_DERIVED))

