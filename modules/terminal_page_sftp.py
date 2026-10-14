# -*- coding: utf-8 -*-
"""The SFTP task BRIDGE of a terminal session — the channel it asks for, the worker and the slots.

`TerminalPageSftpMixin` starts the ONE bounded handshake that opens the SFTP channel over the session's
OWN transport (no second authentication, `modules/sftp_open.py`), owns the transfer bookkeeping
(`_sftp_tasks`, `_transfer_meters`, `_sftp_busy`) and turns the worker's signals into the host's
status/progress bridge. A facade global — the worker class, the kind tables, the size/duration
formatters, the name-refusal renderer and the translator — is resolved through `host_attr()`
(`ui/mixin_support.py`): the mixin never imports `modules/terminal_page` and `terminal_page.<name>`
stays the substitution point. Mechanism — §14b, §64."""

try:  # AGENTS.md §4.1: the ONE seam for a facade global — a mixin never imports the facade module
    from ..ui.mixin_support import host_attr
except ImportError:
    from ui.mixin_support import host_attr

try:  # the ONE bounded opener of this mixin's channel (`AGENTS.md` §4.8.1)
    from .sftp_open import SftpOpenHandshake, close_quiet
except ImportError:
    from sftp_open import SftpOpenHandshake, close_quiet

