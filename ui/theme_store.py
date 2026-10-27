# -*- coding: utf-8 -*-
"""The theme PACK store — the schema, the discovery, the guard and the load-time contrast gate.

A pack is a JSON FILE of declared overrides over ONE base mode, never a code copy: `themes/<id>.json`
ships with the package and `~/.sshmap/themes/<id>.json` shadows it by id (the i18n precedent). The FILE
NAME is the id; `"name"` is the display string (DATA, not an i18n key). `colors` is PARTIAL — a missing
field inherits the base mode — and the GUARD is the schema's allowlist: a field outside it refuses the
whole file, so a typo is a defect and never a silent skip. Every accepted pack is resolved and run
through `ui/theme_contrast.py`: a theme that cannot be read is not a theme.

No Qt. `ui/theme.py` stays the RESOLUTION owner (`PACKS`, `theme_for_mode(..., pack=…)`).
Mechanism — `DOCUMENTATION.md`, "Central UI theme"; the rule — `AGENTS.md` §4.6."""

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:  # the base instances and the field vocabulary (pure data — no Qt either way)
    from . import theme
    from . import theme_contrast
except ImportError:  # flat launch from the project root
    from ui import theme
    from ui import theme_contrast

# ── The schema ────────────────────────────────────────────────────────────────
PACK_VERSION = 1                      # the ONLY schema this build applies
MAX_PACK_BYTES = 64 * 1024            # a theme is a few hundred bytes; a big file is not a theme
PACK_DIRNAME = "themes"
PACK_SUFFIX = ".json"
PACK_BASES = (theme.MODE_DARK, theme.MODE_LIGHT)
PACK_ROOT_KEYS = ("name", "base", "version", "accent_hue", "colors", "terminal_palette")

# The GUARD: what a pack MAY touch — the surfaces, the two text tones and the icon outline, the card,
# the groups, the arrows, the notes and the eight syntax roles. Everything else is refused BY NAME.
ALLOWED_COLORS = (
    "canvas_bg", "render_bg", "window_bg", "base_bg", "surface_alt",
    "text_primary", "text_muted", "icon_color",
    "node_bg", "node_border", "node_hover", "node_icon_bg", "node_text", "node_label", "dot_idle",
    "group_border", "group_hover", "group_title", "group_title_selected", "group_title_hover",
    "arrow_ssh", "arrow_http", "arrow_nfs", "arrow_kubernetes", "arrow_hover_compat",
    "note_bg", "note_border", "note_text",
    "syntax_number", "syntax_string", "syntax_key", "syntax_keyword", "syntax_comment",
    "syntax_tag", "syntax_attribute", "syntax_punctuation",
)

# The LOCKED fields, refused with the reason the report quotes: the product's MEANING (the status trio,
# the selection, the semantic tag strip), the six derived accent tones (a pack declares `accent_hue`),
# the user's note tone, and the geometry (radii, fonts — a font moves the card metrics).
LOCKED_COLORS = {
    "status_online": "the status trio keeps the base values",
    "status_warn": "the status trio keeps the base values",
    "status_offline": "the status trio keeps the base values",
    "selection_amber": "the selection keeps the base value",
    "tag_test": "the semantic tag strip keeps the base values",
    "tag_backup": "the semantic tag strip keeps the base values",
    "tag_dmz": "the semantic tag strip keeps the base values",
    "tag_pink": "the semantic tag strip keeps the base values",
    "accent": "the accent family is DERIVED — declare `accent_hue` instead",
    "accent_hover": "the accent family is DERIVED — declare `accent_hue` instead",
    "accent_selected": "the accent family is DERIVED — declare `accent_hue` instead",
    "accent_strong": "the accent family is DERIVED — declare `accent_hue` instead",
    "accent_strong_hover": "the accent family is DERIVED — declare `accent_hue` instead",
    "accent_strong_selected": "the accent family is DERIVED — declare `accent_hue` instead",
    "accent_hue": "a HUE is a root key, not a colour",
    "note_tone": "the note tone is the user's choice",
    "radius_node": "geometry belongs to the base theme",
    "radius_note": "geometry belongs to the base theme",
    "radius_group": "geometry belongs to the base theme",
    "radius_search_bar": "geometry belongs to the base theme",
    "radius_arrow_label": "geometry belongs to the base theme",
    "radius_resize_mark": "geometry belongs to the base theme",
    "radius_node_glyph_unit": "geometry belongs to the base theme",
    "font_ui": "a font belongs to the base theme (it moves the card metrics)",
    "font_mono": "a font belongs to the base theme (it moves the card metrics)",
}

