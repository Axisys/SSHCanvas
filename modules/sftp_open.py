# -*- coding: utf-8 -*-
"""The SFTP channel opener — the bounded handshake OFF the GUI thread (AGENTS.md §4.8.1).

`open_sftp_session(transport, timeout)` is the whole sequence: `Transport.open_session(timeout=…)`
for the channel and `Channel.settimeout(…)` across `invoke_subsystem("sftp")` / `SFTPClient(chan)`
for the version read, CLEARED once the server answered so a transfer never inherits it — paramiko
bounds neither stage on its own. `SftpOpenHandshake` runs it on its own named `QThread` and answers
`ready()` / `failed(detail)`; the receiver TAKES the client through `take_client()`, so an answer
nobody received cannot leak a channel, and `register_orphan_sftp_open()` holds a thread that
outlived its wait budget (AGENTS.md §4.8). The ONE caller is `_ensure_sftp()` of the session page
(`modules/terminal_page_sftp.py`). Mechanism — `DOCUMENTATION.md` §14b, §64.
"""

from PySide6.QtCore import QThread, Signal

try:
    from .logger import get_logger
except ImportError:
    try:
        from modules.logger import get_logger
    except ImportError:  # pragma: no cover — a stripped build logs nowhere
        import logging

        def get_logger(name):  # noqa: N802 — the same signature
            return logging.getLogger(name)

try:  # the client is created through the MODULE attribute, so a suite substitutes it
    import paramiko
except ImportError:  # pragma: no cover — a build without the SSH library
    paramiko = None

log = get_logger(__name__)

#: The bound of BOTH stages paramiko leaves unbounded: the channel request (its default is
#: `Transport.channel_timeout`, 3600 s) and the SFTP version read (a `Channel.recv()` with no bound).
SFTP_OPEN_TIMEOUT_SEC = 20.0

#: The budget the session waits for a stuck open before the thread joins the orphan registry.
SFTP_OPEN_SHUTDOWN_WAIT_MS = 2500

#: How much of a failure's own text a refusal carries.
SFTP_OPEN_DETAIL_CHARS = 200


def sftp_client_class():
    """The paramiko `SFTPClient` — resolved at CALL time, so a suite substitutes the attribute."""
    return getattr(paramiko, "SFTPClient", None) if paramiko is not None else None


def short_detail(text, limit: int = SFTP_OPEN_DETAIL_CHARS) -> str:
    """PURE: ONE bounded line of a failure's own text — what a refusal may show about itself."""
    folded = " ".join(str(text or "").split())
    return folded[:limit]


def close_quiet(obj) -> bool:
    """Best-effort close of a channel or a client (never masks the real answer)."""
    if obj is None:
        return False
    try:
        obj.close()
        return True
    except Exception:  # noqa: BLE001 — a channel that is already gone is closed enough
        return False


def open_sftp_session(transport, timeout: float = SFTP_OPEN_TIMEOUT_SEC, on_channel=None):
    """The BOUNDED open of one SFTP channel: `(client, channel, detail)` — never raises.

    BOTH stages get a declared bound, because paramiko bounds neither: `open_session(timeout=…)`
    covers the channel request and `settimeout(…)` covers the version read inside
    `SFTPClient(channel)`. The timeout is CLEARED once the version answered, so a large transfer
    never inherits it. A failure closes the half-open channel and answers its own bounded text;
    `on_channel` publishes that channel the moment it exists, so a teardown can close it.
    """
    channel = None
    try:
        channel = transport.open_session(timeout=timeout)
        if channel is None:
            return None, None, "the server opened no session channel"
        if on_channel is not None:
            on_channel(channel)
        channel.settimeout(timeout)
        channel.invoke_subsystem("sftp")
        client_cls = sftp_client_class()
        if client_cls is None:
            raise RuntimeError("the SFTP client is unavailable")
        client = client_cls(channel)
    except Exception as exc:  # noqa: BLE001 — a refused open is an answer, never a traceback
        close_quiet(channel)
        return None, None, short_detail(exc)
    try:
        channel.settimeout(None)
    except Exception:  # noqa: BLE001 — a channel that cannot be re-armed costs only the bound
        pass
    return client, channel, ""


