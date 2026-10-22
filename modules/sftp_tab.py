# -*- coding: utf-8 -*-
"""The Files tab of a terminal session — a CONTAINER of 1–2 PANES over ONE SFTP worker.

`SftpTab` is the FACADE of the container (the pane list, the ONE worker binding, the session identity,
the preview slot, the live viewer settings, the drag forwarding and the ONE teardown) over three
mixins (`sftp_container_panes.py`, `..._session.py`, `..._viewer.py`) and `SftpExtractMixin`.
`_SftpPane` is a FACADE of its own over the `sftp_pane_*.py` mixins, the widgets of
`sftp_pane_widgets.py` and the pure readers of `sftp_pane_helpers.py` — every moved name declared by
`MOVED_NAMES`. A pane binds the SHARED worker's signals and answers only the task ids IT queued, so
the panes navigate independently; the page talks to the container (`page.sftp_tab`).

Contract — `SFTP_PANES.md`; mechanism — §38, §59-§63."""

from PySide6.QtCore import QCoreApplication, QEvent, QStringListModel, Qt, Signal
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QCompleter, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QTreeWidget, QVBoxLayout, QWidget,
)

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # v1.4.3: the ONE QSS registry
    from ..ui import theme_qss
except ImportError:
    try:
        from ui import theme_qss
    except ImportError:  # flat layout: the ui/ directory itself is on sys.path
        theme_qss = None

try:  # v1.5rc4: the ONE visible-focus indicator (the ACTIVE pane of v1.7rc1)
    from ..ui import focus_ring
except ImportError:
    try:
        from ui import focus_ring
    except ImportError:  # flat layout: the ui/ directory itself is on sys.path
        focus_ring = None

try:  # v1.9.8: the vector glyph of the Files Commander corner control
    from ..ui.icons import get_icon
except ImportError:
    try:
        from ui.icons import get_icon
    except ImportError:  # a stripped build — the corner button stays text-only
        def get_icon(name):
            return QIcon()

try:  # v1.3.1: the operation kinds THIS module still queues and the task payload readers
    from .sftp_worker import (KIND_DELETE, KIND_MKDIR, KIND_RENAME, KIND_TRASH,
                              READ_ERROR_TOO_LARGE, SftpWorker, register_orphan_sftp_worker)
except ImportError:
    from sftp_worker import (KIND_DELETE, KIND_MKDIR, KIND_RENAME, KIND_TRASH,  # type: ignore
                             READ_ERROR_TOO_LARGE, SftpWorker, register_orphan_sftp_worker)

try:  # v1.4.7: detection + tokenizers + the ONE highlighter
    from . import syntax_highlight as syntax
except ImportError:
    import syntax_highlight as syntax

try:  # v1.7.4rc1: the LOCAL provider of a pane and its refusals; v1.13.1: the container's extractor
    from . import local_fs_worker as local_fs
    from . import sftp_extract
except ImportError:  # flat launch from the project root
    import local_fs_worker as local_fs
    import sftp_extract  # type: ignore

try:  # v1.8: the ELEVATED provider of a pane — the handshake the pane starts
    from .sftp_elevated import ElevatedHandshake
except ImportError:  # flat launch from the project root
    from sftp_elevated import ElevatedHandshake

try:  # v1.8: the elevation dialogue (the pane resolves it as a facade global, the shipped seam)
    from ..dialogs.elevated_dialog import ask_elevation
except ImportError:  # flat launch from the project root
    from dialogs.elevated_dialog import ask_elevation

# v1.8rc4/rc5: `_SftpPane` is a FACADE over its pane mixins — the pane-scoped keys and the walk, the
# listing with its address bar, the read-only preview (and its v1.14.1 verbs), the transfers with the
# batch copy/move and the drag & drop with the row context menu. A cluster's module-level facts travel
# WITH it and are imported back here, so `modules.sftp_tab` keeps the shipped surface the suite reads.
try:
    from .sftp_pane_walk import (PANE_HINTS, PANE_SHORTCUTS, HINT_SEPARATOR,
                                 SftpPaneWalkMixin)
    from .sftp_pane_listing import (SORT_COLUMNS, SORT_DEFAULT_COLUMN,
                                    SftpPaneListingMixin)
    from .sftp_pane_viewer import (VIEWER_FREEZE_MS_PER_MB, VIEWER_MAX_BYTES_CONFIG,
                                   VIEWER_MAX_BYTES_MAX, VIEWER_MAX_BYTES_MIN,
                                   VIEWER_MAX_BYTES_STEP, VIEWER_MAX_BYTES_WARN,
                                   SftpPaneViewerMixin, viewer_freeze_seconds)
    from .sftp_pane_helpers import (VIEWER_ENCODING_CONFIG, VIEWER_ENCODING_DEFAULT,
                                    VIEWER_ENCODINGS, VIEWER_WRAP_CONFIG, ask_conflict, decode_text,
                                    format_mtime, format_size, normalize_viewer_encoding,
                                    preview_block_reason, resolve_viewer_encoding,
                                    resolve_viewer_wrap, save_viewer_background,
                                    save_viewer_encoding, save_viewer_wrap)
    from .sftp_pane_transfer import SftpPaneTransferMixin
    from .sftp_pane_dnd import SftpPaneDndMixin
    from .sftp_pane_elevated import SftpPaneElevatedMixin
    from .sftp_pane_verbs import SftpViewerVerbsMixin   # v1.14.1: the reader's find bar and chip
except ImportError:  # flat launch from the project root
    from sftp_pane_walk import PANE_HINTS, PANE_SHORTCUTS, HINT_SEPARATOR, SftpPaneWalkMixin
    from sftp_pane_listing import SORT_COLUMNS, SORT_DEFAULT_COLUMN, SftpPaneListingMixin
    from sftp_pane_viewer import (VIEWER_FREEZE_MS_PER_MB, VIEWER_MAX_BYTES_CONFIG,
                                  VIEWER_MAX_BYTES_MAX, VIEWER_MAX_BYTES_MIN,
                                  VIEWER_MAX_BYTES_STEP, VIEWER_MAX_BYTES_WARN,
                                  SftpPaneViewerMixin, viewer_freeze_seconds)
    from sftp_pane_helpers import (VIEWER_ENCODING_CONFIG, VIEWER_ENCODING_DEFAULT,
                                   VIEWER_ENCODINGS, VIEWER_WRAP_CONFIG, ask_conflict, decode_text,
                                   format_mtime, format_size, normalize_viewer_encoding,
                                   preview_block_reason, resolve_viewer_encoding,
                                   resolve_viewer_wrap, save_viewer_background,
                                   save_viewer_encoding, save_viewer_wrap)
    from sftp_pane_transfer import SftpPaneTransferMixin
    from sftp_pane_dnd import SftpPaneDndMixin
    from sftp_pane_elevated import SftpPaneElevatedMixin
    from sftp_pane_verbs import SftpViewerVerbsMixin  # type: ignore


