# -*- coding: utf-8 -*-
"""The standalone terminal surface — `main.py --only-terminal` (contract: `TERMINAL_STANDALONE.md`).

`StandaloneTerminalWindow` is the SHIPPED container (`modules/ssh_terminal.py`) with its two map hooks
answered by the surface instead of a map, and `StandaloneSurface` is that surface: it owns the project
file the `Servers` head lists (read by the PURE `storage/project.py` reader), the ONE connect door and
the bottom row's `Open project`. `start_standalone()` is the entry point `main.py` calls.

Nothing of the map is built here — no scene, no plugins, no probes, no autosave, no undo and no info
collection (the contract's OUT list is the specification). Mechanism — `DOCUMENTATION.md` §75;
rules — `AGENTS.md` §4.3.9; keys — §9 of the contract."""

import os

from PySide6.QtWidgets import QDialog, QFileDialog, QWidget

try:
    from ..dialogs.ssh_connect_dialog import SSHConnectDialog
    from ..models.server import is_unmanaged
    from ..storage.project import PROJECT_SUFFIXES, read_project_servers
except ImportError:  # flat launch from the project root
    from dialogs.ssh_connect_dialog import SSHConnectDialog
    from models.server import is_unmanaged
    from storage.project import PROJECT_SUFFIXES, read_project_servers

try:
    from .command_library import HEAD_SERVERS
    from .ssh_terminal import SSHTerminalWindow
    from .terminal_split import find_host_hook
except ImportError:  # flat launch from the project root
    from command_library import HEAD_SERVERS
    from ssh_terminal import SSHTerminalWindow
    from terminal_split import find_host_hook


#: `SSHConnectDialog` / `QFileDialog` are LIVE module attributes for the test seams (the
#: `command_library.QMessageBox` pattern): the suite substitutes them and drives the doors without a
#: network and without a modal dialog.
MODULE_FACADE_SEAMS = (SSHConnectDialog, QFileDialog)

_t_cache = None


def get_translator():
    """Safe i18n helper — returns cached translator or fallback."""
    global _t_cache
    if _t_cache is None:
        try:
            from i18n import t as _func
            _t_cache = lambda key, **kwargs: (
                _func(key, **kwargs) if kwargs else _func(key)
            )
        except Exception:
            _t_cache = lambda k, **kw: f"[{k}]"
    return _t_cache


def _log():
    """The app logger (lazy — a build without the logger keeps the surface working)."""
    try:
        from modules.logger import get_logger as _gl
        return _gl("modules.terminal_standalone")
    except Exception:
        return None


def project_filter_text() -> str:
    """The `Open project` file dialog's filter — the WORDS from i18n, the SUFFIXES from the code.

    The suffix list is declared ONCE (`storage/project.py`, the same tuple the map's drop gate reads),
    so a filter string can never drift from what the application really opens; the two labels come
    from `terminal.standalone.project_filter` / `.all_files` (`TERMINAL_STANDALONE.md` §9).
    """
    t = get_translator()
    patterns = " ".join(f"*{suffix}" for suffix in PROJECT_SUFFIXES)
    return f"{t('terminal.standalone.project_filter', patterns=patterns)};;{t('terminal.standalone.all_files')}"


class StandaloneTerminalWindow(SSHTerminalWindow):
    """The container of the standalone surface: the shipped window with the SURFACE's own hooks.

    A map-backed window asks its parent chain for `map_server_nodes()` and `_run_ssh_connect()`
    (`AGENTS.md` §4.1); this container answers the SAME two questions from the surface — 
    `project_nodes()` and `connect_server()` — so no map name is ever faked and the panel's contract
    (§4.3.8) is honoured unchanged. The profile manager keeps the SHIPPED hook name: it is an
    application-level door, not a map one. `ALLOWS_NO_SESSIONS` is True, so the container is born and
    stays EMPTY until a server is picked (`TERMINAL_STANDALONE.md` §6).
    """

    ALLOWS_NO_SESSIONS = True
    quit_on_close = True

    def __init__(self, parent=None):
        super().__init__(None, parent=parent)
        # The bottom row's FIRST control is `Open project` on this surface — the ONE door of §7.
        self.cmdlib_panel.set_project_door(self._panel_open_project)

    def _surface_hook(self, name):
        """A surface hook on the parent chain (`find_host_hook`, the §4.1 walk). Never raises."""
        try:
            return find_host_hook(self, name)
        except Exception:  # noqa: BLE001 — a broken chain is "nobody answers", never a crash
            return None

    def _panel_server_nodes(self):
        """The `Servers` head's source — the surface's project list (`None` while no project is open)."""
        hook = self._surface_hook("project_nodes")
        if hook is None:
            return None
        try:
            return hook()
        except Exception:  # noqa: BLE001 — a source that fails is an empty list, never a crash
            return None

    def _panel_connect_server(self, node) -> bool:
        """A click on a server row — the surface's connect door (`TERMINAL_STANDALONE.md` §8)."""
        hook = self._surface_hook("connect_server")
        if hook is None:
            return False
        try:
            return bool(hook(node))
        except Exception as e:  # noqa: BLE001 — a refused connect must not break the panel
            log = _log()
            if log is not None:
                log.warning(f"The standalone connect door failed: {e}")
            return False

    def _panel_open_project(self) -> bool:
        """The bottom row's first control — `Open project` (the contract's §7 door)."""
        hook = self._surface_hook("open_project")
        if hook is None:
            return False
        try:
            return bool(hook())
        except Exception as e:  # noqa: BLE001 — a door must never break the panel
            log = _log()
            if log is not None:
                log.warning(f"The Open project door failed: {e}")
            return False


