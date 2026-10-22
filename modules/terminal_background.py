# -*- coding: utf-8 -*-
"""The terminal wallpaper — the three `terminal_background*` keys and the PURE geometry they feed.

ONE home for the wallpaper's declared facts: the accepted MODES (`cover` / `contain` / `tile`), the
opacity range, the three config keys, the validation of every value (`resolve_background_mode()` /
`resolve_background_opacity()` / `normalize_background_path()`), the path gate (`inspect_background()`)
and the geometry of ONE copy of the image (`background_rect()`). No Qt and no widget: the canvas
(`modules/terminal_widget.py`) decodes, blends and caches the composite, this module only says WHERE
the image goes. `load_background_settings()` is the ONE reader `modules/terminal_config.py` calls; a
broken config answers the DECLARED defaults and never raises (`AGENTS.md` §4.3, `DOCUMENTATION.md` §78).
"""

import os

try:  # v1.14.1.1: the ONE finite-number gate of a stored config value (`models/server.py`)
    from ..models.server import finite_number
except ImportError:  # flat launch from the project root
    from models.server import finite_number  # type: ignore

BACKGROUND_MODE_COVER = "cover"       # the whole canvas — the image is scaled up and cropped
BACKGROUND_MODE_CONTAIN = "contain"   # the whole image — scaled down, the canvas shows around it
BACKGROUND_MODE_TILE = "tile"         # the native size, repeated from the top-left corner

#: The accepted values of `terminal_background_mode`, the DEFAULT first.
BACKGROUND_MODES = (BACKGROUND_MODE_COVER, BACKGROUND_MODE_CONTAIN, BACKGROUND_MODE_TILE)
BACKGROUND_MODE_DEFAULT = BACKGROUND_MODE_COVER

#: The opacity range of the image: the composite is pre-blended onto the palette's default background,
#: so `0` paints nothing (the image stays loaded) and `100` is the image at full strength. The default
#: is deliberately LOW: a wallpaper sits under the text, and a readable prompt outranks decoration.
BACKGROUND_OPACITY_MIN = 0
BACKGROUND_OPACITY_MAX = 100
BACKGROUND_OPACITY_DEFAULT = 35

#: The three `~/.sshmap/config.json` keys — a PATH, a mode and a percentage (all optional).
BACKGROUND_CONFIG_KEY = "terminal_background"
BACKGROUND_MODE_CONFIG_KEY = "terminal_background_mode"
BACKGROUND_OPACITY_CONFIG_KEY = "terminal_background_opacity"

#: The machine codes of a path this program cannot use (the canvas logs ONE line per code).
BACKGROUND_ERROR_MISSING = "missing"
BACKGROUND_ERROR_UNREADABLE = "unreadable"
BACKGROUND_ERROR_NOT_IMAGE = "not_image"


def resolve_background_mode(value) -> str:
    """The `terminal_background_mode` value → one of `BACKGROUND_MODES`. PURE.

    The `resolve_cursor_style()` rule: a missing, empty, unknown or non-string value answers the
    DECLARED default, so a broken config can never disable the wallpaper's geometry.
    """
    if isinstance(value, str) and value.strip().lower() in BACKGROUND_MODES:
        return value.strip().lower()
    return BACKGROUND_MODE_DEFAULT


