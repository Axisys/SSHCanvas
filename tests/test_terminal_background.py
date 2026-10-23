# -*- coding: utf-8 -*-
"""The terminal wallpaper — `terminal_background*` under the grid (v1.13.2).
§1 the PURE half: the three resolvers, the path gate and the cover/contain/tile geometry; §2 the
reader: the three keys through `load_terminal_settings()` and the defaults of a broken config; §3 the
canvas: the composite, its per-mode geometry, the OFF state and the ONE log line of a bad file; §4 the
paint path: the shipped picture while the key is empty and the transparency rule of a cell; §5 the
settings hub: the row, `collect()`'s three keys and the eight translated strings; §6 the session that
reads the keys and the OPEN sessions the hub re-applies them to; §7 the release.
Rule — `AGENTS.md` §4.3; mechanism — `DOCUMENTATION.md` §78.
"""
import logging
import os

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least, write_cfg)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import i18n  # noqa: E402
import modules.terminal_background as TB  # noqa: E402
import modules.terminal_widget as TW  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import ui.settings_dialog as SD  # noqa: E402
from modules.terminal_screen import PALETTES, TerminalScreen  # noqa: E402

from _fakes import FakeSSHThread  # noqa: E402

LANGS = load_i18n_langs(ROOT)
DEFAULT_BG = PALETTES["default"]["default_bg"]
NORD_BG = PALETTES["nord"]["default_bg"]
PICS = os.path.join(WORK, "pics")
os.makedirs(PICS, exist_ok=True)


def make_png(name, colour, size=(64, 32)):
    """A REAL image on disk (the decoder is the only reader a wallpaper has)."""
    path = os.path.join(PICS, name)
    image = QImage(size[0], size[1], QImage.Format.Format_RGB32)
    image.fill(QColor(colour))
    if not image.save(path):
        raise SystemExit(f"cannot write the fixture image: {path}")
    return path


RED = make_png("red.png", "#ff0000")
BLUE = make_png("blue.png", "#0000ff")
NOT_AN_IMAGE = os.path.join(PICS, "not-an-image.png")
with open(NOT_AN_IMAGE, "wb") as _fh:
    _fh.write(b"this is a text file wearing an image suffix\n")
MISSING = os.path.join(PICS, "there-is-no-such-file.png")


def canvas(width=200, height=60, **kwargs):
    """A real canvas over a 20×4 pyte screen (the offscreen renderer is the shipped one)."""
    widget = TW.TerminalWidget(TerminalScreen(columns=20, lines=4), **kwargs)
    widget.resize(width, height)
    return widget


def shot(widget):
    """The painted canvas as an image (a real `paintEvent` into a pixmap)."""
    return widget.grab().toImage()


def pixel(image, x, y):
    """The `#rrggbb` of one pixel (the comparison the pixel checks read)."""
    return image.pixelColor(int(x), int(y)).name()


def bg_colour_of(widget, points):
    """The pixels a wallpaper would have to own — the checks below read them as colours."""
    return [pixel(shot(widget), x, y) for x, y in points]


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the PURE half: the resolvers, the path gate and the geometry ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 the three modes are declared once, the default first",
      TB.BACKGROUND_MODES == ("cover", "contain", "tile")
      and TB.BACKGROUND_MODE_DEFAULT == "cover", str(TB.BACKGROUND_MODES))
check("§1 the opacity range is 0..100 with a LOW default (the text outranks the decoration)",
      (TB.BACKGROUND_OPACITY_MIN, TB.BACKGROUND_OPACITY_MAX) == (0, 100)
      and 0 < TB.BACKGROUND_OPACITY_DEFAULT < 100, str(TB.BACKGROUND_OPACITY_DEFAULT))
check("§1 the three config keys are the declared spellings",
      (TB.BACKGROUND_CONFIG_KEY, TB.BACKGROUND_MODE_CONFIG_KEY, TB.BACKGROUND_OPACITY_CONFIG_KEY)
      == ("terminal_background", "terminal_background_mode", "terminal_background_opacity"),
      TB.BACKGROUND_CONFIG_KEY)
check("§1 the mode resolver accepts the declared values (case/space folded) and nothing else",
      TB.resolve_background_mode(" tile ") == "tile"
      and TB.resolve_background_mode("CONTAIN") == "contain"
      and all(TB.resolve_background_mode(bad) == TB.BACKGROUND_MODE_DEFAULT
              for bad in ("", "stretch", 7, None, True, ["cover"])),
      str([TB.resolve_background_mode(v) for v in (" tile ", "CONTAIN", "", "stretch", 7, None)]))
