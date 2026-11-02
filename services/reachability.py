# -*- coding: utf-8 -*-
"""The PURE half of the reachability report — DNS → TCP → SSH banner (→ ICMP), no Qt, no i18n.

`diagnose_reachability()` walks the steps the application already knows IN ORDER and names the FIRST
failure in its own words; `resolve_host()` / `ping_once()` are the two bounded OS calls and
`ReachabilityReport` / `report_parts()` give a caller its `(i18n key, params)` pairs. A red card
collapses refused / timeout / DNS into ONE `offline`, which is exactly the moment a user needs the
difference. `services/diagnostics.py` wraps this module in a QThread for the GUI; the headless surface
imports it directly (`AGENTS.md` §4.4, §4.35; mechanism — `DOCUMENTATION.md` §46).
"""
import platform
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field

REPORT_TIMEOUT_S = 3.0                 # a single step's budget (the probe's own 3 s)
PING_BUDGET_S = 4.0                    # the ICMP stage: 1 packet + a 4 s ceiling
BANNER_BYTES = 32                      # what a status probe reads (and what we read here)
BANNER_MAX_CHARS = 40                  # the banner text a sentence may quote
DNS_THREAD_NAME = "sshmap-dns-report"  # the daemon thread of a bounded lookup

#: The steps, in the order the report runs them (the acceptance of the task).
REPORT_STEP_ORDER = ("dns", "tcp", "banner", "ping")

#: The verdicts. `ok` — the host is an SSH server; everything else names the FIRST
#: failing step, and one `diagnose.<kind>` key is its sentence.
KIND_OK = "ok"
KIND_DNS_FAILED = "dns_failed"
KIND_DNS_TIMEOUT = "dns_timeout"
KIND_TCP_REFUSED = "tcp_refused"
KIND_TCP_TIMEOUT = "tcp_timeout"
KIND_TCP_FAILED = "tcp_failed"
KIND_BANNER_SILENT = "banner_silent"
KIND_BANNER_FOREIGN = "banner_foreign"

#: kind → the step it belongs to (the report answers "which step failed", not only "what").
KIND_STEP = {
    KIND_OK: "",
    KIND_DNS_FAILED: "dns",
    KIND_DNS_TIMEOUT: "dns",
    KIND_TCP_REFUSED: "tcp",
    KIND_TCP_TIMEOUT: "tcp",
    KIND_TCP_FAILED: "tcp",
    KIND_BANNER_SILENT: "banner",
    KIND_BANNER_FOREIGN: "banner",
}

#: Every verdict a report can carry (the topical test pins the SET, so a new kind
#: cannot appear without joining it — and the language files with it).
REPORT_KINDS = (KIND_OK, KIND_DNS_FAILED, KIND_DNS_TIMEOUT, KIND_TCP_REFUSED,
                KIND_TCP_TIMEOUT, KIND_TCP_FAILED, KIND_BANNER_SILENT,
                KIND_BANNER_FOREIGN)


@dataclass(frozen=True)
class ReachabilityReport:
    """The FACTS of one on-demand reachability report.

    Frozen and language-free: the harness asserts the four acceptance scenarios on it
    without a window, and the text lives in the i18n keys `report_parts()` names.
    """

    host: str
    port: int = 22
    kind: str = KIND_OK
    ip: str = ""          # the address DNS answered with ("" — DNS failed)
    detail: str = ""      # the technical detail: the error text, the foreign banner, the SSH banner
    ping: str = ""        # "" — not attempted | "ok" | "failed"
    timeout: float = REPORT_TIMEOUT_S
    elapsed: float = 0.0
    steps: tuple = field(default=())   # (step, kind) in the order they really ran

    @property
    def ok(self) -> bool:
        """Did every step succeed (the host really speaks SSH)?"""
        return self.kind == KIND_OK

    @property
    def step(self) -> str:
        """The FIRST step that failed ("" — none: the host answered)."""
        return KIND_STEP.get(self.kind, "")

    @property
    def i18n_key(self) -> str:
        """The i18n key of the verdict's sentence (`diagnose.<kind>`)."""
        return f"diagnose.{self.kind}"


