# -*- coding: utf-8 -*-
"""v1.14.6 — THE ADDRESSES: an IPv4 in the plain-text reader wears the key's tone, and a theme pack
only SUGGESTS an accent. §1 the role (no ninth colour); §2 the strict predicate; §3 the merge with the
numbers and the budget; §4 the tone the reader really paints; §5 the accent a pack may not bake in;
§6 the release pins.
Rule — `AGENTS.md` §4.15 / §4.6; mechanism — `DOCUMENTATION.md` §38, "Central UI theme".
Run: python tests/test_followups_v1146.py
"""
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text, check,
                     check_i18n_format, check_i18n_parity, check_release_state, clear_cfg, finish,
                     load_i18n_langs, releases_at_least, rep_doc_text, write_cfg)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication, QPlainTextEdit  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import modules.syntax_highlight as SH  # noqa: E402
import ui.theme as theme  # noqa: E402
import version  # noqa: E402
from ui.settings_dialog import SettingsDialog, load_theme_settings  # noqa: E402

LANGS = load_i18n_langs(ROOT)
DEFAULT_ACCENT = theme.accent_hex()
PACK_ACCENT = theme.accent_hex(140.0)          # `themes/matrix.json`'s declared hue


def tokens(language, line):
    """`tokenize_line` as readable tokens: [(text, role), …]."""
    spans, _state = SH.tokenize_line(language, line)
    return [(line[start:start + length], role) for start, length, role in spans]


def address_texts(line):
    """The substrings `ipv4_spans()` accepted."""
    return [line[start:start + length] for start, length, _role in SH.ipv4_spans(line)]


def block_formats(edit, number):
    """The formats really applied to ONE block: [(text, "#rrggbb"), …] (None — no such block)."""
    block = edit.document().findBlockByNumber(number)
    if block is None or not block.isValid() or block.layout() is None:
        return None
    text = block.text()
    return [(text[run.start:run.start + run.length], run.format.foreground().color().name())
            for run in block.layout().formats()]


# ════════════════════════════════════════════════════════════════════════════
# §1 The role — an address is the KEY's tone, never a ninth colour
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the role: `ROLE_IP` IS `ROLE_KEY` — the palette stays closed at eight tones ==")

check("§1 `ROLE_IP` is the key role itself, not a ninth name",
      SH.ROLE_IP == SH.ROLE_KEY == "key", f"{SH.ROLE_IP!r} / {SH.ROLE_KEY!r}")
check("§1 the vocabulary is still EIGHT unique roles and the address is one of them",
      len(SH.SYNTAX_ROLES) == 8 and len(set(SH.SYNTAX_ROLES)) == 8 and SH.ROLE_IP in SH.SYNTAX_ROLES,
      str(SH.SYNTAX_ROLES))
check("§1 the palette did not grow: eight syntax fields and no `ip` field",
      len(theme.DARK.syntax_colors) == 8
      and tuple(theme.DARK.syntax_colors) == SH.SYNTAX_ROLES
      and not hasattr(theme.DARK, "syntax_ip"),
      str(tuple(theme.DARK.syntax_colors)))
check("§1 the tone is the theme's `key` cyan in BOTH modes (a value, never a literal)",
      theme.DARK.syntax_key == "#22d3ee" and theme.LIGHT.syntax_key == "#155e75"
      and SH.syntax_field(SH.ROLE_IP) == "syntax_key",
      f"{theme.DARK.syntax_key} / {theme.LIGHT.syntax_key}")
check("§1 both DARK and LIGHT keep their eight tones pairwise distinct (the address cannot collide)",
      len(set(theme.DARK.syntax_colors.values())) == 8
      and len(set(theme.LIGHT.syntax_colors.values())) == 8)


# ════════════════════════════════════════════════════════════════════════════
# §2 The predicate — PURE and STRICT
# ════════════════════════════════════════════════════════════════════════════
print("== §2 the predicate: four octets, no leading zeros, the declared boundaries ==")