# The REASON codes of a skipped file — machine values; the Settings row picks its sentence by the code
# and quotes `detail`. `contrast` is the one code that names the FAILING PAIRS, never a field.
REASON_UNREADABLE = "unreadable"
REASON_TOO_BIG = "too_big"
REASON_NOT_JSON = "not_json"
REASON_NOT_OBJECT = "not_object"
REASON_UNKNOWN_KEY = "unknown_key"
REASON_BAD_VERSION = "bad_version"
REASON_BAD_BASE = "bad_base"
REASON_NO_NAME = "no_name"
REASON_BAD_COLOR = "bad_color"
REASON_BAD_ACCENT = "bad_accent"
REASON_BAD_PALETTE = "bad_palette"
REASON_CONTRAST = "contrast"
REASONS = (REASON_UNREADABLE, REASON_TOO_BIG, REASON_NOT_JSON, REASON_NOT_OBJECT,
           REASON_UNKNOWN_KEY, REASON_BAD_VERSION, REASON_BAD_BASE, REASON_NO_NAME,
           REASON_BAD_COLOR, REASON_BAD_ACCENT, REASON_BAD_PALETTE, REASON_CONTRAST)


try:  # the application's own logger when the tree is importable (a bare script has none)
    from modules.logger import get_logger as _get_logger
except ImportError:  # noqa: BLE001 — optional import: the loader works without the app's logging
    _get_logger = None


def _log(message: str) -> None:
    """ONE line into ~/.sshmap/logs/sshmap.log — skipped by a build without the logger."""
    if _get_logger is not None:
        _get_logger("theme").warning(message)


@dataclass(frozen=True)
class ThemePack:
    """ONE accepted pack: what it declares, where it came from, and its display string."""

    id: str
    name: str
    base: str
    version: int
    colors: Dict[str, str]
    accent_hue: Optional[float] = None
    terminal_palette: Optional[str] = None
    path: str = ""
    builtin: bool = False

    def display(self) -> str:
        """The string the combo shows — the file's own `name`, or its id."""
        return self.name or self.id


@dataclass(frozen=True)
class PackProblem:
    """One SKIPPED file: its id, the file it came from, the REASON code and the named detail."""

    id: str
    path: str
    reason: str
    detail: str

    def sentence(self) -> str:
        """The English form a log line or a test reads (the UI translates its own)."""
        return f"{self.id or os.path.basename(self.path)}: {self.detail}"


# ── The two folders and the id rule ───────────────────────────────────────────

def package_dir(root=None) -> str:
    """The SHIPPED folder (`<root>/themes`) — this file lives in `<root>/ui/`."""
    base = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, PACK_DIRNAME)


def user_dir() -> str:
    """The USER folder `~/.sshmap/themes` — sibling of `languages/`, never created here."""
    return os.path.join(os.path.expanduser("~"), ".sshmap", PACK_DIRNAME)


def ensure_user_dir() -> bool:
    """Create the user folder ON DEMAND (the folder door). True = it exists afterwards."""
    try:
        os.makedirs(user_dir(), exist_ok=True)
        return True
    except OSError:
        return False


def is_safe_pack_id(value) -> bool:
    """Is `value` usable as a FILE NAME (one component, no separators)? — the i18n code rule.

    The id reaches this module from a file name AND from `config.json`, so a hand-edited
    `theme.pack = "../../etc/passwd"` must never become a path.
    """
    if not isinstance(value, str):
        return False
    code = value.strip()
    if not code or code in (".", ".."):
        return False
    if os.path.basename(code) != code:
        return False
    for sep in (os.sep, os.altsep, "/", "\\"):
        if sep and sep in code:
            return False
    return True


def palette_names() -> Tuple[str, ...]:
    """The terminal palette ids a pack may name — the SHIPPED vocabulary, imported lazily.

    `modules/terminal_screen.py` owns `PALETTES`; the import is deferred so this module stays
    importable without the application tree (the readers and the schema are pure data).
    """
    for name in ("modules.terminal_screen", "terminal_screen"):
        try:
            module = __import__(name, fromlist=["PALETTES"])
        except ImportError:
            continue
        return tuple(getattr(module, "PALETTES", {}) or ())
    return ()


# ── The validation ────────────────────────────────────────────────────────────

def _problem(pack_id: str, path: str, reason: str, detail: str) -> PackProblem:
    return PackProblem(id=pack_id, path=path, reason=reason, detail=detail)