class StandaloneSurface(QWidget):
    """The host of ONE standalone terminal window: the project's servers and the doors.

    It is the widget the container finds on its parent chain, so the panel's provider pair resolves to
    `project_nodes()` / `connect_server()` and the bottom row's second control resolves to
    `_open_profile_manager()` — the SHIPPED names, because those hooks are read by name (`§4.3.8`).
    The surface owns the loaded project (`project_path`, `servers`) and writes NOTHING to it.
    """

    def __init__(self, parent=None, window=None):
        super().__init__(parent)
        self._project_path = ""
        self._servers = []
        self._loaded = False
        self.window = window if window is not None else StandaloneTerminalWindow(self)

    # ── the source of the `Servers` head ─────────────────────────────────────

    def project_nodes(self):
        """The `Servers` head's provider — the loaded project's servers, in FILE order.

        `None` is the declared "nothing to list YET" (no project is open): the head stays INACTIVE and
        the panel explains itself inline. An EMPTY list is a real answer — a project file whose
        `servers` array is empty keeps the head usable and shows `terminal.cmdlib.project_empty`.
        """
        return list(self._servers) if self._loaded else None

    def project_path(self) -> str:
        """The file the list came from ("" — no project is open) — the surface's own memory."""
        return self._project_path

    def servers(self) -> list:
        """The loaded nodes (`ServerData`), a COPY — the surface keeps its own list."""
        return list(self._servers)

    # ── the doors ────────────────────────────────────────────────────────────

    def open_project(self, path: str = "") -> bool:
        """`Open project` — pick a project FILE and list its servers (`TERMINAL_STANDALONE.md` §7).

        A cancelled dialog changes NOTHING. A file that cannot be read answers ONE sentence and leaves
        the previous list ALONE (the surface is a reader: nothing here writes the file, §3).
        """
        t = get_translator()
        chosen = path or self._ask_project_path()
        if not chosen:
            return False
        try:
            servers = read_project_servers(chosen)
        except Exception as e:  # noqa: BLE001 — an unreadable file is a sentence, not a crash
            self._notify(t("terminal.standalone.project_failed",
                           name=os.path.basename(chosen), error=e))
            return False
        self._project_path = chosen
        self._servers = servers
        self._loaded = True
        self._refresh_servers()
        self._notify(t("terminal.standalone.project_opened",
                       name=os.path.basename(chosen), count=len(servers)))
        log = _log()
        if log is not None:
            log.info("Standalone project loaded", extra={"file": chosen, "servers": len(servers)})
        return True

    def connect_server(self, data) -> bool:
        """The ONE connect door of the surface — the unmanaged gate, the dialog, then the session.

        The order is the contract's (§8): an UNMANAGED node is refused BEFORE a dialog is built, the
        SHIPPED `SSHConnectDialog` collects the login, and the session joins this surface's window.
        The dialog's user / key / port are written to the in-memory node DIRECTLY — this surface has
        no undo stack — and the password falls back to the endpoint-bound keyring record.
        """
        if data is None:
            return False
        if is_unmanaged(data):
            self._notify(get_translator()("status.unmanaged_blocked"))
            return False
        if self.window is None:
            return False
        try:
            dlg = SSHConnectDialog(data, self.window)
        except Exception as e:  # noqa: BLE001 — a dialog that cannot be built opens no session
            log = _log()
            if log is not None:
                log.warning(f"The connect dialog could not be built: {e}")
            return False
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        self._apply_dialog_fields(data, dlg)
        password = str(dlg.password_edit.text()) or self._stored_password(data)
        self.window.add_session(data, password=password, initial_command="")
        self._notify(get_translator()("terminal.session_new_tab", alias=getattr(data, "alias", "")))
        return True

    def _open_profile_manager(self):
        """`Profiles` — the SHIPPED application-level door, under the SHIPPED hook name.

        `SSHTerminalWindow._panel_open_profiles()` looks this name up on the parent chain, so the
        standalone re-uses the dialog instead of growing a second one (`AGENTS.md` §4.3.8).
        """
        try:
            from ..dialogs.profile_manager_dialog import ProfileManagerDialog
        except ImportError:  # flat launch from the project root
            from dialogs.profile_manager_dialog import ProfileManagerDialog
        try:
            dlg = ProfileManagerDialog(self.window or self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._notify(get_translator()("status.profile_updated"))
        except Exception as e:  # noqa: BLE001 — a dialog must never break the surface
            log = _log()
            if log is not None:
                log.warning(f"The profile manager failed: {e}")

    # ── the pieces behind the doors ──────────────────────────────────────────

    def _ask_project_path(self) -> str:
        """The file dialog of `Open project` ("" — the user cancelled). Never raises."""
        start = os.path.dirname(self._project_path) if self._project_path else os.path.expanduser("~")
        try:
            path, _selected = QFileDialog.getOpenFileName(
                self.window or self, get_translator()("terminal.cmdlib.open_project"),
                start, project_filter_text())
        except Exception as e:  # noqa: BLE001 — a dialog that cannot be shown picks nothing
            log = _log()
            if log is not None:
                log.warning(f"The project file dialog failed: {e}")
            return ""
        return str(path or "")

    def _apply_dialog_fields(self, data, dlg):
        """Carry the dialog's user / key path / port onto the node — the map's edit, without undo.

        `_run_ssh_connect()` applies these through `CmdEditNodeData`; a surface that owns no document
        writes them directly and NEVER to the file (`TERMINAL_STANDALONE.md` §3, §8). The dialog OPENS
        prefilled with the node's own user / key path / port, so an untouched field carries the value
        the project file gave it and an emptied one writes what the user left — the map's own edit.
        """
        try:
            user = str(dlg.user_edit.text()).strip()
            key_path = str(dlg.key_path_edit.text()).strip()
            port = int(dlg.port_edit.value() or getattr(data, "ssh_port", 22) or 22)
        except (RuntimeError, AttributeError, TypeError, ValueError):
            return  # a foreign dialog in a test: nothing to carry over
        if user:
            data.user = user
        data.key_path = key_path
        data.ssh_port = port

    def _stored_password(self, data) -> str:
        """The endpoint-bound keyring record of this node ("" — nothing stored for THIS endpoint).

        The ONE read of the shipped credential store (`AGENTS.md` §4.4): the record is bound to the
        `user@host:port` it was saved for, so a foreign project's secret is never offered to a
        different endpoint — its own scope check answers `None` (`_quick_launch_command()` precedent).
        """
        try:
            from ..services.credential_manager import get_credential_manager, node_scope
        except ImportError:  # flat launch from the project root
            from services.credential_manager import get_credential_manager, node_scope
        try:
            return get_credential_manager().load_password(
                getattr(data, "id", ""), scope=node_scope(data)) or ""
        except Exception:  # noqa: BLE001 — an unavailable keyring is "nothing stored"
            return ""

    def _refresh_servers(self):
        """Re-read the provider into the panel — the ONE re-read of the `Servers` head."""
        window = self.window
        panel = getattr(window, "cmdlib_panel", None) if window is not None else None
        if panel is None:
            return
        try:
            panel.refresh_servers()
            panel.set_head(HEAD_SERVERS)
        except RuntimeError:
            pass  # Qt teardown — the panel is already gone

    def _notify(self, text: str, timeout_ms: int = 5000):
        """One sentence on the WINDOW's status line (the shipped surface of this container)."""
        if not text or self.window is None:
            return
        try:
            self.window.statusBar().showMessage(str(text), int(timeout_ms))
        except RuntimeError:
            pass  # Qt teardown — the status bar is already gone


def start_standalone(project: str = "") -> "StandaloneSurface":
    """Build the standalone surface, show its window and answer the surface (`--only-terminal`).

    The ONE entry point of the mode: `main.py` calls it instead of building a `MainWindow`, and closing
    the container ENDS the run (`quit_on_close` — a single-window application has nothing left to show
    once its window is gone). A `project` path is the API seam (the suite and a future subcommand) — the
    command line takes NO argument for the flag (`TERMINAL_STANDALONE.md` §1). The CALLER owns the answer
    and must hold it: the surface is a top-level widget, so a discarded reference lets Python collect the
    window before the loop runs.
    """
    surface = StandaloneSurface()
    surface.window.show()
    if project:
        surface.open_project(project)
    return surface
