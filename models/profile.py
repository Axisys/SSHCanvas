"""Profiles model — reusable SSH credentials (login name + keyring-stored password).

Profiles are stored in ~/.sshmap_profiles.json and shared across all projects.
Passwords are NOT saved to disk — they're stored in the system credential store (keyring) via CredentialManager.
This prevents plaintext passwords from appearing in config files.

The READ is three-state (`read_store()`): a MISSING file is an empty store, VALID JSON is the store,
and a file that EXISTS but cannot be parsed is NEVER overwritten — every writer refuses through
`ProfileStoreError` (`AGENTS.md` §4.4.2, the known_hosts rule). Mechanism — `DOCUMENTATION.md` §3.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Optional, List

try:  # the ONE atomic-write mechanism (`AGENTS.md` §4.4, `DOCUMENTATION.md` §71)
    from ..storage import atomic as _atomic
except ImportError:  # flat launch from the project root
    from storage import atomic as _atomic


def _log():
    """Lazy-imported logger — the model keeps working without the logger tree."""
    try:
        from modules.logger import get_logger
        return get_logger("models.profile")
    except Exception:  # noqa: BLE001 — a build without the logger keeps the store working
        return None


@dataclass
class Profile:
    """Reusable SSH profile: login name and password (password stored in keyring)."""
    id: str  # unique identifier (8-char short UUID)
    name: str  # human-readable label shown in combobox
    user: str  # SSH username
    password: str = ""  # SSH password (optional — only used locally during edit, never persisted to disk)

    def __post_init__(self):
        # AUDIT v0.7.2 (medium #13): id is generated ONLY for new profiles.
        # Earlier any id whose length ≠ 8 was silently replaced on load — the link between
        # the profile and the keyring entry ("profile:{id}") was lost and the password
        # "disappeared". Now an existing id (of any length) is kept as-is.
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())[:8]


# ── Persistence helpers ────────────────────────────────────────────

#: The three answers of ONE read of the profiles file.
STORE_MISSING = "missing"      # no file yet — a fresh install (writers may create it)
STORE_OK = "ok"                # the file parsed (the document is the store)
STORE_UNREADABLE = "unreadable"  # the file EXISTS and cannot be parsed — writers REFUSE

#: The sentence of a refused write, in English: the model owns no i18n (§4.5) and names the REAL path,
#: because the profiles file is the LEGACY `~/.sshmap_profiles.json` (NOT under `~/.sshmap/`).
PROFILE_STORE_ERROR = ("The profiles file {path} cannot be read, so nothing was changed. "
                       "Repair or rename that file and try again.")


class ProfileStoreError(OSError):
    """A profiles WRITE refused because the file exists and cannot be parsed.

    Raised by `save_profiles()` (and every writer reading through it) so the last surviving profiles
    are never replaced by a file the reader could not understand (`AGENTS.md` §4.4.2). `path` is the
    file the user has to repair; `str(error)` is the sentence `PROFILE_STORE_ERROR` composed.
    """

    def __init__(self, path: str, reason: str = ""):
        self.path = str(path)
        self.reason = str(reason or "")
        self.message = PROFILE_STORE_ERROR.format(path=self.path)
        detail = f" ({self.reason})" if self.reason else ""
        super().__init__(self.message + detail)


def _profiles_path() -> str:
    """Return the path to the profiles JSON file."""
    home = os.path.expanduser("~")
    return os.path.join(home, ".sshmap_profiles.json")


def read_store():
    """ONE read of the profiles file: `(state, profiles, path, reason)` — the three-state answer.

    A MISSING file is `(STORE_MISSING, [], path, "")`; a file whose JSON is not a list is read as an
    EMPTY store (the shipped tolerance, one log line); and a file that EXISTS but cannot be parsed or
    opened is `(STORE_UNREADABLE, [], path, reason)` — the state every writer refuses to overwrite.
    A race that removes the file between the `isfile()` probe and the read answers `STORE_MISSING`.
    """
    path = _profiles_path()
    if not os.path.isfile(path):
        return STORE_MISSING, [], path, ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return STORE_MISSING, [], path, "the file disappeared while it was read"
    except json.JSONDecodeError as e:
        return STORE_UNREADABLE, [], path, f"invalid JSON at line {e.lineno} column {e.colno}"
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return STORE_UNREADABLE, [], path, str(e)
    if not isinstance(raw, list):
        return STORE_OK, [], path, ""
    # AUDIT v0.7.2 (medium #13): the id from the file is kept as-is — only an empty one
    # is generated (__post_init__). Corrupt entries are skipped, without breaking the load.
    profiles = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        profiles.append(Profile(
            id=str(p.get("id") or ""),
            name=str(p.get("name", "")),
            user=str(p.get("user", "")),
        ))
    return STORE_OK, profiles, path, ""


def unreadable_profiles_error() -> "Optional[ProfileStoreError]":
    """The refusal of a WRITE — `None` when the file is missing or really parses.

    Every writer asks this BEFORE it touches the file (the `_refuse_overwrite()` shape of
    `modules/host_key_policy.py`): a file that exists and cannot be parsed is left exactly as it is,
    so a repair by hand stays possible.
    """
    state, _profiles, path, reason = read_store()
    if state == STORE_UNREADABLE:
        return ProfileStoreError(path, reason)
    return None


# ── Credential Manager integration (lazy import) ────────────────

def _get_credential_manager():
    """Lazy-load credential manager singleton. Falls back gracefully."""
    try:
        from services.credential_manager import get_credential_manager as gcm
        return gcm()
    except Exception:
        # If keyring is unavailable, return None — password won't be persisted
        return None


# ── Persistence ────────────────────────────────────────────────

def load_profiles() -> List[Profile]:
    """Load all profiles from disk — an EMPTY list when there is nothing readable.

    A missing file and a file that cannot be parsed both answer `[]`, so a caller that only lists
    profiles keeps working; the difference is the ONE log line the second case writes (the path and
    the reason) and `save_profiles()`'s refusal, which is what keeps such a file from being lost.
    """
    state, profiles, path, reason = read_store()
    if state == STORE_UNREADABLE:
        log = _log()
        if log is not None:
            log.warning("The profiles file %s cannot be read (%s) — read as an empty store; "
                        "a write is refused until it is repaired", path, reason or "unreadable")
    return profiles


def save_profiles(profiles: List[Profile]) -> None:
    """Save all profiles to disk — REFUSES to overwrite a file that cannot be parsed.

    Passwords are stripped before saving — they live only in the system credential store (keyring).
    This prevents plaintext passwords from appearing in ~/.sshmap_profiles.json. A file that exists
    and cannot be parsed raises `ProfileStoreError` BEFORE the write (`unreadable_profiles_error()`),
    so the last surviving profiles are never replaced by a file nobody could read.
    """
    refusal = unreadable_profiles_error()
    if refusal is not None:
        raise refusal

    # Save passwords to keyring BEFORE stripping them from memory
    cm = _get_credential_manager()
    for p in profiles:
        if p.password:  # Only save non-empty passwords
            if cm and not cm.save_password(f"profile:{p.id}", p.password):
                pass  # Credential manager unavailable — password lost on restart

    data = []
    for p in profiles:
        d = asdict(p)
        d.pop("password", None)  # the password lives only in the keyring, not in the JSON
        data.append(d)
    # atomic write through the ONE mechanism (`storage/atomic.py`) — a crash mid-way through a
    # direct open/write corrupted the entire profiles file; the failure still RAISES to the caller.
    _atomic.publish_atomic(_profiles_path(), lambda temp: _atomic.dump_json(temp, data))


def add_profile(name: str, user: str, password: str = "") -> Profile:
    """Create a new profile and persist it (raises `ProfileStoreError` — the file is unreadable)."""
    profiles = load_profiles()
    import uuid
    p = Profile(
        id=str(uuid.uuid4())[:8],
        name=name.strip(),
        user=user.strip(),
        password=password,
    )
    profiles.append(p)

    # AUDIT v0.7.2 (low #14): there is no separate keyring write anymore — save_profiles()
    # below does it in the same pass for all profiles with a non-empty password. Earlier the
    # new profile's password was written twice (here and in save_profiles) — useless extra I/O.
    save_profiles(profiles)
    return p


def update_profile(profile_id: str, name: str, user: str,
                   password: Optional[str] = None) -> Optional[Profile]:
    """Update an existing profile by ID.

    password:
        None — do not change the stored password (the keyring entry is kept as-is);
        ""   — clear the password;
        str  — set a new password.
    Raises `ProfileStoreError` when the file exists and cannot be parsed (nothing is written).
    """
    profiles = load_profiles()
    for i, p in enumerate(profiles):
        if p.id == profile_id:
            p.name = name.strip()
            p.user = user.strip()

            if password is None:
                # "Do not change": keep the current password (from the keyring) for in-memory use
                p.password = get_profile_password(profile_id) or ""
            elif password:
                # Save password to keyring BEFORE potentially clearing it from memory
                cm = _get_credential_manager()
                if cm and not cm.save_password(f"profile:{p.id}", password):
                    pass  # Credential manager unavailable — password lost on restart
                p.password = password
            else:
                # Empty password means user wants to clear it
                cm = _get_credential_manager()
                if cm:
                    cm.delete_password(f"profile:{p.id}")
                p.password = ""

            save_profiles(profiles)
            return p
    return None


def delete_profile(profile_id: str) -> bool:
    """Remove a profile by ID. Returns True if deleted.

    An ID that is not in the store returns at once and never touches the file, so `False` stays the
    only answer of a missing profile — `ProfileStoreError` reaches the caller only from a REAL write.
    """
    profiles = load_profiles()
    new_profiles = [p for p in profiles if p.id != profile_id]
    if len(new_profiles) == len(profiles):
        return False  # not found

    # Clean up credential store entry too
    cm = _get_credential_manager()
    if cm:
        cm.delete_password(f"profile:{profile_id}")

    save_profiles(new_profiles)
    return True


def get_profile_by_id(profile_id: str) -> Optional[Profile]:
    """Load a single profile by ID, including password from keyring."""
    # First load without password (from JSON)
    profiles = load_profiles()
    for p in profiles:
        if p.id == profile_id:
            # Try to restore password from credential manager
            cm = _get_credential_manager()
            if cm:
                saved_pw = cm.load_password(f"profile:{p.id}")
                if saved_pw:
                    p.password = saved_pw
            return p
    return None


def get_profile_password(profile_id: str) -> Optional[str]:
    """Directly retrieve a profile's password from the credential store.

    Use this when you need only the password (e.g., for SSH connect without editing).
    Returns None if no keyring backend is available or the profile has no stored password.
    """
    cm = _get_credential_manager()
    if not cm:
        return None
    return cm.load_password(f"profile:{profile_id}")