# v1.14rc3: the split — the four WIDGETS with their constants, the PURE readers and the VOCABULARY of
# the pane family, DEFINED in their own modules and imported back so `modules.sftp_tab.<name>` holds.
try:
    from .sftp_pane_widgets import (BUTTONS_BAR_MIN_WIDTH, ELEVATED_SOURCE_LABEL,
                                    ELEVATED_SOURCE_TOOLTIP, LOCAL_SOURCE_LABEL,
                                    LOCAL_UNAVAILABLE_HINT, _apply_status_style, _ButtonRow,
                                    _SourceSwitch, _SftpRowItem, _SftpTree, _sync_source_switch)
    from .sftp_pane_helpers import (COMMANDER_CONFIG_BOOL, COMMANDER_CONFIG_RATIO,
                                    COMMANDER_MIN_PANE_PX, COMMANDER_RATIO_DEFAULT,
                                    COMMANDER_RATIO_MAX, COMMANDER_RATIO_MIN, DIRS_CONFIG,
                                    ISDIR_ROLE, LOCAL_PATHS, MAX_REMEMBERED_DIRS, MTIME_ROLE,
                                    PANE_DRAG_MIME, PANE_SOURCES, PATH_ROLE, POSIX_PATHS,
                                    SIZE_ROLE, SOURCE_ELEVATED, SOURCE_LOCAL, SOURCE_REMOTE,
                                    PathDialect, _win_standard_path, dialect_for,
                                    load_commander_settings, load_remembered_dirs,
                                    local_error_text, local_files, name_refusal_text, pane_payload,
                                    read_was_truncated, remember_dir, remembered_dir_for, row_name,
                                    row_path, sanitize_dirs)
except ImportError:  # flat launch from the project root
    from sftp_pane_widgets import (BUTTONS_BAR_MIN_WIDTH, ELEVATED_SOURCE_LABEL,  # type: ignore
                                   ELEVATED_SOURCE_TOOLTIP, LOCAL_SOURCE_LABEL,
                                   LOCAL_UNAVAILABLE_HINT, _apply_status_style, _ButtonRow,
                                   _SourceSwitch, _SftpRowItem, _SftpTree, _sync_source_switch)
    from sftp_pane_helpers import (COMMANDER_CONFIG_BOOL, COMMANDER_CONFIG_RATIO,  # type: ignore
                                   COMMANDER_MIN_PANE_PX, COMMANDER_RATIO_DEFAULT,
                                   COMMANDER_RATIO_MAX, COMMANDER_RATIO_MIN, DIRS_CONFIG,
                                   ISDIR_ROLE, LOCAL_PATHS, MAX_REMEMBERED_DIRS, MTIME_ROLE,
                                   PANE_DRAG_MIME, PANE_SOURCES, PATH_ROLE, POSIX_PATHS,
                                   SIZE_ROLE, SOURCE_ELEVATED, SOURCE_LOCAL, SOURCE_REMOTE,
                                   PathDialect, _win_standard_path, dialect_for,
                                   load_commander_settings, load_remembered_dirs,
                                   local_error_text, local_files, name_refusal_text, pane_payload,
                                   read_was_truncated, remember_dir, remembered_dir_for, row_name,
                                   row_path, sanitize_dirs)

try:  # v1.9.8: the corner control of the two-pane view (its own module — the facade's budget)
    from .sftp_commander_corner import CommanderCorner
except ImportError:  # flat launch from the project root
    from sftp_commander_corner import CommanderCorner

# v1.14rc4: the container's OWN clusters — the pane list and the Commander, the session family and the
# preview slot — beside the pane's assembly. The same seam rule as the pane mixins: none of them
# imports this module (`AGENTS.md` §4.1), and every name they resolve lives in `MODULE_FACADE_SEAMS`.
try:
    from .sftp_pane_assembly import SftpPaneAssemblyMixin
    from .sftp_container_panes import SftpContainerPanesMixin
    from .sftp_container_session import SftpContainerSessionMixin
    from .sftp_container_viewer import SftpContainerViewerMixin
except ImportError:  # flat launch from the project root
    from sftp_pane_assembly import SftpPaneAssemblyMixin  # type: ignore
    from sftp_container_panes import SftpContainerPanesMixin  # type: ignore
    from sftp_container_session import SftpContainerSessionMixin  # type: ignore
    from sftp_container_viewer import SftpContainerViewerMixin  # type: ignore


# ── The facts this facade still DECLARES: the worker signals a pane binds, and the reader's
# ── CEILING — the CAP readers stay HERE (`DOCUMENTATION.md` §14f / §68 name this home) ──

#: The worker signals a pane binds (the container owns the worker, the pane its slots).
WORKER_SIGNAL_NAMES = ("list_ready", "task_started", "task_done", "task_error",
                       "task_cancelled", "read_ready", "normalize_ready")

#: The Qt classes the pane's ASSEMBLY builds its widgets with, RE-EXPORTED (`AGENTS.md` §4.1): a
#: caller reads a value off them on THIS module (`modules.sftp_tab.QPlainTextEdit.LineWrapMode`) and
#: that shipped path outlives the move; the manifest keeps the re-export from reading as dead.
REEXPORTED_QT = (QCompleter, QFontDatabase, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                 QPushButton, QStringListModel, QTreeWidget)


def clamp_viewer_max_bytes(value) -> int:
    """PURE: a cap into the DECLARED range `[VIEWER_MAX_BYTES_MIN, VIEWER_MAX_BYTES_MAX]`.

    A foreign value (a string, `None`, a bool, a negative number) answers the DEFAULT — the
    shipped `MAX_READ_BYTES`. The range is ONE declaration, so the slider, the value box and
    the reader can never disagree about what a legal cap is.
    """
    if isinstance(value, bool):
        return VIEWER_MAX_BYTES_MIN
    try:
        number = int(value)
    except (TypeError, ValueError):
        return VIEWER_MAX_BYTES_MIN
    return max(VIEWER_MAX_BYTES_MIN, min(VIEWER_MAX_BYTES_MAX, number))


