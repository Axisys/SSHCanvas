# -*- coding: utf-8 -*-
"""The six defects a review of the shipped `v1.13.4` confirmed in the Diff tab and the Send relay (v1.13.4.2).
§1 a pending leg is keyed by `(worker, task id)` — two workers with colliding ids keep their own bytes
(N125); §2 the relay ignores a foreign completion of the target worker (N126); §3 the engine's line/time
budget, its REFUSAL before `SequenceMatcher` and its background thread (N127); §4 the spool size gate
BEFORE the download is queued (N128); §5 a leg in flight outlives `shutdown()` only as a spool the answer
drops, and it joins the source pane's Cancel (N129); §6 the intra-line mark counts UTF-16 units (N130);
§7 the release — no new key, no schema move, the four-component pin.
Rule — `AGENTS.md` §4.34; mechanism — `DOCUMENTATION.md` §79; contract — `DIFF.md`.
Run: python tests/test_hardening_v11342.py
"""
import os
import sys
import threading

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, VERSION_FORMAT_RE, bootstrap, check,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     releases_at_least, wait_until)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtCore import QObject, Qt, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.sftp_send as SEND  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
import modules.terminal_diff as D  # noqa: E402

LANGS = load_i18n_langs(ROOT)
clear_cfg()


def _read(*parts) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def _tmp_text(name, text):
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path


class _FakeWorker(QObject):
    """The worker surface both consumers bind, with a PER-INSTANCE task counter from 1 (`N125`)."""

    read_ready = Signal(int, str, bytes)
    task_done = Signal(int, str)
    task_error = Signal(int, str, str)
    task_cancelled = Signal(int, str)
    progress = Signal(int, int, int)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.reads = []
        self.downloads = []
        self.uploads = []
        self.copies = []
        self.cancels = 0
        self._next = 0

    def _task(self):
        self._next += 1
        return self._next

    def queue_read(self, path, size=0, max_bytes=0):
        task = self._task()
        self.reads.append((task, path, int(size or 0), int(max_bytes or 0)))
        return task

    def queue_download(self, remote_path, local_dir, total_size=0, local_name="", part_mode=0):
        task = self._task()
        self.downloads.append({"id": task, "path": remote_path,
                               "local": os.path.join(local_dir, local_name or ""),
                               "size": int(total_size or 0), "mode": int(part_mode or 0)})
        return task

    def queue_upload(self, local_path, remote_dir, remote_name=""):
        task = self._task()
        try:
            with open(local_path, "rb") as handle:
                data = handle.read()
        except OSError:
            data = b""
        self.uploads.append({"id": task, "data": data, "dir": remote_dir, "name": remote_name})
        return task

    def queue_copy(self, source, target_dir, name=""):
        task = self._task()
        self.copies.append({"id": task, "source": source, "dir": target_dir, "name": name})
        return task

    def cancel(self):
        self.cancels += 1


# ════════════════════════════════════════════════════════════════════════════
print("== §1 a pending leg is keyed by (worker, task id) (N125) ==")
# ════════════════════════════════════════════════════════════════════════════

_worker_a, _worker_b = _FakeWorker(), _FakeWorker()
_tab = D.DiffTab()
check("§1 fixture: the tab binds TWO workers and each numbers its tasks from 1",
      callable(_worker_a.queue_read) and callable(_worker_b.queue_read))
check("§1 a remote side of worker A and one of worker B are queued",
      _tab.load_side("left", {"kind": "remote", "worker": _worker_a, "path": "/a.txt",
                              "size": 4, "name": "a.txt"}) is True
      and _tab.load_side("right", {"kind": "remote", "worker": _worker_b, "path": "/b.txt",
                                   "size": 4, "name": "b.txt"}) is True)
check("§1 ...and the two pending legs really COLLIDE on the bare id (the defect's precondition)",
      _worker_a.reads[0][0] == _worker_b.reads[0][0] == 1
      and len(_tab._pending_reads) == 2
      and {(key[1], id(key[0])) for key in _tab._pending_reads}
      == {(1, id(_worker_a)), (1, id(_worker_b))}, str(list(_tab._pending_reads)))
