# -*- coding: utf-8 -*-
"""v1.15.2 — the import draft rows: three Qt-free sources, ONE row model, the CLI preview and the GUI apply.
§1 the model (a row's cells, the report's columns, the reason/kind vocabulary against `en.json`); §2 the
`.drawio` reader (the writer's own vocabulary, the label grammar, the member geometry, the edges, the
notes, every skip); §3 the profiles file; §4 the SSH-config adapter (dedupe, the issues, the notes);
§5 `collect()` and its `SourceError` codes; §6 the `import` verb (the registry, the grammar, the payload,
the text form, the codes, the read-only rule, a fresh process without Qt); §7 the dialog and the window
apply; §8 the release state.
Rule — `AGENTS.md` §4.36, §4.35; contract — `CLI.md` §3.7; mechanism — `DOCUMENTATION.md` §27, §28, §80.
Run: python tests/test_import_drafts.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least,
                     translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + offscreen Qt — BEFORE any app import

from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox  # noqa: E402

import services.import_drafts as DRAFTS  # noqa: E402
import storage.import_drawio as DRAWIO  # noqa: E402
import storage.import_profiles as PROFILES  # noqa: E402
import version  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

LANGS = load_i18n_langs(ROOT)
HOME = os.path.expanduser("~")            # the sandbox HOME of this run


def write(path, text, encoding="utf-8"):
    """Write ONE file into the isolated work folder and answer its path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding) as handle:
        handle.write(text)
    return path


