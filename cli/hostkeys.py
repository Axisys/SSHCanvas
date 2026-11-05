# -*- coding: utf-8 -*-
"""The host-key policy of a headless run — refusal by default, `--accept-new` the ONE opt-in.

A bulk run has no dialog to ask through, so the shipped fallback (an unanswered question trusted by the
no-surface rule, `N100`) is exactly the wrong answer here: an UNKNOWN key is a REFUSAL (2) whose sentence
prints the fingerprint, and only a flag the operator typed may pin it. `--accept-new` pins through
`KnownHostsStore.replace()` — the ONE replacement writer, so every other algorithm of that name leaves in
the same atomic publish — and a key that could not be REMEMBERED refuses the run rather than authenticating
against a pin nobody kept. `--host-key <fingerprint>` pins one explicitly named key and refuses any other.
A CHANGED key is refused by every flag (`paramiko.BadHostKeyException` before the policy runs): a moved pin
is not a new host. Rule — `AGENTS.md` §4.4.2, §4.35; contract — `CLI.md` §5.2.
"""
from modules.host_key_policy import HostKeyRejected, SshKnownHostsPolicy, fingerprint

FINGERPRINT_PREFIX = "SHA256:"


def normalize_fingerprint(value) -> str:
    """The fingerprint a value names, in the ONE spelling `fingerprint()` answers (`SHA256:<base64>`).

    PURE: the `SHA256:` head is matched case-insensitively and kept in its shipped spelling, and the
    base64 padding is stripped — `ssh-keygen -lf` prints the body UNPADDED, so a value pasted from it
    must compare equal. A value without the head is taken as the base64 body alone; "" is "no
    fingerprint named".
    """
    text = str(value or "").strip()
    if not text:
        return ""
    head, separator, body = text.partition(":")
    if separator and head.strip().upper() == "SHA256":
        return FINGERPRINT_PREFIX + body.strip().rstrip("=")
    return text.rstrip("=")


class CliHostKeyPolicy(SshKnownHostsPolicy):
    """The GUI's policy with the ASK removed: an unknown key refuses unless a flag pinned it.

    `accept_new` is `--accept-new`, `expected` is `--host-key` (already normalised), and `note` is the
    verb's stderr door — the ONE sentence a pinned key leaves behind (`CLI.md` §5.2). The inherited
    `apply_to_client()` still loads every pinned entry into the client, so a key the store knows never
    reaches this class; a key it knows DIFFERENTLY raises inside `connect()` before it runs either.
    """

    def __init__(self, hostname="", port=22, accept_new=False, expected="", note=None):
        super().__init__(hostname, port)
        self.accept_new = bool(accept_new)
        self.expected = normalize_fingerprint(expected)
        self.note = note if callable(note) else (lambda message: None)

    def missing_host_key(self, client, hostname, key):
        """Pin the key only on an explicit opt-in; answer the refusal otherwise (never a silent accept)."""
        self.last_fingerprint = fingerprint(key)
        self.last_keytype = key.get_name() if hasattr(key, "get_name") else ""
        if self.expected and self.expected != self.last_fingerprint:
            raise HostKeyRejected(
                f"the host key of {self._entry_name()} is {self.last_fingerprint}, not the "
                f"{self.expected} --host-key named")
        if not (self.expected or self.accept_new):
            raise HostKeyRejected(
                f"the host key of {self._entry_name()} is not pinned "
                f"({self.last_keytype or 'unknown key type'} {self.last_fingerprint}) — verify it out "
                f"of band, then pin it with --host-key <fingerprint> or accept this one with "
                f"--accept-new")
        pinned = False
        try:
            pinned = bool(self.store.replace(self._entry_name(), self.last_keytype, key))
        except Exception:  # noqa: BLE001 — an unwritable store refuses the run below, never the dialect
            pinned = False
        if not pinned:
            raise HostKeyRejected(
                f"the host key of {self._entry_name()} was accepted for this run but the store refuses "
                f"the write ({self.store.path}) — repair ~/.sshmap/known_hosts and try again")
        self.accepted_new_key = True
        self.pinned = True
        self.note(f"pinned the host key of {self._entry_name()} "
                  f"({self.last_keytype or 'unknown key type'} {self.last_fingerprint})")
