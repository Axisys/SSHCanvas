# -*- coding: utf-8 -*-
"""The accent VOCABULARY: the eight preset hues of the application, in ONE PURE home (AGENTS.md §4.6).

`ACCENT_PRESETS` is a `(name, hue)` table whose NAME is the i18n suffix of
`settings.appearance.accent.<name>`; sky is FIRST and equals `theme.DEFAULT_ACCENT_HUE`, so "the
default look" is the leftmost entry. TWO readers share the table — the "Appearance" tab's swatches
(`ui/settings_dialog.py`) and the Files reader's background chip (`modules/sftp_pane_helpers.py`) —
so a preset that moves moves both, and a colour is always COMPUTED from its hue (`theme.accent_hex`,
`theme_qss.viewer_background_hex`), never typed. No Qt: `theme` is pure data.
Mechanism — `DOCUMENTATION.md`, "Central UI theme".
"""
try:  # the default hue the sky preset IS (`ui/theme.py`, pure data — no Qt)
    from . import theme
except ImportError:
    try:
        from ui import theme
    except ImportError:  # flat layout: the ui/ directory itself is on sys.path
        import theme

#: `(name, hue)` — the ORDER is the order the two surfaces show, sky first.
ACCENT_PRESETS = (("sky", theme.DEFAULT_ACCENT_HUE),
                  ("cyan", 187.0),
                  ("green", 142.0),
                  ("amber", 38.0),
                  ("orange", 25.0),
                  ("pink", 330.0),
                  ("violet", 262.0),
                  ("slate", 215.0))