def run_cli(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout text, stderr text)`."""
    from cli.main import main
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def document(text):
    """The ONE `--json` document of a run (`{}` when the text is not one)."""
    stripped = str(text or "").strip()
    return json.loads(stripped) if stripped.startswith("{") else {}


def by_kind(report, kind):
    """The drafts of ONE kind, in report order."""
    return [draft for draft in report.drafts if draft.kind == kind]


#: A synthetic `.drawio` model — OUR writer's vocabulary, hand-built (never a real map file).
DRAWIO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="SSH Canvas"><diagram id="sshcanvas-0" name="SSH Canvas"><mxGraphModel dx="1000" dy="700">
<root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="layer-background" value="background" parent="0"/>
<mxCell id="layer-groups" value="groups" parent="0"/>
<mxCell id="layer-map" value="map" parent="0"/>
<mxCell id="bg-image" value="" style="shape=image;image=file:///x.png;" vertex="1" parent="layer-background"/>
<mxCell id="group-1" value="Edge rack" style="rounded=1;container=1;collapsible=0;" vertex="1" parent="layer-groups"><mxGeometry x="100" y="100" width="200" height="150" as="geometry"/></mxCell>
<mxCell id="group-1-member-0" value="web-1&#xa;@192.0.2.10&#xa;Ubuntu 24.04 LTS&#xa;Intel Xeon&#xa;RAM 8 GB&#xa;192.0.2.10&#xa;[prod, web]&#xa;edge node" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="group-1"><mxGeometry x="10" y="20" width="180" height="120" as="geometry"/></mxCell>
<mxCell id="node-srv-db" value="db-1&#xa;@198.51.100.20&#xa;A note of my own" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="layer-map"><mxGeometry x="400" y="50" width="180" height="120" as="geometry"/></mxCell>
<mxCell id="edge-0" value="api" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#a78bfa;strokeWidth=1.5;endArrow=classic;startArrow=classic;" edge="1" parent="layer-map" source="group-1-member-0" target="node-srv-db"><mxGeometry relative="1" as="geometry"/></mxCell>
<mxCell id="edge-1" value="" style="edgeStyle=orthogonalEdgeStyle;strokeColor=#123456;" edge="1" parent="layer-map" source="node-srv-db" target="node-ghost"><mxGeometry relative="1" as="geometry"/></mxCell>
<mxCell id="note-0" value="remember&#xa;the fence" style="shape=note;size=16;" vertex="1" parent="layer-map"><mxGeometry x="600" y="300" width="240" height="160" as="geometry"/></mxCell>
<mxCell id="foreign-1" value="just a box" style="rounded=0;" vertex="1" parent="layer-map"><mxGeometry x="0" y="0" width="10" height="10" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>
"""

DRAWIO_PATH = write(os.path.join(WORK, "import_probe.drawio"), DRAWIO_XML)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the draft-row model ==")
# ════════════════════════════════════════════════════════════════════════════

_DRAFT = DRAFTS.Draft(DRAFTS.KIND_SERVER, {"alias": "web-1", "host": "192.0.2.10", "port": 2222,
                                           "tags": ("prod", "web"), "x": 12.5, "y": 40.0})
check("§1 a row answers its lead columns and its own fields as STRINGS (the report's cells)",
      _DRAFT.cell("kind") == "server" and _DRAFT.cell("verdict") == "add"
      and _DRAFT.cell("reason") == "" and _DRAFT.cell("alias") == "web-1"
      and _DRAFT.cell("port") == "2222" and _DRAFT.cell("tags") == "prod, web"
      and _DRAFT.cell("x") == "12.5" and _DRAFT.cell("user") == "",
      [_DRAFT.cell(name) for name in ("kind", "alias", "port", "tags", "x")])
check("§1 a missing field is an EMPTY cell, a flag reads `true`/`false`, an unknown column is empty",
      _DRAFT.cell("comment") == "" and DRAFTS.cell_text(True) == "true"
      and DRAFTS.cell_text(False) == "false" and DRAFTS.cell_text(None) == ""
      and _DRAFT.cell("nosuchcolumn") == "")

_REPORT = DRAFTS.DraftReport("drawio", "x.drawio", (
    DRAFTS.Draft(DRAFTS.KIND_SERVER, {"alias": "a", "x": 1.0}),
    DRAFTS.Draft(DRAFTS.KIND_SERVER, {"alias": "b"}, verdict=DRAFTS.VERDICT_SKIP,
                 reason=DRAFTS.REASON_FOREIGN_SHAPE),
    DRAFTS.Draft(DRAFTS.KIND_CONNECTION, {"source": "node-a", "target": "node-b"}),
))
check("§1 the report SPLITS its rows into the applicable and the skipped ones",
      [draft.fields.get("alias") for draft in _REPORT.ready()
       if draft.kind == DRAFTS.KIND_SERVER] == ["a"]
      and [draft.reason for draft in _REPORT.skipped()] == [DRAFTS.REASON_FOREIGN_SHAPE]
      and _REPORT.count() == 3)
check("§1 the columns are the lead four plus the fields of every kind the rows carry, in order",
      _REPORT.columns()[:4] == list(DRAFTS.LEAD_COLUMNS)
      and _REPORT.columns()[4:5] == ["ref"] and "source" in _REPORT.columns()
      and len(_REPORT.rows()) == 3 and len(_REPORT.rows()[0]) == len(_REPORT.columns()),
      _REPORT.columns())
check("§1 `payload()` is the pinned report shape — source, path, count, columns, rows",
      tuple(_REPORT.payload()) == ("source", "path", "count", "columns", "rows")
      and _REPORT.payload()["count"] == 3 and _REPORT.payload()["source"] == "drawio")

check("§1 every KIND has a caption key and every reason code a sentence key",
      all(DRAFTS.KIND_KEYS.get(kind) for kind in DRAFTS.KINDS)
      and all(DRAFTS.REASON_KEYS.get(reason) for reason in DRAFTS.REASON_KEYS)
      and len(set(DRAFTS.REASON_KEYS.values())) == len(DRAFTS.REASON_KEYS),
      [kind for kind in DRAFTS.KINDS if not DRAFTS.KIND_KEYS.get(kind)])
_EN = LANGS.get("en") or {}
_EN_KEYS = set(translation_keys(_EN))
check("§1 ...and both tables really name keys of `en.json`",
      all(key in _EN_KEYS for key in DRAFTS.KIND_KEYS.values())
      and all(key in _EN_KEYS for key in DRAFTS.REASON_KEYS.values()),
      sorted(set(DRAFTS.KIND_KEYS.values()) | set(DRAFTS.REASON_KEYS.values()))[:3])
check("§1 the fields of every kind are declared (a kind without one cannot render a table)",
      all(DRAFTS.FIELDS.get(kind) for kind in DRAFTS.KINDS))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the .drawio reader ==")
# ════════════════════════════════════════════════════════════════════════════

_DOC = DRAWIO.parse_drawio_text(DRAWIO_XML, DRAWIO_PATH)
check("§2 the reader reads the writer's OWN vocabulary (the constants live in `storage/export_drawio.py`)",
      DRAWIO.WRITER is not None
      and [value for value in ("NODE_CELL_PREFIX", "EDGE_CELL_PREFIX", "NOTE_CELL_PREFIX",
                               "GROUP_CELL_PREFIX", "MEMBER_CELL_INFIX", "BACKGROUND_CELL_ID",
                               "LAYER_MAP", "LAYER_GROUPS", "LAYER_BACKGROUND")
           if not hasattr(DRAWIO.WRITER, value)] == [])
check("§2 a card's label is reversed: alias, host, the detail block, the tags and the comment",
      len(_DOC.cards) == 2
      and (_DOC.cards[0].alias, _DOC.cards[0].host) == ("web-1", "192.0.2.10")
      and _DOC.cards[0].os_name == "Ubuntu 24.04 LTS"
      and _DOC.cards[0].cpu_model == "Intel Xeon" and _DOC.cards[0].ram == "8 GB"
      and _DOC.cards[0].ip == "192.0.2.10" and _DOC.cards[0].tags == ("prod", "web")
      and _DOC.cards[0].comment == "edge node", str(_DOC.cards[0]))
check("§2 an UNTAGGED label carries its text after `@host` as the COMMENT (no guessed details)",
      (_DOC.cards[1].alias, _DOC.cards[1].host) == ("db-1", "198.51.100.20")
      and _DOC.cards[1].comment == "A note of my own"
      and _DOC.cards[1].tags == () and _DOC.cards[1].os_name == "",
      str(_DOC.cards[1]))
check("§2 a group member is read at the group's ORIGIN + its relative offset",
      (_DOC.cards[0].x, _DOC.cards[0].y) == (110.0, 120.0)
      and (_DOC.cards[1].x, _DOC.cards[1].y) == (400.0, 50.0),
      [(_DOC.cards[i].x, _DOC.cards[i].y) for i in range(len(_DOC.cards))])
check("§2 the label grammar of an absent `@host` line is a FOREIGN shape, never a card",
      DRAWIO.label_fields("just a box") is None and DRAWIO.label_fields("") is None
      and DRAWIO.label_fields("a\n@h")["alias"] == "a")
check("§2 an edge carries its endpoints, label, TYPE (the stroke colour) and both-ways flag",
      len(_DOC.edges) == 1 and _DOC.edges[0].source == "group-1-member-0"
      and _DOC.edges[0].target == "node-srv-db" and _DOC.edges[0].label == "api"
      and _DOC.edges[0].ctype == "database" and _DOC.edges[0].bidirectional is True,
      str(_DOC.edges))
check("§2 a stroke colour no palette carries answers the format's default type",
      DRAWIO.connection_type("strokeColor=#123456;") == "ssh"
      and DRAWIO.connection_type("") == "ssh")
check("§2 a note keeps its text and its geometry",
      len(_DOC.notes) == 1 and _DOC.notes[0].text == "remember\nthe fence"
      and (_DOC.notes[0].x, _DOC.notes[0].width) == (600.0, 240.0), str(_DOC.notes))
check("§2 the FOUR skips are reported with their reason codes, never silently",
      [(issue.subject, issue.reason) for issue in _DOC.skipped]
      == [("bg-image", DRAWIO.REASON_BACKGROUND), ("group-1", DRAWIO.REASON_GROUP),
          ("foreign-1", DRAWIO.REASON_FOREIGN_SHAPE), ("edge-1", DRAWIO.REASON_UNKNOWN_TARGET)],
      [(issue.subject, issue.reason) for issue in _DOC.skipped])
try:
    DRAWIO.parse_drawio_text("<mxfile><diagram>not xml", "bad")
    _PARSE_CODE = ""
except DRAWIO.DrawioError as exc:
    _PARSE_CODE = exc.code
try:
    DRAWIO.parse_drawio_text("<mxfile/>", "empty")
    _EMPTY_CODE = ""
except DRAWIO.DrawioError as exc:
    _EMPTY_CODE = exc.code
check("§2 ...both with their own code (the host and the loader classify them)",
      _PARSE_CODE == DRAWIO.ERROR_PARSE and _EMPTY_CODE == DRAWIO.ERROR_NOT_DRAWIO,
      f"{_PARSE_CODE} / {_EMPTY_CODE}")


def _missing_error():
    try:
        DRAWIO.parse_drawio_file(os.path.join(WORK, "no_such.drawio"))
    except DRAWIO.DrawioError as exc:
        return exc.code
    return ""


check("§2 ...and it is `unreadable` (the CLI turns that into the not-found class)",
      _missing_error() == DRAWIO.ERROR_UNREADABLE)

_REPORT_DRAWIO = DRAFTS.drawio_drafts(_DOC, DRAWIO_PATH)
check("§2 the report carries the cards, the links and the notes as `add`, the skips as `skip`",
      len([d for d in _REPORT_DRAWIO.ready() if d.kind == DRAFTS.KIND_SERVER]) == 2
      and len([d for d in _REPORT_DRAWIO.ready() if d.kind == DRAFTS.KIND_CONNECTION]) == 1
      and len([d for d in _REPORT_DRAWIO.ready() if d.kind == DRAFTS.KIND_NOTE]) == 1
      and len(_REPORT_DRAWIO.skipped()) == 4
      and _REPORT_DRAWIO.path == DRAWIO_PATH, str(_REPORT_DRAWIO.count()))
check("§2 a skipped GROUP row keeps its kind and its name (the dialog reports the frame)",
      [(d.kind, d.fields.get("ref")) for d in _REPORT_DRAWIO.skipped()
       if d.reason == DRAFTS.REASON_GROUP] == [(DRAFTS.KIND_GROUP, "group-1")],
      [d.kind for d in _REPORT_DRAWIO.skipped()])
check("§2 the card's measured facts ride in `detail` — the import carries no os/cpu/ram field",
      "os_name=Ubuntu 24.04 LTS" in by_kind(_REPORT_DRAWIO, DRAFTS.KIND_SERVER)[0].detail
      and "ram=8 GB" in by_kind(_REPORT_DRAWIO, DRAFTS.KIND_SERVER)[0].detail,
      by_kind(_REPORT_DRAWIO, DRAFTS.KIND_SERVER)[0].detail)


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the profiles file ==")
# ════════════════════════════════════════════════════════════════════════════

PROFILES_PATH = write(os.path.join(WORK, "profiles.json"), json.dumps([
    {"id": "aaa", "name": "ops", "user": "root"},
    {"name": "OPS", "user": "other"},
    {"name": "", "user": "x"},
    {"name": "dev", "user": ""},
    "not a record",
]))
_PROFILE_DOC = PROFILES.parse_profiles_file(PROFILES_PATH)
check("§3 a usable record answers its NAME and login; the id is ignored (a name merge)",
      [(row.name, row.user) for row in _PROFILE_DOC.rows] == [("ops", "root"), ("OPS", "other")],
      [(row.name, row.user) for row in _PROFILE_DOC.rows])
check("§3 every unusable entry is a SKIP record with its code",
      [issue.reason for issue in _PROFILE_DOC.skipped]
      == [PROFILES.REASON_MISSING_NAME, PROFILES.REASON_MISSING_USER,
          PROFILES.REASON_MALFORMED_ENTRY],
      [issue.reason for issue in _PROFILE_DOC.skipped])
check("§3 a JSON object instead of a list is ONE `not_a_list` skip, not a crash",
      [issue.reason for issue in PROFILES.parse_profiles_text('{"a": 1}', "f").skipped]
      == [PROFILES.REASON_NOT_A_LIST])
try:
    PROFILES.parse_profiles_text("{ not json", "bad")
    _PROFILES_CODE = ""
except PROFILES.ProfilesFileError as exc:
    _PROFILES_CODE = exc.code
check("§3 a file that does not parse is the PARSE error class", _PROFILES_CODE == PROFILES.ERROR_PARSE)

_PROFILE_REPORT = DRAFTS.profile_drafts(_PROFILE_DOC, existing_names={"ops"})
check("§3 the merge key is the NAME, case-insensitively: a stored name is a SKIP row",
      [(d.fields.get("name"), d.verdict) for d in _PROFILE_REPORT.drafts][:2]
      == [("ops", DRAFTS.VERDICT_SKIP), ("OPS", DRAFTS.VERDICT_SKIP)]
      and [d.reason for d in _PROFILE_REPORT.skipped()
           if d.reason == DRAFTS.REASON_DUPLICATE_NAME] == [DRAFTS.REASON_DUPLICATE_NAME] * 2,
      [(d.fields.get("name"), d.reason) for d in _PROFILE_REPORT.drafts])
check("§3 the profile store's path has ONE public door (`profiles_path()`)",
      hasattr(__import__("models.profile", fromlist=["x"]), "profiles_path"))


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the SSH-config adapter ==")
# ════════════════════════════════════════════════════════════════════════════

CONFIG_PATH = write(os.path.join(WORK, "ssh_config"), (
    "Host web-1\n    HostName 192.0.2.10\n    User deploy\n    Port 2222\n"
    "Host db-1\n    HostName 198.51.100.20\n    User postgres\n    ProxyCommand nc %h %p\n"
    "Host *\n    User global\n"))
_SSH_REPORT = DRAFTS.collect(DRAFTS.SOURCE_SSH_CONFIG, CONFIG_PATH, home=HOME)
check("§4 every concrete host is an `add` row carrying the map's own card fields",
      [(d.fields["alias"], d.fields["host"], d.fields["port"], d.fields["user"])
       for d in _SSH_REPORT.ready()] == [("web-1", "192.0.2.10", 2222, "deploy"),
                                         ("db-1", "198.51.100.20", 22, "postgres")],
      [d.fields for d in _SSH_REPORT.ready()])
check("§4 a wildcard pattern is a SKIP row with the parser's own reason code",
      [(d.fields.get("alias"), d.reason) for d in _SSH_REPORT.skipped()]
      == [("*", "wildcard")], str(_SSH_REPORT.skipped()))
check("§4 a dropped directive is the host's `detail` (the picker translates the notes)",
      "proxy" in _SSH_REPORT.ready()[1].detail, _SSH_REPORT.ready()[1].detail)
_DEDUPED = DRAFTS.collect(DRAFTS.SOURCE_SSH_CONFIG, CONFIG_PATH, home=HOME,
                          project_keys={("192.0.2.10", 2222, "deploy")})
check("§4 a host the project already knows is a SKIP/duplicate row, not a second card",
      [(d.fields.get("alias"), d.reason) for d in _DEDUPED.skipped()
       if d.reason == DRAFTS.REASON_DUPLICATE] == [("web-1", DRAFTS.REASON_DUPLICATE)]
      and len(_DEDUPED.ready()) == 1,
      [d.reason for d in _DEDUPED.skipped()])


# ════════════════════════════════════════════════════════════════════════════
print("== §5 `collect()` and its error codes ==")
# ════════════════════════════════════════════════════════════════════════════


def collect_error(source, path=""):
    """The `SourceError` ONE collect() call raises — `(code, retried)`."""
    try:
        DRAFTS.collect(source, path, home=HOME)
    except DRAFTS.SourceError as exc:
        return exc.code
    return ""


check("§5 a source that is not there is `missing` (the CLI's not-found class)",
      collect_error(DRAFTS.SOURCE_DRAWIO, os.path.join(WORK, "nope.drawio")) == DRAFTS.ERROR_MISSING
      and collect_error(DRAFTS.SOURCE_SSH_CONFIG, os.path.join(WORK, "nope_config"))
      == DRAFTS.ERROR_MISSING)
check("§5 a file that does not parse is `parse`",
      collect_error(DRAFTS.SOURCE_DRAWIO, write(os.path.join(WORK, "bad.drawio"), "<x"))
      == DRAFTS.ERROR_PARSE
      and collect_error(DRAFTS.SOURCE_PROFILES,
                        write(os.path.join(WORK, "bad_profiles.json"), "{ nope"))
      == DRAFTS.ERROR_PARSE)
check("§5 a drawio source names no default path — it needs its file",
      DRAFTS.default_path(DRAFTS.SOURCE_DRAWIO) == ""
      and DRAFTS.default_path(DRAFTS.SOURCE_SSH_CONFIG, HOME).endswith(os.path.join(".ssh", "config"))
      and DRAFTS.default_path(DRAFTS.SOURCE_PROFILES).endswith(".sshmap_profiles.json"),
      DRAFTS.default_path(DRAFTS.SOURCE_PROFILES))


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the `import` verb ==")
# ════════════════════════════════════════════════════════════════════════════

import cli.dispatch as DISPATCH  # noqa: E402
import cli.exit_codes as EX  # noqa: E402
import cli.imports as CLI_IMPORT  # noqa: E402
import cli.report as REPORT  # noqa: E402
import cli.verb_args as VERB_ARGS  # noqa: E402
import storage.table_text as TABLE_TEXT  # noqa: E402

DISPATCH.load_verbs()
check("§6 the verb is registered, takes its source and writes nothing",
      "import" in DISPATCH.VERBS and DISPATCH.VERBS["import"].mutating is False
      and DISPATCH.VERBS["import"].min_args == 1
      and DISPATCH.VERBS["import"].max_args == VERB_ARGS.MAX_ARGUMENTS
      and "cli.imports" in DISPATCH.BUILTIN_VERB_MODULES,
      str(DISPATCH.VERBS.get("import")))
check("§6 the verb's own argument reader declares the source, ONE path and `--format`",
      VERB_ARGS.IMPORT_VERBS == ("import",)
      and VERB_ARGS.read_import("import", ["drawio", "a.drawio"], DRAFTS.SOURCES).source == "drawio"
      and VERB_ARGS.read_import("import", ["drawio", "a.drawio"], DRAFTS.SOURCES).path == "a.drawio"
      and VERB_ARGS.read_import("import", ["drawio", "a.drawio", "--format", "tsv"],
                                DRAFTS.SOURCES).format == "tsv"
      and VERB_ARGS.read_import("import", ["profiles"], DRAFTS.SOURCES).path == "")
_GRAMMAR_ERRORS = []
for _argv in (["import"], ["import", "bogus"], ["import", "drawio", "a", "b"],
              ["import", "drawio", "a", "--format", "xml"], ["import", "--json"]):
    try:
        VERB_ARGS.read_import("import", _argv[1:], DRAFTS.SOURCES)
        _GRAMMAR_ERRORS.append(f"{_argv}: parsed")
    except Exception as exc:  # noqa: BLE001 — the point is that EVERY bad tail is refused
        if type(exc).__name__ != "CliError":
            _GRAMMAR_ERRORS.append(f"{_argv}: {type(exc).__name__}")
check("§6 an undeclared source, a second path, a bad format and a missing source are USAGE",
      not _GRAMMAR_ERRORS, _GRAMMAR_ERRORS)

_CODE, _OUT, _ERR = run_cli(["--json", "import", "drawio", DRAWIO_PATH])
_DOC_JSON = document(_OUT)
_DATA = _DOC_JSON.get("data") or {}
check("§6 `import drawio` answers ONE envelope whose `data` is the pinned payload",
      _CODE == EX.EXIT_OK and _DOC_JSON.get("ok") is True and _DOC_JSON.get("error") is None
      and _DOC_JSON.get("verb") == "import"
      and tuple(_DATA) == CLI_IMPORT.DATA_KEYS
      == ("source", "path", "count", "columns", "rows"),
      f"{_CODE} / {_OUT[:140]}")
check("§6 ...the source, the path, the row count and the cells of every row",
      _DATA.get("source") == "drawio" and _DATA.get("path") == DRAWIO_PATH
      and _DATA.get("count") == len(_REPORT_DRAWIO.drafts)
      and len(_DATA.get("rows") or []) == _DATA.get("count")
      and all(len(row) == len(_DATA.get("columns") or []) for row in _DATA.get("rows") or []),
      str(_DATA.get("count")))
_CODE, _OUT, _ERR = run_cli(["import", "drawio", DRAWIO_PATH])
check("§6 the TEXT form is the shipped writer over the SAME cells (the header is the column ids)",
      _CODE == EX.EXIT_OK and _OUT == TABLE_TEXT.list_table_text(
          [_DATA["columns"]] + _DATA["rows"], TABLE_TEXT.list_delimiter("csv"))
      and _OUT.startswith(",".join(_DATA["columns"]) + "\r\n"), repr(_OUT[:80]))
_CODE, _OUT, _ERR = run_cli(["import", "drawio", DRAWIO_PATH, "--format", "tsv"])
check("§6 `--format tsv` writes the same rows with tabs",
      _CODE == EX.EXIT_OK and "\t" in _OUT and not _OUT.startswith("\ufeff"))
_CODE, _OUT, _ERR = run_cli(["--json", "import", "drawio", os.path.join(WORK, "gone.drawio")])
check("§6 a missing source file is `5` (not-found), NAMED",
      _CODE == EX.EXIT_NOT_FOUND
      and document(_OUT).get("error", {}).get("kind") == "not_found"
      and "gone.drawio" in document(_OUT).get("error", {}).get("message", ""), _OUT[:140])
_CODE, _OUT, _ERR = run_cli(["--json", "import", "drawio",
                             write(os.path.join(WORK, "broken.drawio"), "<nope")])
check("§6 a source that does not parse is `1` (usage)",
      _CODE == EX.EXIT_USAGE and document(_OUT).get("error", {}).get("kind") == "usage")
_CODE, _OUT, _ERR = run_cli(["--json", "import", "profiles", PROFILES_PATH])
_PROFILES_DATA = document(_OUT).get("data") or {}
check("§6 `import profiles` merges by name against the STORE's names (read-only)",
      _CODE == EX.EXIT_OK and _PROFILES_DATA.get("source") == "profiles"
      and "duplicate_name" in [row[2] for row in _PROFILES_DATA.get("rows") or []],
      str(_PROFILES_DATA.get("rows"))[:200])

_BEFORE = open(DRAWIO_PATH, "rb").read()
_LISTING = sorted(os.listdir(WORK))
for _argv in (["import", "drawio", DRAWIO_PATH], ["--json", "import", "ssh-config", CONFIG_PATH]):
    run_cli(_argv)
check("§6 the verb NEVER writes its source (the bytes and the folder are unchanged)",
      open(DRAWIO_PATH, "rb").read() == _BEFORE and sorted(os.listdir(WORK)) == _LISTING)
check("§6 no project file was created (the preview needs no map)",
      not any(name.startswith("preview") and name.endswith(".json") for name in os.listdir(WORK)))

_QT_CODE = ("import importlib\n"
            "for name in ('services.import_drafts', 'storage.import_drawio',"
            " 'storage.import_profiles', 'cli.imports'):\n"
            "    importlib.import_module(name)\n"
            "import sys\nprint('PySide6' in sys.modules)\n")
_DONE = subprocess.run([sys.executable, "-c", _QT_CODE], cwd=ROOT, capture_output=True, text=True,
                       timeout=180, env=dict(os.environ, PYTHONPATH=ROOT))
check("§6 the model and the two readers import in a FRESH process WITHOUT PySide6",
      _DONE.returncode == 0 and _DONE.stdout.strip() == "False",
      f"{(_DONE.stdout or '').strip()!r} / {(_DONE.stderr or '')[-200:]}")


# ════════════════════════════════════════════════════════════════════════════
print("== §7 the dialog and the window apply ==")
# ════════════════════════════════════════════════════════════════════════════

import i18n  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from dialogs import import_drafts_dialog as IDD  # noqa: E402

_DLG = IDD.ImportDraftsDialog(_REPORT_DRAWIO)
check("§7 one row per APPLICABLE draft, every row checked, the import button live",
      _DLG.item_count() == 4 and _DLG.checked_count() == 4 and _DLG.btn_import.isEnabled(),
      f"{_DLG.item_count()} / {_DLG.checked_count()}")
check("§7 the headers are the translated column captions, in the report's order",
      _DLG.tree.columnCount() == len(_REPORT_DRAWIO.columns())
      and _DLG.tree.headerItem().text(0) == i18n.t("import.col.kind")
      and _DLG.tree.headerItem().text(1) == i18n.t("import.col.verdict"),
      [_DLG.tree.headerItem().text(i) for i in range(3)])
check("§7 the `kind` cell is the CAPTION, never the raw id",
      _DLG.tree.topLevelItem(0).text(0) == i18n.t("import.kind.server"),
      _DLG.tree.topLevelItem(0).text(0))
check("§7 `selected_drafts()` answers the live rows of the checked ones",
      _DLG.selected_drafts() == list(_REPORT_DRAWIO.ready()))
_DLG.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
app.processEvents()
check("§7 unchecking a row takes it out of the selection",
      len(_DLG.selected_drafts()) == len(_REPORT_DRAWIO.ready()) - 1)
_DLG.btn_none.click()
app.processEvents()
check("§7 'Uncheck all' empties the selection and DISABLES the import (no dead OK)",
      _DLG.checked_count() == 0 and not _DLG.btn_import.isEnabled())
_DLG.btn_all.click()
app.processEvents()
check("§7 'Check all' restores it", _DLG.checked_count() == 4 and _DLG.btn_import.isEnabled())
check("§7 the skipped rows are a read-only report naming the reason SENTENCES",
      i18n.t("import.skipped", count=4) in _DLG.report_text()
      and i18n.t("import.reason.group") in _DLG.report_text()
      and i18n.t("import.reason.foreign_shape") in _DLG.report_text(), _DLG.report_text())
check("§7 a clean report HIDES the section (nothing to tell)",
      IDD.ImportDraftsDialog(DRAFTS.DraftReport(
          "drawio", "x", (DRAFTS.Draft(DRAFTS.KIND_SERVER, {"alias": "a"}),))).report.isHidden())
check("§7 `reason_text()` falls back to the code pair for an unknown reason",
      IDD.reason_text("nope", "d") == "nope (d)" and IDD.reason_text("nope") == "nope")
check("§7 `kind_text()` falls back to the id, `column_text()` to the column id",
      IDD.kind_text("nope") == "nope" and IDD.column_text("nope") == "nope")
_DLG.close()

import ui.main_window as MW  # noqa: E402

mw = MW.MainWindow()
mw.show()
app.processEvents()

_INFO, _CRITICAL = [], []


class _FakeDraftsDialog:
    """The preview stand-in: accepts, and answers EVERY applicable row."""

    def __init__(self, report, parent=None):
        self.report = report

    def exec(self):
        return QDialog.Accepted

    def selected_drafts(self):
        return list(self.report.ready())


_ORIG_OPEN = QFileDialog.getOpenFileName
_ORIG_INFO = QMessageBox.information
_ORIG_CRIT = QMessageBox.critical
_ORIG_DLG = getattr(MW, "ImportDraftsDialog", None)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (DRAWIO_PATH, ""))
QMessageBox.information = staticmethod(lambda *a, **k: _INFO.append(a) or QMessageBox.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: _CRITICAL.append(a) or QMessageBox.Ok)
MW.ImportDraftsDialog = _FakeDraftsDialog
try:
    mw._import_map_from_drawio()
    app.processEvents()
    _NODES = len(mw.scene.nodes())
    _ARROWS = len(mw.scene.arrows())
    _NOTES = len(mw.scene.notes())
    _POS = {node.data.alias: (node.pos().x(), node.pos().y()) for node in mw.scene.nodes()}
    _IDS = {node.data.alias: node.data.id for node in mw.scene.nodes()}
    _LINK = [(arrow.source.data.alias, arrow.target.data.alias, arrow.connection_type,
              arrow.bidirectional, arrow.label_text) for arrow in mw.scene.arrows()]
    _UNDO_STEPS = mw.undo_stack.count()
    mw._undo()          # the last note
    mw._undo()          # the link
    mw._undo()          # the batch of cards
    app.processEvents()
    _AFTER_UNDO = (len(mw.scene.nodes()), len(mw.scene.arrows()), len(mw.scene.notes()))
finally:
    QFileDialog.getOpenFileName = _ORIG_OPEN
    QMessageBox.information = _ORIG_INFO
    QMessageBox.critical = _ORIG_CRIT
    if _ORIG_DLG is not None:
        MW.ImportDraftsDialog = _ORIG_DLG

check("§7 the window applies the drafts: two cards, one link and one note, no error box",
      _NODES == 2 and _ARROWS == 1 and _NOTES == 1 and not _CRITICAL and _INFO,
      f"{_NODES}/{_ARROWS}/{_NOTES} critical={len(_CRITICAL)}")
check("§7 the cards keep the FILE's geometry — the import grid is skipped",
      _POS == {"web-1": (110.0, 120.0), "db-1": (400.0, 50.0)}, str(_POS))
check("§7 the link resolves the file's cell refs into the NEW node ids, with its type and both ways",
      _LINK == [("web-1", "db-1", "database", True, "api")] and _IDS["web-1"] != _IDS["db-1"],
      str(_LINK))
check("§7 the three gestures are three undo steps (cards, link, note) and each one rolls back",
      _UNDO_STEPS == 3 and _AFTER_UNDO == (0, 0, 0), f"{_UNDO_STEPS} / {_AFTER_UNDO}")
check("§7 the result names what came across (one message box, the skipped count included)",
      _INFO and "2" in str(_INFO[-1][2]), str(_INFO[-1][2]) if _INFO else "")
check("§7 the mixin's seam is the facade attribute the tests swap (`MW.ImportDraftsDialog`)",
      _ORIG_DLG is not None and hasattr(MW, "SshConfigImportDialog"))
mw.close()
app.processEvents()

# ── the profile manager's Import… — a name merge, ONE store write ───────────────────────────
import models.profile as PROFILE_MODEL  # noqa: E402
import dialogs.profile_manager_dialog as PMD  # noqa: E402

STORE_PATH = os.path.join(WORK, "profiles_store.json")
GUEST_PATH = write(os.path.join(WORK, "profiles_guest.json"), json.dumps([
    {"name": "ops", "user": "root"},              # already stored — a skip
    {"name": "deploy", "user": "ubuntu"},          # new — an add
]))
_ORIG_STORE = PROFILE_MODEL._profiles_path
_ORIG_PMD_DLG = PMD.ImportDraftsDialog
_ORIG_OPEN2 = QFileDialog.getOpenFileName
_ORIG_INFO2 = QMessageBox.information
_PROFILE_INFO = []
PROFILE_MODEL._profiles_path = lambda: STORE_PATH
PROFILE_MODEL.save_profiles([PROFILE_MODEL.Profile(id="keep0001", name="ops", user="root")])
PMD.ImportDraftsDialog = _FakeDraftsDialog
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (GUEST_PATH, ""))
QMessageBox.information = staticmethod(lambda *a, **k: _PROFILE_INFO.append(a) or QMessageBox.Ok)
try:
    manager = PMD.ProfileManagerDialog(None)
    manager._on_import_profiles()
    app.processEvents()
    _STORED = [(profile.name, profile.user) for profile in PROFILE_MODEL.load_profiles()]
    _MANAGER_ROWS = manager.table.rowCount()
    manager.close()
finally:
    PROFILE_MODEL._profiles_path = _ORIG_STORE
    PMD.ImportDraftsDialog = _ORIG_PMD_DLG
    QFileDialog.getOpenFileName = _ORIG_OPEN2
    QMessageBox.information = _ORIG_INFO2

check("§7 the profile manager's import MERGES by name: the stored one stays, the new one lands",
      _STORED == [("ops", "root"), ("deploy", "ubuntu")] and _MANAGER_ROWS == 2, str(_STORED))
check("§7 ...ONE store write and ONE result line naming both counts",
      _PROFILE_INFO and str(_PROFILE_INFO[-1][2]).startswith("Imported 1 profiles, 1 skipped"),
      str(_PROFILE_INFO[-1][2]) if _PROFILE_INFO else "")
app.processEvents()


# ════════════════════════════════════════════════════════════════════════════
print("== §8 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

import ui.hotkey_registry as HR  # noqa: E402

check_release_state(ROOT)
check(f"§8 this release is v{EXPECTED_APP_VERSION} (the `1.15` line or a later one)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15") and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§8 the release adds the 51 preview keys (the pin EXPECTED_I18N_KEYS = {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1205 + 51
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
check("§8 the new action is in the registry with an EMPTY default and NO duplicate id",
      HR.default_sequence("file.import_drawio") == ""
      and "file.import_drawio" in HR.HOTKEY_ACTIONS
      and len(HR.HOTKEY_ACTIONS) == 63 and len(HR.empty_default_action_ids()) == 40,
      f"{len(HR.HOTKEY_ACTIONS)} / {len(HR.empty_default_action_ids())}")
check("§8 `CLI.md` carries the §3.7 clause, the three sources and the read-only rule",
      "### 3.7 `import`" in open(os.path.join(ROOT, "CLI.md"), encoding="utf-8").read()
      and all(source in open(os.path.join(ROOT, "CLI.md"), encoding="utf-8").read()
              for source in DRAFTS.SOURCES))
_AGENTS = open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8").read()
check("§8 `AGENTS.md` declares §4.36 and names the ONE row model",
      "### 4.36 The Import Draft Rows" in _AGENTS and "services/import_drafts.py" in _AGENTS)
check("§8 no module of `cli/` IMPORTS PySide6 (a docstring may name the rule — the gate of §6 measures)",
      not [name for name in sorted(os.listdir(os.path.join(ROOT, "cli")))
           if name.endswith(".py")
           and any(line.lstrip().startswith(("import PySide6", "from PySide6"))
                   for line in open(os.path.join(ROOT, "cli", name), encoding="utf-8"))])

finish()
