# -*- coding: utf-8 -*-
"""v1.15rc3 — the HEADLESS probe verbs: `status` and `doctor` over the GUI's own PURE cores.
§1 the registry and the POSITIONAL grammar; §2 `status` over SYNTHETIC projects and LOCAL sockets (the
three statuses, the exit verdict, the pinned `--json` payload); §3 `doctor` (the seven report fields, the
kind→exit table, the text form, an unknown node); §4 the SAME-core identity and a fresh no-Qt process that
RUNS a probe; §5 the release state. Rule — `AGENTS.md` §4.35; contract — `CLI.md` §3.3–§3.4.
Run: python tests/test_cli_probe.py
"""
import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_parity,
                     check_release_state, finish, load_i18n_langs, releases_at_least,
                     translation_keys)

ROOT, WORK = bootstrap()  # HOME isolation + sys.path (BEFORE any app import)

import cli.args as ARGS  # noqa: E402
import cli.dispatch as DISPATCH  # noqa: E402
import cli.doctor as DOCTOR  # noqa: E402
import cli.envelope as ENV  # noqa: E402
import cli.errors as ERR  # noqa: E402
import cli.exit_codes as EX  # noqa: E402
import cli.status as STATUS  # noqa: E402
import cli.verb_args as VERB_ARGS  # noqa: E402
import services.reachability as REACH  # noqa: E402
import services.status_probe as PROBE  # noqa: E402
import version  # noqa: E402
from cli.main import main  # noqa: E402

CLI_MD = os.path.join(ROOT, "CLI.md")
LANGS = load_i18n_langs(ROOT)


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


def _is_usage(reader, token):
    """Does this node reader refuse `token` with the USAGE class?"""
    try:
        reader("status", [token])
    except ERR.CliError as exc:
        return exc.code == EX.EXIT_USAGE
    return False


def fresh(code):
    """Run a snippet in a FRESH process rooted at the repository (the no-Qt gate's own shape)."""
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, env=env)


class LocalPeer:
    """A local TCP peer: a banner (online), silence (warn) or an already-closed port (offline)."""

    def __init__(self, banner=None, hold=0.0):
        self._banner = banner
        self._hold = float(hold)
        self._stop = threading.Event()
        self.accepted = 0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(16)
        self._sock.settimeout(0.2)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, name="cli-probe-peer", daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.accepted += 1
            try:
                if self._banner:
                    conn.sendall(self._banner)
                    time.sleep(0.05)
                elif self._hold:
                    time.sleep(self._hold)
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def close(self):
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=3)