_VALID = {
    "10.0.0.14": ["10.0.0.14"],
    "0.0.0.0": ["0.0.0.0"],
    "255.255.255.255": ["255.255.255.255"],
    "1.2.3.4": ["1.2.3.4"],
    "10.0.0.14:51822": ["10.0.0.14"],
    "10.0.0.0/8": ["10.0.0.0"],
    "[10.0.0.1]": ["10.0.0.1"],
    "10.0.0.14.": ["10.0.0.14"],
    "host 10.0.0.14 down": ["10.0.0.14"],
    "a 10.0.0.1 b 192.168.1.1 c": ["10.0.0.1", "192.168.1.1"],
}
_INVALID = ("256.1.1.1", "010.0.0.1", "1.2.3.4.5", "abc1.2.3.4", "1.2.3", "999.1.1.1",
            "1.2.3.256", "1.2.3.4a", "172.16.0.1_", "1.2.3.4.5.6")

_BAD = {line: address_texts(line) for line in _INVALID if address_texts(line)}
check("§2 every shipped shape is an address (port, prefix, brackets and a final dot included)",
      all(address_texts(line) == expected for line, expected in _VALID.items()),
      {line: address_texts(line) for line in _VALID if address_texts(line) != _VALID[line]})
check("§2 five octets, leading zeros, an out-of-range octet and a glued word are NOT addresses",
      not _BAD, str(_BAD))
check("§2 the boundaries are the regex's own (a lookbehind and a lookahead, not a strip)",
      SH.ipv4_spans("x10.0.0.1") == [] and SH.ipv4_spans(".10.0.0.1") == []
      and SH.ipv4_spans("10.0.0.1x") == [] and SH.ipv4_spans("10.0.0.1.2") == [],
      str([SH.ipv4_spans(line) for line in ("x10.0.0.1", ".10.0.0.1",
                                             "10.0.0.1x", "10.0.0.1.2")]))
check("§2 a non-string line answers nothing instead of raising",
      SH.ipv4_spans(None) == [] and SH.ipv4_spans(42) == [])


# ════════════════════════════════════════════════════════════════════════════
# §3 The merge — addresses and numbers, ONE sorted non-overlapping list
# ════════════════════════════════════════════════════════════════════════════
print("== §3 the merge: the address first, the port/prefix as a number, the budget shared ==")

check("§3 a port is still a NUMBER (the address owns only its own bytes)",
      tokens(SH.LANG_NUMBERS, "10.0.0.14:51822")
      == [("10.0.0.14", SH.ROLE_IP), ("51822", SH.ROLE_NUMBER)],
      str(tokens(SH.LANG_NUMBERS, "10.0.0.14:51822")))
check("§3 a prefix length is a number as well",
      tokens(SH.LANG_NUMBERS, "10.0.0.0/8")
      == [("10.0.0.0", SH.ROLE_IP), ("8", SH.ROLE_NUMBER)],
      str(tokens(SH.LANG_NUMBERS, "10.0.0.0/8")))
check("§3 a five-part version-less run keeps NEITHER an address nor a number span",
      tokens(SH.LANG_NUMBERS, "1.2.3.4.5") == [], str(tokens(SH.LANG_NUMBERS, "1.2.3.4.5")))
check("§3 a three-part version stays plain (the address rule never borrows it)",
      tokens(SH.LANG_NUMBERS, "1.2.3") == [], str(tokens(SH.LANG_NUMBERS, "1.2.3")))
check("§3 the mixed line is sorted by `start` and never overlaps",
      (lambda spans: spans == sorted(spans, key=lambda span: span[0])
       and all(a[0] + a[1] <= b[0] for a, b in zip(spans, spans[1:])))(
          SH.tokenize_line(SH.LANG_NUMBERS, "a 10.0.0.1:22 b 42")[0]),
      str(SH.tokenize_line(SH.LANG_NUMBERS, "a 10.0.0.1:22 b 42")[0]))
