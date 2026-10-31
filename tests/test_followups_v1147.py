# -*- coding: utf-8 -*-
"""v1.14.7 — PAPER: the second theme pack, and the FIRST one over the LIGHT base — warm stock, graphite ink.
§1 the shipped file (the package folder, `builtin`, the schema); §2 the guard (the 36 fields, LIGHT's trio
and geometry BY VALUE, the warm stock and the graphite card); §3 the eight syntax inks; §4 the contrast
matrix over the RESOLVED instance; §5 the resolution order over the light base and the shadowing key; §6
the Appearance value (a light-mode combo that offers a pack for the FIRST time, and a `dark` switch that
drops it); §7 the pins.
Rule — `AGENTS.md` §4.6; mechanism — `DOCUMENTATION.md`, "Central UI theme".
Run: python tests/test_followups_v1147.py
"""
import dataclasses
import json
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text, check,
                     check_i18n_format, check_i18n_parity, check_release_state, clear_cfg, finish,
                     load_i18n_langs, releases_at_least, rep_doc_text, write_cfg)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import modules.syntax_highlight as SH  # noqa: E402
import ui.theme as theme  # noqa: E402
import ui.theme_contrast as theme_contrast  # noqa: E402
import ui.theme_store as store  # noqa: E402
import version  # noqa: E402
from ui.settings_dialog import SettingsDialog, load_theme_settings, theme_from_settings  # noqa: E402

LANGS = load_i18n_langs(ROOT)
PACK_FILE = os.path.join(ROOT, "themes", "paper.json")
EMPTY_USER_DIR = os.path.join(WORK, "no-user-themes")   # a HOME that holds no pack of its own
SYNTAX_FIELDS = {SH.syntax_field(role) for role in SH.SYNTAX_ROLES}
DEFAULT_ACCENT = theme.accent_hex()                       # the sky hue, the LIGHT default too
PACK_ACCENT = theme.accent_hex(218.0)                     # `themes/paper.json`'s declared hue
SURFACES = ("canvas_bg", "render_bg", "window_bg", "base_bg", "surface_alt")


def rgb(color):
    """The three channels of a "#rrggbb" colour."""
    value = color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def warm(color):
    """True when the RED channel is the strongest one — the paper stock and its graphite ink."""
    red, green, blue = rgb(color)
    return red >= green >= blue and red > blue


# ════════════════════════════════════════════════════════════════════════════
# §1 The shipped file — the seam's SECOND file, and its first LIGHT one
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the shipped file: the package folder, the LIGHT base and the schema ==")

_RAW = open(PACK_FILE, encoding="utf-8").read()
_DOC = json.loads(_RAW)
_MATRIX_DOC = json.loads(open(os.path.join(ROOT, "themes", "matrix.json"), encoding="utf-8").read())
_PACKS, _PROBLEMS = store.discover(root=ROOT, user_dir_path=EMPTY_USER_DIR)
_PACK = _PACKS.get("paper")

check("§1 `themes/paper.json` is the SECOND shipped pack — a FILE, never a mechanism",
      os.path.isfile(PACK_FILE) and store.package_dir(ROOT) == os.path.dirname(PACK_FILE),
      PACK_FILE)
check("§1 the file passes the store and lands in the registry as a BUILT-IN",
      _PACK is not None and _PACK.builtin is True and not _PROBLEMS,
      str([p.sentence() for p in _PROBLEMS]))
check("§1 TWO packs ship as TWO files (the folder is the registry's only source)",
      sorted(_PACKS) == ["matrix", "paper"]
      and all(pack.builtin and pack.path.endswith(f"{pack.id}.json")
              for pack in _PACKS.values()),
      str({pack_id: pack.path for pack_id, pack in _PACKS.items()}))
check("§1 the schema: base `light` (the base no pack covered before), `version` 1, the file's own name",
      _PACK is not None and _PACK.base == "light" and _PACK.version == store.PACK_VERSION
      and _PACK.name == "Paper" and _PACK.display() == "Paper" and _PACK.id == "paper",
      f"{_PACK}")
