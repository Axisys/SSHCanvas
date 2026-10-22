# -*- coding: utf-8 -*-
"""The worker, the transport, the dirs memory, the follow and the relay of the Files tab.

`SftpContainerSessionMixin` owns everything one SESSION gives the container: the identity it is
filed under (`set_session_info()` and its four readers), the ONE `SftpWorker` binding and the live
`paramiko.Transport` the elevation rides, the per-server directory memory that is merged into the
window's single config write, the follow switch (a session state, its checkbox only a VIEW), and the
cross-session relay with its ONE send per target. The facade's names are resolved at call time
through `host_attr()` (`AGENTS.md` §4.1, §4.8).

Contract — `SFTP_PANES.md` §2, §5-§6, `ELEVATED_PANE.md` §2; mechanism — `DOCUMENTATION.md` §14f.
"""
try:  # AGENTS.md §4.1: the ONE seam for a facade global — a mixin never imports the facade module
    from ..ui.mixin_support import host_attr
except ImportError:
    from ui.mixin_support import host_attr

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # v1.7.3: the cross-session relay — the module's OWN lower-layer import, never the facade's
    from . import sftp_send as send
except ImportError:  # flat launch from the project root
    import sftp_send as send  # type: ignore

try:  # v1.7.3: the parent-chain host hook of the Send-to provider
    from .terminal_split import find_host_hook
except ImportError:  # flat launch from the project root
    from terminal_split import find_host_hook  # type: ignore