def _short(text: str, limit: int = BANNER_MAX_CHARS) -> str:
    """A one-line, printable, bounded form of a piece of remote/protocol text."""
    clean = "".join(ch for ch in str(text or "") if ch.isprintable())
    clean = " ".join(clean.split())
    return clean[:limit]


def resolve_host(host: str, timeout: float = REPORT_TIMEOUT_S):
    """Resolve a name in a bounded way: `(ip, error)` — "" error means success.

    `socket.getaddrinfo` takes no timeout, and a broken resolver is exactly the case this
    report exists for, so the lookup runs on a DAEMON thread the report waits on for
    `timeout` seconds and then abandons ("timeout"): the daemon flag keeps a hung
    resolver from holding the process at exit (the orphan-thread discipline, without the
    QThread half — there is no C++ object to destroy here).
    """
    target = str(host or "").strip()
    if not target:
        return "", "empty host"
    box: dict = {}

    def _worker():
        try:
            box["infos"] = socket.getaddrinfo(target, None)
        except Exception as exc:  # noqa: BLE001 — a broken name is the ANSWER here
            box["error"] = str(exc) or exc.__class__.__name__

    thread = threading.Thread(target=_worker, name=DNS_THREAD_NAME, daemon=True)
    thread.start()
    thread.join(max(0.1, float(timeout)))
    if thread.is_alive():
        return "", "timeout"
    if box.get("error"):
        return "", box["error"]
    for info in box.get("infos") or ():
        try:
            address = info[4][0]
        except (IndexError, TypeError):
            continue
        if address:
            return str(address), ""
    return "", "no address"


def ping_once(host: str, timeout: float = PING_BUDGET_S) -> bool:
    """ONE ICMP packet — the LAST step of a report (True = the host answered).

    Deliberately not a 3-packet check (that is the status-bar message): the report uses one
    packet with the same -w/-W budget discipline, because its job is "does the host answer at
    all", not "how good is the link". A host starting with "-" is refused BEFORE a process is
    launched (Windows `ping` takes no `--`, so an argument-shaped host would be eaten as a flag).
    """
    target = str(host or "").strip()
    if not target or target.startswith("-"):
        return False
    seconds = max(0.2, float(timeout))
    if platform.system() == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(int(seconds * 1000)), target]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(round(seconds)))), "--", target]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=seconds + 2.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if platform.system() == "Windows" else 0)
    except Exception:  # noqa: BLE001 — no ping binary / a hung process: "no answer"
        return False
    return proc.returncode == 0


class _TcpError:
    """Which verdict a failed TCP connect deserves (the only place that decides it)."""

    @staticmethod
    def kind_for(error: str) -> str:
        text = str(error or "").lower()
        if "refused" in text:
            return KIND_TCP_REFUSED
        if "timed out" in text or "timeout" in text:
            return KIND_TCP_TIMEOUT
        if not text:
            return KIND_TCP_TIMEOUT
        return KIND_TCP_FAILED


def _connect(host: str, port: int, timeout: float):
    """The production connector: `(socket, error)` — never raises, always closes nothing."""
    try:
        return socket.create_connection((host, port), timeout=timeout), ""
    except Exception as exc:  # noqa: BLE001 — the error TEXT is what classifies it
        return None, str(exc) or exc.__class__.__name__