check("§1 the opacity resolver clamps a hand-edited number and defaults a foreign type",
      [TB.resolve_background_opacity(v) for v in (0, 35, 100, 150, -5, 42.6)]
      == [0, 35, 100, 100, 0, 43]
      and [TB.resolve_background_opacity(v) for v in ("50", None, True, float("nan"), [1])]
      == [TB.BACKGROUND_OPACITY_DEFAULT] * 5,
      str([TB.resolve_background_opacity(v) for v in (150, -5, 42.6, "50", True)]))
check("§1 the path is stored AS TYPED (trimmed) — the resolver expands `~` when it opens the file",
      TB.normalize_background_path("  ~/pics/room.png ") == "~/pics/room.png"
      and TB.normalize_background_path(None) == ""
      and TB.normalize_background_path(12) == ""
      and TB.normalize_background_path("") == "",
      repr(TB.normalize_background_path("  ~/pics/room.png ")))
check("§1 only `tile` repeats the image",
      TB.background_is_tiled("tile") and not TB.background_is_tiled("cover")
      and not TB.background_is_tiled("contain") and not TB.background_is_tiled("nonsense"))

_cover = TB.background_rect("cover", 100, 50, 200, 200)
_contain = TB.background_rect("contain", 100, 50, 200, 200)
_tile = TB.background_rect("tile", 100, 50, 200, 200)
check("§1 cover fills the canvas and is CENTRED on the overflow (a 2:1 image in a square)",
      _cover == (-100, 0, 400, 200), str(_cover))
check("§1 contain fits the whole image inside and leaves the canvas around it",
      _contain == (0, 50, 200, 100), str(_contain))
check("§1 tile is the NATIVE size at the origin (ONE copy — the repetition is the caller's)",
      _tile == (0, 0, 100, 50), str(_tile))
check("§1 cover never leaves a hole and contain never overflows, on any ratio",
      all(c[2] >= w and c[3] >= h and (c[2] == w or c[3] == h)
          for w, h in ((200, 200), (300, 40), (17, 999))
          for c in (TB.background_rect("cover", 64, 32, w, h),))
      and all(k[2] <= w and k[3] <= h and (k[2] == w or k[3] == h)
              for w, h in ((200, 200), (300, 40), (17, 999))
              for k in (TB.background_rect("contain", 64, 32, w, h),)),
      str([TB.background_rect("cover", 64, 32, 300, 40),
           TB.background_rect("contain", 64, 32, 300, 40)]))
check("§1 the rect keeps the image's ASPECT (a rounding error of one pixel at most)",
      all(abs(c[2] / c[3] - 2.0) < 0.06
          for c in (TB.background_rect("cover", 100, 50, 201, 199),
                    TB.background_rect("contain", 100, 50, 201, 199),
                    TB.background_rect("cover", 100, 50, 33, 900))),
      str(TB.background_rect("contain", 100, 50, 201, 199)))
check("§1 an unusable size answers None (there is nothing to draw)",
      all(TB.background_rect(mode, iw, ih, w, h) is None
          for mode in TB.BACKGROUND_MODES
          for iw, ih, w, h in ((0, 10, 10, 10), (10, 0, 10, 10), (10, 10, 0, 10),
                               (10, 10, 10, 0), (-4, 10, 10, 10), ("a", 10, 10, 10),
                               (None, None, None, None))))

check("§1 the gate answers the OFF state as an ANSWER, not an error",
      TB.inspect_background("") == (False, "", "")
      and TB.inspect_background(None) == (False, "", "") == TB.inspect_background(7),
      str(TB.inspect_background("")))
_ok, _code, _resolved = TB.inspect_background(RED)
check("§1 a real file passes the gate with its RESOLVED absolute path",
      _ok and _code == "" and os.path.isabs(_resolved) and os.path.isfile(_resolved), _resolved)
check("§1 a path that is not a file is MISSING (the canvas logs its own ONE line)",
      TB.inspect_background(MISSING)[0] is False
      and TB.inspect_background(MISSING)[1] == TB.BACKGROUND_ERROR_MISSING
      and TB.inspect_background(PICS)[1] == TB.BACKGROUND_ERROR_MISSING,
      str(TB.inspect_background(MISSING)))
