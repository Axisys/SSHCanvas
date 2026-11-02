# -*- coding: utf-8 -*-
"""`status` — one SSH probe per selected node, over the GUI's own PURE probe core.

Every status comes from `services.status_probe.probe_ssh()` — the SAME function the map's `StatusChecker`
runs — so a cron job and a card can never disagree. The report is READ-ONLY, the map's UNMANAGED card is
SKIPPED rather than probed (`AGENTS.md` §4.21) and the additive `data.skipped` names the ids it left out
(`count` counts the nodes really probed). Probes run in a bounded `ThreadPoolExecutor` and the records
keep the selection order; the process code is the ROUND's verdict (`0` every node `online`, `4` any
`warn`/`offline`) beside the envelope's `ok: true`. `AGENTS.md` §4.35; contract — `CLI.md` §3.3.
"""
import concurrent.futures

from models.server import is_unmanaged
from services.status_probe import DEFAULT_MAX_PARALLEL, STATUS_ONLINE, probe_ssh

from . import project as PROJECT_SOURCE
from . import verb_args
from .dispatch import Verb, register
from .exit_codes import EXIT_NETWORK

NAME = "status"
SUMMARY = "one SSH probe per node (node... = id or alias; no node = every node)"

#: The `data` keys of a status report, in order — the pinned machine payload (`skipped` is additive).
DATA_KEYS = ("project", "count", "timeout", "nodes", "skipped")


def split_unmanaged(nodes) -> tuple:
    """`(probed, skipped)` — the map's own rule: an unmanaged card is NEVER probed (PURE)."""
    probed, skipped = [], []
    for node in nodes or ():
        (skipped if is_unmanaged(node) else probed).append(node)
    return probed, skipped


def _probe(node, timeout) -> str:
    """One node's status through the SHIPPED probe (the map's own rule)."""
    return probe_ssh(str(getattr(node, "host", "") or ""),
                     int(getattr(node, "ssh_port", 22) or 22), timeout)


def probe_nodes(nodes, timeout, workers=DEFAULT_MAX_PARALLEL) -> list:
    """The `(node, status)` pairs — the selection order, `workers` probes at a time."""
    nodes = list(nodes or ())
    if not nodes:
        return []
    limit = max(1, min(int(workers or DEFAULT_MAX_PARALLEL), len(nodes)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=limit) as pool:
        statuses = list(pool.map(lambda node: _probe(node, timeout), nodes))
    return list(zip(nodes, statuses))


def handle(context, arguments):
    """The verb's FACTS — one record per probed node, and the ids the unmanaged rule left out."""
    tokens = verb_args.read_nodes(NAME, arguments)
    path = PROJECT_SOURCE.resolve_path(context.project)
    nodes = PROJECT_SOURCE.select_servers(PROJECT_SOURCE.read_servers(path), tokens)
    probed, skipped = split_unmanaged(nodes)
    records = [{"id": str(getattr(node, "id", "")),
                "alias": str(getattr(node, "alias", "") or ""),
                "status": status}
               for node, status in probe_nodes(probed, context.timeout)]
    return {"project": path, "count": len(records), "timeout": float(context.timeout),
            "nodes": records,
            "skipped": [str(getattr(node, "id", "")) for node in skipped]}


def verdict(payload) -> int:
    """`0` only when every probed node answered as an SSH server; `4` (`network`) otherwise."""
    for record in (payload or {}).get("nodes") or ():
        if record.get("status") != STATUS_ONLINE:
            return EXIT_NETWORK
    return 0


def render(context, payload) -> list:
    """One line per node — the alias (or the id when it has none) and the status."""
    return [f"{record.get('alias') or record.get('id') or ''}\t{record.get('status', '')}"
            for record in (payload or {}).get("nodes") or ()]


register(Verb(NAME, SUMMARY, handler=handle, render=render, verdict=verdict,
              min_args=0, max_args=verb_args.MAX_NODES))
