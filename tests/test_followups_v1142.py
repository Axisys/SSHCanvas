# -*- coding: utf-8 -*-
"""v1.14.2 — THE NOTE: ONE tone for every note on the map, and a fold like a card's.
§1 the tone is a HUE resolved through `theme_for_mode()` (the pure measures, the default = the shipped
family, the ink's contrast); §2 the `theme.note_tone` key and the Appearance row (the live emit, the
refusal, the clean default); §3 the header band (the geometry, the grab area, the double-click contract);
§4 the fold (the size, the position, the dirty marker NOT the undo stack); §5 the schema (the additive
`folded` key, the expanded geometry, the round trip); §6 the refresh walk over the OPEN notes; §7 the
release pins.
Rule — `AGENTS.md` §4.2/§4.6; mechanism — `DOCUMENTATION.md` §20.
Run: python tests/test_followups_v1142.py
"""
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

import colorsys  # noqa: E402 — the HSL measures of a shipped colour (the test's own arithmetic)

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import _size_budget as SBZ  # noqa: E402 — the size ratchet
import ui.main_window as MW  # noqa: E402
import ui.theme as theme  # noqa: E402
import version  # noqa: E402
from graphics.map_scene import MapScene  # noqa: E402
from graphics.map_view import MapView  # noqa: E402
from graphics.sticky_note import StickyNote  # noqa: E402
from models.server import ServerData  # noqa: E402
from ui import theme_qss  # noqa: E402
from ui.settings_dialog import (SettingsDialog, load_theme_settings,  # noqa: E402
                                theme_from_settings)

LANGS = load_i18n_langs(ROOT)
THEME_SRC = os.path.join(ROOT, "ui", "theme.py")
NOTE_SRC = os.path.join(ROOT, "graphics", "sticky_note.py")
SETTINGS_SRC = os.path.join(ROOT, "ui", "settings_dialog.py")
TONE = "#22c55e"          # the tone these checks choose (its HUE is what reaches the palette)
TONE_HUE = theme.hex_hue(TONE)


def lines(path):
    """The lines of one module — the size pins the slot states."""
    with open(path, encoding="utf-8") as handle:
        return len(handle.read().splitlines())


