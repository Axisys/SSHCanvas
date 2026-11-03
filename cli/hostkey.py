# -*- coding: utf-8 -*-
"""`hostkey verify` — the pins of `~/.sshmap/known_hosts` checked against the servers, as a report.

The subject is the STORE, never a project: the rows are the pure `host_key_rows()` model the manager
dialog's table already reads, and every row is judged by the pure `verify_record()` table of
`modules/host_key_policy.py`. ONE unauthenticated read per ENDPOINT (`read_server_host_key()` — a
fingerprint cannot be turned back into a key), a bounded pool for the reads, and NOTHING is ever written:
a bulk run never auto-accepts, so a rotation is a human's decision. The verdicts are `ok` / `changed` /
`unverified` / `unreachable`; the process code is `0`, `2` (a pin moved) or `4` (a pin was not reached).
`AGENTS.md` §4.35; contract — `CLI.md` §3.6.
"""
import concurrent.futures

from modules import host_key_policy as HKP
from services.status_probe import DEFAULT_MAX_PARALLEL

from . import verb_args
from .dispatch import Verb, register
from .errors import refusal
from .exit_codes import EXIT_NETWORK, EXIT_OK, EXIT_REFUSAL

NAME = "hostkey"
SUMMARY = "check the pinned host keys against the servers (hostkey verify)"

#: The ONE declared subcommand of this family — the reader is `verb_args.SUBCOMMANDS`.
SUBCOMMAND_VERIFY = "verify"

#: The `data` keys of the report, in order — the pinned machine payload.
DATA_KEYS = ("store", "count", "timeout", "entries")

#: The columns of ONE report row, in the order the TEXT form writes them (the record's own keys).
COLUMNS = ("host", "keytype", "verdict", "stored", "presented", "detail")


def probe_endpoint(hostname, port, timeout):
    """The key ONE endpoint presents now, as `(keytype, fingerprint, error)` — an unauthenticated read."""
    key, error = HKP.read_server_host_key(hostname, port, timeout=timeout)
    if key is None:
        return "", "", str(error or "the server presented no host key")
    return (key.get_name() if hasattr(key, "get_name") else ""), HKP.fingerprint(key), ""


def verify_rows(rows, timeout, workers=DEFAULT_MAX_PARALLEL):
    """The report records — ONE probe per ENDPOINT, every pin of it judged by the PURE verdict table."""
    targets = HKP.verify_targets(rows)
    if not targets:
        return []
    limit = max(1, min(int(workers or DEFAULT_MAX_PARALLEL), len(targets)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=limit) as pool:
        answers = list(pool.map(lambda target: probe_endpoint(target[0], target[1], timeout), targets))
    records = []
    for (_hostname, _port, group), answer in zip(targets, answers):
        keytype, presented, error = answer
        for row in group:
            records.append(HKP.verify_record(row, keytype, presented, error))
    return records


def handle(context, arguments):
    """The verb's FACTS — one record per pinned entry, judged against what its endpoint presents now."""
    verb_args.read_subcommand(NAME, arguments)
    store = HKP.get_store()
    rows = HKP.host_key_rows(store.entries())
    if store.load_failed:
        raise refusal(f"the known-hosts store cannot be read: {store.path} "
                      f"({store.load_error or 'unknown error'})",
                      "repair or rename the file, then run the check again")
    records = verify_rows(rows, context.timeout)
    if not records:
        context.warn(f"the known-hosts store holds no pinned key ({store.path}) — nothing to verify")
    return {"store": store.path, "count": len(records), "timeout": float(context.timeout),
            "entries": records}


def verdict(payload):
    """`0` every pin `ok`/`unverified`, `2` any `changed` (a pin moved), else `4` any `unreachable`."""
    verdicts = [str(record.get("verdict") or "") for record in (payload or {}).get("entries") or ()]
    if HKP.VERIFY_CHANGED in verdicts:
        return EXIT_REFUSAL
    if HKP.VERIFY_UNREACHABLE in verdicts:
        return EXIT_NETWORK
    return EXIT_OK


def render(context, payload):
    """One line per pinned entry — the STORED fingerprint beside the one the endpoint presented."""
    return ["\t".join(str(record.get(column) or "") for column in COLUMNS)
            for record in (payload or {}).get("entries") or ()]


register(Verb(NAME, SUMMARY, handler=handle, render=render, verdict=verdict, min_args=1, max_args=1))
