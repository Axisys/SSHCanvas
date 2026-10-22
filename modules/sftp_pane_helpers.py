# -*- coding: utf-8 -*-
"""The PURE helpers and the vocabulary of the Files pane family (`_SftpPane`).

`format_size` / `format_mtime` / `decode_text` / `preview_block_reason` turn a size, a timestamp or a
byte buffer into the text a row or the reader shows — no widget, no provider, no network — beside the
reader's encoding/wrap settings (`ui_viewer_encoding`, `ui_viewer_wrap`, `ui_sftp_encodings`), the TWO
path DIALECTS (`PathDialect` / `dialect_for`), the per-server directory memory (`ui_sftp_dirs`), the
row ROLES and the source/drag vocabulary the widget module imports, the row readers (`row_path` /
`row_name`), the cut predicate, the reader's BACKGROUND hue, the `Network ▸` address detector with its
three commands, and the Commander's own settings; `ask_conflict()` is the ONE overwrite
question, with its `QMessageBox` taken from the facade (`STAB.QMessageBox`). Every name is re-exported
by `modules.sftp_tab` — `SFTP_PANES.md` §5-§6; `DOCUMENTATION.md` §59, §64, §66, §68.
"""

import codecs
import ipaddress
import json
import os
import posixpath
import re
import sys
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QMessageBox

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # the extension classifier of the reader's guess and the machine payload readers
    from .sftp_worker import (NAME_ERROR_UNSAFE, READ_ERROR_BINARY, classify_extension,
                              parse_task_payload)
except ImportError:
    from sftp_worker import (NAME_ERROR_UNSAFE, READ_ERROR_BINARY,  # type: ignore
                             classify_extension, parse_task_payload)

try:  # the LOCAL provider's machine codes — `local_error_text()` renders its refusals
    from . import local_fs_worker as local_fs
except ImportError:  # flat launch from the project root
    import local_fs_worker as local_fs  # type: ignore


# ── The pane's VOCABULARY — the row roles, the two sources and the drag payload ──────
# Declared HERE, in the pure module that BOTH layers read: the row readers below compare the roles,
# the dialects compare the sources and `pane_payload()` reads the MIME, while
# `modules/sftp_pane_widgets.py` imports them DOWNWARD (it never reaches back through the facade).

#: v1.7.3: the drag payload of a row that started INSIDE a Files pane. The remote path alone
#: cannot say WHICH pane (two servers show the same path), so the private type carries the session
#: key, the pane's identity and the path while `text/plain` keeps the plain path for every foreign
#: consumer (a terminal, an editor, a chat window).
PANE_DRAG_MIME = "application/x-sshmap-pane-row"

#: v1.7.4rc1: the two DATA SOURCES of a pane. A pane is typed to ONE of them (its provider);
#: `SOURCE_REMOTE` is the session's own transport (`SftpTab._worker`) and `SOURCE_LOCAL` is the OS
#: disk of this machine, read through `modules/local_fs_worker.py` on its OWN thread. The source is
#: a property of the PANE (LOCAL_PANE.md §1), never of the container: ONE pane of the Commander may
#: read the local disk while the other one reads the server.
SOURCE_REMOTE = "remote"
SOURCE_LOCAL = "local"
PANE_SOURCES = (SOURCE_REMOTE, SOURCE_LOCAL)

#: v1.8: the THIRD position of a pane's SOURCE CONTROL — a REMOTE pane whose PROVIDER reads the
#: server as another user (`ELEVATED_PANE.md` §1). It is deliberately NOT a third data source: the
#: dialect stays POSIX, `PANE_SOURCES` keeps its pair and §5's four-pair dispatch keeps its rows.
SOURCE_ELEVATED = "elevated"

#: The listing's row ROLES — what the listing writes and `_SftpRowItem` compares.
PATH_ROLE = Qt.ItemDataRole.UserRole       # full remote path of the entry
ISDIR_ROLE = Qt.ItemDataRole.UserRole + 1  # bool — is it a directory?
SIZE_ROLE = Qt.ItemDataRole.UserRole + 2   # int — file size (0 for a directory)
MTIME_ROLE = Qt.ItemDataRole.UserRole + 3  # int — unix mtime


def _facade_attr(name, default=None):
    """An attribute of the SHIPPED facade module at call time — the `modules.sftp_tab` seam.

    A module-level helper has no `self` for `host_attr()`, and the facade imports THIS module, so
    the module object is read from `sys.modules` (fully loaded by call time). `STAB.<name> = fake`
    therefore keeps working for the Qt classes the suite substitutes.
    """
    for mod_name in ("modules.sftp_tab", "sftp_tab"):
        mod = sys.modules.get(mod_name)
        if mod is not None:
            return getattr(mod, name, default)
    return default


