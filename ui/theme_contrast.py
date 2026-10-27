# -*- coding: utf-8 -*-
"""The WCAG contrast table of the UI theme — the DECLARED pairs as pure DATA (`AGENTS.md` §4.6).

`CONTRAST_PAIRS` and `DECORATIVE` are the ONE home of the table and of the explained exemptions;
`relative_luminance()` / `contrast_ratio()` are the WCAG 2.x arithmetic and `contrast_problems()` runs
ONE resolved `Theme` instance against every row. TWO readers: `tests/test_theme_contrast.py` (the
DARK/LIGHT/auto gate and the completeness audit — it imports the table back) and `ui/theme_store.py`
(a theme pack is gated at LOAD time, so a built-in file fails the suite and a user file is refused with
the pairs that failed). Thresholds: **4.5** = text, **3.0** = a mark that carries meaning.

No Qt, no state. Mechanism — `DOCUMENTATION.md`, "Central UI theme"."""

# (label, foreground field, background field, threshold)
# The BACKGROUND is the surface the tone is really drawn on — a status dot sits on the CARD
# (`node_bg`), not on the canvas, which is what the 1.5rc1 review measured.
CONTRAST_PAIRS = [
    # ── text on the chrome ────────────────────────────────────────────────────
    ("body text on the window", "text_primary", "window_bg", 4.5),
    ("body text on a card surface", "text_primary", "base_bg", 4.5),
    ("body text on a button", "text_primary", "surface_alt", 4.5),
    ("body text on the canvas", "text_primary", "canvas_bg", 4.5),
    ("muted text on the window (the status bar, the hints)", "text_muted", "window_bg", 4.5),
    ("muted text on a card surface (the item views)", "text_muted", "base_bg", 4.5),
    ("muted text on the canvas", "text_muted", "canvas_bg", 4.5),
    ("a vector icon on the chrome", "icon_color", "window_bg", 3.0),
    ("a vector icon on a card surface", "icon_color", "base_bg", 3.0),
    # ── the STRONG accent: the ink and the fill that carries text ─────────────
    ("the strong accent as text on the window", "accent_strong", "window_bg", 4.5),
    ("the strong accent as text on the canvas", "accent_strong", "canvas_bg", 4.5),
    ("canvas text ON the strong accent (a selected row)", "canvas_bg", "accent_strong", 4.5),
    ("the strong hover as text on the window", "accent_strong_hover", "window_bg", 4.5),
    ("canvas text ON the strong hover (a hovered button)", "canvas_bg", "accent_strong_hover", 4.5),
    ("the strong selected as text on the window", "accent_strong_selected", "window_bg", 4.5),
    # ── the amber selection (it is INK as well: the multi-input counter) ──────
    ("the amber selection as text on the window", "selection_amber", "window_bg", 4.5),
    ("the amber selection as a mark on the canvas", "selection_amber", "canvas_bg", 3.0),
    ("the amber selection as a mark on a card", "selection_amber", "node_bg", 3.0),
    # ── the server card ───────────────────────────────────────────────────────
    ("the card text", "node_text", "node_bg", 4.5),
    ("the card label", "node_label", "node_bg", 4.5),
    ("the server glyph ON the icon plate", "node_text", "node_icon_bg", 3.0),
    ("the card outline on the canvas", "node_border", "canvas_bg", 3.0),
    ("the card outline on the card", "node_border", "node_bg", 3.0),
    ("the hover outline on the canvas (also the `vpn` arrow)", "node_hover", "canvas_bg", 3.0),
    ("the hover outline on the card", "node_hover", "node_bg", 3.0),
    ("the not-yet-checked dot on the card", "dot_idle", "node_bg", 3.0),
    # ── the three statuses: ON THE CARD (where the dot is) and on the canvas ──
    ("online on the card", "status_online", "node_bg", 3.0),
    ("online on the canvas", "status_online", "canvas_bg", 3.0),
    ("warn on the card", "status_warn", "node_bg", 3.0),
    ("warn on the canvas", "status_warn", "canvas_bg", 3.0),
    ("the 'no preview' marker of the SFTP rows", "status_warn", "base_bg", 3.0),
    ("offline on the card", "status_offline", "node_bg", 3.0),
    ("offline on the canvas", "status_offline", "canvas_bg", 3.0),
    # ── the tag strip (the card's own bottom bar) ─────────────────────────────
    ("the test tag on the card", "tag_test", "node_bg", 3.0),
    ("the backup tag on the card", "tag_backup", "node_bg", 3.0),
    ("the dmz tag on the card", "tag_dmz", "node_bg", 3.0),
    ("the pink tag on the card", "tag_pink", "node_bg", 3.0),
    ("the test tag on the canvas", "tag_test", "canvas_bg", 3.0),
    ("the backup tag on the canvas", "tag_backup", "canvas_bg", 3.0),
    ("the dmz tag on the canvas", "tag_dmz", "canvas_bg", 3.0),
    ("the pink tag on the canvas", "tag_pink", "canvas_bg", 3.0),
    # ── the groups ────────────────────────────────────────────────────────────
    ("the group frame", "group_border", "canvas_bg", 3.0),
    ("the group hover frame (also the `database` arrow)", "group_hover", "canvas_bg", 3.0),
    ("the group title", "group_title", "canvas_bg", 4.5),
    ("the selected group title", "group_title_selected", "canvas_bg", 4.5),
    ("the hovered group title", "group_title_hover", "canvas_bg", 4.5),
    # ── the six connection types: a 2 px stroke on the canvas ─────────────────
    ("the ssh arrow", "arrow_ssh", "canvas_bg", 4.5),
    ("the http arrow", "arrow_http", "canvas_bg", 4.5),
    ("the nfs arrow", "arrow_nfs", "canvas_bg", 4.5),
    ("the kubernetes arrow", "arrow_kubernetes", "canvas_bg", 4.5),
    ("the vpn arrow (derived from `node_hover`)", "node_hover", "canvas_bg", 4.5),
    ("the database arrow (derived from `group_hover`)", "group_hover", "canvas_bg", 4.5),
    ("the arrow hover tone", "arrow_hover_compat", "canvas_bg", 3.0),
    # ── the sticky note ───────────────────────────────────────────────────────
    ("the note text", "note_text", "note_bg", 4.5),
    ("the note outline on the canvas", "note_border", "canvas_bg", 3.0),
    ("the note outline on a card", "note_border", "node_bg", 3.0),
    # ── the SFTP viewer's syntax palette (on the QPlainTextEdit surface) ──────
    ("syntax: a number", "syntax_number", "base_bg", 4.5),
    ("syntax: a string", "syntax_string", "base_bg", 4.5),
    ("syntax: a key", "syntax_key", "base_bg", 4.5),
    ("syntax: a keyword", "syntax_keyword", "base_bg", 4.5),
    ("syntax: a comment", "syntax_comment", "base_bg", 4.5),
    ("syntax: a tag", "syntax_tag", "base_bg", 4.5),
    ("syntax: an attribute", "syntax_attribute", "base_bg", 4.5),
    ("syntax: punctuation", "syntax_punctuation", "base_bg", 4.5),
]