check("§1 `~` is expanded by the ONE resolver (the gate reads the same path the decoder does)",
      TB.inspect_background("~/.sshmap/../.sshmap")[1] == TB.BACKGROUND_ERROR_MISSING
      and "~" not in TB.inspect_background("~/pics/room.png")[2],
      TB.inspect_background("~/pics/room.png")[2])


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the reader: the three keys and the defaults of a broken config ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 an empty config answers the declared defaults (the wallpaper is OFF)",
      TB.load_background_settings({}) == {"path": "", "mode": "cover", "opacity": 35},
      str(TB.load_background_settings({})))
check("§2 the three keys are read and validated (a mode case/space folded, an opacity clamped)",
      TB.load_background_settings({"terminal_background": " ~/pics/room.png ",
                                   "terminal_background_mode": " TILE ",
                                   "terminal_background_opacity": 70})
      == {"path": "~/pics/room.png", "mode": "tile", "opacity": 70},
      str(TB.load_background_settings({"terminal_background": " ~/pics/room.png ",
                                       "terminal_background_mode": " TILE ",
                                       "terminal_background_opacity": 70})))
check("§2 a broken key is its DEFAULT, one by one (a foreign type never reaches the canvas)",
      TB.load_background_settings({"terminal_background": 5,
                                   "terminal_background_mode": ["tile"],
                                   "terminal_background_opacity": "loud"})
      == {"path": "", "mode": "cover", "opacity": 35},
      str(TB.load_background_settings({"terminal_background": 5})))
check("§2 a non-mapping config store answers the defaults instead of raising",
      all(TB.load_background_settings(store)["path"] == ""
          for store in ([], "config", 3))
      and TB.load_background_settings(None)["mode"] == TB.BACKGROUND_MODE_DEFAULT)

clear_cfg()
check("§2 without a config the shipped reader answers the OFF state",
      ST.load_terminal_settings()["background"] == ""
      and ST.load_terminal_settings()["background_mode"] == "cover"
      and ST.load_terminal_settings()["background_opacity"] == 35,
      str(ST.load_terminal_settings()["background"]))
write_cfg({"terminal_background": RED, "terminal_background_mode": "contain",
           "terminal_background_opacity": 64})
_settings = ST.load_terminal_settings()
check("§2 `load_terminal_settings()` carries the three keys (the ONE reader of the family)",
      _settings["background"] == RED and _settings["background_mode"] == "contain"
      and _settings["background_opacity"] == 64,
      f"{_settings['background']} / {_settings['background_mode']} / "
      f"{_settings['background_opacity']}")
check("§2 ...and the display mode is NOT overwritten by the wallpaper's own `mode`",
      _settings["mode"] == "windows", _settings["mode"])
clear_cfg()


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the canvas: the composite, its geometry and the bad file ==")
# ════════════════════════════════════════════════════════════════════════════

_plain = canvas()
check("§3 a canvas without a wallpaper has NO composite (the paint path is the shipped one)",
      _plain.background_state() == {"path": "", "mode": "cover", "opacity": 35}
      and _plain._background_layer() is None, str(_plain.background_state()))

_cover_w = canvas()
_cover_w.set_background_image(RED, mode="cover", opacity=100)
check("§3 cover: EVERY pixel the cells leave alone is the image's own colour",
      bg_colour_of(_cover_w, ((100, 40), (150, 50), (10, 40))) == ["#ff0000"] * 3,
      str(bg_colour_of(_cover_w, ((100, 40), (150, 50), (10, 40)))))
_contain_w = canvas()
_contain_w.set_background_image(RED, mode="contain", opacity=100)
check("§3 contain: the image sits in the middle and the BASE COLOUR shows around it",
      pixel(shot(_contain_w), 2, 2) == DEFAULT_BG
      and pixel(shot(_contain_w), 100, 30) == "#ff0000",
      f"{pixel(shot(_contain_w), 2, 2)} / {pixel(shot(_contain_w), 100, 30)}")
_tile_w = canvas()
_tile_w.set_background_image(RED, mode="tile", opacity=100)
check("§3 tile: the image repeats from the top-left corner (a 64×32 png on a 200×60 canvas)",
      pixel(shot(_tile_w), 5, 5) == "#ff0000"
      and pixel(shot(_tile_w), 70, 5) == "#ff0000"
      and pixel(shot(_tile_w), 5, 40) == "#ff0000", pixel(shot(_tile_w), 70, 5))

