# -*- coding: utf-8 -*-
"""The credential policy of a headless run — a key file, the endpoint-scoped keyring secret, else the agent.

The three sources are the contract's (`CLI.md` §5.1): a password is never read from stdin, an environment
variable or `argv`, so the ONE decision a verb has left is WHICH declared source a node resolves to. A key
file wins (`--identity PATH`, else the node's own `key_path`), the OS keyring answers only for the endpoint
it was stored FOR (`services/credential_manager.load_password()` over `node_scope()`), and the ssh-agent is
the LAST source — the branch `build_connect_kwargs()` already declares for "no secret of ours". A named key
that cannot be opened, and a secret stored for ANOTHER endpoint, are the missing-secret REFUSAL (2) whose
sentence names the door. Nothing here connects, prints or logs a secret. Rule — `AGENTS.md` §4.35;
contract — `CLI.md` §5.1; mechanism — `DOCUMENTATION.md` §80.
"""
import os
from dataclasses import dataclass

from modules.local_paths import resolve_local_path
from services.credential_manager import get_credential_manager, node_scope

from .errors import refusal

CRED_KEY = "key"                # a private key FILE — `--identity PATH` or the node's own `key_path`
CRED_PASSWORD = "password"      # the OS keyring's endpoint-scoped secret
CRED_AGENT = "agent"            # the ssh-agent / the user's default keys — `build_connect_kwargs()`'s last
CRED_SOURCES = (CRED_KEY, CRED_PASSWORD, CRED_AGENT)

#: The ONE door a missing secret's sentence names — the GUI's connect dialog is what stores a password.
DOOR = "run `sshcanvas`, connect once and let it store the password"


@dataclass(frozen=True)
class Credential:
    """ONE resolved credential: which declared source answered, and the secret/ path it answers WITH."""

    branch: str = CRED_AGENT
    password: str = ""
    key_path: str = ""
    scope: str = ""


def readable_key(path) -> bool:
    """Is `path` a file this run may hand to paramiko? PURE — never raises (an unusable path is False)."""
    try:
        return bool(path) and os.path.isfile(path)
    except (OSError, TypeError, ValueError):  # noqa: BLE001 — the caller owns the refusal that follows
        return False


def _store(manager=None):
    """The credential store this run reads (a test's own, otherwise the application's singleton)."""
    if manager is not None:
        return manager
    try:
        return get_credential_manager()
    except Exception:  # noqa: BLE001 — an unavailable keyring is "no stored secret", never a crash
        return None


def _node_id(node) -> str:
    """The keyring identity of a node — its `id`, the ONE spelling the GUI saves under (§4.4.1)."""
    return str(getattr(node, "id", "") or "")


def _secret(store, node, scope) -> str:
    """The keyring secret bound to `scope` ("" — nothing stored, another endpoint, or no store at all)."""
    if store is None:
        return ""
    try:
        return str(store.load_password(_node_id(node), scope=scope) or "")
    except Exception:  # noqa: BLE001 — a broken store is answered by the declared "no secret" branch
        return ""


def _saved_scope(store, node) -> str:
    """The endpoint a secret for this node was saved FOR ("" — a bare entry, or nothing stored)."""
    if store is None:
        return ""
    try:
        return str(store.stored_scope(_node_id(node)) or "")
    except Exception:  # noqa: BLE001 — an unreadable scope is the same as an absent one
        return ""


def resolve(node, identity="", manager=None) -> Credential:
    """Resolve ONE node's credential through the three declared sources, or raise the missing-secret refusal.

    The order is the contract's: a KEY this run names wins over everything (it is the operator's explicit
    choice for THIS invocation), then the node's own key file, then the keyring secret bound to the
    endpoint the node names today, then the ssh-agent. A key that is named but cannot be opened and a
    secret bound to ANOTHER endpoint are refusals rather than quiet fall-throughs: the run would otherwise
    authenticate as somebody nobody asked for.
    """
    wanted = str(identity or "").strip()
    if wanted:
        path = resolve_local_path(wanted)
        if not readable_key(path):
            raise refusal(f"no private key file at {wanted}",
                          f"--identity PATH must name a readable key, or {DOOR}")
        return Credential(CRED_KEY, key_path=path)
    named = str(getattr(node, "key_path", "") or "").strip()
    if named:
        path = resolve_local_path(named)
        if not readable_key(path):
            raise refusal(f"the private key of this node is not there: {named}",
                          "--identity PATH, or " + DOOR)
        return Credential(CRED_KEY, key_path=path)
    scope = node_scope(node)
    store = _store(manager)
    secret = _secret(store, node, scope)
    if secret:
        return Credential(CRED_PASSWORD, password=secret, scope=scope)
    bound = _saved_scope(store, node)
    if bound:
        raise refusal(f"the stored credential of {_node_id(node)} belongs to {bound}, not to {scope}", DOOR)
    return Credential(CRED_AGENT, scope=scope)