check("§1 the accent is declared as a HUE (`218`) and no terminal palette is suggested",
      _PACK.accent_hue == 218.0 and _PACK.terminal_palette is None,
      f"{_PACK.accent_hue} / {_PACK.terminal_palette!r}")
check("§1 the file is DATA: the closed root key set, a #rrggbb colour set and no code in it",
      set(_DOC) == {"name", "base", "version", "accent_hue", "colors"}
      and all(theme.is_valid_hex(value) for value in _DOC["colors"].values())
      and os.path.getsize(PACK_FILE) < 8 * 1024 and "settings." not in _RAW,
      f"{sorted(_DOC)} / {os.path.getsize(PACK_FILE)} bytes")


# ════════════════════════════════════════════════════════════════════════════
# §2 The guard — the whole allowlist set, and LIGHT's locked tones BY VALUE
# ════════════════════════════════════════════════════════════════════════════
print("== §2 the guard: the 36 fields, the locked tones of LIGHT and the warm stock ==")

_INSTANCE = theme.theme_for_mode("light", None, None, pack=_PACK)

check("§2 the pack sets EVERY field a pack may set (the whole allowlist, nothing outside it)",
      set(_PACK.colors) == set(store.ALLOWED_COLORS),
      f"missing={sorted(set(store.ALLOWED_COLORS) - set(_PACK.colors))} "
      f"stray={sorted(set(_PACK.colors) - set(store.ALLOWED_COLORS))}")
check("§2 the status trio is NOT in the file — it inherits LIGHT BY VALUE (the guard refuses it)",
      not ({"status_online", "status_warn", "status_offline"} & set(_PACK.colors))
      and _INSTANCE.status_colors == theme.LIGHT.status_colors,
      str(_INSTANCE.status_colors))
check("§2 the trust surface's warning tone is LIGHT's too (`selection_amber`)",
      "selection_amber" not in _PACK.colors
      and _INSTANCE.selection_amber == theme.LIGHT.selection_amber,
      f"{_INSTANCE.selection_amber} / {theme.LIGHT.selection_amber}")
check("§2 the semantic tag strip keeps LIGHT's four tones",
      "tag_test" not in _PACK.colors
      and all(getattr(_INSTANCE, f"tag_{name}") == getattr(theme.LIGHT, f"tag_{name}")
              for name in ("test", "backup", "dmz", "pink")))
check("§2 the geometry is untouched — every radius and both fonts are LIGHT's",
      all(getattr(_INSTANCE, field.name) == getattr(theme.LIGHT, field.name)
          for field in dataclasses.fields(theme.Theme)
          if field.name.startswith("radius_") or field.name.startswith("font_")),
      str([field.name for field in dataclasses.fields(theme.Theme)
           if field.name.startswith("radius_")]))
check("§2 the stock is the declared paper ramp (canvas, export fill, window, base, controls)",
      _INSTANCE.canvas_bg == "#fdfaf3" and _INSTANCE.render_bg == "#fffefa"
      and _INSTANCE.window_bg == "#fbf7ee" and _INSTANCE.base_bg == "#f6f1e6"
      and _INSTANCE.surface_alt == "#eae2d1",
      str([(name, getattr(_INSTANCE, name)) for name in SURFACES]))
check("§2 every surface and every ink tone is WARM (the red channel leads — paper, never slate)",
      all(warm(getattr(_INSTANCE, name)) for name in SURFACES)
      and all(warm(getattr(_INSTANCE, name)) for name in
              ("text_primary", "text_muted", "icon_color", "node_text", "node_label")),
      str([(name, getattr(_INSTANCE, name)) for name in SURFACES]))
