# -*- coding: utf-8 -*-
"""v1.14.7.1 — THE SEAM THAT CANNOT COST THE START: the seven confirmed defects of `v1.14.7`.
§1 the pack FOLDER is a problem, never a fatal, and the registry scans ONCE per run (`N161`, `N163`);
§2 the clamped fold snapshot — a record outside MIN..MAX is repaired on load and saved repaired (`N162`);
§3 the XML/YAML span budget is the budget (`N164`); §4 the STRICT accent hue (`N165`); §5 the corrected
`collect()` contract (`N166`); §6 a stripped build keeps the corner control's WORD (`N167`); §7 the pins.
Rule — `AGENTS.md` §4.6 / §4.32.2; mechanism — `DOCUMENTATION.md`, "Central UI theme" and §23, §38, §64.
Run: python tests/test_hardening_v11471.py
"""
import json
import os
import sys
import tempfile

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, changelog_family_text, check,
                     check_i18n_format, check_i18n_parity, check_release_state, clear_cfg, finish,
                     load_i18n_langs, releases_at_least, rep_doc_text)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import modules.syntax_highlight as SH  # noqa: E402
import ui.theme as theme  # noqa: E402
import ui.theme_store as theme_store  # noqa: E402
import version  # noqa: E402
from graphics.sticky_note import StickyNote  # noqa: E402
from modules import terminal_corner as TC  # noqa: E402
from modules.undo_commands import CmdAddRemoveNote  # noqa: E402
from storage import atomic  # noqa: E402
from ui.settings_dialog import SettingsDialog, theme_from_settings  # noqa: E402

LANGS = load_i18n_langs(ROOT)
SETTINGS_SRC = os.path.join(ROOT, "ui", "settings_dialog.py")
BROKEN_USER = os.path.join(WORK, "pack-folder-denied")   # the ACL shape: isdir() passes, listdir() raises
os.makedirs(BROKEN_USER, exist_ok=True)
_REAL_LISTDIR = os.listdir
_REAL_USER_DIR = theme_store.user_dir


def listing_denied(path=".", *args, **kwargs):
    """`os.listdir` of ONE folder, denied — the Windows ACL the entry describes."""
    if os.path.abspath(str(path)) == os.path.abspath(BROKEN_USER):
        raise PermissionError(13, "Access is denied")
    return _REAL_LISTDIR(path, *args, **kwargs)


# ════════════════════════════════════════════════════════════════════════════
# §1 The pack folder — an unreadable one costs its own files, never the START
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the folder (`N161`) and the ONE scan (`N163`) ==")

os.listdir = listing_denied
try:
    _packs, _problems = theme_store.discover(root=ROOT, user_dir_path=BROKEN_USER)
except OSError as exc:   # the pre-fix shape: the whole discovery aborts
    _packs, _problems = {}, [exc]
check("§1 an unreadable pack FOLDER is ONE problem, never an exception out of `discover()`",
      isinstance(_problems[0], theme_store.PackProblem),
      f"{type(_problems[0]).__name__}: {_problems[0]}")
check("§1 ...and the OTHER folder is still read — the shipped packs survive a broken user folder",
      sorted(_packs) == ["matrix", "paper"]
      and all(pack.builtin for pack in _packs.values()),
      f"{sorted(_packs)} / {[getattr(p, 'reason', p) for p in _problems]}")
check("§1 the problem carries REASON_UNREADABLE and NAMES the folder it could not list",
      [getattr(p, "reason", None) for p in _problems] == [theme_store.REASON_UNREADABLE]
      and [getattr(p, "path", "") for p in _problems] == [BROKEN_USER]
      and os.path.basename(BROKEN_USER) in _problems[0].sentence(),
      f"{[getattr(p, 'sentence', lambda: '')() for p in _problems]}")

theme_store.user_dir = lambda: BROKEN_USER
try:
    _registry = theme.packs(reload=True)
    check("§1 `theme.packs()` never raises over the broken folder — the START and the Settings hub live",
          sorted(_registry) == ["matrix", "paper"] and len(theme.PACK_PROBLEMS) == 1
          and theme.PACK_PROBLEMS[0].reason == theme_store.REASON_UNREADABLE,
          f"{sorted(_registry)} / {[p.sentence() for p in theme.PACK_PROBLEMS]}")
    _instance = theme_from_settings({"mode": "dark", "accent": "#38bdf8", "pack": "matrix"})
    check("§1 a stored pack id still resolves: the start path answers the SHIPPED look, not a crash",
          _instance.canvas_bg == "#000a04",
          f"{_instance.canvas_bg} / {[p.sentence() for p in theme.PACK_PROBLEMS]}")
