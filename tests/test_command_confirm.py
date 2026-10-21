# -*- coding: utf-8 -*-
"""The command that asks first: the `confirm` flag of a library record and the ONE question
between a double click and the wire (`modules/command_library.py`).

Offscreen, no network, no real session (a fake page + the `QMessageBox` module seam). §1 the
record; §2 the form (the box UNDER `Enabled`, its defaults); §3 the door (asked, Yes, No, no
dialog, disabled); §4 the target (no session, the split-pane seam); §5 the hand-overs (import,
export, duplicate, the History door); §6 the keys and the release — contract `DOCUMENTATION.md` §14e.
Run: python tests/test_command_confirm.py   (from the project root) or python tests/run_all.py"""
import json
import os
import sys
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QDialog, QFormLayout

from _common import (bootstrap, check, finish, load_i18n_langs, check_i18n_parity,
                     check_i18n_format, check_release_state, releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation inside)

app = QApplication(sys.argv)

import i18n
import modules.command_library as CL

i18n.set_language("en")   # the assertions read the English labels of the keys

STATUS_TIMEOUT = 4000
CONFIRM_KEYS = ("terminal.cmdlib.confirm_required", "terminal.cmdlib.confirm_tooltip",
                "terminal.cmdlib.confirm_title", "terminal.cmdlib.confirm_send")


def store_path(name):
    return os.path.join(WORK, name)


def fresh_store(name):
    path = store_path(name)
    if os.path.isfile(path):
        os.remove(path)
    return CL.CommandLibraryStore(path=path)


class _Widget:
    """The `page.widget` of the send path: records the bytes, answers True/False."""

    def __init__(self, ok=True):
        self.sent = []
        self.ok = ok

    def send_macro(self, text):
        self.sent.append(text)
        return self.ok


class _Page:
    """A session page as the panel sees it: `widget.send_macro` + `server_data.alias`."""

    def __init__(self, alias="srv-1", ok=True):
        self.server_data = SimpleNamespace(alias=alias)
        self.widget = _Widget(ok)


class _Tabs:
    """The duck-typed session QTabWidget: only `currentWidget()` is asked."""

    def __init__(self, page=None):
        self.page = page

    def currentWidget(self):
        return self.page


class _Box:
    """The `QMessageBox` module seam: records the question, answers `reply`, may explode."""

    Yes, No = 16384, 65536
    reply = Yes
    explode = False
    calls = []

    @classmethod
    def question(cls, *args, **kwargs):
        cls.calls.append((args, kwargs))
        if cls.explode:
            raise RuntimeError("no dialog on this platform")
        return cls.reply

    @classmethod
    def reset(cls, reply=None, explode=False):
        cls.calls = []
        cls.reply = cls.Yes if reply is None else reply
        cls.explode = explode


def make_panel(name, page=None, provider=None):
    """A panel over its own store, its status messages collected, the fake target installed."""
    panel = CL.CommandLibraryPanel(None, store=fresh_store(name))
    panel.messages = []
    panel.status_message.connect(lambda text, ms: panel.messages.append((text, ms)))
    if provider is not None:
        panel.set_active_session_provider(provider)
    elif page is not None:
        panel.set_session_tabs(_Tabs(page))
    return panel


def record(confirm=True, enabled=True, name="Deploy", command="systemctl restart app"):
    return {"id": "cf-1", "name": name, "command": command,
            "category": "Ops", "enabled": enabled, "confirm": confirm}


class _StubDialog:
    """The dialog seam of `add_from_history()`: the ADD form, pre-filled, accepted."""

    last = {}

    def __init__(self, entry=None, categories=None, parent=None):
        _StubDialog.last = {"entry": dict(entry or {}), "categories": list(categories or [])}

    def exec(self):
        return QDialog.DialogCode.Accepted

    def result_entry(self):
        return {"name": "ls", "category": "", "command": "ls -la",
                "enabled": True, "confirm": False}


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the record: the flag, the default, the round trip ==")
# ════════════════════════════════════════════════════════════════════════════

_norm = CL.CommandLibraryStore._normalize({"name": "n", "command": "c"})
check("§1 a record without `confirm` normalizes to False (the additive default)",
      _norm is not None and _norm["confirm"] is False, str(_norm))
check("§1 ...and the normalized field set carries it ALWAYS",
      set(_norm) == {"id", "name", "command", "category", "enabled", "confirm"}, str(sorted(_norm)))
check("§1 a truthy foreign value reads True and a falsey one reads False",
      CL.CommandLibraryStore._normalize({"name": "n", "command": "c", "confirm": "yes"})["confirm"]
      is True
      and CL.CommandLibraryStore._normalize({"name": "n", "command": "c", "confirm": 0})["confirm"]
      is False)