# A tone that carries NO meaning on its own is EXEMPT — with the reason written down. The rule of the
# line ("no new meaning only in a colour") is what makes the list this short: every element the user
# must TELL APART is gated above.
DECORATIVE = {
    "render_bg": "the fill of the export pixmap — drawBackground paints canvas_bg over it",
    "accent": "decoration: borders, focus outlines, the search-bar frame, the minimap frame, "
              "the rubber band, the reveal glow (v1.5rc1 keeps it decorative on purpose)",
    "accent_hover": "the hover shade of the same decoration",
    "accent_selected": "the selected shade of the same decoration",
}


def _channel(value: int) -> float:
    """One 0..255 sRGB channel → its linear value (the WCAG 2.x definition)."""
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    """The relative luminance of a "#rrggbb" colour (0 = black, 1 = white)."""
    value = str(color).strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"not a #rrggbb colour: {color!r}")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(foreground: str, background: str) -> float:
    """The WCAG contrast ratio between two colours (1.0 … 21.0)."""
    a, b = relative_luminance(foreground), relative_luminance(background)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def gated_fields() -> frozenset:
    """The theme fields the table measures as foreground or background (a typo cannot skip a tone)."""
    return frozenset(name for _label, fg, bg, _t in CONTRAST_PAIRS for name in (fg, bg))


def contrast_problems(instance) -> list:
    """The rows ONE resolved `Theme` instance fails, as `"<label>: N.NN (needs T)"` sentences.

    PURE: the instance is read by attribute, so the caller may pass any theme-shaped object. An
    empty answer is a GREEN gate — the shape `tests/test_theme_contrast.py` §4 and the pack loader
    (`ui/theme_store.py`) both read, so a built-in pack fails the suite and a user file is REFUSED.
    """
    problems = []
    for label, fg, bg, threshold in CONTRAST_PAIRS:
        ratio = contrast_ratio(getattr(instance, fg), getattr(instance, bg))
        if ratio < threshold:
            problems.append(f"{label}: {ratio:.2f} (needs {threshold})")
    return problems
