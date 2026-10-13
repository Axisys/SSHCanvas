# -*- coding: utf-8 -*-
"""The command guard — ONE PURE classifier over a FINAL command string, and ONE confirmation per RUN.

The gate sits where the LAST chance to notice a mistake is: the run's own boundary
(`PluginManager._start_command_run()`, so both the core's "Run a command on servers…" door and every
plugin's `ctx.run_command()` pass it) and the `Enter` that SUBMITS a multi-input line. The policy is the
boolean `guard_commands` of `~/.sshmap/config.json` — CONFIG and never the project — and its default is
ON: a false positive costs one dialog, a false negative costs the fleet. It is a CONFIRMATION and never a
lock. A line over `MAX_COMMAND_CHARS` is REFUSED, never read up to the bound. `dangerous_token()` /
`needs_confirmation()` / `guard_enabled()` / `excerpt()` are PURE; the dialog is the module attribute
seam and a guard that cannot ask REFUSES. Rule and owner — `AGENTS.md` §4.30; mechanism —
`DOCUMENTATION.md` §74.
"""

import re

try:  # pragma: no cover — Qt is a hard dependency of the application
    from PySide6.QtWidgets import QMessageBox
except ImportError:
    QMessageBox = None

from i18n import load_config, t

GUARD_COMMANDS_KEY = "guard_commands"   # the policy: the guard is ON unless the user turns it off
MAX_COMMAND_CHARS = 4096                # the classification's input bound — over it the line is REFUSED
SHOWN_CHARS = 200                       # the excerpt the dialog prints

#: The words a shell puts IN FRONT of the real command (they are skipped, never matched).
WRAPPERS = ("sudo", "doas", "env", "nohup", "time", "xargs", "watch")
REBOOT_WORDS = ("reboot", "shutdown", "halt", "poweroff")
#: The runlevel spelling of the same action: the WORD alone is harmless (`init 3` switches a runlevel),
#: so it needs its TARGET — the shipped `dd` / `kill` rule, never a bare word match.
INIT_WORDS = ("init", "telinit")
INIT_TARGETS = ("0", "6", "-r")         # power-off, reboot, and the flag spelling of "reboot"
PARTITION_WORDS = ("fdisk", "parted", "diskpart")
KILL_WORDS = ("kill", "pkill", "killall")
REMOVE_WORDS = ("remove",)              # the package managers' own verb (`apt remove`)
MKFS_WORD = "mkfs"                      # the family's shortest spelling (`mkfs`, `mkfs.ext4`, …)

#: The POSITIONAL interpreter table: the words that put a COMMAND inside an ARGUMENT, and WHERE.
#: A quoted run is an argument (the quote-aware split) unless this table names the position that holds
#: a command — a shell's `-c` payload, `eval`'s first argument, the `ssh <target> <command>` shape.
#: `sh run.sh` and `python -c "…"` are DELIBERATELY absent: a file indirection and a foreign payload
#: are declared blind spots, never chased with word lists (`AGENTS.md` §4.30).
INTERPRETER_WORDS = ("sh", "bash", "dash", "zsh", "ksh")
COMMAND_FLAG = "c"                      # the short flag cluster that carries the payload (`-c`, `-lc`)
SSH_WORD = "ssh"
MAX_NESTED_DEPTH = 2                    # `bash -c "sh -c '…'"` is the second level; a third is not chased

#: The `ssh` options that carry a SEPARATE value (`-p 2222`, `-o ProxyCommand`, `-i key`, `-J jump`):
#: the positional reading steps over the flag AND its value, so the TARGET is the first real
#: positional and the command is everything after it. A bare flag needs no entry — the leading dash
#: skips it. An option this table cannot know is the reading's one declared uncertainty, and there it
#: stays GENEROUS (an earlier payload) rather than silent (`AGENTS.md` §4.30).
SSH_VALUE_FLAGS = ("-b", "-c", "-D", "-e", "-F", "-i", "-J", "-L", "-l", "-m", "-O", "-o", "-p",
                   "-Q", "-R", "-S", "-W", "-w")

TOKEN_RM = "rm -rf"                     # the danger is the FLAG PAIR, so the token is the shape
TOKEN_DD = "dd"
TOKEN_KILL = "kill -9"
TOKEN_KILL_ONE = "kill -1"
TOKEN_FORK_BOMB = "fork bomb"
#: The token of a line the classifier REFUSES to read: `MAX_COMMAND_CHARS` is a bound, and a bound
#: that silently drops the rest of a line is exactly the hole `N99` found (the guard read the head
#: while the submission buffer keeps the tail). A refusal costs one dialog; a skipped tail costs a
#: fleet, so the over-long line IS the finding (AGENTS.md §4.30).
TOKEN_OVER_LONG = "input too long"