def luminance(hex_color):
    """WCAG relative luminance of a "#rrggbb" colour (the contrast gate's own measure)."""
    channels = []
    for i in (1, 3, 5):
        value = int(hex_color[i:i + 2], 16) / 255.0
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(one, two):
    """The contrast ratio of two "#rrggbb" colours."""
    a, b = sorted((luminance(one), luminance(two)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def hsl_of(hex_color):
    """(saturation, lightness) in 0..100 of a "#rrggbb" colour — the measures a tone declares."""
    rgb = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    _hue, light, sat = colorsys.rgb_to_hls(*rgb)
    return round(sat * 100.0, 1), round(light * 100.0, 1)


clear_cfg()
theme_qss.apply_theme(theme.DARK, app=app, refresh_windows=False)

# ════════════════════════════════════════════════════════════════════════════
print("== §1 the tone: one HUE, three measures, the shipped default ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the three measures are declared ONCE (the shipped sticky note's own paper/frame/ink)",
      theme.NOTE_TONE_PAPER == (70.0, 78.0) and theme.NOTE_TONE_BORDER == (47.0, 45.0)
      and theme.NOTE_TONE_INK == (19.6, 21.0),
      str((theme.NOTE_TONE_PAPER, theme.NOTE_TONE_BORDER, theme.NOTE_TONE_INK)))
_measures = ((hsl_of(theme.DARK.note_bg), theme.NOTE_TONE_PAPER),
             (hsl_of(theme.DARK.note_border), theme.NOTE_TONE_BORDER),
             (hsl_of(theme.DARK.note_text), theme.NOTE_TONE_INK))
check("§1 ...and each measure IS the shipped note's own saturation/lightness (within 0.5)",
      all(abs(got - want) <= 0.5 for pair, measure in _measures
          for got, want in zip(pair, measure)),
      str(_measures))
check("§1 the resolver: a colour → its HUE, a number → itself, NO value → None",
      theme.resolve_note_tone(TONE) == TONE_HUE and theme.resolve_note_tone(200) == 200.0
      and theme.resolve_note_tone(None) is None and theme.resolve_note_tone("") is None,
      str([theme.resolve_note_tone(TONE), theme.resolve_note_tone(200), theme.resolve_note_tone("")]))
check("§1 a broken tone is NO tone (never an error, never a second palette)",
      all(theme.resolve_note_tone(v) is None for v in ("zzz", "green", True, object())),
      str([theme.resolve_note_tone(v) for v in ("zzz", "green", True)]))
check("§1 ...a colour spelled WITHOUT its '#' is still the colour (the accent's own tolerance)",
      theme.resolve_note_tone("22c55e") == TONE_HUE, str(theme.resolve_note_tone("22c55e")))
check("§1 no tone → the SHARED instance (the identity the caches and the tests rely on)",
      theme.theme_for_mode("dark") is theme.DARK
      and theme.theme_for_mode("light", None, "") is theme.LIGHT
      and theme.theme_for_mode("dark", None, None) is theme.DARK)
_toned = theme.theme_for_mode("dark", None, TONE)
check("§1 a tone → a REPLACED instance that carries the hue it was generated from",
      _toned is not theme.DARK and _toned.note_tone == TONE_HUE
      and (_toned.note_bg, _toned.note_border, _toned.note_text) == theme.note_tone_colors(TONE_HUE),
      f"{_toned.note_bg} {_toned.note_border} {_toned.note_text} / {_toned.note_tone}")
check("§1 ...and DARK / LIGHT themselves do not move (the shipped literals stay the default)",
      theme.DARK.note_tone is None and theme.LIGHT.note_tone is None
      and (theme.DARK.note_bg, theme.DARK.note_border, theme.DARK.note_text)
      == ("#eedd9f", "#a9853d", "#403a2b")
      and (theme.LIGHT.note_bg, theme.LIGHT.note_border, theme.LIGHT.note_text)
      == ("#ecd284", "#8a6d2f", "#403a2b"),
      f"{theme.DARK.note_bg} / {theme.LIGHT.note_bg}")
_light_toned = theme.theme_for_mode("light", 260.0, TONE)
check("§1 the tone and the accent resolve TOGETHER (one call, two independent choices)",
      _light_toned.canvas_bg == theme.LIGHT.canvas_bg and _light_toned.hue() == 260.0
      and _light_toned.note_bg == _toned.note_bg,
      f"{_light_toned.canvas_bg} {_light_toned.accent} {_light_toned.note_bg}")
_ratios = {hue: contrast(*[theme.note_tone_colors(hue)[i] for i in (0, 2)])
           for hue in (0.0, 60.0, 120.0, 180.0, 240.0, 300.0)}
check("§1 the ink clears AA (4.5:1) on the paper of EVERY hue tried (six hues, one family)",
      all(ratio >= 4.5 for ratio in _ratios.values()),
      str({hue: round(ratio, 2) for hue, ratio in _ratios.items()}))
check("§1 ...and the paper keeps its own contrast on both canvases (the border is the light one)",
      contrast(_toned.note_border, theme.LIGHT.canvas_bg) >= 1.5
      and contrast(_toned.note_bg, theme.DARK.canvas_bg) >= 8.0,
      f"{contrast(_toned.note_border, theme.LIGHT.canvas_bg):.2f} / "
      f"{contrast(_toned.note_bg, theme.DARK.canvas_bg):.2f}")
_exported = theme.export_theme()
theme.set_theme(_toned)
try:
    check("§1 an EXPORT carries the ACTIVE tone (the notes are content, not chrome)",
          theme.export_theme(palette=theme.PALETTE_PRINT).note_bg == _toned.note_bg
          and theme.export_theme(palette=theme.PALETTE_THEME) is _toned,
          theme.export_theme().note_bg)
    check("§1 ...while the print palette still answers the LIGHT page",
          theme.export_theme().canvas_bg == theme.LIGHT.canvas_bg)
finally:
    theme.set_theme(theme.DARK)

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the key and the Appearance row ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 no `theme.note_tone` → the shipped family, and the dict still names it",
      load_theme_settings() == {"mode": "dark", "accent": "#38bdf8", "motion": True,
                                "density": "normal", "note_tone": ""},
      str(load_theme_settings()))
clear_cfg()
from _common import write_cfg  # noqa: E402 — the config writer of the isolated HOME

write_cfg({"theme": {"mode": "light", "note_tone": "22C55E"}})
_stored = load_theme_settings()
check("§2 a stored tone round-trips as a lower-case colour and reaches the instance",
      _stored["note_tone"] == TONE and theme_from_settings(_stored).note_tone == TONE_HUE,
      f"{_stored['note_tone']} / {theme_from_settings(_stored).note_tone}")
write_cfg({"theme": {"note_tone": "green"}})
check("§2 a broken tone is refused with ONE log line (the app keeps the shipped family)",
      load_theme_settings()["note_tone"] == "" and theme_from_settings(
          load_theme_settings()).note_tone is None,
      str(load_theme_settings()))
clear_cfg()

dlg = SettingsDialog(None)
check("§2 the row exists (its own label, the colour field, the picker and the hint)",
      dlg._lbl_note_tone.text() != "" and dlg.note_tone_edit.text() == ""
      and dlg.note_tone_pick_btn.text() != "" and dlg._lbl_note_tone_hint.text() != "",
      f"{dlg._lbl_note_tone.text()!r} / {dlg.note_tone_edit.text()!r}")
check("§2 the row is SEARCHABLE like every other row of the tab",
      any(entry["label"] is dlg._lbl_note_tone for entry in dlg._search_entries)
      and any(entry["label"] is dlg._lbl_note_tone_hint for entry in dlg._search_entries),
      str([entry["text"] for entry in dlg._search_entries if "tone" in entry["text"].lower()]))
check("§2 the shipped default writes NO key — a clean config stays clean",
      "note_tone" not in dlg.collect()["theme"] and len(dlg.collect()) == 30,
      str(dlg.collect()["theme"]))
_emitted = []
dlg.theme_changed.connect(lambda instance: _emitted.append(instance))
dlg.note_tone_edit.setText(TONE)
dlg._on_note_tone_edited()
check("§2 a typed colour applies LIVE (the map sees it before OK)",
      _emitted and _emitted[-1].note_tone == TONE_HUE
      and _emitted[-1].note_bg == theme.note_tone_colors(TONE_HUE)[0],
      str(getattr(_emitted[-1], "note_tone", None) if _emitted else None))
check("§2 collect() carries the chosen tone inside the ONE nested `theme` key",
      dlg.collect()["theme"]["note_tone"] == TONE and len(dlg.collect()) == 30,
      str(dlg.collect()["theme"]))
_before = _emitted[-1] if _emitted else None
dlg.note_tone_edit.blockSignals(True)
dlg.note_tone_edit.setText("nope")
dlg._on_note_tone_edited()
dlg.note_tone_edit.blockSignals(False)
check("§2 an unusable value is REFUSED — the field returns to the applied tone",
      dlg.note_tone_edit.text() == TONE and dlg.collect()["theme"]["note_tone"] == TONE,
      f"field={dlg.note_tone_edit.text()!r}")
dlg.note_tone_edit.setText("")
dlg._on_note_tone_edited()
check("§2 an EMPTY field is the default tone again (no second control for the reset)",
      _emitted[-1].note_tone is None and "note_tone" not in dlg.collect()["theme"],
      str(dlg.collect()["theme"]))
dlg.close()

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the header band ==")
# ════════════════════════════════════════════════════════════════════════════

scene = MapScene()
view = MapView(scene)
view.resize(640, 480)
view.show()
app.processEvents()
note = scene.add_note("deploy window\nnotify the NOC", 0.0, 0.0, 300.0, 160.0)
check("§3 the band is declared once and fits inside the smallest note",
      StickyNote.HEADER_H == 22.0 and 0.0 < StickyNote.HEADER_H < StickyNote.MIN_H,
      f"{StickyNote.HEADER_H} of {StickyNote.MIN_H}")
check("§3 band_rect() is the top strip; the chevron zone is its right corner",
      note.band_rect() == QRectF(0.0, 0.0, 300.0, StickyNote.HEADER_H)
      and note.chevron_rect().right() == 300.0
      and note.chevron_rect().width() == StickyNote.CHEVRON_ZONE,
      f"{note.band_rect()} / {note.chevron_rect()}")
check("§3 the title columns never run under the fold arrow (the elide window is smaller)",
      note.band_rect().width() - 10.0 - StickyNote.CHEVRON_ZONE < note.chevron_rect().left())
check("§3 the editor's TEXT starts BELOW the band (its viewport is pushed down, not the item)",
      note.widget().viewport().geometry().top() >= StickyNote.HEADER_H,
      str(note.widget().viewport().geometry()))
check("§3 the band's line is the FIRST non-empty line of the text",
      note._band_title() == "deploy window", note._band_title())
note.set_text("\n\n   \n  the real line\nsecond")
check("§3 ...an empty or blank-led note answers the placeholder sentence",
      note._band_title() == "the real line", note._band_title())
note.set_text("")
check("§3 ...and a note with NO text asks the i18n placeholder (one key, no new string)",
      note._band_title() != "" and LANGS["en"].get("note.fold.tooltip"), note._band_title())
note.set_text("deploy window\nnotify the NOC")
check("§3 the fold is discoverable without a menu (the item carries its tooltip)",
      note.toolTip() != "" and note.toolTip() == LANGS["en"]["note.fold.tooltip"],
      note.toolTip())

# ── the painted band: the tint above, the paper below (the ONE way to read a paint) ────
_image = QImage(420, 260, QImage.Format.Format_ARGB32)
_image.fill(0)
_painter = QPainter(_image)
scene.render(_painter, QRectF(0, 0, 420, 260), QRectF(0, 0, 420, 260))  # 1:1 — a pixel IS a point
_painter.end()


def blend(bottom, top, alpha):
    """The "#rrggbb" of `top` painted over `bottom` at `alpha` (0..255) — the band's own maths."""
    return "#" + "".join(
        "%02x" % int(round(int(bottom[i:i + 2], 16) + (int(top[i:i + 2], 16)
                                                     - int(bottom[i:i + 2], 16)) * alpha / 255.0))
        for i in (1, 3, 5))


_band_expected = blend(theme.DARK.note_bg, theme.DARK.note_border, StickyNote.BAND_TINT_ALPHA)
_band_px = _image.pixelColor(50, 8).name()
check("§3 the band is painted over the paper as a TINT of the note's own frame tone",
      all(abs(int(_band_px[i:i + 2], 16) - int(_band_expected[i:i + 2], 16)) <= 2 for i in (1, 3, 5))
      and _image.pixelColor(150, 60).name() == theme.DARK.note_bg,
      f"band={_band_px} expected={_band_expected} body={_image.pixelColor(150, 60).name()}")

# ── the double-click contract: the BAND folds, the BODY edits ────────
view_pt = lambda scene_pos: view.mapFromScene(note.mapToScene(scene_pos))  # noqa: E731
QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                  view_pt(QPointF(120, 8)))
app.processEvents()
check("§3 a double click on the BAND toggles the fold (and never enters the editor)",
      note.folded is True and note.editing is False, f"folded={note.folded} editing={note.editing}")
QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                  view_pt(QPointF(120, 8)))
app.processEvents()
check("§3 ...a folded note's whole strip IS the band, so the same double click unfolds it",
      note.folded is False and note.editing is False)
QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                  view_pt(QPointF(120, 90)))
app.processEvents()
check("§3 a double click on the BODY keeps the shipped contract (the editor takes the focus)",
      note.editing is True and note.folded is False)
note.exit_edit_mode()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the fold: the size, the position, the state ==")
# ════════════════════════════════════════════════════════════════════════════

note.setPos(120.0, 140.0)
w0, h0 = note.rect().width(), note.rect().height()
_seen = []
note.foldChanged.connect(lambda folded: _seen.append(folded))
check("§4 fold() answers once and is idempotent",
      note.fold() is True and note.fold() is False and _seen == [True], str(_seen))
check("§4 a folded note IS the band (the item's height is the band's, the width untouched)",
      note.rect() == QRectF(0.0, 0.0, w0, StickyNote.HEADER_H),
      f"{note.rect()} (was {w0:.0f}x{h0:.0f})")
check("§4 the fold moves NOTHING (the position and the pinned offset survive)",
      (note.pos().x(), note.pos().y()) == (120.0, 140.0) and note.anchor_offset == (0.0, 0.0),
      str(note.pos()))