check("§1 an invalid record is still dropped (the flag does not rescue it)",
      CL.CommandLibraryStore._normalize({"name": "", "command": "c", "confirm": True}) is None)

check("§1 needs_confirmation is the ONE reader (True / False / absent / not a dict)",
      CL.needs_confirmation({"confirm": True}) is True
      and CL.needs_confirmation({"confirm": False}) is False
      and CL.needs_confirmation({"name": "n"}) is False
      and CL.needs_confirmation(None) is False
      and CL.needs_confirmation("confirm") is False)

_s1 = fresh_store("cf_round.json")
_rec = record(confirm=True)
_s1.save([_rec, {"id": "cf-2", "name": "Quiet", "command": "uptime", "category": "",
                 "enabled": True, "confirm": False}])
_lib = _s1.load()
check("§1 round trip: both flags survive the write",
      [e["confirm"] for e in _lib] == [True, False], str(_lib))
with open(_s1.path, encoding="utf-8") as f:
    _doc = json.load(f)
check("§1 the document writes the flag on EVERY record",
      all("confirm" in e for e in _doc["commands"]), str(_doc["commands"]))
check("§1 a foreign key of the file is dropped by the normalization (the record has ONE shape)",
      all(set(e) == {"id", "name", "command", "category", "enabled", "confirm"} for e in _lib))

_seeds = fresh_store("cf_seeds.json").load()
check("§1 the seeds carry confirm=False (a seed is an example, not a policy)",
      len(_seeds) == 5 and all("confirm" in e and e["confirm"] is False for e in _seeds))


# ════════════════════════════════════════════════════════════════════════════
print("== §2 the form: the box under Enabled, the defaults, result_entry() ==")
# ════════════════════════════════════════════════════════════════════════════

_dlg = CL.CommandLibraryDialog(None, categories=["Ops", "Logs"])
_form = _dlg.layout()
check("§2 the ADD form opens with the confirmation box UNCHECKED",
      _dlg.confirm_check.isChecked() is False and _dlg.enabled_check.isChecked() is True)
check("§2 the box wears its own label and tooltip (the four keys of §6)",
      _dlg.confirm_check.text() == i18n.t("terminal.cmdlib.confirm_required")
      and _dlg.confirm_check.toolTip() == i18n.t("terminal.cmdlib.confirm_tooltip"),
      f"{_dlg.confirm_check.text()!r} / {_dlg.confirm_check.toolTip()!r}")
check("§2 the box sits UNDER `Enabled` in the same form (the record's two switches together)",
      isinstance(_form, QFormLayout)
      and _form.itemAt(3, QFormLayout.ItemRole.FieldRole).widget() is _dlg.enabled_check
      and _form.itemAt(4, QFormLayout.ItemRole.FieldRole).widget() is _dlg.confirm_check,
      f"rows={_form.rowCount()}")

_result = _dlg.result_entry()
check("§2 result_entry carries the flag (name/category/command/enabled/confirm)",
      set(_result) == {"name", "category", "command", "enabled", "confirm"}
      and _result["confirm"] is False, str(_result))
_dlg.confirm_check.setChecked(True)
check("§2 ...and it follows the box",
      _dlg.result_entry()["confirm"] is True)

_edit = CL.CommandLibraryDialog(record(confirm=True), categories=["Ops"])
check("§2 the EDIT form reads the flag of the record",
      _edit.confirm_check.isChecked() is True)
_edit_quiet = CL.CommandLibraryDialog(record(confirm=False), categories=["Ops"])
check("§2 ...and an unflagged record opens unchecked",
      _edit_quiet.confirm_check.isChecked() is False)
_prefilled = CL.CommandLibraryDialog({"name": "n", "command": "c", "category": "",
                                      "enabled": True, "confirm": True}, categories=[])
check("§2 a pre-filled ID-LESS record (the History door) opens as the ADD form, flag read",
      _prefilled.windowTitle() == i18n.t("terminal.cmdlib.add")
      and _prefilled.confirm_check.isChecked() is True)
for _d in (_dlg, _edit, _edit_quiet, _prefilled):
    _d.deleteLater()


# ════════════════════════════════════════════════════════════════════════════
print("== §3 the door: asked / not asked / Yes / No / no dialog / disabled ==")
# ════════════════════════════════════════════════════════════════════════════

