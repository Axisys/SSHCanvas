# -*- coding: utf-8 -*-
"""v1.10rc2 — the leftovers the `1.10rc1` slot recorded: the marshalled send path, the PTY's
`TERM` key and the `ssh <target> <command>` positional reading.
§1 the input point PARKS and WAKES while the session thread is the ONE channel writer (N92);
§2 the `terminal_term` key — its allowlist, its settings row and the entry the PTY really asks for;
§3 the `ssh` reading over the declared option-value table (N85); §4 the release state.
Rule — `AGENTS.md` §4.3, §4.4, §4.30; mechanism — `DOCUMENTATION.md` §64, §74.
"""
import inspect
import os
import sys
import threading
import time

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, docs_mode, finish,
                     load_i18n_langs, releases_at_least, rep_doc_text, wait_for, wait_until, write_cfg)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import paramiko  # noqa: E402
import i18n  # noqa: E402
import modules.command_guard as CG  # noqa: E402
import modules.ssh_terminal as ST  # noqa: E402
import modules.terminal_config as TC  # noqa: E402
from ui.settings_dialog import SettingsDialog  # noqa: E402


def _read(*parts) -> str:
    """The text of a repository file that SHIPS (the source audits below read several)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _func_source(owner, name) -> str:
    """The source of ONE function of a class/module — the seam the source audits read."""
    return inspect.getsource(getattr(owner, name))


def _code(owner, name) -> str:
    """The CODE of one function, its DOCSTRING dropped (the prose names what the body must not do)."""
    src = _func_source(owner, name)
    first = src.find('"""')
    if first >= 0:
        end = src.find('"""', first + 3)
        if end >= 0:
            src = src[:first] + src[end + 3:]
    return src


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the marshalled send path: the GUI thread PARKS, the session thread WRITES (N92) ==")
# ════════════════════════════════════════════════════════════════════════════


class _CountingChannel:
    """A channel that records what it was asked to write (the ONE writer's seam)."""

    closed = False

    def __init__(self, window=1 << 20):
        self.buffer = bytearray()
        self.window = window
        self.calls = 0

    def send_ready(self):
        return self.window > 0

    def send(self, data):
        self.calls += 1
        chunk = bytes(data)[:self.window]
        self.buffer.extend(chunk)
        self.window -= len(chunk)
        return len(chunk)


_ch = _CountingChannel()
_thread = ST.SSHTerminalThread("h", "u", 22)
_thread.channel = _ch
_errors = []
_thread.error_signal.connect(_errors.append)
_thread.send_data(b"typed on the GUI thread")
check("§1 `send_data()` writes NOTHING — the payload is PARKED, in order, and the loop is WOKEN",
      _ch.calls == 0 and bytes(_thread._pending) == b"typed on the GUI thread"
      and _thread._wake.is_set() and _errors == [],
      f"calls={_ch.calls} parked={len(_thread._pending)}")
check("§1 ...and the ONE writer is the session thread's drain (the channel is then written once)",
      "channel.send(" not in _code(ST.SSHTerminalThread, "send_data")
      and "channel.send(" in _code(ST.SSHTerminalThread, "_write_all")
      and _thread._flush_pending() is True and bytes(_ch.buffer) == b"typed on the GUI thread",
      f"calls={_ch.calls} delivered={len(_ch.buffer)}")
check("§1 the FIFO survives two parks (a keystroke behind a paste never overtakes it)",
      (_thread.send_data(b"AAA"), _thread.send_data(b"BBB"),
       _thread._flush_pending())[-1] is True
      and bytes(_ch.buffer).endswith(b"AAABBB"),
      repr(bytes(_ch.buffer)[-12:]))
_loop_src = _func_source(ST.SSHTerminalThread, "run")
check("§1 the drain sits at the TOP of the receive loop (output can never starve a keystroke)",
      "moved = self._flush_pending()" in _loop_src
      and 0 <= _loop_src.index("moved = self._flush_pending()")
      < _loop_src.index("if self.channel.recv_ready():")
      and "_wake.wait(0.03)" in _loop_src,
      f"drain@{_loop_src.find('moved = self._flush_pending()')} "
      f"recv@{_loop_src.find('if self.channel.recv_ready():')}")

_stopped = ST.SSHTerminalThread("h", "u", 22)
_stopped.channel = _CountingChannel()
_stopped._wake.clear()
_stopped.stop()
check("§1 `stop()` wakes a sleeping loop instead of making it wait out its 30 ms",
      _stopped.running is False and _stopped._wake.is_set())

_closed = ST.SSHTerminalThread("h", "u", 22)
_closed.send_data(b"nowhere to go")
_dead_channel = _CountingChannel()
_dead_channel.closed = True
_closed.channel = _dead_channel
_closed.send_data(b"the channel is gone")
check("§1 a missing or closed channel is a quiet no-op (nothing parked, another channel never asked)",
      not _closed._pending and _dead_channel.calls == 0,
      f"parked={len(_closed._pending)} calls={_dead_channel.calls}")


