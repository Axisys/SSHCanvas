"""Sticky notes — free-standing text notes on the map (AGENTS.md §4.2, §4.6; DOCUMENTATION.md §20).

A QGraphicsProxyWidget holding a QTextEdit, so a note is BOTH a scene object (draggable, resizable by the
bottom-right corner, folded to its header band) and a real input widget (a double click on the BODY enters
edit mode). The mouse is handled manually because `ItemIsMovable` cannot work here: the proxy forwards events
to the child QTextEdit, which "eats" them for its cursor and selection, so the two modes are NORMAL (the item
moves/resizes the note, the widget holds no focus) and EDIT (`StrongFocus` on the editor; `focusOut` returns
to normal). The HEADER BAND is the grab area and the fold's door (a double click on it or its arrow): a folded
note IS the band, and its state is the additive project key `folded`, never an undo step. The body is painted
in `paint()` as a rounded rect (the editor stays transparent), because a QSS `border-radius` alone does not
clip a widget background. The tone is ONE value for every note — read live, never a per-note field.
"""
import uuid
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QEvent
from PySide6.QtGui import (QFont, QBrush, QColor, QPainter, QPainterPath,
                           QPen)
from PySide6.QtWidgets import QGraphicsProxyWidget, QTextEdit, QGraphicsItem

try:  # the central theme (palette/radii/fonts — ui/theme.py)
    from ..ui import theme
except ImportError:
    from ui import theme

try:  # the ONE QSS registry (the Qt half of the theme)
    from ..ui import theme_qss
except ImportError:
    try:
        from ui import theme_qss
    except ImportError:  # flat layout without the ui package: the editor keeps its own default
        theme_qss = None


def _t(key: str) -> str:
    """Safe i18n hook: returns the key itself when i18n is unavailable."""
    try:
        from i18n import t as _translate
        return _translate(key)
    except Exception:
        return key


