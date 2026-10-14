# -*- coding: utf-8 -*-
"""The panel and the terminal: the small follow-ups (v1.12.3).
§1 the secrets the history can MARK (`R14(b)`): `user:pass` in a URL, `-u user:pass`, an
`Authorization:` header and `openssl passwd` join the DECLARED list, and such a command is still
WRITTEN; §2 the jump host on `ServerData`, its round trip through the project file and the server
dialog; §3 the importer: `ProxyJump` FILLS the field while `ProxyCommand` stays a note; §4 the
external terminal receives it at BOTH doors and the internal path never sees it; §5 the reader's
encoding is a PER-PANE choice over ONE remembered default; §6 the standalone's exemption from
`terminal_max_open`, in the contract and in the code; §7 the i18n and the release state.
Rule — `AGENTS.md` §4.3.6, §4.3.9, §4.4.2; mechanism — `DOCUMENTATION.md` §27, §49, §64, §75.
"""
import json
import os
import sys

from _common import (EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, bootstrap, check, check_i18n_format,
                     check_i18n_parity, check_release_state, clear_cfg, finish, load_i18n_langs,
                     pane_family_text, read_cfg, releases_at_least, translation_keys, wait_for,
                     write_cfg)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (HOME isolation + offscreen inside)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import i18n  # noqa: E402
import modules.command_history as CH  # noqa: E402
import modules.external_terminal as ET  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
import modules.ssh_connect as SC  # noqa: E402
import services.ssh_config_importer as SCI  # noqa: E402
import ui.main_window as MW  # noqa: E402
from dialogs.add_server_dialog import AddServerDialog  # noqa: E402
from dialogs.ssh_config_import_dialog import SshConfigImportDialog  # noqa: E402
from models.server import ServerData, server_data_from_dict, server_data_to_dict  # noqa: E402
from modules.sftp_tab import SftpTab  # noqa: E402
from modules.sftp_worker import SftpWorker  # noqa: E402
from storage.project import read_project_servers  # noqa: E402
from ui.main_window_ssh import SshMixin  # noqa: E402

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)
PANE_SRC = pane_family_text(ROOT)


def _read(*parts) -> str:
    """The text of a repository file that SHIPS (the wiring audits below read several)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _project_file(name, servers) -> str:
    """A real project FILE under the run's scratch folder (never a fixture of the map itself)."""
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"version": "0.9", "servers": servers, "connections": []}, fh)
    return path


def _make_tab(fs, commander=True):
    """(tab, worker) over the fake SFTP surface, optionally in the two-pane mode (the v1.7.5 shape)."""
    worker = SftpWorker(FakeSftpClient(fs))
    wire_worker(worker, EventLog())
    worker.start()
    tab = SftpTab()
    tab.message.connect(lambda *_a: None)
    if commander:
        tab.set_commander(True)
    tab.set_worker(worker)
    return tab, worker


def _rows(pane):
    return [pane.tree.topLevelItem(i).text(0) for i in range(pane.tree.topLevelItemCount())]


def _item(pane, name):
    for i in range(pane.tree.topLevelItemCount()):
        if pane.tree.topLevelItem(i).text(0) == name:
            return pane.tree.topLevelItem(i)
    return None


def _open(pane, name, ms=10000) -> bool:
    """Open one row in the pane's reader and wait for the answer (the ONE preview rule holds)."""
    pane._on_item_double_clicked(_item(pane, name), 0)
    return wait_for(lambda: pane._viewer_open and pane._viewer_path.endswith(name), timeout_ms=ms)