class _LiveChannel(_CountingChannel):
    """A channel of a session that STAYS open: nothing to read, nothing announced."""

    eof_received = False

    def settimeout(self, _timeout):
        pass

    def recv_ready(self):
        return False

    def recv(self, _n):                      # pragma: no cover — the loop never gets here
        return b""

    def exit_status_ready(self):
        return False

    def close(self):
        self.closed = True


class _FakeTransport:
    def set_keepalive(self, _seconds):
        pass

    def close(self):
        pass


class _FakeClient:
    """The `paramiko.SSHClient` double of the driven session (test_terminal_truth's pattern)."""

    def __init__(self, channel):
        self._channel = channel
        self.shell_kwargs = {}

    def connect(self, *args, **kwargs):
        pass

    def set_missing_host_key_policy(self, _policy):
        pass

    def load_system_host_keys(self):
        pass

    def invoke_shell(self, **kwargs):
        self.shell_kwargs = kwargs
        return self._channel

    def get_transport(self):
        return _FakeTransport()

    def close(self):
        pass


_orig_client_cls = paramiko.SSHClient
_live = _LiveChannel()
_client = _FakeClient(_live)
paramiko.SSHClient = lambda *a, **kw: _client
_session = ST.SSHTerminalThread("h", "u", 22)
_runner = threading.Thread(target=_session.run, daemon=True)
try:
    _runner.start()
    wait_until(lambda: _session.channel is not None, timeout_ms=2000)
    _live.window = 1 << 20
    _session._pending.clear()               # the connect path owns nothing here
    _t0 = time.monotonic()
    _session.send_data(b"ls\n")
    _delivered = wait_for(lambda: bytes(_live.buffer) == b"ls\n", timeout_ms=2000)
    _latency = time.monotonic() - _t0
    check("§1 a REAL session loop delivers a parked keystroke (the marshalled path end to end)",
          _delivered and bytes(_live.buffer) == b"ls\n",
          f"delivered={bytes(_live.buffer)!r}")
    check("§1 ...and the wake makes it immediate, not a 30 ms poll tick",
          _latency < 0.25, f"{_latency * 1000:.1f} ms")
    check("§1 ...with the PTY asked for the shipped default while no key is set",
          _client.shell_kwargs.get("term") == ST.TERMINAL_TYPE == "xterm-256color"
          and _client.shell_kwargs.get("width") == 120,
          str(_client.shell_kwargs))
finally:
    _session.stop()
    _runner.join(timeout=2.0)
    paramiko.SSHClient = _orig_client_cls
check("§1 the loop really ended on `stop()` (a session that is told to stop stops)",
      not _runner.is_alive(), "the runner thread outlived the budget")


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the PTY's `TERM` is ONE key with ONE allowlist (`terminal_term`) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 the key, its default, its presets and its allowlist are declared ONCE",
      TC.TERM_CONFIG_KEY == "terminal_term" and TC.TERM_DEFAULT == "xterm-256color"
      and TC.TERM_PRESETS[0] == TC.TERM_DEFAULT and ST.TERMINAL_TYPE == TC.TERM_DEFAULT
      and TC.TERM_NAME_PATTERN == r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}",
      f"{TC.TERM_CONFIG_KEY} {TC.TERM_PRESETS}")

_TERMS = [(None, "xterm-256color"), (7, "xterm-256color"), (True, "xterm-256color"),
          ("", "xterm-256color"), ("   ", "xterm-256color"), ("vt100", "vt100"),
          ("  vt100  ", "vt100"), ("screen-256color", "screen-256color"), ("tmux-256color", "tmux-256color"),
          ("linux", "linux"), ("xterm-256color", "xterm-256color"), ("a" * 64, "a" * 64),
          ("a" * 65, "xterm-256color"), ("bad name", "xterm-256color"), ("a/b", "xterm-256color"),
          ("xterm;rm -rf /", "xterm-256color"), ("хterm", "xterm-256color")]
check("§2 `resolve_term()` is the ONE predicate: a terminfo NAME or the declared default",
      [TC.resolve_term(v) for v, _w in _TERMS] == [w for _v, w in _TERMS],
      str([TC.resolve_term(v) for v, _w in _TERMS]))

clear_cfg()
check("§2 no config → the declared default (a broken store can never move the PTY)",
      TC.load_terminal_settings()["term"] == TC.TERM_DEFAULT)
write_cfg({TC.TERM_CONFIG_KEY: " screen-256color "})
check("§2 the key is read and trimmed", TC.load_terminal_settings()["term"] == "screen-256color")
write_cfg({TC.TERM_CONFIG_KEY: "not a term!!"})
check("§2 an unusable value → the declared default (the allowlist judges the config too)",
      TC.load_terminal_settings()["term"] == TC.TERM_DEFAULT)