def diagnose_reachability(host: str, port: int = 22, timeout: float = REPORT_TIMEOUT_S,
                          *, resolver=None, connector=None, pinger=None) -> ReachabilityReport:
    """Run DNS → TCP → SSH banner (→ ICMP ping) and report the FIRST failure.

    The three callables are the TEST SEAMS (the status provider / transport injection
    pattern of the plugin runner): `resolver(host, timeout) -> (ip, error)`,
    `connector(host, port, timeout) -> (sock, error)` and `pinger(host, budget) -> bool`.
    Production passes the defaults (`resolve_host` / `_connect` / `ping_once`), so a test
    can produce a DNS-only failure, a refused port, a silent port and a live SSH host
    WITHOUT a network — which is exactly the task's acceptance list.

    The ICMP step runs only when TCP failed: after a banner the host is proven alive, and
    before DNS there is nothing to ping. Its result is EVIDENCE, not a verdict — the
    first failing step keeps the headline.
    """
    started = time.monotonic()
    resolver = resolver or resolve_host
    connector = connector or _connect
    pinger = pinger or (lambda target, budget: ping_once(target, budget))
    host = str(host or "").strip()
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 22
    port = max(1, min(65535, port))
    budget = max(0.2, float(timeout))
    steps = []

    def _report(kind, ip="", detail="", ping="", banner=""):
        steps.append((KIND_STEP.get(kind, ""), kind))
        return ReachabilityReport(
            host=host, port=port, kind=kind, ip=ip,
            detail=_short(banner or detail), ping=ping, timeout=budget,
            elapsed=time.monotonic() - started, steps=tuple(steps))

    # ── step 1: DNS ────────────────────────────────────────────────────────────
    try:
        ip, error = resolver(host, budget)
    except Exception as exc:  # noqa: BLE001 — a broken resolver seam is "DNS failed"
        ip, error = "", str(exc)
    ip = str(ip or "")
    error = str(error or "")
    if not ip:
        kind = KIND_DNS_TIMEOUT if error == "timeout" else KIND_DNS_FAILED
        return _report(kind, detail=error)

    # ── step 2: TCP ────────────────────────────────────────────────────────────
    sock, tcp_error = None, ""
    try:
        sock, tcp_error = connector(ip, port, budget)
    except Exception as exc:  # noqa: BLE001 — a broken connector seam is a TCP failure
        sock, tcp_error = None, str(exc)
    if sock is None:
        kind = _TcpError.kind_for(tcp_error)
        # "Is it the port or the host?" — the ONE question ICMP can still answer.
        answered = False
        try:
            answered = bool(pinger(host, budget))
        except Exception:  # noqa: BLE001 — a report never raises
            answered = False
        return _report(kind, ip=ip, detail=tcp_error,
                       ping="ok" if answered else "failed")

    # ── step 3: the SSH banner ─────────────────────────────────────────────────
    try:
        try:
            banner_bytes = sock.recv(BANNER_BYTES)
        except (socket.timeout, TimeoutError, OSError):
            return _report(KIND_BANNER_SILENT, ip=ip)
        if not banner_bytes:
            return _report(KIND_BANNER_SILENT, ip=ip)
        banner = banner_bytes.decode("utf-8", errors="replace").strip()
        if not banner.lstrip().startswith("SSH-"):
            return _report(KIND_BANNER_FOREIGN, ip=ip, banner=banner)
        return _report(KIND_OK, ip=ip, banner=banner)
    finally:
        try:
            sock.close()
        except Exception:  # noqa: BLE001 — closing a probe socket is best-effort
            pass


def report_parts(report: ReachabilityReport) -> list:
    """The `(i18n key, params)` pairs of a report: the verdict first, the ICMP evidence second.

    PURE (no i18n import): the caller formats the pairs with `t()` — which keeps the words in
    the language files and the logic testable without a window. The params of a kind are the
    placeholders its sentence uses; an extra one is harmless (`t()` ignores what the sentence
    does not mention).
    """
    key = report.i18n_key
    params = {"host": report.host, "port": report.port}
    if report.kind == KIND_OK:
        params["banner"] = report.detail
    elif report.kind in (KIND_DNS_FAILED, KIND_DNS_TIMEOUT):
        pass
    else:
        params["ip"] = report.ip or report.host
    if report.kind == KIND_TCP_TIMEOUT:
        params["timeout"] = f"{float(report.timeout):g}"
    if report.kind in (KIND_TCP_FAILED, KIND_BANNER_FOREIGN):
        params["banner" if report.kind == KIND_BANNER_FOREIGN else "detail"] = report.detail
    parts = [(key, params)]
    if report.ping == "ok":
        parts.append(("diagnose.ping_ok", {"host": report.host}))
    elif report.ping == "failed":
        parts.append(("diagnose.ping_failed", {"host": report.host}))
    return parts