_worker_a.read_ready.emit(1, "/a.txt", b"AAA\n")
_worker_b.read_ready.emit(1, "/b.txt", b"BBB\n")
app.processEvents()
check("§1 each side receives ITS OWN worker's bytes (no side shows the other file)",
      _tab.side_state("left")["text"] == "AAA\n" and _tab.side_state("right")["text"] == "BBB\n",
      (_tab.side_state("left")["text"], _tab.side_state("right")["text"]))
check("§1 ...and both legs left their pending maps", not _tab._pending_reads)
_tab.shutdown()

_worker_c, _worker_d = _FakeWorker(), _FakeWorker()
_tab2 = D.DiffTab()
_tab2.load_side("left", {"kind": "spool", "worker": _worker_c, "path": "/a.txt", "size": 5,
                         "name": "a.txt"})
_tab2.load_side("right", {"kind": "spool", "worker": _worker_d, "path": "/b.txt", "size": 5,
                          "name": "b.txt"})
check("§1 the SPOOL legs collide the same way and are keyed by the pair too",
      _worker_c.downloads[0]["id"] == _worker_d.downloads[0]["id"] == 1
      and len(_tab2._pending_spools) == 2, str(list(_tab2._pending_spools)))
for _worker, _payload in ((_worker_c, b"LEFT\n"), (_worker_d, b"RIGHT\n")):
    _leg = _worker.downloads[0]
    with open(_leg["local"], "wb") as _handle:
        _handle.write(_payload)
    _worker.task_done.emit(_leg["id"], _leg["local"])
app.processEvents()
check("§1 ...and each side decodes the spool ITS OWN leg published",
      _tab2.side_state("left")["text"] == "LEFT\n"
      and _tab2.side_state("right")["text"] == "RIGHT\n"
      and _tab2._spools == [] and _tab2._pending_spools == {},
      (_tab2.side_state("left")["text"], _tab2.side_state("right")["text"]))
_tab2.shutdown()


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the SendRelay ignores a FOREIGN completion (N126) ==")
# ════════════════════════════════════════════════════════════════════════════

_source_worker, _target_worker = _FakeWorker(), _FakeWorker()
_source = SEND.SendEndpoint(key="s", label="alpha", host="10.0.0.1", port=22, user="root",
                            worker=_source_worker, directory="/in")
_target = SEND.SendEndpoint(key="t", label="beta", host="10.0.0.2", port=22, user="root",
                            worker=_target_worker, directory="/out")
_relay = SEND.SendRelay(_source, _target, {"path": "/in/a.txt", "name": "a.txt", "size": 7,
                                           "mtime": 0})
_results = []
_relay.finished.connect(_results.append)
_relay.start("/out")
_download = _source_worker.downloads[0]
check("§2 fixture: the relay queued ONE download and its spool exists",
      _relay.strategy == SEND.SEND_STRATEGY_RELAY and _download["id"] == 1
      and os.path.exists(_relay.spool), _relay.spool)
check("§2 ...and the pending leg is keyed by the source WORKER, not the bare id",
      list(_relay._tasks) == [(_source_worker, 1)], str(list(_relay._tasks)))
_target_worker.task_done.emit(1, "the target pane's own transfer")
app.processEvents()
check("§2 a completion of the TARGET worker with the download's id queues NO upload",
      _target_worker.uploads == [] and _results == [] and os.path.exists(_relay.spool),
      str(_target_worker.uploads))
with open(_relay.spool, "wb") as _handle:
    _handle.write(b"PAYLOAD")
_source_worker.task_done.emit(1, _relay.spool)
app.processEvents()
check("§2 the download's OWN answer queues the upload out of the spool",
      len(_target_worker.uploads) == 1 and _target_worker.uploads[0]["data"] == b"PAYLOAD"
      and (_target_worker, _target_worker.uploads[0]["id"]) in _relay._tasks,
      str(_target_worker.uploads))
_target_worker.task_done.emit(_target_worker.uploads[0]["id"], "/out/a.txt")
app.processEvents()
check("§2 ...and the send finishes ONCE with the spool gone",
      len(_results) == 1 and _results[0]["ok"] is True and not os.path.exists(_relay.spool),
      str(_results[:1]))


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the engine budget and its thread (N127) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 the budget is DECLARED in the module (lines, milliseconds and the inline bound)",
      D.DIFF_MAX_LINES == 4000 and 0 < D.DIFF_BUDGET_MS <= 2000
      and D.DIFF_INLINE_MAX_LINES < D.DIFF_MAX_LINES, (D.DIFF_MAX_LINES, D.DIFF_BUDGET_MS))
