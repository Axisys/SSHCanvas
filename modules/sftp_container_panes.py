# -*- coding: utf-8 -*-
"""The PANES, the Commander, the ACTIVE pane and the sources of the Files tab (mixed into `SftpTab`).

`SftpContainerPanesMixin` owns what a CONTAINER does with the panes it holds: the pane list and the
ACTIVE one, the mc/far pane switch, the ONE question a source switch asks (`can_use_local()` /
`can_elevate()`), the listing refresh a finished operation triggers, and the two-pane view itself
(`set_commander()` with its ratio, its hints and its teardown). The facade's names are resolved at
call time through `host_attr()` — a mixin never imports `modules.sftp_tab` (`AGENTS.md` §4.1).

Contract — `SFTP_PANES.md` §1, §4-§6, `LOCAL_PANE.md` §4, `ELEVATED_PANE.md` §4;
mechanism — `DOCUMENTATION.md` §14f, §59-§63.
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


class SftpContainerPanesMixin:
    """The pane list, the Commander, the ACTIVE pane and the sources (mixed into `SftpTab`)."""

    # ── the pane list and the ACTIVE pane ────────────────────────────────

    @property
    def panes(self) -> list:
        """The live panes, in splitter order (the FIRST one is the shipped listing)."""
        return list(self._panes)

    @property
    def active_pane(self):
        """The pane that owns the buttons and the keys (never None while a pane exists)."""
        return self._active_pane

    @property
    def commander(self) -> bool:
        """The two-pane view is ON (the persisted `ui_sftp_commander` state)."""
        return bool(self._commander)

    def other_pane(self, pane=None):
        """The pane that is NOT `pane` — the DESTINATION of F5/F6 (v1.7rc2).

        None while the mode is off (one pane has nothing to copy to): the key then answers
        ONE honest sentence instead of a silent no-op. `pane` defaults to the ACTIVE one.
        """
        pane = pane if pane is not None else self._active_pane
        for other in list(self._panes):
            if other is not pane:
                return other
        return None

    # ── the ACTIVE pane and the mc/far walk ─────────────────────────────

    def set_active_pane(self, pane) -> bool:
        """Make `pane` the ACTIVE pane; True — the state really changed.

        The ring is drawn only in the two-pane mode: a single pane has nothing to compete
        with, and the shipped look carries no frame. Never raises.
        """
        if pane is None or pane not in self._panes:
            return False
        changed = pane is not self._active_pane
        self._active_pane = pane
        if self._commander:
            for p in self._panes:
                p.set_active(p is pane)
        return changed

    def focus_pane(self, pane):
        """Make `pane` the ACTIVE pane AND give it the keyboard; None — it is not a pane.

        The second half is the v1.7rc3 half: the mc/far `Tab` is a PANE switch, so the keyboard
        has to land in the other pane's listing (the ring alone would leave the keys where they
        were). The ring, the buttons and the shipped tab-level reads all follow `set_active_pane`.
        """
        if pane is None or pane not in self._panes:
            return None
        self.set_active_pane(pane)
        try:
            pane.focus_listing()
        except (RuntimeError, AttributeError):
            pass  # Qt teardown — the pane has no listing left to focus
        return pane

    def focus_other_pane(self, pane, back: bool = False):
        """`Tab` / `Shift+Tab` (v1.7rc3): give the keyboard to the OTHER pane.

        With ONE pane there is nothing to switch to and the answer is None — the key falls
        through to the widget (the shipped single-pane look keeps its tab order). With TWO panes
        the walk is a two-item CYCLE: from either pane the key lands on the other one, so `Tab`
        and `Shift+Tab` are inverses of each other and neither can walk out of the Files tab.
        `back` reverses the direction (the pane BEFORE this one in the splitter).
        """
        panes = list(self._panes)
        if pane not in panes or len(panes) < 2:
            return None
        index = panes.index(pane)
        step = -1 if back else 1
        return self.focus_pane(panes[(index + step) % len(panes)])

    def _sync_active_ring(self):
        """Draw the ring on the ACTIVE pane (and only in the two-pane mode)."""
        for p in self._panes:
            p.set_active(self._commander and p is self._active_pane)

    # ── the sources of a pane (LOCAL_PANE.md §4) ────────────────────────

    def can_use_local(self, pane) -> bool:
        """May THIS pane read the OS disk? The ONE question the switch and the pane ask.

        TWO conditions, both structural (LOCAL_PANE.md §4): the container must hold TWO panes —
        the Commander is what makes "the other side" a concept, so with one pane there is
        nothing to browse the local disk BESIDE — and the pane must be the SECOND one, because
        the first is the SESSION's own remote tree (the cwd follow, the `Send to…` provider and
        the Files panel all address it).

        A single-pane view of a SESSION (`terminal_mode = "tabs"`'s dock and the v1.7.1 Files
        PANEL) therefore answers False by construction: it holds ONE pane, and the ask is refused
        with ONE sentence instead of a dead control.
        """
        if pane is None or pane not in self._panes:
            return False
        if len(self._panes) < 2:
            return False
        return pane is not self._panes[0]

    def can_elevate(self, pane) -> bool:
        """May THIS pane read the server as ANOTHER user? The sibling of `can_use_local()`.

        The SAME two structural conditions, for the same reasons (`ELEVATED_PANE.md` §4): the
        elevation replaces the provider of a pane BESIDE the session's own tree, so it is offered
        on the SECOND pane of a two-pane container alone — the first pane, the dock's single-pane
        view and the Files panel answer False and are refused with ONE sentence.
        """
        return self.can_use_local(pane)

    def pane_source(self, pane) -> str:
        """The source a pane reads (`SOURCE_REMOTE` for a pane this container does not hold)."""
        try:
            return str(pane.source)
        except (AttributeError, RuntimeError):
            return host_attr(self, "SOURCE_REMOTE", "remote")

    def set_pane_source(self, pane, source: str, notify: bool = True) -> bool:
        """Switch ONE pane's source through the pane (the container's door, v1.7.4rc1)."""
        if pane is None or pane not in self._panes:
            return False
        try:
            return bool(pane.set_source(source, notify=notify))
        except (RuntimeError, AttributeError):
            return False

    # ── the listings a finished operation re-lists ──────────────────────

    def pane_for_provider(self, provider):
        """The pane whose slots are BOUND to `provider` (`None` — no pane holds it, v1.7.4).

        ONE pane answers ONE provider (§1), so a batch that runs on a provider the pane that
        STARTED it no longer holds — a local pane uploading through the session's transport — is
        COUNTED by the pane bound to that transport.
        """
        if provider is None:
            return None
        for pane in list(self._panes):
            try:
                if pane._bound_provider is provider:
                    return pane
            except RuntimeError:
                continue   # Qt teardown — that pane is already gone
        return None

    def relist_dir(self, path: str):
        """Re-list EVERY pane that is SHOWING `path` (v1.7rc2).

        A remote copy/move changes a directory that may be on either screen: the pane that
        ran the operation owns the report, the LISTINGS are the container's business. A pane
        showing another directory is left alone (its answer is still true).
        """
        if not path:
            return
        for pane in list(self._panes):
            try:
                if pane.source != host_attr(self, "SOURCE_REMOTE", "remote"):
                    continue   # v1.7.4rc1: a LOCAL pane owns its listing (LOCAL_PANE.md §1)
                if pane.current_dir == path:
                    pane._relist(path)
            except RuntimeError:
                continue   # Qt teardown — the pane is already gone

    def relist_pane(self, pane, path: str):
        """Re-list the ONE listing a finished transfer really CHANGED (v1.7.4rc2).

        The destination of a batch answers through the dialect of the pane it belongs to: a REMOTE
        path keeps the shipped rule (`relist_dir` re-lists every remote pane showing it, and the
        copy may have been started in either one), while a LOCAL path belongs to the pane whose
        provider owns it and to nobody else — the OS disk is nobody's server, and re-listing
        another pane there would navigate it to a path of the wrong dialect.
        """
        if not path or pane is None:
            return
        try:
            local = getattr(pane, "source", host_attr(self, "SOURCE_REMOTE", "remote")) == host_attr(self, "SOURCE_LOCAL", "local")
        except RuntimeError:
            return   # Qt teardown — the pane is already gone
        if not local:
            self.relist_dir(path)
            return
        try:
            if pane in list(self._panes) and pane.paths.same(pane.current_dir, path):
                pane._relist(path)
        except (RuntimeError, AttributeError):
            return   # Qt teardown — the pane is already gone

    # ── the construction and the teardown of ONE pane ───────────────────

    def _new_pane(self):
        """Create a pane, wire it up and put it in the splitter (ONE construction path)."""
        pane = host_attr(self, "_SftpPane")(self, self)
        pane.message.connect(self.message)
        index = self.pane_splitter.count()
        self.pane_splitter.addWidget(pane)
        self.pane_splitter.setCollapsible(index, False)
        self._panes.append(pane)
        pane.bind_worker(None, self._worker)
        return pane

    def _destroy_pane(self, pane):
        """Tear ONE pane down: unbind its worker, drop its preview, remove it. Never raises.

        v1.7rc3: a preview this pane LENT or BORROWED is closed FIRST — the viewer widget belongs
        to its owner and must not be destroyed together with a pane that was only showing it.
        """
        try:
            self._close_viewer_of(pane)
        except Exception:  # noqa: BLE001 — teardown robustness
            pass
        try:
            pane.release()
        except Exception:  # noqa: BLE001 — teardown robustness
            pass
        try:
            self.pane_splitter.setCollapsible(self.pane_splitter.indexOf(pane), True)
        except (RuntimeError, TypeError):  # noqa: BLE001 — teardown of a dead object: the splitter is already gone
            pass
        if pane in self._panes:
            self._panes.remove(pane)
        try:
            pane.setParent(None)
            pane.deleteLater()
        except RuntimeError:
            pass  # teardown race — the pane dies with its parent anyway
        for p in self._panes:
            p.setMinimumWidth(0)
        if self._active_pane is pane:
            self._active_pane = self._panes[0] if self._panes else None

    def _ensure_second_pane(self):
        """Create the second pane (idempotent) and start it in the first pane's directory."""
        if self._pane_b is not None:
            return self._pane_b
        first = self._panes[0] if self._panes else None
        pane = self._new_pane()
        if first is not None:
            pane._current_dir = first.current_dir
        pane.bind_worker(None, self._worker)   # the new pane lists its directory too
        self._pane_b = pane
        for p in self._panes:
            p.setMinimumWidth(host_attr(self, "COMMANDER_MIN_PANE_PX"))
        # v1.7rc3: the role of every pane follows the mode (the right one loses the button row).
        self._sync_hint_rows()
        return pane

    def _close_viewer_of(self, pane):
        """Close the preview a pane OWNS or CARRIES, keeping the viewer widget alive.

        The panel is a widget of its OWNER: a pane that merely CARRIES it must hand it back
        before it goes away (and the owner must let go of its own panel), so the sibling always
        ends up with a clean listing. Called when the two-pane mode goes off and when a pane is
        torn down. Never raises.
        """
        for owner in list(self._panes):
            try:
                if owner.viewer_host() == pane:
                    owner.close_viewer()
            except (RuntimeError, AttributeError):
                continue  # Qt teardown — that pane is already gone

    # ── the two-pane view ───────────────────────────────────────────────

    def _sync_hint_rows(self):
        """v1.7rc3: the button row belongs to the FIRST pane, the hint row to the second.

        ONE rule for the container: in the two-pane mode only the left pane keeps the shipped
        button row (and the right one shows the key hints), in the single-pane mode the only
        pane keeps them. `_panes[0]` is the FIRST pane for the whole life of the tab — the
        second one is the one that comes and goes — which is what makes the rule idempotent.
        """
        panes = list(self._panes)
        if not panes:
            return
        first = panes[0]
        for p in panes:
            try:
                p.secondary = self._commander and p is not first
            except RuntimeError:
                continue  # Qt teardown — the pane is already gone

    def set_commander(self, on) -> bool:
        """Turn the two-pane view on/off; False — it could not be created (the caller
        puts its checkmark back, the `set_split_enabled()` discipline).

        ON — a SECOND pane appears to the right of the first, starting WHERE the first one
        is (a commander's second pane that starts somewhere else is a puzzle, not a tool),
        the ratio is applied and the ACTIVE pane is ringed. **The cwd follow is switched OFF
        here and stays off**: one OSC 7 report cannot say which of the two panes should move,
        and a listing that walks under the keyboard is worse than no follow — the owner (the
        session) is told through `follow_cwd_changed`, so the checkbox and the session state
        cannot diverge.

        v1.7.4rc1: the SECOND pane is also the ONE pane whose source may be switched to the OS
        disk (LOCAL_PANE.md §4) — the switch is enabled by `_sync_hint_rows()` below, which is
        why the pane is created and then told its role.

        OFF — the second pane is torn down; the FIRST one keeps its directory, its listing
        and its viewer.
        """
        on = bool(on)
        if on == self._commander:
            return True
        if on:
            pane = self._ensure_second_pane()
            if pane is None:
                return False
            self._commander = True
            self._apply_commander_sizes()
            self.set_active_pane(self._active_pane or self._panes[0])
            self._sync_active_ring()
            self._sync_hint_rows()
            if self._follow_cwd:
                # the mode cannot honour the follow: OFF, and the session is told
                self._follow_cwd = False
                self._set_follow_checkbox(False)
                try:
                    self.follow_cwd_changed.emit(False)
                except RuntimeError:
                    pass  # Qt teardown
            self._sync_follow_availability()
            self.message.emit(_t("sftp.commander_hint"))
            return True
        # OFF
        pane = self._pane_b
        self._pane_b = None
        self._commander = False
        if pane is not None:
            self._close_viewer_of(pane)
            self._destroy_pane(pane)
        self.set_active_pane(self._panes[0] if self._panes else None)
        for p in self._panes:
            p.set_active(False)
        self._sync_hint_rows()
        self._sync_follow_availability()
        return True

    def commander_ratio(self):
        """The FIRST pane's CURRENT share of the width (None — nothing to measure).

        None while the mode is off: a ratio measured on a hidden member would be 0 and would
        overwrite the proportion the user left behind (the split's rule, §4.3).
        """
        if not self._commander or self._pane_b is None:
            return None
        try:
            sizes = self.pane_splitter.sizes()
        except RuntimeError:
            return None
        if len(sizes) < 2:
            return None
        total = sum(sizes)
        if total <= 0 or sizes[0] <= 0:
            return None
        return sizes[0] / float(total)

    def _on_commander_moved(self, _pos=None, _index=None):
        """The user dragged the pane divider — the new proportion becomes THE ratio."""
        ratio = self.commander_ratio()
        if ratio is None:
            return
        self._commander_ratio = max(host_attr(self, "COMMANDER_RATIO_MIN"),
                                    min(host_attr(self, "COMMANDER_RATIO_MAX"), ratio))

    def _apply_commander_sizes(self):
        """Apply the stored proportion through `setSizes` only (Qt gotcha #13). Never raises."""
        if self._pane_b is None:
            return
        try:
            total = self.pane_splitter.width() - self.pane_splitter.handleWidth()
        except RuntimeError:
            return
        if total <= 0:
            return  # not laid out yet — the ratio is applied on the next pass
        left = int(round(total * self._commander_ratio))
        left = max(1, min(left, total - 1))
        try:
            self.pane_splitter.setSizes([left, total - left])
        except RuntimeError:
            pass  # C++ teardown — nothing to size

    def commander_extra_config(self, extra: dict = None) -> dict:
        """The two-pane state as CONFIG keys, for the window's SINGLE geometry write.

        The `_save_split_state()` shape: the ratio is re-read from the live splitter (a
        hidden/never-shown mode keeps the last real proportion) and clamped.
        """
        ratio = self.commander_ratio()
        if ratio is not None:
            self._commander_ratio = max(host_attr(self, "COMMANDER_RATIO_MIN"),
                                        min(host_attr(self, "COMMANDER_RATIO_MAX"), ratio))
        payload = {
            host_attr(self, "COMMANDER_CONFIG_BOOL"): bool(self._commander),
            host_attr(self, "COMMANDER_CONFIG_RATIO"): round(float(self._commander_ratio), 4),
        }
        if isinstance(extra, dict):
            extra.update(payload)
            return extra
        return payload
