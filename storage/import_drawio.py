# -*- coding: utf-8 -*-
"""The `.drawio` READER — an mxGraph model back into import drafts, the reverse of the shipped writer.

The cell vocabulary is `storage/export_drawio.py`'s OWN (`LAYER_*`, the id prefixes): a card is
`node-<id>` or a group member, a link `edge-<n>`, a note `note-<n>`, a group container `group-<n>`.
The label grammar is `_node_label()`'s, reversed: line 0 the alias, line 1 `@host`, the optional
os / cpu / `RAM …` / ip details BEFORE the `[tags]` line, then the comment lines (a label with no
`[tags]` line carries its text after `@host` as the COMMENT — the writer emits the details only when a
tag line follows them, so an untagged card's details are not reconstructed).
A label with no `@host` line, a foreign shape and a group frame are SKIP records with a reason code:
this reader never guesses. PURE — `xml.etree` only (no Qt, no i18n); mechanism — `DOCUMENTATION.md` §28.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    from . import export_drawio as WRITER
    from .project import DEFAULT_CONNECTION_TYPE
except ImportError:
    import export_drawio as WRITER
    from project import DEFAULT_CONNECTION_TYPE

try:  # the ONE address predicate — the import family's own (`services/host_importer` re-exports it)
    from ..models.server import is_ip_address
except ImportError:
    from models.server import is_ip_address

# ── loader error codes (the CLI / the GUI maps them to their own class) ──────────────────────
ERROR_UNREADABLE = "unreadable"
ERROR_PARSE = "parse"
ERROR_NOT_DRAWIO = "not_drawio"

# ── skip reasons: a cell that is NOT imported ────────────────────────────────────────────────
REASON_FOREIGN_SHAPE = "foreign_shape"     # a vertex whose label is not this app's card grammar
REASON_GROUP = "group"                     # a group frame — its members still come across
REASON_BACKGROUND = "background"           # the background image layer
REASON_UNSUPPORTED = "unsupported"         # a compressed / model-less diagram
REASON_UNKNOWN_TARGET = "unknown_target"   # an edge naming a cell the file does not carry

#: The detail-line prefix `_node_label()` writes for the RAM fact.
RAM_PREFIX = "RAM "


class DrawioError(Exception):
    """The `.drawio` file cannot be used (``code`` = ERROR_UNREADABLE / ERROR_PARSE / ERROR_NOT_DRAWIO)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class DrawioIssue:
    """One cell the reader left out: the cell id as ``subject`` and a reason code."""

    subject: str
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class DrawioCard:
    """One card vertex — the label fields `_node_label()` writes, plus its absolute geometry."""

    cell_id: str
    alias: str
    host: str
    tags: Tuple[str, ...] = ()
    comment: str = ""
    os_name: str = ""
    cpu_model: str = ""
    ram: str = ""
    ip: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass(frozen=True)
class DrawioEdge:
    """One link edge: the two cell ids it connects, its label, the type its stroke names."""

    cell_id: str
    source: str
    target: str
    label: str = ""
    ctype: str = "ssh"
    bidirectional: bool = False


@dataclass(frozen=True)
class DrawioNote:
    """One note vertex: its text and its geometry."""

    cell_id: str
    text: str
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass(frozen=True)
class DrawioDocument:
    """The parsed document: the three imported families beside every cell that was left out."""

    cards: Tuple[DrawioCard, ...] = ()
    edges: Tuple[DrawioEdge, ...] = ()
    notes: Tuple[DrawioNote, ...] = ()
    skipped: Tuple[DrawioIssue, ...] = ()
    path: str = ""


def _number(text, default: float = 0.0) -> float:
    """A geometry attribute as a float (an unparsable one answers the default, never raises)."""
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return float(default)


def style_fields(style) -> dict:
    """`"rounded=1;fillColor=#fff;"` → `{"rounded": "1", "fillcolor": "#fff"}` (keys lower-cased)."""
    out = {}
    for part in str(style or "").split(";"):
        name, separator, value = part.partition("=")
        if separator:
            out[name.strip().lower()] = value.strip()
    return out


def cell_geometry(cell) -> Tuple[float, float, float, float]:
    """(x, y, width, height) of ONE cell — the `mxGeometry` child the writer always emits."""
    geometry = cell.find("mxGeometry")
    if geometry is None:
        return 0.0, 0.0, 0.0, 0.0
    return (_number(geometry.get("x")), _number(geometry.get("y")),
            _number(geometry.get("width")), _number(geometry.get("height")))


def _looks_like_address(text: str) -> bool:
    """Is this detail line an IP address? (the writer's ip line)."""
    try:
        return bool(is_ip_address(text))
    except Exception:  # noqa: BLE001 — a __str__ that raises is not an address
        return False