_original_matcher = D.difflib.SequenceMatcher
_matcher_calls = []


def _recording_matcher(*args, **kwargs):
    _matcher_calls.append(1)
    return _original_matcher(*args, **kwargs)


D.difflib.SequenceMatcher = _recording_matcher
try:
    _over = "\n".join("x" for _ in range(D.DIFF_MAX_LINES + 1))
    try:
        D.diff_rows(_over, "")
        _refused, _exc = False, None
    except D.DiffBudgetExceeded as exc:
        _refused, _exc = True, exc
finally:
    D.difflib.SequenceMatcher = _original_matcher
check("§3 a pair over the line budget is REFUSED with the pair and the limit named",
      _refused and _exc.lines == D.DIFF_MAX_LINES + 1 and _exc.limit == D.DIFF_MAX_LINES,
      repr(_exc))
check("§3 ...and `SequenceMatcher` was never constructed (the gate is BEFORE the engine)",
      _matcher_calls == [], str(len(_matcher_calls)))
check("§3 a pair exactly AT the budget is still compared",
      len(D.diff_rows("\n".join("y" for _ in range(D.DIFF_MAX_LINES)), "")) == D.DIFF_MAX_LINES)

_threads = []
_original_rows = D.diff_rows


def _recording_rows(left, right, *args, **kwargs):
    _threads.append(threading.current_thread().name)
    return _original_rows(left, right, *args, **kwargs)


_left_big = "\n".join(f"alpha {i}" for i in range(150))
_right_big = "\n".join(f"beta {i}" for i in range(150))
D.diff_rows = _recording_rows
try:
    _tab3 = D.DiffTab()
    _tab3.load_side("left", {"kind": "local", "path": _tmp_text("engine_left.txt", _left_big)})
    _tab3.load_side("right", {"kind": "local", "path": _tmp_text("engine_right.txt", _right_big)})
    check("§3 a pair over the INLINE bound returns to the GUI at once (the text is shown, no marks)",
          _tab3._rendering is True and _tab3.rows() == []
          and _tab3.status_text().startswith(i18n.t("sftp.viewer.reading", name="engine_right.txt")),
          _tab3.status_text())
    wait_until(lambda: _tab3.rows() or _tab3._budget_error, timeout_ms=15000)
finally:
    D.diff_rows = _original_rows
check("§3 ...and the comparison ran OFF the GUI thread (a worker, never the main thread)",
      bool(_threads) and threading.main_thread().name not in _threads, str(_threads))
check("§3 ...the aligned rows land and the summary carries the figures",
      len(_tab3.rows()) == 150 and _tab3.status_text().startswith(
          i18n.t("diff.stats", added=0, removed=0, changed=150)), _tab3.status_text())
_tab3.shutdown()

_tab4 = D.DiffTab()
_huge = "\n".join("z" for _ in range(D.DIFF_MAX_LINES + 1))
_tab4.load_side("left", {"kind": "local", "path": _tmp_text("huge_left.txt", _huge)})
_tab4.load_side("right", {"kind": "local", "path": _tmp_text("huge_right.txt", _huge)})
wait_until(lambda: _tab4._budget_error, timeout_ms=15000)
check("§3 an over-budget pair answers the SHIPPED refusal sentence, never a frozen window",
      _tab4.status_text().startswith(i18n.t("sftp.viewer.too_large", limit=D.DIFF_MAX_LINES)),
      _tab4.status_text())
check("§3 ...and the refusal leaves no marks behind (both editors show the plain text)",
      _tab4.rows() == [] and _tab4._rendering is False)
_tab4.shutdown()


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the spool size gate (N128) ==")
# ════════════════════════════════════════════════════════════════════════════

_original_cap = D._viewer_cap
D._viewer_cap = lambda: 1024
try:
    _tab5 = D.DiffTab()
finally:
    D._viewer_cap = _original_cap