finally:
    theme_store.user_dir = _REAL_USER_DIR
    os.listdir = _REAL_LISTDIR
    theme.packs(reload=True)

_calls = {"n": 0}
_real_discover = theme_store.discover


def counted_discover(*args, **kwargs):
    """The real discovery, counted — the ONE seam the entry's probe patches."""
    _calls["n"] += 1
    return _real_discover(*args, **kwargs)


theme_store.discover = counted_discover
theme.PACKS.clear()
theme._PACK_LOADED = False
try:
    for _ in range(5):
        theme.theme_for_mode("dark", None, None, pack="matrix")
    _first = _calls["n"]
    theme.packs(reload=True)
    _second = _calls["n"]
finally:
    theme_store.discover = _real_discover
    theme.packs(reload=True)
check("§1 the registry is scanned ONCE for five resolutions — an EMPTY registry is a RESULT",
      _first == 1, f"scans={_first} for 5 resolutions")
check("§1 `reload=True` still forces the scan (the Settings door and the folder recovery)",
      _second == 2, f"scans after packs(reload=True)={_second}")
check("§1 an intact folder set answers both packs and NO problem (the guard is not vacuous)",
      sorted(theme.PACKS) == ["matrix", "paper"] and not theme.PACK_PROBLEMS,
      f"{sorted(theme.PACKS)} / {[p.sentence() for p in theme.PACK_PROBLEMS]}")


# ════════════════════════════════════════════════════════════════════════════
# §2 The fold snapshot — a foreign record is repaired on load and saved repaired
# ════════════════════════════════════════════════════════════════════════════
print("== §2 the clamped fold snapshot (`N162`) ==")

MAX_PAIR = (StickyNote.MAX_W, StickyNote.MAX_H)
MIN_PAIR = (StickyNote.MIN_W, StickyNote.MIN_H)
_wide = StickyNote("wide", 0.0, 0.0, 4000.0, 3000.0, folded=True)
check("§2 the fold snapshot holds the CLAMPED pair — never the raw 4000 × 3000 of the record",
      _wide._expanded_size == MAX_PAIR,
      f"{_wide._expanded_size} vs {MAX_PAIR}")
_wide.unfold()
check("§2 `unfold()` restores INSIDE the declared bound (the second belt)",
      (_wide.rect().width(), _wide.rect().height()) == MAX_PAIR,
      f"{_wide.rect().width()} × {_wide.rect().height()}")
_broken = StickyNote("broken", 0.0, 0.0, -50.0, -10.0, folded=True)
_broken.unfold()
check("§2 a NEGATIVE record unfolds to the MIN pair, never to a 0 × 0 note",
      (_broken.rect().width(), _broken.rect().height()) == MIN_PAIR,
      f"{_broken.rect().width()} × {_broken.rect().height()}")
_folded = StickyNote("saved", 0.0, 0.0, 4000.0, 3000.0, folded=True)
_record = _folded.to_dict()
check("§2 a folded note SAVES the clamped pair — the next load cannot inherit 4000 × 3000",
      (_record["width"], _record["height"]) == MAX_PAIR and _record["folded"] is True,
      f"{_record}")
_inside = StickyNote.from_dict({"id": "ok1", "text": "app-written", "x": 5.0, "y": 6.0,
                                "width": 300.0, "height": 160.0, "folded": True})
_inside.unfold()
_inside_record = _inside.to_dict()
check("§2 an app-written record is unchanged byte for byte (the repair touches ONLY a foreign one)",
      (_inside_record["width"], _inside_record["height"]) == (300.0, 160.0)
      and (_inside.rect().width(), _inside.rect().height()) == (300.0, 160.0)
      and (_inside_record["x"], _inside_record["y"]) == (5.0, 6.0),
      f"{_inside_record}")


class _NoteScene:
    """The THREE doors `CmdAddRemoveNote` asks of a scene (no QGraphicsScene is needed)."""

    def __init__(self):
        self.notes = {}

    def add_note(self, text="", x=0.0, y=0.0, width=240.0, height=160.0,
                 note_id=None, folded=False):
        note = StickyNote(text, x, y, width, height, note_id=note_id, folded=folded)
        self.notes[note.note_id] = note
        return note

    def get_note_by_id(self, note_id):
        """The note of one id, or None."""
        return self.notes.get(note_id)

    def remove_note(self, note_id):
        """Drop a note by id."""
        self.notes.pop(note_id, None)


