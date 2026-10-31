# -*- coding: utf-8 -*-
"""v1.14.5 — THE MATRIX: the first theme pack is a FILE of DATA — green phosphor over black.
§1 the shipped file (the package folder, `builtin`, the schema values); §2 the guard (the 36 fields, the
locked trio and amber ABSENT and DARK's by value, the mono-leaning chrome); §3 the eight syntax tones;
§4 the contrast matrix over the RESOLVED instance; §5 the resolution order and the export; §6 the
Appearance value (the combo, the two suggestions, `collect()`); §7 the release pins.
Rule — `AGENTS.md` §4.6; mechanism — `DOCUMENTATION.md`, "Central UI theme".
Run: python tests/test_followups_v1145.py
"""
import dataclasses
import json
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text, check,
                     check_i18n_format, check_i18n_parity, check_release_state, clear_cfg, finish,
                     load_i18n_langs, releases_at_least, rep_doc_text)

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
PACK_FILE = os.path.join(ROOT, "themes", "matrix.json")
EMPTY_USER_DIR = os.path.join(WORK, "no-user-themes")   # a HOME that holds no pack of its own
SYNTAX_FIELDS = {SH.syntax_field(role) for role in SH.SYNTAX_ROLES}
SURFACES = ("canvas_bg", "render_bg", "window_bg", "base_bg", "surface_alt")


def rgb(color):
    """The three channels of a "#rrggbb" colour."""
    value = color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def green_dominant(color):
    """True when the GREEN channel is the strongest one — the mono-leaning chrome of this pack."""
    red, green, blue = rgb(color)
    return green > red and green > blue


# ════════════════════════════════════════════════════════════════════════════
# §1 The shipped file — one JSON document in the package folder
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the shipped file: the package folder, the schema and the display name ==")

_RAW = open(PACK_FILE, encoding="utf-8").read()
_DOC = json.loads(_RAW)
_PACKS, _PROBLEMS = store.discover(root=ROOT, user_dir_path=EMPTY_USER_DIR)
_PACK = _PACKS.get("matrix")

check("§1 `themes/matrix.json` is the FIRST shipped pack — the loader reads the package folder",
      os.path.isfile(PACK_FILE) and store.package_dir(ROOT) == os.path.dirname(PACK_FILE),
      PACK_FILE)
check("§1 the file passes the store and lands in the registry as a BUILT-IN",
      _PACK is not None and _PACK.builtin is True and not _PROBLEMS,
      str([p.sentence() for p in _PROBLEMS]))
check("§1 every shipped pack is ONE file in the package folder — a pack is data, never a mechanism",
      sorted(_PACKS) == ["matrix", "paper"]
      and all(pack.builtin and os.path.isfile(pack.path) for pack in _PACKS.values()),
      str(sorted(_PACKS)))
check("§1 the schema: base `dark`, `version` 1, and the display name comes from the file",
      _PACK is not None and _PACK.base == "dark" and _PACK.version == store.PACK_VERSION
      and _PACK.name == "Matrix" and _PACK.display() == "Matrix" and _PACK.id == "matrix",
      f"{_PACK}")
check("§1 the two SUGGESTIONS are declared (the user still owns both fields)",
      _PACK.accent_hue == 140.0 and _PACK.terminal_palette == "default"
      and _PACK.terminal_palette in store.palette_names(),
      f"{_PACK.accent_hue} / {_PACK.terminal_palette}")
check("§1 the file is DATA: the closed root key set, a #rrggbb colour set and no code in it",
      set(_DOC) == {"name", "base", "version", "accent_hue", "terminal_palette", "colors"}
      and all(theme.is_valid_hex(value) for value in _DOC["colors"].values())
      and os.path.getsize(PACK_FILE) < 8 * 1024 and "settings." not in _RAW,
      f"{sorted(_DOC)} / {os.path.getsize(PACK_FILE)} bytes")


# ════════════════════════════════════════════════════════════════════════════
# §2 The guard — what the pack sets, and what stays DARK's by value
# ════════════════════════════════════════════════════════════════════════════
print("== §2 the guard: the 36 fields, the locked tones ABSENT and the DARK geometry untouched ==")

_INSTANCE = theme.theme_for_mode("dark", None, None, pack=_PACK)

check("§2 the pack sets EVERY field a pack may set (the whole allowlist, nothing outside it)",
      set(_PACK.colors) == set(store.ALLOWED_COLORS),
      f"missing={sorted(set(store.ALLOWED_COLORS) - set(_PACK.colors))} "
      f"stray={sorted(set(_PACK.colors) - set(store.ALLOWED_COLORS))}")