def format_size(n) -> str:
    """Human-readable size: 0 → "0 B", 1536 → "1.5 KB" (no locales)."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    if n < 0:
        return "?"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def format_mtime(ts) -> str:
    """Local mtime time "%Y-%m-%d %H:%M"; broken/zero → ""."""
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return ""
    if ts <= 0:
        return ""
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


def decode_text(data: bytes, truncated: bool = False, encoding: str = "auto"):
    """v1.3.1: bytes → (text, encoding really used).

    UTF-8 (BOM-aware — "utf-8-sig" strips an UTF-8 BOM) first; on a decode
    failure the Latin-1 fallback, which never fails and always yields a string
    (mojibake instead of an exception — the header carries the encoding note).

    v1.9.3: `encoding` is the reader's CHOICE — `"auto"` is the shipped rule above and a NAMED codec
    (one of `VIEWER_ENCODINGS`) is tried FIRST with that rule kept as the fallback, so a buffer the
    chosen encoding cannot read is still SHOWN. The second half of the pair is the codec that really
    read it, which is how the caller tells a choice that worked from one that fell back.

    `truncated` says the read STOPPED AT THE CEILING (N46): a byte-exact cut lands inside a
    multi-byte character roughly every second time on Cyrillic/CJK text, and the resulting
    `UnicodeDecodeError` describes the CAP, not the file — the incomplete tail is therefore held
    back (an incremental decoder with `final=False`, at most three bytes) and the text stays
    UTF-8. A COMPLETE buffer keeps the shipped rule BYTE FOR BYTE, so a real Latin-1 file whose
    last byte is a lead byte keeps its last character; a genuinely invalid byte still raises and
    still falls back.
    """
    data = bytes(data)
    chosen = normalize_viewer_encoding(encoding)
    if chosen != "auto":
        codec = "utf-8-sig" if chosen == "utf-8" else chosen
        try:
            decoder = codecs.getincrementaldecoder(codec)()
            return decoder.decode(data, final=not truncated), chosen
        except (UnicodeDecodeError, LookupError):  # noqa: BLE001 — the caller owns the fallback: the shipped rule below answers
            pass   # the choice cannot read this buffer — the shipped rule below is the answer
    if truncated:
        try:
            decoder = codecs.getincrementaldecoder("utf-8-sig")()
            return decoder.decode(data, final=False), "utf-8"
        except (UnicodeDecodeError, LookupError):  # noqa: BLE001 — the caller owns the fallback: the shipped rule below answers
            pass   # a real invalid byte — the fallback below is the shipped answer
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace"), "latin-1"


#: v1.9.3: the reader's ENCODING choice — ONE key of `~/.sshmap/config.json` (the `ui_viewer_wrap`
#: rule: one global value, an unknown or broken one falling back to `auto`) and the DECLARED list the
#: reader's submenu offers. A codec NAME is an identifier and is deliberately never translated; only
#: `auto` — the shipped utf-8 → latin-1 rule — carries a word of its own.
VIEWER_ENCODING_CONFIG = "ui_viewer_encoding"
VIEWER_ENCODING_DEFAULT = "auto"
VIEWER_ENCODINGS = ("auto", "utf-8", "cp1251", "cp1252", "cp866", "koi8-r", "latin-1", "gbk")

#: v1.7.3: the reader's WORD WRAP — the twin of the key above, and the reason both live here: the
#: reader's two global settings are resolved ONCE by a pane and travel into the read/show path.
VIEWER_WRAP_CONFIG = "ui_viewer_wrap"


def resolve_viewer_wrap(cfg: dict = None) -> bool:
    """The reader's word wrap as a PURE value (v1.7.3).

    Only a real JSON `true`/`false` counts; anything else — a string `"true"`, a number, a missing
    key, an unreadable config — answers the DEFAULT (`False`: the shipped no-wrap look).
    """
    if not isinstance(cfg, dict):
        try:
            from i18n import load_config
        except Exception:  # noqa: BLE001 — a build without i18n keeps the default
            return False
        try:
            cfg = load_config() or {}
        except Exception:  # noqa: BLE001 — a broken config store keeps the default
            cfg = {}
    value = cfg.get(VIEWER_WRAP_CONFIG) if isinstance(cfg, dict) else None
    return value if isinstance(value, bool) else False


def save_viewer_wrap(on) -> bool:
    """Write the ONE word-wrap key (merge-write; False — the config could not be written)."""
    try:
        from i18n import save_config
    except Exception:  # noqa: BLE001 — a build without i18n cannot remember it
        return False
    try:
        return bool(save_config({VIEWER_WRAP_CONFIG: bool(on)}))
    except Exception:  # noqa: BLE001 — a write failure must not break the reader
        return False


def normalize_viewer_encoding(value) -> str:
    """PURE: one value into the DECLARED list — `auto` (the shipped rule) for anything else."""
    code = str(value if value is not None else "").strip().lower()
    return code if code in VIEWER_ENCODINGS else VIEWER_ENCODING_DEFAULT


def resolve_viewer_encoding(cfg: dict = None) -> str:
    """The reader's encoding choice as a PURE value (v1.9.3): the config's codec, else `auto`.

    A missing key, a foreign type or an unreadable config answers the DEFAULT — the shipped
    utf-8 → latin-1 rule is what a user who never touched the setting has.
    """
    if not isinstance(cfg, dict):
        try:
            from i18n import load_config
        except Exception:  # noqa: BLE001 — a build without i18n keeps the default
            return VIEWER_ENCODING_DEFAULT
        try:
            cfg = load_config() or {}
        except Exception:  # noqa: BLE001 — a broken config store keeps the default
            cfg = {}
    value = cfg.get(VIEWER_ENCODING_CONFIG) if isinstance(cfg, dict) else None
    return normalize_viewer_encoding(value)


def save_viewer_encoding(value) -> bool:
    """Write the ONE encoding key, NORMALISED (merge-write; False — the config could not be written)."""
    try:
        from i18n import save_config
    except Exception:  # noqa: BLE001 — a build without i18n cannot remember it
        return False
    try:
        return bool(save_config({VIEWER_ENCODING_CONFIG: normalize_viewer_encoding(value)}))
    except Exception:  # noqa: BLE001 — a write failure must not break the reader
        return False


#: v1.14.1: the READER's BACKGROUND — ONE global key holding a HUE (0..359) and nothing else: the
#: syntax palette is tuned to the theme's own surface, so a free COLOUR would make the ink unreadable
#: while a hue keeps the tone (the lightness of `base_bg`) derivable. An absent value IS the theme.
VIEWER_BACKGROUND_CONFIG = "ui_viewer_background"
VIEWER_BACKGROUND_HUE_MIN = 0
VIEWER_BACKGROUND_HUE_MAX = 359
#: The presets the reader's chip offers — `(name, hue)`, the "Appearance" tab's own vocabulary
#: (`settings.appearance.accent.<name>` is the SAME i18n key, never a copy of it).
VIEWER_BACKGROUND_PRESETS = (("sky", 198.4), ("cyan", 187.0), ("green", 142.0), ("amber", 38.0),
                             ("orange", 25.0), ("pink", 330.0), ("violet", 262.0),
                             ("slate", 215.0))


def viewer_background_hue(value):
    """PURE: one stored value → `(hue, refused)` — a hue in 0..359, or None for the theme.

    An ABSENT / null / blank value is the theme. Every other value outside the declared range — a
    string, a bool, a negative number, 400 — is REFUSED rather than clamped into a colour the user
    never chose, and the caller says so once (v1.14.1).
    """
    if value is None:
        return (None, False)
    if isinstance(value, str) and not value.strip():
        return (None, False)
    if isinstance(value, bool):
        return (None, True)
    try:
        rounded = int(round(float(value)))
    except (TypeError, ValueError):
        return (None, True)
    if not (VIEWER_BACKGROUND_HUE_MIN <= rounded <= VIEWER_BACKGROUND_HUE_MAX):
        return (None, True)   # a NaN and an out-of-range number land here together
    return (rounded % 360, False)


def resolve_viewer_background(cfg: dict = None):
    """The reader's background as `(hue, refused)` from ONE config read (PURE, v1.14.1)."""
    if not isinstance(cfg, dict):
        try:
            from i18n import load_config
        except Exception:  # noqa: BLE001 — a build without i18n keeps the theme's look
            return (None, False)
        try:
            cfg = load_config() or {}
        except Exception:  # noqa: BLE001 — a broken config store keeps the theme's look
            cfg = {}
    value = cfg.get(VIEWER_BACKGROUND_CONFIG) if isinstance(cfg, dict) else None
    return viewer_background_hue(value)