#: The families the classifier knows. The token it answers is the MATCHED spelling (`shutdown`,
#: `mkfs.ext4`, …) except where the danger is a flag pair or a shape (`rm -rf`, `kill -9`, `fork bomb`).
FAMILIES = ("reboot", "init", "rm", "remove", "mkfs", "dd", "wipefs", "partition", "userdel", "kill",
            "fork_bomb")

_SEGMENT_SPLIT_RE = re.compile(r"[;|&\n\r()`]+")
#: The self-replicating function definition, BOTH spellings: `name() { … }` and bash's
#: `function name { … }` — the name is group 1 and the body group 2 in either one.
_FUNCTION_RE = re.compile(r"(?:function)?([:\w]+)(?:\(\))?\{([^}]*)\}")


def _text(value) -> str:
    """One value as a stripped string (a foreign type → "" — never an exception)."""
    try:
        return str(value if value is not None else "")
    except Exception:  # noqa: BLE001 — a broken __str__ is "no command"
        return ""


def _squash(text: str) -> str:
    """The text without ANY whitespace — the normalised form the shape families are read in."""
    return re.sub(r"\s+", "", text)


def _basename(word: str) -> str:
    """The lower-cased last path component of a word (`/sbin/reboot` and `sudo` → `reboot`, `sudo`)."""
    return word.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _words(segment: str) -> list:
    """A segment's words, QUOTE-AWARE: a quoted run is ONE word (its quotes dropped)."""
    out, token, quote, index = [], [], "", 0
    while index < len(segment):
        ch = segment[index]
        if quote:
            if ch == quote:
                quote = ""
            else:
                token.append(ch)
        elif ch in "\"'":
            quote = ch
        elif ch == "\\" and index + 1 < len(segment):
            index += 1
            token.append(segment[index])
        elif ch.isspace():
            if token:
                out.append("".join(token))
                token = []
        else:
            token.append(ch)
        index += 1
    if token:
        out.append("".join(token))
    return out


def _segments(command: str) -> list:
    """The command split on the shell separators (`;`, `|`, `&`, a newline, a parenthesis, a backtick)."""
    return [part for part in _SEGMENT_SPLIT_RE.split(command) if part.strip()]


def _flag_cluster(word: str) -> str:
    """The letters of a SHORT flag cluster (`-rfv` → `rfv`); "" for a long flag or a plain word."""
    if not word.startswith("-") or word.startswith("--"):
        return ""
    return word[1:]


def _has_recursive(words) -> bool:
    """Is a recursive flag among the segment's words (`-r`, `-R`, `-rf`, `--recursive`)? PURE."""
    for word in words:
        if word in ("-r", "-R", "--recursive"):
            return True
        cluster = _flag_cluster(word)
        if cluster and ("r" in cluster or "R" in cluster):
            return True
    return False


def _has_force(words) -> bool:
    """Is a force flag among the segment's words (`-f`, `-rf`, `--force`)? PURE."""
    for word in words:
        if word in ("-f", "--force"):
            return True
        cluster = _flag_cluster(word)
        if cluster and "f" in cluster:
            return True
    return False


def _dd_target(rest) -> bool:
    """Does `dd` write to a DEVICE (`of=/dev/…`, `of=/dev/null` excluded)? PURE."""
    for word in rest:
        low = word.lower()
        if low.startswith("of=/dev/"):
            return low.split("of=", 1)[1].rstrip("/") != "/dev/null"
    return False


def _kill_token(words) -> str:
    """The token of a `kill` naming a fatal signal (`-9`/`-KILL`) or the whole-table target (`-1`)."""
    low = [word.lower() for word in words]
    for index, word in enumerate(low):
        if word in ("-1",):
            return TOKEN_KILL_ONE
        if word in ("-9", "-kill", "-sigkill"):
            return TOKEN_KILL
        if word in ("-s", "--signal") and index + 1 < len(low):
            nxt = low[index + 1].lstrip("-")
            if nxt in ("9", "kill", "sigkill"):
                return TOKEN_KILL
            if nxt in ("1", "hup"):
                return TOKEN_KILL_ONE
    return ""