check("§2 the status trio is NOT in the file — it inherits DARK BY VALUE (the guard refuses it)",
      not ({"status_online", "status_warn", "status_offline"} & set(_PACK.colors))
      and _INSTANCE.status_colors == theme.DARK.status_colors,
      str(_INSTANCE.status_colors))
check("§2 the trust surface's warning tone is DARK's too (`selection_amber`)",
      "selection_amber" not in _PACK.colors
      and _INSTANCE.selection_amber == theme.DARK.selection_amber,
      f"{_INSTANCE.selection_amber} / {theme.DARK.selection_amber}")
check("§2 the semantic tag strip keeps DARK's four tones",
      "tag_test" not in _PACK.colors
      and all(getattr(_INSTANCE, f"tag_{name}") == getattr(theme.DARK, f"tag_{name}")
              for name in ("test", "backup", "dmz", "pink")))
check("§2 the geometry is untouched — every radius and both fonts are DARK's",
      all(getattr(_INSTANCE, field.name) == getattr(theme.DARK, field.name)
          for field in dataclasses.fields(theme.Theme)
          if field.name.startswith("radius_") or field.name.startswith("font_")),
      str([field.name for field in dataclasses.fields(theme.Theme)
           if field.name.startswith("radius_")]))
check("§2 the chrome is ONE green ramp — every surface is near-black and green-dominant",
      all(max(rgb(getattr(_INSTANCE, name))) <= 0x40 and green_dominant(getattr(_INSTANCE, name))
          for name in SURFACES),
      str([(name, getattr(_INSTANCE, name)) for name in SURFACES]))
check("§2 the phosphor tones are green-dominant too (the text, the label, the icon, the card's ink)",
      all(green_dominant(value) for value in (_INSTANCE.text_primary, _INSTANCE.text_muted,
                                              _INSTANCE.icon_color, _INSTANCE.node_text,
                                              _INSTANCE.node_label)),
      f"{_INSTANCE.text_primary} / {_INSTANCE.text_muted} / {_INSTANCE.node_label}")
check("§2 the four connection types keep FOUR tones (meaning is not flattened into one green)",
      len({_INSTANCE.arrow_ssh, _INSTANCE.arrow_http, _INSTANCE.arrow_nfs,
           _INSTANCE.arrow_kubernetes}) == 4,
      str([_INSTANCE.arrow_ssh, _INSTANCE.arrow_http, _INSTANCE.arrow_nfs,
           _INSTANCE.arrow_kubernetes]))


# ════════════════════════════════════════════════════════════════════════════
# §3 The eight syntax tones of the plain-text reader
# ════════════════════════════════════════════════════════════════════════════
print("== §3 the eight syntax tones: declared, distinct and readable on the pack's own surface ==")

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
check("§3 every tone clears 4.5:1 on the PACK's own viewer surface (the reader's background)",
      all(theme_contrast.contrast_ratio(tone, _INSTANCE.base_bg) >= 4.5
          for tone in _INSTANCE.syntax_colors.values()),
      str({role: round(theme_contrast.contrast_ratio(tone, _INSTANCE.base_bg), 2)
           for role, tone in _INSTANCE.syntax_colors.items()}))
check("§3 none of them is the 'no preview' tone (the marker of a refused row)",
      all(tone != _INSTANCE.sftp_preview_blocked for tone in _INSTANCE.syntax_colors.values()),
      _INSTANCE.sftp_preview_blocked)


# ════════════════════════════════════════════════════════════════════════════
# §4 The contrast matrix — over the instance the FILE resolves to
# ════════════════════════════════════════════════════════════════════════════
print("== §4 the contrast matrix over the RESOLVED instance (a built-in that fails is a SUITE failure) ==")

_FAILURES = theme_contrast.contrast_problems(_INSTANCE)
check("§4 the matrix is the SHIPPED table (one home, imported back — never a second copy)",
      len(theme_contrast.CONTRAST_PAIRS) > 55 and bool(theme_contrast.DECORATIVE)
      and theme_contrast.contrast_ratio is not None, str(len(theme_contrast.CONTRAST_PAIRS)))
check("§4 the Matrix pack clears EVERY declared pair (4.5 for text, 3.0 for a mark)",
      not _FAILURES, "; ".join(_FAILURES[:4]))
check("§4 the gate really measured the PACK and not DARK (the instance is the file's)",
      _INSTANCE.canvas_bg == "#000a04" and _INSTANCE.base_bg == "#062112",
      f"{_INSTANCE.canvas_bg} / {_INSTANCE.base_bg}")