def label_fields(value) -> Optional[dict]:
    """The card fields of ONE label — `None` when the label is not this application's grammar.

    The grammar is `_node_label()`'s own, reversed: alias, `@host`, the DETAILS (os, cpu, `RAM …`,
    ip — in the writer's order), the `[tag, …]` line, then the comment. The detail block is consumed
    only while a tag line follows it: an untagged label has no declared boundary between its details
    and its comment, and the user-authored text wins (a measured fact is re-collected anyway).
    """
    lines = str(value if value is not None else "").replace("\r\n", "\n").split("\n")
    if len(lines) < 2 or not lines[1].startswith("@"):
        return None
    fields = {"alias": lines[0].strip(), "host": lines[1][1:].strip(), "tags": (), "comment": "",
              "os_name": "", "cpu_model": "", "ram": "", "ip": ""}
    rest = lines[2:]
    bracket = None
    for index, line in enumerate(rest):
        text = line.strip()
        if len(text) >= 2 and text.startswith("[") and text.endswith("]"):
            bracket = index
            fields["tags"] = tuple(part.strip() for part in text[1:-1].split(",") if part.strip())
            break
    if bracket is None:
        fields["comment"] = "\n".join(rest).strip("\n")
        return fields
    for line in rest[:bracket]:
        text = line.strip()
        if not text:
            continue
        if text.startswith(RAM_PREFIX):
            fields["ram"] = fields["ram"] or text[len(RAM_PREFIX):].strip()
        elif _looks_like_address(text):
            fields["ip"] = fields["ip"] or text
        elif not fields["os_name"]:
            fields["os_name"] = text
        elif not fields["cpu_model"]:
            fields["cpu_model"] = text
    comment = rest[bracket + 1:]
    fields["comment"] = "\n".join(comment).strip("\n") if comment else ""
    return fields


def edge_type_colors() -> dict:
    """`{stroke colour: connection type}` over the TWO declared export palettes (lower-cased keys)."""
    out = {}
    for palette in (WRITER.PALETTE_PRINT, WRITER.PALETTE_THEME):
        for ctype, color in WRITER.export_palette_colors(palette)["arrow_colors"].items():
            out.setdefault(str(color).strip().lower(), str(ctype))
    return out


def connection_type(style, colors=None) -> str:
    """The declared connection type a link's stroke names — the format's default otherwise."""
    table = colors if colors is not None else edge_type_colors()
    stroke = style_fields(style).get("strokecolor", "").strip().lower()
    return table.get(stroke, DEFAULT_CONNECTION_TYPE) if stroke else DEFAULT_CONNECTION_TYPE


def parse_drawio_text(text, source: str = "") -> DrawioDocument:
    """Parse ONE `.drawio` XML text into cards, links, notes and the cells left out."""
    try:
        root = ET.fromstring(str(text if text is not None else ""))
    except ET.ParseError as exc:
        raise DrawioError(ERROR_PARSE, str(exc))
    cells = list(root.iter("mxCell"))
    if not cells:
        raise DrawioError(ERROR_NOT_DRAWIO, "the file carries no mxCell — a compressed model is not read")
    # Groups carry their members' RELATIVE coordinates — every origin is read before the members.
    origins = {}
    for cell in cells:
        style = style_fields(cell.get("style"))
        if style.get("container") == "1":
            x, y, _w, _h = cell_geometry(cell)
            origins[str(cell.get("id") or "")] = (x, y)
    colors = edge_type_colors()
    cards, edges, notes, skipped = [], [], [], []
    for cell in cells:
        cell_id = str(cell.get("id") or "")
        style = style_fields(cell.get("style"))
        value = cell.get("value")
        x, y, width, height = cell_geometry(cell)
        if cell.get("edge") == "1":
            edges.append(DrawioEdge(
                cell_id=cell_id,
                source=str(cell.get("source") or ""),
                target=str(cell.get("target") or ""),
                label=str(value or ""),
                ctype=connection_type(cell.get("style"), colors),
                bidirectional=style.get("startarrow") == "classic"))
            continue
        if cell.get("vertex") != "1":
            continue                            # a layer / the root pair — structural, not a shape
        if style.get("shape") == "image" or cell_id == WRITER.BACKGROUND_CELL_ID:
            skipped.append(DrawioIssue(cell_id, REASON_BACKGROUND, str(value or "")))
            continue
        if style.get("container") == "1":
            skipped.append(DrawioIssue(cell_id, REASON_GROUP, str(value or "")))
            continue
        if style.get("shape") == "note":
            notes.append(DrawioNote(cell_id, str(value or ""), x, y, width, height))
            continue
        fields = label_fields(value)
        if fields is None:
            skipped.append(DrawioIssue(cell_id, REASON_FOREIGN_SHAPE, str(value or "")[:120]))
            continue
        parent = str(cell.get("parent") or "")
        origin = origins.get(parent)
        if origin is not None:                   # a group member — the writer's relative geometry
            x, y = origin[0] + x, origin[1] + y
        cards.append(DrawioCard(
            cell_id=cell_id, alias=fields["alias"], host=fields["host"], tags=fields["tags"],
            comment=fields["comment"], os_name=fields["os_name"], cpu_model=fields["cpu_model"],
            ram=fields["ram"], ip=fields["ip"], x=x, y=y, width=width, height=height))
    known = {card.cell_id for card in cards}
    for edge in edges:
        missing = [ref for ref in (edge.source, edge.target) if ref not in known]
        if missing:
            skipped.append(DrawioIssue(edge.cell_id, REASON_UNKNOWN_TARGET, ", ".join(missing)))
    edges = [edge for edge in edges if edge.source in known and edge.target in known]
    return DrawioDocument(cards=tuple(cards), edges=tuple(edges), notes=tuple(notes),
                          skipped=tuple(skipped), path=str(source or ""))


def parse_drawio_file(path) -> DrawioDocument:
    """Read and parse a `.drawio` FILE — a missing or unreadable one raises `DrawioError`."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read()
    except FileNotFoundError:
        raise DrawioError(ERROR_UNREADABLE, f"no file at {path}")
    except OSError as exc:
        raise DrawioError(ERROR_UNREADABLE, f"{path}: {exc}")
    return parse_drawio_text(text, str(path or ""))
