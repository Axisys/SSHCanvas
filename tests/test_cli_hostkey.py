# -*- coding: utf-8 -*-
"""v1.15.1 — `hostkey verify`: the pins of `known_hosts` checked against the servers, and the rotation report.
§1 the subcommand grammar and the registry; §2 the PURE core (the row model, the endpoint grouping, the
four verdicts); §3 the verb over a REAL isolated store and IN-PROCESS paramiko servers (ok / changed /
unverified / unreachable, the exit verdict, the pinned `--json` payload, the rotation columns);
§4 one probe per endpoint, the read-only rule and the no-Qt fresh process; §5 the release state.
Rule — `AGENTS.md` §4.35; contract — `CLI.md` §3.6.
Run: python tests/test_cli_hostkey.py
"""
import contextlib
import io
import json
import logging
import os
import socket
import subprocess
import sys
import threading

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least,
                     translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + sys.path (BEFORE any app import)

# The harness's own peer sockets die on teardown, and paramiko reports that through `logging` — the
# surface installs its own guard (`cli.main:silence_library_logs()`), but a socket of THIS process may die
# before the first `main()` call, so the silence is installed here too.
logging.getLogger("paramiko").addHandler(logging.NullHandler())
logging.getLogger("paramiko").propagate = False

import paramiko  # noqa: E402

import cli.args as ARGS  # noqa: E402
import cli.dispatch as DISPATCH  # noqa: E402
import cli.envelope as ENV  # noqa: E402
import cli.errors as ERR  # noqa: E402
import cli.exit_codes as EX  # noqa: E402
import cli.hostkey as HOSTKEY  # noqa: E402
import cli.verb_args as VERB_ARGS  # noqa: E402
import modules.host_key_policy as HKP  # noqa: E402
import version  # noqa: E402
from cli.main import main  # noqa: E402

CLI_MD = os.path.join(ROOT, "CLI.md")
LANGS = load_i18n_langs(ROOT)
STORE_PATH = os.path.join(str(WORK), "known_hosts_v1151")
STORE = HKP.KnownHostsStore(STORE_PATH)
HKP.set_store(STORE)

#: A NON-22 port is what the `[host]:port` spelling exists for — every probe below dials 127.0.0.1.
HOST_A = paramiko.ECDSAKey.generate()      # the pin that still holds
HOST_B = paramiko.ECDSAKey.generate()      # the rotation: another key of the SAME algorithm
PIN_RSA = paramiko.RSAKey.generate(2048)   # a pin whose algorithm the endpoint no longer presents


def read(path):
    """The text of one repository file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def run(argv):
    """`cli.main()` as a console run sees it: `(exit code, stdout text, stderr text)`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def document(text):
    """The ONE `--json` document of a run (a second document on stdout is a defect)."""
    stripped = str(text or "").strip()
    return json.loads(stripped) if stripped.startswith("{") else {}


def entry_name(port):
    """The store's OWN spelling of the test endpoint (`entry_name_for()`, the ONE writer)."""
    return HKP.entry_name_for("127.0.0.1", port)


def cost(reader, *arguments):
    """The `CliError` a grammar read costs (`None` — it accepted the tail)."""
    try:
        reader(*arguments)
    except ERR.CliError as exc:
        return exc
    return None


class _KeyServer(paramiko.ServerInterface):
    """The minimum a transport needs to complete a key exchange and present its host key."""

    def get_allowed_auths(self, username):
        return "publickey"

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED


