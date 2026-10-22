# -*- coding: utf-8 -*-
"""The ASSEMBLY of ONE Files pane — the state and the widgets `_SftpPane.__init__` builds.

`SftpPaneAssemblyMixin` owns `_build_pane_ui()`: the pane's bookkeeping, the source header line,
the address bar with its completer, the button row, the hint row, the listing tree, the preview
panel and the splitter that pairs them, plus the ONE drag & drop installation over every child.
The facade's own names are resolved through the seam when the body RUNS, so a caller that swaps
one on `modules.sftp_tab` still gets the swap (`AGENTS.md` §4.1, §4.3).

Contract — `SFTP_PANES.md` §1; mechanism — `DOCUMENTATION.md` §38, §59-§63.
"""
from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QCompleter, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QSplitter, QTreeWidget, QVBoxLayout, QWidget)

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # AGENTS.md §4.1: the ONE seam for a facade global — a mixin never imports the facade module
    from ..ui.mixin_support import host_attr
except ImportError:
    from ui.mixin_support import host_attr


class SftpPaneAssemblyMixin:
    """The ONE construction body of a pane: its state, its widgets and its drag & drop wiring."""

    def _build_pane_ui(self):
        """Build the pane's state and widgets (the facade's `__init__` delegates here).

        The facade's names are read ONCE at the top, through the seam, so this body stays the
        shipped one while a suite that swaps `ST._SftpTree` (or any other of them) still sees the
        replacement (`AGENTS.md` §4.1).
        """
        _SourceSwitch = host_attr(self, "_SourceSwitch")
        _SftpTree = host_attr(self, "_SftpTree")
        _ButtonRow = host_attr(self, "_ButtonRow")
        _ViewerTextView = host_attr(self, "ViewerTextView", QPlainTextEdit)
        _apply_status_style = host_attr(self, "_apply_status_style")
        _sync_source_switch = host_attr(self, "_sync_source_switch")
        SORT_DEFAULT_COLUMN = host_attr(self, "SORT_DEFAULT_COLUMN", 0)
        SOURCE_REMOTE = host_attr(self, "SOURCE_REMOTE", "remote")
        focus_ring = host_attr(self, "focus_ring")
        syntax = host_attr(self, "syntax")
        resolve_viewer_wrap = host_attr(self, "resolve_viewer_wrap")
        resolve_viewer_max_bytes = host_attr(self, "resolve_viewer_max_bytes")

        self._current_dir = "/"
        self._pending_lists = {}     # task_id → requested path (staleness filter)
        self._transfer_tasks = set()  # task ids of active upload/download
        self._own_transfers = set()   # the transfer ids THIS pane queued (v1.7rc1)
        self._up_item = None          # the ".." row (identified by object)
        # v1.3.1: the viewer's read tasks — task_id → remote path, and the id of
        # the LAST requested read (only its answer fills the panel: a fast double
        # click on two files must end up showing the SECOND one).
        self._read_tasks = {}
        self._last_read = None
        self._viewer_encoding = "utf-8"
        # v1.4.7: ONE highlighter per pane (created on the first preview), the
        # language of what is on the screen, and the block window the last
        # formatting pass covered (so a repeated scroll is free).
        self._highlighter = None
        self._viewer_language = syntax.LANG_NUMBERS
        self._highlight_range = None
        # v1.3.1.1: the FACTS about previewability — path → READ_ERROR_* of a read
        # that the worker really refused (see preview_block_reason); per session.
        self._blocked = {}
        self._blocked_icon_cache = None
        # v1.3.3.2: the file operations — task_id → kind, so an
        # answer refreshes the listing and an error is reported as an OPERATION
        # error (the queue itself is untouched), and the pre-flight listings of a
        # drop on a directory row — task_id → (target dir, local files).
        self._op_tasks = {}
        self._pending_batches = {}
        # v1.7.3: the pane-to-pane drops whose target directory is NOT on the screen — the task id
        # of the pre-flight listing → (the (source, name, size) triples, the kind, the destination,
        # the SOURCE dialect of the rows). v1.7.4rc2: the dialect rides along, because a local row
        # and a remote one carry two spellings of "the same" path.
        self._pending_drops = {}
        self._drag_source = None      # the widget the current drag event came from
        # v1.7rc3: the viewer's MOVE (the mc preview of the two-pane view). `_viewer_home` is the
        # pane the viewer widget belongs to, and the pane currently CARRYING it is the one whose
        # `_viewer_host is None` → the viewer answers "which pane is showing a preview" ONCE.
        self._viewer_home = self
        self._viewer_host = None      # set on the pane that borrowed the viewer
        self._viewer_from = None      # the pane whose row opened the borrowed preview
        self._viewer_borrowed = False  # set on the pane that is CARRYING a borrowed preview
        # The DECLARED "a preview is open" flag: `QWidget.isVisible()` answers False for a pane
        # that is not on screen yet (a dock tab that was never shown, the offscreen test
        # platform), so the preview state is never read off the widgets.
        self._viewer_open = False
        # v1.13: the ARCHIVE view (`ARCHIVES.md`) — the listing the SAME panel carries, the copy it
        # reads, the leg in flight, the legs a close ABANDONED and the legs a SWITCH left owned.
        self._archive = None
        self._archive_open = False
        self._archive_tasks = {}
        self._archive_dropped = set()
        self._archive_legs = {}
        # v1.6.3: the address bar's own bookkeeping — the normalize tasks
        # in flight (task_id → the text the user typed) and the completer's listings
        # (task_id → the directory they answer). `_completer_dir` is the directory the
        # completer is currently fed with, so the typed directory is listed at most ONCE
        # per directory change.
        self._normalize_tasks = {}
        self._completer_lists = {}
        self._completer_dir = None
        # v1.7rc2: the copy/move BATCHES — `_op_batches` maps a queued task id to its batch and
        # `_batches` holds the counters that make ONE report over an asynchronous queue. v1.7.4rc2:
        # `_op_targets` names the DESTINATION of a batch task (its pane and its directory), because
        # the provider that ANSWERS may belong to the OTHER pane.
        self._op_batches = {}
        self._op_targets = {}
        self._batches = {}
        self._batch_seq = 0
        # v1.7.3: the remembered directory of this session — the hint the
        # FIRST transport of each pane opens, and the flag that keeps a second list from re-asking.
        self._restored = False
        self._restore_dir = ""
        # v1.7.3: the reader's word wrap — ONE global setting, read at
        # construction so both panes and every session agree.
        self._viewer_wrap = resolve_viewer_wrap()
        # v1.9.3: the reader's ENCODING — resolved on the FIRST read (`viewer_encoding_choice`), because
        # a pane is built before its container knows WHICH session it is: the session's own memory
        # (`ui_sftp_encodings`, v1.13.6) decides first, then the shipped global default. A pane's menu
        # moves its own slot alone, so a CP1251 preview and a Latin-1 one live side by side.
        # `_viewer_encoding_chosen` is the value the USER picked ("" — this pane never chose).
        self._viewer_encoding_choice = self._viewer_encoding_chosen = None
        self._viewer_path = ""
        # v1.7.5: the reader's CEILING — the SAME "one global setting, resolved ONCE" rule as the
        # wrap above. The value travels into every read task, so the worker never reads a config.
        self._viewer_cap = resolve_viewer_max_bytes()
        # v1.7.5: the LISTING's sort — a VIEW state of this pane (never a config key): the column
        # the header click chose and its direction. The default IS the provider's own order
        # (directories first, then case-insensitive by name), so a listing nobody sorted stays
        # exactly as the source answered it.
        self._sort_column = SORT_DEFAULT_COLUMN
        self._sort_desc = False
        # v1.7rc1: the pane-scoped keys (the F-actions) and the ACTIVE-pane ring.
        self._pane_actions = []
        self._ring = focus_ring.FocusRing(styled_widget=None) if focus_ring is not None else None
        # v1.7.4rc1: the DATA SOURCE of this pane (LOCAL_PANE.md §1). The provider is the object
        # the pane binds — the container's shipped worker for a remote pane, and ONE
        # `LocalFsWorker` of its own for a local one, created on the first switch to Local and
        # kept alive for the pane's whole life (a switch back and forth costs no thread).
        self._source = SOURCE_REMOTE
        self._local_provider = None
        #: The provider this pane's slots are CONNECTED to (`bind_worker` is the ONE writer):
        #: a disconnect asks for it by name, so a provider the pane never bound is never asked.
        self._bound_provider = None
        #: The local directory this pane really sat in — the OS look survives a round trip
        #: through the server (LOCAL_PANE.md §4), while the REMOTE side is re-opened by the
        #: session's own rule (the per-server memory, then "/").
        self._local_dir = ""
        # v1.8: the ELEVATED provider of this pane (ELEVATED_PANE.md §1) — the SHIPPED
        # `SftpWorker` over the client the handshake opened as another user, plus its client (the
        # object that closes the channel), the target user, the in-flight flag and the handshake
        # thread. The SOURCE stays `SOURCE_REMOTE`; only the provider the pane binds changes.
        self._elevated_provider = None
        self._elevated_client = None
        self._elevation_user = ""
        self._elevation_pending = False
        self._handshake = None
        self._waiting = True   # no provider bound yet: the shipped "waiting for connection" state
        #: v1.9.8: is this the ACTIVE pane? The header line carries the mark beside the
        #: source (`header_text_marked()`), written by `set_active()` through `_sync_header()`.
        self._active = False

        t = _t
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        # v1.7.5 (LOCAL_PANE.md §3): the pane's SOURCE HEADER LINE — the FIRST row, naming WHAT
        # this pane READS ("This computer" for the OS disk, the session's alias for a server). It
        # is a VIEW of the source: ONE line, never focusable, never a drop target — the keyboard
        # walk of §4 belongs to the tree and a drop is resolved in the tree's viewport.
        self.header_label = QLabel("")
        _apply_status_style(self.header_label, "status.sftp_row")
        self.header_label.setWordWrap(False)
        self.header_label.setTextFormat(Qt.TextFormat.PlainText)
        self.header_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        outer.addWidget(self.header_label)
        self._sync_header()

        # Path row — the current directory (the "address bar"): EDITABLE, because Enter navigates
        # through the SERVER's own resolution (the worker's `queue_normalize`), so `~`, a relative
        # path and a symlink stay the remote's business. Read-only until a transport is bound.
        self.path_label = QLineEdit(t("sftp.waiting_connection"))
        _apply_status_style(self.path_label, "status.sftp_row")
        self.path_label.setReadOnly(True)   # until set_worker() binds a transport
        self.path_label.setPlaceholderText(t("sftp.path_placeholder"))
        self.path_label.setClearButtonEnabled(True)
        self.path_label.returnPressed.connect(self._on_path_entered)
        self.path_label.textEdited.connect(self._on_path_edited)
        self.path_completer_model = QStringListModel([], self)
        self.path_completer = QCompleter(self.path_completer_model, self)
        self.path_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.path_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.path_completer.setCompletionRole(Qt.ItemDataRole.DisplayRole)
        self.path_label.setCompleter(self.path_completer)
        # v1.7.4rc1: the SOURCE SWITCH of the pane (LOCAL_PANE.md §4) — the leading control of the
        # address row, a one-line pair so it costs the bar no height. It is the SECOND pane's
        # control alone: the first pane is the session's own remote tree, the local source is what
        # makes the OTHER side of a commander a choice, and with one pane there is no other side.
        self.source_switch = _SourceSwitch()
        self.source_switch.changed.connect(self._on_source_switch)
        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(6)
        path_row.addWidget(self.source_switch, 0)
        path_row.addWidget(self.path_label, 1)
        outer.addLayout(path_row)
        _sync_source_switch(self.source_switch, self._source, enabled=False, available=False)

        # Buttons: navigation | operations.
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.btn_up = QPushButton(t("sftp.up"))
        self.btn_refresh = QPushButton(t("sftp.refresh"))
        # v1.14: the search of this pane as a CONTROL, not only a row-menu verb — it walks from the
        # directory on the screen, exactly like `_op_find_text()` of the row menu (ONE door, two
        # gestures), so it rides the row's enable rule (`_sync_transfer_availability`).
        self.btn_find = QPushButton(t("sftp.search.row"))
        self.btn_find.setToolTip(t("sftp.search.tooltip"))
        self.btn_upload = QPushButton(t("sftp.upload"))
        self.btn_download = QPushButton(t("sftp.download"))
        self.btn_cancel = QPushButton(t("sftp.cancel"))
        self.btn_cancel.setEnabled(False)  # active while transfers are running
        for b in (self.btn_up, self.btn_refresh, self.btn_find, self.btn_upload,
                  self.btn_download):
            b.setEnabled(False)  # until set_worker()
        bar.addWidget(self.btn_up)
        bar.addWidget(self.btn_refresh)
        bar.addWidget(self.btn_find)
        bar.addStretch(1)
        bar.addWidget(self.btn_upload)
        bar.addWidget(self.btn_download)
        bar.addWidget(self.btn_cancel)
        # ONE widget, so the second pane hides the row as a unit; the layout is built INTO it (Qt
        # refuses a layout that already has an owner) and the floor is the class's own (`_ButtonRow`).
        self.buttons_bar = _ButtonRow()
        self.buttons_bar.setLayout(bar)
        outer.addWidget(self.buttons_bar)
        # v1.7rc3: the hint row of the right pane — hidden in the shipped single-pane look and
        # in the FIRST pane; elided (ONE line, never a reflow of the listing) with the whole
        # text in the tooltip.
        self.hints_label = QLabel("")
        _apply_status_style(self.hints_label, "status.sftp_row")
        self.hints_label.setWordWrap(False)
        self.hints_label.setTextFormat(Qt.TextFormat.PlainText)
        self.hints_label.hide()
        outer.addWidget(self.hints_label)
        # The pane's role in the container (v1.7rc3): a SECONDARY pane keeps no button row.
        self._secondary = False
        self._sync_secondary_ui()

        # Listing: Name | Size | Modified.
        self.tree = _SftpTree()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([t("sftp.column_name"), t("sftp.column_size"),
                                   t("sftp.column_modified")])
        # v1.7.5: the header is a real SORT CONTROL. Qt's automatic sorting stays OFF: it sorts with
        # the direction it is given, and `DescendingOrder` REVERSES the comparator — which would drop
        # the files above the directories and break the two GROUP rules of `_SftpRowItem`. The pane
        # drives `sortItems()` itself, always ASCENDING, and sets the arrow afterwards with the
        # signals blocked.
        self.tree.header().setSectionsClickable(True)
        self.tree.header().setSortIndicatorShown(True)
        self.tree.header().setSortIndicator(SORT_DEFAULT_COLUMN, Qt.SortOrder.AscendingOrder)
        self.tree.header().sectionClicked.connect(self._on_header_clicked)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setColumnWidth(0, 320)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        # v1.3.3.2: the operations live in the context menu (the QActions are built
        # by _build_context_menu — the test seam; exec() never runs in the tests).
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        # v1.3.3.2: drag-OUT — a dragged row hands out its remote path as text/plain
        # (DragOnly: the tree never accepts its own drops; D&D INTO the tab is
        # handled by the pane's own eventFilter, which consumes those events first).
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.DragOnly)
        self.tree.setToolTip(t("sftp.drag_hint"))
        # v1.7rc1: the focus inside a pane makes it the ACTIVE pane of the container.
        self.tree.focus_in = self.activate

        # v1.3.1: the preview panel — QSplitter [tree | viewer].
        # The panel starts hidden (it appears on a double click on a text file);
        # the splitter is a horizontal pair, the viewer is collapsible — but the
        # size is only fixed via minimumWidth + setSizes (Qt gotcha #13:
        # setMaximumWidth on a splitter member breaks the size accounting).
        self.viewer = QWidget()
        self.viewer.setMinimumWidth(240)
        viewer_box = QVBoxLayout(self.viewer)
        viewer_box.setContentsMargins(4, 0, 0, 0)
        viewer_box.setSpacing(2)
        viewer_head = QHBoxLayout()
        viewer_head.setSpacing(6)
        self.viewer_label = QLabel("")
        _apply_status_style(self.viewer_label, "status.sftp_row")
        self.viewer_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.viewer_label.setWordWrap(False)
        self.btn_viewer_close = QPushButton("\u00d7")  # × — the panel header's close cross
        self.btn_viewer_close.setFixedWidth(24)
        self.btn_viewer_close.setToolTip(t("sftp.viewer.close_tooltip"))
        # v1.7rc3: the cross must never take the KEYBOARD. A preview belongs to the pane whose
        # listing it was opened from, so `←`/`→` must keep reaching that tree instead of walking
        # into this button (a focusable child of the panel is the one way the walk could be lost).
        self.btn_viewer_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        viewer_head.addWidget(self.viewer_label, 1)
        # v1.14.1: the reader's BACKGROUND chip — it shows the hue the reader's surface is painted
        # with (`ui_viewer_background`) and opens the preset menu of the verbs mixin. A control, not
        # a row: the header is already the panel's one strip of chrome.
        self.btn_viewer_background = QPushButton("")
        self.btn_viewer_background.setFixedSize(22, 22)
        self.btn_viewer_background.setToolTip(t("sftp.viewer.background"))
        self.btn_viewer_background.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_viewer_background.clicked.connect(self._on_viewer_background_clicked)
        viewer_head.addWidget(self.btn_viewer_background, 0)
        viewer_head.addWidget(self.btn_viewer_close, 0)
        viewer_box.addLayout(viewer_head)
        self.viewer_text = _ViewerTextView()
        self.viewer_text.setReadOnly(True)          # v1.3.1: read-only (editing is rejected)
        self.viewer_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # v1.7.3: the reader's OWN context menu — Qt's standard one PLUS the "Word wrap" row, which
        # is why the menu is built by a method (the `_build_context_menu` test seam).
        self.viewer_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.viewer_text.customContextMenuRequested.connect(self._on_viewer_menu)
        self.viewer_text.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        # v1.4.7: the lazy hook — updateRequest fires on a scroll AND on a
        # resize, which is exactly the two moments new blocks become visible.
        self.viewer_text.updateRequest.connect(self._on_viewer_update_request)
        viewer_box.addWidget(self.viewer_text, 1)
        # v1.14.1: the reader's own verbs — the `Ctrl+F` owner and the stored background hue.
        self._setup_viewer_verbs()
        self.viewer.hide()
        self.set_viewer_wrap(self._viewer_wrap, persist=False)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.viewer)
        # setCollapsible AFTER addWidget (Qt: an out-of-range index otherwise):
        # the tree must never vanish, the viewer may be dragged shut.
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        outer.addWidget(self.splitter, 1)

        self.btn_up.clicked.connect(self.go_up)
        self.btn_refresh.clicked.connect(lambda: self._relist(self._current_dir))
        self.btn_find.clicked.connect(lambda: self._op_find_text())
        self.btn_upload.clicked.connect(self._on_upload)
        self.btn_download.clicked.connect(self._on_download)
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_viewer_close.clicked.connect(self.close_viewer)

        # v1.2.8: D&D — files from Explorer into any spot of the pane. Qt delivers
        # drag events to the widget under the cursor (the tree covers almost the
        # whole pane), so the handlers live here, and eventFilter forwards events
        # from the CHILDREN (tree/viewport/header/buttons) to the same handlers.
        self.setAcceptDrops(True)
        for w in self.findChildren(QWidget):
            w.installEventFilter(self)
        self.installEventFilter(self)

        self._build_pane_shortcuts()
        # v1.7rc3: the tree hands its keys to the pane (the walk of the two-pane view).
        self.tree.pane_key = self._on_pane_key
        # v1.7.3: the tree hands out the pane's IDENTITY with a dragged row (the pane-to-pane drop).
        self.tree.pane = self
        if self._ring is not None:
            self._ring.styled_widget = self.tree
            self._ring.apply()
