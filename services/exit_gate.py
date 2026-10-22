# -*- coding: utf-8 -*-
"""The ONE exit gate — no running `QThread` reaches the interpreter teardown (AGENTS.md §4.8).

Every orphan registry of the process holds a Python reference to a thread that outlived its owner's
wait. A reference is NOT enough at exit: the interpreter drops the wrapper, the still-running
`QThread` is destroyed and Qt aborts the process (`qFatal`, exit `0xC0000409`). `join_all()` is the
ONE gate — it asks every registered thread to stop through its OWN door (`stop` / `cancel` / `close`
/ `requestInterruption`), then joins them against ONE declared total budget; `terminate()` is the
last resort and is logged. `main.py` arms it on `aboutToQuit` for both launch modes.
Mechanism — `DOCUMENTATION.md` §64."""

import sys
import time

#: The TOTAL budget of the gate, in milliseconds — ONE deadline for every registered thread.
EXIT_GATE_BUDGET_MS = 3000

#: The budget of the last resort (`terminate()`), in milliseconds — logged either way.
EXIT_GATE_TERMINATE_WAIT_MS = 500

#: The ONE table of the process's orphan registries: `(module, registry attribute)`. A module that
#: was never imported holds no thread, so the gate reads `sys.modules` and imports NOTHING at exit.
REGISTRY_OWNERS = (
    ("services.diagnostics", "_orphan_threads"),
    ("modules.ssh_terminal", "_orphan_threads"),
    ("modules.sftp_worker", "_orphan_workers"),
    ("modules.sftp_open", "_orphan_opens"),
    ("modules.sftp_elevated", "_orphan_handshakes"),
    ("modules.local_fs_worker", "_orphan_providers"),
)

#: The prefix a module may also carry when the application runs as a package (`sshmap.services.…`).
PACKAGE_PREFIX = "sshmap."

#: The doors a thread may offer, in the order the gate asks: the cheap signals first, `close()` last
#: (a handshake's `close()` drops the channel that unblocks it; a worker's `close()` does not exist).
STOP_DOORS = ("stop", "cancel", "close", "requestInterruption")

_installed = False


def _log():
    """The module logger, or None — the gate must work in a stripped build."""
    try:
        from modules.logger import get_logger
        return get_logger("services.exit_gate")
    except Exception:  # noqa: BLE001
        return None


def _module(module_name: str):
    """The ALREADY-IMPORTED module of a registry owner, under either import layout."""
    for name in (module_name, PACKAGE_PREFIX + module_name):
        module = sys.modules.get(name)
        if module is not None:
            return module
    return None


def _name_of(thread) -> str:
    """The thread's own name — Qt's abort message names an anonymous one as `''`."""
    try:
        return str(thread.objectName() or "") or type(thread).__name__
    except Exception:  # noqa: BLE001 — a dying C++ object cannot even be named
        return type(thread).__name__


def registered_threads() -> list:
    """Every thread an orphan registry holds RIGHT NOW — ONE snapshot, no duplicates.

    Reads only modules the process has already imported: a module that was never imported cannot
    hold a thread, so the gate never pulls the terminal/SFTP stack in at exit.
    """
    found, seen = [], set()
    for module_name, attr in REGISTRY_OWNERS:
        module = _module(module_name)
        if module is None:
            continue
        registry = getattr(module, attr, None)
        if not registry:
            continue
        try:
            threads = list(registry)
        except TypeError:  # a registry that is not a sequence is not one this gate owns
            continue
        for thread in threads:
            if id(thread) in seen:
                continue
            seen.add(id(thread))
            found.append(thread)
    return found


def stop_thread(thread) -> str:
    """Ask ONE thread to stop through its OWN door; answer the door's name (`""` — no door)."""
    for name in STOP_DOORS:
        door = getattr(thread, name, None)
        if not callable(door):
            continue
        try:
            door()
            return name
        except (RuntimeError, TypeError):
            continue   # the C++ object is gone, or the door wants an argument
        except Exception as e:  # noqa: BLE001 — a door that raises is tried no further
            log = _log()
            if log:
                log.debug("The exit door %s() of %s raised (%s) — the next door answers",
                          name, _name_of(thread), e)
            continue
    return ""


def _join(thread, remaining_ms: int) -> bool:
    """Wait ≤ `remaining_ms` for ONE thread; True — it ended (or there was nothing to wait for)."""
    try:
        if not thread.isRunning():
            return True
        return bool(thread.wait(int(remaining_ms)))
    except (RuntimeError, TypeError):
        return True   # a dead C++ object cannot outlive anything


def _terminate(thread) -> bool:
    """The declared LAST RESORT: `terminate()` a thread that ignored its own door. True — it ended."""
    try:
        if not thread.isRunning():
            return True
        thread.terminate()
        ended = bool(thread.wait(EXIT_GATE_TERMINATE_WAIT_MS))
    except (RuntimeError, TypeError):
        return True
    log = _log()
    if log:
        try:
            log.warning("Exit gate: thread '%s' ignored its own stop door and was TERMINATED "
                        "(the declared last resort)", _name_of(thread))
        except Exception:  # noqa: BLE001 — the caller owns the fallback: the report carries the name
            pass
    return ended


def join_all(budget_ms: int = EXIT_GATE_BUDGET_MS) -> dict:
    """Join every registered thread against ONE declared total budget — the gate's whole job.

    Returns `{"threads", "stopped", "joined", "survivors", "terminated"}`: the thread count, the
    names whose own door was asked, how many really ended, the names the last resort had to
    terminate and the names that are STILL running (an unkillable thread is REPORTED, never
    silently left — the registries keep their reference). Never raises.
    """
    try:
        budget = max(0, int(budget_ms))
    except (TypeError, ValueError):
        budget = EXIT_GATE_BUDGET_MS
    threads = registered_threads()
    report = {"threads": len(threads), "stopped": [], "joined": 0,
              "survivors": [], "terminated": []}
    for thread in threads:
        door = stop_thread(thread)
        if door:
            report["stopped"].append(_name_of(thread))
    deadline = time.monotonic() + budget / 1000.0
    survivors = []
    for thread in threads:
        remaining_ms = int(max(deadline - time.monotonic(), 0.0) * 1000)
        if _join(thread, remaining_ms):
            report["joined"] += 1
        else:
            survivors.append(thread)
    for thread in survivors:
        if _terminate(thread):
            report["terminated"].append(_name_of(thread))
        else:
            report["survivors"].append(_name_of(thread))
    return report


def close_gate(*_args) -> dict:
    """The `aboutToQuit` slot: run the gate and write ONE line. Never raises."""
    report = join_all()
    log = _log()
    if log:
        try:
            detail = (" — terminated: " + ", ".join(report["terminated"])) \
                if report["terminated"] else ""
            log.info("Exit gate: %d thread(s), %d joined, %d stopped, %d survivor(s)%s",
                     report["threads"], report["joined"], len(report["stopped"]),
                     len(report["survivors"]), detail)
        except Exception:  # noqa: BLE001 — the log is a side channel
            pass
    return report


def install_exit_gate(app=None) -> bool:
    """Arm the gate on `aboutToQuit` (idempotent). False — there is no application object."""
    global _installed
    if app is None:
        try:
            from PySide6.QtCore import QCoreApplication
        except Exception:  # noqa: BLE001 — a build without Qt has no threads to gate
            return False
        app = QCoreApplication.instance()
    if app is None:
        return False
    if _installed:
        return True
    try:
        app.aboutToQuit.connect(close_gate)
    except (AttributeError, RuntimeError, TypeError):
        return False
    _installed = True
    return True
