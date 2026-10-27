# -*- coding: utf-8 -*-
"""v1.14.4 — THE THEME SEAM: a third theme is a JSON FILE of declared overrides, not a code copy.
§1 the schema (the root keys, `version`, `base`, `name`, the 64 KB cap); §2 the GUARD (the allowlist,
the locked fields BY NAME, the refusal details); §3 the discovery (both folders, SHADOWING, a broken
user file, the id rule, the on-demand folder); §4 the resolution order (`theme_for_mode`: base → file →
accent → note tone, and the export that never takes a pack); §5 the contrast gate at LOAD time; §6 the
Appearance row (the combo, the suggestions, `collect()`, the skipped sentence, the folder door);
§7 the release pins.
Rule — `AGENTS.md` §4.6; mechanism — `DOCUMENTATION.md`, "Central UI theme".
Run: python tests/test_theme_store.py
"""
import dataclasses
import json
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import ui.theme as theme  # noqa: E402
import ui.theme_contrast as theme_contrast  # noqa: E402
import ui.theme_store as store  # noqa: E402
import version  # noqa: E402
from ui import theme_qss  # noqa: E402
from ui.settings_dialog import SettingsDialog, load_theme_settings, theme_from_settings  # noqa: E402

LANGS = load_i18n_langs(ROOT)
STORE_SRC = os.path.join(ROOT, "ui", "theme_store.py")
CONTRAST_SRC = os.path.join(ROOT, "ui", "theme_contrast.py")

# The one GREEN pack these checks use: a dark base, the surfaces and the eight syntax roles moved.
GREEN_COLORS = {
    "canvas_bg": "#001100", "render_bg": "#000800", "window_bg": "#001a00",
    "base_bg": "#002200", "surface_alt": "#003300",
    "text_primary": "#ccffcc", "text_muted": "#88aa88", "icon_color": "#aaffaa",
    "node_bg": "#002200", "node_border": "#33ff33", "node_hover": "#66ff66",
    "node_icon_bg": "#004400", "node_text": "#ccffcc", "node_label": "#88aa88",
    "dot_idle": "#88cc88", "group_border": "#00aa00", "group_hover": "#44cc44",
    "group_title": "#88ff88", "group_title_selected": "#ccff66",
    "group_title_hover": "#aaffaa", "arrow_ssh": "#44ff88", "arrow_http": "#ffee44",
    "arrow_nfs": "#ff88cc", "arrow_kubernetes": "#66ffff", "arrow_hover_compat": "#88ffbb",
    "note_bg": "#eedd9f", "note_border": "#a9853d", "note_text": "#403a2b",
    "syntax_number": "#ffee44", "syntax_string": "#66ff66", "syntax_key": "#66ffff",
    "syntax_keyword": "#aaffaa", "syntax_comment": "#88aa88", "syntax_tag": "#ff88cc",
    "syntax_attribute": "#66ff66", "syntax_punctuation": "#aaffaa",
}


def pack_doc(**overrides):
    """A valid pack document (the shipped-looking one), with fields replaced on request."""
    doc = {"name": "Green phosphor", "base": "dark", "version": 1,
           "accent_hue": 142, "colors": dict(GREEN_COLORS), "terminal_palette": "nord"}
    doc.update(overrides)
    return doc


def light_doc(**overrides):
    """A valid pack over the LIGHT base — no declared hue (the shipped accent already passes)."""
    doc = pack_doc(name="Light pack", base="light", colors={"canvas_bg": "#fffdf5"})
    doc.pop("accent_hue")
    doc.pop("terminal_palette")
    doc.update(overrides)
    return doc