def save_viewer_background(hue) -> bool:
    """Write the ONE background key — a hue, or `None` for the theme (merge-write)."""
    try:
        from i18n import save_config
    except Exception:  # noqa: BLE001 — a build without i18n cannot remember it
        return False
    try:
        return bool(save_config({VIEWER_BACKGROUND_CONFIG: viewer_background_hue(hue)[0]}))
    except Exception:  # noqa: BLE001 — a write failure must not break the reader
        return False


# ── The reader's `Network ▸` verbs (v1.14.1) ──────────────────────────────────
# The selection a reader hands over is UNTRUSTED TEXT (a config file, a log line, a stranger's
# comment), so the row's target is an ALLOWLIST: four dotted decimal octets in 0..255 and an OPTIONAL
# port in 1..65535 — the commands below are built from that validated address alone.

#: The dotted shape a selection must have before `ipaddress` is even asked.
NETWORK_TARGET_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?$")

#: The THREE verbs and their ONE literal command each (`{host}` is the validated address).
NETWORK_VERBS = ("ping", "trace", "reverse")
NETWORK_COMMANDS = {
    "ping": "ping -c 4 -W 2 {host}",
    "trace": "traceroute -n {host} 2>/dev/null || tracepath -n {host}",
    "reverse": "getent hosts {host}",
}