class _NoteWin:
    """The window half: the attach door the command calls (the real one wires the signals)."""

    def _attach_note(self, note):
        """Accepted and ignored — the command's own contract is what this check drives."""
        return note


_scene, _win = _NoteScene(), _NoteWin()
_command = CmdAddRemoveNote(_win, _scene, {"id": "fold1", "text": "folded",
                                          "x": 10.0, "y": 10.0, "width": 4000.0,
                                          "height": 3000.0, "folded": True}, "add")
_command.redo()
_note = _scene.get_note_by_id("fold1")
check("§2 `CmdAddRemoveNote` re-spawns a folded note through the constructor — the clamp holds",
      _note is not None and _note._folded and _note._expanded_size == MAX_PAIR,
      f"{None if _note is None else (_note._folded, _note._expanded_size)}")
_command.undo()
_gone = _scene.get_note_by_id("fold1") is None
_command.redo()
_note = _scene.get_note_by_id("fold1")
check("§2 ...and `folded` survives BOTH directions of the command, still inside the bound",
      _gone and _note is not None and _note._folded and _note._expanded_size == MAX_PAIR,
      f"gone={_gone} / {None if _note is None else (_note._folded, _note._expanded_size)}")


# ════════════════════════════════════════════════════════════════════════════
# §3 The span budget — the budget means the budget, in every language
# ════════════════════════════════════════════════════════════════════════════
print("== §3 the XML/YAML span budget (`N164`) ==")

SHAPES = (("xml", '<?xml?><?xml?>key: value<!--'),
          ("xml", '#---<a b="c"><!--1.2.3.4'),
          ("yaml", 'cmd: echo a | grep ba # b'),
          ("yaml", 'key: "quoted | > block" # tail'),
          ("json", '{"a": [1, 2.5e3, true], "b": null}'),
          ("numbers", 'host 1.2.3.4 port 42 ver 1.2.3'))
_over = []
for _language, _line in SHAPES:
    for _budget in (1, 2, 3, 4, 5):
        _spans, _state = SH.tokenize_line(_language, _line, 0, _budget)
        if len(_spans) > _budget:
            _over.append((_language, _budget, len(_spans)))
check("§3 no language answers MORE spans than its budget (1..5 over six hostile shapes)",
      not _over, f"{_over}")
_sorted_bad, _overlap_bad, _bounds_bad, _stray = [], [], [], []
for _language, _line in SHAPES:
    _full, _ = SH.tokenize_line(_language, _line, 0, 500)
    for _budget in (1, 2, 3, 4, 5):
        _spans, _ = SH.tokenize_line(_language, _line, 0, _budget)
        if [s[0] for s in _spans] != sorted(s[0] for s in _spans):
            _sorted_bad.append((_language, _budget))
        if any(a[0] + a[1] > b[0] for a, b in zip(_spans, _spans[1:])):
            _overlap_bad.append((_language, _budget))
        if any(s[0] < 0 or s[0] + s[1] > len(_line) for s in _spans):
            _bounds_bad.append((_language, _budget))
        if [s for s in _spans if s not in _full]:
            _stray.append((_language, _budget))
check("§3 the kept spans stay SORTED by start (the slice drops whole tokens, never splits one)",
      not _sorted_bad, f"{_sorted_bad}")
check("§3 ...and never OVERLAP each other", not _overlap_bad, f"{_overlap_bad}")
check("§3 ...and every one of them lies INSIDE the line", not _bounds_bad, f"{_bounds_bad}")
check("§3 every span a reduced budget keeps is one the FULL scan answers (no span is invented)",
      not _stray, f"{_stray}")
_full_xml, _ = SH.tokenize_line("xml", SHAPES[1][1], 0, 500)
_full_yaml, _ = SH.tokenize_line("yaml", SHAPES[2][1], 0, 500)
check("§3 a generous budget is NOT clipped — the two state-carrying scanners keep their whole line",
      len(_full_xml) == 7 and len(_full_yaml) == 4,
      f"xml={len(_full_xml)} yaml={len(_full_yaml)}")


# ════════════════════════════════════════════════════════════════════════════
# §4 The strict accent hue — a typo refuses the FILE, never a colour by luck
# ════════════════════════════════════════════════════════════════════════════
print("== §4 the strict `accent_hue` (`N165`) ==")


def parse_hue(value):
    """One minimal dark pack carrying `accent_hue = value` → (pack, problems)."""
    return theme_store.parse_pack({"version": 1, "base": "dark", "name": "T",
                                   "accent_hue": value}, "probe")