check("§3 an address inside a JSON string stays the STRING's span (one span per token)",
      tokens(SH.LANG_JSON, '"ip": "10.0.0.14"')
      == [('"ip"', SH.ROLE_KEY), (":", SH.ROLE_PUNCTUATION),
          ('"10.0.0.14"', SH.ROLE_STRING)],
      str(tokens(SH.LANG_JSON, '"ip": "10.0.0.14"')))
check("§3 ...and the YAML grammar is untouched (the mode is `numbers` only)",
      tokens(SH.LANG_YAML, "ip: 10.0.0.14")
      == [("ip", SH.ROLE_KEY), (":", SH.ROLE_PUNCTUATION)],
      str(tokens(SH.LANG_YAML, "ip: 10.0.0.14")))
check(f"§3 both families share ONE budget ({SH.MAX_TOKENS_PER_BLOCK} spans, a hostile line stays bounded)",
      len(SH.tokenize_line(SH.LANG_NUMBERS, "10.0.0.1 " * 5000)[0]) == SH.MAX_TOKENS_PER_BLOCK
      and len(SH.tokenize_line(SH.LANG_NUMBERS, "10.0.0.1 42 " * 1000)[0])
      == SH.MAX_TOKENS_PER_BLOCK,
      str(len(SH.tokenize_line(SH.LANG_NUMBERS, "10.0.0.1 42 " * 1000)[0])))
check("§3 the budget keeps both roles when the line mixes them (not an address-only prefix)",
      {role for _start, _length, role
       in SH.tokenize_line(SH.LANG_NUMBERS, "10.0.0.1 42 " * 1000)[0]}
      == {SH.ROLE_IP, SH.ROLE_NUMBER},
      str({role for _start, _length, role
           in SH.tokenize_line(SH.LANG_NUMBERS, "10.0.0.1 42 " * 1000)[0]}))


# ════════════════════════════════════════════════════════════════════════════
# §4 The reader — the tone the parser really paints
# ════════════════════════════════════════════════════════════════════════════
print("== §4 the reader: the address is painted in the LIVE key tone, the port in the number tone ==")

_EDIT = QPlainTextEdit()
_EDIT.resize(420, 120)
_EDIT.show()
_EDIT.setPlainText("host 10.0.0.14 port 51822")
_HL = SH.create_highlighter(_EDIT.document(), SH.LANG_NUMBERS)
_HL.set_window(0, _EDIT.document().blockCount())
_HL.highlight_window(force=True)
app.processEvents()
_FORMATS = block_formats(_EDIT, 0)
check("§4 the applied formats are the address in `syntax_key` and the port in `syntax_number`",
      _FORMATS == [("10.0.0.14", theme.DARK.syntax_key), ("51822", theme.DARK.syntax_number)],
      str(_FORMATS))
theme.set_theme(theme.LIGHT)
_HL.refresh_theme()
app.processEvents()
_LIGHT_FORMATS = block_formats(_EDIT, 0)
theme.set_theme(theme.DARK)
_HL.refresh_theme()
check("§4 a theme switch repaints the address in that instance's key tone (no literal)",
      _LIGHT_FORMATS == [("10.0.0.14", theme.LIGHT.syntax_key),
                         ("51822", theme.LIGHT.syntax_number)],
      str(_LIGHT_FORMATS))
_EDIT.close()


# ════════════════════════════════════════════════════════════════════════════
# §5 The accent a pack only SUGGESTS (the defect this release closes)
# ════════════════════════════════════════════════════════════════════════════
print("== §5 the accent: a pack's hue is applied while it is chosen, and given back when it leaves ==")


def open_dialog():
    """A fresh dialog + the themes it emitted (a config is prepared by the caller)."""
    dlg = SettingsDialog(None)
    emitted = []
    dlg.theme_changed.connect(emitted.append)
    return dlg, emitted


def choose_pack(dlg, pack_id):
    """The pack row's real signal path (the combo is what a user moves)."""
    dlg.pack_combo.setCurrentIndex(dlg.pack_combo.findData(pack_id))


