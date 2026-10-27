# -*- coding: utf-8 -*-
"""v1.14.1.3 — THE FIND BAR, CLOSED: the empty bar, the step that outran the scan, the one name.
§1 a bar with NO query says nothing (`ViewerFindBar._count` starts at `(0, None)`); §2 a step FLUSHES
a pending debounced pass instead of walking the previous query's list; §3 `_viewer_find_more` is
pane-owned state (`SftpTab.PANE_STATE`); §4 the release pins. Rule — `AGENTS.md` §4.15; mechanism —
`DOCUMENTATION.md` §14f. Run: python tests/test_followups_v11413.py
"""
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.sftp_pane_verbs as SVV  # noqa: E402
import modules.sftp_tab as ST  # noqa: E402
import modules.terminal_find_bar as TFB  # noqa: E402
import version  # noqa: E402

LANGS = load_i18n_langs(ROOT)


def make_pane():
    """A bare Files container with ONE pane (no worker, no session) — the widget-level seam."""
    tab = ST.SftpTab()
    return tab, tab._active_pane


def fill(pane, text, path="/tmp/notes.txt"):
    """Put `text` in the reader through the shipped show path (no worker needed)."""
    pane._show_viewer(path, len(text.encode("utf-8")), text)


def label(pane):
    """The counter's text (`""` — no sentence at all)."""
    return pane._viewer_find_bar.count_label.text()


def lines(path):
    """The lines of one module — the size pins the slot states."""
    with open(path, encoding="utf-8") as handle:
        return len(handle.read().splitlines())


# ════════════════════════════════════════════════════════════════════════════
print("== §1 a bar with NO query says NOTHING (`0` is a query that found nothing) ==")
# ════════════════════════════════════════════════════════════════════════════

clear_cfg()
bar = SVV.ViewerFindBar()
check("§1 a FRESH bar starts at the empty state, not at \"No matches\"",
      bar._count == (0, None) and bar.count_label.text() == "",
      f"{bar._count} label={bar.count_label.text()!r}")
bar.retranslate()
check("§1 ...and a re-text (a language switch) keeps it silent (the constructor's own walk)",
      bar.count_label.text() == "" and bar._count == (0, None),
      repr(bar.count_label.text()))
check("§1 the bar holds ONE state field (no second \"is there a query\" flag)",
      "_count" in vars(bar) and not any(name in vars(bar) for name in
                                        ("_count_state", "_has_query", "_empty")),
      str(sorted(vars(bar))))
check("§1 `set_count()` is the ONE reading: `None` — silence, `0` — no hit, `N` — the count",
      (bar.set_count(0, None), bar.count_label.text()) == (None, "")
      and (bar.set_count(0, 0), bar.count_label.text()) == (None, i18n.t("search.no_results"))
      and (bar.set_count(3, 5), bar.count_label.text()) == (None, i18n.t("sftp.find.count",
                                                                        cur=3, total=5)),
      repr(bar.count_label.text()))
check("§1 the sibling terminal bar declares the same shape (ONE `None` — not a second rule)",
      TFB.TerminalFindBar()._count_state is None, "the terminal find bar's pin")

tab, pane = make_pane()
fill(pane, "alpha one\nbeta two\n")
pane.open_viewer_find()
check("§1 the first `Ctrl+F` over a file with no selection and an empty field says nothing",
      pane.viewer_find_active and pane._viewer_find_bar.query_edit.text() == ""
      and label(pane) == "" and pane._viewer_find_bar._count == (0, None),
      f"{pane.viewer_find_state()} label={label(pane)!r}")
check("§1 ...while a query that really found nothing still says `No matches`",
      (pane._on_viewer_find_query("zzz-not-there") or True)
      and label(pane) == i18n.t("search.no_results")
      and pane._viewer_find_bar._count == (0, 0),
      f"{pane.viewer_find_state()} label={label(pane)!r}")
pane._viewer_find_bar.query_edit.setText("")   # a keystroke: the debounce is armed, nothing ran
pane.viewer_find_next()                        # the step flushes the pending pass (§2)
check("§1 ...and an EMPTIED field goes back to silence (a query that no longer exists says nothing)",
      label(pane) == "" and pane._viewer_find_bar._count == (0, None)
      and pane.viewer_find_state()["total"] == 0,
      f"{pane.viewer_find_state()} label={label(pane)!r}")
tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §2 a step FLUSHES the pending scan (Enter walks the query the field shows) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the debounce is unchanged (the step was fixed, not the scan)",
      SVV.VIEWER_FIND_DEBOUNCE_MS == 180, str(SVV.VIEWER_FIND_DEBOUNCE_MS))
tab, pane = make_pane()
fill(pane, "alpha one\nbeta two\nalpha three\nbeta four\nbeta five\n", path="/tmp/find.txt")
pane.open_viewer_find()
pane._on_viewer_find_query("alpha")            # a DOOR: the list is alpha's two hits
check("§2 the door built the list of the query it searched",
      pane.viewer_find_state() == {"query": "alpha", "current": 1, "total": 2},
      str(pane.viewer_find_state()))
pane._viewer_find_bar.query_edit.setText("beta")   # ONE keystroke: the query moves, the list waits
check("§2 the keystroke leaves the PREVIOUS list in place while the debounce waits",
      pane._viewer_find_timer.isActive()
      and pane.viewer_find_state() == {"query": "beta", "current": 1, "total": 2},
      f"{pane.viewer_find_state()} timer={pane._viewer_find_timer.isActive()}")
_PASSES = []
_orig_refresh = pane._refresh_viewer_find_matches


def _counted_refresh():
    _PASSES.append(1)
    return _orig_refresh()


