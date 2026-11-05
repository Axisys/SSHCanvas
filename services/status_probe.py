# -*- coding: utf-8 -*-
"""The PURE half of the status checks — the vocabulary, the probe and the three readers. No Qt.

`probe_ssh()` is the ONE synchronous SSH reachability probe (`online` = TCP + banner, `warn` = an open
port without one, `offline` = unreachable); `resolve_interval_sec()` / `is_manual_interval()` are the ONE
reading of the `status_interval_sec` cadence (`0` = manual only), `get_status_settings()` the ONE reader of
the three keys and `round_summary()` the ONE log line of a finished round. `services/status_checker.py`
runs a round in a QThread and re-exports this module because it is the GUI's live namespace; the headless
surface imports it directly (`AGENTS.md` §4.8.2, §4.35; mechanism — `DOCUMENTATION.md` §19).
"""
import math
import socket

try:  # the round summary (the activity history)
    from modules.logger import get_logger
except ImportError:  # pragma: no cover — the package layout (sshmap.services.*)
    from ..modules.logger import get_logger

log = get_logger(__name__)


STATUS_ONLINE = "online"    # green: TCP + SSH banner
STATUS_WARN = "warn"        # yellow: port open, but no banner
STATUS_OFFLINE = "offline"  # red: unreachable

#: The DECLARED order of the statuses, mildest first — ONE declaration that the group aggregate
#: (`graphics/node_group.py`), the plugin merge ladder and the reports all read.
STATUS_ORDER = (STATUS_ONLINE, STATUS_WARN, STATUS_OFFLINE)

#: The severity ladder of the status merge with a plugin's `status_probe` (`PLUGINS.md` §3 — "the
#: worse of the two by severity"): the status's own RANK in `STATUS_ORDER`.
SEVERITY = {status: rank for rank, status in enumerate(STATUS_ORDER)}

#: What "needs attention" means: the two statuses that are a problem on their own, plus (in
#: `is_in_trouble()`) the stale mark. A status outside the tuple is not a datum at all — a card that
#: was never probed carries "" and is neither a problem nor a member of an aggregate.
PROBLEM_STATUSES = (STATUS_WARN, STATUS_OFFLINE)


def is_in_trouble(status, stale: bool = False) -> bool:
    """Does this card need attention? — the ONE predicate of the trouble lens and the reports. PURE.

    `warn` / `offline`, or a status whose datum has grown STALE (a result nothing refreshed is exactly
    the "the map is lying to me" case the lens exists for). An UNCHECKED card is deliberately not
    trouble: there is no measurement to call a problem, and dimming "never probed" as an incident would
    be a false alarm.
    """
    return bool(stale) or str(status or "") in PROBLEM_STATUSES

DEFAULT_INTERVAL_MS = 30_000   # interval between periodic checks
DEFAULT_INTERVAL_SEC = 30      # the same, in seconds — default for the status_interval_sec key
PROBE_TIMEOUT_S = 3.0          # timeout of a single probe (connect + banner)

# The cadence's DECLARED range and its third state. The range is the clamp the key has always had
# (`5..86400`); `MANUAL_INTERVAL_SEC = 0` is the SENTINEL that selects "manual only" — NOT a second
# config key, so the setting keeps ONE home. `resolve_interval_sec()` is the PURE reader: exactly 0 means
# manual, every other value (a missing, negative, non-numeric or out-of-range one included) keeps the
# ordinary clamp, so a corrupt value degrades to a REAL interval rather than to a silent mode change.
MANUAL_INTERVAL_SEC = 0        # the sentinel: no round starts by itself
MIN_INTERVAL_SEC = 5
MAX_INTERVAL_SEC = 86400