check("§2 the card is the paper's own: a white fill, a GRAPHITE frame and a pencil-plate icon",
      _INSTANCE.node_bg == "#fffefa" and _INSTANCE.node_border == "#6f6757"
      and _INSTANCE.node_icon_bg == "#ded4bd" and _INSTANCE.dot_idle == "#7a7264"
      and warm(_INSTANCE.node_border) and warm(_INSTANCE.node_icon_bg),
      f"{_INSTANCE.node_border} / {_INSTANCE.node_icon_bg}")
check("§2 the accent is the only COOL tone on the map's chrome (no other field is blue-leaning)",
      all(warm(getattr(_INSTANCE, name)) for name in
              ("node_bg", "node_border", "node_hover", "node_icon_bg", "node_text",
               "node_label", "dot_idle", "group_border", "group_hover", "group_title",
               "group_title_selected", "group_title_hover"))
      and rgb(_INSTANCE.accent_strong)[2] > rgb(_INSTANCE.accent_strong)[0],
      f"accent_strong={_INSTANCE.accent_strong}")
check("§2 the four connection types keep FOUR tones (meaning is not flattened into one ink)",
      len({_INSTANCE.arrow_ssh, _INSTANCE.arrow_http, _INSTANCE.arrow_nfs,
           _INSTANCE.arrow_kubernetes}) == 4,
      str([_INSTANCE.arrow_ssh, _INSTANCE.arrow_http, _INSTANCE.arrow_nfs,
           _INSTANCE.arrow_kubernetes]))
check("§2 the note family is a sticky pad, and the user's `theme.note_tone` still WINS over it",
      _INSTANCE.note_bg == "#fff3c4" and _INSTANCE.note_border == "#866817"
      and _INSTANCE.note_text == "#3d3320"
      and theme.theme_for_mode("light", None, "#ff8800", pack="paper").note_bg
      == theme.note_tone_colors(theme.hex_hue("#ff8800"))[0],
      f"{_INSTANCE.note_bg} / {_INSTANCE.note_border} / {_INSTANCE.note_text}")


# ════════════════════════════════════════════════════════════════════════════
# §3 The eight syntax tones of the plain-text reader
# ════════════════════════════════════════════════════════════════════════════
print("== §3 the eight syntax inks: declared, distinct and readable on the pack's own surface ==")

check("§3 exactly the EIGHT roles of the tokenizer vocabulary are declared (no ninth tone)",
      set(_PACK.colors) & SYNTAX_FIELDS == SYNTAX_FIELDS and len(SYNTAX_FIELDS) == 8
      and not [f for f in _PACK.colors if f.startswith("syntax_") and f not in SYNTAX_FIELDS],
      str(sorted(f for f in _PACK.colors if f.startswith("syntax_"))))
check("§3 the resolved reader palette IS the file's — the reader follows the pack",
      tuple(_INSTANCE.syntax_colors) == SH.SYNTAX_ROLES
      and _INSTANCE.syntax_colors
      == {role: _PACK.colors[SH.syntax_field(role)] for role in SH.SYNTAX_ROLES},
      str(_INSTANCE.syntax_colors))
check("§3 the eight tones are pairwise DISTINCT (a role must be tellable apart)",
      len(set(_INSTANCE.syntax_colors.values())) == 8,
      str(sorted(set(_INSTANCE.syntax_colors.values()))))
_RATIOS = {role: theme_contrast.contrast_ratio(tone, _INSTANCE.base_bg)
           for role, tone in _INSTANCE.syntax_colors.items()}
check("§3 every ink clears 4.5:1 on the PACK's own viewer surface (the reader's background)",
      all(ratio >= 4.5 for ratio in _RATIOS.values()),
      str({role: round(ratio, 2) for role, ratio in _RATIOS.items()}))
check("§3 the WORST of the eight is 5.63:1 — the margin is measured, not assumed",
      round(min(_RATIOS.values()), 2) == 5.63, str(round(min(_RATIOS.values()), 2)))
check("§3 none of them is the 'no preview' tone (the marker of a refused row)",
      all(tone != _INSTANCE.sftp_preview_blocked for tone in _INSTANCE.syntax_colors.values()),
      _INSTANCE.sftp_preview_blocked)