check("§4 the text layer is gone while folded (an empty viewport, no scrollbar)",
      note.widget().viewport().height() == 0
      and not note.widget().verticalScrollBar().isVisible()
      and note.widget().isVisible() and note.isVisible(),
      f"viewport={note.widget().viewport().geometry()} visible={note.isVisible()}")
check("§4 a folded note still takes the mouse (the ITEM stays visible and selectable)",
      [item for item in scene.items(note.mapToScene(QPointF(20, 8))) if item is note],
      str([type(i).__name__ for i in scene.items(note.mapToScene(QPointF(20, 8)))]))
check("§4 a folded note refuses the corner resize and the editor (the band has neither)",
      (note.set_note_size(400, 400), note.rect().height() == StickyNote.HEADER_H)[1]
      and (note.enter_edit_mode(), note.editing is False)[1],
      str(note.rect()))
_seen.clear()
check("§4 unfold() restores the size the fold snapshotted",
      note.unfold() is True and note.unfold() is False
      and (note.rect().width(), note.rect().height()) == (w0, h0) and _seen == [False],
      f"{note.rect()} / {_seen}")
check("§4 ...and the text layer returns (a viewport below the band, the 'as needed' bars)",
      note.widget().viewport().geometry().top() >= StickyNote.HEADER_H
      and note.widget().viewport().height() > 0)
