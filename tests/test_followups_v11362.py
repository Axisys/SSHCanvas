# -*- coding: utf-8 -*-
"""`v1.13.6.2` — the search that SAYS what it cut: the cap with the read, the per-file sentence and the dropped run.
§1 the PURE engine (`modules/sftp_search.py`): `allow_read()` records the budget, `match_lines()` peeks the
next hit and `files_cut` counts the capped files; §2 the walk decodes a CUT read as the encoding it really
is and reports the per-file cap ONCE per run; §3 a provider rebind DROPS the run (no task map outlives it);
§4 the four search names of `SftpTab.PANE_STATE`; §5 the key and the release.
Rule — `AGENTS.md` §4.3.6, §4.15; mechanism — `DOCUMENTATION.md` §14f.
"""
import os
import re
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, finish, load_i18n_langs,
                     releases_at_least, wait_for)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import i18n  # noqa: E402
import modules.sftp_pane_helpers as PH  # noqa: E402
import modules.sftp_search as SEARCH  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
from modules.sftp_tab import SftpTab  # noqa: E402
from modules.sftp_worker import SftpWorker  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def placeholders(value) -> set:
    """The `{name}` placeholders of ONE sentence — the parity rule read off the text."""
    return set(PLACEHOLDER.findall(str(value or "")))


def make_tab(fs):
    """(tab, worker, messages) over the fake SFTP surface — the shipped stack."""
    tab = SftpTab()
    messages = []
    tab.message.connect(messages.append)
    worker = SftpWorker(FakeSftpClient(fs))
    wire_worker(worker, EventLog())
    worker.start()
    tab.set_worker(worker)
    return tab, worker, messages


def run_search(pane_obj, query, limits=None, ms=20000):
    """Drive ONE search of `pane_obj` to its end and answer the report."""
    pane_obj._start_search(query, limits=limits)
    wait_for(lambda: (pane_obj._search or {}).get("done"), timeout_ms=ms)
    return pane_obj.search_report


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the PURE engine — the budget that is SAID and the per-file cap that is PEEKED ==")
# ════════════════════════════════════════════════════════════════════════════

_whole = SEARCH.SearchReport(SEARCH.normalize_query("x"), max_bytes=100)
check("§1 a read the budget answers WHOLE records no bound",
      _whole.allow_read(64) == 64 and _whole.note_read(10) == 10
      and _whole.cut is False and _whole.cut_reason == "", str(_whole.as_dict()))
_short = SEARCH.SearchReport(SEARCH.normalize_query("x"), max_bytes=100)
check("§1 a read the budget cuts SHORT answers the rest AND records `CUT_BYTES` (N142b)",
      _short.note_read(60) == 60 and _short.allow_read(1000) == 40
      and _short.cut is True and _short.cut_reason == SEARCH.CUT_BYTES, str(_short.as_dict()))
_spent = SEARCH.SearchReport(SEARCH.normalize_query("x"), max_bytes=10)
check("§1 ...a spent budget still answers 0, and the FIRST bound stays the one reported",
      _spent.note_read(10) == 10 and _spent.allow_read(64) == 0 and _spent.allow_read(64) == 0
      and _spent.cut_reason == SEARCH.CUT_BYTES, str(_spent.as_dict()))

_rows, _cut = SEARCH.match_lines("hit\n" * 3, "hit", limit=3)
check("§1 a file that carries EXACTLY the cap is whole — `cut` is False (N144a)",
      len(_rows) == 3 and _cut is False and _rows[-1] == (3, "hit"), str((_rows, _cut)))
_rows, _cut = SEARCH.match_lines("hit\n" * 4, "hit", limit=3)
check("§1 ...and ONE hit past the cap is PEEKED, so the flag is the file's own answer",
      len(_rows) == 3 and _cut is True and [number for number, _text in _rows] == [1, 2, 3],
      str((_rows, _cut)))
check("§1 the per-file bound itself did not move (50 rows, the declared ceiling)",
      SEARCH.MATCHES_PER_FILE == 50, str(SEARCH.MATCHES_PER_FILE))

_report = SEARCH.SearchReport(SEARCH.normalize_query("hit"))
check("§1 a fresh run has counted no capped file",
      _report.files_cut == 0 and _report.as_dict()["files_cut"] == 0, str(_report.as_dict()))
_report.note_file_cut()
_report.note_file_cut()
check("§1 `note_file_cut()` counts the files whose hits ran past the cap — and stops no walk",
      _report.files_cut == 2 and _report.as_dict()["files_cut"] == 2 and _report.cut is False,
      str(_report.as_dict()))
check("§1 the report's dict carries the per-file counter beside the shipped five",
      {"files_cut", "files_scanned", "files_matched", "bytes_read", "matches"}
      <= set(_report.as_dict()), str(sorted(_report.as_dict())))
_counted = SEARCH.SearchReport(SEARCH.normalize_query("hit"))
_counted.note_matches([(1, "hit")])
_counted.note_matches([])
check("§1 a file is counted as MATCHED once per answer, and an empty answer is no file at all",
      _counted.files_matched == 1 and _counted.matches == 1 and _counted.cut is False,
      str(_counted.as_dict()))

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the walk — a CUT read keeps its encoding and the per-file cap is said once ==")
# ════════════════════════════════════════════════════════════════════════════