# ════════════════════════════════════════════════════════════════════════════
# §4 The contrast matrix — over the instance the FILE resolves to
# ════════════════════════════════════════════════════════════════════════════
print("== §4 the contrast matrix over the RESOLVED instance (a built-in that fails is a SUITE failure) ==")

_FAILURES = theme_contrast.contrast_problems(_INSTANCE)
check("§4 the matrix is the SHIPPED table (one home, imported back — never a second copy)",
      len(theme_contrast.CONTRAST_PAIRS) == 64 and bool(theme_contrast.DECORATIVE),
      str(len(theme_contrast.CONTRAST_PAIRS)))
check("§4 the Paper pack clears EVERY declared pair (4.5 for text, 3.0 for a mark)",
      not _FAILURES, "; ".join(_FAILURES[:4]))
check("§4 the gate really measured the PACK and not LIGHT (the instance is the file's)",
      _INSTANCE.canvas_bg == "#fdfaf3" and _INSTANCE.base_bg == "#f6f1e6"
      and _INSTANCE.canvas_bg != theme.LIGHT.canvas_bg,
      f"{_INSTANCE.canvas_bg} / {_INSTANCE.base_bg}")
check("§4 the gate is not vacuous — a muted tone on its own canvas FAILS it",
      bool(theme_contrast.contrast_problems(
          dataclasses.replace(_INSTANCE, text_muted=_INSTANCE.canvas_bg))))
_REFUSED = store.parse_pack(dict(_DOC, colors=dict(_DOC["colors"], text_muted="#fdfaf3")), "probe")
check("§4 the LOADER refuses the same defect by its failing pairs (never a half-applied file)",
      _REFUSED[0] is None and _REFUSED[1][0].reason == store.REASON_CONTRAST
      and "muted text" in _REFUSED[1][0].detail, _REFUSED[1][0].detail)
# The DECISION behind the stock: a deeper cream is refused by the LOCKED status tone, not by taste.
_DEEPER = store.parse_pack(dict(_DOC, colors=dict(_DOC["colors"], canvas_bg="#f4eee2")), "probe")
check("§4 a deeper cream is refused — the locked `status_online` fails 3.0 on it (2.85:1)",
      _DEEPER[0] is None and _DEEPER[1][0].reason == store.REASON_CONTRAST
      and "online on the canvas" in _DEEPER[1][0].detail
      and theme_contrast.contrast_ratio(theme.LIGHT.status_online, "#f4eee2") < 3.0,
      _DEEPER[1][0].detail)
check("§4 loading the pack edits NO base instance (DARK and LIGHT keep their literals)",
      theme.DARK.canvas_bg == "#020617" and theme.LIGHT.canvas_bg == "#f8fafc"
      and theme.DARK.accent == "#38bdf8" and theme.LIGHT.node_bg == "#ffffff",
      f"{theme.DARK.canvas_bg} / {theme.LIGHT.canvas_bg}")


# ════════════════════════════════════════════════════════════════════════════
# §5 The resolution order over the LIGHT base — base → file → the user's choices
# ════════════════════════════════════════════════════════════════════════════
print("== §5 record: the light base first, the file over it, the user's choices, and the shadowing key ==")

_BY_ID = theme.theme_for_mode("light", None, None, pack="paper")
check("§5 a stored ID resolves through the registry (no pack object is passed in)",
      _BY_ID.canvas_bg == "#fdfaf3" and _BY_ID.node_bg == "#fffefa", _BY_ID.canvas_bg)
check("§5 ...and it is the SAME cached instance (`==` AND `is` — the identity the switch relies on)",
      _BY_ID == _INSTANCE and _BY_ID is not theme.LIGHT
      and _BY_ID is theme.theme_for_mode("light", None, None, pack="paper"))
