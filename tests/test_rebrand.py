# -*- coding: utf-8 -*-
"""v1.12.1 — the name the project answers to: `SSHCanvas`, and the identifiers the rename FREEZES.
# tags: docs

The user-visible name is `SSH Canvas` (`version.py` → `APP_NAME`) and the installable identity is
`sshcanvas` with the legacy `sshmap` alias. §1 the identity (name, normalisation, entry points, version
sync); §2 the FROZEN spellings — a stored path, the keyring service, the logger tree and the plugin API
group — because a moved path loses the user's data; §3 the name-bearing i18n keys; §4 the live documents
and the code answer to ONE name (the changelog family keeps the old one VERBATIM); §5 the release state."""
import ast
import io
import os
import re

from _common import (bootstrap, check, check_i18n_parity, check_release_state, finish,
                     load_i18n_langs, releases_at_least, VERSION_FORMAT_RE,
                     EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS)

ROOT, WORK = bootstrap()

#: The product name and its installable form (the ONE normalisation rule of `tests/test_pyproject.py`).
APP_NAME = "SSH Canvas"
DIST_NAME = "sshcanvas"
ALIAS = "sshmap"

#: The clusters the §4 scan walks (the frozen data paths are NOT what that check is about).
CODE_DIRS = ("modules", "ui", "graphics", "storage", "services", "models", "dialogs")