_orig_box = CL.QMessageBox
CL.QMessageBox = _Box
try:
    # a quiet record — no question at all
    _p = make_panel("cf_door.json", page=_Page())
    _Page_target = _p.session_tabs.currentWidget()
    _Box.reset()
    _p.send_entry(record(confirm=False))
    check("§3 a record without the flag is sent with NO question",
          _Box.calls == [] and _Page_target.widget.sent == ["systemctl restart app"],
          f"calls={len(_Box.calls)} sent={_Page_target.widget.sent}")

    # the asking record — Yes sends the exact command text
    _Box.reset()
    _p.send_entry(record(confirm=True))
    check("§3 a flagged record asks ONE question and Yes sends the command",
          len(_Box.calls) == 1 and _Page_target.widget.sent[-1] == "systemctl restart app",
          f"calls={len(_Box.calls)} sent={_Page_target.widget.sent}")
    _args, _kw = _Box.calls[0]
    check("§3 the question names the RECORD (its name, never its command text)",
          _args[1] == i18n.t("terminal.cmdlib.confirm_title")
          and _args[2] == i18n.t("terminal.cmdlib.confirm_send", name="Deploy"),
          f"{_args[1:3]}")
    check("§3 the buttons are Yes/No and the DEFAULT is No",
          _args[3] == (_Box.Yes | _Box.No) and _args[4] == _Box.No, str(_args[3:]))
    check("§3 the sent status line is the shipped sent_to({alias})",
          _p.messages[-1] == (i18n.t("terminal.cmdlib.sent_to", alias="srv-1"), STATUS_TIMEOUT),
          str(_p.messages))

    # No — nothing sent, silence
    _Box.reset(reply=_Box.No)
    _n_sent = len(_Page_target.widget.sent)
    _n_msgs = len(_p.messages)
    _p.send_entry(record(confirm=True))
    check("§3 No sends NOTHING and says nothing (a refusal is not a failure)",
          len(_Page_target.widget.sent) == _n_sent and len(_p.messages) == _n_msgs,
          f"sent={_Page_target.widget.sent} msgs={_p.messages}")

    # a dialog that cannot be shown — nothing sent, no exception, silence
    _Box.reset(explode=True)
    _n_sent = len(_Page_target.widget.sent)
    _n_msgs = len(_p.messages)
    _p.send_entry(record(confirm=True))
    check("§3 a dialog that cannot be shown sends NOTHING and says nothing",
          len(_Page_target.widget.sent) == _n_sent and len(_p.messages) == _n_msgs,
          f"sent={_Page_target.widget.sent} msgs={_p.messages}")

    # a disabled record — no question, no send (the shipped rule comes FIRST)
    _Box.reset()
    _p.send_entry(record(confirm=True, enabled=False))
    check("§3 a DISABLED record asks nothing and sends nothing",
          _Box.calls == [] and len(_Page_target.widget.sent) == _n_sent, str(_Page_target.widget.sent))

    # a dead channel (send_macro answers False) — the question was asked, the sentence is the shipped one
    _dead = _Page(alias="dead", ok=False)
    _p2 = make_panel("cf_dead.json", page=_dead)
    _Box.reset()
    _p2.send_entry(record(confirm=True))
    check("§3 a dead session answers no_active_session (the question was asked first)",
          len(_Box.calls) == 1
          and _p2.messages[-1] == (i18n.t("terminal.cmdlib.no_active_session"), STATUS_TIMEOUT),
          str(_p2.messages))
finally:
    CL.QMessageBox = _orig_box


# ════════════════════════════════════════════════════════════════════════════
print("== §4 the target: no session → the sentence and NO dialog; the split-pane seam ==")
# ════════════════════════════════════════════════════════════════════════════

CL.QMessageBox = _Box
try:
    _Box.reset()
    _none = make_panel("cf_nosess.json")
    _none.send_entry(record(confirm=True))
    check("§4 no session → the shipped no_active_session sentence and NO question",
          _Box.calls == []
          and _none.messages == [(i18n.t("terminal.cmdlib.no_active_session"), STATUS_TIMEOUT)],
          f"calls={len(_Box.calls)} msgs={_none.messages}")

    _empty = make_panel("cf_empty.json", page=None)
    _empty.set_session_tabs(_Tabs(None))
    _Box.reset()
    _empty.send_entry(record(confirm=True))
    check("§4 an empty QTabWidget → the same sentence, still no question",
          _Box.calls == [] and _empty.messages[0][0] == i18n.t("terminal.cmdlib.no_active_session"),
          f"calls={len(_Box.calls)} msgs={_empty.messages}")

    # the split pane: the container's active_session provider WINS over currentWidget()
    _tab_page = _Page(alias="tab")
    _split_page = _Page(alias="split")
    _split = make_panel("cf_split.json", page=_tab_page,
                        provider=lambda: _split_page)
    _Box.reset()
    _split.send_entry(record(confirm=True))
    check("§4 the active-session provider (the split pane) is the target, not the tab",
          _split_page.widget.sent == ["systemctl restart app"]
          and _tab_page.widget.sent == [] and len(_Box.calls) == 1,
          f"split={_split_page.widget.sent} tab={_tab_page.widget.sent}")
    check("§4 ...and the status names THAT session",
          _split.messages[-1][0] == i18n.t("terminal.cmdlib.sent_to", alias="split"))