check("§5 the pack's HUE generates the six accent tones at the LIGHT strength (no colour literal)",
      _INSTANCE.accent_hue == 218.0 and _INSTANCE.accent == theme.accent_hex(218.0)
      and _INSTANCE.accent_strong == theme.accent_strong_hex(218.0, theme.MODE_LIGHT)
      and _INSTANCE.accent_strong == "#0641a7",
      f"{_INSTANCE.accent} / {_INSTANCE.accent_strong}")
check("§5 the USER's accent WINS over the file's suggestion",
      theme.theme_for_mode("light", 280.0, None, pack="paper").accent == theme.accent_hex(280.0),
      theme.theme_for_mode("light", 280.0, None, pack="paper").accent)
check("§5 a pack of the other base never crosses over (a light pack over the dark mode)",
      theme.theme_for_mode("dark", None, None, pack="paper") is theme.DARK
      and theme.theme_for_mode("light", None, None, pack="matrix") is theme.LIGHT)
check("§5 `export_theme()` never takes a pack (a report is a white page, not a stock)",
      theme.export_theme().canvas_bg == theme.LIGHT.canvas_bg
      and theme.export_theme(theme.PALETTE_THEME) is theme.THEME)
# Why the ink is BLUE: the teal an "ink stamp" wants cannot pass the six accent rows of the table.
_TEAL = theme.theme_for_mode("light", 174.0)
check("§5 hue 174 (the obvious ink teal) is refused by the accent rows — 2.75:1 on the window",
      bool(theme_contrast.contrast_problems(_TEAL))
      and round(theme_contrast.contrast_ratio(theme.accent_strong_hex(174.0, theme.MODE_LIGHT),
                                              theme.LIGHT.window_bg), 2) == 2.75,
      str(theme_contrast.contrast_problems(_TEAL)[:2]))

# The cache names the pack's CONTENT: a user file SHADOWS the shipped pack under the SAME id.
os.makedirs(store.user_dir(), exist_ok=True)
_USER_PACK = os.path.join(store.user_dir(), "matrix.json")


def write_user_pack(doc):
    """One user file in the isolated HOME's `themes/` — the folder the loader really reads."""
    with open(_USER_PACK, "w", encoding="utf-8") as handle:
        json.dump(doc, handle)


write_user_pack(dict(_MATRIX_DOC, colors=dict(_MATRIX_DOC["colors"], canvas_bg="#112233")))
theme.packs(reload=True)
check("§5 a user file shadows the shipped pack of the same id — the CONTENT decides, never the id",
      theme.PACKS["matrix"].builtin is False
      and theme.theme_for_mode("dark", None, None, pack="matrix").canvas_bg == "#112233",
      f"{theme.PACKS['matrix'].path} / "
      f"{theme.theme_for_mode('dark', None, None, pack='matrix').canvas_bg}")
write_user_pack(dict(_MATRIX_DOC, colors=dict(_MATRIX_DOC["colors"], text_muted="#112233")))
theme.packs(reload=True)
check("§5 ...and a BROKEN override is refused by the gate that measured IT (the shipped pack stays)",
      theme.PACKS["matrix"].builtin is True and bool(theme.PACK_PROBLEMS)
      and theme.PACK_PROBLEMS[0].reason == store.REASON_CONTRAST,
      str([p.sentence() for p in theme.PACK_PROBLEMS]))
os.remove(_USER_PACK)
theme.packs(reload=True)
check("§5 ...and removing it restores the built-in (shadowing is not a replacement)",
      theme.PACKS["matrix"].builtin is True and not theme.PACK_PROBLEMS
      and theme.theme_for_mode("dark", None, None, pack="matrix").canvas_bg == "#000a04",
      f"{sorted(theme.PACKS)} / {[p.sentence() for p in theme.PACK_PROBLEMS]}")


# ════════════════════════════════════════════════════════════════════════════
# §6 The Appearance value — a LIGHT combo that offers a pack for the FIRST time
# ════════════════════════════════════════════════════════════════════════════
print("== §6 the Appearance value: the light combo, the suggestions, `collect()` and the drop ==")