class StickyNote(QGraphicsProxyWidget):
    """A note on the map: dragging, resize by the corner, a header band, the fold — text.

    An attached note can be moved (a drag does not detach it) — the anchor line follows live via
    dragUpdated → MapScene.on_note_drag_updated.
    """

    MIN_W, MIN_H = 140.0, 90.0
    MAX_W, MAX_H = 1200.0, 800.0
    CORNER_HIT = 16.0      # "grab the corner" zone for resize (px from the bottom-right)
    HEADER_H = 22.0        # the header band: the grab area, the title line and the fold's arrow
    CHEVRON_ZONE = 18.0    # the fold arrow's click zone in the band's right corner

    # The note family comes from the ACTIVE theme as a live descriptor, so ONE global tone repaints
    # every open note through the ordinary theme walk (AGENTS.md §4.6) — never a per-note field.
    BG_COLOR = theme.ThemeValue(lambda: theme.NOTE_BG)
    BORDER_COLOR = theme.ThemeValue(lambda: theme.NOTE_BORDER)
    TEXT_COLOR = theme.ThemeValue(lambda: theme.NOTE_TEXT)
    CORNER_RADIUS = theme.RADIUS_NOTE   # rounding of the note window corners

    # The band's two marks are DERIVED from the note's own frame tone (an alpha, never a literal).
    BAND_TINT_ALPHA = 38   # the band's fill over the paper
    BAND_LINE_ALPHA = 96   # the separator under it

    textEdited = Signal()  # the text changed (MainWindow marks the project dirty)
    moved = Signal()       # the note was moved with the mouse (also a dirty reason)
    attachRequested = Signal(object)  # release over a ServerNode → the window attaches the note
    detachRequested = Signal()        # fallback path; never emitted from a drag
    # live geometry during a drag (move AND resize) and after a fold, every step —
    # the scene recomputes the anchor offset and the anchor-line path of the attached note
    dragUpdated = Signal(object)  # emitted with the note itself (self)
    # the fold moved (it is SAVED, so the window marks the project dirty — it is not an undo step)
    foldChanged = Signal(bool)

    def __init__(self, text: str = "", x: float = 0.0, y: float = 0.0,
                 width: float = 240.0, height: float = 160.0, note_id: Optional[str] = None,
                 folded: bool = False):
        editor = QTextEdit()
        super().__init__()
        self.setWidget(editor)
        # the proxy's minimumSize IS the widget's minimumSizeHint (54×54 for a QTextEdit) and it
        # clamps every resize — the folded band is shorter than that, so the clamp is released here
        # and the note's OWN MIN_W/MIN_H stay the only bound (`_clamp_size`).
        self.setMinimumSize(0.0, 0.0)

        self.note_id = note_id or str(uuid.uuid4())[:8]
        # the id of the attached server (None — a free note); serialized via to_dict()
        self.server_id: Optional[str] = None
        # the note's position offset from the node anchor (top-right corner + 12 px).
        # (0,0) — the note is exactly at the anchor (a fresh attach/menu); !=0 — the user moved
        # the attached note. Driven by MapScene; not serialized — on load it is computed from the
        # stored x/y.
        self.anchor_offset: Tuple[float, float] = (0.0, 0.0)
        self._editing = False
        self._drag_mode = None  # None | "move" | "resize"
        self._drag_start_scene = None
        self._size_start: Tuple[float, float] = (width, height)
        self._moved_this_drag = False
        # the fold: the flag (the SAVED state) and the size to return to (a session snapshot —
        # the file always stores the EXPANDED geometry, so a folded note's save loses nothing)
        self._folded = bool(folded)
        self._expanded_size: Tuple[float, float] = (float(width), float(height))

        # ── Editor look (the sticker) ────────────────────────
        # the background/border/rounding is drawn by this item's paint() (see it),
        # the editor — TEXT ONLY on a transparent background. A QSS background alone
        # is not clipped to border-radius (the widget background is drawn as a square) — the
        # rounded corners "stuck out" as a square beyond the border.
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setFont(QFont(theme.FONT_UI, 10))
        # the editor's stylesheet comes from the ONE registry (ui/theme_qss.py) and is
        # re-applied by refresh_theme() — the object name is what the registry rule targets.
        editor.setObjectName("StickyNoteEditor")
        if theme_qss is not None:
            editor.setStyleSheet(theme_qss.style("note.editor"))
        else:  # a flat layout without the ui package — the colours of the note itself
            editor.setStyleSheet(
                "QTextEdit { background: transparent; color: %s;"
                " border: none; padding: 6px; }" % self.TEXT_COLOR)
        editor.setPlaceholderText(_t("note.placeholder"))
        # Normal mode: the widget does NOT take focus — the note handles the clicks
        # (move/resize), not the QTextEdit. A double click enters edit mode.
        editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # the fold is discoverable without a menu (the arrow is the second door)
        self.setToolTip(_t("note.fold.tooltip"))

        self._loading = True
        editor.setPlainText(text or "")
        self._loading = False

        editor.textChanged.connect(self._on_editor_text_changed)
        # Qt6: the focusIn/focusOut signals no longer exist on QWidget — we catch FocusOut
        # via eventFilter (exit edit mode on focus loss)
        editor.installEventFilter(self)
        self._apply_editor_margins()

        self.setPos(x, y)
        w, h = self._clamp_size(width, height)
        self.resize(w, h)
        # ItemIsSelectable — for Delete removal and highlighting; ItemIsMovable is NOT
        # set: we move it manually (see the module docstring).
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        if self._folded:
            # a note restored folded applies its state BEFORE any receiver is wired: no signal,
            # and the file's width/height are the expanded ones (the band is a drawing size)
            self._set_editor_active(False)
            self.resize(w, self.HEADER_H)
            self._apply_editor_margins()

    # ── Geometry helpers ───────────────────────────────────────

    @classmethod
    def _clamp_size(cls, w: float, h: float):
        w = max(cls.MIN_W, min(cls.MAX_W, float(w)))
        h = max(cls.MIN_H, min(cls.MAX_H, float(h)))
        return w, h

    def set_note_size(self, width: float, height: float):
        """Change the note size (bounded by MIN/MAX) — a FOLDED note has no size of its own."""
        if self._folded:
            return
        w, h = self._clamp_size(width, height)
        if abs(w - self.rect().width()) < 0.5 and abs(h - self.rect().height()) < 0.5:
            return
        self.prepareGeometryChange()
        self.resize(w, h)
        self._expanded_size = (float(w), float(h))

    def boundingRect(self) -> QRectF:
        """Explicit geometry (uniform with ServerNode; see its boundingRect)."""
        return QRectF(0, 0, self.rect().width(), self.rect().height())

    def text(self) -> str:
        return self.widget().toPlainText()

    def set_text(self, value: str):
        """Set the text without the textEdited signal (loading from a file)."""
        self._loading = True
        self.widget().setPlainText(value or "")
        self._loading = False

    # ── The header band ────────────────────────────────────────

    def band_rect(self) -> QRectF:
        """The header band — the top strip, the whole item while the note is folded."""
        return QRectF(0.0, 0.0, self.rect().width(),
                      min(self.HEADER_H, self.rect().height()))

    def chevron_rect(self) -> QRectF:
        """The fold arrow's click zone — the RIGHT corner of the band (the NodeGroup pattern)."""
        zone = min(self.CHEVRON_ZONE, self.rect().width())
        return QRectF(max(self.rect().width() - zone, 0.0), 0.0, zone, self.band_rect().height())

    def _in_band(self, local: QPointF) -> bool:
        """Is the local point inside the header band (the grab area and the fold's door)?"""
        try:
            return self.band_rect().contains(QPointF(local))
        except (TypeError, AttributeError):
            return False

    def _in_chevron(self, local: QPointF) -> bool:
        """Is the local point inside the fold arrow's click zone?"""
        try:
            return self.chevron_rect().contains(QPointF(local))
        except (TypeError, AttributeError):
            return False

    def _band_title(self) -> str:
        """The band's line: the note's FIRST non-empty line, else the placeholder sentence."""
        for line in (self.text() or "").splitlines():
            line = line.strip()
            if line:
                return line
        return _t("note.placeholder")

    def _band_font(self) -> QFont:
        """The band's font — the UI family one step under the editor's, read live."""
        return QFont(theme.FONT_UI, 8)

    def _chevron_path(self) -> QPainterPath:
        """The fold glyph: ▾ while folded ("can be unfolded") / ▴ while expanded."""
        path = QPainterPath()
        rect = self.chevron_rect()
        cx, cy = rect.center().x(), rect.center().y()
        if self._folded:
            path.moveTo(cx - 4.5, cy - 2.0)
            path.lineTo(cx + 4.5, cy - 2.0)
            path.lineTo(cx, cy + 3.5)
        else:
            path.moveTo(cx - 4.5, cy + 2.0)
            path.lineTo(cx + 4.5, cy + 2.0)
            path.lineTo(cx, cy - 3.5)
        path.closeSubpath()
        return path

    # ── The fold ───────────────────────────────────────────────

    def is_folded(self) -> bool:
        """Is the note folded to its header band?"""
        return bool(self._folded)

    @property
    def folded(self) -> bool:
        """The fold state (the persisted one — `is_folded()` in property form)."""
        return bool(self._folded)

    def set_folded(self, folded: bool) -> bool:
        """Fold or unfold the note — the ONE writer (the constructor, a double click, the arrow)."""
        return self.fold() if folded else self.unfold()

    def fold(self) -> bool:
        """Fold the note to its header band; no position moves and nothing enters the undo stack.

        The editor leaves the scene widget, the size becomes the band's and the size to return to is
        snapshotted (`_expanded_size`). The anchor, the pinned offset and the anchor line stay — a
        folded note keeps its place (`AGENTS.md` §4.2 owns the undo side).
        """
        if self._folded:
            return False
        self.exit_edit_mode()
        self._expanded_size = (self.rect().width(), self.rect().height())
        self._folded = True
        self._set_editor_active(False)
        self._resize_to(self._expanded_size[0], self.HEADER_H)
        self._apply_editor_margins()
        self._after_fold()
        return True

    def unfold(self) -> bool:
        """Unfold the note to the size it had when it folded (after a load — the file's size)."""
        if not self._folded:
            return False
        self._folded = False
        w, h = self._expanded_size
        self._resize_to(w, h)
        self._set_editor_active(True)
        self._apply_editor_margins()
        self._after_fold()
        return True

    def _after_fold(self) -> None:
        """The state changed: repaint, tell the window (dirty) and let the scene fix the anchor line."""
        self.update()
        try:
            self.foldChanged.emit(self._folded)
            self.dragUpdated.emit(self)   # the geometry moved — the anchor line is recomputed
        except RuntimeError:  # Qt teardown
            pass

    def _resize_to(self, width: float, height: float) -> None:
        """Resize the item (the geometry change first) and repaint."""
        self.prepareGeometryChange()
        self.resize(width, height)
        self.update()

    def _set_editor_active(self, active: bool) -> None:
        """Let the text layer paint or take it away — a folded note IS its band.

        The proxied WIDGET stays visible: Qt mirrors the widget's visibility onto the ITEM, so hiding
        it would leave a folded note unpainted and deaf to the mouse. The fold therefore empties the
        editor's viewport (`_apply_editor_margins`) and parks its scrollbars; unfolding restores the
        shipped "as needed" pair.
        """
        try:
            editor = self.widget()
            if editor is None:
                return
            policy = (Qt.ScrollBarPolicy.ScrollBarAsNeeded if active
                      else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            editor.setVerticalScrollBarPolicy(policy)
            editor.setHorizontalScrollBarPolicy(policy)
        except RuntimeError:  # Qt teardown
            pass

    # ── Dirty marking ──────────────────────────────────────────

    def _on_editor_text_changed(self):
        if not getattr(self, "_loading", False) and self.scene() is not None:
            self.textEdited.emit()

    # ── Edit mode (double click / focusOut) ────────────────────

    def enter_edit_mode(self):
        """Enter the text editing mode — a folded note has no body to edit."""
        if self._editing or self._folded:
            return
        self._editing = True
        ed = self.widget()
        ed.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        ed.setFocus()

    def exit_edit_mode(self):
        if not self._editing:
            return
        self._editing = False
        ed = self.widget()
        ed.clearFocus()
        ed.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    @property
    def editing(self) -> bool:
        return self._editing

    # ── Event filter (Qt6: no focusOut signal — we catch the widget event) ──

    def eventFilter(self, obj, event):
        if (self.widget() is not None and obj is self.widget()
                and event.type() == QEvent.Type.FocusOut):
            # The focus left the editor — return the note to normal mode
            self.exit_edit_mode()
        return super().eventFilter(obj, event)

    # ── Mouse handling (manual move/resize, see the docstring) ──

    def _in_corner(self, pos) -> bool:
        r = self.rect()
        return (r.width() - self.CORNER_HIT <= pos.x() <= r.width()) and \
               (r.height() - self.CORNER_HIT <= pos.y() <= r.height())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Edit mode: events — to the editor (caret/selection)
            if self._editing:
                super().mousePressEvent(event)
                return
            scene_pos = event.scenePos()
            local = self.mapFromScene(scene_pos) if scene_pos is not None else None
            if local is None or not self.rect().contains(local):
                super().mousePressEvent(event)  # a click outside the note — the standard path
                return
            self.setSelected(True)
            if self._in_chevron(local):
                # the fold's second door: checked BEFORE the move/resize branches, so a click on
                # the arrow can never start a drag
                self.set_folded(not self._folded)
                event.accept()
                return
            if not self._folded and self._in_corner(local):
                self._drag_mode = "resize"
                self._size_start = (self.rect().width(), self.rect().height())
                self._drag_start_scene = scene_pos  # the press point — the size baseline
            else:
                self._drag_mode = "move"
                self._drag_start_scene = scene_pos
            self._moved_this_drag = False
            event.accept()  # do NOT pass it to the QTextEdit — otherwise it would hijack the drag
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_mode and (event.buttons() & Qt.MouseButton.LeftButton):
            scene_pos = event.scenePos()
            if scene_pos is None:
                return
            if self._drag_mode == "move":
                delta = scene_pos - self._drag_start_scene
                if not self._moved_this_drag and abs(delta.x()) + abs(delta.y()) > 1.0:
                    self._moved_this_drag = True
                    # dragging an attached note does NOT detach it — the anchor line follows live
                self.prepareGeometryChange()
                # Incremental shift (the start is updated) — no cumulative drift
                self.setPos(self.pos() + delta)
                self._drag_start_scene = scene_pos
            else:  # resize by the bottom-right corner
                w0, h0 = self._size_start
                start_local = self.mapFromScene(self._drag_start_scene or scene_pos)
                cur_local = self.mapFromScene(scene_pos)
                if abs(cur_local.x() - start_local.x()) + abs(cur_local.y() - start_local.y()) > 1.0:
                    self.set_note_size(w0 + (cur_local.x() - start_local.x()),
                                       h0 + (cur_local.y() - start_local.y()))
            # live geometry — the scene updates the offset/line of the attached note
            try:
                self.dragUpdated.emit(self)
            except RuntimeError:  # Qt teardown
                pass
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_mode:
            mode = self._drag_mode
            self._drag_mode = None
            self._drag_start_scene = None
            if mode == "move" and self._moved_this_drag and self.scene() is not None:
                self.moved.emit()  # a move — an unsaved change
                # release over a ServerNode → attach to it. items() (not itemAt) — the note
                # itself is under the cursor, the node may be UNDER it. For an ALREADY attached
                # note this is re-attaching to ANOTHER node (server_id != node.data.id); releasing
                # over its OWN node — a no-op (the note stays where it was dragged to).
                node = self._find_node_at_release(event.scenePos())
                if node is not None and getattr(self, "server_id", None) != node.data.id:
                    try:
                        self.attachRequested.emit(node)
                    except RuntimeError:  # Qt teardown
                        pass
        super().mouseReleaseEvent(event)

    def _find_node_at_release(self, scene_pos):
        """The ServerNode under the release point (hit-test + walking parentItem).

        Duck-typing by the `data.id` attribute — without importing ServerNode (a risk of a
        circular import; only ServerNode carries self.data, see server_node.py).
        scene.items() returns ALL objects under the point — the note itself is in the list
        and is simply skipped.
        """
        if scene_pos is None:
            return None
        scene = self.scene()
        if scene is None:
            return None
        try:
            items = list(scene.items(scene_pos))
        except RuntimeError:  # Qt teardown
            return None
        for item in items:
            n = item
            while n is not None:
                data = getattr(n, "data", None)
                if data is not None and getattr(data, "id", None):
                    return n
                n = n.parentItem()
        return None

    # ── Painting ───────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        """The note body — a rounded rect, the header band, then the transparent editor.

        QGraphicsProxyWidget draws ONLY the widget image; the QSS background of the QTextEdit is
        not clipped to border-radius (the background is drawn as a square, and the corners "stuck
        out" beyond the border). Therefore: background+border here (QPainterPath), the band over it,
        the text on top (the editor, transparent, its viewport pushed below the band).
        `adjusted(1)` + a 2 px pen — the stroke is entirely inside the boundingRect.
        """
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1),
                            self.CORNER_RADIUS, self.CORNER_RADIUS)
        painter.setPen(QPen(QColor(self.BORDER_COLOR), 2))
        painter.setBrush(QBrush(QColor(self.BG_COLOR)))
        painter.drawPath(path)
        self._paint_header(painter)
        super().paint(painter, option, widget)

    def _paint_header(self, painter: QPainter):
        """The band: its tint, its separator, the elided title line and the fold arrow."""
        rect = self.rect()
        band = QPainterPath()
        band.setFillRule(Qt.FillRule.WindingFill)
        radius = self.CORNER_RADIUS
        band.addRoundedRect(QRectF(1.0, 1.0, rect.width() - 2.0, self.band_rect().height()),
                            radius, radius)
        # the squared bottom half: a rounded rect alone would notch the band's lower corners
        band.addRect(QRectF(1.0, self.band_rect().height() / 2.0, rect.width() - 2.0,
                            self.band_rect().height() / 2.0))
        tint = QColor(self.BORDER_COLOR)
        tint.setAlpha(self.BAND_TINT_ALPHA)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(tint))
        painter.drawPath(band)
        if not self._folded:
            line = QColor(self.BORDER_COLOR)
            line.setAlpha(self.BAND_LINE_ALPHA)
            painter.setPen(QPen(line, 1.0))
            painter.drawLine(QPointF(2.0, self.HEADER_H), QPointF(rect.width() - 2.0, self.HEADER_H))
        painter.setFont(self._band_font())
        painter.setPen(QPen(QColor(self.TEXT_COLOR)))
        avail = max(rect.width() - 10.0 - self.CHEVRON_ZONE, 8.0)
        title = painter.fontMetrics().elidedText(self._band_title(), Qt.TextElideMode.ElideRight,
                                                 int(avail))
        painter.drawText(QRectF(6.0, 0.0, avail, self.band_rect().height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        pen = QPen(QColor(self.TEXT_COLOR), 1.5)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawPath(self._chevron_path())

    def refresh_theme(self):
        """Re-apply the theme to the note.

        `paint()` already reads the live palette (the ONE note tone included); the EDITOR is a real
        QWidget with a QSS string, so its stylesheet has to be rebuilt from the registry, the font
        re-applied (the UI font is a theme field) and the band's reserve re-established.
        """
        try:
            editor = self.widget()
        except RuntimeError:
            return  # Qt teardown
        if editor is None:
            return
        if theme_qss is not None:
            theme_qss.refresh(editor, "note.editor")
        else:
            editor.setStyleSheet(
                "QTextEdit { background: transparent; color: %s;"
                " border: none; padding: 6px; }" % self.TEXT_COLOR)
        editor.setFont(QFont(theme.FONT_UI, 10))
        self._apply_editor_margins()
        self.update()

    def _apply_editor_margins(self):
        """Push the editor's TEXT below the band (the widget keeps the item's own size).

        The registry's `padding` stays the document's inset; this is the BAND's reserve — and while the
        note is folded the reserve is the WHOLE item, so the text layer has no viewport left to paint
        into. Re-applied after every stylesheet and after every fold resize.
        """
        try:
            editor = self.widget()
            if editor is None:
                return
            top = int(self.rect().height()) if self._folded else int(self.HEADER_H)
            editor.setViewportMargins(0, top, 0, 0)
        except (RuntimeError, AttributeError):  # Qt teardown / an editor that is not a scroll area
            pass

    def mouseDoubleClickEvent(self, event):
        """Double click: the BAND folds or unfolds, the BODY enters the editing mode.

        The band is the fold's own door (its arrow is the other), so the "a double click edits" rule
        belongs to the body; a folded note has no body and always unfolds.
        """
        local = self.mapFromScene(event.scenePos()) if event.scenePos() is not None else None
        inside = local is not None and self.rect().contains(local)
        if inside and self._in_band(local):
            self.set_folded(not self._folded)
            event.accept()
            return
        if self._editing:
            # Already editing — a regular double click in the text (selecting a word)
            super().mouseDoubleClickEvent(event)
            return
        if inside:
            self.enter_edit_mode()
            # Pass it on — the caret will land under the cursor
        super().mouseDoubleClickEvent(event)

    # ── Hover: cursors (drag / resize corner / band / arrow) ────

    def hoverMoveEvent(self, event):
        if not self._editing and event.scenePos() is not None:
            local = self.mapFromScene(event.scenePos())
            if local is not None and self.rect().contains(local):
                if self._in_chevron(local):
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                elif self._in_band(local):
                    self.setCursor(Qt.CursorShape.OpenHandCursor)  # the grab area
                elif not self._folded and self._in_corner(local):
                    self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                else:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverMoveEvent(event)

    def hoverEnterEvent(self, event):
        if not self._editing:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    # ── Serialization (the "notes" array in the project JSON) ───

    def to_dict(self) -> dict:
        """The project record — always the EXPANDED geometry, so a folded note loses no size.

        `folded` is written only while folded (the additive-key rule: a map of unfolded notes carries
        no new key, and `VERSION_FORMAT` stays "0.9").
        """
        if self._folded:
            width, height = self._expanded_size
        else:
            width, height = float(self.rect().width()), float(self.rect().height())
        d = {
            "id": self.note_id,
            "text": self.text(),
            "x": float(self.pos().x()),
            "y": float(self.pos().y()),
            "width": width,
            "height": height,
        }
        # the key is written ONLY when set — clean files for free notes;
        # older app versions simply do not read an unknown key
        if getattr(self, "server_id", None):
            d["server_id"] = str(self.server_id)
        if self._folded:
            d["folded"] = True
        return d

    @classmethod
    def from_dict(cls, raw: dict) -> "StickyNote":
        """Create a note from a JSON entry (extra/corrupt keys — defaults)."""
        try:
            x = float(raw.get("x") or 0.0)
            y = float(raw.get("y") or 0.0)
            w = float(raw.get("width") or 240.0)
            h = float(raw.get("height") or 160.0)
        except (TypeError, ValueError):
            x, y, w, h = 0.0, 0.0, 240.0, 160.0
        note_id = str(raw.get("id") or "")[:8] or None
        return cls(
            text=str(raw.get("text") or ""),
            x=x, y=y, width=w, height=h, note_id=note_id,
            folded=bool(raw.get("folded")),
        )
