# -*- coding: utf-8 -*-
"""The repository map and the code text: the polish that closes the line (v1.12.4).
§1 the three directory rows of `AGENTS.md` §2 that named nothing, corrected (`N103`) and §4.3.8's
dock paragraph read against the panel's shipped refusal; §2 no widget writes QSS of its own (`N111`
a/b — the QSS home owns the colours and the radius); §3 the two export headers read `APP_NAME` and
the files they write carry it (`N111` c); §4 the two corrected docstrings and the release narration
that left the code text (`N111` d/e/f); §5 the i18n and the release state.
Rule — `AGENTS.md` §2, §4.3.8, §4.6, §4.30; mechanism — `DOCUMENTATION.md` §3, §39, §72.
"""
import ast
import io
import os
import re
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least,
                     translation_keys)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import ui.theme_qss as TQ  # noqa: E402
from graphics.map_scene import MapScene  # noqa: E402
from models.server import ServerData  # noqa: E402
from storage.export_drawio import DrawioExporter  # noqa: E402
from version import APP_NAME, APP_VERSION  # noqa: E402

import _comment_budget as CB  # noqa: E402

LANGS = load_i18n_langs(ROOT)

#: The application's own source (the frozen data paths of `tests/` are no part of these scans).
CODE_DIRS = ("modules", "ui", "graphics", "storage", "services", "models", "dialogs")
CODE_FILES = ("main.py", "version.py")

#: The ONE module allowed to write a colour or a radius into a stylesheet: it IS the QSS home.
QSS_HOME = "ui/theme_qss.py"