CYR = "привет мир\nneedle\n"
FS = FakeSftpFS()
FS.add_dir("/cyr")
FS.add_file("/cyr/note.txt", CYR.encode("utf-8"))
FS.add_dir("/hits")
FS.add_file("/hits/many.txt", ("hit line\n" * 55).encode("utf-8"))
FS.add_file("/hits/two.txt", ("hit\n" * 55).encode("utf-8"))
FS.add_file("/hits/exact.txt", ("hit\n" * 50).encode("utf-8"))
FS.add_dir("/exact")
FS.add_file("/exact/exact.txt", ("hit\n" * 50).encode("utf-8"))

tab, worker, messages = make_tab(FS)
tab.set_session_info(key="cut-session", label="Fake", host="192.0.2.20", port=22)
pane = tab.panes[0]
wait_for(lambda: pane.tree.topLevelItemCount() >= 1, timeout_ms=5000)

_raw = CYR.encode("utf-8")[:14]
check("§2 a read cut inside a multi-byte character falls back to latin-1 WITHOUT the fact (N142a)",
      PH.decode_text(_raw)[1] == "latin-1" and "привет" not in PH.decode_text(_raw)[0],
      f"{PH.decode_text(_raw)[1]}: {PH.decode_text(_raw)[0]!r}")
check("§2 ...and the SAME bytes read as a CUT tail stay UTF-8 and keep the needle",
      PH.decode_text(_raw, truncated=True)[1] == "utf-8"
      and "привет" in PH.decode_text(_raw, truncated=True)[0],
      f"{PH.decode_text(_raw, truncated=True)[1]}: {PH.decode_text(_raw, truncated=True)[0]!r}")

pane._relist("/cyr")
wait_for(lambda: pane.current_dir == "/cyr" and pane.tree.topLevelItemCount() >= 1,
         timeout_ms=5000)
_cyr = run_search(pane, {"needle": "привет", "scope": "here"}, limits={"max_bytes": 14})
check("§2 the walk DECODES the cut read as UTF-8 — the needle is found (N142a)",
      _cyr["matches"] == 1 and _cyr["bytes_read"] == 14, str(_cyr))
check("§2 ...and the row carries the line the cut really HELD, never mojibake",
      [row[2] for row in pane.search_rows()] == ["привет"], str(pane.search_rows()))
check("§2 ...the run NAMES the budget that stopped it, instead of 'no matches' (N142b)",
      _cyr["cut"] is True and _cyr["cut_reason"] == SEARCH.CUT_BYTES
      and i18n.t("sftp.search.cut_bytes", limit=STAB.format_size(14)) in messages
      and i18n.t("sftp.search.none", needle="привет") not in messages, str(messages[-3:]))
tab.close_preview()

pane._relist("/hits")
wait_for(lambda: pane.current_dir == "/hits" and pane.tree.topLevelItemCount() >= 3,
         timeout_ms=5000)
messages.clear()
_many = run_search(pane, {"needle": "hit", "scope": "here"})
_capped_text = i18n.t("sftp.search.file_cut", limit=SEARCH.MATCHES_PER_FILE)
check("§2 a file over the cap carries its first 50 rows and the run COUNTS it (N144b)",
      _many["matches"] == 150 and _many["files_matched"] == 3 and _many["files_cut"] == 2
      and _many["cut"] is False, str(_many))
check("§2 ...the panel really holds those rows, 50 of the capped file and no more",
      len(pane.search_rows()) == 150
      and sum(1 for row in pane.search_rows() if row[0] == "/hits/many.txt") == 50,
      str(len(pane.search_rows())))
check("§2 ...and ONE sentence says it for the whole run, however many files were capped",
      messages.count(_capped_text) == 1, f"{messages.count(_capped_text)} in {messages[-4:]}")
tab.close_preview()

pane._relist("/exact")
wait_for(lambda: pane.current_dir == "/exact" and pane.tree.topLevelItemCount() >= 1,
         timeout_ms=5000)
messages.clear()
_exact = run_search(pane, {"needle": "hit", "scope": "here"})
check("§2 a file that carries EXACTLY the cap is never reported as cut",
      _exact["matches"] == 50 and _exact["files_cut"] == 0 and _capped_text not in messages,
      str(_exact))
tab.close_preview()

# ════════════════════════════════════════════════════════════════════════════
print("== §3 a provider rebind DROPS the run (N143) ==")
# ════════════════════════════════════════════════════════════════════════════

FS2 = FakeSftpFS()
FS2.add_dir("/home")
FS2.add_file("/home/other.txt", b"other\n")
pane._relist("/hits")
wait_for(lambda: pane.current_dir == "/hits" and pane.tree.topLevelItemCount() >= 3,
         timeout_ms=5000)
_started = pane._start_search({"needle": "hit", "scope": "here"})
check("§3 a run is in flight — its state, its panel and its task maps",
      _started is True and pane._search is not None and pane.search_open is True,
      f"open={pane.search_open} state={bool(pane._search)}")