def _fork_bomb(text: str) -> bool:
    """The whitespace-normalised SELF-REPLICATING function (`:(){ :|:& };:` and its re-spellings).

    Both spellings of the definition count: the POSIX `name() { … }` and bash's `function name { … }`,
    which the `_FUNCTION_RE` reads as the same shape (`N99`). The body must call the name and carry
    BOTH the pipe and the background operator — the two parents that make it a bomb.
    """
    for match in _FUNCTION_RE.finditer(text):
        name, body = match.group(1), match.group(2)
        if name and name in body and "|" in body and "&" in body:
            return True
    return False


def _init_target(base: str, rest) -> str:
    """The token of an `init` / `telinit` whose TARGET really is a reboot — "" otherwise. PURE.

    The rule is `dd`'s own: the word alone is not the danger. The FIRST positional argument is the
    runlevel (`init 3` is a plain switch), while `0` / `6` / `-r` are the power-off and the reboot.
    """
    for word in rest:
        low = word.lower()
        if low in INIT_TARGETS:
            return base
        if not low.startswith("-"):
            return ""       # the first positional is the runlevel — anything else is not a reboot
    return ""


def _flag_carries(word: str, letter: str) -> bool:
    """Is the word a SHORT flag cluster carrying `letter` (`-c`, `-lc`, `-ec`)? PURE."""
    if not word.startswith("-") or word.startswith("--"):
        return False
    return letter in word[1:]


def _ssh_command(rest) -> str:
    """The command of an `ssh <target> <command>` segment — "" for a plain connect. PURE.

    The reading is STRUCTURAL, not positional-by-luck: `SSH_VALUE_FLAGS` are stepped over WITH the
    value they carry, so `ssh -p 2222 host '…'` and `ssh -o ProxyCommand nc host '…'` both answer
    `host` as the TARGET and the words after it as the command. The command keeps its own FLAGS
    (`ssh host rm -rf /` reads `rm -rf /`), which is what the recursion classifies.
    """
    positionals, index = [], 0
    while index < len(rest):
        word = rest[index]
        if not word.startswith("-"):
            break                       # the TARGET is here — everything after it is the command
        index += 2 if word in SSH_VALUE_FLAGS else 1
    positionals = rest[index:]
    return " ".join(positionals[1:]) if len(positionals) > 1 else ""


def _nested_commands(words) -> list:
    """The arguments of ONE segment that ARE a command — the POSITIONAL interpreter table. PURE.

    Each entry is the payload a recursive pass classifies: a shell's `-c` argument, `eval`'s first
    argument and the command of `ssh <target> <command>` (`_ssh_command()`). A shell WITHOUT `-c`
    runs a FILE, and a payload of another language is not guessed: both stay the declared blind
    spots of `AGENTS.md` §4.30.
    """
    out = []
    for index, word in enumerate(words):
        base = _basename(word)
        rest = words[index + 1:]
        if base == "eval":
            payload = " ".join(w for w in rest if not w.startswith("-"))
        elif base in INTERPRETER_WORDS:
            payload = " ".join(rest[i + 1] for i, w in enumerate(rest)
                               if i + 1 < len(rest) and _flag_carries(w, COMMAND_FLAG))
        elif base == SSH_WORD:
            payload = _ssh_command(rest)
        else:
            continue
        if payload:
            out.append(payload)
    return out


def _segment_token(words) -> str:
    """The token of ONE segment — the FIRST destructive word (or flag pair / shape) it carries."""
    for index, word in enumerate(words):
        base = _basename(word)
        if base in REBOOT_WORDS or base in PARTITION_WORDS or base in REMOVE_WORDS:
            return base
        if base in INIT_WORDS:
            token = _init_target(base, words[index + 1:])
            if token:
                return token
        if base in ("wipefs", "userdel"):
            return base
        if base == MKFS_WORD or base.startswith("mkfs."):
            return base
        if base == "dd" and _dd_target(words[index + 1:]):
            return TOKEN_DD
        if base == "rm" and _has_recursive(words) and _has_force(words):
            return TOKEN_RM
        if base in KILL_WORDS:
            token = _kill_token(words)
            if token:
                return token
    return ""


def _scan(text: str, depth: int) -> str:
    """The token of the first destructive shape of ONE string, its NESTED payloads included.

    Every string this reads goes through `_bound_problem()` FIRST, so a nested payload can no more be
    silently truncated than the top-level line can (`N99`).
    """
    if _bound_problem(text):
        return TOKEN_OVER_LONG
    for segment in _segments(text):
        words = _words(segment)
        while words and _basename(words[0]) in WRAPPERS:   # a wrapper is never the command
            words = words[1:]
        token = _segment_token(words)
        if token:
            return token
        if depth >= MAX_NESTED_DEPTH:
            continue
        for nested in _nested_commands(words):
            token = _scan(nested, depth + 1)
            if token:
                return token
    return ""