_half = canvas()
_half.set_background_image(RED, mode="cover", opacity=50)
_half_px = QColor(pixel(shot(_half), 100, 40))
_base = QColor(DEFAULT_BG)
_expected = [(0.5 * 255 + 0.5 * _base.red()), (0.5 * 0.0 + 0.5 * _base.green()),
             (0.5 * 0.0 + 0.5 * _base.blue())]
check("§3 the opacity is a REAL blend onto the palette's default background (50 % of red)",
      abs(_half_px.red() - _expected[0]) <= 2
      and abs(_half_px.green() - _expected[1]) <= 2
      and abs(_half_px.blue() - _expected[2]) <= 2,
      f"{_half_px.name()} vs {[round(v) for v in _expected]}")
_zero = canvas()
_zero.set_background_image(RED, mode="cover", opacity=0)
check("§3 opacity 0 paints NOTHING but keeps the image loaded (the OFF-without-clearing state)",
      pixel(shot(_zero), 100, 40) == DEFAULT_BG
      and _zero.background_state()["path"] == RED
      and _zero._background_source() is not None,
      f"{pixel(shot(_zero), 100, 40)} / {_zero.background_state()['path']}")

check("§3 a missing file is the EMPTY background (the canvas still paints)",
      (lambda w: (w.set_background_image(MISSING), w._background_layer() is None,
                  pixel(shot(w), 100, 40) == DEFAULT_BG)[1:])(canvas())
      == (True, True), "the missing-file canvas")
check("§3 a NON-IMAGE file is the same empty background, not a traceback",
      (lambda w: (w.set_background_image(NOT_AN_IMAGE), w._background_layer() is None)[1])(canvas()))

# ONE log line: the decode is cached per PATH, so a second paint never repeats the warning
_log_records = []


class _Sink(logging.Handler):
    def emit(self, record):
        _log_records.append(record)


_sink = _Sink(level=logging.WARNING)
_logger = logging.getLogger("sshmap")     # the canvas logs under `sshmap.modules.terminal_widget`
_logger.addHandler(_sink)
try:
    _bad = canvas()
    _bad.set_background_image(MISSING)
    shot(_bad)
    shot(_bad)
    _bad._background_layer()
    _bad_paints = sum(1 for r in _log_records
                      if r.levelno >= logging.WARNING and TB.BACKGROUND_ERROR_MISSING in r.getMessage())
    _log_records.clear()
    _bad2 = canvas()
    _bad2.set_background_image(NOT_AN_IMAGE)
    shot(_bad2)
    shot(_bad2)
    _not_image = sum(1 for r in _log_records
                     if r.levelno >= logging.WARNING
                     and TB.BACKGROUND_ERROR_NOT_IMAGE in r.getMessage())
finally:
    _logger.removeHandler(_sink)
check("§3 a missing file is ONE log line however often the canvas repaints",
      _bad_paints == 1, str(_bad_paints))
check("§3 ...and a non-image file names its own code once",
      _not_image == 1, str(_not_image))

_resize_w = canvas()
_resize_w.show()          # a hidden widget's resize event is only POSTED — show it to deliver it
app.processEvents()
_resize_w.set_background_image(RED, mode="cover", opacity=100)
shot(_resize_w)
_first = _resize_w._bg_layer[0]
_resize_w.resize(320, 90)
app.processEvents()
check("§3 a resize REBUILDS the composite (the new geometry covers the new canvas)",
      _resize_w._bg_layer is not None
      and _resize_w._bg_layer[0][1:3] == (320, 90)
      and pixel(shot(_resize_w), 300, 80) == "#ff0000",
      str(_resize_w._bg_layer[0] if _resize_w._bg_layer else None))
from PySide6.QtGui import QResizeEvent  # noqa: E402 — one synthetic event, the mechanism's own seam

_resize_w._bg_layer = (_first, None)       # a sheet of the PREVIOUS frame
_resize_w.resizeEvent(QResizeEvent(_resize_w.size(), _resize_w.size()))
check("§3 ...and `resizeEvent()` itself drops the cached sheet (it is the SIZE of the canvas)",
      _resize_w._bg_layer is None, str(_resize_w._bg_layer))