class TerminalPageSftpMixin:
    """The SFTP worker bridge (mixed into `TerminalSessionPage`)."""

    # The SFTP task kinds that feed the progress bridge (the busy counter, the QProgressBar and the
    # status-bar text): `read` is the viewer's read, whose OUTCOME the SFTP tab renders itself. The
    # file operations (mkdir/rename/delete) are outside this set on purpose — no bytes, no bar — and
    # a remote→remote COPY joins it (bytes, a total from stat, the rate/ETA meter) while a MOVE is a
    # rename (nothing to measure) — `DOCUMENTATION.md` §14.
    _SFTP_PROGRESS_KINDS = ("upload", "download", "read", "copy")

    # The i18n key that NAMES a transfer in flight — one mapping for the start line and for the
    # indeterminate-progress line, so a new kind cannot half-land.
    _SFTP_KIND_KEYS = {"upload": "sftp.uploading", "download": "sftp.downloading",
                       "read": "sftp.viewer.reading", "copy": "sftp.copying"}

    # ── v1.1.3: the SFTP tab (ROADMAP tasks 2-4) ────────────────────────────

    def _ensure_sftp(self) -> bool:
        """Ask for the session's SFTP channel — WITHOUT blocking the GUI thread.

        True — the channel is OPEN (the worker is live); False — it is still opening, was refused
        (`sftp.open_failed` on the status bridge) or is impossible. The open runs on ONE
        `SftpOpenHandshake` thread, because BOTH of its stages block with no bound of their own:
        the channel request waits `Transport.channel_timeout` (3600 s) and the SFTP version read
        waits on a `Channel.recv()` whose timeout is `None` — a silent server would freeze the
        window that asked. It reuses the session's OWN transport (no second authentication and no
        second known_hosts pass) and a session that is not connected yet answers False (the tab
        waits). `with_sftp=False` (a split pane) never opens a channel. ONE open per session.
        """
        if getattr(self, "sftp_tab", None) is None:
            return False   # v1.3.3.5: a split pane is a command line — no SFTP channel
        worker = getattr(self, "_sftp_worker", None)
        if worker is not None and not worker.isFinished():
            return True
        if self.sftp_channel_pending():
            return False   # a handshake is already in flight — a second ask is the same question
        transport = self._sftp_transport()
        if transport is None:
            return False
        self._start_sftp_open(transport)
        return False

    def sftp_channel_pending(self) -> bool:
        """Is a channel still OPENING for this session? (the `sftp.opening` moment of the panel)"""
        handshake = getattr(self, "_sftp_handshake", None)
        if handshake is None:
            return False
        try:
            return not handshake.isFinished()
        except RuntimeError:
            return False   # the C++ object is already gone — nothing is opening any more

    def _sftp_transport(self):
        """The session's LIVE transport — None when it is not connected, closed or already gone."""
        thread = getattr(self, "terminal_thread", None)
        client = getattr(thread, "client", None) if thread is not None else None
        if client is None:
            return None
        try:
            transport = client.get_transport()
            return transport if transport is not None and transport.is_active() else None
        except Exception:  # noqa: BLE001 — an unaskable client is not a connected one
            return None

    def _start_sftp_open(self, transport):
        """Start the ONE handshake of this session; its three signals answer this page."""
        handshake = SftpOpenHandshake(transport)
        self._sftp_handshake = handshake
        handshake.ready.connect(self._on_sftp_open_ready)
        handshake.failed.connect(self._on_sftp_open_failed)
        handshake.finished.connect(self._on_sftp_open_finished)
        handshake.start()

    def _on_sftp_open_ready(self):
        """The server answered: the SHIPPED worker wiring runs over the channel that opened.

        The client is TAKEN from the handshake (the ownership moves in one step), so an answer
        that arrives after the session is gone is closed here instead of leaking a channel.
        """
        handshake = getattr(self, "_sftp_handshake", None)
        sftp = handshake.take_client() if handshake is not None else None
        if sftp is None:
            return   # already dropped by the teardown
        if getattr(self, "_shut_down", False):
            close_quiet(sftp)
            return
        try:
            self._bind_sftp_worker(sftp, handshake.transport)
        except RuntimeError:
            close_quiet(sftp)   # the C++ object is already gone (a close race)

    def _on_sftp_open_failed(self, detail: str):
        """The open was REFUSED — the status bridge carries ONE sentence (`sftp.open_failed`)."""
        if getattr(self, "_shut_down", False):
            return
        t = host_attr(self, "get_translator")()
        msg = t("sftp.open_failed", error=str(detail or ""))
        self.status_message.emit(
            msg if not msg.startswith("[") else f"Failed to open SFTP channel: {detail}", 8000)

    def _on_sftp_open_finished(self):
        """The thread is really done — the ONE place the reference is dropped (`AGENTS.md` §4.8)."""
        handshake = getattr(self, "_sftp_handshake", None)
        if handshake is None:
            return
        try:
            if not handshake.isFinished():
                return   # still inside its wait budget — the orphan registry answers for it
        except RuntimeError:
            pass   # the C++ object is gone — a stale reference goes either way
        self._sftp_handshake = None

    def _bind_sftp_worker(self, sftp, transport) -> bool:
        """The worker over a channel that is already open (the shipped wiring, one step later).

        WITHOUT a QObject parent: the window has WA_DeleteOnClose, and a hanging transfer may
        outlive it — the orphan worker registry keeps the thread alive until finished(); all slots
        are disconnected in shutdown().
        """
        new_worker = host_attr(self, "SftpWorker")(sftp)
        self._sftp_worker = new_worker
        new_worker.task_started.connect(self._on_sftp_task_started)
        new_worker.progress.connect(self._on_sftp_progress)
        new_worker.task_done.connect(self._on_sftp_task_done)
        new_worker.task_error.connect(self._on_sftp_task_error)
        new_worker.task_cancelled.connect(self._on_sftp_task_cancelled)
        new_worker.finished.connect(self._on_sftp_worker_finished)
        new_worker.start()
        self.sftp_tab.set_worker(new_worker)
        # v1.8: the SESSION's transport is published with the transport it belongs to — the
        # elevated pane of `ELEVATED_PANE.md` §2 opens its channel on it, and the pane may not
        # reach into this worker for the object.
        try:
            self.sftp_tab.set_transport(transport)
        except (RuntimeError, AttributeError):
            pass  # Qt teardown / a bare stub — the elevation is simply not offered
        return True

    def _on_tab_changed(self, index: int):
        """A switch to the "Files" tab — a lazy SFTP start (idempotent).

        v1.3.3.5: on a page without the SFTP tab `self.sftp_tab` is None and no widget
        can be it, so the guard is a no-op by itself (kept for symmetry).
        """
        if self.sftp_tab is not None and self.tabs.widget(index) is self.sftp_tab:
            self._ensure_sftp()

    def _on_sftp_tab_message(self, msg: str):
        """A tab message (a file selection and the like) → the status_message bridge (5 s)."""
        self.status_message.emit(msg, 5000)

    def _on_connected_for_sftp(self):
        """connected_signal: open the channel the session is really going to need.

        Two triggers ask for it — the user was already sitting on "Files", or v1.7.1 shows
        the tree in the window's right-hand PANEL (where there is no Files tab to switch to).
        """
        try:
            if self._files_panel_on or self.tabs.currentWidget() is self.sftp_tab:
                self._ensure_sftp()
        except RuntimeError:
            pass  # the C++ object was already destroyed (a close race)

    def _transfer_kind_text(self, kind: str, label: str) -> str:
        """The status line naming a transfer in flight (v1.7rc2: ONE mapping for the
        start line and the indeterminate-progress line — `sftp.uploading` /
        `sftp.downloading` / `sftp.viewer.reading` / `sftp.copying`)."""
        key = self._SFTP_KIND_KEYS.get(kind, "sftp.downloading")
        return host_attr(self, "get_translator")()(key, name=label)

    def _on_sftp_task_started(self, task_id: int, kind: str, label: str):
        if self._shut_down:
            return   # v1.8rc6 (N56): a POSTED emission survives the disconnect() of the teardown
        t = host_attr(self, "get_translator")()
        self._sftp_tasks[task_id] = (kind, label)
        if kind in self._SFTP_PROGRESS_KINDS:
            self._sftp_busy += 1
            self.progress_busy.emit()   # v1.1.x: setRange(0,0)+setValue(0)+show()
            self.status_message.emit(self._transfer_kind_text(kind, label), 0)
        elif kind in host_attr(self, "OP_KINDS"):
            pass   # v1.3.3.2: a file operation — the SFTP tab reports it itself
        else:  # list — without a progress bar
            self.status_message.emit(t("sftp.listing", path=label), 0)

    def _on_sftp_progress(self, task_id: int, done: int, total: int):
        if self._shut_down:
            return   # v1.8rc6 (N56): the posted-emission guard of the transfer family
        t = host_attr(self, "get_translator")()
        entry = self._sftp_tasks.get(task_id)
        if entry is None or entry[0] not in self._SFTP_PROGRESS_KINDS:
            return
        kind, label = entry
        if total > 0:
            self.progress_update.emit(done, total)   # v1.1.x: setRange(0,total)+setValue
            text = t("sftp.progress", name=label, pct=int(done * 100 // total),
                     done=host_attr(self, "format_size")(done),
                     total=host_attr(self, "format_size")(total))
            # v1.3.3.4 (ROADMAP task 6): the measured throughput and the ETA, appended
            # to the same line (an empty string while the meter has nothing honest to show).
            detail = self._transfer_detail(task_id, done, total)
            if detail:
                text = f"{text} · {detail}"
        else:  # total unknown — name only (an indeterminate bar)
            self.progress_update.emit(done, 0)
            text = self._transfer_kind_text(kind, label)
        self.status_message.emit(text, 0)

    def _transfer_detail(self, task_id: int, done: int, total: int) -> str:
        """v1.3.3.4 (ROADMAP task 6): "1.2 MB/s · ETA 0:42" — or "" while unmeasurable.

        The meter is created on the first sample of the task and dropped with it
        (SUCCESS, error and cancel all call _drop_transfer_meter). Never raises: a
        broken measurement costs the suffix, not the progress line.
        """
        try:
            meter = self._transfer_meters.get(task_id)
            if meter is None:
                meter = host_attr(self, "TransferMeter")()
                self._transfer_meters[task_id] = meter
            sample = meter.update(done, total)
            if sample is None:
                return ""
            rate, eta = sample
            if rate is None or rate <= 0:
                return ""
            t = host_attr(self, "get_translator")()
            parts = [t("sftp.rate", rate=host_attr(self, "format_size")(int(rate)))]
            eta_text = host_attr(self, "format_duration")(eta) if eta is not None else ""
            if eta_text:
                parts.append(t("sftp.eta", time=eta_text))
            return " · ".join(parts)
        except Exception:  # noqa: BLE001 — a cosmetic suffix must never break the transfer UI
            return ""

    def _drop_transfer_meter(self, task_id: int):
        """Forget the rate meter of a finished/failed/cancelled task."""
        try:
            self._transfer_meters.pop(task_id, None)
        except Exception:  # noqa: BLE001 — teardown race
            pass

    def _on_sftp_task_done(self, task_id: int, detail: str):
        if self._shut_down:
            return   # v1.8rc6 (N56): the posted-emission guard of the transfer family
        t = host_attr(self, "get_translator")()
        self._drop_transfer_meter(task_id)   # v1.3.3.4 (task 6): the meter dies with the task
        entry = self._sftp_tasks.pop(task_id, None)
        if entry is not None and entry[0] in self._SFTP_PROGRESS_KINDS:
            self._sftp_busy = max(0, self._sftp_busy - 1)
            if self._sftp_busy == 0:
                self.progress_hidden.emit()
            # v1.3.1: a read is reported by the SFTP tab itself (the preview panel),
            # not by a "transfer complete" line in the status bar.
            if entry[0] != "read":
                self.status_message.emit(t("sftp.transfer_done", name=entry[1]), 5000)

    def _on_sftp_task_error(self, task_id: int, kind: str, message: str):
        if self._shut_down:
            return   # v1.8rc6 (N56): the posted-emission guard of the transfer family
        t = host_attr(self, "get_translator")()
        self._drop_transfer_meter(task_id)   # v1.3.3.4 (task 6): the meter dies with the task
        entry = self._sftp_tasks.pop(task_id, None)
        if entry is not None and entry[0] in self._SFTP_PROGRESS_KINDS:
            self._sftp_busy = max(0, self._sftp_busy - 1)
            if self._sftp_busy == 0:
                self.progress_hidden.emit()
        if kind == "read":
            # v1.3.1: the message of a read error is a MACHINE code — the SFTP tab
            # translates it (its message signal → the bridge); showing it here as
            # well would duplicate the hint with an untranslated code.
            return
        if kind in host_attr(self, "OP_KINDS"):
            # v1.3.3.2: a file operation — the SFTP tab wraps the server's error in
            # its own translated line (the same no-duplication rule as for "read").
            return
        refusal = host_attr(self, "sftp_name_refusal_text")(message)
        if refusal:
            # v1.7.5.1 (N40): a server name this platform cannot turn into a path — the ONE
            # renderer of that payload, so the sentence is the user's language, not JSON.
            self.status_message.emit(refusal, 8000)
            return
        prefix = t("terminal.error_prefix")
        self.status_message.emit(f"{prefix} {message}", 8000)

    def _on_sftp_task_cancelled(self, task_id: int, kind: str):
        if self._shut_down:
            return   # v1.8rc6 (N56): the posted-emission guard of the transfer family
        t = host_attr(self, "get_translator")()
        self._drop_transfer_meter(task_id)   # v1.3.3.4 (task 6): the meter dies with the task
        entry = self._sftp_tasks.pop(task_id, None)
        if entry is not None and entry[0] in self._SFTP_PROGRESS_KINDS:
            self._sftp_busy = max(0, self._sftp_busy - 1)
            if self._sftp_busy == 0:
                self.progress_hidden.emit()
        self.status_message.emit(t("sftp.transfer_cancelled"), 5000)

    def _on_sftp_worker_finished(self):
        """The worker stopped on its own (the transport died — the session
        closed/crashed): a state reset; the tab returns to "waiting", a restart —
        on the next switch to it, if a live connection appears. v1.3.3.5: a page
        without the SFTP tab has no worker to reset — the guard keeps it symmetrical."""
        try:
            self._sftp_worker = None
            self._sftp_tasks.clear()
            self._transfer_meters.clear()   # v1.3.3.4 (task 6): no live task — no meter
            self._sftp_busy = 0
            self.progress_hidden.emit()
            if getattr(self, "sftp_tab", None) is not None:
                self.sftp_tab.set_worker(None)
                # v1.8: the transport died with the worker — an elevation that rode it loses its
                # channel and is dropped by the pane (ELEVATED_PANE.md §4).
                self.sftp_tab.set_transport(None)
        except RuntimeError:
            pass  # the C++ object was already destroyed (a close race)