def _func_body(text, name) -> str:
    """The source of ONE function or method — up to the next `def` at the same indentation.

    A method of a mixin ends where its SIBLING begins, never at the next column-0 line: the
    methods of one class are separated by comments that stay inside it.
    """
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip().startswith(f"def {name}(")), -1)
    if start < 0:
        return ""
    indent = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for line in lines[start + 1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        out.append(line)
    return "\n".join(out)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the secrets the history can mark (R14(b)) ==")
# ════════════════════════════════════════════════════════════════════════════

_SHAPES = (
    # the four verified misses of the round
    ("curl -u bob:hunter2 https://api.example.com", True),
    ("git clone https://bob:hunter2@git.example.com/repo.git", True),
    ("psql 'postgresql://bob:hunter2@db.example.com/prod'", True),
    ("openssl passwd -1 hunter2", True),
    ('curl -H "Authorization: Basic Ym9iOmh1bnRlcjI=" https://x/y', True),
    ('curl -H "Proxy-Authorization: Basic YWJj" https://x/y', True),
    ("curl --user bob:hunter2 https://x/y", True),
    # the shapes the release deliberately does NOT mark
    ("sudo -u root systemctl restart nginx", False),
    ("sort -u /var/log/syslog", False),
    ("df -h", False),
    ("ls -la /etc", False),
    ("git commit -m 'fix the pass word'", False),
)
_wrong = [s for s, want in _SHAPES if CH.looks_like_secret(s) is not want]
check("§1 every verified shape is MARKED and a command that carries no credential is NOT",
      not _wrong, str(_wrong))
check("§1 the DECLARED list stays ONE literal tuple (no heuristic grew beside it)",
      len(CH.SECRET_PATTERNS) == 10
      and all(hasattr(p, "search") for p in CH.SECRET_PATTERNS)
      and CH.looks_like_secret(None) is False and CH.looks_like_secret(42) is False,
      str(len(CH.SECRET_PATTERNS)))

_store = CH.CommandHistoryStore("v1123-secret", directory=os.path.join(WORK, "history"))
_CMD = "curl -u bob:hunter2 https://api.example.com"
_store.record(_CMD, timestamp=1_700_000_000)
_store.record("df -h", timestamp=1_700_000_001)
_rows_by_cmd = {e["cmd"]: e for e in _store.load()}
check("§1 such a command is WRITTEN and marked — the store keeps what went on the wire",
      _rows_by_cmd[_CMD][CH.SECRET_FIELD] is True
      and _rows_by_cmd[_CMD]["cmd"] == _CMD
      and _rows_by_cmd["df -h"][CH.SECRET_FIELD] is False,
      str(_rows_by_cmd.get(_CMD)))
check("§1 ...and the mark is the field the FILE carries (a reader of the file sees it too)",
      any(rec.get("cmd") == _CMD and rec.get(CH.SECRET_FIELD) is True
          for rec in json.load(open(_store.path, encoding="utf-8"))["commands"]),
      _store.path)

_panel = CH.CommandHistoryPanel(store=_store)
_secret_msgs = []
_panel.status_message.connect(lambda text, _ms: _secret_msgs.append(text))
_refused = _panel.send_to_library(_rows_by_cmd[_CMD])
check("§1 the row the new patterns mark is REFUSED by the door into the command library",
      _refused is False and _secret_msgs == [i18n.t("terminal.history.secret_refused")],
      f"refused={_refused} msgs={_secret_msgs}")
check("§1 the row's second channel still spells the mark out (the padlock is a SHAPE + words)",
      _panel.entries() and CH.secret_row_icon() is not None
      and i18n.t("terminal.history.secret_tooltip"))
_panel.deleteLater()

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the jump host on the model and through the project file ==")
# ════════════════════════════════════════════════════════════════════════════

check("§2 `ServerData` carries the jump host as an OPTIONAL string (default — no jump)",
      "jump_host" in ServerData.__dataclass_fields__
      and ServerData(id="a", alias="a", host="h", user="u").jump_host == "")

_jump_data = ServerData(id="j-1", alias="jump", host="10.0.0.9", user="ops",
                        jump_host="bastion.example.com")
_doc = server_data_to_dict(_jump_data)
_back = server_data_from_dict(_doc)
check("§2 the value round-trips through the project JSON and the password still does not",
      _doc.get("jump_host") == "bastion.example.com" and _back.jump_host == "bastion.example.com"
      and "password" not in _doc,
      str(sorted(k for k in _doc if "jump" in k)))

check("§2 a project written WITHOUT the key loads as \"no jump\" (the additive direction)",
      server_data_from_dict({"id": "j-2", "alias": "old", "host": "h", "user": "u"}).jump_host == "")
check("§2 a foreign value answers \"no jump\" instead of reaching a command line",
      all(server_data_from_dict({"id": "j-3", "alias": "x", "host": "h", "user": "u",
                                 "jump_host": bad}).jump_host == ""
          for bad in (42, ["a"], {"a": 1}, None, True)))

_standalone_file = _project_file("v1123-jump.json", [
    {"id": "s-1", "alias": "web", "host": "10.1.1.5", "user": "root",
     "jump_host": "ops@bastion:2222"},
])
check("§2 the file reader of the standalone terminal sees the SAME field",
      [d.jump_host for d in read_project_servers(_standalone_file)] == ["ops@bastion:2222"])
check("§2 the schema did NOT move (an ADDITIVE key, `VERSION_FORMAT` stays 0.9)",
      'VERSION_FORMAT = "0.9"' in _read("version.py"))

_dlg = AddServerDialog(None, edit_data=_jump_data)
check("§2 the server properties dialog shows the value it holds",
      _dlg.jump_host.text() == "bastion.example.com"
      and _dlg.jump_host.isEnabled() is True)
_edited = _dlg.get_data()
check("§2 ...and writes back exactly what the user left (the dialog is the field's ONE editor)",
      _edited.jump_host == "bastion.example.com")
_dlg.jump_host.setText("  ops@bastion:2222  ")
check("§2 the value is stored STRIPPED (a trailing space never reaches `ssh -J`)",
      _dlg.get_data().jump_host == "ops@bastion:2222")

_dlg_u = AddServerDialog(None, edit_data=_jump_data)
_dlg_u.unmanaged.setChecked(True)
check("§2 an UNMANAGED card carries no jump host — the credential family rule",
      _dlg_u.jump_host.text() == "" and _dlg_u.get_data().jump_host == ""
      and _dlg_u.jump_host.isEnabled() is False)
_dlg_u.unmanaged.setChecked(False)
check("§2 ...and unticking the box GIVES THE VALUE BACK (nothing is lost by a mis-click)",
      _dlg_u.jump_host.text() == "bastion.example.com"
      and _dlg_u.get_data().jump_host == "bastion.example.com")
check("§2 the dialog reads its label and its hint from the i18n keys (no literal sentence)",
      "server.jump_label" in _read("dialogs", "add_server_dialog.py")
      and "server.jump_hint" in _read("dialogs", "add_server_dialog.py")
      and all(LANGS[c].get("server.jump_label") and LANGS[c].get("server.jump_hint") for c in LANGS))
for _d in (_dlg, _dlg_u):
    _d.deleteLater()

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the importer: the jump is FILLED, not dropped ==")
# ════════════════════════════════════════════════════════════════════════════

_CONFIG = (
    "Host jump-1\n"
    "    HostName 10.0.0.9\n"
    "    User ops\n"
    "    Port 2222\n"
    "    ProxyJump ops@bastion.example.com\n"
    "    ProxyCommand nc -X connect %h %p\n"
    "\n"
    "Host plain-1\n"
    "    HostName 10.0.0.10\n"
    "    ProxyJump first.example.com\n"
    "    ProxyJump second.example.com\n"
    "\n"
    "Host cleared-1\n"
    "    HostName 10.0.0.11\n"
    "    ProxyJump none\n"
)
_result = SCI.parse_ssh_config(_CONFIG, "cfg")
_by_alias = {h.alias: h for h in _result.hosts}
check("§3 `ProxyJump` becomes the node's jump host (the `-J` value, verbatim)",
      _by_alias["jump-1"].jump_host == "ops@bastion.example.com"
      and _by_alias["jump-1"].host == "10.0.0.9" and _by_alias["jump-1"].port == 2222,
      _by_alias["jump-1"].jump_host)
check("§3 `ProxyCommand` is still a NOTE — a command is not a `-J` spec",
      [i.reason for i in _result.notes].count(SCI.NOTE_PROXY) == 1
      and _by_alias["jump-1"].jump_host == "ops@bastion.example.com")
check("§3 the FIRST `ProxyJump` wins, like every other option of the parse",
      _by_alias["plain-1"].jump_host == "first.example.com", _by_alias["plain-1"].jump_host)
check("§3 the documented `none` idiom clears the value instead of becoming a host",
      _by_alias["cleared-1"].jump_host == "")
check("§3 the note the dialog renders names the directive that really was dropped",
      "ProxyJump" not in i18n.t("sshconfig.note.proxy")
      and "ProxyCommand" in i18n.t("sshconfig.note.proxy"),
      i18n.t("sshconfig.note.proxy"))

_dlg_imp = SshConfigImportDialog(_result.hosts, _result.skipped, _result.notes, "cfg")
_rows_imp = [_dlg_imp.tree.topLevelItem(i) for i in range(_dlg_imp.tree.topLevelItemCount())]
check("§3 the import picker carries the jump as its OWN column (a hidden value is not a choice)",
      _dlg_imp.tree.columnCount() == 6
      and _dlg_imp.tree.headerItem().text(5) == i18n.t("sshconfig.col_jump")
      and _rows_imp[0].text(5) == "ops@bastion.example.com",
      str([_r.text(5) for _r in _rows_imp]))
check("§3 ...and the parsed record the row returns is the one the import writes onto the node",
      _dlg_imp.selected_hosts()[0].jump_host == "ops@bastion.example.com"
      and "jump_host=str(getattr(host, \"jump_host\", \"\") or \"\")"
      in _read("ui", "main_window_node_ops.py"))
_dlg_imp.deleteLater()

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the external terminal carries the jump, the internal path does not ==")
# ════════════════════════════════════════════════════════════════════════════

_EXT_ARGS = ET.build_ssh_args("10.0.0.9", "ops", 2222, None, "bastion.example.com")
check("§4 `-J` reaches the OS ssh client with its value in ONE argument",
      _EXT_ARGS[_EXT_ARGS.index("-J") + 1] == "bastion.example.com"
      and ET.build_ssh_args("10.0.0.9", "ops", 2222) ==
      [a for a in _EXT_ARGS if a not in ("-J", "bastion.example.com")],
      str(_EXT_ARGS))
check("§4 a jump the foreign parser could act on is refused BEFORE a launcher is looked for",
      ET.validate_target("10.0.0.9", "ops", "bastion;calc") == ET.TARGET_BAD_JUMP
      and ET.validate_target("10.0.0.9", "ops", "10.0.0.5&calc") == ET.TARGET_BAD_JUMP
      and ET.jump_problem("ops@bastion:2222") is None)


class _Recorder:
    """The `external_terminal` seam: a MODULE-shaped stub, every call recorded, one canned answer."""

    def __init__(self, answer=(True, None)):
        self.answer = answer
        self.calls = []

    def connect_external(self, **kwargs):
        self.calls.append(kwargs)
        return self.answer


class _Bar:
    def showMessage(self, *_a, **_k):
        return None


# The shipped stub-`self` technique: `host_attr()` reads the FACADE module through
# `type(self).__module__`, so the stub is built with that name (the v1.7.5.1 test's own trick).
_ExtSelf = type("_ExtSelf", (), {"__module__": "ui.main_window"})

import ui.main_window_ssh as MWS  # noqa: E402


def _stub_self():
    """A window stub the door accepts: the facade globals resolve exactly as they do in the window."""
    stub = _ExtSelf()
    stub.log = None
    stub.t = lambda key, **kwargs: i18n.t(key, **kwargs) if kwargs else i18n.t(key)
    stub.statusBar = lambda: _Bar()
    stub._refuse_unmanaged = lambda node, key: False
    return stub


class _JumpNode:
    class data:
        host = "10.0.0.9"
        user = "ops"
        ssh_port = 2222
        key_path = ""
        alias = "jump-1"
        jump_host = "ops@bastion.example.com"


_orig_ext = MW._ext_term
_rec = _Recorder()
MW._ext_term = _rec
try:
    SshMixin._connect_ssh_external(_stub_self(), _JumpNode())
finally:
    MW._ext_term = _orig_ext
check("§4 the map's door hands the node's jump host to `connect_external()`",
      _rec.calls and _rec.calls[0].get("jump") == "ops@bastion.example.com"
      and _rec.calls[0].get("host") == "10.0.0.9",
      str(_rec.calls))

_boxes = []
_orig_warning = MWS.QMessageBox.warning
MWS.QMessageBox.warning = staticmethod(lambda *a, **k: _boxes.append(a[2] if len(a) > 2 else ""))
_rec_bad = _Recorder(answer=(False, "bad_jump"))
MW._ext_term = _rec_bad
try:
    SshMixin._connect_ssh_external(_stub_self(), _JumpNode())
finally:
    MW._ext_term = _orig_ext
    MWS.QMessageBox.warning = _orig_warning
check("§4 ...and a refused jump is REPORTED with the shipped sentence (never a silent return)",
      _boxes == [i18n.t("ssh_ext.bad_jump")], str(_boxes))

import dialogs.ssh_connect_dialog as SCD  # noqa: E402

_orig_dlg_ext = ET.connect_external
_orig_dlg_critical = SCD.QMessageBox.critical
_rec_dlg = _Recorder(answer=(False, "popen_failed"))
ET.connect_external = _rec_dlg.connect_external
SCD.QMessageBox.critical = staticmethod(lambda *a, **k: None)
try:
    _sdlg = SCD.SSHConnectDialog(ServerData(id="j-9", alias="jump-1", host="10.0.0.9",
                                            user="ops", ssh_port=2222,
                                            jump_host="ops@bastion.example.com"))
    _sdlg._open_external()
finally:
    ET.connect_external = _orig_dlg_ext
    SCD.QMessageBox.critical = _orig_dlg_critical
check("§4 the SHIPPED connect dialog's own external door passes it too",
      _rec_dlg.calls and _rec_dlg.calls[0].get("jump") == "ops@bastion.example.com",
      str(_rec_dlg.calls))
_sdlg.deleteLater()

_connect_src = _read("modules", "ssh_connect.py")
_mws_src = _read("ui", "main_window_ssh.py")
check("§4 the INTERNAL path never reads the field — no `direct-tcpip`, no jump in the builder",
      "jump" not in _connect_src
      and all("jump_host" not in _read(*parts)
              for parts in (("modules", "ssh_terminal.py"), ("modules", "terminal_page.py"),
                            ("services", "system_info_collector.py")))
      and "jump_host" in _func_body(_mws_src, "_connect_ssh_external")
      and "jump_host" not in _func_body(_mws_src, "_run_ssh_connect"),
      str(_mws_src.count("jump_host")))
check("§4 ...and the ONE connect builder keeps its signature (the jump is the OS client's job)",
      "jump" not in SC.build_connect_kwargs.__code__.co_varnames
      and "sock" not in SC.build_connect_kwargs.__code__.co_varnames,
      str(SC.build_connect_kwargs.__code__.co_varnames))

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the reader's encoding is a PER-PANE choice ==")
# ════════════════════════════════════════════════════════════════════════════

_CYR = "\u041f\u0440\u0438\u0432\u0435\u0442, \u043c\u0438\u0440\n"      # "Привет, мир"
_FS = FakeSftpFS()
_FS.add_dir("/etc")
_FS.add_file("/etc/cyr.txt", _CYR.encode("cp1251"), mtime=1_700_000_000)
_FS.add_file("/etc/alt.txt", _CYR.encode("cp866"), mtime=1_700_000_000)
_tab, _worker = _make_tab(_FS, commander=True)
_pane_a, _pane_b = _tab.panes[0], _tab.panes[1]
_pane_a._relist("/etc")
_pane_b._relist("/etc")
check("§5 both panes start from the ONE remembered default (a fresh profile — `auto`)",
      wait_for(lambda: "cyr.txt" in _rows(_pane_a) and "alt.txt" in _rows(_pane_b))
      and _pane_a.viewer_encoding_choice == _pane_b.viewer_encoding_choice == "auto",
      f"{_pane_a.viewer_encoding_choice}/{_pane_b.viewer_encoding_choice}")

_open(_pane_a, "cyr.txt")
check("§5 under `auto` the CP1251 file is mojibake (the shipped rule cannot know the codec)",
      _pane_a.viewer_encoding == "latin-1" and _pane_a.viewer_text.toPlainText() != _CYR)
_pane_a._on_encoding_chosen("cp1251")
check("§5 the pane's menu applies the codec to THAT pane and re-reads ITS file",
      wait_for(lambda: _pane_a.viewer_text.toPlainText() == _CYR, timeout_ms=10000)
      and _pane_a.viewer_encoding == "cp1251"
      and _pane_a.viewer_encoding_choice == "cp1251",
      f"{_pane_a.viewer_encoding}/{_pane_a.viewer_encoding_choice}")
check("§5 ...and the SIBLING keeps its own choice (the value is no longer a ceiling)",
      _pane_b.viewer_encoding_choice == "auto", _pane_b.viewer_encoding_choice)
check("§5 the chosen codec is still remembered as the DEFAULT of the container",
      read_cfg().get(STAB.VIEWER_ENCODING_CONFIG) == "cp1251",
      str(read_cfg().get(STAB.VIEWER_ENCODING_CONFIG)))

_pane_a.close_viewer()
_check_b = _open(_pane_b, "alt.txt")
_pane_b._on_encoding_chosen("cp866")
check("§5 the second pane reads its OWN file through its OWN choice (not the sibling's)",
      wait_for(lambda: _pane_b.viewer_text.toPlainText() == _CYR, timeout_ms=10000)
      and _pane_b.viewer_encoding == "cp866"
      and _pane_a.viewer_encoding_choice == "cp1251",
      f"{_pane_b.viewer_encoding}/{_pane_a.viewer_encoding_choice}")

_pane_b.close_viewer()
_open(_pane_a, "cyr.txt")
check("§5 the fight is over: the first pane re-reads its file with ITS codec, untouched",
      wait_for(lambda: _pane_a.viewer_text.toPlainText() == _CYR, timeout_ms=10000)
      and _pane_a.viewer_encoding == "cp1251",
      f"{_pane_a.viewer_encoding}/{_pane_a.viewer_encoding_choice}")
_menu = _pane_a._build_viewer_menu()
check("§5 the submenu of a pane mirrors THAT pane's value (a rebuild never shares a checkmark)",
      _pane_a._encoding_actions["cp1251"].isChecked()
      and not _pane_a._encoding_actions["cp866"].isChecked())
_menu.deleteLater()
_pane_a.close_viewer()

check("§5 a container-wide change still walks EVERY pane (the default is what a pane starts from)",
      _tab.apply_viewer_encoding("cp866") == "cp866"
      and all(p.viewer_encoding_choice == "cp866" for p in _tab.panes)
      and read_cfg().get(STAB.VIEWER_ENCODING_CONFIG) == "cp866",
      str([p.viewer_encoding_choice for p in _tab.panes]))
_tab_fresh = SftpTab()
check("§5 ...and the NEXT pane is born with it (resolution stays ONCE per pane)",
      _tab_fresh.panes[0].viewer_encoding_choice == "cp866",
      _tab_fresh.panes[0].viewer_encoding_choice)
_tab_fresh.deleteLater()
check("§5 the declaration keeps the ONE key and the pane-scoped door in the code",
      STAB.VIEWER_ENCODING_CONFIG == "ui_viewer_encoding"
      and "def apply_viewer_encoding(self, codec, pane=None)" in _read("modules", "sftp_tab.py")
      and "apply_viewer_encoding(codec, pane=self)" in PANE_SRC,
      STAB.VIEWER_ENCODING_CONFIG)
write_cfg({})
_worker.shutdown(wait_ms=2500)

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the standalone does not ask `terminal_max_open` ==")
# ════════════════════════════════════════════════════════════════════════════

_ts_src = _read("modules", "terminal_standalone.py")
_contract = _read("TERMINAL_STANDALONE.md")
check("§6 the exemption is WRITTEN into the contract's connect-door section (R14(c))",
      "terminal_max_open" in _contract
      and "deliberately NOT asked" in _contract
      and "`window.add_session()` directly" in _contract)
check("§6 the surface really asks no limit and calls `add_session()` on the shipped window",
      "max_open" not in _ts_src
      and "terminal_max_open" not in _ts_src
      and "self.window.add_session(data" in _ts_src)
check("§6 ...while the MAP's door keeps the shipped limit and its eviction question",
      "max_open" in _read("ui", "main_window_ssh.py")
      and "terminal_limit_close_oldest" in _read("ui", "main_window_ssh.py"))

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the i18n and the release state ==")
# ════════════════════════════════════════════════════════════════════════════

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
_NEW_KEYS = ("server.jump_label", "server.jump_hint", "sshconfig.col_jump")
check("§7 the release adds the THREE keys of the jump field to EVERY language at once",
      EXPECTED_I18N_KEYS == 1117
      and all(len(translation_keys(LANGS[c])) == EXPECTED_I18N_KEYS for c in LANGS)
      and all(LANGS[c].get(k) for c in LANGS for k in _NEW_KEYS),
      f"{EXPECTED_I18N_KEYS} / " + str({c: len(translation_keys(LANGS[c])) for c in sorted(LANGS)}))
check("§7 the sentences the release re-uses are the SHIPPED ones",
      all(LANGS["en"].get(k) for k in ("sshconfig.note.proxy", "terminal.history.secret_refused",
                                       "ssh_ext.bad_jump", "sftp.viewer.encoding")))

check_release_state(ROOT)
check("§7 the pin names this line's release or a later one",
      releases_at_least(EXPECTED_APP_VERSION, "1.12.3"), EXPECTED_APP_VERSION)
check("§7 no new dependency and no new config key came with the release",
      "jump" not in _read("requirements.txt")
      and STAB.VIEWER_ENCODING_CONFIG == "ui_viewer_encoding")
check("§7 the topical file is listed by the suite map (tests/INDEX.md regenerated)",
      "test_followups_v1123.py" in _read("tests", "INDEX.md"))

finish()