def _bound_problem(command) -> str:
    """`TOKEN_OVER_LONG` when the string is past `MAX_COMMAND_CHARS` — the ONE bound of the classifier.

    PURE. `None` and a foreign value are empty strings (the shortest answer there is); the count is of
    the string's own characters, never of its stripped form, so trailing whitespace cannot hide a line
    that is over the bound.
    """
    return TOKEN_OVER_LONG if len(_text(command)) > MAX_COMMAND_CHARS else ""


def dangerous_token(command) -> str:
    """The token of the first destructive shape in a FINAL command string; "" when nothing matched.

    PURE and it never raises: a foreign value and a broken quote are "no match". A string over
    `MAX_COMMAND_CHARS` is `TOKEN_OVER_LONG` — the line is REFUSED rather than read up to the bound,
    which is what makes the bound a policy instead of a blind spot. The match is DELIBERATELY generous
    — a destructive word is looked for at ANY word position of ANY segment, so a `git`/`docker` prefix,
    a wrapper or a pipeline never hides it — because a false positive costs one dialog. The POSITIONAL
    interpreter table adds the payload a quoted argument hides (`bash -c "…"`, `eval "…"`,
    `ssh host '…'`) without re-opening the shipped `echo "rm -rf /"` false positive.
    """
    text = _text(command)
    bound = _bound_problem(text)
    if bound:
        return bound
    if not text.strip():
        return ""
    if _fork_bomb(_squash(text)):
        return TOKEN_FORK_BOMB
    return _scan(text, 0)


def guard_enabled(cfg=None) -> bool:
    """Is the command guard armed? — the CONFIG boolean `guard_commands`, ON by default.

    A missing key, a foreign type and an unreadable store all answer the declared default (True): the
    guard exists for the user who never read a document, so only an explicit `false` turns it off.
    """
    cfg = load_config() if cfg is None else cfg
    try:
        value = cfg.get(GUARD_COMMANDS_KEY)
    except Exception:  # noqa: BLE001 — a broken store keeps the declared default
        return True
    return value if isinstance(value, bool) else True


def needs_confirmation(command, cfg=None) -> str:
    """The token that makes a command ask before it runs — "" when it may go ahead. PURE."""
    if not guard_enabled(cfg):
        return ""
    return dangerous_token(command)


def excerpt(command) -> str:
    """The command as the dialog prints it: one line, capped at `SHOWN_CHARS`. PURE."""
    text = " ".join(_text(command).split())
    return text if len(text) <= SHOWN_CHARS else text[:SHOWN_CHARS] + "…"


def confirmation_text(command, token, count=1) -> str:
    """The RUN's ONE sentence (`guard.command.text`). PURE."""
    return t("guard.command.text", command=excerpt(command), token=str(token), count=int(count or 1))


def broadcast_text(line, token, count=1) -> str:
    """The multi-input submission's ONE sentence (`guard.command.broadcast`). PURE."""
    return t("guard.command.broadcast", command=excerpt(line), token=str(token),
             count=int(count or 1))


def _ask(text: str, parent=None) -> bool:
    """The ONE dialog: a `QMessageBox` whose DEFAULT button is No, the module attribute being the seam.

    A build that cannot show a dialog answers False — the guard is a REFUSAL by default, never a silent
    pass; `parent=None` is legal Qt and therefore still asked.
    """
    if QMessageBox is None:
        return False
    try:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(t("guard.title"))
        box.setText(str(text))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes
    except Exception:  # noqa: BLE001 — a dialog that cannot open never green-lights a command
        return False


def confirm(command, token, count=1, plugin_id="", parent=None) -> bool:
    """The RUN's question — ONE dialog per run, the node count NAMED in it. True when confirmed.

    `plugin_id` is accepted for the caller's sake (the sentence names the count, never the author's
    strings) and is deliberately not printed: the dialog shows the MATCHED token and the command.
    """
    return _ask(confirmation_text(command, token, count=count), parent)


def confirm_broadcast(line, token, count=1, parent=None) -> bool:
    """The multi-input submission's question — ONE dialog per `Enter`. True when confirmed."""
    return _ask(broadcast_text(line, token, count=count), parent)