#: Parallel probes and a soft auto-interval: the default, the clamp ceiling (the dialog spinbox and the
#: validator share it) and the map size above which a round's interval doubles ("N > ~50").
DEFAULT_MAX_PARALLEL = 16      # default for the status_max_parallel key
MAX_PARALLEL_LIMIT = 64        # clamp ceiling (dialog spinbox and validator — one range)
LARGE_MAP_THRESHOLD = 50       # N > 50 nodes → round interval doubles ("N > ~50")

# The status FRESHNESS: a status is a fact with a timestamp and the map must not present an old fact as
# a current one. The threshold is a FLOOR as well as a multiple — `max(2 × the effective interval,
# STALE_MIN_SEC)`, i.e. 90 s at the 30 s default, and a user who shortens the interval to 5 s still
# gets a meaningful "this is old" (10 s would be noise, not a signal).
STALE_MIN_SEC = 90.0

# The horizon of the MANUAL mode. "Two missed rounds" is not a sentence that means anything where there
# are no rounds, and marking a 90-second-old manual check stale would be noise rather than a signal — so
# the manual mode answers this DECLARED horizon instead: one day, patient enough to be a signal and short
# enough that a green card is never presented as a current fact for a whole week.
MANUAL_STALE_SEC = 86400.0


def round_summary(results) -> str:
    """The ONE line a finished round leaves in the log.

    PURE, so the topical test pins the sentence without a probe: the counts by status in
    the fixed order online → warn → offline, plus `?` for an answer that is none of the
    three (a plugin's merged kind is validated elsewhere — a summary must never lose a
    probed node silently). Example:

        "Status round: 5 probed — online 3, warn 1, offline 1"
    """
    counts = {STATUS_ONLINE: 0, STATUS_WARN: 0, STATUS_OFFLINE: 0}
    other = 0
    total = 0
    for item in results or ():
        try:
            _sid, status = item
        except (TypeError, ValueError):
            continue
        total += 1
        if status in counts:
            counts[status] += 1
        else:
            other += 1
    parts = [f"{name} {counts[name]}" for name in (STATUS_ONLINE, STATUS_WARN, STATUS_OFFLINE)]
    if other:
        parts.append(f"other {other}")
    return f"Status round: {total} probed — " + ", ".join(parts)


def resolve_interval_sec(value=DEFAULT_INTERVAL_SEC) -> int:
    """The round interval the key REALLY selects — 0 meaning "manual only".

    PURE, and the ONE reader of the `status_interval_sec` value: exactly `0` is the DECLARED
    sentinel of the manual mode and is answered as `0`; every other usable number keeps the
    ordinary clamp (`MIN_INTERVAL_SEC..MAX_INTERVAL_SEC`). A MISSING (`None`), non-numeric,
    boolean, NaN / ±inf or out-of-range value answers the DEFAULT (`DEFAULT_INTERVAL_SEC`) —
    never the sentinel: a corrupt value must degrade to a real interval, because silently
    switching the probes OFF is the one failure this reader exists to prevent. A negative
    number is an ordinary out-of-range value (clamped to `MIN_INTERVAL_SEC`), not a way to
    select the manual mode.
    """
    if value is None or isinstance(value, bool):
        return DEFAULT_INTERVAL_SEC
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SEC
    if number != number or number in (float("inf"), float("-inf")):  # NaN / ±inf
        return DEFAULT_INTERVAL_SEC
    if number == MANUAL_INTERVAL_SEC:
        return MANUAL_INTERVAL_SEC
    return max(MIN_INTERVAL_SEC, min(int(number), MAX_INTERVAL_SEC))


def is_manual_interval(resolved_sec) -> bool:
    """Does a RESOLVED interval mean "manual only"? (PURE — the `0` sentinel, one place.)"""
    try:
        return int(resolved_sec) == MANUAL_INTERVAL_SEC
    except (TypeError, ValueError):
        return False