_spool_worker = _FakeWorker()
check("§4 fixture: the tab's ceiling is the shipped viewer cap (no second key)", _tab5._cap == 1024)
_refused = _tab5.load_side("left", {"kind": "spool", "worker": _spool_worker, "path": "/huge.bin",
                                    "size": 5 * 1024 ** 3, "name": "huge.bin"})
check("§4 a foreign file over the cap is REFUSED BEFORE the download is queued",
      _refused is False and _spool_worker.downloads == [] and _tab5._spools == [],
      str(_spool_worker.downloads))
check("§4 ...with the shipped refusal vocabulary (the ceiling named, the file named)",
      _tab5.side_state("left")["error"] == i18n.t(
          "sftp.viewer.read_failed", name="huge.bin",
          error=i18n.t("sftp.viewer.too_large", limit=D.format_size(1024))),
      _tab5.side_state("left")["error"])
check("§4 a copy INSIDE the cap is queued as before (the gate never refuses a legal copy)",
      _tab5.load_side("right", {"kind": "spool", "worker": _spool_worker, "path": "/small.txt",
                                "size": 6, "name": "small.txt"}) is True
      and len(_spool_worker.downloads) == 1)
_ok_leg = _spool_worker.downloads[0]
with open(_ok_leg["local"], "wb") as _handle:
    _handle.write(b"small\n")
_spool_worker.task_done.emit(_ok_leg["id"], _ok_leg["local"])
app.processEvents()
check("§4 ...and its answer is decoded like any other remote side",
      _tab5.side_state("right")["text"] == "small\n" and _tab5._spools == [])
_tab5.shutdown()


# ════════════════════════════════════════════════════════════════════════════
print("== §5 a leg in flight outlives `shutdown()` only as an owned spool (N129) ==")
# ════════════════════════════════════════════════════════════════════════════

_tab6 = STAB.SftpTab()
_pane = _tab6.active_pane
check("§5 the source pane answers the ONE tracking door (`track_transfer`)",
      callable(getattr(_pane, "track_transfer", None)))
check("§5 a leg registered there joins the shipped Cancel bookkeeping",
      _pane.track_transfer(7) is True and 7 in _pane._own_transfers
      and 7 in _pane._transfer_tasks and _pane.btn_cancel.isEnabled() is True,
      (7 in _pane._own_transfers, _pane.btn_cancel.isEnabled()))
_pane._on_task_finished(7)
check("§5 ...and the answer drops it (no second cancel mechanism)",
      7 not in _pane._own_transfers and 7 not in _pane._transfer_tasks
      and _pane.btn_cancel.isEnabled() is False)
_tab6.release()

_leg_worker = _FakeWorker()
_tab7 = D.DiffTab()
check("§5 a spool leg queued by the tab is registered with its SOURCE pane",
      _tab7.load_side("left", {"kind": "spool", "worker": _leg_worker, "path": "/late.txt",
                               "size": 6, "name": "late.txt", "track": _pane}) is True
      and 1 in _pane._own_transfers and len(_tab7._spools) == 1)
_spool = _tab7._spools[0]
check("§5 ...and that spool exists on the disk before the answer lands",
      os.path.exists(_spool) and os.path.exists(_spool + ".part"), _spool)
_tab7.shutdown()
check("§5 the teardown does NOT forget the leg (its answer still owns the copy)",
      _tab7._shut_down is True and _leg_worker in _tab7._workers
      and len(_tab7._pending_spools) == 1 and os.path.exists(_spool), str(_tab7._pending_spools))
with open(_spool, "wb") as _handle:
    _handle.write(b"LATE\n")
_leg_worker.task_done.emit(1, _spool)
app.processEvents()
check("§5 the answer that lands AFTER the teardown drops the copy it published",
      not os.path.exists(_spool) and _tab7._spools == [] and _tab7._pending_spools == {}
      and _tab7._workers == [],
      (os.path.exists(_spool), _tab7._spools, len(_tab7._workers)))
check("§5 ...and the tab's own state never wrote the side after the teardown",
      _tab7.side_state("left")["loaded"] is False)


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the intra-line mark counts UTF-16 units (N130) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§6 a non-BMP character before the change shifts the span by ONE UTF-16 unit",
      D.utf16_spans("😀abcDEF", [(4, 7)]) == ((5, 8),), str(D.utf16_spans("😀abcDEF", [(4, 7)])))