def resolve_viewer_max_bytes(cfg: dict = None) -> int:
    """The reader's ceiling as a PURE value (v1.7.5): the config's cap, clamped, else the default.

    Only a real number counts; a missing key, a string, a bool or an unreadable config answers
    `MAX_READ_BYTES` — the shipped read policy is what a user who never touched the setting has.
    """
    if not isinstance(cfg, dict):
        try:
            from i18n import load_config
        except Exception:  # noqa: BLE001 — a build without i18n keeps the default
            return VIEWER_MAX_BYTES_MIN
        try:
            cfg = load_config() or {}
        except Exception:  # noqa: BLE001 — a broken config store keeps the default
            cfg = {}
    value = cfg.get(VIEWER_MAX_BYTES_CONFIG) if isinstance(cfg, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return VIEWER_MAX_BYTES_MIN
    return clamp_viewer_max_bytes(value)


class _SftpPane(SftpPaneAssemblyMixin, SftpPaneWalkMixin, SftpPaneListingMixin,
                SftpPaneViewerMixin, SftpViewerVerbsMixin, SftpPaneTransferMixin,
                SftpPaneDndMixin, SftpPaneElevatedMixin, QWidget):
    """ONE directory pane of the "Files" tab — a FACADE over its eight pane mixins.

    The facade keeps what ONE pane is: the assembly entry (`__init__`), the worker binding and the
    source switch, the file operations, the copy/move batches, the worker slots and the theme/re-text
    walks. The clusters live in their own modules: the state and the widgets
    (`sftp_pane_assembly.py`), the pane-scoped keys and the mc/far walk (`sftp_pane_walk.py`), the
    listing and the address bar (`sftp_pane_listing.py`), the read-only preview
    (`sftp_pane_viewer.py`), its FIND BAR and background chip (`sftp_pane_verbs.py`, v1.14.1), the
    transfers with the batch copy/move (`sftp_pane_transfer.py`), the drag & drop with the row
    context menu (`sftp_pane_dnd.py`) and the ELEVATED source (`sftp_pane_elevated.py`, §4.25).

    A mixin never imports this module — it duck-types the instance and resolves a facade global
    through `host_attr()` at call time (`MODULE_FACADE_SEAMS` below DECLARES them, `AGENTS.md` §4.1,
    §4.3). Everything a pane owns is per-listing state; the WORKER is the container's, so a second
    pane costs a second listing and never a second channel. The pane answers only the task ids IT
    queued (they are unique, so the split of the shared worker's signals is exact).
    """

    # The row ROLES are declared ONCE in `sftp_pane_helpers.py` (the row class and the row readers
    # compare them there); the class-level aliases keep the shipped `pane.PATH_ROLE` answering.
    PATH_ROLE, ISDIR_ROLE, SIZE_ROLE, MTIME_ROLE = PATH_ROLE, ISDIR_ROLE, SIZE_ROLE, MTIME_ROLE

    # Local hints in the window's status bar (waiting for connection, no selection).
    # Worker errors/progress are shown by the window itself via its signals.
    message = Signal(str)

    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._build_pane_ui()

    # ── v1.7rc1: the pane identity and the ACTIVE-pane hook ──────────────

    @property
    def source(self) -> str:
        """This pane's DATA SOURCE (`SOURCE_REMOTE` | `SOURCE_LOCAL`, LOCAL_PANE.md §1)."""
        return self._source

    @property
    def paths(self) -> PathDialect:
        """The path rules of this pane's source — every join, split and root test goes through it."""
        return dialect_for(self._source)

    @property
    def provider(self):
        """The object this pane binds (the shipped worker, the local provider, or the elevated one).

        `None` — no provider yet: a remote pane waiting for the session's connection. A LOCAL pane
        and an ELEVATED one always have theirs, which is why the waiting state is a REMOTE state.
        """
        if self._source == SOURCE_LOCAL:
            return self._local_provider
        if self._elevated_provider is not None:
            return self._elevated_provider
        return self.worker

    @property
    def worker(self):
        """The SHARED transport worker — the CONTAINER owns the binding (SFTP_PANES.md §2).

        A LOCAL pane reads the OS disk through its OWN provider and never through this one: the
        property answers the session's worker whatever the source, so a remote call site keeps
        its shipped meaning (LOCAL_PANE.md §1).
        """
        return self._container.worker

    def session_key(self) -> str:
        """The stable identity of the SESSION this pane lists (the container's, v1.7.3)."""
        try:
            return str(self._container.session_key() or "")
        except (AttributeError, RuntimeError):
            return ""

    def activate(self):
        """Tell the container that the keyboard entered THIS pane (the ACTIVE pane)."""
        try:
            self._container.set_active_pane(self)
        except (RuntimeError, AttributeError):
            pass  # Qt teardown / a bare pane in a unit test — never raises

    def set_active(self, on: bool):
        """Draw (or drop) the focus ring of the ACTIVE pane — and MARK ITS HEADER (v1.9.8).

        The ring alone was the whole cue: a thin border a user has to hunt for. The header line
        carries the pane's source, so the mark lands exactly where the pane names itself
        (`header_text_marked()`, the ONE writer of that label). Never raises.
        """
        self._active = bool(on)
        if self._ring is not None:
            try:
                self._ring.set_active(bool(on))
            except RuntimeError:
                pass  # Qt teardown — the tree is already destroyed
        try:
            self._sync_header()
        except (RuntimeError, AttributeError):
            pass  # Qt teardown — the header is already destroyed

    # ── Worker binding (the container calls these) ───────────────────────

    def bind_worker(self, old_worker, new_worker, source: str = ""):
        """Bind/unbind the pane's PROVIDER: `None` — the "waiting for connection" state.

        `_bound_provider` (the DECLARED record) WINS over `old_worker`, so a pane bound to a
        provider of its OWN (LOCAL or ELEVATED) never listens to two. Every task map belongs to ONE
        provider and is cleared here; the `source` keyword is what a SWITCH passes (the pane adopts
        the source and binds its provider, while the container's own call keeps every pane).
        """
        if source:
            self._source = SOURCE_LOCAL if str(source) == SOURCE_LOCAL else SOURCE_REMOTE
        old = self._bound_provider if self._bound_provider is not None else old_worker
        if old is None:
            old = self._disconnect_current()
        if self._source == SOURCE_LOCAL:
            # A LOCAL pane reads the OS disk and NOTHING else (LOCAL_PANE.md §1), however often the
            # session re-binds its transport: the container's worker never lands on this pane.
            new_worker = self._ensure_local_provider()
        elif self._elevated_provider is not None:
            # The same rule for the ELEVATED pane (ELEVATED_PANE.md §1): its provider is the
            # client of another user, and the session's transport never lands on it.
            new_worker = self._elevated_provider
        self._disconnect_worker(old)
        self._drop_search()   # a search run belongs to ONE provider: a rebind DROPS it
        self._transfer_tasks.clear()
        self._own_transfers.clear()
        # v1.13: an archive read rides ONE provider as well — the spool it was downloading is
        # dropped by the ANSWER of that provider (`N131`), never under a download still writing.
        self._archive_forget_legs(old)
        # v1.13.1: a staged extraction the previous provider was delivering is dropped with it.
        self._drop_staged_all()
        # v1.3.3.2: the operation answers and the pre-flight listings belong to the transport asked.
        self._op_tasks.clear()
        self._pending_batches.clear()
        # v1.7.3: the dropped rows waiting for a listing belong to ONE transport as well.
        self._pending_drops.clear()
        # v1.6.3: the address bar's tasks and the completer's listings belong to ONE
        # transport as well (a normalize of the previous server must not navigate THIS one).
        self._normalize_tasks.clear()
        self._completer_lists.clear()
        self._completer_dir = None
        # v1.7rc2: the batch bookkeeping belongs to ONE transport as well (an answer of
        # the previous server must not be counted into a batch of this one).
        self._op_batches.clear()
        self._op_targets.clear()
        self._batches.clear()
        self.path_completer_model.setStringList([])
        # v1.3.1.1: the previewability facts belong to ONE transport/session — a new worker starts
        # with a clean listing.
        self._blocked.clear()
        self.btn_cancel.setEnabled(False)

        if new_worker is None:
            self._waiting = True
            self._bound_provider = None
            self._current_dir = self.paths.root()
            self._pending_lists.clear()
            self.tree.clear()
            self._up_item = None
            # v1.3.1: the preview belongs to the session's transport — the content
            # of a dead worker must not stay on the screen.
            self.close_viewer()
            self._set_path_text(_t("sftp.waiting_connection"))
            self.path_label.setReadOnly(True)
            for b in (self.btn_up, self.btn_refresh, self.btn_find, self.btn_upload,
                      self.btn_download):
                b.setEnabled(False)
            self._sync_source_availability()
            return

        self._waiting = False
        for name in WORKER_SIGNAL_NAMES:
            sig = getattr(new_worker, name, None)
            slot = getattr(self, "_on_" + name, None)
            if sig is None or slot is None:
                continue
            sig.connect(slot)
        self._bound_provider = new_worker
        self._sync_transfer_availability()
        self.path_label.setReadOnly(False)
        self._sync_source_availability()
        # v1.7.3: the FIRST transport of this pane opens the directory the server was
        # left in (ONE per-server key, a HINT): the answer may be a refusal, and `_on_task_error`
        # then says so and falls back to the shipped opening rule.
        start = self._current_dir
        try:
            hint = "" if self._restored else self._container.remembered_dir()
        except (AttributeError, RuntimeError):
            hint = ""   # a foreign container without the memory — the shipped opening rule
        if hint:
            self._restored = True
            self._restore_dir = hint
            start = hint
        self._relist(start)

    def _disconnect_worker(self, worker):
        """Drop this pane's slots from the provider it is REALLY bound to (idempotent).

        `_bound_provider` is the ONE record — a receiver-wide `disconnect` is a TypeError anyway.
        """
        if worker is None or worker is not self._bound_provider:
            return
        self._bound_provider = None
        # A QUEUED emission of the provider just left survives the disconnect (Qt cancels no posted
        # call) and task ids are per provider: the late answer would pop the new provider's entry.
        try:
            QCoreApplication.removePostedEvents(self, QEvent.Type.MetaCall)
        except (RuntimeError, TypeError):  # noqa: BLE001 — teardown of a dead object: no event loop yet
            pass  # no event loop yet (a bare construction) — nothing is queued anyway
        for name in WORKER_SIGNAL_NAMES:
            sig = getattr(worker, name, None)
            slot = getattr(self, "_on_" + name, None)
            if sig is None or slot is None:
                continue
            try:
                sig.disconnect(slot)
            except (TypeError, RuntimeError):  # noqa: BLE001 — teardown of a dead object: the worker is already gone
                pass  # no connection existed / the worker is already gone

    def _disconnect_current(self):
        """The provider this pane is REALLY bound to — read BEFORE a source change (v1.7.4rc1).

        The shipped `worker` property answers the container's transport whatever the source, so
        a local pane needs this to find the object it must disconnect from.
        """
        return self.provider

    def _ensure_local_provider(self):
        """The pane's OWN provider, created once and kept for the pane's whole life.

        The thread starts with the first Local switch (a pane that never goes local costs no
        thread at all) and lives until `release()`: a switch back and forth therefore keeps the
        local directory, the listing and the costs of nothing.
        """
        if self._local_provider is None:
            self._local_provider = local_fs.LocalFsWorker(root=self.paths.root(), parent=self)
            self._local_provider.start()
        return self._local_provider

    def shutdown_provider(self):
        """Stop the pane's local provider (the pane is going away). Never raises.

        A thread that outlives its wait budget is registered as an ORPHAN instead of being left
        to GC (`AGENTS.md` §4.8); the shipped worker of the session belongs to the page and is
        NOT touched here.
        """
        provider = self._local_provider
        self._local_provider = None
        if provider is None:
            return
        try:
            provider.shutdown(local_fs.LOCAL_SHUTDOWN_WAIT_MS)
        except Exception:  # noqa: BLE001 — teardown robustness
            pass
        try:
            if provider.isRunning():
                local_fs.register_orphan_local_provider(provider)
        except RuntimeError:
            pass   # the C++ object is already gone

    def set_source(self, source: str, notify: bool = True) -> bool:
        """Switch this pane's DATA SOURCE and re-bind its provider; False — the switch was refused.

        The switch goes through the SAME `bind_worker()` path a new connection takes, and a refusal
        is SAID with `sftp.local.unavailable` — never a silent no-op. `SOURCE_ELEVATED` is the
        CLIENT's token and not a data source (`ELEVATED_PANE.md` §1): it is delegated to the
        elevation cluster, and the data source below stays the shipped pair.
        """
        token = str(source or "")
        if token == SOURCE_ELEVATED:
            return bool(self.begin_elevation(notify=notify))
        target = SOURCE_LOCAL if token == SOURCE_LOCAL else SOURCE_REMOTE
        if self._elevated_provider is not None or self._elevation_pending:
            # A switch AWAY from the elevated source drops the elevation first (its provider and
            # its client are not the session's), then continues on the shipped path.
            return bool(self.leave_elevation(target, notify=notify))
        if target == self._source:
            self._sync_source_availability()
            return True
        allowed = True
        can_use = getattr(self._container, "can_use_local", None)
        if target == SOURCE_LOCAL and callable(can_use):
            allowed = bool(can_use(self))
        if not allowed:
            if notify:
                self.message.emit(_t(LOCAL_UNAVAILABLE_HINT))
            self._sync_source_availability()
            return False
        old = self._disconnect_current()
        # The directory belongs to the SOURCE (LOCAL_PANE.md §4): the OS look this pane already
        # had survives a round trip, while the way back is the session's opening rule — never the
        # other dialect's path, and never the per-server memory on the OS disk.
        if self._source == SOURCE_LOCAL and self._current_dir:
            self._local_dir = self._current_dir
        self._source = target
        self._current_dir = self._local_dir if target == SOURCE_LOCAL and self._local_dir \
            else self.paths.root()
        self._restored = target == SOURCE_LOCAL
        # v1.7.5: the header line names the SOURCE — it moves with the switch, while the ADDRESS BAR
        # keeps the shipped wording (the current directory; `bind_worker` writes the waiting line
        # when there is no transport), so "This computer" never lands in a path.
        self._sync_header()
        self._set_path_text(self._current_dir)
        # The way BACK re-binds the SESSION's transport (a remote pane IS the session's tree,
        # §1): without it the pane would sit in the "waiting" state with an empty listing.
        self.bind_worker(old, None if target == SOURCE_LOCAL else self.worker, source=target)
        self._sync_source_availability()
        return True

    def _on_source_switch(self, source: str):
        """The switch widget asked for a source: try it and put the control back on a refusal."""
        if not self.set_source(source):
            self._sync_source_availability()

    def _sync_source_availability(self):
        """Show the pane's source on its switch and say whether it may be switched at all.

        The LOCAL and the ELEVATED sources are refused for the FIRST pane and while the container
        holds ONE pane (`LOCAL_PANE.md` §4, `ELEVATED_PANE.md` §4): the commander is what makes "the
        other side" a concept. The switch itself stays visible in the shipped look — it is the
        pane's own control — and is simply not offered until it can do something.
        """
        switch = getattr(self, "source_switch", None)
        if switch is None:
            return
        enabled = bool(getattr(self, "_secondary", False))
        available = True
        can_use = getattr(self._container, "can_use_local", None)
        if callable(can_use):
            try:
                available = bool(can_use(self))
            except (RuntimeError, AttributeError):
                available = True
        _sync_source_switch(switch, self._switch_state(), enabled=enabled, available=available)

    def _sync_transfer_availability(self):
        """Enable the shared row for a bound provider (v1.7.4rc2: a local pane transfers too).

        The row follows the PROVIDER and not the source: both panes move bytes now — a remote one
        through the session's transport, a local one through its own engine (LOCAL_PANE.md §5/§6) —
        and a pane with no provider keeps the shipped "waiting" row; the search needs one too.
        """
        bound = not self._waiting and self.provider is not None
        try:
            self.btn_up.setEnabled(bound)
            self.btn_refresh.setEnabled(bound)
            self.btn_find.setEnabled(bound)
            self.btn_upload.setEnabled(bound)
            self.btn_download.setEnabled(bound)
        except RuntimeError:
            pass  # Qt teardown — the row is already gone

    def release(self):
        """Detach the pane: unbind the provider, stop a local or an ELEVATED one, drop the preview."""
        self._archive_forget_legs()   # `N131`: the slots go with the pane — no answer can drop it
        self._disconnect_worker(self._disconnect_current())
        self.shutdown_elevated()
        self.shutdown_provider()
        self._drop_staged_all()
        self.close_viewer()

    # ── v1.3.3.1: live i18n — re-text on a language switch ──

    def refresh_theme(self):
        """v1.4.3: re-apply the theme to this pane's own labels.

        Both label styles come from the ONE registry (`_apply_status_style`), so
        the switch is the same call the constructor made. Never raises.

        v1.4.7: the syntax colours are read LIVE from the active `Theme` by the
        highlighter, but the formats APPLIED to the visible blocks are values — so it
        is asked to drop them and repaint the window.

        v1.7rc1: the ACTIVE-pane ring is a stylesheet — re-applied here as well.
        """
        for widget in (getattr(self, "path_label", None),
                       getattr(self, "viewer_label", None),
                       getattr(self, "archive_label", None),
                       getattr(self, "hints_label", None),
                       getattr(self, "header_label", None)):
            if widget is None:
                continue
            try:
                _apply_status_style(widget, "status.sftp_row")
            except RuntimeError:
                continue  # Qt teardown — this label is already destroyed
        switch = getattr(self, "source_switch", None)
        if switch is not None:
            try:
                _apply_status_style(switch.lbl, "status.sftp_row")
                switch.refresh_theme()
            except (RuntimeError, AttributeError):
                pass  # Qt teardown — the switch is already gone
        if self._ring is not None:
            try:
                self._ring.refresh_theme()
            except RuntimeError:
                pass  # Qt teardown — the tree is already destroyed
        if self._highlighter is not None:
            try:
                self._highlighter.refresh_theme()
            except RuntimeError:
                pass  # Qt teardown — the document is already gone
        self._refresh_viewer_verbs()   # v1.14.1: the find card and the background chip

    def retranslate(self):
        """v1.3.3.1: re-text the pane's own strings in the current language.

        Every string already has an i18n key: the six buttons (the search one with its own
        tooltip), the three column headers, the viewer's close tooltip and the row tooltips.
        The module translator (`i18n.t`) is looked up at call time — no cache to invalidate.

        v1.3.3.2: the drag-out hint of the tree (the context menu is rebuilt on
        every right click and needs nothing here).

        v1.4.7: the heuristic-highlighting note of the viewer header
        (`sftp.viewer.syntax_heuristic`) is deliberately NOT re-texted here — like
        the path and the size it describes the file ON THE SCREEN; the next
        preview renders it in the active language.

        Deliberately NOT touched: the path label and the viewer header — they carry
        the CURRENT directory / file (data, not UI text); the "waiting connection"
        state is re-texted by `bind_worker(None)` on the next call. Never raises —
        the dead-C++-object discipline of every container method.
        """
        try:
            self.btn_up.setText(_t("sftp.up"))
            self.btn_refresh.setText(_t("sftp.refresh"))
            self.btn_find.setText(_t("sftp.search.row"))
            self.btn_find.setToolTip(_t("sftp.search.tooltip"))
            self.btn_upload.setText(_t("sftp.upload"))
            self.btn_download.setText(_t("sftp.download"))
            self.btn_cancel.setText(_t("sftp.cancel"))
            self._retranslate_viewer_verbs()   # v1.14.1: the find bar and the background chip
            self.tree.setHeaderLabels([_t("sftp.column_name"), _t("sftp.column_size"),
                                       _t("sftp.column_modified")])
            self.tree.setToolTip(_t("sftp.drag_hint"))
            self.btn_viewer_close.setToolTip(_t("sftp.viewer.close_tooltip"))
            # v1.13: the archive panel's own chrome — it exists only after the first `Open archive`
            # (the header LINE describes the open archive, so it is re-rendered by the next open).
            if getattr(self, "archive_panel", None) is not None:
                self.archive_tree.setHeaderLabels([_t("sftp.column_name"), _t("sftp.column_size"),
                                                   _t("sftp.column_modified")])
                self.btn_archive_close.setToolTip(_t("sftp.viewer.close_tooltip"))
            # v1.6.3: the address bar's placeholder.
            self.path_label.setPlaceholderText(_t("sftp.path_placeholder"))
            # v1.7.4rc1: the source switch of the pane (its label, its two buttons and the
            # availability tooltip) is UI text like every other row of this bar.
            switch = getattr(self, "source_switch", None)
            if switch is not None:
                switch.retranslate()
                self._sync_source_availability()
            # v1.7rc3: the hint row of the SECOND pane (five `sftp.hint.*` keys + the pane
            # toggle, the mark key and the open key) — re-read in the active language. The
            # row is re-elided by the layout on the next pass, so nothing else is needed.
            self._sync_secondary_ui()
            # v1.7.5: the SOURCE header line — its local wording is the shipped key, and an alias
            # is data that is simply put back unchanged (never translated).
            self._sync_header()
            # The row markers carry the refusal text in the tooltip — re-text the
            # rows of the CURRENT listing that are really marked (the facts of this
            # session; the marker itself is re-applied by the next listing).
            for path, reason in list(getattr(self, "_blocked", {}).items()):
                if not reason:
                    continue
                for i in range(self.tree.topLevelItemCount()):
                    item = self.tree.topLevelItem(i)
                    if item.data(0, self.PATH_ROLE) == path:
                        item.setToolTip(0, self._blocked_tooltip(reason))
                        break
        except RuntimeError:
            pass  # the C++ object was already destroyed (a close race)

    # ── the file operations the row context menu fires ───────────────

    def _op_new_folder(self):
        """New folder in the CURRENT directory (mkdir through THIS pane's provider queue)."""
        if self._refuse_elevated_write() or self._refuse_without_provider():
            return
        name = self._prompt_name(_t("sftp.op.new_folder"))
        if not name:
            return
        self._queue_op(self.provider.queue_mkdir(self._current_dir, name), KIND_MKDIR)

    def _op_rename(self, item):
        """Rename a row inside its own directory (only the NAME changes)."""
        if self._refuse_elevated_write() or self._refuse_without_provider():
            return
        path = item.data(0, self.PATH_ROLE)
        if not path:
            return
        current = self.paths.basename(path)
        name = self._prompt_name(_t("sftp.op.rename"), current)
        if not name or name == current:
            return   # cancelled, or the name did not change — nothing to do
        self._queue_op(self.provider.queue_rename(path, name), KIND_RENAME)

    def _op_delete(self, item):
        """Delete a row — a confirmation first (QMessageBox — a module attribute).

        A directory is removed with rmdir: a NON-EMPTY one reports the provider's error (a
        recursive delete is not in this version). A LOCAL row goes to the OS TRASH when the platform
        has a backend (`trash_backend()`), and the question says which really happens; without one
        the permanent delete keeps its shipped warning. v1.8: an ELEVATED pane refuses first.
        """
        if self._refuse_elevated_write() or self._refuse_without_provider():
            return
        path = item.data(0, self.PATH_ROLE)
        if not path:
            return
        is_dir = bool(item.data(0, self.ISDIR_ROLE))
        key, backend = self._delete_plan()
        box = QMessageBox   # the monkeypatch STAB.QMessageBox works in the tests
        reply = box.question(
            self, _t("sftp.op.delete"),
            _t(key, name=self.paths.basename(path)),
            box.Yes | box.No, box.No)
        if reply != box.Yes:
            return
        self._queue_op(self._delete_queue(path, is_dir, backend),
                       KIND_TRASH if backend else KIND_DELETE)

    def _op_copy_path(self, item):
        """Copy the REMOTE path of the row to the clipboard (never a URL)."""
        path = item.data(0, self.PATH_ROLE)
        if not path:
            return
        try:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(str(path))
        except Exception:   # noqa: BLE001 — the clipboard is not critical
            pass
        self.message.emit(_t("sftp.op.path_copied"))

    def _queue_op(self, task_id, kind: str):
        """Remember an operation task: its answer refreshes the listing (task_done)
        or reports a message (task_error)."""
        if task_id is not None:
            self._op_tasks[task_id] = kind


class SftpTab(SftpContainerPanesMixin, SftpContainerSessionMixin, SftpContainerViewerMixin,
              QWidget, sftp_extract.SftpExtractMixin):
    """The "Files" tab: a container of 1–2 directory PANES over the queue (v1.7rc1).

    The shipped single-listing tab is the ONE-pane case of this container: the pane holds the widgets
    and the listing state, the container holds the worker binding, the session's "follow the shell's
    directory" switch, the pane splitter, the ACTIVE pane and the persisted mode. A shipped attribute
    read (`tab.tree`, `tab._blocked`, `tab._relist()`) resolves on the ACTIVE pane.

    The container's clusters live in `sftp_container_panes.py` (the panes, the Commander, the ACTIVE
    pane and the sources), `sftp_container_session.py` (the worker and transport bindings, the dirs
    memory, the follow and the relay) and `sftp_container_viewer.py` (the ONE preview slot, the live
    viewer settings, the reader's background walk and the `Network ▸` row). This class keeps the
    assembly, the ONE teardown, the drag forwarding and the `__getattr__` / `__setattr__` pair — the
    pair stays HERE, last in the MRO, because it forwards a pane-owned name to the ACTIVE pane.
    """

    PATH_ROLE = _SftpPane.PATH_ROLE       # the pane's row roles (class-level compatibility)
    ISDIR_ROLE = _SftpPane.ISDIR_ROLE
    SIZE_ROLE = _SftpPane.SIZE_ROLE
    MTIME_ROLE = _SftpPane.MTIME_ROLE

    VIEWER_TREE_SHARE = _SftpPane.VIEWER_TREE_SHARE
    VIEWER_LAZY_MARGIN = _SftpPane.VIEWER_LAZY_MARGIN

    #: The pane-owned state the container FORWARDS to the ACTIVE pane: a name in this set is the
    #: PANE's bookkeeping (a test writes `tab._blocked = {…}` and reads it back from the pane that
    #: really holds it), everything else on the tab address is the container's.
    PANE_STATE = frozenset({
        "_current_dir", "_pending_lists", "_transfer_tasks", "_own_transfers", "_up_item",
        "_read_tasks", "_last_read", "_viewer_encoding", "_highlighter", "_viewer_language",
        "_highlight_range", "_blocked", "_blocked_icon_cache", "_op_tasks",
        "_pending_batches", "_drag_source", "_normalize_tasks", "_completer_lists",
        "_completer_dir", "_op_batches", "_batches", "_batch_seq", "_pending_drops",
        # the listing's sort and the reader's ceiling / encoding / preview path (v1.7.5, v1.9.3),
        # v1.13.4.3's ARCHIVE view, v1.13.6.2's SEARCH run and v1.14.1's find state + hue
        "_sort_column", "_sort_desc", "_viewer_cap", "_viewer_encoding_choice", "_viewer_path",
        "_archive", "_archive_open", "_archive_tasks", "_archive_dropped", "_archive_legs",
        "_search_state", "_search_open", "_search_list_tasks", "_search_read_tasks",
        "_viewer_find_matches", "_viewer_find_current", "_viewer_find_query", "_viewer_background",
    })

    # Local hints in the window's status bar (waiting for connection, no selection).
    message = Signal(str)

    # v1.6.3: the user switched the cwd follow. The TAB only reports it — the session installs the
    # hook, applies it live and persists the `terminal_follow_cwd` key (a SESSION state, not a view).
    follow_cwd_changed = Signal(bool)

    # The drag-payload helper of the pane, kept on the CLASS for the shipped suite
    # (`SftpTab._local_files(mime)` — a class-level read, which `__getattr__` cannot serve).
    _local_files = staticmethod(local_files)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        #: v1.8: the session's live `paramiko.Transport`, published by the page (`set_transport`)
        #: because the elevated channel rides it (`ELEVATED_PANE.md` §2).
        self._transport = None
        self._released = False
        self._panes = []
        self._pane_b = None
        self._active_pane = None
        self._commander = False
        self._commander_ratio = COMMANDER_RATIO_DEFAULT
        # v1.6.3/v1.7rc1: the follow state of the SESSION — the checkbox is a VIEW of it and
        # lives on the container (one OSC 7 report, one answer).
        self._follow_cwd = False
        # v1.7.3: the session's identity and the live sends. The KEY is the `history_key()` of the
        # server (the per-server memory uses it too), the label/host/port are what `Send to…`
        # prints and what decides the SAME-host path; `_sends` holds ONE send per TARGET session.
        self._session_key = ""
        self._session_label = ""
        self._session_host = ""
        self._session_port = None
        #: v1.7.5: the login user — the `user@host` fallback of a pane's SOURCE header line.
        self._session_user = ""
        #: v1.14.1: the node's LIVE `ServerData` — the kernel gate of the reader's `Network ▸` row.
        self._session_data = None
        self._sends = {}
        # v1.7.3: the per-server directory memory — the map read at construction (so a pane can
        # restore a directory before anybody navigates) and the entries THIS container really
        # moved, which are the ones its own write merges into the live config.
        self._dirs = load_remembered_dirs()
        self._dirs_touched = {}
        self._extract_provider = None   # v1.13.1: built on the first `Extract` (`sftp_extract`)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # v1.6.3: "follow the shell's directory" — the OSC 7 switch of THIS
        # session. It is a SESSION state: the page installs the hook and persists the key, and
        # the switch belongs to the CONTAINER (v1.7rc1) so the two-pane mode cannot offer two
        # answers to the one OSC 7 report the session receives.
        self.chk_follow_cwd = QCheckBox(_t("sftp.follow_cwd"))
        self.chk_follow_cwd.setToolTip(_t("sftp.follow_cwd_tooltip"))
        self.chk_follow_cwd.setEnabled(False)   # until a transport exists
        self.chk_follow_cwd.toggled.connect(self._on_follow_toggled)
        outer.addWidget(self.chk_follow_cwd)

        # The panes: ONE pane is the shipped look, TWO are the Files Commander. The splitter
        # is present in both cases (a QSplitter with a single member draws no handle), so the
        # refactor has ONE code path.
        self.pane_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.pane_splitter.setChildrenCollapsible(False)
        self.pane_splitter.splitterMoved.connect(self._on_pane_splitter_moved)
        outer.addWidget(self.pane_splitter, 1)

        # v1.2.8/v1.7rc1: a drop that misses every pane (the follow switch, the splitter
        # handle) is still the tab's — the container forwards it to the ACTIVE pane, exactly
        # the way the shipped single-pane tab handled a drop on any of its children.
        self.setAcceptDrops(True)
        self.chk_follow_cwd.installEventFilter(self)

        pane_a = self._new_pane()
        self._active_pane = pane_a

        settings = load_commander_settings()
        self._commander_ratio = settings["ratio"]
        if settings["commander"]:
            # The mode the user left behind is restored — through the SAME path the action
            # uses, so the panes, the ratio and the persisted state cannot diverge.
            self.set_commander(True)

    # ── the pane list and the ACTIVE pane ────────────────────────────────

    # ── the ONE teardown door (the page's idempotent `shutdown()`) ──────

    def release(self):
        """The container is going away: stop EVERY pane's provider and drop its preview.

        The tab's ONE teardown door (the page's idempotent `shutdown()` calls it, and so does a
        pane that leaves): a LOCAL pane owns a QThread of its own (`LOCAL_PANE.md` §1), and a
        thread that is still running when the widget tree dies takes the process with it
        (AGENTS.md §4.8). Idempotent, never raises, and the SESSION's worker is NOT touched.
        """
        if self._released:
            return
        self._released = True
        self._release_extracts()
        for pane in list(self._panes):
            try:
                self._close_viewer_of(pane)
            except Exception:  # noqa: BLE001 — teardown robustness
                pass
            try:
                pane.release()
            except Exception:  # noqa: BLE001 — teardown robustness
                pass

    # ── v1.3.3.1: live i18n — the walk over BOTH panes ──

    def retranslate(self):
        """v1.3.3.1: re-text the container and EVERY pane in the current language.

        The container owns the follow switch (one label + one tooltip) and walks its panes,
        so a language switch re-texts the second pane as well. Never raises.
        """
        try:
            self.chk_follow_cwd.setText(_t("sftp.follow_cwd"))
            self.chk_follow_cwd.setToolTip(_t("sftp.follow_cwd_tooltip"))
        except RuntimeError:
            pass  # Qt teardown — the switch is already destroyed
        for pane in list(self._panes):
            try:
                pane.retranslate()
            except RuntimeError:
                pass  # Qt teardown — the pane is already destroyed

    def refresh_theme(self):
        """v1.4.3: re-apply the theme to the container and EVERY pane. Never raises."""
        for pane in list(self._panes):
            hook = getattr(pane, "refresh_theme", None)
            if not callable(hook):
                continue
            try:
                hook()
            except RuntimeError:
                pass  # Qt teardown — the pane is already destroyed

    def close_viewer(self):
        """v1.3.1: close the preview of EVERY pane (the page teardown path). Never raises."""
        for pane in list(self._panes):
            try:
                pane.close_viewer()
            except RuntimeError:
                pass  # Qt teardown — the pane is already destroyed

    def resizeEvent(self, event):
        """v1.7rc1: a resize re-applies the pane proportion (the split's rule)."""
        super().resizeEvent(event)
        if self._commander:
            self._apply_commander_sizes()

    def _on_pane_splitter_moved(self, _pos=None, _index=None):
        """The user dragged the pane divider — the new proportion becomes THE ratio."""
        self._on_commander_moved()

    # ── D&D: the CONTAINER's own surface (a drag that misses every pane) ──

    def _pane_for_widget(self, obj):
        """The pane a widget belongs to; the container's OWN chrome answers the ACTIVE pane.

        `__getattr__` cannot serve the drag/filter family: `dragEnterEvent`, `dropEvent` and
        `eventFilter` exist on QWidget itself, so an ordinary lookup finds the (empty) base
        implementation and never reaches the pane. The container therefore DELEGATES them —
        and it resolves the pane by ANCESTRY, which is what keeps the shipped test seam
        (`tab.dropEvent(ev)`, `tab.eventFilter(tab.tree.viewport(), ev)`) working.
        """
        for pane in list(self._panes):
            try:
                if obj is pane or pane.isAncestorOf(obj):
                    return pane
            except RuntimeError:
                continue  # Qt teardown — the pane is already destroyed
        return self._active_pane

    def eventFilter(self, obj, event):
        """Forward a child's event to the pane it belongs to (the shipped seam)."""
        pane = self._pane_for_widget(obj)
        if pane is None:
            return False
        try:
            return bool(pane.eventFilter(obj, event))
        except RuntimeError:
            return False  # Qt teardown — nothing to forward to

    def _pane_under_drag(self, event):
        """The pane the cursor is really OVER (None — nobody is under it).

        The parent chain is not the answer: the v1.7.1 Files panel borrows the whole widget and a
        Commander borrows its sibling's viewer, so the target is resolved from the WIDGET UNDER THE
        CURSOR first and only then by ancestry (`_pane_for_widget` as the fallback). Never raises.
        """
        try:
            try:
                point = event.globalPosition().toPoint()
            except AttributeError:   # an older event object without globalPosition()
                point = event.globalPos()
            widget = QApplication.widgetAt(point)
        except (RuntimeError, AttributeError, TypeError):
            widget = None
        hops = 0
        while widget is not None and hops < 32:
            for pane in list(self._panes):
                if widget is pane:
                    return pane
            try:
                widget = widget.parentWidget()
            except RuntimeError:
                break
            hops += 1
        return None

    def _forward_drag(self, event, name: str):
        """Deliver a drag event that reached the CONTAINER to the pane UNDER THE CURSOR."""
        pane = self._pane_under_drag(event) or self._pane_for_widget(self._drag_source or self)
        if pane is None:
            return
        pane._drag_source = pane
        try:
            getattr(pane, name)(event)
        finally:
            pane._drag_source = None

    def dragEnterEvent(self, event):
        """A drag over the tab's own chrome (the follow switch, the splitter handle)."""
        self._forward_drag(event, "dragEnterEvent")

    def dragMoveEvent(self, event):
        """Same answer as dragEnter — otherwise Qt resets the action before Drop."""
        self._forward_drag(event, "dragMoveEvent")

    def dropEvent(self, event):
        """A drop on the tab's own chrome lands in the ACTIVE pane's current directory."""
        self._forward_drag(event, "dropEvent")

    # ── The shipped single-pane surface (resolved on the ACTIVE pane) ────

    def __getattr__(self, name):
        """Forward an unknown attribute to the ACTIVE pane (the shipped tab surface).

        `tab.tree`, `tab.path_label`, `tab._relist(...)`, `tab._blocked` — every name the
        page, the window or a test reads from the shipped single-pane tab resolves on the
        pane that really owns it. Container attributes and methods win by construction
        (`__getattr__` runs only when the ordinary lookup fails), and a name NOBODY owns
        still raises `AttributeError`, so `hasattr()` keeps answering honestly.
        """
        pane = self.__dict__.get("_active_pane")
        if pane is not None:
            try:
                return getattr(pane, name)
            except AttributeError:
                pass
        raise AttributeError(name)

    def __setattr__(self, name, value):
        """Write a PANE-owned name through to the ACTIVE pane (`PANE_STATE`).

        Without it `tab._blocked = {...}` would shadow the pane's dictionary on the
        container and the pane would keep answering from its own — a second truth. Every
        other name is the container's and lands here as usual.
        """
        if name in SftpTab.PANE_STATE:
            pane = self.__dict__.get("_active_pane")
            if pane is not None:
                setattr(pane, name, value)
                return
        super().__setattr__(name, value)


#: v1.14rc3: the names the split MOVED out of this module — DEFINED in `sftp_pane_widgets.py` /
#: `sftp_pane_helpers.py` and RE-EXPORTED here, because `modules.sftp_tab.<name>` is what a caller, the
#: page and the suite import (`AGENTS.md` §4.1). ONE manifest: a copy never stands in for the definition.
MOVED_NAMES = {
    # the four WIDGETS and the two functions beside them
    "_SftpRowItem": _SftpRowItem, "_SftpTree": _SftpTree, "_ButtonRow": _ButtonRow,
    "_SourceSwitch": _SourceSwitch, "_sync_source_switch": _sync_source_switch,
    "_apply_status_style": _apply_status_style,
    "BUTTONS_BAR_MIN_WIDTH": BUTTONS_BAR_MIN_WIDTH, "LOCAL_SOURCE_LABEL": LOCAL_SOURCE_LABEL,
    "LOCAL_UNAVAILABLE_HINT": LOCAL_UNAVAILABLE_HINT,
    "ELEVATED_SOURCE_LABEL": ELEVATED_SOURCE_LABEL,
    "ELEVATED_SOURCE_TOOLTIP": ELEVATED_SOURCE_TOOLTIP,
    # the pane's VOCABULARY: the row roles, the two sources and the drag payload
    "PATH_ROLE": PATH_ROLE, "ISDIR_ROLE": ISDIR_ROLE, "SIZE_ROLE": SIZE_ROLE,
    "MTIME_ROLE": MTIME_ROLE, "SOURCE_REMOTE": SOURCE_REMOTE, "SOURCE_LOCAL": SOURCE_LOCAL,
    "SOURCE_ELEVATED": SOURCE_ELEVATED, "PANE_SOURCES": PANE_SOURCES,
    "PANE_DRAG_MIME": PANE_DRAG_MIME,
    # the two path DIALECTS and the two refusal renderers
    "PathDialect": PathDialect, "POSIX_PATHS": POSIX_PATHS, "LOCAL_PATHS": LOCAL_PATHS,
    "dialect_for": dialect_for, "_win_standard_path": _win_standard_path,
    "local_error_text": local_error_text, "name_refusal_text": name_refusal_text,
    # the per-server directory memory and the Commander's own settings
    "DIRS_CONFIG": DIRS_CONFIG, "MAX_REMEMBERED_DIRS": MAX_REMEMBERED_DIRS,
    "load_remembered_dirs": load_remembered_dirs, "sanitize_dirs": sanitize_dirs,
    "remember_dir": remember_dir, "remembered_dir_for": remembered_dir_for,
    "COMMANDER_CONFIG_BOOL": COMMANDER_CONFIG_BOOL,
    "COMMANDER_CONFIG_RATIO": COMMANDER_CONFIG_RATIO,
    "COMMANDER_RATIO_DEFAULT": COMMANDER_RATIO_DEFAULT,
    "COMMANDER_RATIO_MIN": COMMANDER_RATIO_MIN, "COMMANDER_RATIO_MAX": COMMANDER_RATIO_MAX,
    "COMMANDER_MIN_PANE_PX": COMMANDER_MIN_PANE_PX,
    "load_commander_settings": load_commander_settings,
    # the cut fact, the row readers and the drag payload
    "read_was_truncated": read_was_truncated, "row_path": row_path, "row_name": row_name,
    "local_files": local_files, "pane_payload": pane_payload,
    # the listing's sort table the row class reads DOWNWARD (a shipped re-export of the waves)
    "SORT_COLUMNS": SORT_COLUMNS,
    # v1.14rc4: the container's own modules — DEFINED in `sftp_pane_assembly.py` /
    # `sftp_container_panes.py` / `..._session.py` / `..._viewer.py` and re-exported from this path
    "SftpPaneAssemblyMixin": SftpPaneAssemblyMixin,
    "SftpContainerPanesMixin": SftpContainerPanesMixin,
    "SftpContainerSessionMixin": SftpContainerSessionMixin,
    "SftpContainerViewerMixin": SftpContainerViewerMixin,
    # v1.14.1: the reader's own verbs — the find bar and the background chip
    "SftpViewerVerbsMixin": SftpViewerVerbsMixin,
}

# The LIVE-NAMESPACE SEAMS, declared once: every name a `sftp_pane_*.py` / `sftp_container_*.py` mixin
# resolves on THIS module at call time (`host_attr`). The declaration IS the seam — it keeps the name
# importable, it is the substitution point a suite patches, and it keeps a live seam from reading as a
# dead import (`AGENTS.md` §4.1, §4.3), so it comes LAST.
MODULE_FACADE_SEAMS = (
    # ── the pure readers the listing and the viewer resolve here (rc5 moved them to their own
    # ── module and re-exports them from this path, so the seam outlives the wave) ──
    format_size, format_mtime, preview_block_reason, decode_text, ask_conflict, read_was_truncated,
    clamp_viewer_max_bytes, save_viewer_wrap, save_viewer_encoding, normalize_viewer_encoding,
    save_viewer_background,   # v1.14.1: the reader's background key (the chip writes it)
    VIEWER_WRAP_CONFIG, VIEWER_ENCODING_CONFIG, VIEWER_ENCODING_DEFAULT, VIEWER_ENCODINGS,
    resolve_viewer_wrap, resolve_viewer_encoding,
    # ── the Qt surfaces the transfer and the drag & drop mixins resolve here: a suite substitutes
    # ── them on THIS module (`STAB.QFileDialog = <fake>` and its two siblings) ──
    QFileDialog, QInputDialog, QMenu,
    # ── the pane's source vocabulary, the batch's dispatcher and the listing's row class ──
    SOURCE_REMOTE, SOURCE_LOCAL, SOURCE_ELEVATED, PANE_SOURCES, dialect_for, local_error_text,
    name_refusal_text, local_files, pane_payload, _SftpRowItem, READ_ERROR_TOO_LARGE,
    # ── v1.14rc3: the status-label style the viewer and the archive/search panels resolve ──
    _apply_status_style,
    # ── v1.8: the ELEVATION seams the `sftp_pane_elevated.py` mixin resolves here (the handshake
    # ── class, the dialogue, the shipped engine over the elevated client and its orphan registry)
    ElevatedHandshake, ask_elevation, SftpWorker, register_orphan_sftp_worker,
    # ── the cluster facts the waves moved OUT of this module and RE-EXPORTS: the shipped surface a
    # ── caller and the suite read on `modules.sftp_tab` (`PANE_SHORTCUTS`, the cap's range, the
    # ── measured freeze slope, the tab-bar corner control) stays importable HERE ──
    PANE_SHORTCUTS, PANE_HINTS, HINT_SEPARATOR, VIEWER_MAX_BYTES_STEP, VIEWER_MAX_BYTES_WARN,
    VIEWER_FREEZE_MS_PER_MB, viewer_freeze_seconds,
    CommanderCorner,
    # ── v1.14rc4: what the container mixins and the pane's assembly resolve here — the pane class
    # ── the container instantiates, the widgets and the two readers of the assembly, the Commander
    # ── facts, the dirs memory and the relay's two doors ──
    _SftpPane, _SftpTree, _ButtonRow, _SourceSwitch, _sync_source_switch, SORT_DEFAULT_COLUMN,
    resolve_viewer_max_bytes, focus_ring, syntax,
    COMMANDER_RATIO_MIN, COMMANDER_RATIO_MAX, COMMANDER_MIN_PANE_PX, COMMANDER_CONFIG_BOOL,
    COMMANDER_CONFIG_RATIO, DIRS_CONFIG, load_remembered_dirs, remember_dir, remembered_dir_for,
)