shot(_resize_w)
_second = _resize_w._bg_layer[0]
check("§3 ...and the new composite is keyed by the new SIZE",
      _first != _second and _second[1:3] == (320, 90)
      and pixel(shot(_resize_w), 300, 80) == "#ff0000", str(_second))
check("§3 the composite is not rebuilt while nothing changed (ONE sheet per frame)",
      _resize_w._background_layer() is _resize_w._background_layer(),
      "identity")

_palette_w = canvas()
_palette_w.set_background_image(RED, mode="cover", opacity=0)
shot(_palette_w)
check("§3 the base the composite blends onto is the PALETTE's default background",
      pixel(shot(_palette_w), 100, 40) == DEFAULT_BG)
_palette_w.set_palette("nord")
check("§3 a palette change drops the composite and re-blends onto the NEW base",
      _palette_w._bg_layer is None and pixel(shot(_palette_w), 100, 40) == NORD_BG,
      f"{_palette_w._bg_layer} / {pixel(shot(_palette_w), 100, 40)}")

_opacity_w = canvas()
_opacity_w.set_background_image(RED, mode="cover", opacity=100)
shot(_opacity_w)
_source_before = _opacity_w._background_source()
_opacity_w.set_background_opacity(20)
check("§3 a new opacity keeps the DECODED image (the file is read once per path)",
      _opacity_w._background_source() is _source_before and _opacity_w._bg_layer is None,
      "the decode cache")
_opacity_w.set_background_image(BLUE, mode="cover", opacity=20)
check("§3 a new PATH drops the decode too",
      _opacity_w._background_source() is not _source_before
      and pixel(shot(_opacity_w), 100, 40).startswith("#0"),
      pixel(shot(_opacity_w), 100, 40))
_opacity_w.clear_background()
check("§3 `clear_background()` is the OFF state (path, decode and composite together)",
      _opacity_w.background_state()["path"] == ""
      and _opacity_w._background_layer() is None
      and _opacity_w._bg_source is None
      and pixel(shot(_opacity_w), 100, 40) == DEFAULT_BG,
      str(_opacity_w.background_state()))
check("§3 the three setters validate their own argument (the resolver is the ONE rule)",
      _opacity_w.set_background_mode("stretch") == "cover"
      and _opacity_w.set_background_opacity("loud") == TB.BACKGROUND_OPACITY_DEFAULT
      and _opacity_w.set_background_image(None) == "",
      str(_opacity_w.background_state()))

