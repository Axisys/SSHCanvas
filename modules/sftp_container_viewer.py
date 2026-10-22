# -*- coding: utf-8 -*-
"""The ONE preview slot of the Files tab and the live settings of its reader (mixed into `SftpTab`).

`SftpContainerViewerMixin` routes the panel the panes share: `preview_pane()` is the ONE answer of
"who carries a preview", `preview_allowed()` the ONE rule of one-at-a-time, and `present_viewer()` the
mc `F3` move into the OTHER pane with its way back (`_restore_borrowed_viewer()`). Beside it sit the
three settings the SETTINGS hub re-applies to the open containers at once — the word wrap, the
encoding and the read ceiling. The facade's names are resolved through `host_attr()` (`AGENTS.md`
§4.1).

Contract — `SFTP_PANES.md` §3b, `ARCHIVES.md` §5; mechanism — `DOCUMENTATION.md` §14f, §38.
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

try:  # v1.14.1: the PURE half of the reader's verbs — the hue and the address allowlist
    from .sftp_pane_helpers import (NETWORK_VERBS, network_command, parse_network_target,
                                    viewer_background_hue)
except ImportError:  # flat launch from the project root
    from sftp_pane_helpers import (NETWORK_VERBS, network_command,  # type: ignore
                                   parse_network_target, viewer_background_hue)

try:  # v1.14.1: the split of the container this tab lives in — the parent-chain walk
    from .terminal_split import find_split
except ImportError:  # flat launch from the project root
    from terminal_split import find_split  # type: ignore

try:  # v1.14.1: the KERNEL gate of the Linux-only verbs (the `uname -s` fact)
    from ..models.server import is_linux_host
except ImportError:
    from models.server import is_linux_host  # type: ignore


class SftpContainerViewerMixin:
    """The preview slot routing and the live viewer settings (mixed into `SftpTab`)."""

    # ── the ONE preview slot of the two-pane view (the mc `F3`) ─────────

    def preview_pane(self):
        """The pane whose splitter carries an open preview (None — nothing is being previewed).

        The viewer widget is OWNED by the pane it was built in but may be CARRIED by the other one
        (`present_viewer_in()`), so the reader is asked of every pane: that single answer is what
        `close_preview()` closes and what the pane switch must not lose.
        """
        for pane in list(self._panes):
            try:
                if pane.viewer_host() is not None:
                    return pane
            except RuntimeError:
                continue  # Qt teardown — the pane is already gone
        return None

    def preview_source(self):
        """The pane whose listing opened the open preview (None — nothing is being previewed)."""
        pane = self.preview_pane()
        if pane is None:
            return None
        return pane._viewer_from or pane

    def preview_in_other_pane(self, pane) -> bool:
        """True while the OTHER pane carries a borrowed panel — a PANEL, not a listing (v1.7).

        The walk asks this before a pane switch: a pane whose listing is off the screen is not a
        destination for `Tab`/`Shift+Tab`, so the key is consumed and the reading pane keeps the
        keyboard until `Esc` closes the preview.
        """
        other = self.other_pane(pane)
        return bool(other is not None and getattr(other, "_viewer_borrowed", False))

    def preview_allowed(self, pane, report=True) -> bool:
        """May `pane` open — or be shown — a preview now? False — a panel of the OTHER pane is up.

        ONE preview at a time, judged by the OWNER: its own pane replaces its content (the `F3`
        walk), the other owner REFUSES with `sftp.cmd.preview_busy`; `report=False` is the SHOW
        path, whose key is long gone.
        """
        if pane is None or pane not in self._panes:
            return True   # a foreign pane: nothing to route, the caller keeps its in-pane panel
        if self._pane_b is None:
            return True   # ONE pane: its preview stays inside it (the shipped look)
        owner = self.preview_pane()
        if owner is None or owner is pane:
            return True
        if report:
            pane.message.emit(_t("sftp.cmd.preview_busy"))
        return False

    def present_viewer(self, pane) -> bool:
        """Show `pane`'s panel WHERE THE OTHER PANE IS (the mc `F3`); False — it stays in its own.

        False for ONE pane, for an other pane that already carries a panel of this one (`ARCHIVES.md`
        §5), and for a read that lost the race against a preview opened meanwhile — the panel then
        shows in its OWN pane, keeping the one-preview rule true.
        """
        if pane is None or pane not in self._panes:
            return False
        other = self.other_pane(pane)
        if other is None:
            return False
        if getattr(other, "_viewer_borrowed", False):
            return False
        if not self.preview_allowed(pane, report=False):
            return False
        moved = bool(pane.present_viewer_in(other, source=pane))
        if moved:
            try:
                other._sync_secondary_ui()
            except RuntimeError:
                pass  # Qt teardown
        return moved

    def close_preview(self) -> bool:
        """`Esc` — close the open preview, wherever it is shown; False — there was none.

        The panel goes back to the pane it belongs to and that pane's listing (its address bar,
        its buttons or its hints) comes back; the focus stays where the keyboard was, which is the
        listing the file was opened from. False lets `Esc` fall through to the focused widget.
        """
        pane = self.preview_pane()
        if pane is None:
            return False
        try:
            pane.close_viewer()
        except RuntimeError:
            return False  # Qt teardown — there is nothing left to close
        return True

    def _restore_borrowed_viewer(self, pane):
        """Hand a borrowed preview back to its OWNER before `pane` goes away. Never raises.

        Called from `_close_viewer_of()`: the pane that is dying may be the pane CARRYING the
        viewer (then the owner takes it home) or the pane that LENT it (then the borrower gets its
        listing back). A pane with no preview involved changes nothing.
        """
        try:
            host = pane.viewer_host()
        except (RuntimeError, AttributeError):
            return
        if host is None:
            return
        for owner in list(self._panes):
            if owner is pane:
                continue
            try:
                if owner.viewer_host() is host:
                    owner.restore_viewer()
                    return
            except (RuntimeError, AttributeError):
                continue

    # ── the live settings of the reader (ONE key each, re-applied at once) ──

    def apply_viewer_wrap(self, on) -> bool:
        """Write the ONE word-wrap key and apply it to EVERY pane of this container (v1.7.3)."""
        saved = host_attr(self, "save_viewer_wrap")(bool(on))
        for pane in list(self._panes):
            try:
                pane.set_viewer_wrap(on, persist=False)
            except RuntimeError:
                continue   # Qt teardown — the pane is already gone
        return saved

    def apply_viewer_encoding(self, codec, pane=None) -> str:
        """Write the ONE encoding key and apply it to the pane(s) the caller names (v1.9.3, v1.12.3).

        The reader's encoding is ONE remembered DEFAULT (`ui_viewer_encoding`) beside a PER-PANE
        choice: `pane=None` walks EVERY pane of this container — a container-wide change, where every
        pane follows — while a pane asks for ITSELF (`pane=self`) when the user picks a codec in its
        own menu, and its sibling keeps whatever it holds. Either way the chosen value is written as
        the remembered default, so the next pane (and the next session) starts where the last
        explicit choice left off. Returns the NORMALISED value that was applied.
        """
        resolved = host_attr(self, "normalize_viewer_encoding")(codec)
        host_attr(self, "save_viewer_encoding")(resolved)
        targets = list(self._panes) if pane is None else [pane]
        for target in targets:
            try:
                target.set_viewer_encoding(resolved, persist=False)
            except RuntimeError:
                continue   # Qt teardown — the pane is already gone
        return resolved

    def apply_viewer_max_bytes(self, value) -> int:
        """Apply a new preview CEILING to every pane of this container (v1.7.5).

        The settings hub owns the key (it writes it on OK); the live containers are told here, so
        an OPEN tab reads with the new cap at once and the "no preview" facts of the old one are
        dropped pane by pane (`set_viewer_max_bytes`). Never raises.
        """
        cap = host_attr(self, "clamp_viewer_max_bytes")(value)
        for pane in list(self._panes):
            try:
                cap = pane.set_viewer_max_bytes(cap)
            except (RuntimeError, AttributeError):
                pass  # Qt teardown / a bare stub — the pane keeps its own
        return cap

    # ── v1.14.1: the reader's background hue (ONE key, every pane) ───────

    def apply_viewer_background(self, hue, pane=None):
        """Write the ONE reader-background key and apply it to EVERY pane (v1.14.1).

        The twin of `apply_viewer_max_bytes()`: the KEY goes first (the `viewer.background` QSS
        builder reads the config, so a pane refreshed before the write would paint the old hue),
        then each pane repaints its own surface. The pane that ASKED is answered with ONE status
        sentence — the choice is global and persistent, and nothing else on the screen would say so.
        Returns the NORMALISED hue (None — the theme's own look).
        """
        resolved = viewer_background_hue(hue)[0]
        host_attr(self, "save_viewer_background")(resolved)
        for target in list(self._panes):
            try:
                target.set_viewer_background(resolved, persist=False)
            except (RuntimeError, AttributeError):
                continue   # Qt teardown — the pane is already gone
        name_of = getattr(pane, "background_name", None)
        if callable(name_of):
            try:
                pane.message.emit(_t("sftp.viewer.background_applied", name=name_of(resolved)))
            except RuntimeError:
                pass   # Qt teardown — the reader that asked is already gone
        return resolved

    # ── v1.14.1: the reader's `Network ▸` verbs (the SESSION's, over its selection) ──

    def append_network_menu(self, menu, pane=None) -> int:
        """Add the `Network ▸` submenu to the reader's menu — the verbs really offered (0 — none).

        Offered ONLY when the session is a Linux one (`is_linux_host`, the `uname -s` KERNEL fact —
        `os_name` carries no "Linux" word) AND the reader's SELECTION is an address the allowlist
        accepts. A name, a URL, a path and a half-typed address are refused BEFORE a menu exists, so
        no text of a document ever reaches a command (`AGENTS.md` §4.15).
        """
        if menu is None or getattr(self, "_session_data", None) is None:
            return 0
        if not is_linux_host(self._session_data):
            return 0
        reader = getattr(pane, "viewer_selection", None)
        if not callable(reader):
            return 0
        try:
            selection = str(reader() or "")
        except RuntimeError:
            return 0   # Qt teardown — the reader is already gone
        target = parse_network_target(selection)
        if target is None:
            return 0
        submenu = menu.addMenu(_t("sftp.network.menu"))
        offered = 0
        actions = []
        for verb in NETWORK_VERBS:
            command = network_command(verb, target[0])
            if not command:
                continue
            action = submenu.addAction(_t(f"sftp.network.{verb}", host=target[0]))
            action.triggered.connect(lambda _checked=False, cmd=command:
                                     self.run_network_command(cmd))
            actions.append(action)
            offered += 1
        # Qt gotcha #9: a dying Python `QAction` wrapper destroys its `QMenu` — and the action a
        # submenu is INSTALLED with is the one `menu.addMenu()` created. The pane keeps the submenu,
        # ITS OWN action and the verb actions, so a menu built on one right click outlives the
        # wrapper that built it (`_qaction_guard` rule).
        if pane is not None:
            try:
                pane._network_menu = submenu
                pane._network_menu_action = submenu.menuAction()
                pane._network_actions = actions
            except (AttributeError, RuntimeError):
                pass   # a bare stub without the attribute — the menu lives with its parent
        return offered

    def run_network_command(self, command) -> bool:
        """Run ONE literal command in the session's terminal SPLIT — the `Network ▸` door.

        The split belongs to the container this tab lives in (`TerminalSplit`), reached by the
        parent-chain walk, so a Files pane shown as a tab, a right-hand panel or a moved stack finds
        the SAME door. The pane is a real second session of the same node with the same credential
        (`TerminalSplit.set_enabled`); False — nothing was opened.
        """
        split = find_split(self)
        if split is None or not command:
            return False
        return bool(split.set_enabled(True, initial_command=str(command)))