theme.packs(reload=True)
check("§6 the LIVE registry holds BOTH shipped packs, so the row offers them with no user file",
      sorted(theme.PACKS) == ["matrix", "paper"] and not theme.PACK_PROBLEMS,
      f"{sorted(theme.PACKS)} / {[p.sentence() for p in theme.PACK_PROBLEMS]}")
check("§6 `packs_for()` splits the two packs by BASE — the light one is finally offered",
      [pack.id for pack in theme.packs_for("light")] == ["paper"]
      and [pack.id for pack in theme.packs_for("dark")] == ["matrix"],
      f"{[p.id for p in theme.packs_for('light')]} / {[p.id for p in theme.packs_for('dark')]}")

clear_cfg()
_DLG = SettingsDialog(None)
_EMITTED = []
_DLG.theme_changed.connect(_EMITTED.append)
check("§6 the dialog opens on the DARK base, whose combo holds that base's pack alone",
      _DLG.pack_combo.count() == 2 and _DLG.pack_combo.itemData(1) == "matrix",
      str([(_DLG.pack_combo.itemText(i), _DLG.pack_combo.itemData(i))
           for i in range(_DLG.pack_combo.count())]))
_DLG.theme_mode_combo.setCurrentIndex(1)   # light — the base that had nothing to offer
check("§6 a mode switch to LIGHT re-reads the combo: `Default` then `Paper` (the FIRST light pack)",
      _DLG._pack_id == "" and _DLG.pack_combo.count() == 2
      and _DLG.pack_combo.itemData(1) == "paper" and _DLG.pack_combo.itemText(1) == "Paper"
      and _DLG.pack_combo.currentIndex() == 0,
      str([(_DLG.pack_combo.itemText(i), _DLG.pack_combo.itemData(i))
           for i in range(_DLG.pack_combo.count())]))
_DLG.pack_combo.setCurrentIndex(_DLG.pack_combo.findData("paper"))
check("§6 choosing Paper applies its SUGGESTED hue and the pack's stock (a SUGGESTION, live)",
      _DLG._pack_id == "paper" and _DLG._accent_hex == PACK_ACCENT
      and _DLG._own_accent_hex == DEFAULT_ACCENT
      and _EMITTED and _EMITTED[-1].canvas_bg == "#fdfaf3"
      and abs(_EMITTED[-1].accent_hue - 218.0) < 1.0,
      f"{_DLG._accent_hex} / {_EMITTED[-1].canvas_bg if _EMITTED else None}")
check("§6 ...and `collect()` writes the id into the SAME nested `theme` key (30 keys)",
      _DLG.collect()["theme"].get("pack") == "paper" and len(_DLG.collect()) == 30,
      str(_DLG.collect()["theme"]))
check("§6 the store round trip: the written key re-reads and re-resolves to the same instance",
      theme_from_settings(dict(load_theme_settings(), mode="light", accent=_DLG._accent_hex,
                               pack="paper")).canvas_bg == "#fdfaf3")
_DLG.theme_mode_combo.setCurrentIndex(0)   # back to dark: the light pack cannot cross over
check("§6 a switch back to DARK drops the light pack and gives the accent back to the user",
      _DLG._pack_id == "" and _DLG.pack_combo.count() == 2
      and _DLG.pack_combo.itemData(1) == "matrix"
      and _DLG._accent_hex == DEFAULT_ACCENT
      and "pack" not in _DLG.collect()["theme"],
      f"{_DLG._pack_id!r} / {_DLG._accent_hex} / {_DLG.collect()['theme']}")
_DLG.reject()
check("§6 Cancel restores the theme the dialog OPENED with", theme.THEME is theme.DARK)
_DLG.close()

# A config a previous start left holding the pack's suggestion is HEALED on the next open.
write_cfg({"theme": {"mode": "light", "accent": PACK_ACCENT, "motion": True,
                     "density": "normal", "pack": "paper"}})
