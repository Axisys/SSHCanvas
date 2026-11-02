"""Background checking of map node statuses — one parallel round in a QThread.

`online` = the port is open AND an SSH banner arrived; `warn` = an open port without a banner;
`offline` = unreachable. This module owns the ROUND (the timer, the parallelism, the cancel and the
result stamps) and re-exports the PURE half of `services/status_probe.py` — the vocabulary, the probe,
the cadence reader and the summary — because it is the GUI's live namespace. The card's mark, the
freshness tick and the activity line live in `graphics/server_node.py` / `ui/main_window.py`, and the
plugin status merge is the manager's (`set_status_provider`).

The probes run in a `ThreadPoolExecutor` inside the QThread (a synchronous `create_connection(timeout=3)`
× N nodes would block the GUI), and `stop()`/`shutdown()` are idempotent: an unstarted probe returns
with no status, an in-flight one runs out its timeout. Mechanism — `DOCUMENTATION.md` §19."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QObject, QThread, QTimer, Signal

try:  # the PURE half: the vocabulary, the probe, the cadence and the summary (no Qt)
    from .status_probe import (DEFAULT_INTERVAL_MS, DEFAULT_INTERVAL_SEC, DEFAULT_MAX_PARALLEL,
                               LARGE_MAP_THRESHOLD, MANUAL_INTERVAL_SEC, MANUAL_STALE_SEC,
                               MAX_INTERVAL_SEC, MAX_PARALLEL_LIMIT, MIN_INTERVAL_SEC,
                               PROBE_TIMEOUT_S, SEVERITY, STALE_MIN_SEC, STATUS_OFFLINE,
                               STATUS_ONLINE, STATUS_WARN, build_targets as _build_targets,
                               get_status_settings, is_manual_interval, probe_ssh,
                               resolve_interval_sec, round_summary)
except ImportError:  # the package layout (sshmap.services.*)
    from services.status_probe import (DEFAULT_INTERVAL_MS, DEFAULT_INTERVAL_SEC,
                                       DEFAULT_MAX_PARALLEL, LARGE_MAP_THRESHOLD,
                                       MANUAL_INTERVAL_SEC, MANUAL_STALE_SEC, MAX_INTERVAL_SEC,
                                       MAX_PARALLEL_LIMIT, MIN_INTERVAL_SEC, PROBE_TIMEOUT_S,
                                       SEVERITY, STALE_MIN_SEC, STATUS_OFFLINE, STATUS_ONLINE,
                                       STATUS_WARN, build_targets as _build_targets,
                                       get_status_settings, is_manual_interval, probe_ssh,
                                       resolve_interval_sec, round_summary)

try:  # the round summary's log line
    from modules.logger import get_logger
except ImportError:  # pragma: no cover — the package layout (sshmap.services.*)
    from ..modules.logger import get_logger

log = get_logger(__name__)


class _ProbeThread(QThread):
    """One check round: probes in parallel (ThreadPoolExecutor),
    results — as they complete."""

    probed = Signal(str, str)  # (server_id, status)
    # The plugin detail of a merged result — a tooltip line ("HTTP 503", "3 containers"). Emitted
    # only when a plugin had something to say, so the SSH-only path stays byte-for-byte what it was.
    detail = Signal(str, str)  # (server_id, plugin detail)

    def __init__(self, targets, timeout: float = PROBE_TIMEOUT_S, parent=None,
                 cancel: "threading.Event | None" = None,
                 max_parallel: int = DEFAULT_MAX_PARALLEL,
                 status_provider=None):
        super().__init__(parent)
        self._targets = list(targets)  # [(id, host, port), ...]
        self._timeout = max(0.2, float(timeout))
        self._cancel = cancel
        # The plugin status provider — `provider(server_id, ssh_status)` returns `(kind, detail) | None`
        # and is called INSIDE the pool worker (a worker thread, never the GUI thread: the `PLUGINS.md`
        # §6 discipline). The manager owns the hook budget, so a hung plugin cannot hang the round.
        self._status_provider = status_provider
        try:
            mp = int(max_parallel)
        except (TypeError, ValueError):
            log.debug("max_parallel is unreadable (%r) — %s answers", max_parallel,
                      DEFAULT_MAX_PARALLEL)
            mp = DEFAULT_MAX_PARALLEL
        self._max_parallel = max(1, min(mp, MAX_PARALLEL_LIMIT))

    def run(self):
        # ThreadPoolExecutor instead of a sequential loop: the worst case of a round is
        # ceil(N/max_parallel) × timeout (was N × timeout). Cancellation is checked before each
        # submission: submitted probes run out their network timeout, new ones are not submitted;
        # the executor waits for all its workers (with block), so run() finishes after the last probe.
        with ThreadPoolExecutor(max_workers=self._max_parallel) as pool:
            futures = {}
            for sid, host, port in self._targets:
                if self._cancel is not None and self._cancel.is_set():
                    break  # round cancelled (stop()/shutdown()) — do not submit new probes
                futures[pool.submit(self._probe_one, sid, host, port)] = sid
            # as_completed: results arrive AS THEY COMPLETE (not in the order of the target list). The
            # signal is emitted here — in the QThread, not in the pool workers: queued delivery to the
            # GUI thread and the probed → finished order (FIFO of a single sender) are preserved.
            for fut in as_completed(futures):
                try:
                    answer = fut.result()
                except Exception as e:
                    answer = (STATUS_OFFLINE, "")  # a probe must not crash the round
                    log.debug("The probe of %s raised (%s) — reported offline", futures[fut], e)
                if answer is None:
                    continue  # probe cancelled before it started — no result
                if isinstance(answer, tuple):
                    status, detail = answer
                else:  # a foreign return shape (an exotic monkeypatch) — status only
                    status, detail = answer, ""
                if status is None:
                    continue
                self.probed.emit(futures[fut], status)
                if detail:
                    # After `probed`, so a receiver that reacts to the status (node.set_status) is
                    # already in the detail-aware state.
                    self.detail.emit(futures[fut], detail)

    def _probe_one(self, sid: str, host: str, port: int):
        """One probe in a pool worker (the network timeout is bounded by timeout).

        None — the round was cancelled BEFORE this probe started (the cancel flag was set while the
        probe was waiting for a worker): the node is assigned no result, the signal is not emitted —
        the same semantics as a sequential loop's "exit between nodes". Without this check
        cancellation would be useless: the submit loop hands all N tasks to the pool in
        microseconds, and the round would run out the whole ceil(N/mp) × timeout.

        The answer is `(status, plugin_detail)` — the SSH probe's result MERGED with the status
        plugins' opinions (the worse by severity, the details concatenated, `PLUGINS.md` §3). A
        plugin can only make a status worse, never better: the SSH probe is the transport truth.
        """
        if self._cancel is not None and self._cancel.is_set():
            return None
        try:
            status = probe_ssh(host, port, self._timeout)
        except Exception as e:
            status = STATUS_OFFLINE  # a probe must not crash the round
            log.debug("The SSH probe of %s:%s raised (%s) — reported offline", host, port, e)
        detail = ""
        if self._status_provider is not None:
            try:
                merged = self._status_provider(sid, status)
            except Exception as e:
                merged = None  # a broken provider never breaks a round
                log.debug("The status provider of %s raised (%s) — its opinion is skipped", sid, e)
            if merged:
                try:
                    merged_status, merged_detail = merged[0], merged[1]
                    if merged_status in SEVERITY:
                        status = merged_status
                    detail = str(merged_detail or "")
                except (IndexError, TypeError) as e:
                    detail = ""
                    log.debug("The status provider of %s answered a foreign shape (%r: %s)",
                              sid, merged, e)
        return status, detail


class StatusChecker(QObject):
    """Periodic controller of node status checks.

    Signals:
        status_changed(server_id, str) — the status of a single server was determined
        round_finished(list)           — round finished; [(server_id, status), ...]

    Usage (MainWindow):
        checker = StatusChecker(parent=window)
        checker.status_changed.connect(on_status)
        checker.set_servers([(node.data.id, node.data.host, node.data.ssh_port), ...])
        checker.start()  # first round after ~2 s + a periodic QTimer
    """

    status_changed = Signal(str, str)
    round_finished = Signal(list)
    # The optional plugin detail of a merged probe result — a tooltip line on the card. Emitted only
    # when a plugin produced one.
    status_detail = Signal(str, str)

    def __init__(self, interval_ms: int = DEFAULT_INTERVAL_MS,
                 probe_timeout: float = PROBE_TIMEOUT_S,
                 max_parallel: int = DEFAULT_MAX_PARALLEL, parent=None):
        super().__init__(parent)
        self._interval = max(5000, int(interval_ms))  # no more often than once per 5 s
        self._probe_timeout = float(probe_timeout)
        try:
            mp = int(max_parallel)
        except (TypeError, ValueError):
            mp = DEFAULT_MAX_PARALLEL
        self._max_parallel = max(1, min(mp, MAX_PARALLEL_LIMIT))
        self._targets: list = []          # [(id, host, port), ...]
        self._busy = False                # is a round already running?
        self._last_results: dict = {}     # id -> last status
        self._last_details: dict = {}     # id -> last plugin detail
        # id -> epoch seconds of the last result, plus the end of the last completed round. The window
        # reads them to answer "checked N min ago" and to paint the stale mark; a status itself is
        # never derived from them.
        self._last_times: dict = {}
        self._last_round_at: float = 0.0
        self._status_provider = None      # provider(sid, ssh_status) -> (kind, detail)
        # The ids the checker must NEVER probe while the DEMO map is the open project — their status is
        # EMULATED by `storage/example_project.py`, and a round would repaint them `offline` within 30 s
        # and turn the demo into a lie. A skipped id is not a target at all (`_subset`), so no probe, no
        # result, no timestamp and no `status_changed` — the card keeps what the demo declared.
        self._skip_ids: set = set()
        self._thread: _ProbeThread | None = None
        self._cancel = threading.Event()  # cancel the current round
        # The cadence's third state and whether periodic checking was ever ASKED for. `_manual_only` is
        # the live switch ("no round starts by itself"); `_enabled` remembers a `start()` that a
        # `stop()` has not undone, so switching the manual mode OFF resumes the periodic rounds the
        # user had already enabled — and switching it on BEFORE `start()` arms nothing later.
        self._manual_only = False
        self._enabled = False

        self._timer = QTimer(self)
        self._timer.setInterval(self.effective_interval_ms())
        self._timer.timeout.connect(self.start_round)

    @property
    def interval_ms(self) -> int:
        return self._interval

    @property
    def probe_timeout(self) -> float:
        """Timeout of a single probe (s) — for visibility in tests/dialog."""
        return self._probe_timeout

    @property
    def is_busy(self) -> bool:
        return self._busy

    @property
    def manual_only(self) -> bool:
        """Is the checker in the manual-only mode?

        The ONE predicate of the mode, read by the two guards that decide whether a round may start by
        itself (`start()` and `MainWindow._load_project_at()`). Purely a MODE: the manual doors ("Check
        statuses now", the node context menu) never ask it.
        """
        return bool(self._manual_only)

    @property
    def max_parallel(self) -> int:
        """Ceiling of parallel probes per round (clamped 1..64)."""
        return self._max_parallel

    @property
    def target_count(self) -> int:
        """Number of targets in the current check plan."""
        return len(self._targets)

    def is_large_map(self) -> bool:
        """"Large map" — N > LARGE_MAP_THRESHOLD (50)."""
        return len(self._targets) > LARGE_MAP_THRESHOLD

    def effective_interval_ms(self) -> int:
        """The effective round interval.

        A soft safeguard instead of a hard limit on the number of servers: for large maps (N >
        LARGE_MAP_THRESHOLD) the base interval doubles — a round of parallel probes is still longer
        than on a small map. There is no hard ceiling (150 real servers is a legitimate case;
        navigation for large maps exists — groups/tags/search/collapse).
        """
        return self._interval * 2 if self.is_large_map() else self._interval

    def set_interval(self, ms: int):
        """Change the round interval on the fly (the "Statuses" dialog).

        Clamped as in the constructor (no more often than once per 5 s). Works while the timer is
        active too — QTimer.setInterval restarts the countdown. The timer receives the EFFECTIVE
        interval (for large maps — doubled, `effective_interval_ms()`).
        """
        self._interval = max(5000, int(ms))
        try:
            self._timer.setInterval(self.effective_interval_ms())
        except RuntimeError:
            pass  # Qt teardown — the timer's C++ object is already destroyed

    def set_probe_timeout(self, seconds: float):
        """Change the probe timeout (takes effect from the next round)."""
        self._probe_timeout = max(0.2, float(seconds))

    def set_max_parallel(self, n: int):
        """Change the ceiling of parallel probes on the fly.

        Clamped 1..MAX_PARALLEL_LIMIT; takes effect from the next round (the current one runs in its
        own executor). Corrupt value → default (the `set_probe_timeout` pattern).
        """
        try:
            mp = int(n)
        except (TypeError, ValueError):
            mp = DEFAULT_MAX_PARALLEL
        self._max_parallel = max(1, min(mp, MAX_PARALLEL_LIMIT))

    def set_manual_only(self, flag: bool) -> None:
        """The ONE live switch of the manual-only mode.

        ON — the periodic timer is stopped AT ONCE and no later `start()` will arm it, and no deferred
        first round will slip through (the slot re-asks this flag when it fires). OFF — a `start()`
        that a `stop()` has not undone resumes the periodic rounds, so un-ticking the box in the
        settings does not silently leave the map unmonitored until the next launch. Idempotent, safe
        BEFORE `start()` (nothing is armed either way) and safe on a torn-down Qt object (RuntimeError
        is swallowed, the flag is already set).

        The manual DOORS are deliberately untouched: `start_round()`, `_subset()`, `is_busy`, the
        results and the skip set behave exactly as they do in the automatic mode, so "Check statuses
        now" and the node context menu keep working.
        """
        flag = bool(flag)
        self._manual_only = flag
        try:
            if flag:
                self._timer.stop()
            elif self._enabled and not self._timer.isActive():
                self._timer.start()
        except RuntimeError:
            pass  # Qt teardown — the timer's C++ object is already destroyed

    def set_status_provider(self, provider) -> None:
        """Install the plugin status provider (`provider(sid, ssh_status)`).

        The provider returns `(kind, detail) | None` and is called INSIDE the round's pool worker — a
        worker thread, never the GUI thread (`PLUGINS.md` §6). The plugin manager owns the hook budget,
        so a hung plugin cannot hang a round; a provider that raises is ignored (the SSH probe's own
        result stands). `None` removes it — the round is then exactly the plain probe.
        """
        self._status_provider = provider if callable(provider) else None

    def last_detail(self, server_id: str) -> str:
        """The last plugin detail of the server ("" — none was ever reported)."""
        return self._last_details.get(server_id, "")

    # ── the age of a result ─────────────────────────────────────────────────────

    def stale_threshold_s(self) -> float:
        """How old a result may be before it is presented as stale (seconds).

        `max(2 × the EFFECTIVE round interval, STALE_MIN_SEC)` — the effective one, so a large map
        (whose interval the soft doubling already stretched) gets the same "two missed rounds" rule as
        a small one. The single place that decides it; the card only paints what it is told.

        In the MANUAL mode the answer is the DECLARED `MANUAL_STALE_SEC` (one day) instead. There are
        no rounds to miss, and the age of a status is then the ONLY clock — a threshold of 90 s would
        mark every manual check stale before the user had a chance to look at it.
        """
        if self._manual_only:
            return MANUAL_STALE_SEC
        return max(2.0 * float(self.effective_interval_ms()) / 1000.0, STALE_MIN_SEC)

    def last_checked_at(self, server_id: str) -> float:
        """Epoch seconds of the server's last result (0.0 — never probed in this run)."""
        try:
            return float(self._last_times.get(server_id, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def is_stale(self, server_id: str, now: float = None) -> bool:
        """Is the server's last result older than `stale_threshold_s()`?

        A server that was never probed is NOT stale — it has no datum to be old (the card shows its
        idle mark instead). Purely a question about TIME: the status itself is untouched, here and
        everywhere else.
        """
        checked = self.last_checked_at(server_id)
        if checked <= 0.0:
            return False
        moment = time.time() if now is None else float(now)
        return (moment - checked) > self.stale_threshold_s()

    def last_round_at(self) -> float:
        """Epoch seconds of the end of the last COMPLETED round (0.0 — none yet)."""
        return float(self._last_round_at or 0.0)

    def set_servers(self, servers):
        """Update the target list. `servers` — an iterable of (id, host, port)."""
        self._targets = _build_targets(servers)

    def set_skip_ids(self, server_ids) -> None:
        """Ids this checker must NEVER probe (the demo's emulated nodes).

        Called by the window with `storage.example_project.demo_status_ids()` while the example map is
        the open project and with NOTHING for every other project, so the emulation can never outlive
        the demo. The filter lives in `_subset()` — the ONE place that decides what a round holds — so
        the periodic timer, the round of a project load and the on-demand "Check statuses now" of the
        selection all obey it without a second rule. Purely a target filter: the checker still knows
        nothing about emulation, and a skipped node simply never produces a result.
        """
        self._skip_ids = {str(sid) for sid in (server_ids or ()) if sid}

    def _subset(self, server_ids=None) -> list:
        """The targets of a round: all of them, or only the given server ids.

        The on-demand round of the node context menu checks the SELECTION, not the map —
        ``server_ids=None`` keeps the periodic behaviour (every target), a list restricts it (an
        unknown id is skipped). The order follows the stored target list, so a manual round of the
        whole selection behaves exactly like a periodic one.

        The SKIPPED ids (`set_skip_ids`) are dropped here, whatever the caller asked for — the demo's
        emulated nodes are never probed.
        """
        if self._skip_ids:
            if server_ids is None:
                return [t for t in self._targets if t[0] not in self._skip_ids]
            wanted = {str(sid) for sid in server_ids if sid}
            return [t for t in self._targets if t[0] in wanted and t[0] not in self._skip_ids]
        if server_ids is None:
            return list(self._targets)
        wanted = {str(sid) for sid in server_ids if sid}
        return [t for t in self._targets if t[0] in wanted]

    def last_status(self, server_id: str) -> str:
        """The last determined status of the server ("" — never probed yet)."""
        return self._last_results.get(server_id, "")

    def start_round(self, server_ids=None) -> bool:
        """Start a check round. If the previous one is still running — do nothing.

        An optional ``server_ids`` restricts the round to those servers (the "Check statuses now"
        action probes the selection). Returns True when a round really started — False for "already
        busy" / "nothing to probe", so the caller can tell the user the truth. The probes themselves
        are unchanged: a ``_ProbeThread`` with the same timeout/parallel cap/cancel flag, i.e. off the
        GUI thread.
        """
        if self._busy:
            return False
        targets = self._subset(server_ids)
        if not targets:
            return False
        self._busy = True
        self._cancel.clear()  # new round — clear the previous round's cancel flag
        thread = _ProbeThread(targets, self._probe_timeout, parent=self,
                              cancel=self._cancel, max_parallel=self._max_parallel,
                              status_provider=self._status_provider)
        results = []

        def _on_probed(sid: str, status: str):
            results.append((sid, status))
            self._last_results[sid] = status
            # the result is a fact WITH A TIME — the staleness clock starts here
            self._last_times[sid] = time.time()
            self.status_changed.emit(sid, status)

        def _on_detail(sid: str, detail: str):
            # The plugin detail of a merged result travels on its own signal, so `status_changed` (and
            # every existing receiver) keeps its exact semantics.
            self._last_details[sid] = detail
            self.status_detail.emit(sid, detail)

        def _on_done():
            self._busy = False
            if self._thread is thread:
                self._thread = None
            thread.deleteLater()
            # the round is closed — its age is measurable
            self._last_round_at = time.time()
            # the interval of the NEXT tick — for the current size of the map (targets may have
            # changed during the round: nodes added/removed).
            try:
                self._timer.setInterval(self.effective_interval_ms())
            except RuntimeError:
                pass  # Qt teardown — the timer's C++ object is already destroyed
            # The round summary — ONE record per round for the log file AND the activity panel (the
            # per-node answers live on the cards). Guarded: a broken logging setup must never break a
            # round's completion.
            try:
                log.info(round_summary(results))
            except Exception:  # noqa: BLE001 — the summary is a side channel
                pass
            self.round_finished.emit(results)

        self._thread = thread
        thread.probed.connect(_on_probed)
        thread.detail.connect(_on_detail)
        thread.finished.connect(_on_done)
        thread.start()
        return True

    def _deferred_first_round(self):
        """The 2 s deferred first round of `start()` — a GUARDED slot.

        A `QTimer.singleShot` cannot be un-armed, so switching the manual mode ON inside the 2 s
        window would otherwise let exactly one stray round through — the one promise the mode exists
        to keep. The slot therefore re-asks the mode when it FIRES instead of being cancelled: a
        callback on a dangling object is impossible, and "manual only" means the same thing whenever
        it was selected.

        The fire itself is inside the guard: the checker is a QObject and the window that owns it may
        be gone by then (`WA_DeleteOnClose`), and an exception raised out of a timer slot escapes
        whatever pumped the events — the `TerminalSessionPage._sync_grid` shape.
        """
        try:
            if self._manual_only:
                return
            self.start_round()
        except RuntimeError:
            pass  # the C++ object was already destroyed

    def start(self):
        """Enable periodic checks + the first round a bit after startup.

        The first round via QTimer.singleShot(2000), not immediately: at app startup the event
        sequence is still unfolding, and in headless tests without an event loop the deferred call
        simply never happens (safe).

        In the MANUAL-only mode this arms NOTHING — no timer and no deferred round
        (`_deferred_first_round()` re-asks the flag anyway). Opening the application is not "check my
        servers now": the manual doors are the only way in.
        """
        self._enabled = True
        if self._manual_only:
            return
        if not self._timer.isActive():
            self._timer.start()
            QTimer.singleShot(2000, self._deferred_first_round)

    def stop(self):
        """Stop the periodic checks and the current round.

        An early return of the round is impossible — the cancel flag is set, the executor stops
        accepting new probes (the submitted ones run out their network timeout); then the thread is
        waited on with a margin of ceil(N/max_parallel) × timeout + 2 s (the round is parallel — the
        margin is ceil(N/max_parallel) × timeout, not N × timeout).
        """
        self._enabled = False  # a stopped checker is not resumed by set_manual_only(False)
        self._timer.stop()
        self._cancel.set()
        thread = self._thread
        if thread is not None and thread.isRunning():
            batches = (len(self._targets) + self._max_parallel - 1) // max(1, self._max_parallel)
            wait_ms = int(self._probe_timeout * 1000) * max(1, batches) + 2000
            if not thread.wait(wait_ms):
                try:
                    from modules.logger import get_logger as _gl
                    _gl("services.status_checker").warning(
                        f"Probe thread did not finish within {wait_ms} ms after cancel")
                except Exception:  # noqa: BLE001 — the log is a side channel: the round already returned
                    pass

    def shutdown(self):
        """Full stop when MainWindow is destroyed (the destroyed signal).

        Timer + cancellation and waiting for the current round — so the probe thread is not destroyed
        on the fly together with its parent (a wait shorter than a whole round with ≥ 2 nodes would
        be the same defect).
        """
        self.stop()