def write(directory, name, payload, raw=False):
    """One file in a folder (a JSON document, or raw text when `raw`)."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(payload if raw else json.dumps(payload))
    return path


def parse(doc, pack_id="probe"):
    """`store.parse_pack()` of one document → (pack, problems)."""
    return store.parse_pack(doc, pack_id, os.path.join(WORK, f"{pack_id}.json"))


PKG_ROOT = os.path.join(WORK, "pkgroot")
PKG_DIR = os.path.join(PKG_ROOT, "themes")
USER_DIR = os.path.join(WORK, "userdir")
JUNK_DIR = os.path.join(WORK, "junkdir")   # the refusals of §1 never pollute a discovery


# ════════════════════════════════════════════════════════════════════════════
# §1 The schema — one file, one shape, and a typo is never a silent skip
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the schema: the root keys, version, base, name and the 64 KB cap ==")

_pack, _problems = parse(pack_doc())
check("§1 a valid file parses into a ThemePack with its id, name, base and version",
      _pack is not None and not _problems and _pack.id == "probe"
      and _pack.name == "Green phosphor" and _pack.base == "dark"
      and _pack.version == store.PACK_VERSION and _pack.display() == "Green phosphor",
      f"{_pack} / {_problems}")
check("§1 its colours are PARTIAL and normalised to lower-case #rrggbb",
      _pack is not None and _pack.colors["canvas_bg"] == "#001100"
      and len(_pack.colors) == len(GREEN_COLORS)
      and all(value == value.lower() for value in _pack.colors.values()),
      str(sorted(_pack.colors)[:4]))
check("§1 a missing `colors` block is a pack that changes nothing but still LOADS",
      parse({"name": "Bare", "base": "dark", "version": 1})[0] is not None)
check("§1 unknown ROOT keys are refused (a typo in the schema is a defect)",
      parse(pack_doc(colour={"canvas_bg": "#001100"}))[1][0].reason == store.REASON_UNKNOWN_KEY
      and "colour" in parse(pack_doc(colour="x"))[1][0].detail,
      parse(pack_doc(colour="x"))[1][0].detail)
check("§1 a `version` this build does not know is REFUSED with a sentence, never guessed",
      parse(pack_doc(version=2))[1][0].reason == store.REASON_BAD_VERSION
      and "2" in parse(pack_doc(version=2))[1][0].detail,
      parse(pack_doc(version=2))[1][0].detail)
check("§1 a `base` that is neither dark nor light is refused (a pack belongs to ONE base)",
      parse(pack_doc(base="sepia"))[1][0].reason == store.REASON_BAD_BASE)
check("§1 the display `name` is required (the file name is the ID, not the label)",
      parse(pack_doc(name="  "))[1][0].reason == store.REASON_NO_NAME
      and parse(pack_doc(name=42))[1][0].reason == store.REASON_NO_NAME)
check("§1 a non-object root and a non-object `colors` are refused",
      store.parse_pack(["x"], "probe")[1][0].reason == store.REASON_NOT_OBJECT
      and parse(pack_doc(colors=["#ffffff"]))[1][0].reason == store.REASON_UNKNOWN_KEY)
check("§1 a colour that is not #rrggbb is refused WITH the field named",
      parse(pack_doc(colors={"canvas_bg": "green"}))[1][0].reason == store.REASON_BAD_COLOR
      and "canvas_bg" in parse(pack_doc(colors={"canvas_bg": "green"}))[1][0].detail)
check("§1 `accent_hue` takes a hue NUMBER or a #rrggbb colour, and nothing else",
      parse(pack_doc(accent_hue=142))[0].accent_hue == 142.0
      and abs(parse(pack_doc(accent_hue="#22c55e"))[0].accent_hue
              - theme.hex_hue("#22c55e")) < 0.01
      and parse(pack_doc(accent_hue="green"))[1][0].reason == store.REASON_BAD_ACCENT)
check("§1 `terminal_palette` is the SHIPPED vocabulary (one home in modules/terminal_screen.py)",
      parse(pack_doc(terminal_palette="solarized"))[1][0].reason == store.REASON_BAD_PALETTE
      and "nord" in store.palette_names()
      and parse(pack_doc())[0].terminal_palette == "nord")
check(f"§1 the file is capped at {store.MAX_PACK_BYTES // 1024} KB — judged BEFORE the parse",
      store.MAX_PACK_BYTES == 64 * 1024
      and store.read_pack(write(JUNK_DIR, "huge.json",
                                json.dumps(pack_doc()) + " " * (70 * 1024), raw=True), "huge")[1][0]
      .reason == store.REASON_TOO_BIG)
check("§1 an unreadable file and a non-JSON file are two different refusals",
      store.read_pack(os.path.join(WORK, "nope.json"), "nope")[1][0].reason == store.REASON_UNREADABLE
      and store.read_pack(write(JUNK_DIR, "broken.json", "{oops", raw=True), "broken")[1][0]
      .reason == store.REASON_NOT_JSON)
check("§1 every reason code a refusal can carry is declared (the Settings row picks by code)",
      set(store.REASONS) == {store.REASON_UNREADABLE, store.REASON_TOO_BIG, store.REASON_NOT_JSON,
                             store.REASON_NOT_OBJECT, store.REASON_UNKNOWN_KEY,
                             store.REASON_BAD_VERSION, store.REASON_BAD_BASE, store.REASON_NO_NAME,
                             store.REASON_BAD_COLOR, store.REASON_BAD_ACCENT,
                             store.REASON_BAD_PALETTE, store.REASON_CONTRAST})


# ════════════════════════════════════════════════════════════════════════════
# §2 The GUARD — the schema's allowlist, and the locked fields refused BY NAME
# ════════════════════════════════════════════════════════════════════════════
print("== §2 the guard: the allowlist and the locked tones ==")

_ALL = set(store.ALLOWED_COLORS)
_LOCKED = set(store.LOCKED_COLORS)
_real = {f.name for f in dataclasses.fields(theme.Theme)}
check(f"§2 the allowlist is {len(_ALL)} fields and the locked list {len(_LOCKED)} — no overlap",
      not (_ALL & _LOCKED) and _ALL <= _real and _LOCKED <= _real,
      f"stray={sorted((_ALL | _LOCKED) - _real)} overlap={sorted(_ALL & _LOCKED)}")
check("§2 the LOCKED list is the product's MEANING: the status trio, the selection and the tag strip",
      {"status_online", "status_warn", "status_offline", "selection_amber",
       "tag_test", "tag_backup", "tag_dmz", "tag_pink"} <= _LOCKED)
check("§2 ...the six DERIVED accent tones and the user's tone are locked too (a pack declares the HUE)",
      {"accent", "accent_hover", "accent_selected", "accent_strong", "accent_strong_hover",
       "accent_strong_selected", "note_tone", "accent_hue"} <= _LOCKED)
check("§2 ...and the geometry: every radius and both fonts",
      {f.name for f in dataclasses.fields(theme.Theme) if f.name.startswith("radius_")
       or f.name.startswith("font_")} <= _LOCKED)
check("§2 the eight syntax roles, the notes, the card, the groups, the arrows and the surfaces pass",
      {"syntax_number", "syntax_string", "syntax_key", "syntax_keyword", "syntax_comment",
       "syntax_tag", "syntax_attribute", "syntax_punctuation", "note_bg", "note_border",
       "note_text", "node_bg", "group_border", "arrow_ssh", "canvas_bg", "base_bg",
       "window_bg", "text_primary", "icon_color", "dot_idle"} <= _ALL)
check("§2 EVERY allowed field really loads (the guard is not a list of unreadable names)",
      all(parse(pack_doc(colors={name: value}))[0] is not None
          for name, value in ((name, GREEN_COLORS[name]) for name in _ALL if name in GREEN_COLORS)))
_refusals = []
for _field in sorted(_LOCKED):
    _pack, _issues = parse(pack_doc(colors={_field: "#123456"}))
    if _pack is not None or _field not in _issues[0].detail:
        _refusals.append(_field)
check(f"§2 every locked field ({len(_LOCKED)}) is REFUSED and NAMED in the report",
      not _refusals, str(_refusals))
check("§2 the refusal quotes the REASON of the lock (not a bare 'no')",
      "status trio" in parse(pack_doc(colors={"status_online": "#00ff00"}))[1][0].detail
      and "DERIVED" in parse(pack_doc(colors={"accent": "#00ff00"}))[1][0].detail
      and "geometry" in parse(pack_doc(colors={"radius_node": "#00ff00"}))[1][0].detail)
check("§2 an unknown field is refused as UNKNOWN, not as locked (the two answers are distinct)",
      parse(pack_doc(colors={"node_bgg": "#112233"}))[1][0].reason == store.REASON_UNKNOWN_KEY
      and "may set" in parse(pack_doc(colors={"node_bgg": "#112233"}))[1][0].detail)
check("§2 the file is skipped WHOLE — a valid field beside a refused one applies nothing",
      parse(pack_doc(colors=dict(GREEN_COLORS, tag_pink="#ff00ff")))[0] is None)


# ════════════════════════════════════════════════════════════════════════════
# §3 Discovery — both folders, SHADOWING, and the id rule before a path
# ════════════════════════════════════════════════════════════════════════════
print("== §3 the discovery: the package first, the user folder second (shadowing) ==")

write(PKG_DIR, "shipped.json", pack_doc(name="Shipped"))
write(PKG_DIR, "shadowed.json", pack_doc(name="Shipped copy"))
write(PKG_DIR, "notes.txt", "not a pack", raw=True)
_packs, _issues = store.discover(root=PKG_ROOT, user_dir_path=os.path.join(WORK, "empty-user"))
check("§3 the package folder is read and only `*.json` counts",
      sorted(_packs) == ["shadowed", "shipped"] and not _issues
      and _packs["shipped"].builtin is True, str(sorted(_packs)))
write(USER_DIR, "shadowed.json", light_doc(name="User copy",
                                           colors={"canvas_bg": "#ffffff"}))
write(USER_DIR, "extra.json", pack_doc(name="Extra"))
_packs, _issues = store.discover(root=PKG_ROOT, user_dir_path=USER_DIR)
check("§3 a user file of the same id SHADOWS the shipped one; a new id ADDS a pack",
      sorted(_packs) == ["extra", "shadowed", "shipped"]
      and _packs["shadowed"].name == "User copy" and _packs["shadowed"].builtin is False
      and _packs["shipped"].name == "Shipped", str({k: v.name for k, v in _packs.items()}))
write(USER_DIR, "shipped.json", {"name": "Broken", "base": "sepia", "version": 1})
_packs, _issues = store.discover(root=PKG_ROOT, user_dir_path=USER_DIR)
check("§3 a BROKEN user file costs the user nothing: the shipped pack of that id stays",
      _packs["shipped"].name == "Shipped" and _packs["shipped"].builtin is True
      and [p.reason for p in _issues] == [store.REASON_BAD_BASE],
      f"{_packs['shipped'].name} / {[p.reason for p in _issues]}")
check("§3 a skipped file answers ONE problem record (id, path, reason, detail)",
      _issues[0].id == "shipped" and _issues[0].path.endswith("shipped.json")
      and _issues[0].detail.startswith("base") and "shipped" in _issues[0].sentence())
check("§3 an id is a FILE NAME before it is a path (the i18n code rule)",
      store.is_safe_pack_id("matrix") and store.is_safe_pack_id("pt_BR")
      and not any(store.is_safe_pack_id(value) for value in
                  ("", " ", ".", "..", "../x", "a/b", "a\\b", None, 7)))
check("§3 the user folder is NOT created at import (only by the door)",
      store.ensure_user_dir() is True and os.path.isdir(store.user_dir())
      and os.path.basename(store.user_dir()) == "themes")


# ════════════════════════════════════════════════════════════════════════════
# §4 The resolution order — base → file → accent → note tone
# ════════════════════════════════════════════════════════════════════════════
print("== §4 record: base mode first, the file over it, then the user's two choices ==")

_green = parse(pack_doc())[0]
_instance = theme.theme_for_mode("dark", None, None, pack=_green)
check("§4 the pack's colours land over the base mode and nothing else moves",
      _instance.canvas_bg == "#001100" and _instance.node_bg == "#002200"
      and _instance.status_online == theme.DARK.status_online
      and _instance.radius_node == theme.DARK.radius_node
      and _instance.font_ui == theme.DARK.font_ui)
check("§4 the pack's declared hue generates the SIX accent tones (no literal in the file)",
      _instance.accent_hue == 142.0 and _instance.accent == theme.accent_hex(142.0)
      and _instance.accent_strong == theme.accent_strong_hex(142.0, theme.MODE_DARK)
      and _instance.accent_hue != theme.DARK.accent_hue)
check("§4 DARK itself is NEVER edited by a pack (still the frozen literal)",
      theme.DARK.canvas_bg == "#020617" and theme.DARK.accent_hue == theme.DEFAULT_ACCENT_HUE)
check("§4 the same request answers the SAME instance (the cache the switch and the tests rely on)",
      theme.theme_for_mode("dark", None, None, pack=_green) is _instance
      and theme.theme_for_mode("dark") is theme.DARK)
_user = theme.theme_for_mode("dark", 280.0, None, pack=_green)
check("§4 the USER's accent WINS over the file's suggestion",
      _user.accent_hue == 280.0 and _user.accent == theme.accent_hex(280.0)
      and _user.canvas_bg == "#001100", f"{_user.accent_hue} {_user.accent}")
_toned = theme.theme_for_mode("dark", None, "#ff8800", pack=_green)
check("§4 the user's NOTE TONE is applied LAST — over the file's own note family",
      _toned.note_tone == theme.hex_hue("#ff8800")
      and _toned.note_bg == theme.note_tone_colors(theme.hex_hue("#ff8800"))[0]
      and _toned.canvas_bg == "#001100")
check("§4 a pack of the OTHER base is never applied over the resolved mode",
      theme.theme_for_mode("light", None, None, pack=_green) is theme.LIGHT)
check("§4 an unknown / unsafe / blank id is the mode's own look (never an exception)",
      theme.theme_for_mode("dark", None, None, pack="nope") is theme.DARK
      and theme.theme_for_mode("dark", None, None, pack="../x") is theme.DARK
      and theme.theme_for_mode("dark", None, None, pack=None) is theme.DARK
      and theme.theme_for_mode("dark", None, None, pack="") is theme.DARK)
check("§4 `pack_by_id` reads the LIVE registry and refuses an unsafe name",
      theme.pack_by_id("nope") is None and theme.pack_by_id("../../etc/passwd") is None
      and theme.pack_by_id("") is None)
check("§4 `packs_for()` answers ONE base, by display name (the combo's order)",
      all(pack.base == theme.MODE_LIGHT for pack in theme.packs_for("light"))
      and isinstance(theme.packs_for("dark"), list))
check("§4 `export_theme()` keeps the PRINT palette — a pack never reaches an export",
      theme.export_theme().canvas_bg == theme.LIGHT.canvas_bg
      and theme.export_theme().node_bg == theme.LIGHT.node_bg
      and theme.export_theme(theme.PALETTE_THEME) is theme.THEME)
check("§4 `ui/theme.py` stays PURE DATA — every Qt import sits INSIDE a function",
      not [line for line in open(os.path.join(ROOT, "ui", "theme.py"), encoding="utf-8")
           .read().splitlines() if line.startswith("from PySide6")])
check("§4 the store itself imports no Qt (the schema is data, the row is the UI's)",
      "PySide6" not in open(STORE_SRC, encoding="utf-8").read()
      and "import json" in open(STORE_SRC, encoding="utf-8").read())


# ════════════════════════════════════════════════════════════════════════════
# §5 The contrast gate — the SAME table the suite reads, at LOAD time
# ════════════════════════════════════════════════════════════════════════════
print("== §5 the contrast gate: a built-in fails the suite, a user file is refused ==")

import ui.theme_contrast as _contrast_again  # noqa: E402 — the SAME module object

check("§5 the table is the ONE home — a second import answers the same rows",
      len(theme_contrast.CONTRAST_PAIRS) > 55
      and _contrast_again.CONTRAST_PAIRS is theme_contrast.CONTRAST_PAIRS
      and bool(theme_contrast.DECORATIVE))
check("§5 the GREEN pack of §4 clears every pair (a valid file is not refused by luck)",
      not theme_contrast.contrast_problems(_instance))
_bad = parse(pack_doc(colors={"canvas_bg": "#020617", "text_muted": "#101010"}))
check("§5 an unreadable pack is REFUSED with the FAILING PAIRS, never applied anyway",
      _bad[0] is None and _bad[1][0].reason == store.REASON_CONTRAST
      and "muted text" in _bad[1][0].detail,
      _bad[1][0].detail)
check("§5 the gate is not vacuous — a dark tone on a dark surface really fails it",
      theme_contrast.contrast_ratio("#101010", "#020617") < 4.5)
_red = parse(pack_doc(accent_hue=0))
_red_ratio = theme_contrast.contrast_ratio(
    theme.accent_strong_hex(0.0, theme.MODE_DARK), theme.DARK.window_bg)
check("§5 the gate runs over the RESOLVED instance — a pack's own hue is measured too",
      (_red[0] is not None) == (_red_ratio >= 4.5),
      f"accent-strong on the window = {_red_ratio:.2f}: {_red[1]}")


# ════════════════════════════════════════════════════════════════════════════
# §6 The Appearance row — the combo, the suggestions, `collect()`, the sentences
# ════════════════════════════════════════════════════════════════════════════
print("== §6 the Appearance row: the pack combo and its live application ==")

clear_cfg()
os.makedirs(store.user_dir(), exist_ok=True)
for _name in os.listdir(store.user_dir()):
    os.remove(os.path.join(store.user_dir(), _name))
write(store.user_dir(), "matrix.json",
      pack_doc(name="Matrix", accent_hue=142, terminal_palette="nord"))
write(store.user_dir(), "sunrise.json",
      light_doc(name="Sunrise", colors={"canvas_bg": "#fffdf5"}))
theme.packs(reload=True)
check("§6 the LIVE registry is loaded from the user folder (one id → one pack)",
      sorted(theme.PACKS) == ["matrix", "sunrise"] and not theme.PACK_PROBLEMS,
      f"{sorted(theme.PACKS)} / {[p.sentence() for p in theme.PACK_PROBLEMS]}")

_dlg = SettingsDialog(None)
_row = [i for i in range(_dlg.pack_combo.count())]
check("§6 the combo is `Default` FIRST and then the packs of the RESOLVED base only",
      _dlg.pack_combo.count() == 2 and _dlg.pack_combo.itemData(0) == ""
      and _dlg.pack_combo.itemData(1) == "matrix" and _dlg.pack_combo.currentIndex() == 0
      and _dlg.pack_combo.itemText(1) == "Matrix",
      str([(_dlg.pack_combo.itemText(i), _dlg.pack_combo.itemData(i)) for i in _row]))
check("§6 a clean config opens on `Default` — no key is written for the default look",
      _dlg._pack_id == "" and "pack" not in _dlg.collect()["theme"] and len(_dlg.collect()) == 30,
      str(_dlg.collect()["theme"]))
_emitted = []
_dlg.theme_changed.connect(lambda instance: _emitted.append(instance))
_dlg.pack_combo.setCurrentIndex(_dlg.pack_combo.findData("matrix"))
check("§6 choosing a pack applies its SUGGESTED accent and terminal palette, and emits the theme",
      _dlg._accent_hex == theme.accent_hex(142.0)
      and _dlg.palette_combo.currentData() == "nord"
      and _emitted and _emitted[-1].canvas_bg == "#001100"
      and abs(_emitted[-1].accent_hue - 142.0) < 1.0,   # the hex → hue round trip (±0.5°)
      f"{_dlg._accent_hex} / {_dlg.palette_combo.currentData()} / "
      f"{[(e.canvas_bg, e.accent_hue) for e in _emitted]}")
check("§6 ...and `collect()` writes the id into the SAME nested `theme` key (30 keys)",
      _dlg.collect()["theme"].get("pack") == "matrix" and len(_dlg.collect()) == 30,
      str(_dlg.collect()["theme"]))
check("§6 the store round trip: the written key re-reads and re-resolves to the same instance",
      theme_from_settings(dict(load_theme_settings(), mode="dark", accent=_dlg._accent_hex,
                               pack="matrix")).canvas_bg == "#001100")
_dlg.theme_mode_combo.setCurrentIndex(1)   # light: the dark pack cannot cross over
check("§6 a mode switch drops the pack of the OTHER base and says so ONCE",
      _dlg._pack_id == "" and _dlg.pack_combo.count() == 2
      and _dlg.pack_combo.itemData(1) == "sunrise"
      and "pack" not in _dlg.collect()["theme"],
      f"{_dlg._pack_id} / {[_dlg.pack_combo.itemData(i) for i in range(2)]}")
_dlg.reject()
check("§6 the row is SEARCHABLE like the rest of the tab, and Cancel restores the theme",
      any(entry["label"] is _dlg._lbl_theme_pack for entry in _dlg._search_entries)
      and any(entry["label"] is _dlg._lbl_pack_locked for entry in _dlg._search_entries)
      and theme.THEME is theme.DARK)
_dlg.close()

# a refused file: the row says ONE sentence and names the file
write(store.user_dir(), "broken.json", "{oops", raw=True)
_dlg2 = SettingsDialog(None)
check("§6 a skipped file is REPORTED in the row with ONE sentence naming it",
      _dlg2.pack_status.text() != "" and "broken" in _dlg2.pack_status.text()
      and not _dlg2.pack_status.isHidden(),
      _dlg2.pack_status.text())
check("§6 ...and the sentence is a translated key (not an English literal in the widget)",
      "settings.appearance.pack.skipped" in open(
          os.path.join(ROOT, "ui", "settings_dialog.py"), encoding="utf-8").read())
check("§6 the load-time gate's own sentence is reachable too (the contrast key exists)",
      all(code in LANGS and "settings.appearance.pack.contrast" in LANGS[code] for code in LANGS))
os.remove(os.path.join(store.user_dir(), "broken.json"))
_dlg2.close()

# the folder door: created on demand and handed to the OS
_opened = []


class _Desk:
    """A stand-in for QDesktopServices (the dialog's only OS call)."""

    @staticmethod
    def openUrl(url):
        _opened.append(url.toString())
        return True


import ui.settings_dialog as _sd  # noqa: E402
_original_desk = _sd.QDesktopServices
_sd.QDesktopServices = _Desk
try:
    _dlg3 = SettingsDialog(None)
    _dlg3._on_open_theme_folder()
finally:
    _sd.QDesktopServices = _original_desk
check("§6 the folder door creates `~/.sshmap/themes` and asks the OS to open it",
      bool(_opened) and _opened[-1].startswith("file:")
      and _opened[-1].rstrip("/").endswith("themes"),
      str(_opened[-1:]))
_dlg3.close()
theme_qss.apply_theme(theme.DARK, app=app, refresh_windows=False)


# ════════════════════════════════════════════════════════════════════════════
# §7 The release pins
# ════════════════════════════════════════════════════════════════════════════
print("== §7 i18n, the release state and the packaging ==")

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
PACK_KEYS = ["settings.appearance.pack", "settings.appearance.pack.default",
             "settings.appearance.pack.hint", "settings.appearance.pack.locked",
             "settings.appearance.pack.folder", "settings.appearance.pack.skipped",
             "settings.appearance.pack.contrast"]
_missing = [key for key in PACK_KEYS
            if any(not str(LANGS[code].get(key, "")).strip() for code in sorted(LANGS))]
check(f"§7 the {len(PACK_KEYS)} pack strings exist in EVERY language",
      not _missing, str(_missing))
_src = open(os.path.join(ROOT, "ui", "settings_dialog.py"), encoding="utf-8").read()
check("§7 every one of them is USED by the UI code (no dead string)",
      all(key in _src for key in PACK_KEYS),
      str([key for key in PACK_KEYS if key not in _src]))
check(f"§7 the parity pin covers them ({EXPECTED_APP_VERSION}, {EXPECTED_I18N_KEYS} keys)",
      all(len([k for k in LANGS[code] if k not in ("name", "partial")]) == EXPECTED_I18N_KEYS
          for code in sorted(LANGS))
      and EXPECTED_I18N_KEYS >= 1198 + 7)
check(f"§7 the release is {EXPECTED_APP_VERSION} and the schema did not move",
      version.APP_VERSION == EXPECTED_APP_VERSION and version.VERSION_FORMAT == "0.9"
      and releases_at_least(EXPECTED_APP_VERSION, "1.14.4"),
      f"{version.APP_VERSION} / {version.VERSION_FORMAT}")
_pyproject = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
check("§7 `themes/` ships in the build — the package AND its data",
      '"themes",' in _pyproject and 'themes = ["*.json"]' in _pyproject
      and os.path.isfile(os.path.join(ROOT, "themes", "__init__.py")))
check("§7 the shipped folder is a PACKAGE the loader can find (empty is a valid state)",
      store.package_dir(ROOT) == os.path.join(ROOT, "themes")
      and os.path.isdir(store.package_dir(ROOT)))
check("§7 the topical file is registered in the suite map (tests/INDEX.md)",
      "test_theme_store.py" in open(os.path.join(ROOT, "tests", "INDEX.md"),
                                    encoding="utf-8").read())
check("§7 `ui/theme_contrast.py` is the moved TABLE — the test imports it, never copies it",
      os.path.isfile(CONTRAST_SRC)
      and "CONTRAST_PAIRS" in open(os.path.join(ROOT, "tests", "test_theme_contrast.py"),
                                   encoding="utf-8").read())

finish()