theme.packs(reload=True)
_DLG = SettingsDialog(None)
_EMITTED = []
_DLG.theme_changed.connect(_EMITTED.append)
check("§6 a stored light pack + its own suggested colour opens ON the pack (the stock is the file's)",
      _DLG._pack_id == "paper" and _DLG._accent_hex == PACK_ACCENT
      and _DLG.pack_combo.currentData() == "paper",
      f"{_DLG._pack_id!r} / {_DLG._accent_hex}")
check("§6 ...while its real OWNER is the default accent (the suggestion is not a user choice)",
      _DLG._own_accent_hex == DEFAULT_ACCENT, _DLG._own_accent_hex)
_DLG.pack_combo.setCurrentIndex(0)   # `Default`
check("§6 `Default` returns the light page AND the user's own accent",
      _DLG._pack_id == "" and _DLG._accent_hex == DEFAULT_ACCENT
      and _EMITTED and _EMITTED[-1].canvas_bg == theme.LIGHT.canvas_bg
      and "pack" not in _DLG.collect()["theme"],
      f"{_DLG._accent_hex} / {_EMITTED[-1].canvas_bg if _EMITTED else None}")
_DLG.reject()
_DLG.close()
clear_cfg()


# ════════════════════════════════════════════════════════════════════════════
# §7 The release pins
# ════════════════════════════════════════════════════════════════════════════
print("== §7 the release pins: the version, the parity, the packaging and the documents ==")

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§7 the pack adds NO i18n key — a pack carries values, not strings (parity {EXPECTED_I18N_KEYS})",
      len([key for key in LANGS["en"] if key not in ("name", "partial")]) == EXPECTED_I18N_KEYS
      and not [key for key in LANGS["en"] if "paper" in key.lower()],
      str([key for key in LANGS["en"] if "paper" in key.lower()]))
check(f"§7 the release is {EXPECTED_APP_VERSION} and the JSON schema did not move",
      version.APP_VERSION == EXPECTED_APP_VERSION and version.VERSION_FORMAT == "0.9"
      and releases_at_least(EXPECTED_APP_VERSION, "1.14.7"),
      f"{version.APP_VERSION} / {version.VERSION_FORMAT}")
_PYPROJECT = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
check("§7 both packs SHIP: `themes = [\"*.json\"]` carries the folder, the file is on disk",
      '"themes",' in _PYPROJECT and 'themes = ["*.json"]' in _PYPROJECT
      and os.path.isfile(PACK_FILE) and os.path.isfile(os.path.join(ROOT, "themes", "matrix.json")))
check("§7 the suite map lists this file (tests/INDEX.md regenerated)",
      "test_followups_v1147" in open(os.path.join(ROOT, "tests", "INDEX.md"),
                                     encoding="utf-8").read())
_FAMILY = changelog_family_text(ROOT)
_DETAILS = changelog_family_text(ROOT, "DETAILS")
check("§7 the changelog family carries the release (the LIVE file or a CLOSED line of it)",
      (not _FAMILY or "v1.14.7" in _FAMILY) and (not _DETAILS or "v1.14.7" in _DETAILS),
      f"changelog={'v1.14.7' in _FAMILY} details={'v1.14.7' in _DETAILS}")
_ROADMAP_TEXT = rep_doc_text("ROADMAP.md")
check("§7 the plan of record no longer carries the shipped section",
      not _ROADMAP_TEXT or "## v1.14.7" not in _ROADMAP_TEXT)
_AGENTS_TEXT = rep_doc_text("AGENTS.md")
_DOC_TEXT = rep_doc_text("DOCUMENTATION.md")
check("§7 the contract names the second pack and the mechanism documents it",
      (not _AGENTS_TEXT or "themes/paper.json" in _AGENTS_TEXT)
      and (not _DOC_TEXT or "themes/paper.json" in _DOC_TEXT),
      f"agents={'themes/paper.json' in _AGENTS_TEXT} docs={'themes/paper.json' in _DOC_TEXT}")

finish()