check("§4 the gate is not vacuous — a muted tone on its own canvas FAILS it",
      bool(theme_contrast.contrast_problems(
          dataclasses.replace(_INSTANCE, text_muted=_INSTANCE.canvas_bg))))
_REFUSED = store.parse_pack(dict(_DOC, colors=dict(_DOC["colors"], text_muted="#031007")), "probe")
check("§4 the LOADER refuses the same defect by its failing pairs (never a half-applied file)",
      _REFUSED[0] is None and _REFUSED[1][0].reason == store.REASON_CONTRAST
      and "muted text" in _REFUSED[1][0].detail, _REFUSED[1][0].detail)
check("§4 loading the pack edits NO base instance (DARK and LIGHT keep their literals)",
      theme.DARK.canvas_bg == "#020617" and theme.LIGHT.canvas_bg == "#f8fafc"
      and theme.DARK.accent == "#38bdf8", f"{theme.DARK.canvas_bg} / {theme.LIGHT.canvas_bg}")


# ════════════════════════════════════════════════════════════════════════════
# §5 The resolution order — base → file → the user's two choices
# ════════════════════════════════════════════════════════════════════════════
print("== §5 record: the base mode first, the file over it, then the user's two choices ==")

_BY_ID = theme.theme_for_mode("dark", None, None, pack="matrix")
check("§5 a stored ID resolves through the registry (no pack object is passed in)",
      _BY_ID.canvas_bg == "#000a04" and _BY_ID.node_bg == "#072a19", _BY_ID.canvas_bg)
check("§5 ...it carries the values the FILE resolves to (the cache is a cache, not a second look)",
      _BY_ID == _INSTANCE and _BY_ID is not theme.DARK)
check("§5 the same request answers the SAME cached instance (the identity the switch relies on)",
      _BY_ID is theme.theme_for_mode("dark", None, None, pack="matrix"))
check("§5 the pack's HUE generates the accent family (no colour literal in the file)",
      _INSTANCE.accent_hue == 140.0
      and _INSTANCE.accent == theme.accent_hex(140.0)
      and _INSTANCE.accent_strong == theme.accent_strong_hex(140.0, theme.MODE_DARK),
      f"{_INSTANCE.accent} / {_INSTANCE.accent_strong}")
check("§5 the USER's accent WINS over the file's suggestion",
      theme.theme_for_mode("dark", 280.0, None, pack="matrix").accent == theme.accent_hex(280.0),
      theme.theme_for_mode("dark", 280.0, None, pack="matrix").accent)
check("§5 the user's NOTE TONE is applied LAST — over the pack's own note family",
      theme.theme_for_mode("dark", None, "#ff8800", pack="matrix").note_bg
      == theme.note_tone_colors(theme.hex_hue("#ff8800"))[0])
check("§5 a pack of the other base never crosses over (a dark pack over the light mode)",
      theme.theme_for_mode("light", None, None, pack="matrix") is theme.LIGHT)
check("§5 `export_theme()` never takes a pack (a report is a white page)",
      theme.export_theme().canvas_bg == theme.LIGHT.canvas_bg
      and theme.export_theme(theme.PALETTE_THEME) is theme.THEME)


# ════════════════════════════════════════════════════════════════════════════
# §6 The Appearance value — the combo, the two suggestions and `collect()`
# ════════════════════════════════════════════════════════════════════════════
print("== §6 the Appearance value: the combo, the suggested hue and palette, `collect()` ==")

theme.packs(reload=True)
check("§6 the LIVE registry holds the shipped pack, so the row offers it with no user file",
      sorted(theme.PACKS) == ["matrix", "paper"] and not theme.PACK_PROBLEMS,
      f"{sorted(theme.PACKS)} / {[p.sentence() for p in theme.PACK_PROBLEMS]}")
check("§6 `packs_for()` answers the DARK base only (the other shipped pack is the LIGHT one)",
      [pack.id for pack in theme.packs_for("dark")] == ["matrix"]
      and [pack.id for pack in theme.packs_for("light")] == ["paper"],
      f"{[p.id for p in theme.packs_for('dark')]} / {[p.id for p in theme.packs_for('light')]}")

clear_cfg()
_DLG = SettingsDialog(None)
check("§6 the combo is `Default` FIRST and then the shipped pack",
      _DLG.pack_combo.count() == 2 and _DLG.pack_combo.itemData(0) == ""
      and _DLG.pack_combo.itemData(1) == "matrix"
      and _DLG.pack_combo.itemText(1) == "Matrix" and _DLG.pack_combo.currentIndex() == 0,
      str([(_DLG.pack_combo.itemText(i), _DLG.pack_combo.itemData(i))
           for i in range(_DLG.pack_combo.count())]))
