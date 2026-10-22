# -*- coding: utf-8 -*-
"""The read-only PREVIEW of ONE Files pane — the reader AND the archive view (`_SftpPane` wave 1).

`SftpPaneViewerMixin` owns the panel: the share of the `QSplitter`, the read task and its answer, the
header (size, the truncation notice, the encoding, the heuristic language), the pane's ONE
`QSyntaxHighlighter` with its lazy window, the word-wrap mode, the per-pane ENCODING choice and the
panel's MOVE into the other pane (`present_viewer_in()` / `restore_viewer()`). The SAME slot carries
the ARCHIVE listing and the SEARCH results: ONE panel at a time, and `panel_in_slot()` is the ONE
answer of what this pane shows. The reader's CEILING (`ui_viewer_max_bytes`) is resolved ONCE by the
pane and travels in the task (`AGENTS.md` §4.8).

Contract — `SFTP_PANES.md` §3b, `ARCHIVES.md`; mechanism — `DOCUMENTATION.md` §38, §64, §76, §14f.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # v1.4.7: detection + tokenizers + the ONE highlighter
    from . import syntax_highlight as syntax
except ImportError:
    import syntax_highlight as syntax

try:  # v1.13: the pure archive reader behind the `Open archive` row
    from . import archive_view as archive
except ImportError:
    import archive_view as archive  # type: ignore

try:  # v1.13.6: the pure search engine behind the `Find text…` row
    from . import sftp_search as search
except ImportError:
    import sftp_search as search  # type: ignore

try:  # v1.3.1: the shipped read policy — the FLOOR of the reader's ceiling
    from .sftp_worker import MAX_READ_BYTES
except ImportError:
    from sftp_worker import MAX_READ_BYTES

try:  # v1.9.3: the DECLARED encoding list, its normaliser and the value of "the shipped rule"
    from .sftp_pane_helpers import (VIEWER_ENCODING_DEFAULT, VIEWER_ENCODINGS,
                                    load_remembered_encodings, normalize_viewer_encoding,
                                    remember_encoding, remembered_encoding_for,
                                    resolve_viewer_encoding, save_remembered_encodings)
except ImportError:
    from sftp_pane_helpers import (VIEWER_ENCODING_DEFAULT, VIEWER_ENCODINGS,  # type: ignore
                                   load_remembered_encodings, normalize_viewer_encoding,
                                   remember_encoding, remembered_encoding_for,
                                   resolve_viewer_encoding, save_remembered_encodings)

try:  # AGENTS.md §4.1: the ONE seam for a facade global — a mixin never imports the facade module
    from ..ui.mixin_support import host_attr
except ImportError:
    from ui.mixin_support import host_attr

#: v1.7.5: the reader's CEILING as a SETTING — the reader truncates at the cap instead of refusing
#: the file, so `MAX_READ_BYTES` (the shipped read policy) is the DEFAULT and the FLOOR of this key
#: while the slider's top is a DECLARED 250 MiB. The pane resolves the cap ONCE and hands it to the
#: task (`_SftpTask.max_bytes`), so the worker never reads a config (AGENTS.md §4.8, §4.15).
VIEWER_MAX_BYTES_CONFIG = "ui_viewer_max_bytes"
VIEWER_MAX_BYTES_MIN = MAX_READ_BYTES            # 1 MiB — the shipped policy is the smallest cap
VIEWER_MAX_BYTES_MAX = 250 * 1024 * 1024         # the slider's hard top
VIEWER_MAX_BYTES_STEP = 1024 * 1024              # one step of the slider and of the value box
#: Above this the settings page WARNS: a `QPlainTextEdit` fed tens of megabytes is seconds of freeze.
VIEWER_MAX_BYTES_WARN = 3 * 1024 * 1024

#: The GUI cost of the ceiling, MEASURED (N57): the dominant term of one preview is
#: `QPlainTextEdit.setPlainText()` — the document build and layout — at ~159 ms per MiB, while the
#: decode (~0.17 ms/MiB) and the syntax verdict (~1.2 ms/MiB) are noise beside it. The freeze
#: cannot leave the GUI thread (a `QPlainTextEdit` document is built there), so the number is the
#: PRICE the setting carries, and the settings row prints it for the cap the user is choosing.
VIEWER_FREEZE_MS_PER_MB = 159.0


def viewer_freeze_seconds(cap) -> float:
    """PURE (N57): the seconds one preview of a `cap`-byte file costs on the GUI thread.

    A foreign value answers `0.0` — the caller is a label, never a gate. The slope is the declared
    `VIEWER_FREEZE_MS_PER_MB`, so the warning and the measurement cannot drift apart.
    """
    try:
        mib = max(0.0, float(cap) / (1024 * 1024))
    except (TypeError, ValueError):
        return 0.0
    return mib * VIEWER_FREEZE_MS_PER_MB / 1000.0


#: v1.13: the ARCHIVE view of the SAME panel (`ARCHIVES.md` §3) — the shipped listing's three
#: columns over the readable members of ONE level. The tree is FLAT on purpose: a member name carries
#: its own path, so a hierarchy would only repeat it.
ARCHIVE_COLUMNS = 3
ARCHIVE_COLUMN_WIDTH = 320

#: v1.13.6: the RESULTS panel of a search — TWO hidden-header columns, the `path:line` pair and the
#: matched text. ONE row per hit, capped by the engine's report (`sftp_search.MATCHES_PER_FILE`).
SEARCH_COLUMNS = 2
SEARCH_COLUMN_WIDTH = 380
SEARCH_ROW_TEXT_MAX = 160
#: The ONE sentence of a bound that stopped the walk — one i18n key per `sftp_search.CUT_*` code.
SEARCH_CUT_KEYS = {search.CUT_ENTRIES: "sftp.search.cut_entries",
                   search.CUT_DEPTH: "sftp.search.cut_depth",
                   search.CUT_BYTES: "sftp.search.cut_bytes",
                   search.CUT_MATCHES: "sftp.search.cut_matches"}


class _ArchiveTree(QTreeWidget):
    """The FLAT listing of ONE archive: `Esc` closes the view, `Enter` previews the current member.

    A SUBCLASS, never a patched slot (`AGENTS.md` §7): the two keys are the view's own and every
    other key stays Qt's (the arrows, the type-ahead and the selection walk are the tree's). It takes
    no drop — the archive panel is a READING surface (`ARCHIVES.md` §5).
    """

    def __init__(self, pane, parent=None):
        super().__init__(parent)
        self.pane = pane

    def keyPressEvent(self, event):  # noqa: N802 — Qt's own spelling
        pane = self.pane
        if pane is None or not pane.archive_key(event):
            super().keyPressEvent(event)


class _SearchTree(QTreeWidget):
    """The FLAT result list of ONE search: `Esc` closes the panel, `Enter` opens the current file.

    The twin of `_ArchiveTree` and for the same reason: the two keys are the view's own, the selection
    walk stays Qt's, and the list takes no drop (it is a READING surface).
    """

    def __init__(self, pane, parent=None):
        super().__init__(parent)
        self.pane = pane

    def keyPressEvent(self, event):  # noqa: N802 — Qt's own spelling
        pane = self.pane
        if pane is None or not pane.search_key(event):
            super().keyPressEvent(event)


class _FindTextDialog(QDialog):
    """The query dialog of `Find text…` — the needle, the subfolder scope and the case switch.

    A plain `QDialog` with three widgets, so a suite builds it and reads `query()` without an event
    loop; the pane asks it through `_ask_search_query()` (the ONE seam a test replaces). Qt's own
    `QDialogButtonBox` carries the OK / Cancel labels, so the dialog costs no key of its own.
    """

    def __init__(self, parent=None, query=None):
        super().__init__(parent)
        record = dict(query or {})
        self.setWindowTitle(_t("sftp.search.title"))
        box = QVBoxLayout(self)
        box.setSpacing(6)
        box.addWidget(QLabel(_t("sftp.search.needle"), self))
        self.needle_edit = QLineEdit(str(record.get("needle") or ""), self)
        box.addWidget(self.needle_edit)
        self.subfolders_box = QCheckBox(_t("sftp.search.subfolders"), self)
        self.subfolders_box.setChecked(search.query_scope(record) == search.SEARCH_SCOPE_SUBTREE)
        box.addWidget(self.subfolders_box)
        self.case_box = QCheckBox(_t("sftp.search.case"), self)
        self.case_box.setChecked(bool(record.get("case_sensitive")))
        box.addWidget(self.case_box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)
        self.needle_edit.setFocus()

    def query(self):
        """The query record of what the dialog holds (None — the needle is blank)."""
        return search.normalize_query(
            self.needle_edit.text(), case_sensitive=self.case_box.isChecked(),
            scope=(search.SEARCH_SCOPE_SUBTREE if self.subfolders_box.isChecked()
                   else search.SEARCH_SCOPE_HERE))


class SftpPaneViewerMixin:
    """The read-only preview panel of ONE Files pane (mixed into `_SftpPane`)."""

    # v1.3.1: the preview panel — the tree's share of the splitter on the first open.
    VIEWER_TREE_SHARE = 0.45

    # v1.3.1: the width the share above is measured against while the splitter is not laid out yet
    # (a panel opened on a never-shown tab measured 0 — the share is computed for SOMETHING).
    VIEWER_MIN_TOTAL_PX = 640

    # v1.4.7: the blocks formatted AROUND the viewport on either side (the lazy
    # window of the highlighter — a small scroll costs nothing because the
    # neighbours are already done).
    VIEWER_LAZY_MARGIN = syntax.VIEWER_LAZY_MARGIN

    # v1.7.3: the multiplier of that margin while the reader WRAPS — one block is several visual
    # rows there, so the window has to reach further to cover the same distance on the screen.
    WRAP_MARGIN_FACTOR = 2

    # ── v1.7.5: the preview ceiling of THIS pane ─────────────────────────

    def viewer_cap(self) -> int:
        """The ceiling every read of this pane is TRUNCATED at (the resolved setting)."""
        return int(getattr(self, "_viewer_cap", 0) or VIEWER_MAX_BYTES_MIN)

    def set_viewer_max_bytes(self, value) -> int:
        """Apply a new ceiling to THIS pane and re-read the marks (v1.7.5).

        The per-session "no preview" FACTS are dropped: a size verdict is a fact of the CAP that
        produced it, so a read attempt that answered under the old ceiling says nothing about the
        new one. Every row of the listing is re-marked from the (now clean) state.
        """
        self._viewer_cap = host_attr(self, "clamp_viewer_max_bytes")(value)
        self._blocked.clear()
        self._mark_rows()
        return self._viewer_cap

    def _mark_rows(self):
        """Re-apply the preview marker of EVERY row of the listing on the screen. Never raises."""
        try:
            for index in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(index)
                if item is not None:
                    self._apply_preview_marker(item, item.data(0, self.PATH_ROLE))
        except RuntimeError:
            pass  # Qt teardown — the tree is already gone

    def _known_size(self, path: str) -> int:
        """The size the CURRENT listing knows for `path` (0 — the path is not on the screen)."""
        try:
            for index in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(index)
                if item is not None and item.data(0, self.PATH_ROLE) == path:
                    return int(item.data(0, self.SIZE_ROLE) or 0)
        except (RuntimeError, TypeError, ValueError):  # noqa: BLE001 — best effort (declared): 0 means the path is not on screen
            pass
        return 0

    # ── v1.3.1: the preview panel ────────────────────────────────────────

    def _open_viewer(self, item: QTreeWidgetItem):
        """A double click on a file → read it through the worker queue and show it.

        The pane never touches the remote file itself: the read is a "read" task
        of the existing queue (32 KB chunks, the limit and the binary check are
        the worker's job), the answer arrives via read_ready. The panel opens
        only when the answer is there — a refusal (binary / too large) stays a
        message in the status bar (task_error → _on_task_error).

        v1.7rc3: in the TWO-PANE view the preview is shown WHERE THE OTHER PANE IS (the mc
        behaviour) and THIS pane keeps the keyboard and the cursor; the reading pane stays the
        owner of the task and of the message, so a refusal is reported exactly as before.

        v1.7.4rc1: the read goes to THIS pane's provider, so a LOCAL file previews through the
        SHIPPED read policy unchanged (LOCAL_PANE.md §3).
        """
        if self.provider is None:
            self.message.emit(_t("sftp.waiting_connection"))
            return
        path = item.data(0, self.PATH_ROLE)
        # v1.7rc3: the GATE is asked first — ONE preview exists at a time, and a file opened while
        # the OTHER pane shows a panel is refused with ONE sentence. A panel THIS pane owns is not
        # in the way: the new file is read into it (walking the listing with F3 is the whole point
        # of a commander, so a second open from the reading pane must never be refused as "busy").
        if not self._container.preview_allowed(self):
            return
        # Opening a file ALWAYS starts from a clean look: a preview already open in the two-pane
        # view (whichever pane lent or carries its panel) closes first, so a new preview can never
        # share a splitter with the old one, and a re-open of the SAME file re-reads it. The panel
        # is MOVED to the other pane only once the content is there (`_show_viewer()`): a read the
        # worker refuses must not leave the other pane dressed as a panel that shows nothing.
        self._container.close_preview()
        self._queue_viewer_read(path, item.data(0, self.SIZE_ROLE))

    def _queue_viewer_read(self, path: str, size=0) -> bool:
        """Ask this pane's provider for `path` at the pane's ceiling (the ONE preview read).

        v1.9.3: the ENCODING choice needs the same read a double click makes — the shown text was
        decoded with the previous codec, so a change re-reads the file instead of leaving a
        mis-decoded document on the screen — and ONE place asks `queue_read()`, so the ceiling
        travels with it exactly once (AGENTS.md §4.15).

        v1.13: a path that names a MEMBER of the open archive is read from the ARCHIVE (the spool the
        panel already holds) — a member name exists inside the file on the screen and nowhere on the
        server, so asking a provider for it would read a stranger's path (`ARCHIVES.md` §4).
        """
        raw = self._archive_member_raw(path)
        if raw:
            return self._preview_member_by_name(raw)
        provider = self.provider
        if provider is None:
            self.message.emit(_t("sftp.waiting_connection"))
            return False
        tid = provider.queue_read(path, int(size or 0), max_bytes=self.viewer_cap())
        if tid is None:
            return False   # the worker is finished — there is nobody to read
        self._read_tasks[tid] = path
        self._last_read = tid
        self.viewer_label.setText(_t("sftp.viewer.reading", name=self.paths.basename(path)))
        return True

    def _archive_member_raw(self, path: str) -> str:
        """The RAW name of the open archive's member a viewer path names — `""` — it names none.

        A member is keyed by its RAW name (what the reader asks the archive for), while the panel
        SHOWS the display one (`member_name()` drops a leading `./`): the click hands the raw name and
        the encoding re-read hands what the panel shows, so BOTH spellings resolve here. A member path
        is never a path of the server — the re-read must ask the archive or nothing at all.
        """
        state = getattr(self, "_archive", None)
        entries = (state or {}).get("entries") or {}
        if path in entries:
            return str(path)
        for raw, entry in entries.items():
            if entry.get("name") == path:
                return str(raw)
        return ""

    def _on_read_ready(self, task_id: int, remote_path: str, data: bytes):
        """The read answer (already on the GUI thread): render it in the panel.

        The pane is the ONE place that knows whether the read was CUT — it holds the cap it handed
        to the task and the size the listing reports — so the truncation fact is resolved HERE and
        travels into `decode_text()` (`N46`: a byte cut is not a different encoding).
        """
        searched = self._search_reads.pop(task_id, None)
        if searched is not None:
            path, size, cap = searched
            self._on_search_read(path, size, data, cap)  # v1.13.6: a file of the walk
            return
        path = self._read_tasks.pop(task_id, remote_path)
        if task_id != self._last_read:
            return  # an outdated answer (another file was opened since) — dropped
        self._last_read = None
        # v1.3.1.1: a successful read is a FACT too — drop a stale mark of this row
        # (defensive: the two heuristics agree today, and the state must not drift).
        if self._blocked.pop(path, None) is not None:
            self._mark_row(path)
        truncated = host_attr(self, "read_was_truncated")(
            len(data), self.viewer_cap(), self._known_size(path))
        text, encoding = self._decoded_text(bytes(data), truncated=truncated,
                                          encoding=self.viewer_encoding_choice)
        self._show_viewer(path, len(data), text, encoding)

    def _decoded_text(self, data, truncated: bool = False, encoding: str = "auto"):
        """The ONE decode call site of the pane — the shipped rule PLUS the cut fact.

        Both readers go through it: the preview (whose `truncated` is resolved from the cap and the
        listing's size, `N46`) and the search walk (a file cut by the run's byte budget is the same
        fact). ONE call site is what keeps "a byte cut is not a different encoding" true for both.
        """
        return host_attr(self, "decode_text")(bytes(data or b""), truncated=truncated,
                                              encoding=encoding)

    def _show_viewer(self, path: str, size: int, text: str, encoding: str = "utf-8", total=None):
        """Fill the panel with the file and show it (an unshown panel gets sizes).

        v1.4.7: the language is decided from the path AND the content
        (`syntax.detect_syntax` — the honesty rule: a `.json`/`.xml` hint is
        accepted only after a real parse) and the pane's ONE highlighter colours
        the blocks around the viewport. The header carries the heuristic note
        for the modes no parser verified (YAML), exactly like the encoding note.

        v1.7rc3: the panel may have been MOVED to the other pane before this call
        (`present_viewer_in()`), so the share is computed for the splitter that really carries it
        and the READING pane keeps the keyboard (its listing stays under the cursor while the
        preview appears beside it — the mc behaviour).

        v1.7.5: the header's SIZE becomes the truncation notice when the read stopped at the
        ceiling — the listing knows the real size, so the panel can say how much of how many it
        shows (`sftp.viewer.truncated`) instead of presenting a part as the whole.

        v1.13: `total` is the size of what is on the screen when the LISTING does not carry it — a
        member of the open archive has no row in the pane's tree, so its real size travels in.
        """
        # The parser has a declared budget (N57): over it the extension hint is accepted WITHOUT the
        # parse and the header owes the heuristic note — a 250 MiB `.json` is never `json.loads`-ed.
        verifiable = syntax.within_verify_budget(text)
        language = syntax.detect_syntax(path, text, verify=verifiable)
        format_bytes = host_attr(self, "format_size")
        size_text = format_bytes(size)
        total = self._known_size(path) if total is None else int(total or 0)
        if int(total or 0) > int(size or 0):
            size_text = _t("sftp.viewer.truncated", shown=format_bytes(size),
                           total=format_bytes(total))
        head = _t("sftp.viewer.header", path=path, size=size_text)
        chosen = self.viewer_encoding_choice
        if chosen != "auto" and encoding != chosen:
            # v1.9.3: the CHOICE could not read the file — the shipped rule did, and the header says
            # which is which instead of presenting a fallback as the requested decoding.
            head = f"{head} · {_t('sftp.viewer.encoding_failed', encoding=chosen, fallback=encoding)}"
        elif encoding != "utf-8":
            head = f"{head} · {_t('sftp.viewer.encoding_note', encoding=encoding)}"
        if syntax.is_heuristic(language) or not verifiable:
            head = f"{head} · {_t('sftp.viewer.syntax_heuristic', language=language)}"
        self.viewer_label.setText(head)
        self.viewer_label.setToolTip(path)
        self._viewer_encoding = encoding
        self._viewer_path = path
        self._viewer_language = language
        highlighter = self._ensure_highlighter()
        if highlighter is not None:
            highlighter.set_language(language)
            # BEFORE setPlainText: Qt reformats the WHOLE changed range, and with
            # an EMPTY window that pass applies no format at all — which is what
            # keeps the previous file from bleeding into this one.
            highlighter.reset_for_document()
        self._highlight_range = None
        self.viewer_text.setPlainText(text)   # the cursor lands at the start by itself
        self._viewer_open = True
        # The panel is where the FILE is: with two panes it takes the OTHER pane's slot (mc/far),
        # with one it stays inside this one (the shipped look). The move happens HERE — with the
        # content already in the widget — so a read the worker refused leaves every pane alone.
        self._container.present_viewer(self)
        self.viewer.show()
        self._layout_viewer_share(self.viewer)
        self._highlight_visible(force=True)

    # ── v1.7rc3: the preview moved to the other pane (the mc F3 of the two-pane view) ──

    def panel_in_slot(self):
        """The panel this pane SHOWS — the SEARCH results, the ARCHIVE listing, or the reader.

        ONE slot, ONE panel: the three are moved between the panes by the same two methods and the
        container asks "is a panel open" once (`viewer_host()`), which is what keeps the one-panel
        rule true for all of them (`ARCHIVES.md` §5, `AGENTS.md` §4.3.6).
        """
        if getattr(self, "_search_open", False):
            panel = getattr(self, "search_panel", None)
            if panel is not None:
                return panel
        if getattr(self, "_archive_open", False):
            panel = getattr(self, "archive_panel", None)
            if panel is not None:
                return panel
        return self.viewer

    def _viewer_splitter(self, panel=None):
        """The splitter that really carries `panel` (the panel this pane SHOWS by default)."""
        parent = (self.panel_in_slot() if panel is None else panel).parent()
        return parent if parent is not None else self.splitter

    def _layout_viewer_share(self, panel=None):
        """Give `panel` its declared share of the splitter that REALLY carries it. Never raises.

        The panel is passed by the method that just filled it (`_show_viewer()` / `_show_archive()`):
        the pane may be showing a BORROWED panel of the other one, and the panel it shows is not
        always the panel that was just filled — sizing `panel_in_slot()` then lays out the archive
        listing in the neighbour's splitter and leaves the reader at the default 50/50.

        Qt gotcha #13: a splitter member's share is set via `setSizes()` only. The splitter can hold a
        THIRD member — a pane carrying a borrowed panel keeps its OWN one in the layout (hidden, so it
        lands nowhere) while the borrowed one takes the slot it left — which is why the share is
        computed over the members BY NAME: the listing takes `VIEWER_TREE_SHARE`, the panel that is
        really on screen takes the rest and a panel that stepped aside answers 0. A share handed out by
        POSITION would give the column to the hidden member and leave the borrowed panel zero pixels
        wide: the borrowing pane changed its look and showed nothing at all.
        """
        panel = self.panel_in_slot() if panel is None else panel
        splitter = self._viewer_splitter(panel)
        try:
            count = splitter.count()
            index = splitter.indexOf(panel)
        except RuntimeError:
            return   # Qt teardown — the splitter or the panel is already gone
        if count <= 0 or index < 0:
            return
        total = max(splitter.width(), self.VIEWER_MIN_TOTAL_PX)
        left = int(total * self.VIEWER_TREE_SHARE)
        try:
            # v1.7: a pane CARRYING a borrowed panel is a PANEL — its own listing left the layout
            # (`present_viewer_in()` hides it), so the panel takes the WHOLE pane.
            listing = splitter.widget(0)
            if listing is not None and listing.isHidden():
                left = 0
        except RuntimeError:
            pass   # Qt teardown — the splitter is already gone
        sizes = [0] * count
        sizes[0] = left                                   # the listing is the first member
        sizes[index] = max(total - left, 0)               # the panel is the one that is showing
        splitter.setSizes(sizes)

    def viewer_host(self):
        """The pane whose splitter currently carries a panel (None — no panel is open).

        ONE answer for the whole container: the pane that BORROWED the panel registers itself in
        `_viewer_host`, so "close the preview and restore the listing" has a single subject and
        the pane that opened it never has to guess. The state is the DECLARED `_viewer_open` /
        `_archive_open` / `_search_open` flag, never `QWidget.isVisible()` — a pane that is not on
        screen yet (a never-shown dock tab, the offscreen test platform) reports its widgets as
        invisible while its panel is really open.
        """
        if not (getattr(self, "_viewer_open", False) or getattr(self, "_archive_open", False)
                or getattr(self, "_search_open", False)):
            return None
        if self._viewer_host is not None:
            return self._viewer_host
        return self._viewer_home or self

    def _restore_listing(self):
        """Put the tree and the pane's own rows back after a borrowed viewer leaves it.

        Called with `_viewer_host` ALREADY cleared (the owner has taken its panel home), so the
        only question is whether this pane was CARRYING it — a pane that never did must keep its
        own panel's look untouched. Never raises.
        """
        try:
            if not getattr(self, "_viewer_borrowed", False):
                return
            self._viewer_borrowed = False
            self.path_label.show()
            self.tree.show()                  # v1.7: the listing comes back with the rows
            self.splitter.setCollapsible(0, False)   # the tree is never draggable shut again
            self.set_pane_keys_enabled(True)
            self._sync_secondary_ui()
        except (RuntimeError, AttributeError):
            pass  # Qt teardown / a pane built before the rows exist

    def present_viewer_in(self, host, source=None) -> bool:
        """Move THIS pane's OPEN panel into `host`'s splitter; True — it really moved.

        The two-pane view shows a preview WHERE THE OTHER PANE IS (mc and far do the same): the
        listing that opened it keeps the cursor and the keyboard, and the panel takes the other
        pane's place for as long as it is open. The panel is ONE widget owned by the pane it was
        built in, so the move is a re-parent (`QSplitter.insertWidget()`) instead of a second
        `QPlainTextEdit` per pane — the highlighter, the content and the × belong to the same
        object, and closing the preview puts it back where it came from. v1.13: the ARCHIVE listing
        takes the same slot, so both panels travel through this ONE method.

        **The host is a PANEL for as long as it carries the preview**: its address bar and its key
        row were already gone, and since v1.7 its LISTING leaves the layout too (`tree.hide()`), so
        the panel gets the whole pane instead of sharing it with a listing nobody is looking at.
        That is also why the pane's own pane-scoped keys are disarmed here: a key that acts on a
        listing off the screen would act on rows nobody can see.

        Refused (False) for the pane itself and for a foreign pane: the container asks
        `preview_allowed()` BEFORE the read (the ONE-preview rule) and `present_viewer()` decides
        whether the move is still wanted when the answer is there, this method only performs it.
        """
        if host is None or host is self or host is not self._container.other_pane(self):
            return False
        panel = self.panel_in_slot()
        try:
            # The host's OWN panel steps aside — it stays in the splitter, hidden (a hidden member
            # takes no room) — and the borrowed one is inserted in the very slot it left, so the
            # panel is the pane's RIGHT column and not a third member squeezed to nothing.
            index = host.splitter.indexOf(host.panel_in_slot())
            if index < 0:
                index = host.splitter.count()
            else:
                host.panel_in_slot().hide()
            host.splitter.insertWidget(index, panel)
        except RuntimeError:
            return False
        self._viewer_host = host
        self._viewer_from = source if source is not None else self
        # The host is a PREVIEW now: its address bar belongs to a listing nobody can see and the
        # key row of a pane that carries a panel is hidden (see `_sync_secondary_ui`). Since v1.7
        # its LISTING leaves the layout as well — the panel takes the WHOLE pane (the mc/far quick
        # view), and the tree's own keys (`Tab` into it, `F3`-`F8` on a row) are disarmed with it.
        host._viewer_borrowed = True
        try:
            host.path_label.hide()
            host.tree.hide()
            host.splitter.setCollapsible(0, True)   # a HIDDEN listing may really collapse to 0
            host.set_pane_keys_enabled(False)
            host._sync_secondary_ui()
        except (RuntimeError, AttributeError):
            pass  # Qt teardown / a pane built before the rows exist
        return True

    def restore_viewer(self) -> bool:
        """Move the OPEN panel back to its HOME pane; True — it really moved. Never raises.

        The home splitter shows the panel again (hidden) and the borrowing pane gets its listing
        rows back; a pane that is being TORN DOWN never takes the panel with it (the container
        calls this before it destroys the pane).
        """
        host = self._viewer_host
        if host is None:
            return False
        panel = self.panel_in_slot()
        self._viewer_host = None
        self._viewer_from = None
        try:
            panel.hide()
        except RuntimeError:
            pass  # Qt teardown — the panel is already gone
        home = self._viewer_home
        if home is not None and home is not host:
            try:
                home.splitter.addWidget(panel)
            except RuntimeError:
                pass  # Qt teardown — the home pane is already gone
        try:
            # `_restore_listing()` clears the borrowing flag itself and puts the host's own rows
            # (its address bar, its buttons or its hints) back.
            host._restore_listing()
        except (RuntimeError, AttributeError):
            pass
        try:
            if home is not None:
                home._sync_secondary_ui()
        except (RuntimeError, AttributeError):
            pass  # the home pane is gone / has no rows yet
        return True

    # ── v1.13: the archive view — the READ half of `ARCHIVES.md` ─────────────────

    @property
    def archive_open(self) -> bool:
        """Is the ARCHIVE listing the panel this pane shows (the topical seam)?"""
        return bool(getattr(self, "_archive_open", False))

    @property
    def archive_state(self):
        """The open archive's facts — `path` / `local` / `kind` / `spool` / `entries` (None: none)."""
        return getattr(self, "_archive", None)

    def archive_key(self, event) -> bool:
        """`Esc` leaves the view, `Enter` previews the current member; True — the key is consumed."""
        try:
            key = int(event.key())
        except (AttributeError, TypeError, ValueError):
            return False
        if key == int(Qt.Key.Key_Escape):
            return bool(self._container.close_preview())
        if key in (int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter)):
            self.preview_current_member()
            return True
        return False

    def _op_view_archive(self, item):
        """The `Open archive` row: claim the local copy of ONE archive and LIST it.

        The ONE door of the READ half (`ARCHIVES.md` §3); the row itself is offered on a declared
        archive of a FILE row, so the guards here stay defensive. A LOCAL source needs no copy — its
        path IS a local path and the OS disk is read where it lies — while a remote or an elevated
        one is DOWNLOADED into the SHIPPED spool, and the answer of that leg opens the view.
        """
        if self.provider is None:
            self.message.emit(_t("sftp.waiting_connection"))
            return
        path = item.data(0, self.PATH_ROLE) if item is not None else ""
        kind = archive.archive_kind(path)
        if not path or item is None or item.data(0, self.ISDIR_ROLE) or not kind:
            return   # the row is offered on a declared archive only — the door stays defensive
        size = int(item.data(0, self.SIZE_ROLE) or 0)
        limit = archive.resolve_archive_max_bytes()
        format_bytes = host_attr(self, "format_size")
        if not archive.size_allowed(size, limit):
            self.message.emit(_t("sftp.archive.cap", size=format_bytes(size),
                                 limit=format_bytes(limit)))
            return
        if not self._container.preview_allowed(self):
            return   # ONE panel at a time — the shipped sentence names the busy pane
        self._container.close_preview()
        if self.source == host_attr(self, "SOURCE_LOCAL"):
            self._show_archive(path, path, kind, "")
            return
        spool = archive.spool_archive(self.paths.basename(path))
        if not spool:
            self.message.emit(_t("sftp.op.error", error="spool"))
            return
        local_dir, local_name, part_mode = archive.spool_download_args(spool)
        task = self.provider.queue_download(path, local_dir, total_size=size,
                                            local_name=local_name, part_mode=part_mode)
        if task is None:
            archive.drop_archive(spool)
            self.message.emit(_t("sftp.op.error", error="queue"))
            return
        self._archive_tasks[int(task)] = (path, spool, kind)
        self._own_transfers.add(int(task))   # the shipped Cancel button covers the spool leg
        self.message.emit(_t("sftp.viewer.reading", name=self.paths.basename(path)))

    def _archive_answer(self, phase: str, task_id, payload) -> bool:
        """Is this task ONE spool leg of THIS pane? — the ONE hook of the three worker handlers.

        True means the answer was OURS and is answered here (the shipped handlers return at once).
        A leg whose view was CLOSED while it was in flight lands here as well, so the temp copy it
        published is dropped instead of reopening a panel nobody asked for.
        """
        task_id = int(task_id)
        pending = self._archive_tasks.pop(task_id, None)
        if pending is None:
            return False
        path, spool, kind = pending
        abandoned = task_id in self._archive_dropped
        self._archive_dropped.discard(task_id)
        if phase == "done" and not abandoned:
            self._show_archive(path, spool, kind, spool)
        elif phase == "done":
            archive.drop_archive(spool)
        else:
            archive.drop_archive(spool)
            self.message.emit(_t("sftp.transfer_cancelled") if phase == "cancelled"
                              else _t("sftp.op.error", error=str(payload or "")))
        self._on_task_finished(task_id)
        return True

    def _show_archive(self, path, local, kind, spool):
        """Read the LISTING of `local` and show the panel — the ONE place the view appears.

        The CAP is asked AGAIN here, against the file on THIS disk: the row's size is the listing's
        word, and the copy a download published (or a local file that grew while it sat on the
        screen) can be larger than that word — a parse of a file the declared cap does not allow is
        the one thing this door must not start. A refusal answers the shipped sentence and drops the
        copy; a parse that refuses answers ONE sentence and never dresses the other pane: the panel
        is presented with the members already in it (the reader's rule), and the spool goes with it.

        The ROW bound (`ARCHIVE_LIST_MAX`) is the second ceiling: the bytes of a zip say nothing
        about how many members it names, so a listing that meets more answers ONE sentence beside the
        rows it could carry — a panel, never a frozen window.
        """
        limit = archive.resolve_archive_max_bytes()
        size = archive.local_size(local)
        if not archive.size_allowed(size, limit):
            archive.drop_archive(spool)
            format_bytes = host_attr(self, "format_size")
            self.message.emit(_t("sftp.archive.cap", size=format_bytes(size),
                                 limit=format_bytes(limit)))
            return
        entries, encrypted, code, cut = archive.archive_listing(local, kind,
                                                                archive.ARCHIVE_LIST_MAX)
        if code:
            archive.drop_archive(spool)
            self.message.emit(_t("sftp.op.error", error=code))
            return
        if cut:
            self.message.emit(_t("sftp.archive.list_cut", limit=archive.ARCHIVE_LIST_MAX))
        panel = self._ensure_archive_panel()
        self._archive = {"path": path, "local": local, "kind": kind, "spool": spool,
                         "encrypted": bool(encrypted),
                         "entries": {entry["raw"]: entry for entry in entries}}
        self._archive_open = True
        self._fill_archive_tree(entries)
        head = _t("sftp.archive.header", name=self.paths.basename(path) or path,
                  count=len(entries))
        if encrypted:
            head = f"{head} · {_t('sftp.archive.encrypted')}"
        self.archive_label.setText(head)
        self.archive_label.setToolTip(path)
        # The SAME move the reader makes, with the content already in the widget: the panel takes the
        # OTHER pane's slot (mc/far) and stays in this one while there is no second pane.
        self._container.present_viewer(self)
        panel.show()
        self._layout_viewer_share(panel)

    def _ensure_archive_panel(self):
        """Build the archive panel ONCE per pane — lazily, like every other cost of this view.

        It mirrors the reader's shape (a header line with the ×, then the listing) because it takes
        the SAME slot of the splitter; a pane that never opens an archive builds none of it.
        """
        panel = getattr(self, "archive_panel", None)
        if panel is not None:
            return panel
        panel = QWidget()
        panel.setMinimumWidth(self.viewer.minimumWidth())
        box = QVBoxLayout(panel)
        box.setContentsMargins(4, 0, 0, 0)
        box.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.archive_label = QLabel("")
        host_attr(self, "_apply_status_style")(self.archive_label, "status.sftp_row")
        self.archive_label.setTextFormat(Qt.TextFormat.PlainText)
        self.archive_label.setWordWrap(False)
        self.archive_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.btn_archive_close = QPushButton("\u00d7")   # × — the panel header's close cross
        self.btn_archive_close.setFixedWidth(24)
        self.btn_archive_close.setToolTip(_t("sftp.viewer.close_tooltip"))
        self.btn_archive_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        head.addWidget(self.archive_label, 1)
        head.addWidget(self.btn_archive_close, 0)
        box.addLayout(head)
        self.archive_tree = _ArchiveTree(self)
        self.archive_tree.setColumnCount(ARCHIVE_COLUMNS)
        self.archive_tree.setHeaderLabels([_t("sftp.column_name"), _t("sftp.column_size"),
                                           _t("sftp.column_modified")])
        self.archive_tree.setRootIsDecorated(False)   # ONE level: a flat list of member names
        self.archive_tree.setUniformRowHeights(True)
        self.archive_tree.setColumnWidth(0, ARCHIVE_COLUMN_WIDTH)
        # v1.13.1: the listing's OWN verbs — the WRITE half's door. The tree takes no DROP (it is a
        # reading surface); a context menu is not a drop, and it is where a row gesture belongs.
        self.archive_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.archive_tree.customContextMenuRequested.connect(self._on_archive_menu)
        self.archive_tree.itemDoubleClicked.connect(self._on_archive_item)
        box.addWidget(self.archive_tree, 1)
        panel.hide()
        self.archive_panel = panel
        self.btn_archive_close.clicked.connect(self._on_archive_close)
        self.splitter.addWidget(panel)
        try:
            self.splitter.setCollapsible(self.splitter.indexOf(panel), True)
        except (RuntimeError, TypeError):  # noqa: BLE001 — teardown of a dead object: the splitter is already gone
            pass   # Qt teardown — the splitter is already gone
        return panel

    def _fill_archive_tree(self, entries):
        """Fill the flat listing (Name | Size | Modified) with the members the parse answered."""
        format_bytes = host_attr(self, "format_size")
        format_mtime = host_attr(self, "format_mtime")
        self.archive_tree.clear()
        for entry in entries:
            item = QTreeWidgetItem([entry["name"], format_bytes(entry["size"]),
                                    format_mtime(entry["mtime"])])
            item.setData(0, self.PATH_ROLE, entry["raw"])
            item.setToolTip(0, entry["name"])
            self.archive_tree.addTopLevelItem(item)

    def _on_archive_close(self):
        """The archive panel's × — the SHIPPED close door (the container closes whichever is open)."""
        try:
            self._container.close_preview()
        except (RuntimeError, AttributeError):
            self.close_viewer()

    def _reset_archive(self):
        """Drop the spool, empty the listing and hide the panel — the state this view owns.

        A leg still in flight is marked ABANDONED rather than forgotten: it keeps its entry in
        `_archive_tasks`, so the answer that lands afterwards drops the temp copy it published
        instead of showing a listing the user has closed. v1.13.1: a copy an EXTRACTION is reading
        is handed to the container first (`take_archive_copy()`) — the spool goes with the answer of
        that extraction instead of vanishing under it. Never raises.
        """
        state = getattr(self, "_archive", None) or {}
        self._archive_open = False
        self._archive = None
        self._archive_dropped |= {int(task_id) for task_id in self._archive_tasks}
        local = str(state.get("local") or "")
        spool = str(state.get("spool") or "")
        kept = bool(local) and self._container is not None \
            and bool(self._container.take_archive_copy(local))
        if spool and not kept:
            archive.drop_archive(spool)
        panel = getattr(self, "archive_panel", None)
        if panel is None:
            return
        try:
            self.archive_tree.clear()
            self.archive_label.clear()
            self.archive_label.setToolTip("")
            panel.hide()
        except (RuntimeError, AttributeError):
            pass   # Qt teardown — the panel is already gone

    def _archive_forget_legs(self, provider=None):
        """Drop every spool leg of a provider this pane is LEAVING (`N131`). Never raises.

        A leg whose download is still writing cannot be dropped here: its own commit would publish
        the spool a moment later, with nobody left to remove it. With a `provider`, the legs stay
        OWNED — they move out of `_archive_tasks` into `_archive_legs` and the pane listens to that
        provider's three answer signals through its own `_on_leg_*` slots, which drop the copy the
        answer published. A leg that is never answered (a transport that died) is the startup
        sweep's, the declared sibling of a crashed run's leftover. Without a `provider` — a
        teardown — the spools go at once.
        """
        pending = dict(self._archive_tasks)
        self._archive_tasks.clear()
        self._archive_dropped.clear()
        if provider is not None and pending:
            self._own_legs(provider, pending)
            return
        for _task_id, (_path, spool, _kind) in pending.items():
            archive.drop_archive(spool)
        for owner, owned in list((getattr(self, "_archive_legs", None) or {}).items()):
            for spool in list(owned.values()):
                if spool:
                    archive.drop_archive(spool)
            owned.clear()
            self._release_leg_owner(owner)

    def _own_legs(self, provider, pending):
        """Keep `pending` legs owned by the provider this pane just left (the `N131` handover)."""
        legs = getattr(self, "_archive_legs", None)
        if legs is None:
            legs = self._archive_legs = {}
        fresh = provider not in legs
        owned = legs.setdefault(provider, {})
        for task_id, (_path, spool, _kind) in pending.items():
            owned[int(task_id)] = str(spool or "")
        if not fresh:
            return   # the slots of this provider are connected already (ONE connection per owner)
        for name, slot in (("task_done", self._on_leg_done),
                           ("task_error", self._on_leg_error),
                           ("task_cancelled", self._on_leg_cancelled)):
            signal = getattr(provider, name, None)
            if signal is None:
                continue
            try:
                signal.connect(slot)
            except (RuntimeError, TypeError):  # noqa: BLE001 — teardown of a dead object: a stub without the signals
                pass   # a dead provider / a stub without the shipped signals

    def _release_leg_owner(self, provider):
        """Disconnect the three leg slots of ONE owner and forget it. Never raises."""
        legs = getattr(self, "_archive_legs", None) or {}
        legs.pop(provider, None)
        for name, slot in (("task_done", self._on_leg_done),
                           ("task_error", self._on_leg_error),
                           ("task_cancelled", self._on_leg_cancelled)):
            signal = getattr(provider, name, None)
            if signal is None:
                continue
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):  # noqa: BLE001 — teardown of a dead object: the C++ object is already gone
                pass   # never connected / the C++ object is already gone

    def _on_leg_done(self, task_id, _detail=""):
        """An OWNED leg of a provider this pane left finished: drop the spool it published."""
        self._answer_owned_leg(task_id)

    def _on_leg_error(self, task_id, _kind="", _message=""):
        """An OWNED leg failed: the provisional copy never became a spool — nothing to drop."""
        self._answer_owned_leg(task_id)

    def _on_leg_cancelled(self, task_id, _kind=""):
        """An OWNED leg was cancelled: its provisional file went with the task."""
        self._answer_owned_leg(task_id)

    def _answer_owned_leg(self, task_id) -> bool:
        """Retire ONE owned leg; True — the id belonged to a provider this pane left."""
        try:
            task_id = int(task_id)
        except (TypeError, ValueError):
            return False
        legs = getattr(self, "_archive_legs", None) or {}
        for provider, owned in list(legs.items()):
            if task_id not in owned:
                continue
            spool = owned.pop(task_id)
            if spool:
                archive.drop_archive(spool)
            if not owned:
                self._release_leg_owner(provider)
            return True
        return False

    def preview_current_member(self):
        """`Enter` on the flat listing (the double click's twin)."""
        try:
            item = self.archive_tree.currentItem()
        except (RuntimeError, AttributeError):
            return
        if item is None:
            self.message.emit(_t("sftp.cmd.no_selection"))
            return
        self._preview_member(item)

    # ── v1.13.1: the archive's OWN row menu — the door of the WRITE half (`ARCHIVES.md` §6) ──

    def _on_archive_menu(self, pos):
        """The listing's context menu (the seam is `_build_archive_menu()`)."""
        self.activate()   # the row menu belongs to the pane it was opened in
        menu = self._build_archive_menu()
        if menu is not None:
            menu.exec(self.archive_tree.viewport().mapToGlobal(pos))

    def _build_archive_menu(self):
        """`Extract` — the ONE verb of the open archive (a test seam: the tests trigger the QAction).

        It is live on an OPEN listing only, and it names the OTHER pane as the destination because
        that is where an extraction goes by construction: the pane that still shows a LISTING
        receives the tree, the pane that carries this panel is the one it was opened from.
        """
        state = getattr(self, "_archive", None)
        if not state:
            return None
        menu = host_attr(self, "QMenu")(self)
        act = menu.addAction(_t("sftp.archive.extract"))
        act.setEnabled(True)
        act.triggered.connect(lambda: self._op_extract_archive())
        return menu

    def _op_extract_archive(self):
        """The `Extract` row: hand the OPEN archive to the container's extraction (`ARCHIVES.md` §6).

        The container owns the pipeline (the stage, the engine, the delivery to the destination
        pane), so this door asks ONE question — is there an archive here at all — and refuses an
        ENCRYPTED one BEFORE a byte is written, with the shipped §4 sentence and no password
        prompt. The listing itself stays where it is: an extraction is not a preview.
        """
        if not getattr(self, "_archive", None):
            return
        if self._container is None:
            return
        self._container.begin_extract(self)

    def _on_archive_item(self, item, _column=0):
        """A double click on a member row — the ONE gesture of the listing."""
        self._preview_member(item)

    def _preview_member(self, item):
        """A member ROW was asked for: read it through the shipped policy."""
        raw = item.data(0, self.PATH_ROLE) if item is not None else ""
        if raw:
            self._preview_member_by_name(str(raw))

    def _preview_member_by_name(self, raw: str) -> bool:
        """Read ONE member of the OPEN archive into this pane's reader panel; False — nothing read.

        The bytes come from the local copy the panel already holds (the spool or the OS disk), so the
        read is LOCAL and bounded by the reader's ceiling; the member's NAME travels as the reader's
        path, which is what makes the syntax hint, the truncation notice and the encoding choice the
        shipped ones. The reader stays in the pane that OPENED the archive — the other pane carries
        the listing, and `ARCHIVES.md` §5 makes the two panels ONE preview session.
        """
        state = getattr(self, "_archive", None)
        if not state:
            return False
        entry = state["entries"].get(raw)
        if entry is None:
            return False
        cap = self.viewer_cap()
        data, code = archive.read_member(state["local"], state["kind"], entry["raw"], cap,
                                         entry["size"])
        if code == archive.ARCHIVE_ERROR_ENCRYPTED:
            self.message.emit(_t("sftp.archive.encrypted"))
            return False
        if code:
            self.message.emit(self._read_error_text(code, entry["name"]))
            return False
        truncated = host_attr(self, "read_was_truncated")(len(data), cap, int(entry["size"] or 0))
        text, encoding = host_attr(self, "decode_text")(bytes(data), truncated=truncated,
                                                       encoding=self.viewer_encoding_choice)
        self._show_viewer(entry["name"], len(data), text, encoding, total=int(entry["size"] or 0))
        return True

    # ── v1.4.7: the lazy syntax highlighting ────────────────────────────────

    def _ensure_highlighter(self):
        """The pane's ONE highlighter (built on the first preview, reused after).

        A viewer must keep working when the highlighter cannot be built (an
        exotic Qt build): the preview then stays monochrome, which is exactly
        the v1.3.1 behaviour.
        """
        if self._highlighter is None:
            try:
                self._highlighter = syntax.create_highlighter(
                    self.viewer_text.document())
            except Exception:   # noqa: BLE001 — highlighting is never critical
                self._highlighter = None
        return self._highlighter

    # ── v1.7.3: the reader's word wrap ──────────────────────────────────────

    def _build_viewer_menu(self):
        """The reader's menu: Qt's OWN standard one PLUS the TWO app rows (wrap, encoding).

        `createStandardContextMenu()` carries Copy / Select All translated by Qt itself (no i18n
        key of ours), so the app rows are APPENDED after a separator — the same seam shape as
        `_build_context_menu()`: the tests trigger the QAction directly and never run `exec()`.
        v1.9.3: the encoding row is a SUBMENU of the declared codecs (a codec name is an
        identifier, so only `auto` carries a translated word) whose checkmark mirrors the ONE
        global value the container owns.
        """
        menu = self.viewer_text.createStandardContextMenu()
        menu.addSeparator()
        act = QAction(_t("sftp.viewer.word_wrap"), menu)
        act.setCheckable(True)
        act.setChecked(bool(self._viewer_wrap))
        act.toggled.connect(self._on_wrap_toggled)
        menu.addAction(act)
        self._wrap_action = act
        submenu = menu.addMenu(_t("sftp.viewer.encoding"))
        self._encoding_menu = submenu
        self._encoding_actions = {}
        for codec in VIEWER_ENCODINGS:
            item = QAction(_t("sftp.viewer.encoding_auto") if codec == VIEWER_ENCODING_DEFAULT
                           else codec, submenu)
            item.setCheckable(True)
            item.setChecked(codec == self.viewer_encoding_choice)
            item.triggered.connect(lambda _checked=False, code=codec:
                                   self._on_encoding_chosen(code))
            submenu.addAction(item)
            self._encoding_actions[codec] = item
        return menu

    def _on_encoding_chosen(self, codec):
        """An encoding row was chosen: the PANE's own choice is applied (v1.12.3).

        The reader's encoding is a per-pane value — the codec the user picked in THIS pane is the
        codec THIS pane reads its file with, so a CP1251 preview and a Latin-1 one live side by side
        instead of fighting over one key. The container still owns the ONE remembered DEFAULT
        (`ui_viewer_encoding`), so the door is told WHICH pane asked
        (`apply_viewer_encoding(codec, pane=self)`): the value is written as the default for the
        panes to come and the sibling's own choice is left alone. A container that answers nothing
        keeps the shipped writer. v1.13.6: the SESSION also keeps this pane's choice
        (`ui_sftp_encodings`), so re-opening the node returns both panes as they were left.
        """
        apply_one = getattr(self._container, "apply_viewer_encoding", None)
        if callable(apply_one):
            try:
                apply_one(codec, pane=self)
                self._remember_encoding(codec)
                return
            except RuntimeError:
                return   # Qt teardown — nothing left to re-read
        self.set_viewer_encoding(codec)

    def set_viewer_encoding(self, codec, persist: bool = True, reread: bool = True) -> str:
        """Set the encoding CHOICE of THIS pane (the container's walk reaches this method).

        The text on the screen was decoded with the PREVIOUS choice, so a real change re-reads the
        file the preview holds instead of leaving a mis-decoded document there; a panel with nothing
        open simply carries the new default into its next read. The value is normalised against the
        DECLARED list, so a hand-edited config cannot reach the decoder with an unknown codec.
        `persist` writes the value as the container's remembered DEFAULT — the menu route asks
        through the container instead, which is what keeps the sibling's own choice intact.
        Never raises.
        """
        resolved = normalize_viewer_encoding(codec)
        changed = resolved != self.viewer_encoding_choice
        self._viewer_encoding_choice = resolved
        self._viewer_encoding_chosen = resolved   # a REAL choice — the session memory keeps it
        for name, act in (getattr(self, "_encoding_actions", None) or {}).items():
            try:
                act.setChecked(name == resolved)
            except RuntimeError:
                pass   # Qt teardown — the menu is already gone
        if persist:
            host_attr(self, "save_viewer_encoding")(resolved)
        if changed and reread and self._viewer_open and self._viewer_path:
            self._queue_viewer_read(self._viewer_path, self._known_size(self._viewer_path))
        return resolved

    @property
    def viewer_encoding_choice(self) -> str:
        """The encoding this reader ASKS for — its OWN choice, else the SESSION's memory, else the
        remembered global default (`ui_viewer_encoding`); `auto` is the shipped utf-8 → latin-1 rule.

        The value is resolved on the FIRST read (`v1.13.6`): a pane is built before its container
        knows WHICH session it is, so the memory cannot be read in `__init__` — the `_restore_dir`
        rule of the per-server directory memory. A resolved value is cached; an explicit choice
        overwrites it for good (`set_viewer_encoding()`).
        """
        choice = getattr(self, "_viewer_encoding_choice", None)
        if not choice:
            choice = self._remembered_encoding() or resolve_viewer_encoding()
            self._viewer_encoding_choice = choice
        return str(choice or VIEWER_ENCODING_DEFAULT)

    def _on_viewer_menu(self, pos):
        """Show the reader's menu at the click (the event is the only caller of the seam)."""
        try:
            menu = self._build_viewer_menu()
            menu.exec(self.viewer_text.viewport().mapToGlobal(pos))
            menu.deleteLater()
        except RuntimeError:
            return   # Qt teardown — the panel is already gone

    def _on_wrap_toggled(self, on: bool):
        """The row was toggled: the CONTAINER owns the ONE global setting (v1.7.3)."""
        apply_all = getattr(self._container, "apply_viewer_wrap", None)
        if callable(apply_all):
            try:
                apply_all(bool(on))
                return
            except RuntimeError:
                return   # Qt teardown — nothing left to re-text
        self.set_viewer_wrap(on)

    def _apply_viewer_wrap(self):
        """Write the mode into the widget and re-run the lazy pass (the wrap changes the window).

        Never raises: a viewer without the enum (an exotic Qt build) keeps the shipped no-wrap look.
        """
        mode = (QPlainTextEdit.LineWrapMode.WidgetWidth if self._viewer_wrap
                else QPlainTextEdit.LineWrapMode.NoWrap)
        try:
            self.viewer_text.setLineWrapMode(mode)
        except (RuntimeError, AttributeError):
            return
        self._highlight_range = None
        self._highlight_visible(force=True)

    def set_viewer_wrap(self, on, persist: bool = True) -> bool:
        """Set the reader's word wrap for THIS pane (the container walks the rest)."""
        self._viewer_wrap = bool(on)
        self._apply_viewer_wrap()
        act = getattr(self, "_wrap_action", None)
        if act is not None:
            try:
                act.setChecked(self._viewer_wrap)
            except RuntimeError:
                pass   # Qt teardown — the menu is already gone
        if persist:
            return host_attr(self, "save_viewer_wrap")(self._viewer_wrap)
        return True

    @property
    def viewer_wrap(self) -> bool:
        """Is the reader wrapping long lines (the topical seam)?"""
        return bool(self._viewer_wrap)

    def _lazy_margin(self) -> int:
        """The blocks the lazy window keeps around the viewport.

        Under wrapping ONE block covers SEVERAL visual rows, so the block margin is widened: the
        same visual distance stays formatted around the viewport (the measured seam of the mode).
        """
        if self._viewer_wrap:
            return self.VIEWER_LAZY_MARGIN * self.WRAP_MARGIN_FACTOR
        return self.VIEWER_LAZY_MARGIN

    def _viewer_block_range(self):
        """The block numbers on the screen → `(first, last)`, or None.

        Measured from the LAYOUT (`blockBoundingGeometry` + `contentOffset`), so
        it answers correctly for a hidden panel too (it degrades to block 0).
        """
        edit = self.viewer_text
        try:
            block = edit.firstVisibleBlock()
            if not block.isValid():
                return None
            height = edit.viewport().height()
            offset = edit.contentOffset()
            first = last = block.blockNumber()
            while block.isValid():
                if edit.blockBoundingGeometry(block).translated(offset).top() > height:
                    break
                last = block.blockNumber()
                block = block.next()
            return first, last
        except RuntimeError:
            return None   # the C++ object was already destroyed (a close race)

    def _highlight_visible(self, force: bool = False) -> int:
        """Format the blocks around the viewport.

        A 1 MB file is ~20 000 blocks and `setPlainText()` marks every one of
        them dirty, so the EXPENSIVE half (turning spans into text formats) is
        applied only to the visible window ± `VIEWER_LAZY_MARGIN`; the block
        STATE is still computed for every line, because the state of a line
        depends on the line before it. A repeated call whose window is already
        done costs one comparison.

        Returns the number of blocks really rehighlighted.
        """
        highlighter = self._highlighter
        if highlighter is None:
            return 0
        window = self._viewer_block_range()
        if window is None:
            return 0
        margin = self._lazy_margin()
        first = max(0, window[0] - margin)
        last = window[1] + margin
        if not force and (first, last) == self._highlight_range:
            return 0
        self._highlight_range = (first, last)
        highlighter.set_window(first, last)
        return highlighter.highlight_window(force=force)

    def _on_viewer_update_request(self, _rect, dy):
        """`QPlainTextEdit.updateRequest`: a scroll (`dy != 0`) or a resize.

        A hidden panel is skipped: the content of a closed viewer is gone, and
        `clear()` fires the signal while it empties the document — formatting a
        block nobody can see would only leave a mark behind.
        """
        if self.viewer.isHidden():
            return
        self._highlight_visible()

    @property
    def viewer_highlighter(self):
        """The pane's highlighter (None until the first preview — the test seam)."""
        return self._highlighter

    @property
    def viewer_language(self) -> str:
        """The language the shown content was detected as (v1.4.7)."""
        return self._viewer_language

    @property
    def viewer_encoding(self) -> str:
        """The encoding of the shown content ("utf-8" | "latin-1")."""
        return self._viewer_encoding

    def close_viewer(self):
        """v1.3.1: hide the panel and drop its content.

        Idempotent and never raises: it is called by the header's ×, by the
        container's `set_worker(None)` (the worker died) and by the single page
        teardown (page.shutdown()) — the preview closes together with the session.

        v1.7rc3: a BORROWED panel goes back to the pane it belongs to first (the other pane gets
        its listing and its address bar back), so closing the preview always restores the two-pane
        look the user had before it.

        v1.13: an open ARCHIVE view is the panel this method closes — `ARCHIVES.md` §5 makes the
        listing and a member's preview ONE session, so the archive panel goes home, the spool it
        read is dropped and only then does the reader's own content leave.
        v1.13.6: a SEARCH results panel is the same slot and closes the same way — its walk is
        dropped with it (a late answer finds no task of its own).
        """
        if getattr(self, "_search_open", False):
            self.restore_viewer()   # the RESULTS panel is the one the other pane may carry
            self._reset_search()
        if getattr(self, "_archive_open", False):
            self.restore_viewer()   # the ARCHIVE panel is the one the other pane carries
            self._reset_archive()
        self._read_tasks.clear()
        self._last_read = None
        # v1.4.7: the panel is empty → the formatting pass has nothing to cover.
        self._highlight_range = None
        self._viewer_open = False
        self._viewer_path = ""   # v1.9.3: no file on the screen → the choice re-reads nothing
        if self._highlighter is not None:
            self._highlighter.reset_for_document()
        self.restore_viewer()
        try:
            self.viewer.hide()
            self.viewer_text.clear()
            self.viewer_label.clear()
            self.viewer_label.setToolTip("")
        except RuntimeError:
            pass  # the C++ object was already destroyed (a close race) — nothing to hide
        # v1.7rc3: this pane may have been the CARRYING one while the panel belonged to its
        # sibling — its own path row and key hints come back with the panel's closing.
        if getattr(self, "_viewer_borrowed", False):
            self._viewer_borrowed = False
            self._viewer_host = None
            try:
                self.path_label.show()
            except RuntimeError:
                pass
            self._sync_secondary_ui()

    # ── v1.13.6: FIND IT — the content search of THIS pane (`AGENTS.md` §4.3.6) ──────
    # The walk is the SHIPPED task family (`queue_list()` / `queue_read()`), ONE task at a time,
    # because the provider's queue is shared with the pane's own navigation; the query, the matcher
    # and every bound live in the PURE `modules/sftp_search.py`. A stop drops the task maps, so an
    # answer that lands afterwards belongs to nobody.

    @property
    def _search(self):
        """The walk in flight — its query, its `SearchReport` and its two queues (None — no run)."""
        return self.__dict__.get("_search_state")

    @_search.setter
    def _search(self, value):
        self.__dict__["_search_state"] = value

    @property
    def _search_lists(self) -> dict:
        """The directories this run listed: task id → `(directory, level)` (created with the first)."""
        return self.__dict__.setdefault("_search_list_tasks", {})

    @property
    def _search_reads(self) -> dict:
        """The candidate files this run is reading: task id → `(path, size, cap)`."""
        return self.__dict__.setdefault("_search_read_tasks", {})

    @property
    def search_open(self) -> bool:
        """Are the RESULTS the panel this pane shows (the topical seam)?"""
        return bool(getattr(self, "_search_open", False))

    @property
    def search_report(self) -> dict:
        """The counters of the open run as the header shows them ({} — nothing runs)."""
        state = self._search
        return state["report"].as_dict() if state else {}

    def search_rows(self) -> list:
        """The rows the RESULTS panel carries, as `(path, line_no, text)` — the test seam."""
        rows = []
        tree = getattr(self, "search_tree", None)
        if tree is None:
            return rows
        try:
            for index in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(index)
                label = item.text(0)
                path = str(item.data(0, self.PATH_ROLE) or "")
                rows.append((path, label.split(":")[-1], item.text(1)))
        except (RuntimeError, AttributeError):
            return []
        return rows

    def _op_find_text(self, item=None):
        """The `Find text…` row: ask the query, then walk from the directory on the screen.

        The search is THIS pane's — its provider (the session's worker, the local one or the
        elevated one), its dialect and its own report — so two panes of two servers never share a
        run. `item` is accepted for the row menu's shape and names no target: the ROOT is always
        the directory the listing shows.
        """
        if self._refuse_without_provider():
            return
        query = self._ask_search_query()
        if query is None:
            return   # the dialog was cancelled — nothing walks
        self._start_search(query)

    def _ask_search_query(self):
        """The query dialog — the ONE seam a suite replaces (the pane never runs `exec()` there)."""
        dialog = _FindTextDialog(self, self._last_search_query())
        try:
            accepted = int(dialog.exec()) == int(QDialog.DialogCode.Accepted)
        except (RuntimeError, AttributeError, TypeError):
            return None
        return dialog.query() if accepted else None

    def _last_search_query(self) -> dict:
        """The last query of THIS pane (the dialog's initial state; {} — never searched)."""
        return dict(getattr(self, "_search_query", None) or {})

    def _start_search(self, query, limits: dict = None) -> bool:
        """Open the RESULTS panel and queue the FIRST step of the walk; False — nothing ran.

        The panel takes the reader's slot (`panel_in_slot()`), so a preview already open is closed
        through the container's ONE door first — ONE panel at a time. A local pane needs no special
        case: its provider answers `queue_list()` over `local_entries()` and `queue_read()` over the
        shipped read policy, exactly like a server does. `limits` overrides a declared bound of the
        run (`modules/sftp_search.py`) — the seam a suite drives a cut through.
        """
        record = search.normalize_query((query or {}).get("needle"),
                                        (query or {}).get("case_sensitive"),
                                        (query or {}).get("scope"))
        if record is None or self.provider is None or not self._current_dir:
            return False
        if not self._container.preview_allowed(self):
            return False   # ONE panel at a time — the shipped sentence names the busy pane
        self._search_query = record
        self._container.close_preview()
        self._search = {"query": record,
                        "report": search.SearchReport(record, **dict(limits or {})),
                        "dirs": [(self._current_dir, 0)], "files": [], "done": False}
        self._search_lists.clear()
        self._search_reads.clear()
        panel = self._ensure_search_panel()
        self.search_tree.clear()
        self._search_open = True
        self.search_label.setToolTip(self._current_dir)
        self._sync_search_header()
        self._container.present_viewer(self)
        panel.show()
        self._layout_viewer_share(panel)
        self._search_advance()
        return True

    def _search_advance(self):
        """Walk ONE step — list the next directory, read the next file, or finish the run.

        ONE task at a time is the declared shape: the provider's queue is shared with the pane's
        navigation, so a search that queued thousands of reads would make its own listing crawl.
        A bound met here (or by an answer) ENDS the walk at the next step with the counters already
        reached — `SearchReport.cut` is the ONE predicate of that decision.
        """
        state = self._search
        if state is None or state.get("done"):
            return
        provider = self.provider
        if provider is None:
            self._finish_search()
            return
        report = state["report"]
        if report.cut:
            self._finish_search()      # a bound is met — nothing else is queued
            return
        if state["dirs"]:
            directory, level = state["dirs"][0]
            if not report.allow_depth(level):
                self._finish_search()  # a deeper level is deeper still — the walk is over
                return
            state["dirs"].pop(0)
            tid = provider.queue_list(directory)
            if tid is None:
                self._finish_search()
                return
            self._search_lists[int(tid)] = (directory, level)
            return
        if state["files"]:
            path, size = state["files"][0]
            cap = report.allow_read(self.viewer_cap())
            if cap <= 0:
                self._finish_search()  # the byte budget is spent — no read could run
                return
            state["files"].pop(0)
            tid = provider.queue_read(path, int(size or 0), max_bytes=cap)
            if tid is None:
                self._finish_search()
                return
            # The CAP travels with the task: the answer resolves the cut fact from it and the
            # listing's own size, exactly as the preview does (the ONE decoder, one rule).
            self._search_reads[int(tid)] = (path, int(size or 0), cap)
            return
        self._finish_search()

    def _on_search_list(self, directory, level: int, entries):
        """A directory of the walk answered: queue its candidate files and its subfolders."""
        state = self._search
        if state is None:
            return
        report = state["report"]
        subtree = search.query_scope(state["query"]) == search.SEARCH_SCOPE_SUBTREE
        paths = self.paths
        for entry in list(entries or []):
            if not report.allow_entries(1):
                break
            report.note_entries(1)
            name = str(entry.get("name") or "")
            if not name:
                continue
            full = paths.join(directory, name)
            if entry.get("is_dir"):
                if subtree:
                    state["dirs"].append((full, int(level) + 1))
                continue
            state["files"].append((full, int(entry.get("size") or 0)))
        self._sync_search_header()
        self._search_advance()

    def _on_search_read(self, path: str, size, data, cap=None):
        """A candidate answered: count it, match it, append the rows the report CARRIED.

        The bytes are decoded with the pane's OWN encoding choice (the shipped decoder), so a
        CP1251 file is searched as CP1251 text and the rows the panel shows are the rows a preview
        would show. `cap` is the ceiling the task was handed, so the CUT FACT is resolved here — a
        read stopped inside a multi-byte character is not "another encoding" (`N46`, the preview's
        rule) and its rows are not mojibake.
        """
        state = self._search
        if state is None:
            return
        report = state["report"]
        query = state["query"]
        raw = bytes(data or b"")
        truncated = bool(host_attr(self, "read_was_truncated")(len(raw), cap,
                                                              int(size or 0)))
        text, _encoding = self._decoded_text(raw, truncated=truncated,
                                            encoding=self.viewer_encoding_choice)
        report.note_read(len(raw))
        found, cut = search.match_lines(text, query["needle"], bool(query["case_sensitive"]))
        if cut:
            report.note_file_cut()   # the PER-FILE cap — said once per run, never per file
        carried = report.note_matches(found)
        rows = [(path, int(size or 0), number, line) for number, line in found[:carried]]
        if rows:
            self._append_search_rows(rows)
        self._sync_search_header()
        self._search_advance()

    def _search_answer_error(self, task_id, kind: str, message: str = "") -> bool:
        """Is this FAILED task one step of the walk? — True: it is counted and the walk goes on.

        A refused READ (a binary file, one this account cannot read) is a file the search looked at:
        it counts as scanned and the folder keeps walking. A refused LISTING costs that folder only.
        """
        state = self._search
        if state is None:
            return False
        try:
            task_id = int(task_id)
        except (TypeError, ValueError):
            return False
        listed = self._search_lists.pop(task_id, None)
        path = self._search_reads.pop(task_id, None)
        if listed is None and path is None:
            return False
        if path is not None:
            state["report"].note_read(0)   # opened and refused — still a file it looked at
            self._sync_search_header()
        self._search_advance()
        return True

    def _search_answer_cancelled(self, task_id) -> bool:
        """A step of the walk was CANCELLED (the pane's own Cancel): the run stops with it."""
        state = self._search
        if state is None:
            return False
        try:
            task_id = int(task_id)
        except (TypeError, ValueError):
            return False
        listed = self._search_lists.pop(task_id, None)
        path = self._search_reads.pop(task_id, None)
        if listed is None and path is None:
            return False
        self._finish_search()
        return True

    def _finish_search(self):
        """The walk is over: the final counters and the ONE sentence of the outcome (once)."""
        state = self._search
        if state is None or state.get("done"):
            return
        state["done"] = True
        report = state["report"]
        self._sync_search_header()
        if report.files_cut:
            # ONE sentence per RUN, however many files met the cap (never one per file).
            self.message.emit(_t("sftp.search.file_cut", limit=search.MATCHES_PER_FILE))
        if report.cut:
            self.message.emit(self._search_cut_text(report))
        elif not report.matches:
            self.message.emit(_t("sftp.search.none", needle=search.query_needle(state["query"])))

    def _search_cut_text(self, report) -> str:
        """ONE sentence naming the bound that stopped the run (the `sftp.archive.list_cut` rule)."""
        reason = report.cut_reason
        limit = {search.CUT_BYTES: host_attr(self, "format_size")(report.bytes_limit),
                 search.CUT_MATCHES: report.matches_limit,
                 search.CUT_DEPTH: report.depth_limit}.get(reason, report.entries_limit)
        return _t(SEARCH_CUT_KEYS.get(reason, "sftp.search.cut_entries"), limit=limit)

    def _sync_search_header(self):
        """The panel's header: the needle and the counters the run really reached."""
        state = self._search
        if state is None:
            return
        report = state["report"]
        try:
            self.search_label.setText(_t("sftp.search.header",
                                         needle=search.query_needle(state["query"]),
                                         matches=report.matches, files=report.files_matched,
                                         scanned=report.files_scanned))
        except (RuntimeError, AttributeError):
            pass   # Qt teardown — the label is already gone

    def _ensure_search_panel(self):
        """Build the RESULTS panel ONCE per pane — lazily, like every other cost of this view.

        It mirrors the archive listing's shape (a header line with the ×, then the rows) because it
        takes the SAME slot of the splitter; a pane that never searches builds none of it.
        """
        panel = getattr(self, "search_panel", None)
        if panel is not None:
            return panel
        panel = QWidget()
        panel.setMinimumWidth(self.viewer.minimumWidth())
        box = QVBoxLayout(panel)
        box.setContentsMargins(4, 0, 0, 0)
        box.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.search_label = QLabel("")
        host_attr(self, "_apply_status_style")(self.search_label, "status.sftp_row")
        self.search_label.setTextFormat(Qt.TextFormat.PlainText)
        self.search_label.setWordWrap(False)
        self.search_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.btn_search_close = QPushButton("\u00d7")   # × — the panel header's close cross
        self.btn_search_close.setFixedWidth(24)
        self.btn_search_close.setToolTip(_t("sftp.viewer.close_tooltip"))
        self.btn_search_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        head.addWidget(self.search_label, 1)
        head.addWidget(self.btn_search_close, 0)
        box.addLayout(head)
        self.search_tree = _SearchTree(self)
        self.search_tree.setColumnCount(SEARCH_COLUMNS)
        self.search_tree.setHeaderHidden(True)   # a row says what it is: `path:line` and the text
        self.search_tree.setRootIsDecorated(False)
        self.search_tree.setUniformRowHeights(True)
        self.search_tree.setColumnWidth(0, SEARCH_COLUMN_WIDTH)
        self.search_tree.itemDoubleClicked.connect(self._on_search_item)
        box.addWidget(self.search_tree, 1)
        panel.hide()
        self.search_panel = panel
        self.btn_search_close.clicked.connect(self._on_search_close)
        self.splitter.addWidget(panel)
        try:
            self.splitter.setCollapsible(self.splitter.indexOf(panel), True)
        except (RuntimeError, TypeError):  # noqa: BLE001 — teardown of a dead object: the splitter is already gone
            pass   # Qt teardown — the splitter is already gone
        return panel

    def _append_search_rows(self, rows):
        """Append the rows the report carried: `path:line` and the matched text, one per hit."""
        tree = getattr(self, "search_tree", None)
        if tree is None:
            return
        for path, size, number, line in rows:
            item = QTreeWidgetItem([f"{path}:{number}", line[:SEARCH_ROW_TEXT_MAX]])
            item.setData(0, self.PATH_ROLE, path)
            item.setData(0, self.SIZE_ROLE, int(size or 0))
            item.setToolTip(0, f"{path}:{number}")
            item.setToolTip(1, line)
            tree.addTopLevelItem(item)

    def search_key(self, event) -> bool:
        """`Esc` leaves the results, `Enter` opens the current file; True — the key is consumed."""
        try:
            key = int(event.key())
        except (AttributeError, TypeError, ValueError):
            return False
        if key == int(Qt.Key.Key_Escape):
            return bool(self._container.close_preview())
        if key in (int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter)):
            self.open_current_search_row()
            return True
        return False

    def _on_search_item(self, item, _column=0):
        """A double click on a result row — the ONE gesture of the list (`Enter` is its twin)."""
        self._open_search_row(item)

    def open_current_search_row(self):
        """`Enter` on the results (the double click's twin)."""
        try:
            item = self.search_tree.currentItem()
        except (RuntimeError, AttributeError):
            return
        if item is None:
            self.message.emit(_t("sftp.cmd.no_selection"))
            return
        self._open_search_row(item)

    def _open_search_row(self, item):
        """Open the FILE of one result through the SHIPPED preview (the panel gives the slot up).

        A jump to the matched LINE is deliberately NOT this version: the row says where the hit is
        and the reader shows the file from its first line.
        """
        path = str(item.data(0, self.PATH_ROLE) or "") if item is not None else ""
        if not path:
            return
        size = int(item.data(0, self.SIZE_ROLE) or 0)
        if self.provider is None:
            self.message.emit(_t("sftp.waiting_connection"))
            return
        if not self._container.preview_allowed(self):
            return
        self._container.close_preview()   # the RESULTS leave the slot, the reader takes it
        self._queue_viewer_read(path, size)

    def _on_search_close(self):
        """The panel's × — the SHIPPED close door (the container closes whichever is open)."""
        try:
            self._container.close_preview()
        except (RuntimeError, AttributeError):
            self._reset_search()

    def _drop_search(self) -> bool:
        """Drop the open run because its PROVIDER is leaving — the panel goes home, the maps go.

        A search belongs to ONE provider (its task ids are that provider's), so a rebind never
        resumes it: the walk was a question about the old tree. The container's `bind_worker()` asks
        this BEFORE the new transport is bound; False — nothing was running.
        """
        if self._search is None:
            return False
        self.restore_viewer()
        self._reset_search()
        return True

    def _reset_search(self):
        """Drop the run — its task maps go FIRST, so an answer in flight belongs to nobody."""
        self._search = None
        self._search_open = False
        self._search_lists.clear()
        self._search_reads.clear()
        panel = getattr(self, "search_panel", None)
        if panel is None:
            return
        try:
            self.search_tree.clear()
            self.search_label.clear()
            self.search_label.setToolTip("")
            panel.hide()
        except (RuntimeError, AttributeError):
            pass   # Qt teardown — the panel is already gone

    # ── v1.13.6: the per-SESSION encoding memory (`ui_sftp_encodings`) ───────

    def _pane_index(self) -> int:
        """This pane's INDEX in its container (0/1 — -1 when the container cannot say).

        The memory is filed per pane POSITION, so the first pane's CP1251 and the second one's
        Latin-1 come back as they were left.
        """
        try:
            return list(self._container.panes).index(self)
        except (AttributeError, RuntimeError, ValueError):
            return -1

    def _remembered_encoding(self) -> str:
        """The codec the SESSION remembers for this pane (`""` — it never chose / no identity)."""
        key = self.session_key()
        index = self._pane_index()
        if not key or index < 0:
            return ""
        return remembered_encoding_for(load_remembered_encodings(), key, index)

    def _remember_encoding(self, codec) -> bool:
        """File THIS pane's choice under the session — a merge-write of `ui_sftp_encodings`."""
        key = self.session_key()
        index = self._pane_index()
        if not key or index < 0:
            return False
        mapping = remember_encoding(load_remembered_encodings(), key, index, codec)
        return save_remembered_encodings(mapping)

    @property
    def remembered_encoding_choice(self) -> str:
        """The codec THIS pane's user really CHOSE (`""` — it still follows the global default)."""
        return str(getattr(self, "_viewer_encoding_chosen", "") or "")