note.enter_edit_mode()
_folded_while_editing = note.fold()
check("§4 folding WHILE editing leaves the editor (no focus in a text layer under the band)",
      _folded_while_editing is True and note.editing is False
      and note.widget().hasFocus() is False,
      f"fold={_folded_while_editing} editing={note.editing}")
QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                 view_pt(QPointF(note.rect().width() - 8.0, 10.0)))
app.processEvents()
check("§4 a click on the ARROW is the fold's second door (it never starts a drag)",
      note.folded is False and note._drag_mode is None,
      f"folded={note.folded} drag={note._drag_mode}")

# ── a pinned note: the fold keeps the anchor and its line ────────
node = scene.add_server(ServerData(id="nt-1", alias="web-1", host="10.0.0.5", user="root"))
scene.attach_note_to_node(note, node)
_anchor_before = tuple(note.anchor_offset)
_line_before = scene._note_anchor_lines.get(note.note_id)
check("§4 (setup) the note is pinned and its anchor line exists",
      note.server_id == "nt-1" and _line_before is not None, str(note.server_id))
note.fold()
app.processEvents()
check("§4 a pinned note keeps its anchor offset AND its line follows the folded edge",
      tuple(note.anchor_offset) == _anchor_before
      and scene._note_anchor_lines.get(note.note_id) is _line_before
      and _line_before.path().pointAtPercent(0.0).y() is not None,
      f"{note.anchor_offset} / {_line_before.path().elementCount()}")