clear_cfg()
theme.packs(reload=True)
_DLG, _EMITTED = open_dialog()
check("§5 a clean config opens on the default accent, with nothing to give back",
      _DLG._accent_hex == DEFAULT_ACCENT and _DLG._own_accent_hex == DEFAULT_ACCENT
      and _DLG._pack_id == "",
      f"{_DLG._accent_hex} / {_DLG._own_accent_hex} / {_DLG._pack_id!r}")
choose_pack(_DLG, "matrix")
check("§5 choosing Matrix applies its suggested hue and the pack's look (a SUGGESTION, live)",
      _DLG._accent_hex == PACK_ACCENT and _DLG._pack_id == "matrix"
      and _EMITTED and _EMITTED[-1].canvas_bg == "#000a04"
      and abs(_EMITTED[-1].accent_hue - 140.0) < 1.0,
      f"{_DLG._accent_hex} / {_EMITTED[-1].canvas_bg if _EMITTED else None}")
check("§5 ...but the USER's own accent was not overwritten (the field still has its owner)",
      _DLG._own_accent_hex == DEFAULT_ACCENT, _DLG._own_accent_hex)
choose_pack(_DLG, "")
check("§5 going back to `Default` gives the field back — the green does not stick (the reported defect)",
      _DLG._accent_hex == DEFAULT_ACCENT and _DLG._own_accent_hex == DEFAULT_ACCENT
      and _DLG._pack_id == "" and _EMITTED[-1].accent == DEFAULT_ACCENT
      and _EMITTED[-1].canvas_bg == theme.DARK.canvas_bg,
      f"{_DLG._accent_hex} / emitted={_EMITTED[-1].accent}")
check("§5 `collect()` writes the restored accent, so the next start cannot inherit the green",
      _DLG.collect()["theme"]["accent"] == DEFAULT_ACCENT
      and "pack" not in _DLG.collect()["theme"],
      str(_DLG.collect()["theme"]))
_DLG.reject()
_DLG.close()

# A config a previous start left holding the pack's suggestion IS healed at the next open.
write_cfg({"theme": {"mode": "dark", "accent": PACK_ACCENT, "motion": True,
                     "density": "normal", "pack": "matrix"}})
theme.packs(reload=True)
_DLG, _EMITTED = open_dialog()
check("§5 a stored pack + its own suggested colour opens ON the pack (the look is the file's)",
      _DLG._accent_hex == PACK_ACCENT and _DLG._pack_id == "matrix"
      and load_theme_settings()["accent"] == PACK_ACCENT,
      f"{_DLG._accent_hex} / {_DLG._pack_id!r}")
check("§5 ...while its real OWNER is the default accent (the suggestion is not a user choice)",
      _DLG._own_accent_hex == DEFAULT_ACCENT, _DLG._own_accent_hex)
choose_pack(_DLG, "")
check("§5 `Default` restores the default accent from a config a previous build baked",
      _DLG._accent_hex == DEFAULT_ACCENT
      and _DLG.collect()["theme"]["accent"] == DEFAULT_ACCENT
      and "pack" not in _DLG.collect()["theme"],
      str(_DLG.collect()["theme"]))
_DLG.reject()
_DLG.close()

# A REAL user accent beside a pack still wins and survives the pack leaving.
write_cfg({"theme": {"mode": "dark", "accent": "#b838f8", "motion": True,
                     "density": "normal", "pack": "matrix"}})
_DLG, _EMITTED = open_dialog()
check("§5 a user's OWN accent beside a pack opens as itself (the choice wins over the suggestion)",
      _DLG._accent_hex == "#b838f8" and _DLG._own_accent_hex == "#b838f8",
      f"{_DLG._accent_hex} / {_DLG._own_accent_hex}")
choose_pack(_DLG, "")
check("§5 ...and leaving the pack keeps it (`Default` never invents a colour)",
      _DLG._accent_hex == "#b838f8" and _DLG.collect()["theme"]["accent"] == "#b838f8",
      str(_DLG.collect()["theme"]))