# ── Orphan registry (the `_orphan_handshakes` pattern of `modules/sftp_elevated.py`) ──
_orphan_opens = []


def register_orphan_sftp_open(handshake) -> None:
    """Hold a still-running opener until finished() (idempotent, detached from its parent)."""
    if handshake in _orphan_opens:
        return
    try:
        handshake.setParent(None)
    except RuntimeError:
        pass  # the C++ object is already gone
    _orphan_opens.append(handshake)

    def _drop(_=None, h=handshake):
        try:
            _orphan_opens.remove(h)
        except ValueError:
            pass  # already removed
    handshake.finished.connect(_drop)


class SftpOpenHandshake(QThread):
    """ONE thread: the bounded SFTP open of the session's OWN transport (`AGENTS.md` §4.8.1).

    `ready` carries NOTHING — the receiver takes the client through `take_client()`, so the
    ownership moves in ONE step and `close()` can drop what nobody took; `failed` carries the
    failure's own bounded text. Both are emitted ONCE, at the end of `run()`, and the session's
    transport is published for the caller that wires the answer to the Files surface.
    """

    ready = Signal()
    failed = Signal(str)

    def __init__(self, transport, timeout=None, parent=None):
        super().__init__(parent)
        # A managed QThread carries a NAME (`AGENTS.md` §4.8): a bare '' in Qt's abort message is a
        # thread that never went through a constructor.
        self.setObjectName("SftpOpenHandshake")
        self._transport = transport
        self._timeout = SFTP_OPEN_TIMEOUT_SEC if timeout is None else float(timeout)
        self._client = None
        self._channel = None
        self._cancel = False

    # ── Public API (GUI thread) ──────────────────────────────────────────

    @property
    def transport(self):
        """The transport this handshake was asked to open a channel on."""
        return self._transport

    @property
    def timeout(self) -> float:
        """The bound this handshake applies to BOTH stages."""
        return self._timeout

    def take_client(self):
        """Claim the client this handshake opened; None — nothing to claim (or already taken)."""
        client = self._client
        self._client = None
        return client

    def close(self):
        """Drop what this handshake opened (the session is going away). Never raises.

        Closing the CHANNEL is also what unblocks a version read that is still inside its bound; a
        channel that appears after the cancel is closed by `run()` instead.
        """
        self._cancel = True
        channel, self._channel = self._channel, None
        client, self._client = self._client, None
        close_quiet(client)
        close_quiet(channel)

    def shutdown(self, wait_ms: int = SFTP_OPEN_SHUTDOWN_WAIT_MS):
        """Cancel-free stop: wait ≤ wait_ms and register a stuck thread as an ORPHAN."""
        try:
            if self.isRunning():
                self.wait(wait_ms)
        except RuntimeError:
            return   # the C++ object is already gone
        if self.isRunning():
            register_orphan_sftp_open(self)

    # ── The open (worker thread) ─────────────────────────────────────────

    def run(self):
        client, channel, detail = open_sftp_session(self._transport, self._timeout,
                                                    on_channel=self._remember_channel)
        if client is None:
            self._emit(self.failed, detail)
            return
        if self._cancel:   # the session was torn down while the server was answering
            self._channel = None
            close_quiet(client)
            close_quiet(channel)
            return
        self._client = client   # handed over by `take_client()` — never by the emission
        self._emit(self.ready)

    def _remember_channel(self, channel):
        """Publish the channel the moment it exists, so a teardown can CLOSE it and unblock us."""
        self._channel = channel
        if self._cancel:
            close_quiet(channel)

    def _emit(self, signal, *args):
        """Emit with the teardown guard: a late emit without receivers is a safe no-op."""
        try:
            signal.emit(*args)
        except RuntimeError:
            pass
