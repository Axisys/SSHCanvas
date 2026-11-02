"""Background diagnostics off the GUI thread — ping, reverse DNS and the reachability report — in the
"module + callbacks" pattern (AGENTS.md §4.1; DOCUMENTATION.md §46).

`PingThread(host)` emits `finished_ping(ok, text)`, `ReverseDnsThread(host, parent=…)` emits
`resolved(name)`; MainWindow keeps the reference (`self._ping_thread` / `self._dns_thread`) and
connects with local closures, so a repeated request never clobbers a running one, and
`_shutdown_background_threads()` stops them with `stop()`/`wait()`. Neither has a `stop()`: with an
unreachable resolver it outlives the wait budget, so a survivor goes to the orphan registry
(`_orphan_threads` / `register_orphan_thread()`) — never a live QThread left to GC.
`ReachabilityThread` wraps the PURE probe of `services/reachability.py` off-thread; that module owns
the steps, the verdicts and the `(i18n key, params)` pairs, and this one re-exports them because it is
the GUI's live namespace. No i18n policy here, and no status is ever touched by a report."""
import platform
import subprocess
from typing import List

from PySide6.QtCore import QThread, Signal

try:  # the PURE half: the steps, the verdicts and the sentence parts (no Qt)
    from .reachability import (BANNER_BYTES, BANNER_MAX_CHARS, DNS_THREAD_NAME, KIND_BANNER_FOREIGN,
                               KIND_BANNER_SILENT, KIND_DNS_FAILED, KIND_DNS_TIMEOUT, KIND_OK,
                               KIND_STEP, KIND_TCP_FAILED, KIND_TCP_REFUSED, KIND_TCP_TIMEOUT,
                               PING_BUDGET_S, REPORT_KINDS, REPORT_STEP_ORDER, REPORT_TIMEOUT_S,
                               ReachabilityReport, diagnose_reachability, ping_once, report_parts,
                               resolve_host)
except ImportError:  # the package layout (sshmap.services.*)
    from services.reachability import (BANNER_BYTES, BANNER_MAX_CHARS, DNS_THREAD_NAME,
                                       KIND_BANNER_FOREIGN, KIND_BANNER_SILENT, KIND_DNS_FAILED,
                                       KIND_DNS_TIMEOUT, KIND_OK, KIND_STEP, KIND_TCP_FAILED,
                                       KIND_TCP_REFUSED, KIND_TCP_TIMEOUT, PING_BUDGET_S,
                                       REPORT_KINDS, REPORT_STEP_ORDER, REPORT_TIMEOUT_S,
                                       ReachabilityReport, diagnose_reachability, ping_once,
                                       report_parts, resolve_host)


# ── the orphan-thread registry for ping/DNS (the N4 pattern) ──────────────────────
# `PingThread` / `ReverseDnsThread` have NO stop(): on window close they are only waited
# for with a budget (`MainWindow._shutdown_background_threads`), and a live QThread with
# no strong referencing object must not be left to GC ("QThread: Destroyed while running").
# The registry holds such threads until `finished()` — `AGENTS.md` §4.3, `DOCUMENTATION.md` §64.
_orphan_threads: List["QThread"] = []


def register_orphan_thread(thread: "QThread"):
    """Hold a still-running ping/DNS/reachability/info thread until finished().

    The thread is DETACHED from its QObject parent FIRST: a reverse-DNS lookup or a collector is
    created under the window, the window dies, and a parented `QThread` is destroyed with it however
    firmly this registry holds the Python wrapper (N122 — the same reason
    `register_orphan_sftp_worker()` detaches). Idempotent; self-cleans on the finished() signal.
    """
    if thread not in _orphan_threads:
        try:
            thread.setParent(None)
        except RuntimeError:
            pass  # the C++ object is already gone
        _orphan_threads.append(thread)

        def _drop(_=None, t=thread):
            try:
                _orphan_threads.remove(t)
            except ValueError:  # noqa: BLE001 — best effort (declared): a double finished
                pass  # already removed (a double finished — does not happen in practice)
        thread.finished.connect(_drop)