def closed_port():
    """A port that was bound and released — a connect is refused at once."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def node(nid, alias, port, host="127.0.0.1"):
    """ONE synthetic server record (never a real map file)."""
    return {"id": nid, "alias": alias, "host": host, "ssh_port": port, "user": "tester"}


def fixture(name, servers=()):
    """Write ONE SYNTHETIC project into the isolated work folder."""
    payload = {"version": version.VERSION_FORMAT, "servers": list(servers), "connections": [],
               "notes": [], "groups": [], "background": None}
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


ONLINE = LocalPeer(banner=b"SSH-2.0-CliProbe\r\n")
SILENT = LocalPeer(hold=1.4)
FOREIGN = LocalPeer(banner=b"HTTP/1.0 400 Bad Request\r\n")
OFF = closed_port()
MAP = fixture("probe-map.json", [node("srv-on", "web-1", ONLINE.port),
                                 node("srv-warn", "db-1", SILENT.port),
                                 node("srv-off", "cache-1", OFF)])
ONLINE_MAP = fixture("probe-online.json", [node("srv-a", "a", ONLINE.port),
                                           node("srv-b", "b", ONLINE.port)])
FOREIGN_MAP = fixture("probe-foreign.json", [node("srv-f", "http-1", FOREIGN.port)])
EMPTY = fixture("probe-empty.json")
TWINS = fixture("probe-twins.json", [node("srv-1", "twin", ONLINE.port),
                                     node("srv-2", "twin", ONLINE.port)])


# ════════════════════════════════════════════════════════════════════════════
# §1 The registry and the POSITIONAL grammar
# ════════════════════════════════════════════════════════════════════════════
print("== §1 the registry and the positional grammar ==")

_ROWS = dict(DISPATCH.registered())
check("§1 the lazy load registers the build's verbs (the two tables, the two probes, `exec`, `hostkey`)",
      set(_ROWS) == {"inventory", "connections", "status", "doctor", "exec", "hostkey"},
      str(sorted(_ROWS)))
check("§1 the built-in modules are the ONE declaration of that load (loaded once, in order)",
      DISPATCH.BUILTIN_VERB_MODULES == ("cli.inventory", "cli.connections", "cli.status",
                                        "cli.doctor", "cli.exec", "cli.hostkey"),
      str(DISPATCH.BUILTIN_VERB_MODULES))
check("§1 `status` declares 0..MAX_NODES node arguments and the round's verdict; `doctor` exactly ONE",
      DISPATCH.VERBS["status"].min_args == 0
      and DISPATCH.VERBS["status"].max_args == VERB_ARGS.MAX_NODES
      and callable(DISPATCH.VERBS["status"].verdict)
      and DISPATCH.VERBS["doctor"].min_args == 1 and DISPATCH.VERBS["doctor"].max_args == 1
      and callable(DISPATCH.VERBS["doctor"].verdict),
      f"{DISPATCH.VERBS['status']} / {DISPATCH.VERBS['doctor']}")
check("§1 the argument tables stay apart: flags for the table verbs, tokens for the probe verbs",
      set(VERB_ARGS.ARGUMENT_TABLE) == {"inventory", "connections"}
      and VERB_ARGS.POSITIONAL_VERBS == ("status", "doctor"), str(VERB_ARGS.ARGUMENT_TABLE))
check("§1 a node token is read verbatim, in order, and repeats are the caller's business",
      VERB_ARGS.read_nodes("status", ["web-1", "srv-db"]) == ("web-1", "srv-db")
      and VERB_ARGS.read_nodes("status", []) == ())
check("§1 a flag-shaped or empty node token is a USAGE error, never a node nobody could name",
      all(_is_usage(VERB_ARGS.read_nodes, token) for token in ("--json", "-h", "", "  ")))
check("§1 the help text lists both probe verbs with their summaries",
      any("status" in line and "SSH probe" in line for line in
          ARGS.usage_text(DISPATCH.registered()).splitlines())
      and any("doctor" in line and "reachability" in line for line in
              ARGS.usage_text(DISPATCH.registered()).splitlines()))
_CODE, _OUT_TEXT, _ERR_TEXT = run(["status", "--json"])
check("§1 `--json` AFTER the verb belongs to the verb and is refused (the global table is BEFORE it)",
      _CODE == EX.EXIT_USAGE and "--json" in _ERR_TEXT, f"{_CODE} / {_ERR_TEXT!r}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--project", MAP, "doctor"])
_CODE2, _OUT_TEXT2, _ERR_TEXT2 = run(["--project", MAP, "doctor", "a", "b"])
check("§1 `doctor` with no node or two nodes is a USAGE error before any handler runs",
      _CODE == EX.EXIT_USAGE and _CODE2 == EX.EXIT_USAGE and "doctor takes 1..1" in _ERR_TEXT,
      f"{_CODE}/{_ERR_TEXT!r} {_CODE2}/{_ERR_TEXT2!r}")
check("§1 the flood stop is a declaration: 257 node arguments are refused before a probe",
      DISPATCH.VERBS["status"].accepts(VERB_ARGS.MAX_NODES)
      and not DISPATCH.VERBS["status"].accepts(VERB_ARGS.MAX_NODES + 1))


# ════════════════════════════════════════════════════════════════════════════
# §2 `status` over SYNTHETIC projects and LOCAL sockets
# ════════════════════════════════════════════════════════════════════════════
print("== §2 `status`: the three statuses and the exit verdict ==")

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--project", MAP, "--timeout", "1", "status"])
check("§2 a round over online + silent + closed answers the THREE statuses, one line per node",
      _CODE == EX.EXIT_NETWORK and _ERR_TEXT == ""
      and _OUT_TEXT.splitlines() == ["web-1\tonline", "db-1\twarn", "cache-1\toffline"],
      f"{_CODE} / {_OUT_TEXT!r} / {_ERR_TEXT!r}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", MAP, "--timeout", "1", "status"])
_DOC = document(_OUT_TEXT)
_DATA = _DOC.get("data") or {}
check("§2 `--json` answers ONE envelope: ok true, no error, the report in `data`",
      _CODE == EX.EXIT_NETWORK and tuple(_DOC) == ENV.ENVELOPE_KEYS and _DOC.get("ok") is True
      and _DOC.get("error") is None and _DOC.get("verb") == "status" and _ERR_TEXT == "",
      f"{_CODE} / {_OUT_TEXT[:120]!r}")
check("§2 ...whose `data` is the PINNED payload — project, count, timeout, nodes, skipped and no more",
      tuple(_DATA) == STATUS.DATA_KEYS == ("project", "count", "timeout", "nodes", "skipped"),
      str(tuple(_DATA)))
check("§2 ...and `skipped` is the additive key of the unmanaged rule (empty with no unmanaged card)",
      _DATA.get("skipped") == [], str(_DATA.get("skipped")))
check("§2 the count is the node count and the project is the path that was read",
      _DATA.get("count") == 3 and _DATA.get("project") == MAP
      and _DATA.get("timeout") == 1.0, f"{_DATA.get('count')} / {_DATA.get('timeout')}")
check("§2 every record carries the id, the alias and the status (the contract's three facts)",
      [tuple(record) for record in _DATA.get("nodes") or ()]
      == [("id", "alias", "status")] * 3
      and [record["status"] for record in _DATA["nodes"]] == ["online", "warn", "offline"],
      str(_DATA.get("nodes")))

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--project", ONLINE_MAP, "--timeout", "2", "status"])
check("§2 every node online is exit 0 (the cron job's green run)",
      _CODE == EX.EXIT_OK and _OUT_TEXT.splitlines() == ["a\tonline", "b\tonline"],
      f"{_CODE} / {_OUT_TEXT!r}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", ONLINE_MAP, "--timeout", "2", "status"])
check("§2 ...and the same round under `--json` is ok true, code 0, count 2",
      _CODE == EX.EXIT_OK and document(_OUT_TEXT).get("ok") is True
      and (document(_OUT_TEXT).get("data") or {}).get("count") == 2)
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", ONLINE_MAP, "--timeout", "2",
                                   "status", "srv-b"])
check("§2 a node is selected by ID — one record, in the argument order",
      _CODE == EX.EXIT_OK
      and [(record["id"], record["status"])
           for record in document(_OUT_TEXT)["data"]["nodes"]] == [("srv-b", "online")],
      _OUT_TEXT[:120])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", ONLINE_MAP, "--timeout", "2",
                                   "status", "a"])
check("§2 ...and by ALIAS, over the same reader",
      _CODE == EX.EXIT_OK
      and [record["id"] for record in document(_OUT_TEXT)["data"]["nodes"]] == ["srv-a"],
      _OUT_TEXT[:120])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", ONLINE_MAP, "--timeout", "2",
                                   "status", "b", "a", "a"])
check("§2 a repeated node is probed ONCE and the answer keeps the first-seen order",
      _CODE == EX.EXIT_OK
      and [record["id"] for record in document(_OUT_TEXT)["data"]["nodes"]] == ["srv-b", "srv-a"],
      _OUT_TEXT[:120])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", EMPTY, "status"])
check("§2 a project with no server answers count 0, an empty report and exit 0 (nothing is broken)",
      _CODE == EX.EXIT_OK and document(_OUT_TEXT)["data"] == {"project": EMPTY, "count": 0,
                                                              "timeout": 10.0, "nodes": [],
                                                              "skipped": []},
      _OUT_TEXT[:120])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--project", EMPTY, "status"])
check("§2 ...and its text form writes no line at all", _CODE == EX.EXIT_OK and _OUT_TEXT == "",
      repr(_OUT_TEXT))

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", ONLINE_MAP, "status", "srv-b", "nope"])
_NOPE = document(_OUT_TEXT)
check("§2 an unknown node is `not_found` (5), and its message NAMES the token",
      _CODE == EX.EXIT_NOT_FOUND and _NOPE.get("ok") is False and _NOPE.get("data") is None
      and _NOPE.get("error", {}).get("kind") == "not_found"
      and "nope" in _NOPE.get("error", {}).get("message", ""), _OUT_TEXT[:160])
_GUARD = LocalPeer(banner=b"SSH-2.0-Guard\r\n")
_GUARD_MAP = fixture("probe-guard.json", [node("srv-g", "guard", _GUARD.port)])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", _GUARD_MAP, "status", "guard", "nope"])
time.sleep(0.2)
check("§2 ...and a round with an unknown token costs NO probe (the selection is resolved first)",
      _CODE == EX.EXIT_NOT_FOUND and _GUARD.accepted == 0, f"accepted={_GUARD.accepted}")
_GUARD.close()

_BEFORE = open(MAP, "rb").read()
_LISTING = sorted(os.listdir(WORK))
run(["--project", MAP, "--timeout", "1", "status"])
run(["--json", "--project", MAP, "--timeout", "1", "status"])
run(["--project", MAP, "--timeout", "1", "doctor", "cache-1"])
check("§2 a probe NEVER writes its project (the bytes and the work folder are unchanged)",
      open(MAP, "rb").read() == _BEFORE and sorted(os.listdir(WORK)) == _LISTING)


# ════════════════════════════════════════════════════════════════════════════
# §3 `doctor`: the report fields, the kind→exit table and the text form
# ════════════════════════════════════════════════════════════════════════════
print("== §3 `doctor`: the reachability report of ONE node ==")

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", ONLINE_MAP, "--timeout", "2",
                                   "doctor", "a"])
_DOC = document(_OUT_TEXT)
_DOCTOR = _DOC.get("data") or {}
check("§3 a live SSH peer answers `ok` and exit 0, with ok true and no error",
      _CODE == EX.EXIT_OK and _DOC.get("ok") is True and _DOC.get("error") is None
      and _DOC.get("verb") == "doctor", _OUT_TEXT[:120])
check("§3 `data` is the report's OWN seven fields, no more and no less",
      tuple(_DOCTOR) == DOCTOR.DATA_KEYS
      == ("host", "port", "kind", "ip", "detail", "ping", "elapsed"), str(tuple(_DOCTOR)))
check("§3 ...carrying the endpoint, the resolved address and the SSH banner",
      _DOCTOR.get("host") == "127.0.0.1" and _DOCTOR.get("port") == ONLINE.port
      and _DOCTOR.get("ip") == "127.0.0.1" and _DOCTOR.get("kind") == "ok"
      and _DOCTOR.get("detail", "").startswith("SSH-2.0-CliProbe")
      and _DOCTOR.get("ping") == "" and float(_DOCTOR.get("elapsed", -1)) >= 0.0,
      str(_DOCTOR))

_TEXT_PAYLOAD = {"host": "127.0.0.1", "port": 2222, "kind": "ok", "ip": "127.0.0.1",
                 "detail": "SSH-2.0-CliProbe", "ping": "", "elapsed": 0.125}
check("§3 the text form renders the SAME facts, one `key: value` line per field",
      DOCTOR.render(None, _TEXT_PAYLOAD) == ["host: 127.0.0.1", "port: 2222", "kind: ok",
                                            "ip: 127.0.0.1", "detail: SSH-2.0-CliProbe",
                                            "ping: ", "elapsed: 0.125"])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--project", ONLINE_MAP, "--timeout", "2", "doctor", "a"])
check("§3 the text run prints those seven lines and exits 0",
      _CODE == EX.EXIT_OK and _OUT_TEXT.splitlines()[0] == "host: 127.0.0.1"
      and _OUT_TEXT.splitlines()[2] == "kind: ok" and len(_OUT_TEXT.splitlines()) == 7,
      repr(_OUT_TEXT))

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", MAP, "--timeout", "1", "doctor",
                                   "cache-1"])
_DEAD = (document(_OUT_TEXT) or {}).get("data") or {}
_DEAD_KIND = _DEAD.get("kind")
check("§3 a dead port is a FAILURE REPORT (network or timeout), never a run failure",
      _CODE == DOCTOR.exit_code_for_kind(_DEAD_KIND) and _CODE in (EX.EXIT_NETWORK, EX.EXIT_TIMEOUT)
      and (document(_OUT_TEXT) or {}).get("ok") is True
      and _DEAD_KIND in ("tcp_refused", "tcp_failed", "tcp_timeout")
      and _DEAD.get("ip") == "127.0.0.1" and _DEAD.get("ping") in ("ok", "failed")
      and _DEAD.get("port") == OFF, f"{_CODE} / {_OUT_TEXT[:160]}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", FOREIGN_MAP, "--timeout", "2",
                                   "doctor", "http-1"])
_FOREIGN = (document(_OUT_TEXT) or {}).get("data") or {}
check("§3 a foreign banner is a NETWORK failure (4) with the banner as the report's detail",
      _CODE == EX.EXIT_NETWORK and _FOREIGN.get("kind") == "banner_foreign"
      and "HTTP" in _FOREIGN.get("detail", ""), f"{_CODE} / {_OUT_TEXT[:160]}")
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", MAP, "--timeout", "1", "doctor", "db-1"])
_SILENT_REPORT = (document(_OUT_TEXT) or {}).get("data") or {}
check("§3 an open port with no banner is `banner_silent`, exit 4",
      _CODE == EX.EXIT_NETWORK and _SILENT_REPORT.get("kind") == "banner_silent",
      f"{_CODE} / {_SILENT_REPORT.get('kind')}")

check("§3 the kind→exit table is the contract's: ok 0, a TIMEOUT 6, every other failure 4",
      DOCTOR.exit_code_for_kind("ok") == EX.EXIT_OK
      and DOCTOR.exit_code_for_kind("dns_timeout") == EX.EXIT_TIMEOUT
      and DOCTOR.exit_code_for_kind("tcp_timeout") == EX.EXIT_TIMEOUT
      and all(DOCTOR.exit_code_for_kind(kind) == EX.EXIT_NETWORK
              for kind in REACH.REPORT_KINDS
              if kind not in ("ok", "dns_timeout", "tcp_timeout"))
      and DOCTOR.exit_code_for_kind("foreign") == EX.EXIT_NETWORK,
      {kind: DOCTOR.exit_code_for_kind(kind) for kind in REACH.REPORT_KINDS})

_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", MAP, "doctor", "nope"])
check("§3 an unknown node is `not_found` (5), never a report about another node",
      _CODE == EX.EXIT_NOT_FOUND and document(_OUT_TEXT).get("data") is None
      and document(_OUT_TEXT).get("error", {}).get("kind") == "not_found", _OUT_TEXT[:140])
_CODE, _OUT_TEXT, _ERR_TEXT = run(["--json", "--project", TWINS, "doctor", "twin"])
_AMBIGUOUS = document(_OUT_TEXT).get("error") or {}
check("§3 a duplicated alias is an ambiguous selection: USAGE, with the id door in the hint",
      _CODE == EX.EXIT_USAGE and "names 2 nodes" in _AMBIGUOUS.get("message", "")
      and "--help" in _AMBIGUOUS.get("hint", ""), _OUT_TEXT[:160])


# ════════════════════════════════════════════════════════════════════════════
# §4 The SAME core, and a REAL probe in a process that never loads Qt
# ════════════════════════════════════════════════════════════════════════════
print("== §4 the same PURE cores and the no-Qt process ==")

check("§4 both verbs import the PURE core OBJECTS, not copies",
      STATUS.probe_ssh is PROBE.probe_ssh
      and DOCTOR.diagnose_reachability is REACH.diagnose_reachability)
_check = fresh(
    "import services.status_probe as SP, services.reachability as R\n"
    "import services.status_checker as SC, services.diagnostics as DG\n"
    "import cli.status as CS, cli.doctor as CD\n"
    "print(SC.probe_ssh is SP.probe_ssh, DG.diagnose_reachability is R.diagnose_reachability,\n"
    "      CS.probe_ssh is SP.probe_ssh, CD.diagnose_reachability is R.diagnose_reachability,\n"
    "      SC.probe_ssh.__module__, DG.diagnose_reachability.__module__)\n")
check("§4 the GUI's probe modules re-export the SAME objects the CLI runs (one core, two surfaces)",
      _check.returncode == 0
      and _check.stdout.split() == ["True", "True", "True", "True",
                                    "services.status_probe", "services.reachability"],
      f"{(_check.stdout or '').strip()} / {(_check.stderr or '').strip()[:200]}")

_STATUS_CHILD = (
    "import sys\n"
    "from cli.main import main\n"
    f"rc = main(['--json', '--project', {MAP!r}, '--timeout', '2', 'status', 'web-1'])\n"
    "print('QT', 'PySide6' in sys.modules, file=sys.stderr)\n"
    "sys.exit(rc)\n")
_CHILD = fresh(_STATUS_CHILD)
_CHILD_DOC = document(_CHILD.stdout)
check("§4 a FRESH process runs a REAL `status` probe with PySide6 absent from sys.modules",
      _CHILD.returncode == EX.EXIT_OK and "QT False" in (_CHILD.stderr or "")
      and _CHILD_DOC.get("ok") is True
      and _CHILD_DOC.get("data", {}).get("nodes", [{}])[0].get("status") == "online",
      f"rc={_CHILD.returncode} / {(_CHILD.stdout or '')[:120]!r} / {(_CHILD.stderr or '')[:120]!r}")
_DOCTOR_CHILD = (
    "import sys\n"
    "from cli.main import main\n"
    f"rc = main(['--json', '--project', {ONLINE_MAP!r}, '--timeout', '2', 'doctor', 'a'])\n"
    "print('QT', 'PySide6' in sys.modules, file=sys.stderr)\n"
    "sys.exit(rc)\n")
_CHILD = fresh(_DOCTOR_CHILD)
_CHILD_DOC = document(_CHILD.stdout)
check("§4 ...and a REAL `doctor` report too, still with no Qt",
      _CHILD.returncode == EX.EXIT_OK and "QT False" in (_CHILD.stderr or "")
      and _CHILD_DOC.get("data", {}).get("kind") == "ok",
      f"rc={_CHILD.returncode} / {(_CHILD.stdout or '')[:120]!r} / {(_CHILD.stderr or '')[:120]!r}")


# ════════════════════════════════════════════════════════════════════════════
# §5 The release state
# ════════════════════════════════════════════════════════════════════════════
print("== §5 the release state ==")

check_release_state(ROOT)
check(f"§5 this release is v{EXPECTED_APP_VERSION} (the line's base release or a later one)",
      releases_at_least(EXPECTED_APP_VERSION, "1.15")
      and version.APP_VERSION == EXPECTED_APP_VERSION,
      f"{EXPECTED_APP_VERSION} / {version.APP_VERSION}")
check(f"§5 the milestone adds NO i18n key (the parity pin stays {EXPECTED_I18N_KEYS})",
      EXPECTED_I18N_KEYS == 1205
      and all(len(translation_keys(data)) == EXPECTED_I18N_KEYS for data in LANGS.values()),
      {code: len(translation_keys(data)) for code, data in sorted(LANGS.items())})
check_i18n_parity(LANGS)
check("§5 no new dependency: requirements.txt keeps its four pins",
      len([line for line in read(os.path.join(ROOT, "requirements.txt")).splitlines()
           if line.strip() and not line.strip().startswith("#")]) == 4)
check("§5 the JSON project format did NOT move (`VERSION_FORMAT` stays 0.9)",
      version.VERSION_FORMAT == "0.9")
_CONTRACT = read(CLI_MD)
check("§5 the contract states the two probes and their VERDICT semantics (the frozen text)",
      "`status [node...]`" in _CONTRACT and "`doctor <node>`" in _CONTRACT
      and "The process code is the ROUND's verdict" in _CONTRACT
      and "A broken node is still a REPORT" in _CONTRACT
      and "`ok` describes the RUN, never the map" in _CONTRACT)


for _peer in (ONLINE, SILENT, FOREIGN):
    _peer.close()
finish()