write_cfg({TC.TERM_CONFIG_KEY: 7})
check("§2 a foreign TYPE → the declared default", TC.load_terminal_settings()["term"] == TC.TERM_DEFAULT)

write_cfg({TC.TERM_CONFIG_KEY: "tmux-256color"})
_hub = SettingsDialog(None)
check("§2 the `Terminal` tab carries the row: EDITABLE, prefilled, with the declared presets",
      _hub.term_combo.isEditable() and _hub.term_combo.currentText() == "tmux-256color"
      and tuple(_hub.term_combo.itemText(i) for i in range(_hub.term_combo.count()))
      == TC.TERM_PRESETS,
      _hub.term_combo.currentText())
_hub.term_combo.setEditText("vt100")
check("§2 `collect()` writes what the field carries and the hub is at 27 keys",
      _hub.collect()["terminal_term"] == "vt100" and len(_hub.collect()) == 27,
      str(len(_hub.collect())))
_validator = _hub.term_combo.lineEdit().validator()
check("§2 the field carries the SAME allowlist, anchored (a byte the rule forbids never enters)",
      _validator is not None
      and str(_validator.validate("vt100", 5)[0]).endswith("Acceptable")
      and str(_validator.validate("vt100/", 6)[0]).endswith("Invalid")
      and str(_validator.validate("bad name", 8)[0]).endswith("Invalid")
      and str(_validator.validate("", 0)[0]).endswith("Intermediate"),
      str(_validator.validate("vt100/", 6)[0]) if _validator else "no validator")
_hub.term_combo.setEditText("rm -rf")
check("§2 a value the allowlist refuses answers the DEFAULT on collect() (never a raw string)",
      _hub.collect()["terminal_term"] == TC.TERM_DEFAULT, _hub.collect()["terminal_term"])
_hub.close()

class _ClosingChannel(_LiveChannel):
    """A session that ends at once: the PTY is asked for its entry and the loop leaves."""

    def exit_status_ready(self):
        return True


write_cfg({TC.TERM_CONFIG_KEY: "vt100"})
_wire = _ClosingChannel()
_wire_client = _FakeClient(_wire)
paramiko.SSHClient = lambda *a, **kw: _wire_client
try:
    ST.SSHTerminalThread("h", "u", 22).run()
finally:
    paramiko.SSHClient = _orig_client_cls
check("§2 a session with NO explicit name asks the PTY for the CONFIGURED entry",
      _wire_client.shell_kwargs.get("term") == "vt100", str(_wire_client.shell_kwargs.get("term")))
_wire2 = _ClosingChannel()
_wire_client2 = _FakeClient(_wire2)
paramiko.SSHClient = lambda *a, **kw: _wire_client2
try:
    ST.SSHTerminalThread("h", "u", 22, term="linux").run()
finally:
    paramiko.SSHClient = _orig_client_cls
check("§2 ...and an EXPLICIT argument wins over the key (the additive constructor argument)",
      _wire_client2.shell_kwargs.get("term") == "linux",
      str(_wire_client2.shell_kwargs.get("term")))
clear_cfg()
check("§2 the store is back to the declared default after the probe",
      TC.load_terminal_settings()["term"] == TC.TERM_DEFAULT)

_langs = load_i18n_langs(ROOT)
check("§2 the row's label is translated in every language (the key, never a literal)",
      all(str(data.get("settings.terminal.term") or "").strip() for data in _langs.values())
      and i18n.t("settings.terminal.term") != "settings.terminal.term",
      str({c: bool(d.get("settings.terminal.term")) for c, d in _langs.items()}))


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the `ssh <target> <command>` reading is STRUCTURAL (N85) ==")
# ════════════════════════════════════════════════════════════════════════════

check("§3 the options that carry a SEPARATE value are declared once",
      "-o" in CG.SSH_VALUE_FLAGS and "-p" in CG.SSH_VALUE_FLAGS and "-i" in CG.SSH_VALUE_FLAGS
      and "-J" in CG.SSH_VALUE_FLAGS and "-l" in CG.SSH_VALUE_FLAGS
      and all(f.startswith("-") and not f.startswith("--") for f in CG.SSH_VALUE_FLAGS),
      str(CG.SSH_VALUE_FLAGS))