def _read(*parts) -> str:
    """The text of one repository file that SHIPS (these audits read the SHIPPED wiring)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _sources():
    """[(repository-relative path, source)] of the application's Python (tests/ aside)."""
    out = []
    for name in CODE_FILES:
        out.append((name, _read(name)))
    for directory in CODE_DIRS:
        for base, dirs, files in os.walk(os.path.join(ROOT, directory)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(files):
                if name.endswith(".py"):
                    path = os.path.join(base, name)
                    out.append((os.path.relpath(path, ROOT).replace("\\", "/"),
                                io.open(path, encoding="utf-8").read()))
    return out


def _style_text(node):
    """A QSS argument as TEXT with every f-string expression folded to a `{…}` placeholder."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_style_text(part) for part in node.values)
    if isinstance(node, ast.FormattedValue):
        return "{…}"
    if isinstance(node, ast.BinOp):        # a "%s" template: both halves are literal text
        return _style_text(node.left) + _style_text(node.right)
    return ""


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the repository map of AGENTS.md §2 (N103) and the dock paragraph (R16) ==")
# ════════════════════════════════════════════════════════════════════════════

_agents = _read("AGENTS.md")
_s2 = _agents[_agents.find("## 2. Repository map"):
              _agents.find("\n## ", _agents.find("## 2. Repository map") + 4)]
check("§1 the section is really there (a guard over nothing is useless)",
      "| Directory/File |" in _s2 and _s2.count("\n|") >= 15, len(_s2))

check("§1 no row declares a directory the tree does not hold (`DOCS/`, `PLUGINS/`, `AUDIT/`)",
      not any(f"`{name}`" in _s2 for name in ("DOCS/", "PLUGINS/", "AUDIT/")),
      [line[:60] for line in _s2.splitlines() if any(n in line for n in ("DOCS/", "PLUGINS/", "AUDIT/"))])
check("§1 the rows name the REAL directories (docs/ is where the published image lives)",
      "`docs/`" in _s2 and os.path.isfile(os.path.join(ROOT, "docs", "map-example.png")))
check("§1 the ROOT documents are named instead (the five internal ones and the public page)",
      all(f"`{name}`" in _s2 for name in (
          "README.md", "AGENTS.md", "DOCUMENTATION.md", "PLUGINS.md", "ROADMAP.md",
          "AUDIT_PENDING.md", "PYTE82_AUDIT.md", "COMMENT_AUDIT.md", "TOOLS.md", "UI_UX_AUDIT.md",
          "PLUGINS_INTERNAL.md", "LOCAL_PANE.md", "SFTP_PANES.md", "ELEVATED_PANE.md",
          "TERMINAL_STANDALONE.md", "CHANGELOG.md")),
      [name for name in ("README.md", "AGENTS.md", "CHANGELOG.md") if f"`{name}`" not in _s2])

_s438 = _agents[_agents.find("#### §4.3.8"):_agents.find("#### §4.3.9")]
check("§1 §4.3.8 reads the shipped refusal: the sentence is a STATUS LINE, the hint the same text",
      "STATUS-LINE sentence" in _s438 and "_notify(_hint_text())" in _s438
      and "INLINE" not in _s438, _s438[:200])
check("§1 §4.3.8 no longer promises `Profiles` ON THE DOCK (the row belongs to `Servers`)",
      "live on the dock too" not in _s438 and "menubar" in _s438)
_panel_src = _read("modules", "command_library.py")
check("§1 ...and the code agrees: the row's visibility IS the head's, the refusal is `_notify`",
      "self.doors_row.setVisible(servers)" in _panel_src
      and "self._notify(self._hint_text())" in _panel_src
      and "set_map_doors(None, self._panel_open_profiles)" in _read("modules", "terminal_dock.py"))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 no widget writes QSS of its own (N111 a/b) ==")
# ════════════════════════════════════════════════════════════════════════════

_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_NAMED_RE = re.compile(r"\b(?:gray|grey|silver|maroon|olive|lime|aqua|teal|navy|fuchsia)\b")
_RADIUS_RE = re.compile(r"border(?:-[a-z]+)?-radius\s*:\s*(?!\{…)")
_offenders, _call_sites = [], 0
for _rel, _source in _sources():
    if _rel == QSS_HOME:
        continue        # the QSS home — the ONE module whose job IS the stylesheet text
    for _node in ast.walk(ast.parse(_source, filename=_rel)):
        if not (isinstance(_node, ast.Call) and isinstance(_node.func, ast.Attribute)
                and _node.func.attr == "setStyleSheet"):
            continue
        _call_sites += 1
        _text = " ".join(_style_text(arg) for arg in _node.args)
        for _pattern, _what in ((_HEX_RE, "a hex colour"), (_NAMED_RE, "a named colour"),
                                (_RADIUS_RE, "a radius literal")):
            if _pattern.search(_text):
                _offenders.append(f"{_rel}:{_node.lineno} writes {_what}: {_text.strip()[:60]}")
check("§2 the scan really reads the call sites (a guard over nothing is useless)",
      _call_sites >= 8, f"setStyleSheet call sites read={_call_sites}")
check("§2 every `setStyleSheet` argument is THEME-owned (no colour, no radius — AGENTS.md §4.6)",
      not _offenders, _offenders[:4])

_swatch = TQ.accent_swatch_style("#38bdf8")
check("§2 the accent chip is a REGISTRY style: the radius is the QSS home's, the fill is the caller's",
      f"border-radius: {TQ.CONTROL_RADIUS_PX}px" in _swatch and "#38bdf8" in _swatch
      and TQ.CONTROL_RADIUS_PX == 4, _swatch)
check("§2 ...and the SELECTED chip frames itself from the theme, never from a second literal",
      TQ.accent_swatch_style("#38bdf8", True).count("border: 2px solid") == 1
      and TQ.accent_swatch_style("#38bdf8", True) != _swatch)
_dialog_src = _read("ui", "settings_dialog.py")
check("§2 the Settings dialog carries no QSS text of its own (the registry answers both states)",
      "swatch_style(hex_value)" in _dialog_src and "swatch_style(hex_value, selected)" in _dialog_src
      and "border-radius" not in _dialog_src)
check("§2 the palette's hint label takes the muted registry entry (not the literal `gray`)",
      'theme_qss.style("status.muted")' in _read("ui", "command_palette.py")
      and "gray" not in _read("ui", "command_palette.py"))


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the export headers read APP_NAME (N111 c) ==")
# ════════════════════════════════════════════════════════════════════════════

for _rel in ("graphics/map_scene.py", "storage/export_drawio.py"):
    _text = _read(*_rel.split("/"))
    check(f"§3 {_rel} imports the name from `version.py` and keeps no literal of it",
          "import APP_NAME" in _text and APP_NAME not in _text, _rel)

_scene = MapScene()
_node = ServerData("id-identity-1", "prod-web-01", "192.0.2.10", "root")
_scene.add_server(_node)

_svg_path = os.path.join(WORK, "identity.svg")
_scene.render_to_svg(_svg_path)
_svg = io.open(_svg_path, encoding="utf-8", errors="replace").read()
check("§3 the SVG header carries the product name it read from the constant",
      f"<title>{APP_NAME}</title>" in _svg and f"exported from {APP_NAME}" in _svg,
      _svg[:160].replace("\n", " "))

_root = DrawioExporter(_scene).build()
_diagram = _root.find("diagram")
check("§3 the drawio file's host and diagram name are the same ONE name",
      _root.get("host") == APP_NAME and _diagram is not None and _diagram.get("name") == APP_NAME,
      f"host={_root.get('host')!r} name={_diagram.get('name') if _diagram is not None else None!r}")


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the corrected docstrings and the narration that left the code text (N111 d/e/f) ==")
# ════════════════════════════════════════════════════════════════════════════

_activity = _read("modules", "activity_log.py")
_logger_name = re.search(r'install_activity_handler\(logger_name: str = "([^"]+)"', _activity)
check("§4 the logging tap names the logger the tree really uses (the frozen `sshmap`)",
      _logger_name is not None and _logger_name.group(1) == "sshmap"
      and "`sshmap` logger" in _activity and "`sshcanvas` logger" not in _activity,
      _logger_name.group(1) if _logger_name else "no default argument")

_standalone = _read("modules", "terminal_standalone.py")
check("§4 `_panel_server_nodes` declares the LIST the surface answers (None = no hook at all)",
      "The surface answers a LIST (empty while no project is open)" in _standalone
      and "`None` while no project is open" not in _standalone)

for _rel in ("storage/export_drawio.py", "pyproject.toml"):
    check(f"§4 {_rel} carries no `ROADMAP` pointer",
          "ROADMAP" not in _read(*_rel.split("/")), _rel)

_narrative = CB.measure(ROOT)
check("§4 the code text carries no release narrative (AGENTS.md §12.4)",
      _narrative["narrative"] == 0, _narrative["narrative_offenders"][:3])


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the i18n and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check("§5 the polish adds no key to ANY language (the pin stays where v1.12.3 left it)",
      EXPECTED_I18N_KEYS == 1117 + 1 + 4 + 3 + 2 + 8 + 9 + 18 + 4 + 13 + 1 + 1 + 12 + 3
      and all(len(translation_keys(LANGS[c])) == EXPECTED_I18N_KEYS for c in LANGS),
      f"{EXPECTED_I18N_KEYS} / " + str({c: len(translation_keys(LANGS[c])) for c in sorted(LANGS)}))

check_release_state(ROOT)
check("§5 the pin names this line's release or a later one",
      releases_at_least(EXPECTED_APP_VERSION, "1.12.4"), EXPECTED_APP_VERSION)
check("§5 no new dependency and no new config key came with the release",
      "ipaddress" not in _read("requirements.txt") and APP_VERSION == EXPECTED_APP_VERSION)
check("§5 the project JSON schema did NOT move",
      'VERSION_FORMAT = "0.9"' in _read("version.py"))
check("§5 the topical file is listed by the suite map (tests/INDEX.md regenerated)",
      "test_followups_v1124.py" in _read("tests", "INDEX.md"))

finish()