finally:
    CL.QMessageBox = _orig_box


# ════════════════════════════════════════════════════════════════════════════
print("== §5 the hand-overs: import, export, duplicate, the History door ==")
# ════════════════════════════════════════════════════════════════════════════

SOURCE = store_path("cf_import_src.json")
with open(SOURCE, "w", encoding="utf-8") as f:
    json.dump({"seeded": True, "commands": [
        {"id": "old-1", "name": "Legacy", "command": "uptime", "category": "", "enabled": True},
    ]}, f)
_reader = CL.read_library_file(SOURCE)
check("§5 the import READER normalizes a file that has no flag (the default, no migration)",
      _reader["ok"] is True and _reader["entries"][0]["confirm"] is False, str(_reader))

_target = store_path("cf_import_dst.json")
if os.path.isfile(_target):
    os.remove(_target)
_panel = CL.CommandLibraryPanel(None, store=CL.CommandLibraryStore(path=_target))
_panel.messages = []
_panel.status_message.connect(lambda text, ms: _panel.messages.append((text, ms)))
CL.QMessageBox = _Box
try:
    _Box.reset(reply=_Box.Yes)
    check("§5 the import replaces the library", _panel.import_library(SOURCE) is True,
          str(_panel.messages))
finally:
    CL.QMessageBox = _orig_box
_saved_import = CL.CommandLibraryStore(path=_target).load()
check("§5 ...and the file it writes carries confirm on every record",
      bool(_saved_import) and all("confirm" in e for e in _saved_import), str(_saved_import))

EXPORTED = store_path("cf_export.json")
check("§5 export writes the flag (the store's own document)",
      _panel.export_library(EXPORTED) is True)
with open(EXPORTED, encoding="utf-8") as f:
    _exported_doc = json.load(f)
check("§5 ...on the exported record",
      all("confirm" in e for e in _exported_doc["commands"]), str(_exported_doc["commands"]))

_panel._entries = [record(confirm=True)]
_panel._commit()
_panel._duplicate_entry(_panel._entries[0])
_dup_lib = CL.CommandLibraryStore(path=_target).load()
check("§5 a duplicate keeps the flag (the copy is the record's own switch)",
      len(_dup_lib) == 2 and all(e["confirm"] is True for e in _dup_lib)
      and len({e["id"] for e in _dup_lib}) == 2, str(_dup_lib))
_panel._entries = [record(confirm=True),
                   {"id": "cf-stale", "name": "Stale", "command": "true",
                    "category": "", "enabled": True}]
_panel._duplicate_entry(_panel._entries[1])
_stale_lib = CL.CommandLibraryStore(path=_target).load()
check("§5 ...and a stale copy without the flag is written as False (always written)",
      sorted(e["name"] for e in _stale_lib) == ["Deploy", "Stale", "Stale"]
      and all("confirm" in e for e in _stale_lib)
      and all(e["confirm"] is (e["name"] == "Deploy") for e in _stale_lib), str(_stale_lib))

_orig_dialog = CL.CommandLibraryDialog
CL.CommandLibraryDialog = _StubDialog
try:
    _history_ok = _panel.add_from_history("ls -la")
finally:
    CL.CommandLibraryDialog = _orig_dialog
check("§5 the History door opens the ADD form with confirm=False pre-filled",
      _history_ok is True and _StubDialog.last["entry"].get("confirm") is False,
      str(_StubDialog.last))
_history_lib = CL.CommandLibraryStore(path=_target).load()
check("§5 ...and the record it writes carries the flag",
      any(e["name"] == "ls" and e["confirm"] is False for e in _history_lib), str(_history_lib))


# ════════════════════════════════════════════════════════════════════════════
print("== §6 the keys and the release ==")
# ════════════════════════════════════════════════════════════════════════════

LANGS = load_i18n_langs(ROOT)
check("§6 the four confirm keys exist in ALL language files",
      all(k in LANGS[c] for c in LANGS for k in CONFIRM_KEYS),
      str({c: [k for k in CONFIRM_KEYS if k not in LANGS[c]] for c in LANGS}))
check("§6 the question carries the {name} placeholder in every language",
      all("{name}" in LANGS[c]["terminal.cmdlib.confirm_send"] for c in LANGS),
      str({c: LANGS[c]["terminal.cmdlib.confirm_send"] for c in LANGS}))
check("§6 ...and no label is empty",
      all(str(LANGS[c][k]).strip() for c in LANGS for k in CONFIRM_KEYS))

check_i18n_parity(LANGS)
check_i18n_format(LANGS)
check_release_state(ROOT)
from version import APP_VERSION  # noqa: E402 — read after bootstrap (the release pin)
check("§6 the release is v1.13.5 or later (this batch is the release)",
      releases_at_least(APP_VERSION, "1.13.5"), APP_VERSION)

finish()
