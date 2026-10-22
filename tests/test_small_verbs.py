# -*- coding: utf-8 -*-
"""`v1.14` — THE SMALL VERBS: the bookmarks FRAME, the filter's clear act and the pane's `Find text`.
§1 the PURE frame geometry (`selection_frame_rect()`); §2 the painted row — a selection is a FRAME and
never a fill, measured on the pixmap under both themes; §3 the filter — the clear button and `Esc` are
ONE act; §4 the `Find text` button — its label, its tooltip, the row it joins and the provider gate;
§5 the one new i18n key and the release state.
Rule — `AGENTS.md` §4.23, §4.3.6; mechanism — `DOCUMENTATION.md` §57, §59.
"""
import os
import sys

from _common import (EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtCore import QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QPainter, QPixmap  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QWidget  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
from modules.sftp_tab import SftpTab  # noqa: E402
from modules.sftp_worker import SftpWorker  # noqa: E402
from ui import theme, theme_qss  # noqa: E402
from ui.bookmark_panel import (BookmarkPanel, SELECTION_FRAME_WIDTH,  # noqa: E402
                               _BookmarkRowDelegate, selection_frame_rect)

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the PURE frame geometry: the row's inset plus half the pen ==")
# ════════════════════════════════════════════════════════════════════════════

ROW = QRectF(0.0, 0.0, 260.0, float(BookmarkPanel.ROW_H))
FRAME = selection_frame_rect(ROW)
INSET = float(BookmarkPanel.ROW_INSET) + float(SELECTION_FRAME_WIDTH) / 2.0
check("§1 the pen is the declared 1.5 px and the frame is the row inset by `ROW_INSET` + half the pen",
      abs(float(SELECTION_FRAME_WIDTH) - 1.5) < 1e-9
      and abs(FRAME.left() - INSET) < 1e-9 and abs(FRAME.top() - INSET) < 1e-9
      and abs(FRAME.width() - (ROW.width() - 2.0 * INSET)) < 1e-9
      and abs(FRAME.height() - (ROW.height() - 2.0 * INSET)) < 1e-9,
      f"frame={FRAME} inset={INSET}")
check("§1 the frame is CONCENTRIC with the row (all four margins are one margin)",
      abs((FRAME.left() - ROW.left()) - (ROW.right() - FRAME.right())) < 1e-9
      and abs((FRAME.top() - ROW.top()) - (ROW.bottom() - FRAME.bottom())) < 1e-9,
      f"{FRAME.left()} {ROW.right() - FRAME.right()}")
check("§1 a WIDER pen moves the frame INWARD and never over the row's edge (the stroke stays inside)",
      selection_frame_rect(ROW, 3.0).left() > FRAME.left()
      and ROW.contains(selection_frame_rect(ROW, 3.0))
      and ROW.contains(selection_frame_rect(ROW, 0.0)),
      f"{selection_frame_rect(ROW, 3.0)}")
check("§1 a zero / negative pen answers the row inset by `ROW_INSET` alone (no half to keep inside)",
      selection_frame_rect(ROW, 0.0).left() == float(BookmarkPanel.ROW_INSET)
      and selection_frame_rect(ROW, -4.0).left() == float(BookmarkPanel.ROW_INSET))
check("§1 a row too narrow for both insets collapses to ONE pixel, never to a negative width",
      selection_frame_rect(QRectF(0.0, 0.0, 2.0, 2.0)).width() == 1.0
      and selection_frame_rect(QRectF(0.0, 0.0, 2.0, 2.0)).height() == 1.0)
check("§1 the frame follows the ROW's origin (a scrolled or offset rect is not assumed to start at 0)",
      abs(selection_frame_rect(QRectF(40.0, 90.0, 200.0, 34.0)).left() - (40.0 + INSET)) < 1e-9
      and abs(selection_frame_rect(QRectF(40.0, 90.0, 200.0, 34.0)).top() - (90.0 + INSET)) < 1e-9)


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the painted row: a FRAME and never a fill ==")
# ════════════════════════════════════════════════════════════════════════════

HOST = QWidget()
PANEL = BookmarkPanel(HOST)
PANEL.set_entries([{"name": "Wiki", "value": "https://w.example"},
                   {"name": "Grafana", "value": "https://mon.example.com:3000"},
                   {"name": "Kibana", "value": "https://logs.example.com"}])
ROW_RECT = QRect(0, 0, PANEL.width() - 2 * PANEL.PADDING, BookmarkPanel.ROW_H)


def paint_row(selected: bool):
    """Paint the FIRST row through the panel's OWN delegate; answer (image, frame rect, option)."""
    view = PANEL.list
    option = QStyleOptionViewItem()
    option.initFrom(view)
    option.widget = view
    option.rect = ROW_RECT
    if selected:
        option.state |= QStyle.StateFlag.State_Selected
    pixmap = QPixmap(ROW_RECT.size())
    pixmap.fill(view.palette().base().color())   # the fill the VIEW paints under a row
    painter = QPainter(pixmap)
    try:
        view.itemDelegate().paint(painter, option, view.model().index(0, 0))
    finally:
        painter.end()
    return pixmap.toImage(), selection_frame_rect(option.rect), option


def _band_hits(image_a, image_b, frame) -> list:
    """The pixels where two paints differ OUTSIDE the frame's stroke band ([] when the frame is all)."""
    outer = frame.adjusted(-SELECTION_FRAME_WIDTH, -SELECTION_FRAME_WIDTH,
                           SELECTION_FRAME_WIDTH, SELECTION_FRAME_WIDTH)
    inner = frame.adjusted(SELECTION_FRAME_WIDTH, SELECTION_FRAME_WIDTH,
                           -SELECTION_FRAME_WIDTH, -SELECTION_FRAME_WIDTH)
    out = []
    for y in range(image_a.height()):
        for x in range(image_a.width()):
            if image_a.pixel(x, y) == image_b.pixel(x, y):
                continue
            centre_x, centre_y = x + 0.5, y + 0.5
            if not outer.contains(centre_x, centre_y) or inner.contains(centre_x, centre_y):
                out.append((x, y))
    return out


for _instance, _name in ((theme.DARK, "DARK"), (theme.LIGHT, "LIGHT")):
    theme_qss.apply_theme(_instance, app=app, refresh_windows=False)
    _plain, _plain_frame, _option = paint_row(False)
    _selected, _frame, _ = paint_row(True)
    _base = PANEL.list.palette().base().color().name()
    _highlight = _option.palette.highlight().color().name()
    _sample = (2, BookmarkPanel.ROW_H // 2)
    check(f"§2 {_name}: a SELECTED row keeps the row's own background (the selection paints no fill)",
          _selected.pixelColor(*_sample).name() == _base
          and _plain.pixelColor(*_sample).name() == _base
          and _frame == _plain_frame,
          f"{_selected.pixelColor(*_sample).name()} vs {_base}")
    check(f"§2 {_name}: the two paints differ ONLY along the frame's stroke (its ink is the whole delta)",
          _plain.pixelColor(*_sample).name() == _selected.pixelColor(*_sample).name()
          and not _band_hits(_plain, _selected, _frame),
          str(_band_hits(_plain, _selected, _frame)[:4]))
    _ink = {_selected.pixelColor(x, BookmarkPanel.ROW_H // 2).name()
            for x in range(int(_frame.left()) - 2, int(_frame.left()) + 3)}
    check(f"§2 {_name}: the frame is drawn in the palette's highlight (a 1.5 px rectangle)",
          _highlight in _ink and _ink != {_base}, f"ink={sorted(_ink)} highlight={_highlight}")
    _unselected_highlight = {_plain.pixelColor(x, y).name()
                             for y in range(BookmarkPanel.ROW_H) for x in range(0, 12)}
    check(f"§2 {_name}: an UNSELECTED row carries no frame at all",
          _highlight not in _unselected_highlight, str(sorted(_unselected_highlight)))
theme_qss.apply_theme(theme.DARK, app=app, refresh_windows=False)
check("§2 the panel uses the SHIPPED delegate for its list (one delegate, one row shape)",
      isinstance(PANEL.list.itemDelegate(), _BookmarkRowDelegate))


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the filter: the clear button and `Esc` are ONE act ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 the filter field carries the clear button", PANEL.filter.isClearButtonEnabled() is True)
PANEL.filter.setText("graf")
check("§3 a query filters the rows through the shipped policy",
      PANEL.row_count() == 1 and PANEL.rows_text() == [("Grafana", "https://mon.example.com:3000")],
      str(PANEL.rows_text()))
PANEL.filter.setText("nothing-matches-this")
check("§3 ...and a query that keeps nothing says so", PANEL.message_key() == "bookmarks.no_matches")
PANEL.filter.setText("graf")
QTest.keyClick(PANEL.filter, Qt.Key.Key_Escape)
check("§3 `Esc` empties the query and brings every row back (the clear button's act)",
      PANEL.filter.text() == "" and PANEL.row_count() == 3
      and PANEL.message_key() == "", f"{PANEL.filter.text()!r} rows={PANEL.row_count()}")
QTest.keyClick(PANEL.filter, Qt.Key.Key_Escape)
check("§3 `Esc` on an empty query changes nothing (it is not a second state)",
      PANEL.filter.text() == "" and PANEL.row_count() == 3)
PANEL.filter.setText("kib")
check("§3 the clear BUTTON empties the same query through the same signal",
      PANEL.row_count() == 1)
PANEL.filter.clear()
check("§3 ...and the rows come back on it too", PANEL.filter.text() == "" and PANEL.row_count() == 3)


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the `Find text` button: the shipped verb as a control of the row ==")
# ════════════════════════════════════════════════════════════════════════════

FS = FakeSftpFS()
for _directory in ("/srv", "/srv/app"):
    FS.add_dir(_directory)
FS.add_file("/srv/app/main.py", b"import os\n# needle here\nprint('needle')\n")


def make_tab(fs=None):
    """(tab, worker, messages) over the fake SFTP surface — the shipped stack."""
    tab = SftpTab()
    messages = []
    tab.message.connect(messages.append)
    worker = None
    if fs is not None:
        worker = SftpWorker(FakeSftpClient(fs))
        wire_worker(worker, EventLog())
        worker.start()
        tab.set_worker(worker)
    return tab, worker, messages


BARELESS, _no_worker, _ = make_tab()
check("§4 a pane with no provider keeps the search button INACTIVE (the shipped waiting row)",
      BARELESS.btn_find.isEnabled() is False and BARELESS.btn_find.isVisibleTo(BARELESS))
TAB, WORKER, MESSAGES = make_tab(FS)
PANE = TAB.panes[0]
wait_for(lambda: PANE.tree.topLevelItemCount() >= 1, timeout_ms=5000)
_BAR = PANE.buttons_bar.layout()
check("§4 the button carries the shipped verb and its own tooltip",
      PANE.btn_find.text() == i18n.t("sftp.search.row")
      and PANE.btn_find.toolTip() == i18n.t("sftp.search.tooltip"),
      f"{PANE.btn_find.text()!r} / {PANE.btn_find.toolTip()!r}")
check("§4 it is ENABLED with the provider (the same rule as `Refresh`)",
      PANE.btn_find.isEnabled() is True and PANE.btn_refresh.isEnabled() is True)
check("§4 it belongs to the ONE row widget, so the SECOND pane still hides the whole row as a unit",
      PANE.buttons_bar.isAncestorOf(PANE.btn_find)
      and _BAR.indexOf(PANE.btn_find) == _BAR.indexOf(PANE.btn_refresh) + 1
      and _BAR.itemAt(_BAR.indexOf(PANE.btn_find) + 1).spacerItem() is not None,
      f"index={_BAR.indexOf(PANE.btn_find)}")
check("§4 the row still ends with the operations (the stretch sits between the two groups)",
      _BAR.indexOf(PANE.btn_upload) > _BAR.indexOf(PANE.btn_find)
      and _BAR.indexOf(PANE.btn_cancel) == _BAR.count() - 1)

_ASKED = []


def _fake_ask():
    """The query-dialog seam: ONE subtree query over the directory on the screen."""
    _ASKED.append(1)
    return {"needle": "needle", "scope": "subtree"}


PANE._ask_search_query = _fake_ask
TAB.btn_find.click()
_RAN = wait_for(lambda: (PANE._search or {}).get("done"), timeout_ms=20000)
check("§4 a click goes through the SAME door as the row menu (the query dialog, then the walk)",
      _ASKED == [1] and _RAN is True and PANE.search_report.get("matches") == 2,
      str(PANE.search_report))
check("§4 ...and the results take the reader's slot (ONE panel at a time)",
      PANE.search_open is True and PANE.panel_in_slot() is PANE.search_panel)
del PANE._ask_search_query
TAB.close_preview()

TAB.retranslate()
check("§4 `retranslate()` re-texts the button and its tooltip in the active language",
      PANE.btn_find.text() == i18n.t("sftp.search.row")
      and PANE.btn_find.toolTip() == i18n.t("sftp.search.tooltip"))
TAB.set_worker(None)
check("§4 a transport that goes away deactivates it again (the row follows the provider)",
      TAB.btn_find.isEnabled() is False)


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the one new key and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

NEW_KEY = "sftp.search.tooltip"
check(f"§5 `{NEW_KEY}` is present and non-empty in EVERY language",
      all(str(LANGS[code].get(NEW_KEY) or "").strip() for code in LANGS),
      str([code for code in sorted(LANGS) if not LANGS[code].get(NEW_KEY)]))
check("§5 ...and it is really TRANSLATED, not the English copy",
      len({LANGS[code][NEW_KEY] for code in LANGS}) == len(LANGS),
      str({code: LANGS[code].get(NEW_KEY) for code in sorted(LANGS)}))
_SOURCES = "".join(open(os.path.join(ROOT, "modules", name), encoding="utf-8").read()
                   for name in ("sftp_pane_assembly.py", "sftp_tab.py"))
check("§5 ...and the code really READS it (a key nobody reads is dead weight)",
      NEW_KEY in _SOURCES and "sftp.search.row" in _SOURCES)
for _code in sorted(LANGS):
    check(f"§5 {_code}: the parity pin counts the one new key ({EXPECTED_I18N_KEYS})",
          len([key for key in LANGS[_code] if key not in ("name", "partial")])
          == EXPECTED_I18N_KEYS,
          str(len([key for key in LANGS[_code] if key not in ("name", "partial")])))
check_release_state(ROOT)
check("§5 the JSON schema did NOT move (nothing is persisted by this release)",
      __import__("version").VERSION_FORMAT == "0.9")
check_i18n_parity(LANGS)
check_i18n_format(LANGS)

try:
    BARELESS.release()
except Exception:  # noqa: BLE001 — the teardown must never fail the file
    pass
try:
    TAB.release()
except Exception:  # noqa: BLE001 — the teardown must never fail the file
    pass
if WORKER is not None:
    WORKER.shutdown()
PANEL.deleteLater()
HOST.deleteLater()
finish()