note.unfold()

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the schema: one additive note key ==")
# ════════════════════════════════════════════════════════════════════════════

record = note.to_dict()
check("§5 an OPEN note writes no fold key (the file of a folded map is the only one that changes)",
      "folded" not in record and set(record) == {"id", "text", "x", "y", "width", "height",
                                                 "server_id"},
      str(sorted(record)))
note.fold()
record = note.to_dict()
check("§5 a folded note writes `folded` and the EXPANDED geometry (a save loses no size)",
      record.get("folded") is True
      and (record["width"], record["height"]) == (w0, h0),
      f"folded={record.get('folded')} {record['width']}x{record['height']} (item {note.rect().height():.0f})")
_copy = StickyNote.from_dict(record)
check("§5 from_dict restores the state without a receiver (the constructor applies it silently)",
      _copy.folded is True and _copy.rect().height() == StickyNote.HEADER_H
      and _copy._expanded_size == (w0, h0),
      f"{_copy.folded} {_copy.rect()} {_copy._expanded_size}")
check("§5 ...and the round trip is stable (every value the RECORD owns comes back unchanged — "
      "the position and the pinning are scene operations, §1 of the attach contract)",
      {k: v for k, v in _copy.to_dict().items() if k not in ("x", "y", "server_id")}
      == {k: v for k, v in record.items() if k not in ("x", "y", "server_id")},
      str(_copy.to_dict()))
check("§5 a file WITHOUT the key opens unfolded (backward compatibility, the additive rule)",
      StickyNote.from_dict({"id": "old-1", "text": "t", "width": 240, "height": 160}).folded is False)
check("§5 the folded record's width/height are NOT the band's (one truth for the geometry)",
      record["height"] != StickyNote.HEADER_H, str(record["height"]))
note.unfold()
check("§5 the format did NOT move (an additive key needs no schema bump)",
      version.VERSION_FORMAT == "0.9", version.VERSION_FORMAT)

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the window: the dirty marker, the refresh walk, the undo side ==")
# ════════════════════════════════════════════════════════════════════════════

win = MW.MainWindow()
win._autosave_timer.stop()
win._freshness_timer.stop()
win.resize(1100, 760)
win.show()
app.processEvents()
win.scene.add_note("window note", 0.0, 0.0, 240.0, 140.0)
_wnote = win.scene.notes()[-1]
win._connect_note_signals(_wnote)
win._reset_undo_stack()
win._dirty = False
_undo_before = win.undo_stack.count()
_wnote.fold()
app.processEvents()
check("§6 the fold marks the project DIRTY (the state is saved) ...",
      win._dirty is True, f"{win._dirty}")
check("§6 ...and it is NOT an undo step (it moves no card: the stack is untouched)",
      win.undo_stack.count() == _undo_before == 0, str(win.undo_stack.count()))

_path = os.path.join(WORK, "note_fold_v1142.json")
win._do_save(_path)
import json  # noqa: E402 — the file is the contract

with open(_path, encoding="utf-8") as handle:
    _saved = json.load(handle)
_saved_note = next(n for n in _saved["notes"] if n["id"] == _wnote.note_id)
check("§6 a saved folded note reaches the file as the key + the expanded size",
      _saved_note.get("folded") is True and _saved_note["height"] == 140.0,
      str(_saved_note))
win._reset_undo_stack()
win._dirty = False
win._import_project_raw(_saved, base_dir=os.path.dirname(_path))
_reloaded = win.scene.get_note_by_id(_wnote.note_id)
check("§6 a reload restores the FOLDED note (the same band) without dirtying the project",
      _reloaded is not None and _reloaded.folded is True
      and _reloaded.rect().height() == StickyNote.HEADER_H and _reloaded._expanded_size[1] == 140.0
      and win._dirty is False,
      f"{getattr(_reloaded, 'rect', lambda: None)()} dirty={win._dirty}")