pane._refresh_viewer_find_matches = _counted_refresh
try:
    stepped = pane.viewer_find_next()
    check("§2 `Enter` inside the window runs the pending pass and steps through ITS list",
          stepped is True
          and pane.viewer_find_state() == {"query": "beta", "current": 2, "total": 3}
          and pane.viewer_text.textCursor().selectedText() == "beta",
          f"{pane.viewer_find_state()} sel={pane.viewer_text.textCursor().selectedText()!r}")
    check("§2 ...ONE pass, and the timer stopped waiting (the step is not a second scan)",
          _PASSES == [1] and pane._viewer_find_timer.isActive() is False,
          f"passes={len(_PASSES)} timer={pane._viewer_find_timer.isActive()}")
    _PASSES.clear()
    check("§2 a step with NOTHING pending walks the shipped list and runs no pass",
          pane.viewer_find_next() is True and _PASSES == []
          and pane.viewer_find_state()["current"] == 3,
          f"passes={len(_PASSES)} {pane.viewer_find_state()}")
    pane._on_viewer_find_query("beta")         # three hits again
    pane._viewer_find_bar.query_edit.setText("zzz-not-there")
    check("§2 the defect's shape: the field's query has no hit while the old list has three",
          pane.viewer_find_state() == {"query": "zzz-not-there", "current": 1, "total": 3},
          str(pane.viewer_find_state()))
    check("§2 ...so the step answers FALSE and says `No matches` — never a count of another query",
          pane.viewer_find_next() is False and pane.viewer_find_state()["total"] == 0
          and label(pane) == i18n.t("search.no_results"),
          f"{pane.viewer_find_state()} label={label(pane)!r}")
    _PASSES.clear()
    pane._viewer_find_bar.query_edit.setText("alpha")
    check("§2 `Shift+Enter` flushes by the SAME rule (wraparound over the new list)",
          pane.viewer_find_prev() is True
          and pane.viewer_find_state() == {"query": "alpha", "current": 2, "total": 2}
          and _PASSES == [1],
          f"{pane.viewer_find_state()} passes={len(_PASSES)}")
finally:
    pane._refresh_viewer_find_matches = _orig_refresh
tab.release()

tab, pane = make_pane()
fill(pane, "one alpha two\n", path="/tmp/bare.txt")
pane.open_viewer_find()
pane._viewer_find_timer = None              # the declared fallback: no timer at all
check("§2 a pane with no debounce timer still steps (the flush is a no-op, never an error)",
      pane._flush_viewer_find_scan() is None
      and pane._on_viewer_find_query("alpha") is None
      and pane.viewer_find_next() is True
      and pane.viewer_find_state() == {"query": "alpha", "current": 1, "total": 1},
      str(pane.viewer_find_state()))
tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §3 `_viewer_find_more` is PANE state (`SftpTab.PANE_STATE`) ==")
# ════════════════════════════════════════════════════════════════════════════

_FIND_STATE = ("_viewer_find_matches", "_viewer_find_current", "_viewer_find_query",
               "_viewer_find_more")
check("§3 the flag joins the find state of `SftpTab.PANE_STATE`",
      "_viewer_find_more" in ST.SftpTab.PANE_STATE,
      str([name for name in _FIND_STATE if name not in ST.SftpTab.PANE_STATE]))
check("§3 ...beside its three siblings (the find row is ONE family)",
      all(name in ST.SftpTab.PANE_STATE for name in _FIND_STATE), str(_FIND_STATE))
tab, pane = make_pane()
check("§3 the pane owns the flag (the container starts with no copy of it)",
      pane._viewer_find_more is False and "_viewer_find_more" not in tab.__dict__,
      str(sorted(vars(tab))[:6]))
tab._viewer_find_more = True
check("§3 a WRITE through the container lands on the ACTIVE pane (the `_blocked` rule)",
      pane._viewer_find_more is True and "_viewer_find_more" not in tab.__dict__
      and tab._viewer_find_more is True,
      f"pane={pane._viewer_find_more} tab-copy={'_viewer_find_more' in tab.__dict__}")
fill(pane, "a a a\n", path="/tmp/three-a.txt")
pane.open_viewer_find()
_MAX = SVV.VIEWER_FIND_MATCH_MAX
try:
    SVV.VIEWER_FIND_MATCH_MAX = 2
    pane._on_viewer_find_query("a")
    check("§3 the pass computes the flag over the bound and the counter says `2+`",
          pane._viewer_find_more is True and label(pane).endswith("/ 2+"),
          f"{pane.viewer_find_state()} label={label(pane)!r}")
    tab._viewer_find_more = False             # a write through the CONTAINER
    pane._sync_viewer_find_counter()
    check("§3 ...and a write through the container is the flag the counter reads (one truth)",
          pane._viewer_find_more is False and label(pane).endswith("/ 2")
          and "_viewer_find_more" not in tab.__dict__,
          f"label={label(pane)!r} pane={pane._viewer_find_more}")
finally:
    SVV.VIEWER_FIND_MATCH_MAX = _MAX
tab.release()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 i18n and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
check(f"§4 the patch adds NO i18n key (parity stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1193 + 3 + 2, str(EXPECTED_I18N_KEYS))
check("§4 the pin names this release's line and the schema did NOT move",
      releases_at_least(EXPECTED_APP_VERSION, "1.14.1.3") and version.VERSION_FORMAT == "0.9",
      f"{EXPECTED_APP_VERSION} / {version.VERSION_FORMAT}")
check("§4 the slot's two modules keep their sizes (the flag rides an existing row)",
      lines(SVV.__file__) < 900 and lines(ST.__file__) == 1170,
      f"{lines(SVV.__file__)} / {lines(ST.__file__)}")
finish()