def parse_network_target(text):
    """`(host, port)` of a validated `IPv4` / `IPv4:PORT` selection — None for anything else (PURE).

    `ipaddress` is the parser, so the doctored shapes a looser test would accept are refused:
    `10.0.0.300`, `010.0.0.1` and a five-octet string all answer None. A missing port answers 0.
    """
    match = NETWORK_TARGET_RE.match(str(text if text is not None else "").strip())
    if not match:
        return None
    try:
        host = str(ipaddress.IPv4Address(match.group(1)))
    except ValueError:
        return None
    port_text = match.group(2)
    if port_text is None:
        return (host, 0)
    try:
        port = int(port_text)
    except ValueError:
        return None
    return (host, port) if 1 <= port <= 65535 else None


def network_command(verb: str, host: str) -> str:
    """The ONE command of a `Network ▸` verb over a VALIDATED address (PURE; "" — refused).

    The host is re-validated here, so the builder cannot become a second, looser door onto the
    shell: a foreign verb and a foreign address both answer "" (nothing is queued).
    """
    template = NETWORK_COMMANDS.get(str(verb or ""))
    target = parse_network_target(host or "")
    if not template or not target:
        return ""
    return template.format(host=target[0])


#: v1.13.6: the per-SESSION encoding memory — the codec THIS pane's user chose, filed by the session's
#: `history_key()` and the pane's index (`{session key: [codec of pane 1, codec of pane 2]}`) beside the
#: shipped `ui_sftp_dirs` map. An EMPTY slot means "this pane never chose", so it keeps following the
#: global `ui_viewer_encoding` default — which is what keeps a CP1251 pane and a Latin-1 one apart.
ENCODINGS_CONFIG = "ui_sftp_encodings"
MAX_REMEMBERED_ENCODINGS = 32
ENCODING_SLOTS = 2       # a container holds at most two panes (SFTP_PANES.md §1)


def _stored_codec(value) -> str:
    """ONE slot of the memory: a declared codec, or `""` — the pane never chose / the value is foreign."""
    text = str(value if value is not None else "").strip().lower()
    return text if text in VIEWER_ENCODINGS else ""