_boolean = parse_hue(True)
check("§4 a BOOLEAN hue is refused by the FIELD, not by the contrast matrix",
      _boolean[0] is None and _boolean[1][0].reason == theme_store.REASON_BAD_ACCENT
      and "accent_hue" in _boolean[1][0].detail, str(_boolean[1][0].sentence()))
check("§4 `false` is refused too — the predicate is `bool`, never truthiness",
      parse_hue(False)[1][0].reason == theme_store.REASON_BAD_ACCENT,
      parse_hue(False)[1][0].sentence())
check("§4 the numeric STRING is refused (a hue is a NUMBER or a `#rrggbb` colour)",
      parse_hue("198.4")[1][0].reason == theme_store.REASON_BAD_ACCENT
      and parse_hue("0")[1][0].reason == theme_store.REASON_BAD_ACCENT,
      parse_hue("198.4")[1][0].sentence())
_zero = parse_hue(0)
check("§4 `0` is ACCEPTED by the FIELD — `false` and `0` reach DIFFERENT gates, never conflated",
      _zero[1] and _zero[1][0].reason == theme_store.REASON_CONTRAST
      and theme.resolve_accent_hue(0) == 0.0,
      f"{[p.sentence() for p in _zero[1]]} — the field passed, the matrix refused the tone")
_number, _colour = parse_hue(198.4), parse_hue("#ff8800")
check("§4 a NUMBER and a `#rrggbb` colour both load (the colour through its own hue)",
      (_number[0] is not None and _number[0].accent_hue == 198.4)
      and (_colour[0] is not None and abs(_colour[0].accent_hue
                                          - theme.hex_hue("#ff8800")) < 0.01),
      f"{_number[0] and _number[0].accent_hue} / {_colour[0] and _colour[0].accent_hue}")
check("§4 the RESOLVER refuses a `bool` but keeps its own config rule (0 → 0.0, \"198.4\" → 198.4)",
      theme.resolve_accent_hue(True) is None and theme.resolve_accent_hue(False) is None
      and theme.resolve_accent_hue(0) == 0.0
      and theme.resolve_accent_hue("198.4") == 198.4,
      f"{theme.resolve_accent_hue(True)} / {theme.resolve_accent_hue(0)} / "
      f"{theme.resolve_accent_hue('198.4')}")


# ════════════════════════════════════════════════════════════════════════════
# §5 The `collect()` contract — the TOP-level merge, the whole-object replacement
# ════════════════════════════════════════════════════════════════════════════
print("== §5 the corrected `collect()` docstring (`N166`) ==")

_source = open(SETTINGS_SRC, encoding="utf-8").read()
check("§5 the sentence that promised a NESTED merge is GONE from the source",
      "so a mode change never drops a value a foreign version wrote" not in _source
      and "_on_accept` re-merges the stored object" not in _source)
check("§5 ...and the declared one is there: the TOP level, the whole object, the two deleted keys",
      "merges the TOP level only" in _source and "REPLACED whole" in _source
      and "DELETES a cleared `note_tone`/`pack`" in _source
      and "unknown nested key" in _source)

_writer_path = os.path.join(tempfile.mkdtemp(prefix="collect_", dir=WORK), "config.json")
with open(_writer_path, "w", encoding="utf-8") as _handle:
    json.dump({"theme": {"mode": "dark", "mystery": 7}, "lang": "en"}, _handle)
atomic.write_json_atomic(_writer_path, {"theme": {"mode": "light"}}, merge=True)
with open(_writer_path, encoding="utf-8") as _handle:
    _merged = json.load(_handle)
check("§5 the WRITER confirms the sentence: the nested object is replaced whole, a top key survives",
      _merged == {"theme": {"mode": "light"}, "lang": "en"}, f"{_merged}")

clear_cfg()
_dialog = SettingsDialog(None)
check("§5 ...so the OMISSION is what deletes a cleared choice: `collect()` carries no empty `pack`",
      len(_dialog.collect()) == 30 and "pack" not in _dialog.collect()["theme"]
      and "note_tone" not in _dialog.collect()["theme"],
      str(_dialog.collect()["theme"]))
_dialog.reject()
_dialog.close()
clear_cfg()


# ════════════════════════════════════════════════════════════════════════════
# §6 The corner control — a stripped build keeps its WORD
# ════════════════════════════════════════════════════════════════════════════
print("== §6 the stripped build's word (`N167`) ==")

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402