check("§6 a clean config writes no `pack` key (the absent key IS the mode's own look)",
      _DLG._pack_id == "" and "pack" not in _DLG.collect()["theme"] and len(_DLG.collect()) == 30,
      str(_DLG.collect()["theme"]))
_EMITTED = []
_DLG.theme_changed.connect(lambda instance: _EMITTED.append(instance))
_DLG.palette_combo.setCurrentIndex(_DLG.palette_combo.findData("nord"))
_DLG.pack_combo.setCurrentIndex(_DLG.pack_combo.findData("matrix"))
check("§6 choosing the pack applies its SUGGESTED hue and terminal palette",
      _DLG._accent_hex == theme.accent_hex(140.0)
      and _DLG.palette_combo.currentData() == "default"
      and bool(_EMITTED) and _EMITTED[-1].canvas_bg == "#000a04"
      and abs(_EMITTED[-1].accent_hue - 140.0) < 1.0,
      f"{_DLG._accent_hex} / {_DLG.palette_combo.currentData()} / "
      f"{[(e.canvas_bg, e.accent_hue) for e in _EMITTED]}")
check("§6 ...and `collect()` writes the id into the SAME nested `theme` key (30 keys)",
      _DLG.collect()["theme"].get("pack") == "matrix" and len(_DLG.collect()) == 30,
      str(_DLG.collect()["theme"]))
check("§6 the store round trip: the written key re-reads and re-resolves to the same instance",
      theme_from_settings(dict(load_theme_settings(), mode="dark", accent=_DLG._accent_hex,
                               pack="matrix")).canvas_bg == "#000a04")
_DLG.theme_mode_combo.setCurrentIndex(1)   # light: the dark pack cannot cross over
check("§6 a mode switch drops the dark pack and offers the LIGHT one alone",
      _DLG._pack_id == "" and _DLG.pack_combo.count() == 2
      and _DLG.pack_combo.itemData(1) == "paper"
      and "pack" not in _DLG.collect()["theme"],
      f"{_DLG._pack_id} / {[_DLG.pack_combo.itemData(i) for i in range(_DLG.pack_combo.count())]}")
_DLG.reject()
check("§6 Cancel restores the theme the dialog OPENED with", theme.THEME is theme.DARK)
_DLG.close()


# ════════════════════════════════════════════════════════════════════════════
# §7 The release pins
# ════════════════════════════════════════════════════════════════════════════
print("== §7 the release pins: the version, the parity, the packaging and the documents ==")

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§7 the pack adds NO i18n key — a pack carries values, not strings (parity {EXPECTED_I18N_KEYS})",
      len([key for key in LANGS["en"] if key not in ("name", "partial")]) == EXPECTED_I18N_KEYS
      and not [key for key in LANGS["en"] if "matrix" in key.lower()],
      str([key for key in LANGS["en"] if "matrix" in key.lower()]))
check(f"§7 the release is {EXPECTED_APP_VERSION} and the JSON schema did not move",
      version.APP_VERSION == EXPECTED_APP_VERSION and version.VERSION_FORMAT == "0.9"
      and releases_at_least(EXPECTED_APP_VERSION, "1.14.5"),
      f"{version.APP_VERSION} / {version.VERSION_FORMAT}")
_PYPROJECT = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
check("§7 the pack SHIPS: `themes = [\"*.json\"]` is the package data of the build",
      '"themes",' in _PYPROJECT and 'themes = ["*.json"]' in _PYPROJECT and os.path.isfile(PACK_FILE))
check("§7 the suite map lists this file (tests/INDEX.md regenerated)",
      "test_followups_v1145" in open(os.path.join(ROOT, "tests", "INDEX.md"),
                                     encoding="utf-8").read())
_FAMILY = changelog_family_text(ROOT)
_DETAILS = changelog_family_text(ROOT, "DETAILS")
check("§7 the changelog family carries the release (the LIVE file or a CLOSED line of it)",
      (not _FAMILY or "v1.14.5" in _FAMILY) and (not _DETAILS or "v1.14.5" in _DETAILS),
      f"changelog={'v1.14.5' in _FAMILY} details={'v1.14.5' in _DETAILS}")
_ROADMAP_TEXT = rep_doc_text("ROADMAP.md")
check("§7 the plan of record no longer carries the shipped section",
      not _ROADMAP_TEXT or "## v1.14.5" not in _ROADMAP_TEXT)
_AGENTS_TEXT = rep_doc_text("AGENTS.md")
check("§7 the contract names the shipped pack (`AGENTS.md` §4.6)",
      not _AGENTS_TEXT or "themes/matrix.json" in _AGENTS_TEXT)

finish()