_worker2 = SftpWorker(FakeSftpClient(FS2))
wire_worker(_worker2, EventLog())
_worker2.start()
tab.set_worker(_worker2)
check("§3 the rebind DROPS it: no task map survives the provider it was queued on",
      pane._search is None and pane.search_open is False
      and pane._search_list_tasks == {} and pane._search_read_tasks == {}
      and not pane._search_lists and not pane._search_reads,
      str((pane._search_list_tasks, pane._search_read_tasks)))
check("§3 ...the RESULTS panel leaves the READER's slot (the listing is the one on the screen)",
      pane.panel_in_slot() is pane.viewer and pane.search_panel.isHidden() is True
      and pane.viewer_host() is None)
check("§3 ...and the counters went with the run", pane.search_report == {},
      str(pane.search_report))
check("§3 ...while the NEW provider's own listing really lands (never eaten by the dead walk)",
      wait_for(lambda: pane.tree.topLevelItemCount() >= 1, timeout_ms=10000),
      f"rows={pane.tree.topLevelItemCount()} dir={pane.current_dir}")
pane._relist("/home")
wait_for(lambda: pane.current_dir == "/home" and pane.tree.topLevelItemCount() >= 1,
         timeout_ms=5000)
check("§3 a run started on the new provider is a WHOLE one (the drop left no residue)",
      run_search(pane, {"needle": "other", "scope": "here"})["files_scanned"] == 1,
      str(pane.search_report))
tab.close_preview()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the four search names of `PANE_STATE` (N145) ==")
# ════════════════════════════════════════════════════════════════════════════

_SEARCH_STATE = ("_search_state", "_search_open", "_search_list_tasks", "_search_read_tasks")
check("§4 `SftpTab.PANE_STATE` declares all four search names",
      all(name in SftpTab.PANE_STATE for name in _SEARCH_STATE),
      str([name for name in _SEARCH_STATE if name not in SftpTab.PANE_STATE]))
tab._search_open = True
check("§4 ...and a write through the container lands on the PANE (one truth, the `_blocked` rule)",
      pane.search_open is True and "_search_open" not in tab.__dict__,
      str(sorted(tab.__dict__))[:160])
tab._search_list_tasks = {7: ("/srv", 0)}
tab._search_read_tasks = {8: ("/srv/a.txt", 9, 1024)}
check("§4 ...both task maps travel to the pane and never shadow it on the container",
      pane._search_lists == {7: ("/srv", 0)}
      and pane._search_reads == {8: ("/srv/a.txt", 9, 1024)}
      and "_search_list_tasks" not in tab.__dict__
      and "_search_read_tasks" not in tab.__dict__,
      str((list(pane._search_lists), list(pane._search_reads))))
tab._search_state = {"report": SEARCH.SearchReport(SEARCH.normalize_query("x"))}
check("§4 ...and the READ side resolves on the same state the write reached",
      tab._search is pane._search and tab.search_report["needle"] == "x",
      str(tab.search_report))
tab._search_state = None
tab._search_open = False
tab._search_list_tasks = {}
tab._search_read_tasks = {}

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the key and the release ==")
# ════════════════════════════════════════════════════════════════════════════

_KEY = "sftp.search.file_cut"
check("§5 the ONE new key is present and non-empty in EVERY language",
      all(str(LANGS[code].get(_KEY) or "").strip() for code in LANGS),
      str({code: _KEY in LANGS[code] for code in sorted(LANGS)}))
check("§5 ...it is really TRANSLATED, not the English copy",
      len({LANGS[code][_KEY] for code in LANGS}) > 1,
      str(len({LANGS[code][_KEY] for code in LANGS})))
check("§5 ...and its only placeholder is the bound",
      all(placeholders(LANGS[code][_KEY]) == {"limit"} for code in LANGS),
      str({code: sorted(placeholders(LANGS[code][_KEY])) for code in sorted(LANGS)}))
check("§5 the pin counts it beside the previous release (1179 + 1)",
      EXPECTED_I18N_KEYS == 1179 + 1 + 1, str(EXPECTED_I18N_KEYS))
_VIEWER_SRC = open(os.path.join(ROOT, "modules", "sftp_pane_viewer.py"), encoding="utf-8").read()
check("§5 ...and the pane really reads it (a key nobody reads is dead weight)",
      _KEY in _VIEWER_SRC)
check_release_state(ROOT)
check("§5 the shipped version is the one this file describes or a later release",
      releases_at_least(EXPECTED_APP_VERSION, "1.13.6.2"), EXPECTED_APP_VERSION)
check("§5 the JSON schema did NOT move (the fix adds no written key)",
      __import__("version").VERSION_FORMAT == "0.9")
check_i18n_parity(LANGS)
check_i18n_format(LANGS)

try:
    tab.release()
except Exception:  # noqa: BLE001 — the teardown must never fail the file
    pass
for _worker in (worker, _worker2):
    try:
        _worker.shutdown()
    except Exception:  # noqa: BLE001 — the teardown must never fail the file
        pass
finish()