def parse_pack(data, pack_id: str, path: str = "", builtin: bool = False
               ) -> Tuple[Optional[ThemePack], List[PackProblem]]:
    """A parsed JSON document → (pack, []) or (None, [ONE problem]) — never half-applied.

    The order is the schema's: the ROOT keys, then `version` (a schema this build does not know is
    refused with the sentence that names it), then `base`, `name`, `colors` field by field, the two
    optional values, and LAST the contrast gate over the resolved instance.
    """
    def bad(reason, detail):
        return None, [_problem(pack_id, path, reason, detail)]

    if not isinstance(data, dict):
        return bad(REASON_NOT_OBJECT, "the root is not a JSON object")
    unknown = [key for key in data if key not in PACK_ROOT_KEYS]
    if unknown:
        return bad(REASON_UNKNOWN_KEY, f"unknown key '{unknown[0]}'")
    version = data.get("version")
    if version != PACK_VERSION or isinstance(version, bool):
        return bad(REASON_BAD_VERSION,
                   f"version {version!r} is not this build's schema ({PACK_VERSION})")
    base = data.get("base")
    if base not in PACK_BASES:
        return bad(REASON_BAD_BASE, f"base {base!r} is not one of {PACK_BASES}")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return bad(REASON_NO_NAME, "the 'name' key is missing or empty")
    colors = data.get("colors")
    if colors is None:
        colors = {}
    if not isinstance(colors, dict):
        return bad(REASON_UNKNOWN_KEY, "the 'colors' key is not an object")
    resolved: Dict[str, str] = {}
    for field, value in colors.items():
        if field in LOCKED_COLORS:
            return bad(REASON_UNKNOWN_KEY, f"'{field}' is locked — {LOCKED_COLORS[field]}")
        if field not in ALLOWED_COLORS:
            return bad(REASON_UNKNOWN_KEY, f"'{field}' is not a field a theme pack may set")
        if not theme.is_valid_hex(value):
            return bad(REASON_BAD_COLOR, f"'{field}' is not a #rrggbb colour ({value!r})")
        resolved[field] = "#" + value.strip().lstrip("#").lower()
    hue = None
    if "accent_hue" in data:
        raw = data["accent_hue"]
        hue = (theme.hex_hue(raw) if theme.is_valid_hex(raw)
               else theme.resolve_accent_hue(raw))    # a HUE number OR a #rrggbb colour
        if hue is None:
            return bad(REASON_BAD_ACCENT, f"accent_hue {raw!r} is not a hue")
    palette = data.get("terminal_palette")
    if palette is not None:
        if not isinstance(palette, str) or palette not in palette_names():
            return bad(REASON_BAD_PALETTE,
                       f"terminal_palette {palette!r} is not one of {palette_names()}")
    pack = ThemePack(id=pack_id, name=name.strip(), base=base, version=PACK_VERSION,
                     colors=resolved, accent_hue=hue, terminal_palette=palette,
                     path=path, builtin=builtin)
    failures = theme_contrast.contrast_problems(theme.theme_for_mode(base, hue, None, pack=pack))
    if failures:
        return bad(REASON_CONTRAST, "; ".join(failures[:4])
                   + (f" (+{len(failures) - 4} more)" if len(failures) > 4 else ""))
    return pack, []


def read_pack(path: str, pack_id: str, builtin: bool = False
              ) -> Tuple[Optional[ThemePack], List[PackProblem]]:
    """One file → (pack, []) or (None, [ONE problem]) — the 64 KB cap is judged BEFORE the parse."""
    try:
        if os.path.getsize(path) > MAX_PACK_BYTES:
            return None, [_problem(pack_id, path, REASON_TOO_BIG,
                                   f"the file is larger than {MAX_PACK_BYTES // 1024} KB")]
        with open(path, "r", encoding="utf-8-sig") as handle:
            text = handle.read(MAX_PACK_BYTES + 1)
    except OSError:
        return None, [_problem(pack_id, path, REASON_UNREADABLE, "the file cannot be read")]
    try:
        data = json.loads(text)
    except ValueError:
        return None, [_problem(pack_id, path, REASON_NOT_JSON, "the file is not JSON")]
    return parse_pack(data, pack_id, path, builtin)


def discover(root=None, user_dir_path=None) -> Tuple[Dict[str, ThemePack], List[PackProblem]]:
    """Both folders → ({id: pack}, [problems]) — the user file SHADOWS the shipped one by id.

    A user file that cannot be applied costs the user NOTHING but its own override: the shipped pack
    of the same id stays in the registry (the i18n fallback), and every skipped file is logged ONCE
    here, so the caller only has to say ONE sentence.
    """
    packs: Dict[str, ThemePack] = {}
    problems: List[PackProblem] = []
    for folder, builtin in ((package_dir(root), True), (user_dir_path or user_dir(), False)):
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(PACK_SUFFIX):
                continue
            pack_id = fname[:-len(PACK_SUFFIX)]
            if not is_safe_pack_id(pack_id):
                continue
            pack, issues = read_pack(os.path.join(folder, fname), pack_id, builtin)
            if pack is None:
                problems.extend(issues)
                continue
            packs[pack_id] = pack
    for problem in problems:
        _log(f"theme pack {problem.sentence()}")
    return packs, problems