class PingThread(QThread):
    """Ping a node in a separate thread without blocking the GUI.

    Windows: `ping -n 3`, POSIX: `ping -c 3`. The result — the finished_ping
    signal; interpretation (status bar / dialog) is left to the calling callback.
    """

    finished_ping = Signal(bool, str)

    def __init__(self, host):
        super().__init__()
        self._host = host

    def run(self):
        try:
            from i18n import t as _t
        except Exception:
            def _t(key, **kw):
                return key.format(**kw) if kw else key
        # Guard BEFORE the subprocess — the Windows ping does NOT support "--" (asymmetry of the
        # branches: the POSIX command below has it), so a host starting with "-" could be eaten as
        # a flag. Such a host is invalid as a DNS name anyway — refused WITHOUT launching a process.
        if isinstance(self._host, str) and self._host.startswith("-"):
            self.finished_ping.emit(False, _t("status.ping_failed", host=self._host))
            return
        count_flag = "-n" if platform.system() == "Windows" else "-c"
        # -w/-W — milliseconds on Windows, seconds on Linux; a 3 s timeout in both cases. On Linux
        # the "--" before the host, so a host of the form "-x" is not eaten as a flag.
        if platform.system() == "Windows":
            cmd = ["ping", count_flag, "3", "-w", "3000", self._host]
        else:
            cmd = ["ping", "-c", "3", "-W", "3", "--", self._host]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if platform.system() == "Windows" else 0)
            ok = proc.returncode == 0
            key = "status.ping_ok" if ok else "status.ping_failed"
            msg = _t(key, host=self._host)
            out = proc.stdout.decode(errors="replace")[-400:] if not ok else ""
            self.finished_ping.emit(ok, msg + ("\n" + out if out else ""))
        except Exception as exc:
            self.finished_ping.emit(False, _t("status.ping_failed", host=self._host)
                                    + f" ({exc})")


class ReverseDnsThread(QThread):
    """Reverse DNS outside the GUI thread.

    With an unreachable resolver gethostbyaddr freezes on the DNS timeout in the GUI thread; now —
    a separate thread, the resolved(name) signal. DNS did not return a name → name = the host itself
    (the callback copies it as-is).
    """

    resolved = Signal(str)

    def __init__(self, host_, parent=None):
        # parent — the QObject owner of the thread's C++ object (MainWindow passes self): while the
        # window is alive the thread cannot be destroyed by GC regardless of the Python references;
        # a thread that outlives the shutdown wait budget is registered in `_orphan_threads` above.
        super().__init__(parent)
        self._host = host_

    def run(self):
        import socket as _socket
        try:
            name = _socket.gethostbyaddr(self._host)[0]
        except Exception:
            name = self._host  # DNS did not return a name — copy the host itself
        self.resolved.emit(name)


class ReachabilityThread(QThread):
    """One reachability report on a worker thread.

    The report blocks on DNS/TCP/banner and may launch a `ping` process, so it never runs
    on the GUI thread (§4.8). One thread per request, owned by the window's registry (the
    `_ping_thread` pattern); `report_ready(server_id, ReachabilityReport)` carries the
    FACTS, and the window composes and routes the sentence.
    """

    report_ready = Signal(str, object)

    def __init__(self, server_id: str, host: str, port: int = 22,
                 timeout: float = REPORT_TIMEOUT_S, parent=None, **seams):
        super().__init__(parent)
        self._server_id = str(server_id)
        self._host = host
        self._port = port
        self._timeout = timeout
        self._seams = seams   # resolver / connector / pinger — the test seam

    def run(self):
        try:
            report = diagnose_reachability(self._host, self._port, self._timeout,
                                           **self._seams)
        except Exception as exc:  # noqa: BLE001 — a report must never kill the thread
            report = ReachabilityReport(host=str(self._host), port=int(self._port or 22),
                                        kind=KIND_TCP_FAILED, detail=str(exc))
        try:
            self.report_ready.emit(self._server_id, report)
        except RuntimeError:
            pass  # the receiver died with its window — the report is simply dropped