class SftpContainerSessionMixin:
    """The session identity, the bindings, the dirs memory, the follow and the relay (into `SftpTab`)."""

    # ── the session's identity (the per-server memory and `Send to…` use it) ──

    def set_session_info(self, key: str = "", label: str = "", host: str = "", port=None,
                         user: str = "", data=None):
        """The SESSION this container lists (called once by the page that builds it).

        The key is the `history_key()` of the server — the same fact the per-server directory
        memory is filed under — and `(host, port)` is what turns a send into the server-side
        `queue_copy()` path instead of a relay. A bare container (a unit test) simply has no
        identity: no target is offered and no directory is remembered.

        v1.7.5: `user` joins the identity because the pane's SOURCE HEADER LINE falls back to
        `user@host` when the session was never identified (LOCAL_PANE.md §3) — and every pane
        re-reads its header here, which is what makes the line say the session it belongs to.
        v1.14.1: `data` is the node's LIVE `ServerData` — the Linux gate of the reader's
        `Network ▸` row reads its `kernel_name`, and the object is kept (never copied) so a
        collection that lands while the tab is open is seen by the next menu.
        """
        self._session_key = str(key or "")
        self._session_label = str(label or "")
        self._session_host = str(host or "")
        self._session_port = port
        self._session_user = str(user or "")
        self._session_data = data
        self._sync_pane_headers()

    def session_key(self) -> str:
        """The stable identity of this session ("" — a container nobody identified)."""
        return str(self._session_key or "")

    def session_label(self) -> str:
        """The session's ALIAS (`set_session_info`), or "" when it was never identified."""
        return str(self._session_label or "")

    def session_user(self) -> str:
        """The login user of the session (the `user@host` fallback of the header line)."""
        return str(self._session_user or "")

    def session_host(self) -> str:
        """The host of the session (the `user@host` fallback of the header line)."""
        return str(self._session_host or "")

    def session_data(self):
        """The node's LIVE `ServerData` (None — a container nobody identified, or a bare test stub)."""
        return getattr(self, "_session_data", None)

    def _sync_pane_headers(self):
        """Let every pane re-read its SOURCE header line (the identity just changed). Never raises."""
        for pane in list(self._panes):
            try:
                pane._sync_header()
            except (RuntimeError, AttributeError):
                pass  # Qt teardown / a bare stub — the line keeps what it has

    # ── the worker and the transport (the page's two calls) ─────────────

    def set_worker(self, worker):
        """Bind/unbind the ONE SftpWorker of this session; None — the "waiting" state.

        The worker is the CONTAINER's (SFTP_PANES.md §2): one transport, one queue, two
        panes. Each pane re-binds its own slots, so the two listings stay independent.
        """
        old = self._worker
        self._worker = worker
        for pane in list(self._panes):
            pane.bind_worker(old, worker)
        self._sync_follow_availability()

    @property
    def worker(self):
        """The bound SftpWorker (None before the connection / after it died)."""
        return self._worker

    def set_transport(self, transport):
        """Publish the live `paramiko.Transport` of this session (the page's ONE call).

        The elevated channel rides the transport the Files tab already uses, so the pane needs the
        object and may not reach into the session's worker for it. `None` — the transport is gone:
        every pane drops an elevation that has no channel left, instead of listing through a dead
        one. Never raises.
        """
        self._transport = transport
        if transport is not None:
            return
        for pane in list(self._panes):
            try:
                pane.transport_lost()
            except (RuntimeError, AttributeError):
                continue   # Qt teardown / a bare stub — nothing to drop

    def transport(self):
        """The live transport of this session (`None` — never connected / already gone)."""
        return getattr(self, "_transport", None)

    # ── the per-server directory memory ─────────────────────────────────

    def remember_dir(self, path: str) -> bool:
        """Remember the directory this session was left in (the server really answered for it)."""
        key = self.session_key()
        if not key or not str(path or "").startswith("/"):
            return False
        self._dirs = host_attr(self, "remember_dir")(self._dirs, key, path)
        self._dirs_touched = host_attr(self, "remember_dir")(self._dirs_touched, key, path)
        return True

    def remembered_dir(self) -> str:
        """The directory to OPEN with ("" — there is no memory / nobody identified this session)."""
        return host_attr(self, "remembered_dir_for")(self._dirs, self.session_key())

    def merge_dirs_into(self, payload: dict = None) -> dict:
        """Merge the per-server memory into the window's ONE config write (v1.7.3).

        MERGE-on-write: the live config is re-read (another session may have moved meanwhile), this
        container's own entries are filed into it, and the map — capped and evicted oldest-first —
        rides out under ONE key. The commander's own payload is deliberately NOT touched here:
        `SFTP_PANES.md` §5 declares those two keys, and a third one would change that contract.
        """
        out = dict(payload) if isinstance(payload, dict) else {}
        current = out.get(host_attr(self, "DIRS_CONFIG"))
        if not isinstance(current, dict):
            current = host_attr(self, "load_remembered_dirs")()
        merged = dict(current)
        for key, path in self._dirs_touched.items():
            merged = host_attr(self, "remember_dir")(merged, key, path)
        out[host_attr(self, "DIRS_CONFIG")] = merged
        return out

    # ── the cross-session relay: ONE send per target session ────────────

    def send_targets(self):
        """The sessions `Send to ▸` offers — resolved through the PARENT CHAIN (v1.7.3).

        The provider is the WINDOW's (`_send_session_targets`, the `_adopt_split_session`
        precedent): `modules/*` never imports `ui.main_window` (§4.1), so the hook is found by
        `find_host_hook()` and a detached container simply offers nothing. A target without a live
        SFTP worker cannot receive a file and is skipped here, once, for every caller.
        """
        provider = find_host_hook(self, "_send_session_targets")
        if not callable(provider):
            return []
        try:
            targets = provider(self.session_key()) or []
        except Exception:  # noqa: BLE001 — a broken provider must not break the menu
            return []
        return [t for t in targets if t is not None and getattr(t, "worker", None) is not None]

    def start_send(self, pane, target, entry: dict) -> bool:
        """Hand ONE row to the TARGET session's relay (v1.7.3). ONE send per session pair.

        The conversation itself lives in `modules/sftp_send.py`; the container owns the two things
        that must be true once per application state: the session's identity (the source endpoint)
        and the guard that a second send to the same target is refused with ONE sentence while the
        first one runs. The pane the user started from carries the reports.
        """
        if self._worker is None:
            pane.message.emit(_t("sftp.waiting_connection"))
            return False
        if target is None or getattr(target, "worker", None) is None:
            pane.message.emit(_t("sftp.send.no_targets"))
            return False
        key = str(getattr(target, "key", "") or "") or str(id(target))
        if key in self._sends:
            pane.message.emit(_t("sftp.send.busy",
                                 alias=getattr(target, "label", "") or getattr(target, "host", "") or "?"))
            return False
        coordinator = send.SendCoordinator(self._source_endpoint(pane), target, entry, parent=self,
                                           asker=self._send_asker(pane))
        coordinator.report.connect(pane.message.emit)
        coordinator.progress.connect(self._progress_reporter(pane, target, entry))
        coordinator.finished.connect(
            lambda result, p=pane, t=target, k=key: self._finish_send(p, t, k, result))
        self._sends[key] = coordinator
        if not coordinator.start():
            self._sends.pop(key, None)
            return False
        return True

    def _source_endpoint(self, pane) -> "send.SendEndpoint":
        """The endpoint of THIS session: its identity, its worker and the pane's directory."""
        return send.SendEndpoint(key=self.session_key(), label=self._session_label,
                                 host=self._session_host, port=self._session_port,
                                 user=self._session_user, worker=self._worker,
                                 directory=(pane.current_dir if pane is not None else "/"))

    @staticmethod
    def _send_asker(pane):
        """The pane's OWN overwrite question, adapted to the relay's `(parent, name, target, facts)`.

        The pane keeps its `_ask_conflict()` seam (the tests replace it, and the shipped dialog behind
        it), so the relay asks through the pane instead of reaching for `ask_conflict()` itself —
        the container owns the session, the PANE owns the question. "Apply to all" is never offered
        here: ONE file crosses per send.
        """
        def _ask(_parent, name, target_dir, facts=""):
            try:
                action, _apply_all = pane._ask_conflict(name, target_dir, 0, facts)
            except Exception:  # noqa: BLE001 — a dialog must never break a transfer
                return False
            return action == "overwrite"

        return _ask

    def _progress_reporter(self, pane, target, entry):
        """ONE composed progress line on the pane the user started from (1% steps at most)."""
        alias = str(getattr(target, "label", "") or getattr(target, "host", "") or "?")
        name = str(entry.get("name") or "")
        state = {"pct": -1}

        def _report(done: int, total: int):
            pct = int(done * 100 / total) if total else 0
            if pct == state["pct"]:
                return   # one line per percent — a status bar is not a progress log
            state["pct"] = pct
            try:
                pane.message.emit(_t("sftp.send.progress", name=name, alias=alias, pct=pct,
                                     done=host_attr(self, "format_size")(done), total=host_attr(self, "format_size")(total)))
            except RuntimeError:
                return   # Qt teardown — the pane is already gone

        return _report

    def _finish_send(self, pane, target, key: str, result: dict):
        """The ONE closing answer: forget the guard and re-list the directory that changed."""
        self._sends.pop(key, None)
        if not result.get("ok"):
            return
        refresh = getattr(target, "refresh", None)
        if not callable(refresh):
            return
        try:
            refresh(str(result.get("dir") or getattr(target, "directory", "") or ""))
        except Exception:  # noqa: BLE001 — a stale listing is not a failed send
            return

    def cancel_sends(self):
        """Cancel every send this container started (the pane's Cancel covers the relay too)."""
        for coordinator in list(self._sends.values()):
            try:
                coordinator.cancel()
            except Exception:  # noqa: BLE001 — a dead coordinator is already cancelled
                continue

    # ── the follow switch (a SESSION state, the checkbox a VIEW of it) ──

    def _set_follow_checkbox(self, checked: bool):
        """Write the checkbox WITHOUT reporting it back (the checkbox is a VIEW of the state)."""
        try:
            was = self.chk_follow_cwd.blockSignals(True)
            self.chk_follow_cwd.setChecked(bool(checked))
            self.chk_follow_cwd.blockSignals(was)
        except RuntimeError:
            pass  # Qt teardown

    def _sync_follow_availability(self):
        """The follow is available with a transport and NOT in the two-pane mode.

        One OSC 7 report cannot answer "which of the two panes" — in the Commander the
        switch is greyed (SFTP_PANES.md "The follow rule").
        """
        try:
            self.chk_follow_cwd.setEnabled(self._worker is not None and not self._commander)
        except RuntimeError:
            pass  # Qt teardown

    def _on_follow_toggled(self, checked: bool):
        """The follow checkbox → the session (which owns the hook and the config key)."""
        self._follow_cwd = bool(checked)
        try:
            self.follow_cwd_changed.emit(self._follow_cwd)
        except RuntimeError:
            pass  # Qt teardown — the tab is already gone

    def set_follow_cwd(self, enabled: bool):
        """Install the follow state in the checkbox WITHOUT reporting it back (v1.6.3).

        The page owns the state; this is its write path (the checkbox is a VIEW of it), so
        the signal is blocked — otherwise opening a session would "toggle" the setting.
        """
        self._follow_cwd = bool(enabled)
        self._set_follow_checkbox(self._follow_cwd)

    def follow_directory(self, path: str) -> bool:
        """v1.6.3: the shell moved — move the FIRST pane's listing with it.

        Refused in the two-pane mode (the follow is off there by construction) and forwarded
        to the FIRST pane otherwise: the OSC 7 report is a property of the SESSION, and the
        first pane is the one the shell was following.
        """
        if self._commander or not self._panes:
            return False
        return bool(self._panes[0].follow_directory(path))

    @property
    def current_dir(self) -> str:
        """The ACTIVE pane's directory (the upload target of the shipped single-pane read)."""
        pane = self._active_pane
        return pane.current_dir if pane is not None else "/"