_DLG.reject()
_DLG.close()

# A manual choice made WITH a pack selected is the user's from then on.
clear_cfg()
_DLG, _EMITTED = open_dialog()
choose_pack(_DLG, "matrix")
_DLG._swatch_buttons["violet"][0].click()
_after_swatch = _DLG._accent_hex
_DLG.accent_hex_edit.setText("#b838f8")
_DLG._on_accent_hex_edited()
check("§5 a swatch and a typed hex chosen under a pack both become the USER's accent",
      _after_swatch == theme.accent_hex(262.0)
      and _DLG._accent_hex == "#b838f8" and _DLG._own_accent_hex == "#b838f8",
      f"{_after_swatch} / {_DLG._accent_hex} / {_DLG._own_accent_hex}")
choose_pack(_DLG, "")
check("§5 ...so `Default` keeps the colour the user picked under the pack",
      _DLG._accent_hex == "#b838f8",
      _DLG._accent_hex)
_DLG.reject()
_DLG.close()

# A mode switch that drops the pack (a dark pack under the light base) drops its accent with it.
clear_cfg()
_DLG, _EMITTED = open_dialog()
choose_pack(_DLG, "matrix")
_DLG.theme_mode_combo.setCurrentIndex(1)
check("§5 a mode switch drops the foreign-base pack and returns the user's accent",
      _DLG._pack_id == "" and _DLG._accent_hex == DEFAULT_ACCENT
      and "pack" not in _DLG.collect()["theme"],
      f"{_DLG._pack_id!r} / {_DLG._accent_hex}")
_DLG.reject()
_DLG.close()


# ════════════════════════════════════════════════════════════════════════════
# §6 The release pins
# ════════════════════════════════════════════════════════════════════════════
print("== §6 the release pins: the version, the parity and the documents ==")

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§6 the release adds NO i18n key — an address is a colour, not a string (parity {EXPECTED_I18N_KEYS})",
      len([key for key in LANGS["en"] if key not in ("name", "partial")]) == EXPECTED_I18N_KEYS,
      str(len([key for key in LANGS["en"] if key not in ("name", "partial")])))
check(f"§6 the release is {EXPECTED_APP_VERSION} and the JSON schema did not move",
      version.APP_VERSION == EXPECTED_APP_VERSION and version.VERSION_FORMAT == "0.9"
      and releases_at_least(EXPECTED_APP_VERSION, "1.14.6"),
      f"{version.APP_VERSION} / {version.VERSION_FORMAT}")
check("§6 the suite map lists this file (tests/INDEX.md regenerated)",
      "test_followups_v1146" in open(ROOT + "/tests/INDEX.md", encoding="utf-8").read())
_FAMILY = changelog_family_text(ROOT)
_DETAILS = changelog_family_text(ROOT, "DETAILS")
check("§6 the changelog family carries the release (the LIVE file or a CLOSED line of it)",
      (not _FAMILY or "v1.14.6" in _FAMILY) and (not _DETAILS or "v1.14.6" in _DETAILS),
      f"changelog={'v1.14.6' in _FAMILY} details={'v1.14.6' in _DETAILS}")
_ROADMAP_TEXT = rep_doc_text("ROADMAP.md")
check("§6 the plan of record no longer carries the shipped section",
      not _ROADMAP_TEXT or "## v1.14.6" not in _ROADMAP_TEXT)
_AGENTS_TEXT = rep_doc_text("AGENTS.md")
_DOC_TEXT = rep_doc_text("DOCUMENTATION.md")
check("§6 the contract names the rule and the mechanism documents it",
      (not _AGENTS_TEXT or "ROLE_IP" in _AGENTS_TEXT)
      and (not _DOC_TEXT or "ipv4_spans" in _DOC_TEXT),
      f"agents={'ROLE_IP' in _AGENTS_TEXT} docs={'ipv4_spans' in _DOC_TEXT}")

finish()