check("§6 a line of BMP characters keeps its offsets unchanged",
      D.utf16_spans("plain", [(1, 3)]) == ((1, 3),))
check("§6 a span outside the line is dropped, never clamped",
      D.utf16_spans("short", [(3, 99)]) == () and D.utf16_spans("", [(0, 1)]) == ())
_tab8 = D.DiffTab()
_tab8.load_side("left", {"kind": "local", "path": _tmp_text("emoji_left.txt", "😀abcDEF\n")})
_tab8.load_side("right", {"kind": "local", "path": _tmp_text("emoji_right.txt", "😀abcXYZ\n")})
_block = _tab8._editors["left"].document().findBlockByNumber(0)
_marked = []
_alphas = []
_iterator = _block.begin()
while not _iterator.atEnd():
    _fragment = _iterator.fragment()
    _background = _fragment.charFormat().background()
    if _background.style() != Qt.BrushStyle.NoBrush:
        _marked.append(_fragment.text())
        _alphas.append(_background.color().alpha())
    _iterator += 1
check("§6 the editor marks exactly the changed run of the line (neither shifted nor clamped)",
      _marked == ["DEF"], str(_marked))
check("§6 ...and the marked run carries the declared intra-line alpha",
      _alphas == [D.DIFF_INLINE_ALPHA], str(_alphas))
_tab8.shutdown()


# ════════════════════════════════════════════════════════════════════════════
print("== §7 the release: no new key, no schema move, the four-component pin ==")
# ════════════════════════════════════════════════════════════════════════════

for _key in ("diff.error_read", "sftp.viewer.too_large", "sftp.send.failed"):
    check(f"§7 {_key} still carries a sentence in every language",
          all(str(data.get(_key) or "").strip() for data in LANGS.values()),
          str({code: bool(data.get(_key)) for code, data in LANGS.items()}))
check_i18n_parity(LANGS)
check_release_state(ROOT)
check("§7 the i18n pin is UNCHANGED — this patch adds no translation key",
      EXPECTED_I18N_KEYS == 1162 + 4 + 13, str(EXPECTED_I18N_KEYS))
check("§7 the pin names this patch's line", releases_at_least(EXPECTED_APP_VERSION, "1.13.4"),
      EXPECTED_APP_VERSION)
check("§7 the pin names this patch's line or a later release and the format accepts it",
      releases_at_least(EXPECTED_APP_VERSION, "1.13.4.2")
      and bool(VERSION_FORMAT_RE.match(EXPECTED_APP_VERSION)),
      EXPECTED_APP_VERSION)
import version as VERSION_MODULE  # noqa: E402
check("§7 the JSON schema did NOT move (VERSION_FORMAT stays 0.9)",
      VERSION_MODULE.VERSION_FORMAT == "0.9", VERSION_MODULE.VERSION_FORMAT)
check("§7 no new dependency (requirements.txt keeps its four)",
      len([ln for ln in open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8")
           if ln.strip() and not ln.startswith("#")]) == 4)
_ledger = _read("AUDIT_PENDING.md")
check("§7 the ledger entries of this patch left `AUDIT_PENDING.md`",
      not any(f"#### N{number}" in _ledger for number in range(125, 131))
      and "### `v1.13.4.2`" not in _ledger)
check("§7 the plan of record no longer carries the shipped section",
      "## v1.13.4.2" not in _read("ROADMAP.md"))
check("§7 the changelog family carries the entry",
      "v1.13.4.2" in _read("CHANGELOG.md") and "v1.13.4.2" in _read("CHANGELOG_DETAILS.md"))
check("§7 the contract and the mechanism follow the code",
      "utf16_spans" in _read("DIFF.md") and "DIFF_MAX_LINES" in _read("DOCUMENTATION.md"))
check("§7 the suite map lists this file (tests/INDEX.md regenerated)",
      "test_hardening_v11342" in _read("tests", "INDEX.md"))
check("§7 the rule is owned where it is written (`AGENTS.md` §4.34)",
      "track_transfer" in _read("AGENTS.md") and "(worker, task_id)" in _read("AGENTS.md"))


finish()