class KeyPeer:
    """A LOCAL endpoint presenting ONE host key — a REAL paramiko transport, never a network."""

    def __init__(self, key):
        self.key = key
        self.accepted = 0
        self._stop = threading.Event()
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(8)
        self.port = self._listener.getsockname()[1]
        threading.Thread(target=self._serve, name="hostkey-peer", daemon=True).start()

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _addr = self._listener.accept()
            except OSError:
                return
            self.accepted += 1
            threading.Thread(target=self._handshake, args=(conn,), daemon=True).start()

    def _handshake(self, conn):
        transport = None
        try:
            transport = paramiko.Transport(conn)
            transport.add_server_key(self.key)
            transport.start_server(server=_KeyServer())
            done = threading.Event()
            transport.completion_event = done
            done.wait(15)
        except Exception:  # noqa: BLE001 — the harness must never crash the test
            pass
        finally:
            if transport is not None:
                try:
                    transport.close()
                except Exception:  # noqa: BLE001
                    pass

    def close(self):
        self._stop.set()
        try:
            self._listener.close()
        except OSError:
            pass


def closed_port():
    """A port that was bound and released — a connect is refused at once."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


SAME = KeyPeer(HOST_A)          # the pin holds
ROTATED = KeyPeer(HOST_B)       # the pin moved
FOREIGN = KeyPeer(HOST_A)       # an endpoint the store does NOT pin
OFF = closed_port()


# ════════════════════════════════════════════════════════════════════════════
# §1 The subcommand grammar and the registry
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the `hostkey` subcommand grammar and the registry ==")

_ROWS = dict(DISPATCH.registered())
check("§1 the lazy load registers SIX verbs — the `hostkey` family beside the five of the base release",
      set(_ROWS) == {"inventory", "connections", "status", "doctor", "exec", "hostkey"},
      str(sorted(_ROWS)))
check("§1 `cli.hostkey` is the sixth built-in module, LAST in the ONE declaration of that load",
      DISPATCH.BUILTIN_VERB_MODULES == ("cli.inventory", "cli.connections", "cli.status",
                                        "cli.doctor", "cli.exec", "cli.hostkey"),
      str(DISPATCH.BUILTIN_VERB_MODULES))
check("§1 the row declares EXACTLY one argument, a renderer, a verdict, and is not mutating",
      DISPATCH.VERBS["hostkey"].min_args == 1 and DISPATCH.VERBS["hostkey"].max_args == 1
      and callable(DISPATCH.VERBS["hostkey"].render)
      and callable(DISPATCH.VERBS["hostkey"].verdict)
      and DISPATCH.VERBS["hostkey"].mutating is False,
      str(DISPATCH.VERBS["hostkey"]))
check("§1 the subcommand table is ONE declaration: `hostkey` → `verify` and nothing else",
      set(VERB_ARGS.SUBCOMMANDS) == {"hostkey"}
      and VERB_ARGS.SUBCOMMANDS["hostkey"] == (HOSTKEY.SUBCOMMAND_VERIFY,)
      and HOSTKEY.SUBCOMMAND_VERIFY == "verify",
      str(VERB_ARGS.SUBCOMMANDS))
check("§1 the reader answers the declared token (the only accepted one)",
      VERB_ARGS.read_subcommand("hostkey", ["verify"]) == "verify")
check("§1 ...and refuses a missing, a foreign, a doubled or a flag-shaped token as USAGE",
      all(getattr(cost(VERB_ARGS.read_subcommand, "hostkey", tail), "code", None) == EX.EXIT_USAGE
          for tail in ([], ["list"], ["verify", "verify"], ["--json"], [""])),
      str([cost(VERB_ARGS.read_subcommand, "hostkey", tail) for tail in ([], ["list"])]))
_FOREIGN_COST = cost(VERB_ARGS.read_subcommand, "hostkey", ["list"])
check("§1 a foreign token NAMES the declared set, so a typo costs no probe",
      _FOREIGN_COST is not None and "verify" in _FOREIGN_COST.message
      and "list" in _FOREIGN_COST.message, str(_FOREIGN_COST))
_CODE, _OUT_TEXT, _ERR_TEXT = run(["hostkey"])
check("§1 `hostkey` with no subcommand is a USAGE answer before any probe",
      _CODE == EX.EXIT_USAGE and "hostkey takes 1..1" in _ERR_TEXT, f"{_CODE} / {_ERR_TEXT!r}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["hostkey", "verify", "extra"])
check("§1 ...and a SECOND token is refused by the row's own count (1..1)", _CODE == EX.EXIT_USAGE
      and "hostkey takes 1..1" in _ERR_TEXT, _ERR_TEXT[:90])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["hostkey", "--json"])
check("§1 a GLOBAL option written after the verb is refused where it stands (the tail is the verb's)",
      _CODE == EX.EXIT_USAGE and "global options go BEFORE the verb" in _ERR_TEXT, _ERR_TEXT[:120])
check("§1 the help text lists the family with its summary (the registry's own row)",
      any(line.strip().startswith("hostkey") and "hostkey verify" in line
          for line in ARGS.usage_text(DISPATCH.registered()).splitlines()),
      [line for line in ARGS.usage_text(DISPATCH.registered()).splitlines() if "hostkey" in line])


# ════════════════════════════════════════════════════════════════════════════
# §2 The PURE core — the row model, the grouping and the four verdicts
# ════════════════════════════════════════════════════════════════════════════
print("== §2 the pure core: the rows, the endpoints and the verdict table ==")

check("§2 the `[host]:port` spelling round-trips through the ONE pair of readers",
      HKP.entry_name_for("db", 2222) == "[db]:2222"
      and HKP.split_entry_name("[db]:2222") == ("db", 2222)
      and HKP.split_entry_name(HKP.entry_name_for("web-1", 22)) == ("web-1", 22)
      and HKP.split_entry_name("") == ("", 22) and HKP.split_entry_name(None) == ("", 22))
check("§2 a bracket form with a non-numeric port answers 22 instead of raising (a hand-edited file)",
      HKP.split_entry_name("[db]:x") == ("db", 22)
      and HKP.split_entry_name("[db]:") == ("db", 22))
_ROWS_MODEL = HKP.host_key_rows({"web-1": {HOST_A.get_name(): HOST_A},
                                 "[db]:2222": {PIN_RSA.get_name(): PIN_RSA}})
check("§2 the row model carries the three facts and sorts by (host, keytype)",
      [tuple(row) for row in _ROWS_MODEL] == [("host", "keytype", "fingerprint")] * 2
      and [row["host"] for row in _ROWS_MODEL] == ["[db]:2222", "web-1"]
      and all(row["fingerprint"].startswith("SHA256:") for row in _ROWS_MODEL),
      str(_ROWS_MODEL))
check("§2 a broken store object answers an empty list, never a crash",
      HKP.host_key_rows(None) == [] and HKP.host_key_rows({"h": None}) == []
      and HKP.host_key_rows({"h": "not-a-key-map"}) == [])
_TWO_PINS = [{"host": "[a]:22", "keytype": "ssh-rsa", "fingerprint": "SHA256:1"},
             {"host": "[a]:22", "keytype": "ssh-ed25519", "fingerprint": "SHA256:2"},
             {"host": "b", "keytype": "ssh-rsa", "fingerprint": "SHA256:3"}]
_TARGETS = HKP.verify_targets(_TWO_PINS)
check("§2 the pins of ONE endpoint share one target (a key exchange answers ONE key)",
      len(_TARGETS) == 2 and _TARGETS[0][0] == "a" and _TARGETS[0][1] == 22
      and len(_TARGETS[0][2]) == 2 and _TARGETS[1][:2] == ("b", 22)
      and [row["keytype"] for row in _TARGETS[0][2]] == ["ssh-rsa", "ssh-ed25519"],
      str([(t[0], t[1], len(t[2])) for t in _TARGETS]))
check("§2 the grouping keeps the rows' own order and ignores a row that is not a record",
      [t[0] for t in HKP.verify_targets(list(reversed(_TWO_PINS)))] == ["b", "a"]
      and HKP.verify_targets([None, "x"]) == [] and HKP.verify_targets([]) == [])
_PIN = {"host": "[db]:2222", "keytype": "ssh-rsa", "fingerprint": "SHA256:stored"}
check("§2 verdict `ok`: the pin's own algorithm presented with the SAME fingerprint",
      HKP.verify_record(_PIN, "ssh-rsa", "SHA256:stored")["verdict"] == HKP.VERIFY_OK)
_CHANGED = HKP.verify_record(_PIN, "ssh-rsa", "SHA256:fresh")
check("§2 verdict `changed`: the same algorithm, another fingerprint — the rotation report's row",
      _CHANGED["verdict"] == HKP.VERIFY_CHANGED and _CHANGED["stored"] == "SHA256:stored"
      and _CHANGED["presented"] == "SHA256:fresh" and _CHANGED["detail"] == "")
_OTHER = HKP.verify_record(_PIN, "ssh-ed25519", "SHA256:fresh")
check("§2 verdict `unverified`: ANOTHER algorithm is never called changed (this pin was not exercised)",
      _OTHER["verdict"] == HKP.VERIFY_UNVERIFIED and _OTHER["presented"] == ""
      and "ssh-ed25519" in _OTHER["detail"], str(_OTHER))
_DEAD = HKP.verify_record(_PIN, "", "", "Connection refused")
check("§2 verdict `unreachable`: no key was read, and the reason travels in `detail`",
      _DEAD["verdict"] == HKP.VERIFY_UNREACHABLE and _DEAD["presented"] == ""
      and _DEAD["detail"] == "Connection refused" and _DEAD["stored"] == "SHA256:stored")
check("§2 a missing presented key is `unreachable` even without a reason sentence",
      HKP.verify_record(_PIN)["verdict"] == HKP.VERIFY_UNREACHABLE
      and bool(HKP.verify_record(_PIN)["detail"]))
check("§2 every record carries the SIX columns in the order the TEXT form writes them",
      tuple(HKP.verify_record(_PIN, "ssh-rsa", "SHA256:stored")) == HOSTKEY.COLUMNS
      == ("host", "keytype", "verdict", "stored", "presented", "detail"),
      str(tuple(HKP.verify_record(_PIN))))
check("§2 the four verdicts are ONE declared vocabulary",
      HKP.VERIFY_VERDICTS == ("ok", "changed", "unverified", "unreachable"), str(HKP.VERIFY_VERDICTS))


# ════════════════════════════════════════════════════════════════════════════
# §3 The verb over a REAL store and IN-PROCESS servers
# ════════════════════════════════════════════════════════════════════════════
print("== §3 `hostkey verify`: ok / changed / unverified / unreachable ==")

check("§3 the isolated store really takes the pins (the test writes its OWN file)",
      STORE.replace(entry_name(SAME.port), HOST_A.get_name(), HOST_A) is True
      and STORE.replace(entry_name(ROTATED.port), HOST_A.get_name(), HOST_A) is True
      and STORE.replace(entry_name(OFF), HOST_A.get_name(), HOST_A) is True
      and STORE.replace(entry_name(FOREIGN.port), PIN_RSA.get_name(), PIN_RSA) is True
      and len(HKP.host_key_rows(STORE.entries())) == 4)

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--timeout", "5", "hostkey", "verify"])
_DOC = document(_OUT_TEXT)
_DATA = _DOC.get("data") or {}
_BY_HOST = {record["host"]: record for record in _DATA.get("entries") or ()}
check("§3 `--json` answers ONE envelope: ok true, no error, the report in `data`",
      tuple(_DOC) == ENV.ENVELOPE_KEYS and _DOC.get("ok") is True and _DOC.get("error") is None
      and _DOC.get("verb") == "hostkey", f"{_CODE} / {_OUT_TEXT[:140]!r}")
check("§3 ...whose `data` is the PINNED payload — store, count, timeout, entries and no more",
      tuple(_DATA) == HOSTKEY.DATA_KEYS == ("store", "count", "timeout", "entries"),
      str(tuple(_DATA)))
check("§3 the store is the path that was read and the count is the number of PINS",
      _DATA.get("store") == STORE_PATH and _DATA.get("count") == 4
      and _DATA.get("timeout") == 5.0, f"{_DATA.get('store')} / {_DATA.get('count')}")
check("§3 every record carries exactly the six columns, in order",
      [tuple(record) for record in _DATA.get("entries") or ()] == [HOSTKEY.COLUMNS] * 4,
      str([tuple(record) for record in _DATA.get("entries") or ()]))
check("§3 the pin whose server still presents it is `ok`, both fingerprints equal",
      _BY_HOST[entry_name(SAME.port)]["verdict"] == HKP.VERIFY_OK
      and _BY_HOST[entry_name(SAME.port)]["stored"] == _BY_HOST[entry_name(SAME.port)]["presented"]
      == HKP.fingerprint(HOST_A), str(_BY_HOST[entry_name(SAME.port)]))
_ROTATION = _BY_HOST[entry_name(ROTATED.port)]
check("§3 a server that ROTATED its key is `changed`, and the report names BOTH fingerprints",
      _ROTATION["verdict"] == HKP.VERIFY_CHANGED
      and _ROTATION["stored"] == HKP.fingerprint(HOST_A)
      and _ROTATION["presented"] == HKP.fingerprint(HOST_B)
      and _ROTATION["stored"] != _ROTATION["presented"], str(_ROTATION))
_FOREIGN_ROW = _BY_HOST[entry_name(FOREIGN.port)]
check("§3 an endpoint presenting ANOTHER algorithm is `unverified`, never a false `changed`",
      _FOREIGN_ROW["verdict"] == HKP.VERIFY_UNVERIFIED and _FOREIGN_ROW["presented"] == ""
      and _FOREIGN_ROW["stored"] == HKP.fingerprint(PIN_RSA)
      and HOST_A.get_name() in _FOREIGN_ROW["detail"], str(_FOREIGN_ROW))
check("§3 a port nobody listens on is `unreachable`, with the reason in `detail`",
      _BY_HOST[entry_name(OFF)]["verdict"] == HKP.VERIFY_UNREACHABLE
      and bool(_BY_HOST[entry_name(OFF)]["detail"]), str(_BY_HOST[entry_name(OFF)]))
check("§3 the process code is the ROUND's verdict: a moved pin is the REFUSAL class (2)",
      _CODE == EX.EXIT_REFUSAL, str(_CODE))

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--timeout", "5", "hostkey", "verify"])
_LINES = _OUT_TEXT.splitlines()
check("§3 the TEXT form is one six-column line per pin — the rotation report's stored|presented pair",
      _CODE == EX.EXIT_REFUSAL and len(_LINES) == 4 and _ERR_TEXT == ""
      and all(len(line.split("\t")) == 6 for line in _LINES), repr(_OUT_TEXT[:200]))
_ROTATED_LINE = [line for line in _LINES if line.startswith(entry_name(ROTATED.port) + "\t")]
check("§3 ...and its `changed` row sets the two fingerprints side by side, stored FIRST",
      len(_ROTATED_LINE) == 1
      and _ROTATED_LINE[0].split("\t")[2] == HKP.VERIFY_CHANGED
      and _ROTATED_LINE[0].split("\t")[3] == HKP.fingerprint(HOST_A)
      and _ROTATED_LINE[0].split("\t")[4] == HKP.fingerprint(HOST_B), str(_ROTATED_LINE))

STORE.replace(entry_name(ROTATED.port), HOST_B.get_name(), HOST_B)   # the human re-pinned it
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--timeout", "5", "hostkey", "verify"])
_ROUND_TWO = document(_OUT_TEXT).get("data") or {}
check("§3 only an unreachable pin left → the NETWORK class (4), the report intact and `ok: true`",
      _CODE == EX.EXIT_NETWORK and document(_OUT_TEXT).get("ok") is True
      and _ROUND_TWO.get("count") == 4
      and {r["host"]: r["verdict"] for r in _ROUND_TWO["entries"]}[entry_name(ROTATED.port)]
      == HKP.VERIFY_OK, str(_CODE))
STORE.remove(entry_name(OFF))
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--timeout", "5", "hostkey", "verify"])
check("§3 every pin ok or unverified → exit 0 (the operator's green run)",
      _CODE == EX.EXIT_OK and document(_OUT_TEXT).get("data", {}).get("count") == 3, str(_CODE))

EMPTY_STORE = os.path.join(str(WORK), "known_hosts_empty")
HKP.set_store(HKP.KnownHostsStore(EMPTY_STORE))
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "hostkey", "verify"])
check("§3 an EMPTY store is a report (count 0, exit 0) plus ONE stderr note — never a silent green run",
      _CODE == EX.EXIT_OK and document(_OUT_TEXT).get("data", {}).get("count") == 0
      and len(_ERR_TEXT.splitlines()) == 1 and "nothing to verify" in _ERR_TEXT,
      f"{_CODE} / {_ERR_TEXT!r}")

BROKEN_STORE = os.path.join(str(WORK), "known_hosts_broken")
with open(BROKEN_STORE, "w", encoding="utf-8") as handle:
    handle.write("web-1 ssh-rsa AAAAnotbase64\n")
_BROKEN_BYTES = open(BROKEN_STORE, "rb").read()
HKP.set_store(HKP.KnownHostsStore(BROKEN_STORE))
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "hostkey", "verify"])
_BROKEN_DOC = document(_OUT_TEXT)
check("§3 an UNREADABLE store is a REFUSAL (2) naming the path — nothing can be verified",
      _CODE == EX.EXIT_REFUSAL and _BROKEN_DOC.get("ok") is False
      and _BROKEN_DOC.get("data") is None
      and _BROKEN_DOC.get("error", {}).get("kind") == "refusal"
      and BROKEN_STORE in _BROKEN_DOC.get("error", {}).get("message", ""), _OUT_TEXT[:180])
check("§3 ...and the refusal leaves the unreadable file exactly as it was (no overwrite, no repair)",
      open(BROKEN_STORE, "rb").read() == _BROKEN_BYTES)
HKP.set_store(STORE)


# ════════════════════════════════════════════════════════════════════════════
# §4 ONE probe per endpoint, the read-only rule and the no-Qt process
# ════════════════════════════════════════════════════════════════════════════
print("== §4 one probe per endpoint, read-only, and a process that never loads Qt ==")

BOTH = KeyPeer(HOST_A)
BOTH_STORE = os.path.join(str(WORK), "known_hosts_two_pins")
HKP.set_store(HKP.KnownHostsStore(BOTH_STORE))
HKP.get_store().replace(entry_name(BOTH.port), HOST_A.get_name(), HOST_A)   # retired by `replace()`
HKP.get_store().pin(entry_name(BOTH.port), PIN_RSA.get_name(), PIN_RSA)     # the ADDITIVE writer
_PINS = HKP.host_key_rows(HKP.get_store().entries())
_CALLS = []
_ORIGINAL_READ = HKP.read_server_host_key


def _counting_read(host, port, timeout=HKP.PROBE_HOST_KEY_TIMEOUT_S):
    """The shipped read, counted — the ONE call per endpoint the contract declares."""
    _CALLS.append((host, port, timeout))
    return _ORIGINAL_READ(host, port, timeout=timeout)


HKP.read_server_host_key = _counting_read
try:
    _RECORDS = HOSTKEY.verify_rows(_PINS, 3.5)
finally:
    HKP.read_server_host_key = _ORIGINAL_READ
check("§4 TWO pins of one endpoint cost ONE probe (a key exchange answers ONE key)",
      len(_PINS) == 2 and len(_CALLS) == 1 and _CALLS[0][:2] == ("127.0.0.1", BOTH.port),
      f"pins={len(_PINS)} calls={_CALLS}")
check("§4 ...and both pins get their own verdict from the ONE answer (ok + unverified)",
      [record["verdict"] for record in _RECORDS] == [HKP.VERIFY_UNVERIFIED, HKP.VERIFY_OK]
      or sorted(record["verdict"] for record in _RECORDS) == [HKP.VERIFY_OK, HKP.VERIFY_UNVERIFIED],
      str([(r["keytype"], r["verdict"]) for r in _RECORDS]))
check("§4 the run's `--timeout` really reaches the probe (the budget is not a decoration)",
      [call[2] for call in _CALLS] == [3.5], str(_CALLS))
BOTH.close()

HKP.set_store(HKP.KnownHostsStore(os.path.join(str(WORK), "known_hosts_ro")))
HKP.get_store().replace(entry_name(ROTATED.port), HOST_A.get_name(), HOST_A)
_RO_BYTES = open(HKP.get_store().path, "rb").read()
_listing = sorted(os.listdir(str(WORK)))
run(["--json", "--timeout", "5", "hostkey", "verify"])
run(["--timeout", "5", "hostkey", "verify"])
check("§4 the verb WRITES NOTHING — the store's bytes and the folder are unchanged (a bulk run never accepts)",
      open(HKP.get_store().path, "rb").read() == _RO_BYTES
      and sorted(os.listdir(str(WORK))) == _listing)
check("§4 the verb never reads a project: `--project` is not asked, an absent one is no error",
      run(["--project", os.path.join(str(WORK), "no-such.json"), "hostkey", "verify"])[0]
      in (EX.EXIT_OK, EX.EXIT_REFUSAL, EX.EXIT_NETWORK))
HKP.set_store(STORE)

_CHILD = (
    "import sys\n"
    "from cli.main import main\n"
    "rc = main(['--json', 'hostkey', 'verify'])\n"
    "print('QT', 'PySide6' in sys.modules, file=sys.stderr)\n"
    "sys.exit(rc)\n")
_ENV = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
_DONE = subprocess.run([sys.executable, "-c", _CHILD], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180, env=_ENV)
_CHILD_DOC = document(_DONE.stdout)
check("§4 a FRESH process runs a REAL `hostkey verify` with PySide6 absent from sys.modules",
      "QT False" in (_DONE.stderr or "")
      and _CHILD_DOC.get("ok") is True and _CHILD_DOC.get("verb") == "hostkey"
      and (_CHILD_DOC.get("data") or {}).get("count") == 0,
      f"rc={_DONE.returncode} / {(_DONE.stdout or '')[:120]!r} / {(_DONE.stderr or '')[:160]!r}")
_CONTRACT = read(CLI_MD)
check("§4 the contract carries the clause this code answers (the frozen §3.6)",
      "### 3.6 `hostkey verify`" in _CONTRACT and "a bulk run never auto-accepts" in _CONTRACT
      and "ONE probe per ENDPOINT" in _CONTRACT and "`unverified`" in _CONTRACT)


# ════════════════════════════════════════════════════════════════════════════
# §5 The release state
# ════════════════════════════════════════════════════════════════════════════
print("== §5 the release state ==")

check_release_state(ROOT)
check(f"§5 this release is v{EXPECTED_APP_VERSION} (the 1.15 line's first follow-up or a later one)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15.1")
      and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§5 the release adds NO i18n key (the parity pin stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1205
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
check("§5 no new dependency: requirements.txt keeps its four pins",
      len([line for line in read(os.path.join(ROOT, "requirements.txt")).splitlines()
           if line.strip() and not line.strip().startswith("#")]) == 4)
check("§5 the JSON project format did NOT move (`VERSION_FORMAT` stays 0.9)",
      version.VERSION_FORMAT == "0.9")
check("§5 the family's ONE subcommand is still `verify` (no pin writer joined it in this release)",
      VERB_ARGS.SUBCOMMANDS == {"hostkey": (HOSTKEY.SUBCOMMAND_VERIFY,)},
      str(VERB_ARGS.SUBCOMMANDS))

SAME.close()
ROTATED.close()
FOREIGN.close()
finish()