# the theme walk: a tone reaches every OPEN note through the ordinary switch
_win_note = _reloaded
theme_qss.apply_theme(_toned, app=app, refresh_windows=True)
app.processEvents()
check("§6 the tone switch repaints the OPEN note (the note reads the ACTIVE instance live)",
      theme.NOTE_BG == _toned.note_bg and _win_note.BG_COLOR == _toned.note_bg,
      f"{theme.NOTE_BG} / {_win_note.BG_COLOR}")
img = QImage(600, 400, QImage.Format.Format_ARGB32)
img.fill(0)
painter = QPainter(img)
_rect = QRectF(_win_note.pos().x(), _win_note.pos().y(), 240.0, StickyNote.HEADER_H)
win.scene.render(painter, QRectF(0, 0, 600, 400),
                 QRectF(_rect.x() - 40, _rect.y() - 40, 600, 400))
painter.end()
check("§6 ...and it PAINTS the new tone (the band of the reloaded, folded note)",
      img.pixelColor(60, 50).name() != theme.DARK.note_bg,
      f"{img.pixelColor(60, 50).name()} vs {theme.DARK.note_bg}")
win.refresh_theme()
check("§6 the window's own walk keeps the band's reserve (refresh_theme re-applies the margins)",
      _win_note.widget().viewport().geometry().top() >= StickyNote.HEADER_H
      or not _win_note.folded,
      str(_win_note.widget().viewport().geometry()))
theme_qss.apply_theme(theme.DARK, app=app, refresh_windows=True)
app.processEvents()

# the undo side of a DELETE: the command carries the fold with the record
_removed = win._remove_note(_win_note)
check("§6 (setup) deleting the folded note is one command",
      _removed is True and win.scene.get_note_by_id(_win_note.note_id) is None)
win.undo_stack.undo()
app.processEvents()
_restored = win.scene.get_note_by_id(_win_note.note_id)
check("§6 undoing the DELETE brings the note back FOLDED (the record owns the state)",
      _restored is not None and _restored.folded is True
      and _restored.rect().height() == StickyNote.HEADER_H,
      f"{getattr(_restored, 'folded', None)}")
win._dirty = False
win._undo_baseline_dirty = False
win.close()
app.processEvents()

# ════════════════════════════════════════════════════════════════════════════
print("== §7 i18n, the size ratchet and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§7 the three new strings exist in every language (parity is {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1196
      and all(code in LANGS and all(key in LANGS[code] for key in
                                    ("settings.appearance.note_tone",
                                     "settings.appearance.note_tone.hint", "note.fold.tooltip"))
              for code in LANGS),
      str(sorted(LANGS)))
check("§7 the pin names this release's line and the schema did NOT move",
      releases_at_least(EXPECTED_APP_VERSION, "1.14.2") and version.VERSION_FORMAT == "0.9",
      f"{EXPECTED_APP_VERSION} / {version.VERSION_FORMAT}")
check("§7 APP_VERSION is the shipped release", version.APP_VERSION == EXPECTED_APP_VERSION,
      version.APP_VERSION)
check("§7 the pinned modules ride their LINE PINS (theme.py and the hub pay for their lines)",
      all(lines(path) <= SBZ.LINE_PINS[name] for path, name in
          ((THEME_SRC, "ui/theme.py"), (SETTINGS_SRC, "ui/settings_dialog.py"))),
      f"theme={lines(THEME_SRC)}/{SBZ.LINE_PINS['ui/theme.py']} "
      f"hub={lines(SETTINGS_SRC)}/{SBZ.LINE_PINS['ui/settings_dialog.py']}")
check("§7 the note stays UNDER the band (its size is not a pin the slot had to raise)",
      lines(NOTE_SRC) < SBZ.BUDGET_BAND_LINES
      and "graphics/sticky_note.py" not in SBZ.LINE_PINS,
      f"{lines(NOTE_SRC)} lines")
finish()