def get_status_settings() -> dict:
    """The status settings from ~/.sshmap/config.json (the ONE reader of the three keys).

    Source — i18n.load_config() (never raises, {} on error). Returns:
        {"interval_sec": int, "manual": bool, "probe_timeout_sec": float, "max_parallel": int}
    Keys are OPTIONAL, defaults = 30 s / 3.0 s / 16:
        status_interval_sec      — round period (clamped 5..86400 s) OR the DECLARED `0`
                                   sentinel, which selects the MANUAL-only mode;
        status_probe_timeout_sec — timeout of a single probe (clamped 0.2..60 s);
        status_max_parallel      — ceiling of parallel probes per round
                                   (clamped 1..MAX_PARALLEL_LIMIT).
    Corrupt values (non-numeric, bool) → default. Never raises. The resolved PAIR is answered —
    `interval_sec` and the `manual` flag it implies (`resolve_interval_sec()` +
    `is_manual_interval()` are the ONE place that decides both), so no caller has to compare a
    number to a magic zero.
    """
    cfg: dict = {}
    try:
        from i18n import load_config
        cfg = load_config() or {}
    except Exception as e:  # noqa: BLE001 — the config is optional, defaults matter more
        log.debug("The status settings could not be read (%s) — the defaults answer", e)

    def _num(value, default: float) -> float:
        try:
            if isinstance(value, bool):
                return float(default)
            number = float(value)
        except (TypeError, ValueError):
            number = None
        if number is None or not math.isfinite(number):
            # `1e999` parses as `inf` and `NaN` is a float: `int()` raises on both, so the gate is HERE.
            log.debug("The config value %r is not a finite number — %s answers", value, default)
            return float(default)
        return number

    interval = resolve_interval_sec(cfg.get("status_interval_sec"))
    timeout = _num(cfg.get("status_probe_timeout_sec"), PROBE_TIMEOUT_S)
    timeout = max(0.2, min(timeout, 60.0))
    max_parallel = int(_num(cfg.get("status_max_parallel"), DEFAULT_MAX_PARALLEL))
    max_parallel = max(1, min(max_parallel, MAX_PARALLEL_LIMIT))
    return {"interval_sec": interval, "manual": is_manual_interval(interval),
            "probe_timeout_sec": timeout, "max_parallel": max_parallel}


def probe_ssh(host: str, port: int, timeout: float = PROBE_TIMEOUT_S) -> str:
    """Synchronous SSH reachability probe. Call from a worker thread only!

    Connects to host:port and reads the first bytes: an SSH server sends the
    banner "SSH-x.y-" right after the TCP handshake. Got it — online; the
    connection was established but no data / foreign data — warn; cannot
    connect — offline. An unusable NAME (an IDNA label over 63 characters, a NUL) is as offline as a
    refused port — the resolver raises before any socket exists.
    """
    if not host:
        return STATUS_OFFLINE
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            try:
                banner = sock.recv(32)
            except (socket.timeout, OSError):
                return STATUS_WARN  # connection is up, but no data within the timeout
            if not banner:
                return STATUS_WARN  # the server closed the connection without any bytes
            return STATUS_ONLINE if banner.lstrip().startswith(b"SSH-") else STATUS_WARN
    except (socket.timeout, OSError, UnicodeError, ValueError):
        return STATUS_OFFLINE


def build_targets(servers) -> list:
    """Normalize an iterable of ``(id, host, port)`` into the probe target list.

    Shared by ``StatusChecker.set_servers`` and ``MainWindow._sync_status_targets`` (the manual round
    builds its targets with the SAME normalization instead of a second, drifting copy). An entry
    without an id or a host is dropped — the probe would be meaningless; a broken port falls back to
    22 and is clamped to the protocol range.
    """
    targets = []
    for sid, host, port in servers or ():
        if not sid or not host:
            continue
        try:
            p = int(port) if port else 22
        except (TypeError, ValueError):
            log.debug("The port of server %s is unreadable (%r) — 22 answers", sid, port)
            p = 22
        targets.append((sid, str(host).strip(), max(1, min(65535, p))))
    return targets