def resolve_background_opacity(value) -> int:
    """The `terminal_background_opacity` value → an int inside `BACKGROUND_OPACITY_MIN..MAX`. PURE.

    A JSON number is CLAMPED (a hand-edited `150` is the strongest image, not a defect); a float
    rounds to the nearest whole percent; a bool, a string, a null, a NaN and ±inf — the ONE
    `finite_number()` gate, v1.14.1.1 — answer the DEFAULT, the same foreign-type rule every
    `terminal_*` reader follows. A `1e999` in the config never raises here.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return BACKGROUND_OPACITY_DEFAULT
    number = finite_number(value)
    if number is None:                # a float subclass, a NaN or ±inf
        return BACKGROUND_OPACITY_DEFAULT
    return max(BACKGROUND_OPACITY_MIN, min(BACKGROUND_OPACITY_MAX, int(round(number))))


def normalize_background_path(value) -> str:
    """The `terminal_background` value as the canvas stores it — the TYPED text, trimmed. PURE.

    The path is deliberately NOT resolved here: the field shows what the user wrote, and the
    resolution (`~`, a relative path) belongs to the ONE opener (`inspect_background()`), so a saved
    `~/pics/room.png` comes back as exactly that string. A non-string and an empty value answer `""`
    — the OFF state of a shipped default.
    """
    if not isinstance(value, str):
        return ""
    return value.strip()


def background_is_tiled(mode) -> bool:
    """Whether the mode REPEATS the image (the tile branch of the canvas). PURE."""
    return resolve_background_mode(mode) == BACKGROUND_MODE_TILE


def background_rect(mode, img_w, img_h, width, height):
    """The `(x, y, w, h)` rect ONE copy of an `img_w × img_h` image is drawn in. PURE.

    `cover` fills the target and is CROPPED (the aspect ratio is kept, the overflow is centred out);
    `contain` fits inside and leaves the canvas around it (the composite's own base colour shows
    there); `tile` keeps the NATIVE size at the top-left corner, cut at the canvas — the repetition is
    the caller's, and this is the rect of ONE copy (a copy bigger than the canvas is the one tile a
    canvas can show). Any unusable size (zero, negative, non-numeric) answers `None`: there is nothing
    to draw, which is the empty background the canvas already falls back to.
    """
    try:
        img_w, img_h = int(img_w), int(img_h)
        width, height = int(width), int(height)
    except (TypeError, ValueError):
        return None
    if img_w <= 0 or img_h <= 0 or width <= 0 or height <= 0:
        return None
    if background_is_tiled(mode):
        return (0, 0, min(img_w, width), min(img_h, height))
    if resolve_background_mode(mode) == BACKGROUND_MODE_COVER:
        scale = max(width / img_w, height / img_h)
    else:
        scale = min(width / img_w, height / img_h)
    draw_w = max(1, int(round(img_w * scale)))
    draw_h = max(1, int(round(img_h * scale)))
    return ((width - draw_w) // 2, (height - draw_h) // 2, draw_w, draw_h)


def inspect_background(path):
    """`(ok, code, resolved)` — the PATH gate of the wallpaper, Qt-free. PURE apart from the `os` calls.

    `resolved` is the OS path the decoder is handed (`modules/local_paths.resolve_local_path()`, the
    ONE resolver of `~` and of a relative path). A good answer is `(True, "", resolved)`; an EMPTY
    path is the OFF state — `(False, "", "")`, an answer and not an error; a path that is not a file
    is `BACKGROUND_ERROR_MISSING` and one that cannot be read is `BACKGROUND_ERROR_UNREADABLE`.
    Whether the bytes ARE an image needs a decoder, and the canvas answers that with
    `BACKGROUND_ERROR_NOT_IMAGE`.
    """
    try:
        from .local_paths import resolve_local_path
    except ImportError:   # a flat launch from the project root
        from modules.local_paths import resolve_local_path
    try:
        resolved = resolve_local_path(normalize_background_path(path))
    except Exception:   # noqa: BLE001 — a __str__ that raises is not a path
        return (False, BACKGROUND_ERROR_UNREADABLE, "")
    if not resolved:
        return (False, "", "")
    try:
        if not os.path.isfile(resolved):
            return (False, BACKGROUND_ERROR_MISSING, resolved)
        with open(resolved, "rb") as fh:      # "readable" is decided by the OS, not by the suffix
            fh.read(1)
    except OSError:
        return (False, BACKGROUND_ERROR_UNREADABLE, resolved)
    return (True, "", resolved)


def load_background_settings(cfg=None):
    """The wallpaper of `~/.sshmap/config.json` — `{"path": str, "mode": str, "opacity": int}`.

    The `load_split_settings()` shape: every key is optional, a foreign value answers the DECLARED
    default, and a config store that cannot be read answers the defaults too — a broken file must
    never keep a session from opening. `cfg` is a mapping to read (defaults to `i18n.load_config()`).
    Never raises.
    """
    defaults = {"path": "", "mode": BACKGROUND_MODE_DEFAULT,
                "opacity": BACKGROUND_OPACITY_DEFAULT}
    if cfg is None:
        try:
            from i18n import load_config
        except Exception:   # noqa: BLE001 — a build without i18n keeps the defaults
            return dict(defaults)
        try:
            cfg = load_config()
        except Exception:   # noqa: BLE001 — a broken config store must not break a session
            return dict(defaults)
    if not isinstance(cfg, dict):
        return dict(defaults)
    defaults["path"] = normalize_background_path(cfg.get(BACKGROUND_CONFIG_KEY))
    defaults["mode"] = resolve_background_mode(cfg.get(BACKGROUND_MODE_CONFIG_KEY))
    defaults["opacity"] = resolve_background_opacity(cfg.get(BACKGROUND_OPACITY_CONFIG_KEY))
    return defaults