_SSH_SHAPES = [("ssh host reboot", "reboot"),
               ("ssh prod 'sudo systemctl reboot'", "reboot"),
               ("ssh -p 2222 host 'kill -9 1'", "kill -9"),
               ("ssh -o ProxyCommand nc host reboot", "reboot"),
               ("ssh -o ProxyCommand=nc host reboot", "reboot"),
               ("ssh -l root -p 22 host 'rm -rf /'", "rm -rf"),
               ("ssh -i key.pem deploy@host 'sudo reboot'", "reboot"),
               ("ssh -J jump host reboot", "reboot"),
               ("ssh -F /tmp/cfg host reboot", "reboot"),
               ("ssh -b 10.0.0.1 -c aes128-ctr -m hmac-sha2-256 host reboot", "reboot"),
               ("ssh -D 1080 -w 0:1 -e none host reboot", "reboot"),
               ("ssh -L 8080:localhost:80 -R 9090:localhost:90 host reboot", "reboot"),
               ("ssh -S /tmp/sock -O check host reboot", "reboot"),
               ("ssh -4 -v host reboot", "reboot"),
               ("ssh -p 2222 host rm -rf /", "rm -rf"),
               ("ssh deploy@10.0.0.5 'systemctl poweroff'", "poweroff"),
               ("ssh host", ""),
               ("ssh -p 2222 host", ""),
               ("ssh host uptime", "")]
check("§3 every declared option shape names the command after the TARGET",
      [CG.dangerous_token(c) for c, _w in _SSH_SHAPES] == [w for _c, w in _SSH_SHAPES],
      str([CG.dangerous_token(c) for c, _w in _SSH_SHAPES]))
check("§3 the payload KEEPS the command's own flags (`rm -rf /`, never a stripped `rm /`)",
      CG._ssh_command(["host", "rm", "-rf", "/"]) == "rm -rf /"
      and CG._ssh_command(["-p", "2222", "host", "rm", "-rf", "/"]) == "rm -rf /"
      and CG._ssh_command(["host"]) == "" and CG._ssh_command(["-p", "2222", "host"]) == "",
      repr(CG._ssh_command(["-p", "2222", "host", "rm", "-rf", "/"])))
check("§3 an option the table cannot know keeps the reading GENEROUS (an earlier payload)",
      CG._ssh_command(["weird", "host", "reboot"]) == "host reboot"
      and CG.dangerous_token("ssh --foreign host reboot") == "reboot",
      repr(CG._ssh_command(["weird", "host", "reboot"])))
check("§3 the shipped false positives stay arguments (a quoted run is still ONE word)",
      [CG.dangerous_token(c) for c in ('echo "rm -rf /"', "echo reboot",
                                       'printf "%s" "mkfs /dev/sdb"')] == ["", "reboot", ""],
      str([CG.dangerous_token(c) for c in ('echo "rm -rf /"', "echo reboot",
                                           'printf "%s" "mkfs /dev/sdb"')]))
check("§3 the nested reading is BOUNDED and never raises (a huge payload included)",
      CG.dangerous_token('ssh host "sh -c \'rm -rf /\'"') == "rm -rf"
      and CG.dangerous_token("ssh host " + "x" * 200000) == CG.TOKEN_OVER_LONG
      and CG.dangerous_token(None) == "" and CG.dangerous_token(7) == ""
      and CG.MAX_NESTED_DEPTH == 2,
      repr(CG.dangerous_token('ssh host "sh -c \'rm -rf /\'"')))
check("§3 the interpreter family is untouched (the payload of `-c` and `eval` still recurses)",
      [CG.dangerous_token(c) for c in ('bash -c "rm -rf /tmp/x"', 'eval "shutdown -h now"',
                                       "dash -lc 'mkfs.ext4 /dev/sda1'")]
      == ["rm -rf", "shutdown", "mkfs.ext4"],
      str([CG.dangerous_token(c) for c in ('bash -c "rm -rf /tmp/x"', 'eval "shutdown -h now"')]))


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_release_state(ROOT)
check("§4 the pin names this line's release or a later one (this slot rides on the same code)",
      releases_at_least(EXPECTED_APP_VERSION, "1.10"),
      EXPECTED_APP_VERSION)
check("§4 the schema did NOT move and no new dependency arrived (three code tasks, one key)",
      __import__("version").VERSION_FORMAT == "0.9"
      and all(f"{d}>=" in _read("requirements.txt")
              for d in ("PySide6", "paramiko", "keyring", "wcwidth")))
check("§4 the ONE new key is on the pin (1093 + the TERM row) and the hub collects 27",
      EXPECTED_I18N_KEYS == 1093 + 1 + 10 + 10 + 3 + 1 + 4)
check_i18n_parity(_langs)
check_i18n_format(_langs)
check("§4 the topical file is listed by the suite map (tests/INDEX.md regenerated)",
      "test_leftovers_v110rc2" in _read("tests", "INDEX.md"))
_ledger = rep_doc_text("AUDIT_PENDING.md")
if docs_mode():
    check("§4 the ledger holds NO open entry (all three candidates were DECISIONS, not defects)",
          "The entries above are the `1.10` line's first batch" in _ledger)

finish()