_REAL_CORNER_ICON = TC.get_corner_icon
TC.get_corner_icon = lambda name: QIcon()
try:
    _stripped = QPushButton("Split")
    _shaped = TC.shape_control(_stripped, "split", "Split tooltip", "Split")
finally:
    TC.get_corner_icon = _REAL_CORNER_ICON
check("§6 a build WITHOUT `ui/icons.py` keeps the caller's WORD (no 28 × 28 empty square)",
      _shaped is True and _stripped.text() == "Split" and _stripped.icon().isNull(),
      f"{_stripped.text()!r} / null={_stripped.icon().isNull()}")
check("§6 ...while the tooltip, the accessible name and the fixed square stay in BOTH shapes",
      _stripped.toolTip() == "Split tooltip" and "Split" in _stripped.accessibleName()
      and _stripped.size().toTuple() == (TC.CORNER_BUTTON_PX, TC.CORNER_BUTTON_PX),
      f"{_stripped.toolTip()!r} / {_stripped.accessibleName()!r} / {_stripped.size().toTuple()}")
_shipped = QPushButton("Split")
TC.shape_control(_shipped, "split", "Split tooltip", "Split")
check("§6 the SHIPPED build still clears the word — the glyph carries the control",
      _shipped.text() == "" and not _shipped.icon().isNull()
      and _shipped.size().toTuple() == (TC.CORNER_BUTTON_PX, TC.CORNER_BUTTON_PX),
      f"{_shipped.text()!r} / null={_shipped.icon().isNull()}")
_unknown = QPushButton("Files")
check("§6 an unknown glyph keeps the WORD as well (the glyph's absence is the ONE condition)",
      TC.shape_control(_unknown, "no-such-glyph", "Files tooltip", "Files") is True
      and _unknown.text() == "Files", f"{_unknown.text()!r}")


# ════════════════════════════════════════════════════════════════════════════
# §7 The release pins
# ════════════════════════════════════════════════════════════════════════════
print("== §7 the release pins: the version, the parity, the map and the documents ==")

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§7 the patch adds NO i18n key — parity stays {EXPECTED_I18N_KEYS}",
      all(len([key for key in LANGS[code] if key not in ("name", "partial")]) == EXPECTED_I18N_KEYS
          for code in sorted(LANGS))
      and not [key for key in LANGS["en"] if "v11471" in key.lower()],
      str([key for key in LANGS["en"] if "v11471" in key.lower()]))
check(f"§7 the release is {EXPECTED_APP_VERSION}, four components, and the JSON schema did not move",
      version.APP_VERSION == EXPECTED_APP_VERSION and version.VERSION_FORMAT == "0.9"
      and releases_at_least(EXPECTED_APP_VERSION, "1.14.7") and version.APP_VERSION.count(".") == 3,
      f"{version.APP_VERSION} / {version.VERSION_FORMAT}")
check("§7 the suite map lists this file (tests/INDEX.md regenerated)",
      "test_hardening_v11471" in open(os.path.join(ROOT, "tests", "INDEX.md"),
                                      encoding="utf-8").read())
_family = changelog_family_text(ROOT)
_details = changelog_family_text(ROOT, "DETAILS")
check("§7 the changelog family carries the release (the LIVE file or a CLOSED line of it)",
      (not _family or "v1.14.7.1" in _family) and (not _details or "v1.14.7.1" in _details),
      f"changelog={'v1.14.7.1' in _family} details={'v1.14.7.1' in _details}")
_roadmap_text = rep_doc_text("ROADMAP.md")
check("§7 the plan of record no longer carries the shipped section",
      not _roadmap_text or "## v1.14.7.1" not in _roadmap_text)
_ledger_text = rep_doc_text("AUDIT_PENDING.md")
check("§7 the seven ledger ENTRIES left their file with the release (the batch is a stub now)",
      not _ledger_text or not [n for n in ("N161", "N162", "N163", "N164", "N165", "N166", "N167")
                               if f"### `{n}`" in _ledger_text]
      and "left this file (`N161`–`N167`)" in _ledger_text,
      str([n for n in ("N161", "N162", "N163", "N164", "N165", "N166", "N167")
           if f"### `{n}`" in _ledger_text]))
_agents_text = rep_doc_text("AGENTS.md")
check("§7 the contract states the folder rule and the stripped-build word",
      (not _agents_text or "an unreadable pack FOLDER" in _agents_text)
      and (not _agents_text or "keeps the caller's WORD" in _agents_text))

finish()