_explicit = canvas()
_explicit.set_background_image(RED, mode="cover", opacity=100)
_explicit.tscreen.feed(b"\x1b[44m" + b"W" * 20 + b"\x1b[0m")
_altered = shot(_explicit)
_cell_w, _cell_h = _explicit.cell_size
check("§3 a cell with an EXPLICIT background stays OPAQUE (a full-screen TUI hides the image)",
      pixel(_altered, _cell_w // 2 + _cell_w, _cell_h // 2) != "#ff0000"
      and pixel(_altered, 2, 4 * _cell_h - 2) == "#ff0000",
      f"{pixel(_altered, _cell_w + 2, _cell_h // 2)} / {pixel(_altered, 2, 4 * _cell_h - 2)}")


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the paint path: the shipped picture while the key is empty ==")
# ════════════════════════════════════════════════════════════════════════════

_reference = canvas()
_reference.tscreen.feed(b"prompt$ ls\r\nfile1  file2\r\n\x1b[32mok\x1b[0m\r\n")
_reference_shots = [shot(_reference), shot(_reference)]
_stats_reference = dict(_reference.last_paint_stats)
_missing_w = canvas(background_path=MISSING)
_missing_w.tscreen.feed(b"prompt$ ls\r\nfile1  file2\r\n\x1b[32mok\x1b[0m\r\n")
check("§4 an empty key and a broken key paint the SAME picture (a missing file changes nothing)",
      _reference_shots[-1] == shot(_missing_w)
      and _missing_w.last_paint_stats == _stats_reference,
      f"{_missing_w.last_paint_stats} vs {_stats_reference}")
check("§4 ...and the stats of the shipped suite are the shipped numbers (rows/runs/draw_text_calls)",
      _stats_reference["rows"] == 4 and _stats_reference["draw_text_calls"] >= 20
      and set(_stats_reference) == {"rows", "runs", "draw_text_calls", "selection_cells"},
      str(_stats_reference))
check("§4 two paints of the same empty canvas are byte-identical (no hidden state)",
      _reference_shots[0] == _reference_shots[1])
check("§4 a canvas constructed WITH the wallpaper keys holds them from the start",
      canvas(background_path=RED, background_mode="tile", background_opacity=12)
      .background_state() == {"path": RED, "mode": "tile", "opacity": 12},
      str(canvas(background_path=RED).background_state()))


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the settings hub: the row, collect() and the eight strings ==")
# ════════════════════════════════════════════════════════════════════════════

NEW_KEYS = (
    "settings.terminal.background",
    "settings.terminal.background.browse",
    "settings.terminal.background.clear",
    "settings.terminal.background.mode",
    "settings.terminal.background.mode.cover",
    "settings.terminal.background.mode.contain",
    "settings.terminal.background.mode.tile",
    "settings.terminal.background.opacity",
)
_missing_keys = [key for key in NEW_KEYS
                 if any(not str(LANGS[code].get(key, "")).strip() for code in ("en", "de", "ru", "zh"))]
check("§5 the EIGHT wallpaper strings are in every language file",
      not _missing_keys and len(NEW_KEYS) == 8, str(_missing_keys))
check_i18n_parity(LANGS)
check_i18n_format(LANGS)

clear_cfg()
_hub = SD.SettingsDialog(None)
_row_widgets = [getattr(_hub, name, None) for name in
                ("background_edit", "background_browse_btn", "background_clear_btn",
                 "background_mode_combo", "background_opacity_slider", "background_opacity_spin")]
check("§5 the 'Terminal' tab carries the wallpaper row (a field, two buttons, a combo, a slider)",
      all(widget is not None for widget in _row_widgets), str(_row_widgets))
check("§5 the mode combo offers exactly the three declared values",
      [_hub.background_mode_combo.itemData(i) for i in range(_hub.background_mode_combo.count())]
      == list(TB.BACKGROUND_MODES), str([_hub.background_mode_combo.itemData(i)
                                         for i in range(_hub.background_mode_combo.count())]))
check("§5 the opacity row is ONE number in two views (0..100, the reader's range)",
      (_hub.background_opacity_slider.minimum(), _hub.background_opacity_slider.maximum()) == (0, 100)
      and (_hub.background_opacity_spin.minimum(), _hub.background_opacity_spin.maximum()) == (0, 100))
_collected = _hub.collect()
check("§5 collect() carries the three keys beside the hub's other 27 (30 UI-facing keys)",
      len(_collected) == 30
      and _collected["terminal_background"] == ""
      and _collected["terminal_background_mode"] == "cover"
      and _collected["terminal_background_opacity"] == 35,
      str(sorted(_collected)))
_hub.close()

write_cfg({"terminal_background": RED, "terminal_background_mode": "tile",
           "terminal_background_opacity": 21})
_hub2 = SD.SettingsDialog(None)
check("§5 the row is PREFILLED from the config",
      _hub2.background_edit.text() == RED
      and _hub2.background_mode_combo.currentData() == "tile"
      and _hub2.background_opacity_spin.value() == 21
      and _hub2.background_opacity_slider.value() == 21,
      f"{_hub2.background_edit.text()} / {_hub2.background_mode_combo.currentData()} / "
      f"{_hub2.background_opacity_spin.value()}")
_hub2.background_opacity_slider.setValue(64)
check("§5 the slider writes the box (the mirror is bidirectional and never loops)",
      _hub2.background_opacity_spin.value() == 64)
_hub2.background_opacity_spin.setValue(12)
check("§5 ...and the box writes the slider", _hub2.background_opacity_slider.value() == 12)
_hub2.background_edit.setText("  ~/pics/room.png  ")
check("§5 the field is stored TRIMMED (collect() is the ONE writer of the key)",
      _hub2.collect()["terminal_background"] == "~/pics/room.png"
      and _hub2.collect()["terminal_background_opacity"] == 12,
      _hub2.collect()["terminal_background"])


class _PickFile:
    """The `QFileDialog` seam: the SAME monkeypatch the other dialog tests use."""
    picked = RED + ".picked"

    @staticmethod
    def getOpenFileName(*_args, **_kwargs):
        return (_PickFile.picked, "")


_real_file_dialog = SD.QFileDialog
SD.QFileDialog = _PickFile
try:
    _hub2.background_edit.clear()
    _hub2._on_browse_background()
finally:
    SD.QFileDialog = _real_file_dialog
check("§5 `Browse…` writes the picked path into the field and nothing else",
      _hub2.background_edit.text() == _PickFile.picked
      and _hub2.collect()["terminal_background"] == _PickFile.picked,
      _hub2.background_edit.text())
_hub2._on_clear_background()
check("§5 `Clear` is the OFF state of the field (the key becomes \"\")",
      _hub2.background_edit.text() == "" and _hub2.collect()["terminal_background"] == "")

i18n.set_language("en")
_hub2.retranslate()
check("§5 the row re-texts itself with the rest of the tab (EN labels)",
      _hub2._lbl_background.text() == LANGS["en"]["settings.terminal.background"]
      and _hub2.background_browse_btn.text() == LANGS["en"]["settings.terminal.background.browse"]
      and _hub2.background_clear_btn.text() == LANGS["en"]["settings.terminal.background.clear"]
      and _hub2.background_mode_combo.itemText(2)
      == LANGS["en"]["settings.terminal.background.mode.tile"],
      _hub2._lbl_background.text())
_hub2.close()
clear_cfg()


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the session reads the keys and the hub re-applies them to the OPEN ones ==")
# ════════════════════════════════════════════════════════════════════════════

from models.server import ServerData  # noqa: E402

_orig_thread_cls = ST.SSHTerminalThread
ST.SSHTerminalThread = FakeSSHThread
from modules.terminal_page import TerminalSessionPage  # noqa: E402

try:
    write_cfg({"terminal_background": RED, "terminal_background_mode": "contain",
               "terminal_background_opacity": 40})
    _page = TerminalSessionPage(ServerData(id="wall-1", alias="wall", host="10.99.0.9",
                                           user="root"), None)
    check("§6 a NEW session takes the wallpaper from the config (read at creation)",
          _page.widget.background_state()
          == {"path": RED, "mode": "contain", "opacity": 40},
          str(_page.widget.background_state()))
    _page.shutdown()

    clear_cfg()
    _page2 = TerminalSessionPage(ServerData(id="wall-2", alias="wall2", host="10.99.0.9",
                                            user="root"), None)
    check("§6 the next session takes the NEW answer (no restart)",
          _page2.widget.background_state()["path"] == "", str(_page2.widget.background_state()))
    _page2.shutdown()

    import ui.main_window as MW

    write_cfg({"terminal_background": RED, "terminal_background_mode": "tile",
               "terminal_background_opacity": 55})
    _win = MW.MainWindow()
    _win.show()
    app.processEvents()

    class _FakeContainer:
        def __init__(self):
            self.widget = canvas()

    _container = _FakeContainer()
    _win._terminal_windows.append(_container)
    _win._apply_settings_from_dialog()
    check("§6 the hub's OK re-applies all three keys to the ALREADY OPEN sessions",
          _container.widget.background_state()
          == {"path": RED, "mode": "tile", "opacity": 55},
          str(_container.widget.background_state()))

    write_cfg({"terminal_background": "", "terminal_background_mode": "tile",
               "terminal_background_opacity": 55})
    _win._apply_settings_from_dialog()
    check("§6 ...and a cleared field takes the picture away from them",
          _container.widget.background_state()["path"] == ""
          and _container.widget._background_layer() is None,
          str(_container.widget.background_state()))
    _win._terminal_windows.clear()
    _win._dirty = False
    _win._undo_baseline_dirty = False
    _win.close()
finally:
    ST.SSHTerminalThread = _orig_thread_cls
    clear_cfg()


# ════════════════════════════════════════════════════════════════════════════
print("== §7 the release ==")
# ════════════════════════════════════════════════════════════════════════════

from version import APP_VERSION, VERSION_FORMAT  # noqa: E402

check("§7 the shipped version is the one the pin names",
      APP_VERSION == EXPECTED_APP_VERSION and releases_at_least(APP_VERSION, "1.13.2"),
      APP_VERSION)
check("§7 the wallpaper moves no JSON schema (the keys live in config.json, not in the project)",
      VERSION_FORMAT == "0.9", VERSION_FORMAT)
check_release_state(ROOT)
check(f"§7 the i18n pin carries the eight wallpaper keys ({EXPECTED_I18N_KEYS} = 1127 + 8 + the later keys)",
      EXPECTED_I18N_KEYS == 1162 + 4 + 13 + 1 + 1 + 12 + 3, str(EXPECTED_I18N_KEYS))

finish()