def sanitize_encodings(raw) -> dict:
    """The usable entries of a stored map: a session key and TWO declared slots, or the entry drops."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        name = str(key or "")
        if not name or not isinstance(value, (list, tuple)):
            continue
        slots = [_stored_codec(item) for item in list(value)[:ENCODING_SLOTS]]
        while len(slots) < ENCODING_SLOTS:
            slots.append("")
        if any(slots):
            out[name] = slots
    return out


def remember_encoding(mapping, key, index, codec, limit: int = MAX_REMEMBERED_ENCODINGS) -> dict:
    """File ONE pane's choice into the map, moving the session to the END (PURE, the dirs rule).

    Insertion order IS the age, so the eviction needs no timestamp; a blank key, a pane index outside
    `ENCODING_SLOTS` or a foreign codec changes NOTHING (the caller normalises what the menu hands).
    """
    out = dict(mapping or {})
    name = str(key or "")
    try:
        slot = int(index)
    except (TypeError, ValueError):
        return out
    code = _stored_codec(codec)
    if not name or not 0 <= slot < ENCODING_SLOTS or not code:
        return out
    slots = list(sanitize_encodings(out).get(name) or [""] * ENCODING_SLOTS)
    slots[slot] = code
    out.pop(name, None)
    out[name] = slots
    while len(out) > max(1, int(limit)):
        out.pop(next(iter(out)))
    return out


def remembered_encoding_for(mapping, key, index) -> str:
    """The codec remembered for ONE pane of a session (`""` — that pane never chose)."""
    try:
        slots = (mapping or {}).get(str(key or "")) or []
        return _stored_codec(slots[int(index)])
    except (TypeError, ValueError, IndexError, AttributeError, KeyError):
        return ""


def load_remembered_encodings(cfg: dict = None) -> dict:
    """The per-session encoding map from `~/.sshmap/config.json` ({} — nothing to restore).

    FOREIGN content answers `{}` rather than a guess: a broken config must never decode a pane with
    a codec nobody chose. Never raises.
    """
    if not isinstance(cfg, dict):
        try:
            from i18n import load_config
        except Exception:  # noqa: BLE001 — a build without i18n keeps no memory
            return {}
        try:
            cfg = load_config() or {}
        except Exception:  # noqa: BLE001 — a broken config store must not break a pane
            cfg = {}
    return sanitize_encodings(cfg.get(ENCODINGS_CONFIG) if isinstance(cfg, dict) else None)


def save_remembered_encodings(mapping) -> bool:
    """Write the per-session encoding map, SANITIZED (merge-write; False — the wallet is unwritable)."""
    try:
        from i18n import save_config
    except Exception:  # noqa: BLE001 — a build without i18n cannot remember it
        return False
    try:
        return bool(save_config({ENCODINGS_CONFIG: sanitize_encodings(mapping)}))
    except Exception:  # noqa: BLE001 — a write failure must not break the reader
        return False


def delete_confirm_key(local: bool, backend: str = "") -> str:
    """The ONE i18n key of a delete's confirmation — what the click will really do (PURE).

    A REMOTE row keeps the shipped question; a LOCAL row with a trash backend says that it can be
    restored, and a host WITHOUT one keeps the shipped permanent warning (the delete never changes
    behaviour behind the sentence the user read).
    """
    if not local:
        return "sftp.op.delete_confirm"
    return "sftp.local.trash_confirm" if backend else "sftp.local.delete_confirm"


def preview_block_reason(path: str, size=0, facts=None) -> str:
    """v1.3.1.1: will the viewer refuse this file? "" (no) | "binary" | "too_large".

    The order of the answers is the point of this function — from the certain to
    the guessed:

      1. `facts` — the results of REAL read attempts of this session (path →
         reason): the worker is the only one who sees the content, so its verdict
         wins. A `.txt` with a null byte looks like text by name and is refused by
         the worker — the row is marked only after the attempt, and from then on
         the mark is the truth;
      2. the extension (a GUESS — the null-byte screen can still refuse the file,
         and a file with an unknown/absent extension usually reads fine).

    **`size` is accepted for the callers' shape and is deliberately NOT a reason**
    (v1.7.5): the read is TRUNCATED at the configured ceiling, never refused, so a
    file over the cap opens with its first `cap` bytes and the panel says how much
    of how many it shows (`sftp.viewer.truncated`). A `too_large` FACT of a real
    read attempt still marks the row; the size alone does not.
    """
    if facts:
        known = facts.get(path)
        if known:
            return known
    if classify_extension(path) == "binary":
        return READ_ERROR_BINARY
    return ""


def ask_conflict(parent, name: str, target: str, remaining: int = 0, facts: str = ""):
    """v1.3.3.2: the overwrite question for ONE item of a batch.

    Returns `(action, apply_all)`, where action is one of

      * `"overwrite"` — replace the existing destination;
      * `"skip"` — leave the destination alone and go on with the batch;
      * `"rename"` — ask for another name (the caller prompts, then uploads /
        downloads under it) — `apply_all` is never set for it: a batch rename needs
        a name per file;
      * a cancelled dialog (Esc / the window's X) is reported as `"skip"`.

    `remaining` is the number of conflicts still to come in this batch — "Apply to
    all" is offered only when there is anything left to apply it to.

    `facts` is the ONE optional line the cross-session send adds (v1.7.3): both sides'
    size and date, rendered as the message box's informative text when it is non-empty.

    The QMessageBox is taken as a MODULE ATTRIBUTE at call time
    (`STAB.QMessageBox = <fake>` is the test seam — the command-library pattern);
    the pane's `_ask_conflict()` is the caller, so a test can also replace the whole
    decision.
    """
    box_cls = _facade_attr("QMessageBox", QMessageBox)   # a module attribute — the monkeypatch seam
    box = box_cls(parent)
    box.setWindowTitle(_t("sftp.conflict.title"))
    try:
        box.setIcon(box_cls.Icon.Question)
    except Exception:   # noqa: BLE001 — an exotic Qt build without the enum
        pass
    box.setText(_t("sftp.conflict.message", name=name, target=target))
    if facts:
        try:
            box.setInformativeText(str(facts))
        except Exception:   # noqa: BLE001 — a build without the setter keeps the question
            pass
    btn_over = box.addButton(_t("sftp.conflict.overwrite"),
                             box_cls.ButtonRole.AcceptRole)
    box.addButton(_t("sftp.conflict.skip"),
                  box_cls.ButtonRole.RejectRole)
    btn_rename = box.addButton(_t("sftp.conflict.rename"),
                               box_cls.ButtonRole.ActionRole)
    check = QCheckBox(_t("sftp.conflict.apply_all"))
    check.setEnabled(int(remaining or 0) > 0)
    box.setCheckBox(check)
    box.exec()
    clicked = box.clickedButton()
    if clicked is btn_over:
        action = "overwrite"
    elif clicked is btn_rename:
        action = "rename"
    else:
        action = "skip"        # Skip, or a cancelled dialog (clickedButton() is None)
    apply_all = bool(check.isChecked()) and action in ("overwrite", "skip")
    return action, apply_all


# ── The two PATH DIALECTS — the ONE adapter a pane resolves paths through ─────
def _win_standard_path(path: str) -> str:
    """`os.path.normcase` on every OS (a PURE helper, so the dialect stays testable everywhere).

    The LOCAL dialect is case-insensitive on Windows and case-SENSITIVE elsewhere; the shipped
    `os.path.normcase` is an identity on POSIX, so it is used directly and the fallback keeps the
    same answer when the platform module cannot be asked.
    """
    try:
        return os.path.normcase(str(path or ""))
    except Exception:  # noqa: BLE001 — never break a listing over a path comparison
        return str(path or "")


class PathDialect:
    """The PATH RULES of one data source — the ONE adapter a pane resolves paths through.

    A remote pane speaks POSIX (`posixpath`, the "/" root) and a LOCAL pane speaks the OS disk
    (backslashes, a drive or UNC root, case-insensitive names). Every join, split, root test and
    name comparison of the pane goes through its dialect, so a second dialect costs ONE object and
    not a second pane (LOCAL_PANE.md §2). PURE: no Qt, no IO, no i18n.
    """

    def __init__(self, kind: str, label: str):
        self.kind = str(kind)
        self.label = str(label)

    @property
    def is_local(self) -> bool:
        return self.kind == SOURCE_LOCAL

    @property
    def separator(self) -> str:
        """The character that continues INTO a directory (the completer's trailing one)."""
        return "\\" if self.is_local else "/"

    def dirname(self, path: str) -> str:
        """The parent of `path` — "" at the root (the root itself for the LOCAL dialect)."""
        text = str(path or "")
        if self.is_local:
            return os.path.dirname(text)
        return posixpath.dirname(text)

    def join(self, base: str, name: str) -> str:
        """`base` + `name` as ONE path."""
        text, child = str(base or ""), str(name or "")
        if self.is_local:
            return os.path.join(text, child)
        return posixpath.join(text or "/", child)

    def basename(self, path: str) -> str:
        """The LAST component of `path` (the name a row, a dialog or a sentence shows)."""
        text = str(path or "")
        if self.is_local:
            return os.path.basename(text)
        return posixpath.basename(text)

    def is_root(self, path: str) -> bool:
        """Is `path` a ROOT (nothing above it)? A bare drive name and `~` are NOT.

        For the LOCAL dialect a root is the path its own parent already is — a drive root
        (`C:\\`), a UNC share root, `/` — which is exactly what the pane's "go up" test needs:
        answering True for the bare `C:` would send the listing to the process's current
        directory of that drive, and answering False for `C:\\` would render a ".." row that
        cannot be resolved.
        """
        text = str(path or "")
        if not text:
            return False
        if self.is_local:
            if not os.path.isabs(text):
                return False
            return os.path.dirname(text) == text
        return text == "/"

    def is_absolute(self, path: str) -> bool:
        """Is `path` already anchored? `~` counts as absolute: it resolves to a home."""
        text = str(path or "")
        if text.startswith("~"):
            return True
        if self.is_local:
            return os.path.isabs(text)
        return text.startswith("/")

    def same(self, left: str, right: str) -> bool:
        """Are the two paths the SAME subject? Case-insensitively on the OS disk."""
        if self.is_local:
            return _win_standard_path(left) == _win_standard_path(right)
        return str(left or "") == str(right or "")

    def root(self) -> str:
        """The value a LOCAL pane opens with when nothing else is known — the OS home."""
        return os.path.expanduser("~") if self.is_local else "/"


#: The two dialects, declared ONCE (the pane resolves one from its source).
POSIX_PATHS = PathDialect(SOURCE_REMOTE, "/")
LOCAL_PATHS = PathDialect(SOURCE_LOCAL, os.sep)


def dialect_for(source: str) -> PathDialect:
    """The dialect of a pane's SOURCE (`SOURCE_REMOTE` unless the source really is local)."""
    return LOCAL_PATHS if str(source or "") == SOURCE_LOCAL else POSIX_PATHS


# ── The LOCAL provider's and the download's refusals, rendered ONCE ──────────
def local_error_text(message: str) -> str:
    """A LOCAL `task_error` payload → its translated sentence (a plain message passes through).

    The provider names the MACHINE code and the OS's own text (LOCAL_PANE.md §3); the sentence is
    the tab's, so a refusal reads like every other message of the window. A payload the tab does
    not know falls back to the shipped generic operation sentence.
    """
    data = parse_task_payload(message)
    if not data:
        return _t("sftp.op.error", error=message)
    code = str(data.get("code") or "")
    if code == local_fs.KIND_LIST_PARTIAL:
        return _t(local_fs.LOCAL_ERROR_KEYS[local_fs.KIND_LIST_PARTIAL],
                  count=int(data.get("count") or 0), names=str(data.get("names") or ""))
    key = local_fs.LOCAL_ERROR_KEYS.get(code)
    if not key:
        return _t("sftp.op.error", error=str(data.get("error") or message))
    return _t(key, error=str(data.get("error") or ""))


def name_refusal_text(message: str) -> str:
    """A NAME_ERROR_UNSAFE payload → its translated sentence; "" — another message (v1.7.5.1).

    ONE renderer for the two surfaces that can see the code (the pane's own message line and the
    session's status line), so a refused download name reads the same wherever it is reported.
    """
    data = parse_task_payload(message)
    if not data or str(data.get("code") or "") != NAME_ERROR_UNSAFE:
        return ""
    return _t("sftp.name_refused", name=str(data.get("name") or ""))


# ── The per-server directory memory (`ui_sftp_dirs`) ──────────────────

#: v1.7.3: the per-server directory memory. ONE key of `~/.sshmap/config.json` holds a map
#: `{server key: directory}` (`history_key()` is the key), written by the window's close and read
#: when a pane is built; the map outlives the servers it names, so it is BOUNDED and evicted
#: oldest-first. A restored path is a HINT: a directory the server refuses falls back to the
#: shipped opening rule with ONE status line.
DIRS_CONFIG = "ui_sftp_dirs"
MAX_REMEMBERED_DIRS = 32


def load_remembered_dirs() -> dict:
    """The per-server directory map from `~/.sshmap/config.json` ({} — nothing to restore).

    FOREIGN content answers `{}` rather than a guess (a string where a map is expected, an entry
    whose path is not absolute): a broken config must never navigate a pane anywhere. Never raises.
    """
    try:
        from i18n import load_config
    except Exception:  # noqa: BLE001 — a build without i18n keeps no memory
        return {}
    try:
        raw = (load_config() or {}).get(DIRS_CONFIG)
    except Exception:  # noqa: BLE001 — a broken config store must not break a pane
        return {}
    return sanitize_dirs(raw)


def sanitize_dirs(raw) -> dict:
    """The usable entries of a stored map: a string key and an ABSOLUTE path, or nothing."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, path in raw.items():
        name, value = str(key or ""), str(path or "")
        if name and value.startswith("/"):
            out[name] = value
    return out


def remember_dir(mapping, key, path, limit: int = MAX_REMEMBERED_DIRS) -> dict:
    """Move ONE `{server key: directory}` entry to the END, evicting the OLDEST over the cap (PURE).

    Insertion order IS the age, so the eviction needs no timestamp and the map stays a plain JSON
    object; a blank key or a relative path changes NOTHING (a remote directory is absolute).
    """
    out = dict(mapping or {})
    name, value = str(key or ""), str(path or "")
    if name and value.startswith("/"):
        out.pop(name, None)
        out[name] = value
    while len(out) > max(1, int(limit)):
        out.pop(next(iter(out)))
    return out


def remembered_dir_for(mapping, key) -> str:
    """The directory remembered for ONE server key ("" — never visited / no memory)."""
    try:
        return str((mapping or {}).get(str(key or "")) or "")
    except Exception:  # noqa: BLE001 — a foreign mapping is simply "no memory"
        return ""


# ── The cut fact, the row readers and the drag payload ───────────────────
def read_was_truncated(data_len, cap, known_size=0) -> bool:
    """PURE (N46): did a read stop at the pane's ceiling — i.e. is the tail cut?

    The listing's own size is the CERTAIN signal (`known_size > data_len` — the very condition the
    panel already reports as `sftp.viewer.truncated`); the ceiling is the fallback for a file the
    listing does not know, where a read that returned the whole cap can only have been cut. A file
    the listing measures as COMPLETE is never called truncated, whatever the cap is.
    """
    try:
        known = int(known_size or 0)
        length = int(data_len or 0)
    except (TypeError, ValueError):
        return False
    if known > 0:
        return known > length
    try:
        cap = int(cap or 0)
    except (TypeError, ValueError):
        return False
    return cap > 0 and length >= cap


def row_path(item) -> str:
    """The FULL path a listing row carries in its PATH_ROLE ("" — no role, a dead item). PURE."""
    try:
        return str(item.data(0, PATH_ROLE) or "")
    except (RuntimeError, AttributeError):
        return ""


def row_name(item) -> str:
    """The NAME a listing row sorts by — the basename of its PATH_ROLE, in EITHER dialect (PURE).

    The sort key is read off the ROLE and never off the widget text, so the comparison cannot be
    moved by a re-text pass; the split accepts both separators because a LOCAL row and a REMOTE one
    spell the same shape of path two ways (LOCAL_PANE.md §2).
    """
    path = row_path(item)
    for separator in ("/", "\\"):
        if separator in path:
            path = path.rsplit(separator, 1)[-1]
    if path:
        return path
    try:
        return str(item.text(0) or "")
    except (RuntimeError, AttributeError):
        return ""


def local_files(mime_data) -> list:
    """Existing local files from the dragged URLs. Directories, deleted/
    nonexistent paths, and non-file data — are skipped.

    A MODULE function (v1.7rc1): the drag payload is a property of a PANE and the
    container keeps the same name as a `staticmethod` because the shipped suite reads
    it off the CLASS (`SftpTab._local_files(mime)`).
    """
    out = []
    if mime_data is None or not mime_data.hasUrls():
        return out
    for url in mime_data.urls():
        if not url.isLocalFile():
            continue
        path = url.toLocalFile()
        if os.path.isfile(path):
            out.append(path)
    return out


def pane_payload(mime_data):
    """The `{session, pane, path}` payload of a drag that started inside a pane (None — foreign).

    A malformed payload (not JSON, not an object, no path) is a FOREIGN drag. The `source` field is
    the row's DIALECT (`source`, `size`): a local row and a remote one carry paths of two different
    spellings, so a drop resolves the basename with the dialect that really produced it.
    """
    if mime_data is None or not mime_data.hasFormat(PANE_DRAG_MIME):
        return None
    try:
        data = json.loads(bytes(mime_data.data(PANE_DRAG_MIME)).decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    path = str(data.get("path") or "")
    if not path:
        return None
    source = str(data.get("source") or SOURCE_REMOTE)
    try:
        size = int(data.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    return {"session": str(data.get("session") or ""), "pane": data.get("pane"), "path": path,
            "source": source if source in PANE_SOURCES else SOURCE_REMOTE, "size": size}


# ── The Files Commander's own settings (`ui_sftp_commander*`) ───────────────

# The state of the two-pane view lives in `~/.sshmap/config.json`, exactly like the terminal SPLIT's
# (`ui_terminal_split` / `ui_terminal_split_ratio`): ONE bool and ONE float, merged into the window's
# geometry write on close. The ratio is a FRACTION of the width, so a window resize keeps the proportion,
# and a foreign/broken value falls back to the default instead of squeezing a pane into unusability.
COMMANDER_CONFIG_BOOL = "ui_sftp_commander"          # bool — the mode was on at the last close
COMMANDER_CONFIG_RATIO = "ui_sftp_commander_ratio"   # float — the FIRST pane's share of the width
COMMANDER_RATIO_DEFAULT = 0.5
COMMANDER_RATIO_MIN = 0.2
COMMANDER_RATIO_MAX = 0.8

#: The narrowest a pane may be dragged, in pixels — installed as `setMinimumWidth`
#: while the mode is on (Qt gotcha #13 forbids `setMaximum*` on a splitter member) and
#: dropped again when it goes off, so the single-pane look costs no floor at all.
COMMANDER_MIN_PANE_PX = 200


def load_commander_settings():
    """v1.7rc1: the Files Commander state/ratio from ~/.sshmap/config.json.

    The `load_split_settings()` shape (§4.3): every key is optional, a foreign type (a
    string "true", a bool where a float is expected, a non-finite number) answers the
    DEFAULT — a broken config must never open a second pane or squeeze the two into
    unusability. Never raises. Returns `{"commander": bool, "ratio": float}`.
    """
    defaults = {"commander": False, "ratio": COMMANDER_RATIO_DEFAULT}
    try:
        from i18n import load_config
    except Exception:  # noqa: BLE001 — a build without i18n keeps the defaults
        return dict(defaults)
    try:
        cfg = load_config()
    except Exception:  # noqa: BLE001 — a broken config store must not break the tab
        return dict(defaults)

    v = cfg.get(COMMANDER_CONFIG_BOOL)
    if isinstance(v, bool):
        defaults["commander"] = v

    v = cfg.get(COMMANDER_CONFIG_RATIO)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            ratio = float(v)
        except (TypeError, ValueError):
            ratio = COMMANDER_RATIO_DEFAULT
        if ratio == ratio and ratio not in (float("inf"), float("-inf")):  # not NaN/inf
            defaults["ratio"] = max(COMMANDER_RATIO_MIN, min(COMMANDER_RATIO_MAX, ratio))
    return defaults