def _read(*parts):
    """The text of one file of the checkout (utf-8, never a fixture)."""
    with io.open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _literal(path, name):
    """One module-level string literal of a source file, via `ast` — no import, no side effects."""
    tree = ast.parse(_read(path), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    try:
                        return ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        return None
    return None


def _norm(name):
    """`SSH Canvas` → `sshcanvas` (the PEP 503-ish normalisation `test_pyproject.py` cross-checks)."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _load(name):
    """`pyproject.toml` as a dict (tomllib on 3.11+, tomli below)."""
    try:
        import tomllib as _toml
    except ModuleNotFoundError:  # pragma: no cover — the project supports 3.10
        import tomli as _toml  # type: ignore
    with open(os.path.join(ROOT, name), "rb") as fh:
        return _toml.load(fh)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the identity: the name, its normalisation and the two commands ==")
# ════════════════════════════════════════════════════════════════════════════

_version_name = _literal("version.py", "APP_NAME")
check("§1 version.py: APP_NAME is the product name (`SSH Canvas`)", _version_name == APP_NAME,
      repr(_version_name))

_pp = _load("pyproject.toml")
_project = _pp.get("project", {})
check("§1 [project].name is APP_NAME normalised (the ONE rule test_pyproject.py owns)",
      _project.get("name") == _norm(APP_NAME) == DIST_NAME,
      "{0!r} vs {1!r}".format(_project.get("name"), _norm(APP_NAME)))

_scripts = _project.get("scripts") or {}
check("§1 the product command ships", _scripts.get(DIST_NAME) == "main:main",
      repr(_scripts.get(DIST_NAME)))
check("§1 the legacy command ships BESIDE it, pointing at the ONE main()",
      _scripts.get(ALIAS) == "main:main", repr(_scripts.get(ALIAS)))
check("§1 the description carries the name (the package metadata a user reads)",
      str(_project.get("description", "")).startswith(APP_NAME + ":"),
      repr(_project.get("description")))
check("§1 the version is synced with version.py (the release-state rule)",
      _project.get("version") == _literal("version.py", "APP_VERSION"),
      "{0!r} / {1!r}".format(_project.get("version"), _literal("version.py", "APP_VERSION")))
check("§1 requirements.txt names the SAME release in its header",
      "v" + str(_literal("version.py", "APP_VERSION")) in _read("requirements.txt").splitlines()[0],
      _read("requirements.txt").splitlines()[0])

print("== §2 the FROZEN spellings: what the rename never touches ==")

_frozen = {
    "the config directory": ('os.path.join(os.path.expanduser("~"), ".sshmap")', "i18n/__init__.py"),
    "the project suffix": ('PROJECT_SUFFIXES = (".json", ".sshmap")', "storage/project.py"),
    "the log file name": ('"sshmap.log"', "modules/logger.py"),
    "the logger tree": ('logging.getLogger("sshmap")', "modules/logger.py"),
    "the keyring service": ('f"sshmap:{server_id}"', "services/credential_manager.py"),
    "the plugin API group": ('ENTRY_POINT_GROUP = "sshmap.plugins/v1"', "modules/plugin_manager.py"),
    "the local plugin module prefix": ('LOCAL_MODULE_PREFIX = "sshmap_plugin_local_"',
                                       "modules/plugin_manager.py"),
    "the known_hosts store": ('"known_hosts"', "modules/host_key_policy.py"),
}
for _what, (_needle, _path) in _frozen.items():
    check("§2 {0} keeps its stored spelling ({1})".format(_what, _path),
          _needle in _read(_path), _needle)

# The activity ring is the ONE consumer of the logger namespace — a renamed logger would silently
# empty it, so the default argument is a contract, not a style choice.
check("§2 the activity ring still attaches to the `sshmap` namespace",
      'install_activity_handler(logger_name: str = "sshmap"' in _read("modules/activity_log.py"))

print("== §3 the name-bearing i18n keys (all languages, the SAME value) ==")

_langs = load_i18n_langs(ROOT)
check("§3 every built-in language is readable (a guard over nothing is useless)", len(_langs) >= 4,
      sorted(_langs))

# A proper NOUN is not translated: the keys below carry the name verbatim in every language.
for _code in sorted(_langs):
    _tr = _langs[_code]
    check("§3 {0}: title.main_window IS the product name (the window title)".format(_code),
          _tr.get("title.main_window") == APP_NAME, repr(_tr.get("title.main_window")))

# …and the sentences that WRAP it (a localized prefix, the same name inside).
for _code in sorted(_langs):
    _tr = _langs[_code]
    for _key in ("about.title", "about.open"):
        check("§3 {0}: {1} names the product".format(_code, _key),
              APP_NAME in str(_tr.get(_key, "")), repr(_tr.get(_key)))

for _code in sorted(_langs):
    _tr = _langs[_code]
    for _key, _marker in (("terminal.standalone.title", "SSHCanvas"),
                          ("terminal.standalone.project_filter", "SSHCanvas"),
                          ("terminal.reconnect_marker", "SSHCanvas")):
        check("§3 {0}: {1} carries the one-word form".format(_code, _key),
              _marker in str(_tr.get(_key, "")), repr(_tr.get(_key)))
    for _key in ("ssh_ext.bad_host", "ssh_ext.bad_user"):
        check("§3 {0}: {1} names the product".format(_code, _key),
              APP_NAME in str(_tr.get(_key, "")), repr(_tr.get(_key)))

check("§3 the About dialog's English fallback equals en.json (the §4.5 rule)",
      'APP_NAME, APP_VERSION = "%s"' % APP_NAME in _read("ui", "about_dialog.py"),
      [ln.strip() for ln in _read("ui", "about_dialog.py").splitlines()
       if "APP_VERSION = " in ln][:1])
# The two EXPORT headers carry the name a user opens elsewhere; the literal is the defect the
# rebrand's own review found, so the check reads the CODE for `APP_NAME` rather than for the
# spelling — a second literal would pass a spelling scan and drift at the next rename.
check("§3 the SVG export header reads the name from `version.py` (never a literal)",
      'generator.setTitle(APP_NAME)' in _read("graphics", "map_scene.py")
      and 'from ..version import APP_NAME' in _read("graphics", "map_scene.py")
      and APP_NAME not in _read("graphics", "map_scene.py"))
check("§3 the drawio export reads the same ONE name",
      'ET.Element("mxfile", {"host": APP_NAME})' in _read("storage", "export_drawio.py")
      and '"id": "sshcanvas-0", "name": APP_NAME' in _read("storage", "export_drawio.py")
      and APP_NAME not in _read("storage", "export_drawio.py"))


# ════════════════════════════════════════════════════════════════════════════
print("== §4 ONE name in the live documents and the code (the old one lives in the changelog) ==")
# ════════════════════════════════════════════════════════════════════════════

# The changelog FAMILY records what shipped under the old name — rewriting it would be a false history,
# so it is deliberately NOT scanned (the SSOT rule of AGENTS.md: history belongs to that family).
_OLD = re.compile(r"SSHMap|SSH Map|SSHmap")
_live_docs = ("README.md", "PLUGINS.md", "AGENTS.md", "DOCUMENTATION.md", "ROADMAP.md",
              "PLUGINS_INTERNAL.md", "TOOLS.md", "COMMENT_AUDIT.md", "UI_UX_AUDIT.md",
              "PYTE82_AUDIT.md", "SFTP_PANES.md", "TERMINAL_STANDALONE.md", "ELEVATED_PANE.md",
              "LOCAL_PANE.md", "AUDIT_PENDING.md")
for _doc in _live_docs:
    _path = os.path.join(ROOT, _doc)
    check("§4 {0} exists (the closed world has this document)".format(_doc), os.path.isfile(_path))
    if os.path.isfile(_path):
        _hits = [ln.strip()[:90] for ln in _read(_doc).splitlines() if _OLD.search(ln)]
        check("§4 {0} answers to the new name".format(_doc), not _hits, _hits[:2])

# The code: the old display name has no home left. The test file itself is excluded — it is the ONE
# place allowed to NAME the old spelling (a guard has to quote what it forbids).
_offenders, _with_frozen_path = [], []
for _dir in CODE_DIRS:
    for _root, _dirs, _files in os.walk(os.path.join(ROOT, _dir)):
        _dirs[:] = [d for d in _dirs if d != "__pycache__"]
        for _name in _files:
            if not _name.endswith(".py"):
                continue
            _rel = os.path.relpath(os.path.join(_root, _name), ROOT).replace("\\", "/")
            _text = _read(_rel)
            if ".sshmap" in _text or "sshmap:" in _text:
                _with_frozen_path.append(_rel)
            for _num, _line in enumerate(_text.splitlines(), 1):
                if _OLD.search(_line):
                    _offenders.append("{0}:{1}".format(_rel, _num))
check("§4 the source tree has no `SSH Map` left (the frozen PATHS are not this scan's business)",
      not _offenders, _offenders[:4])

# The frozen spellings must still be THERE: a second careless sweep would rename the config directory,
# the keyring service or the project suffix — and take the user's data with it.
check("§4 the frozen path/service spellings survive in the source (the rename did not eat them)",
      len(_with_frozen_path) >= 10, "{0} file(s): {1}".format(len(_with_frozen_path),
                                                             _with_frozen_path[:6]))

check("§4 the suite map lists this file (tests/INDEX.md regenerated)",
      "test_rebrand.py" in _read("tests", "INDEX.md"))
check("§4 the installed command is documented in the public page",
      DIST_NAME in _read("README.md") and "pipx install ." in _read("README.md"))

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check("§5 the pin names the released 1.12 line (a patch on `X.Y.Z` adds a component)",
      releases_at_least(EXPECTED_APP_VERSION, "1.12")
      and bool(VERSION_FORMAT_RE.match(EXPECTED_APP_VERSION)),
      EXPECTED_APP_VERSION)
check_i18n_parity(_langs)
check("§5 the parity pin did NOT move for the rename (a rename adds no key)",
      # the rename left the pin at 1114; the LATER follow-ups of the line add their own keys
      # (v1.12.3's THREE), so the claim is anchored on the count the rename itself left.
      EXPECTED_I18N_KEYS == 1114 + 3 + 1 + 4 + 3 + 2 + 8 + 9 + 18 + 4 + 13 + 1 + 1 + 12, EXPECTED_I18N_KEYS)
check("§5 the project JSON schema did NOT move",
      'VERSION_FORMAT = "0.9"' in _read("version.py"))

finish()
