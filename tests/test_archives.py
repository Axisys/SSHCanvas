# -*- coding: utf-8 -*-
"""The archive view (v1.13) — the READ half of `ARCHIVES.md`.

§1 the declared family and the pure readers; §2 the LISTING the standard library answers; §3 the
encrypted archive that lists and refuses without asking for a password; §4 the bounded member read;
§5 the declared cap and the spool over `modules/sftp_send.py`; §6 the pane — the ONE row, the spool
leg and the panel that moves into the other pane; §7 the local source, the abandoned leg and the
transport change; §8 the language files and the release state. Offscreen and hermetic: the remote
half runs over `_fakes.py`, the local half over a real HOME tree (`DOCUMENTATION.md` §76)."""
import io
import os
import shutil
import sys
import tarfile
import zipfile

from _common import (bootstrap, check, check_i18n_format, check_i18n_parity, check_release_state,
                     clear_cfg, finish, load_i18n_langs, pane_func_owner, read_cfg, wait_for,
                     write_cfg, EXPECTED_APP_VERSION, EXPECTED_I18N_KEYS, releases_at_least)

ROOT, WORK = bootstrap()  # BEFORE the app module imports (the HOME isolation)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import i18n  # noqa: E402
import modules.archive_view as AV  # noqa: E402
import modules.sftp_pane_dnd as PDND  # noqa: E402
import modules.sftp_send as SEND  # noqa: E402
import modules.sftp_tab as STAB  # noqa: E402
import modules.sftp_worker as SW  # noqa: E402
from modules.sftp_tab import SOURCE_LOCAL, SftpTab  # noqa: E402
from modules.sftp_worker import (MAX_READ_BYTES, READ_ERROR_BINARY, READ_ERROR_TOO_LARGE,  # noqa: E402
                                 SftpWorker)

from _fakes import EventLog, FakeSftpClient, FakeSftpFS, wire_worker  # noqa: E402

LANGS = load_i18n_langs(ROOT)
WORK_TREE = os.path.join(WORK, "archives")


def build_zip(path, members):
    """A REAL zip: `members` = [(name, bytes)]; a directory entry ends with "/" and carries none."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    with open(path, "rb") as fh:
        return fh.read()


def build_tar(path, mode="w:gz"):
    """A REAL tar with a directory, a symlink, a hardlink, a fifo and two regular files."""
    with tarfile.open(path, mode) as archive:
        for name, data, mtime in (("etc/app.conf", b"listen 80\n", 1_700_000_100),
                                  ("etc/notes.txt", b"hello archive\n", 1_700_000_200)):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = mtime
            archive.addfile(info, io.BytesIO(data))
        extra = [("etc", tarfile.DIRTYPE, ""), ("etc/latest.conf", tarfile.SYMTYPE, "app.conf"),
                 ("etc/again.conf", tarfile.LNKTYPE, "etc/app.conf"),
                 ("etc/pipe", tarfile.FIFOTYPE, "")]
        for name, kind, target in extra:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.linkname = target
            archive.addfile(info)
    return path


def encrypt_zip(path):
    """Mark every member of a REAL zip as ENCRYPTED — the standard library writes no such file."""
    with open(path, "rb") as fh:
        raw = bytearray(fh.read())
    raw[6:8] = (int.from_bytes(raw[6:8], "little") | AV.ZIP_ENCRYPTED_FLAG).to_bytes(2, "little")
    start = raw.find(b"PK\x01\x02")
    raw[start + 8:start + 10] = (int.from_bytes(raw[start + 8:start + 10], "little")
                                 | AV.ZIP_ENCRYPTED_FLAG).to_bytes(2, "little")
    with open(path, "wb") as fh:
        fh.write(bytes(raw))
    return path


def make_remote_tab(fs, commander=True):
    """(tab, worker, log) over the fake SFTP surface, optionally in the two-pane mode."""
    worker = SftpWorker(FakeSftpClient(fs))
    log = EventLog()
    wire_worker(worker, log)
    worker.start()
    tab = SftpTab()
    tab.message.connect(lambda *_a: None)
    if commander:
        tab.set_commander(True)
    tab.set_worker(worker)
    return tab, worker, log


def rows(pane):
    """The listing as `[(name, is_dir, size)]` — the ORDER is what the checks read."""
    out = []
    for index in range(pane.tree.topLevelItemCount()):
        item = pane.tree.topLevelItem(index)
        out.append((item.text(0), bool(item.data(0, pane.ISDIR_ROLE)),
                    int(item.data(0, pane.SIZE_ROLE) or 0)))
    return out


def item_named(pane, name):
    for index in range(pane.tree.topLevelItemCount()):
        if pane.tree.topLevelItem(index).text(0) == name:
            return pane.tree.topLevelItem(index)
    return None


def wait_row(pane, name, ms=10000):
    return wait_for(lambda: name in [row[0] for row in rows(pane)], timeout_ms=ms)


def action(menu, key):
    """The `QAction` of ONE context-menu row, found by its TRANSLATED text (the seam of §8.4)."""
    label = i18n.t(key)
    for act in menu.actions():
        if act.text() == label:
            return act
    return None


def archive_rows(pane):
    """The archive listing as `[(name, size text)]`."""
    tree = pane.archive_tree
    return [(tree.topLevelItem(i).text(0), tree.topLevelItem(i).text(1))
            for i in range(tree.topLevelItemCount())]


def archive_member_item(pane, name):
    for index in range(pane.archive_tree.topLevelItemCount()):
        item = pane.archive_tree.topLevelItem(index)
        if item.text(0) == name:
            return item
    return None


def open_archive(pane, item, ms=10000):
    """Drive the ONE row and wait for the panel (the remote leg is asynchronous)."""
    pane._op_view_archive(item)
    app.processEvents()
    return wait_for(lambda: pane.archive_open, timeout_ms=ms)


# ════════════════════════════════════════════════════════════════════════════
print("== §1 the declared family and the pure readers ==")
# ════════════════════════════════════════════════════════════════════════════

check("§1 every declared suffix answers its reader, whatever the case and the directories",
      AV.archive_kind("/srv/backup.zip") == "zip"
      and AV.archive_kind("release.CAR") == "zip"
      and AV.archive_kind("app.war") == "zip"
      and AV.archive_kind("lib.jar") == "zip"
      and AV.archive_kind("a/b/c.tar.gz") == "tar"
      and AV.archive_kind("logs.TGZ") == "tar"
      and AV.archive_kind("src.tar.bz2") == "tar"
      and AV.archive_kind("src.tar.xz") == "tar"
      and AV.archive_kind("plain.tar") == "tar",
      str(sorted(AV.ARCHIVE_SUFFIXES)))
check("§1 ...and everything else is NOT an archive of this family (the suffix is a hint)",
      AV.archive_kind("notes.txt") == "" and AV.archive_kind("photo.png") == ""
      and AV.archive_kind("data.gz") == "" and AV.archive_kind("archive.zip.txt") == ""
      and AV.archive_kind("") == "" and AV.archive_kind(None) == "")
check("§1 the two readers are the standard library's, declared ONCE",
      AV.ARCHIVE_KIND_ZIP == "zip" and AV.ARCHIVE_KIND_TAR == "tar"
      and set(AV.ARCHIVE_SUFFIXES.values()) == {AV.ARCHIVE_KIND_ZIP, AV.ARCHIVE_KIND_TAR}
      and all(suffix.startswith(".") for suffix in AV.ARCHIVE_SUFFIXES))
check("§1 `member_name()` drops the `./` noise a tar of a directory carries",
      AV.member_name("./etc/app.conf") == "etc/app.conf"
      and AV.member_name("././etc/app.conf") == "etc/app.conf"
      and AV.member_name("etc/app.conf") == "etc/app.conf"
      and AV.member_name(None) == "")

# ════════════════════════════════════════════════════════════════════════════
print("== §2 the listing: the readable members of ONE level ==")
# ════════════════════════════════════════════════════════════════════════════

ZIP_PATH = os.path.join(WORK, "sample.car")
ZIP_DATA = build_zip(ZIP_PATH, [("etc/app.conf", b"listen 80\n"), ("etc/", b""),
                                ("README.txt", b"hello archive\n"), ("bin/tool", b"\x7fELF\x02\x01"),
                                ("nested.jar", b"PK\x03\x04not really"),
                                ("logo.png", b"\x89PNG\r\n\x1a\n")])
_entries, _encrypted, _code, _cut = AV.archive_listing(ZIP_PATH)
check("§2 a zip lists its FILE members in the archive's own order (a directory entry is not a row)",
      _code == "" and _encrypted is False
      and [e["name"] for e in _entries]
      == ["etc/app.conf", "README.txt", "bin/tool", "nested.jar", "logo.png"],
      str([e["name"] for e in _entries]))
check("§2 ...with the size and the mtime of every member",
      [e["size"] for e in _entries] == [10, 14, 6, 14, 8]
      and all(e["mtime"] > 0 for e in _entries)
      and all(e["raw"] == e["name"] for e in _entries),
      str([(e["size"], e["mtime"]) for e in _entries]))

TAR_PATH = build_tar(os.path.join(WORK, "sample.tar.gz"))
_tar_entries, _tar_encrypted, _tar_code, _tar_cut = AV.archive_listing(TAR_PATH)
check("§2 a `tar.gz` lists its regular files and nothing a reader could not open (a directory, a "
      "symlink, a hardlink and a fifo carry no bytes of their own)",
      _tar_code == "" and _tar_encrypted is False
      and [e["name"] for e in _tar_entries] == ["etc/app.conf", "etc/notes.txt"],
      str([e["name"] for e in _tar_entries]))
check("§2 ...and the tar mtime is the value the archive really carries",
      [e["mtime"] for e in _tar_entries] == [1_700_000_100, 1_700_000_200],
      str([e["mtime"] for e in _tar_entries]))
_tar_only = build_tar(os.path.join(WORK, "plain.tar"), mode="w")
check("§2 a plain `.tar` is read by the same reader (the suffix decides, `r:*` sniffs)",
      [e["name"] for e in AV.archive_listing(_tar_only)[0]] == ["etc/app.conf", "etc/notes.txt"])

EMPTY_PATH = os.path.join(WORK, "empty.zip")
build_zip(EMPTY_PATH, [])
check("§2 an archive with nothing readable answers an EMPTY listing, never a refusal",
      AV.archive_listing(EMPTY_PATH) == ([], False, "", False))

TEXT_PATH = os.path.join(WORK, "not-really.zip")
with open(TEXT_PATH, "w", encoding="utf-8") as fh:
    fh.write("a text file with an archive suffix\n")
BAD_GZ = os.path.join(WORK, "broken.tar.gz")
with open(BAD_GZ, "wb") as fh:
    fh.write(b"\x1f\x8b\x08\x00truncated")
check("§2 a file whose content disagrees with its suffix is UNREADABLE (the parse is the verdict)",
      AV.archive_listing(TEXT_PATH) == ([], False, AV.ARCHIVE_ERROR_UNREADABLE, False)
      and AV.archive_listing(os.path.join(WORK, "gone.zip"))
      == ([], False, AV.ARCHIVE_ERROR_UNREADABLE, False)
      and AV.archive_listing(BAD_GZ) == ([], False, AV.ARCHIVE_ERROR_UNREADABLE, False))
check("§2 ...and a path with no declared suffix is never opened at all",
      AV.archive_listing(TEXT_PATH, "")[2] == AV.ARCHIVE_ERROR_UNREADABLE
      and AV.archive_listing(os.path.join(WORK, "notes.txt"))[2] == AV.ARCHIVE_ERROR_UNREADABLE
      and AV.read_member(os.path.join(WORK, "notes.txt"), "", "x", 10, 0)
      == (b"", AV.ARCHIVE_ERROR_UNREADABLE))

# ════════════════════════════════════════════════════════════════════════════
print("== §3 the encrypted archive lists and refuses, and asks for no password ==")
# ════════════════════════════════════════════════════════════════════════════

ENCRYPTED_PATH = os.path.join(WORK, "secret.zip")
build_zip(ENCRYPTED_PATH, [("secret.txt", b"top secret\n")])
encrypt_zip(ENCRYPTED_PATH)
_sec_entries, _sec_encrypted, _sec_code, _sec_cut = AV.archive_listing(ENCRYPTED_PATH)
check("§3 an encrypted zip LISTS its members and reports the fact",
      _sec_code == "" and _sec_encrypted is True
      and [e["name"] for e in _sec_entries] == ["secret.txt"],
      str((_sec_entries, _sec_encrypted, _sec_code)))
check("§3 ...and its member is REFUSED with the machine code of the encryption (no password)",
      AV.read_member(ENCRYPTED_PATH, "zip", "secret.txt", 4096, 11)
      == (b"", AV.ARCHIVE_ERROR_ENCRYPTED))
check("§3 a readable archive reports no encryption at all",
      AV.archive_listing(ZIP_PATH)[1] is False)

# ════════════════════════════════════════════════════════════════════════════
print("== §4 the member read: the shipped read policy, bounded ==")
# ════════════════════════════════════════════════════════════════════════════

check("§4 a member comes back byte for byte, from a zip and from a tar alike",
      AV.read_member(ZIP_PATH, "zip", "README.txt", 4096, 14) == (b"hello archive\n", "")
      and AV.read_member(TAR_PATH, "tar", "etc/notes.txt", 4096, 14) == (b"hello archive\n", ""))
check("§4 the ceiling TRUNCATES a member instead of refusing it (the shipped rule)",
      AV.read_member(ZIP_PATH, "zip", "README.txt", 5, 14) == (b"hello", "")
      and AV.read_member(TAR_PATH, "tar", "etc/app.conf", 6, 10) == (b"listen", ""))
check("§4 a binary NAME is refused before a byte is read (the extension is the fast path)",
      AV.read_member(ZIP_PATH, "zip", "logo.png", 4096, 8) == (b"", READ_ERROR_BINARY)
      and AV.read_member(ZIP_PATH, "zip", "nested.tar", 4096, 8) == (b"", READ_ERROR_BINARY))
check("§4 ...while an extensionless member is read and screened by its content (the shipped rule)",
      AV.read_member(ZIP_PATH, "zip", "bin/tool", 4096, 6) == (b"\x7fELF\x02\x01", ""))
check("§4 a NESTED archive is refused with the same code — ONE level, no archive in an archive",
      AV.read_member(ZIP_PATH, "zip", "nested.jar", 4096, 15) == (b"", READ_ERROR_BINARY)
      and AV.read_member(ZIP_PATH, "zip", "inner.tar.gz", 4096, 15) == (b"", READ_ERROR_BINARY))
NULL_PATH = os.path.join(WORK, "null.zip")
build_zip(NULL_PATH, [("data.bin", b"head\x00tail")])
check("§4 a NULL byte in the first chunk is refused (the extension lied about the content)",
      AV.read_member(NULL_PATH, "zip", "data.bin", 4096, 9) == (b"", READ_ERROR_BINARY))
check("§4 a member the archive does not hold is unreadable rather than a traceback",
      AV.read_member(ZIP_PATH, "zip", "etc/gone.conf", 4096, 0)
      == (b"", AV.ARCHIVE_ERROR_UNREADABLE)
      and AV.read_member(TAR_PATH, "tar", "etc/gone.conf", 4096, 0)
      == (b"", AV.ARCHIVE_ERROR_UNREADABLE))
check("§4 a link member and a directory member hold nothing a reader could show",
      AV.read_member(TAR_PATH, "tar", "etc/latest.conf", 4096, 0) == (b"", READ_ERROR_BINARY)
      and AV.read_member(TAR_PATH, "tar", "etc", 4096, 0) == (b"", READ_ERROR_BINARY))
check("§4 a cap of ZERO keeps the shipped `too_large` refusal above the default read policy",
      AV.read_member(ZIP_PATH, "zip", "README.txt", 0, MAX_READ_BYTES + 1)
      == (b"", READ_ERROR_TOO_LARGE)
      and AV.read_member(ZIP_PATH, "zip", "README.txt", 0, 14) == (b"hello archive\n", ""))

# ════════════════════════════════════════════════════════════════════════════
print("== §5 the declared cap and the spool over the SHIPPED family ==")
# ════════════════════════════════════════════════════════════════════════════

check("§5 the cap is a key of its OWN with a declared default (never `ui_viewer_max_bytes`)",
      AV.ARCHIVE_MAX_BYTES_CONFIG == "ui_archive_max_bytes"
      and AV.ARCHIVE_MAX_BYTES == 256 * 1024 * 1024
      and AV.resolve_archive_max_bytes({}) == AV.ARCHIVE_MAX_BYTES
      and AV.resolve_archive_max_bytes({"ui_viewer_max_bytes": 4096}) == AV.ARCHIVE_MAX_BYTES)
check("§5 ...read as a POSITIVE integer and nothing else",
      AV.resolve_archive_max_bytes({AV.ARCHIVE_MAX_BYTES_CONFIG: 4096}) == 4096
      and AV.resolve_archive_max_bytes({AV.ARCHIVE_MAX_BYTES_CONFIG: "8192"}) == 8192
      and AV.resolve_archive_max_bytes({AV.ARCHIVE_MAX_BYTES_CONFIG: 0}) == AV.ARCHIVE_MAX_BYTES
      and AV.resolve_archive_max_bytes({AV.ARCHIVE_MAX_BYTES_CONFIG: -1}) == AV.ARCHIVE_MAX_BYTES
      and AV.resolve_archive_max_bytes({AV.ARCHIVE_MAX_BYTES_CONFIG: True}) == AV.ARCHIVE_MAX_BYTES
      and AV.resolve_archive_max_bytes({AV.ARCHIVE_MAX_BYTES_CONFIG: "big"}) == AV.ARCHIVE_MAX_BYTES)
check("§5 the size gate is inclusive and refuses a foreign value",
      AV.size_allowed(0) and AV.size_allowed(AV.ARCHIVE_MAX_BYTES)
      and not AV.size_allowed(AV.ARCHIVE_MAX_BYTES + 1)
      and AV.size_allowed(1024, 1024) and not AV.size_allowed(1024, 1023)
      and not AV.size_allowed("big") and not AV.size_allowed(-1))

_spool = AV.spool_archive("sample.car")
check("§5 the spool is claimed through the SHIPPED family (its prefix, its tight mode)",
      bool(_spool) and os.path.isfile(_spool)
      and os.path.basename(_spool).startswith(SEND.SPOOL_PREFIX)
      and "sample.car" in os.path.basename(_spool)
      and os.stat(_spool).st_size == 0, _spool)
check("§5 ...and the download leg gets the three arguments of the family's own declaration",
      AV.spool_download_args(_spool) == (os.path.dirname(_spool), os.path.basename(_spool),
                                         SEND.SPOOL_FILE_MODE))
with open(_spool, "wb") as fh:
    fh.write(b"payload")
with open(_spool + SW.PART_SUFFIX, "wb") as fh:
    fh.write(b"twin")
check("§5 `drop_archive()` takes the spool AND its provisional twin",
      AV.drop_archive(_spool) == 2 and not os.path.exists(_spool)
      and not os.path.exists(_spool + SW.PART_SUFFIX))
check("§5 a spool that is already gone is not an error (the teardown is idempotent)",
      AV.drop_archive(_spool) == 0 and AV.drop_archive("") == 0)
_aged = AV.spool_archive("aged.car")
os.utime(_aged, (0, 0))
check("§5 the startup sweep takes an ARCHIVE spool past the age rule (ONE family, ONE sweep)",
      os.path.exists(_aged) and SEND.sweep_spools() >= 1 and not os.path.exists(_aged))

# ════════════════════════════════════════════════════════════════════════════
print("== §6 the pane: the ONE row, the spool leg and the panel ==")
# ════════════════════════════════════════════════════════════════════════════

fs = FakeSftpFS()
fs.add_dir("/srv")
fs.add_file("/data.car", ZIP_DATA, mtime=1_700_000_000)
fs.add_file("/notes.txt", b"just text\n", mtime=1_700_000_000)
fs.add_file("/plain.zip", b"not an archive at all\n", mtime=1_700_000_000)
with open(ENCRYPTED_PATH, "rb") as _fh:
    fs.add_file("/secret.zip", _fh.read(), mtime=1_700_000_000)
tab, worker, log = make_remote_tab(fs)
pane_a, pane_b = tab.panes[0], tab.panes[1]
check("§6 the two panes list the fake server (the fixture is real)",
      wait_row(pane_a, "data.car") and wait_row(pane_b, "data.car"), str(rows(pane_a)))

_zip_item = item_named(pane_a, "data.car")
_zip_menu = pane_a._build_context_menu(_zip_item)
_act_open = action(_zip_menu, "sftp.archive.open")
check("§6 the row menu carries `Open archive`, live on a declared archive",
      _act_open is not None and _act_open.isEnabled() is True
      and action(_zip_menu, "sftp.op.copy_path").isEnabled() is True)
check("§6 ...dead on a file that is not an archive, on a folder and on an empty space",
      action(pane_a._build_context_menu(item_named(pane_a, "notes.txt")),
             "sftp.archive.open").isEnabled() is False
      and action(pane_a._build_context_menu(item_named(pane_a, "srv")),
                 "sftp.archive.open").isEnabled() is False
      and action(pane_a._build_context_menu(None),
                 "sftp.archive.open").isEnabled() is False)
check("§6 ...and OFFERED on a suffix it cannot read (the row asks the suffix, the parse the truth)",
      action(pane_a._build_context_menu(item_named(pane_a, "plain.zip")),
             "sftp.archive.open").isEnabled() is True)

check("§6 the door opens the panel through the spool leg of the SHIPPED queue",
      open_archive(pane_a, _zip_item))
_spool_path = pane_a.archive_state["spool"]
check("§6 ...the listing is the parse of the file the download really published",
      pane_a.archive_state["local"] == _spool_path and bool(_spool_path)
      and os.path.isfile(_spool_path)
      and [name for name, _size in archive_rows(pane_a)]
      == ["etc/app.conf", "README.txt", "bin/tool", "nested.jar", "logo.png"]
      and len(log.of_kind("done")) >= 1,
      str(archive_rows(pane_a)))
check("§6 ...the header names the archive and counts its rows (`sftp.archive.header`)",
      pane_a.archive_label.text()
      == i18n.t("sftp.archive.header", name="data.car", count=5)
      and pane_a.archive_label.toolTip() == "/data.car",
      pane_a.archive_label.text())
check("§6 ...and the size column is the shipped formatter, never a raw byte count",
      dict(archive_rows(pane_a))["README.txt"] == STAB.format_size(14))

check("§6 the panel takes the OTHER pane's slot (the mc/far move, ONE widget)",
      pane_a.archive_panel.parent() is pane_b.splitter
      and pane_b._viewer_borrowed is True and pane_b.tree.isHidden()
      and pane_a.viewer.parent() is pane_a.splitter,
      str(pane_a.archive_panel.parent()))
check("§6 ...and the listing that opened it keeps its keyboard and its rows",
      pane_a.tree.isHidden() is False and pane_a.tree.topLevelItemCount() > 0)

pane_a._preview_member(archive_member_item(pane_a, "README.txt"))
app.processEvents()
check("§6 a member's preview lands in the pane that OPENED the archive (the other one carries it)",
      pane_a.viewer_text.toPlainText() == "hello archive\n"
      and pane_a.viewer_text.isHidden() is False
      and pane_a.viewer.parent() is pane_a.splitter
      and pane_a.archive_panel.parent() is pane_b.splitter)
check("§6 ...with the shipped header: the member's name and its real size",
      pane_a.viewer_label.text() == i18n.t("sftp.viewer.header", path="README.txt",
                                           size=STAB.format_size(14)),
      pane_a.viewer_label.text())
_pane_cap = pane_a.viewer_cap()
pane_a._viewer_cap = 5   # the pane's resolved ceiling (the setter FLOORS at 1 MiB)
check("§6 a TRUNCATED member says how much of how many it shows (the shipped notice, the real total)",
      pane_a.viewer_cap() == 5 and pane_a._preview_member_by_name("README.txt")
      and pane_a.viewer_text.toPlainText() == "hello"
      and i18n.t("sftp.viewer.truncated", shown=STAB.format_size(5),
                 total=STAB.format_size(14)) in pane_a.viewer_label.text(),
      pane_a.viewer_label.text())
pane_a._viewer_cap = _pane_cap
check("§6 a binary member, a nested archive and a name the archive does not hold are refused",
      pane_a._preview_member_by_name("logo.png") is False
      and pane_a._preview_member_by_name("nested.jar") is False
      and pane_a._preview_member_by_name("etc/nothing.txt") is False)

check("§6 the ENCODING choice re-reads the MEMBER, never a path of the server",
      pane_a.set_viewer_encoding("cp1251", persist=False) == "cp1251"
      and pane_a.viewer_text.toPlainText() == "hello archive\n"
      and log.of_kind("read") == [],
      str([e[:3] for e in log.of_kind("read")]))
pane_a.set_viewer_encoding("auto", persist=False)

check("§6 `Esc` closes the WHOLE session — the panel goes home, the listing comes back, the spool goes",
      tab.close_preview() is True
      and pane_a.archive_open is False and pane_a.archive_state is None
      and pane_a.archive_panel.isHidden() and pane_a.viewer.isHidden()
      and pane_b._viewer_borrowed is False and pane_b.tree.isHidden() is False
      and not os.path.exists(_spool_path))

check("§6 a second archive opens in the same pane (the ONE-preview rule is about the OWNER)",
      open_archive(pane_a, item_named(pane_a, "data.car")))
_second_spool = pane_a.archive_state["spool"]
_seen = []
pane_b.message.connect(_seen.append)
pane_b._op_view_archive(item_named(pane_b, "data.car"))
app.processEvents()
check("§6 ...while the OTHER pane is refused with the SHIPPED sentence, spooling nothing",
      pane_b.archive_open is False and pane_a.archive_open is True
      and pane_b.archive_state is None and i18n.t("sftp.cmd.preview_busy") in _seen, str(_seen))
tab.close_preview()
check("§6 a closed view drops its spool", not os.path.exists(_second_spool))

_seen2 = []
pane_a.message.connect(_seen2.append)
open_archive(pane_a, item_named(pane_a, "plain.zip"), ms=3000)
check("§6 a file whose CONTENT disagrees with its suffix answers ONE sentence and dresses no pane",
      pane_a.archive_open is False and bool(_seen2)
      and i18n.t("sftp.op.error", error=AV.ARCHIVE_ERROR_UNREADABLE) in _seen2, str(_seen2))

check("§6 an encrypted archive LISTS in the panel and says so in its header",
      open_archive(pane_a, item_named(pane_a, "secret.zip"))
      and [name for name, _s in archive_rows(pane_a)] == ["secret.txt"]
      and i18n.t("sftp.archive.encrypted") in pane_a.archive_label.text(),
      pane_a.archive_label.text())
_seen3 = []
pane_a.message.connect(_seen3.append)
pane_a._preview_member_by_name("secret.txt")
check("§6 ...and its member is REFUSED with the encrypted sentence — no password is ever asked",
      i18n.t("sftp.archive.encrypted") in _seen3, str(_seen3))
tab.close_preview()

write_cfg({AV.ARCHIVE_MAX_BYTES_CONFIG: 16})
_seen4 = []
pane_a.message.connect(_seen4.append)
pane_a._op_view_archive(item_named(pane_a, "data.car"))
app.processEvents()
check("§6 an archive over the declared cap is refused BEFORE a byte is copied",
      pane_a.archive_open is False
      and i18n.t("sftp.archive.cap", size=STAB.format_size(len(ZIP_DATA)),
                 limit=STAB.format_size(16)) in _seen4
      and read_cfg({}).get(AV.ARCHIVE_MAX_BYTES_CONFIG) == 16, str(_seen4))
clear_cfg()

# ════════════════════════════════════════════════════════════════════════════
print("== §7 the local source, the abandoned leg and the transport change ==")
# ════════════════════════════════════════════════════════════════════════════

if os.path.isdir(WORK_TREE):
    shutil.rmtree(WORK_TREE, ignore_errors=True)
os.makedirs(WORK_TREE)
LOCAL_ZIP = os.path.join(WORK_TREE, "local.zip")
build_zip(LOCAL_ZIP, [("inside/one.txt", b"one\n"), ("two.txt", b"two\n")])
check("§7 the second pane may read the OS disk (the LOCAL_PANE.md rule)",
      tab.set_pane_source(pane_b, SOURCE_LOCAL) is True and pane_b.source == SOURCE_LOCAL)
pane_b._relist(WORK_TREE)
check("§7 ...and lists the real file", wait_row(pane_b, "local.zip"), str(rows(pane_b)))
check("§7 a LOCAL archive is read WHERE IT LIES — the OS disk is already local, nothing is copied",
      open_archive(pane_b, item_named(pane_b, "local.zip"))
      and pane_b.archive_state["spool"] == ""
      and pane_b.archive_state["local"] == LOCAL_ZIP
      and [name for name, _s in archive_rows(pane_b)] == ["inside/one.txt", "two.txt"],
      str(pane_b.archive_state))
check("§7 ...and the panel moved into the FIRST pane (the same ONE move)",
      pane_b.archive_panel.parent() is pane_a.splitter and pane_a._viewer_borrowed is True)
tab.close_preview()

_orphan = AV.spool_archive("abandoned.car")
with open(_orphan, "wb") as fh:
    fh.write(b"stale bytes")
pane_a._archive_tasks[987654] = ("/data.car", _orphan, "zip")
pane_a._archive_dropped.add(987654)
check("§7 a spool leg whose view was CLOSED while it was in flight drops the copy it published",
      pane_a._archive_answer("done", 987654, "") is True
      and not os.path.exists(_orphan) and pane_a.archive_open is False
      and 987654 not in pane_a._archive_tasks and 987654 not in pane_a._archive_dropped)
check("§7 a leg of NO this pane is left to the shipped handlers (one answer, one owner)",
      pane_a._archive_answer("done", 424242, "") is False
      and pane_a._archive_answer("error", 424242, "boom") is False)

check("§7 the archive opens again for the transport check",
      open_archive(pane_a, item_named(pane_a, "data.car")))
_pending_spool = pane_a.archive_state["spool"]
tab.set_worker(None)
check("§7 a provider change closes the archive with the transport — no temp copy survives it",
      pane_a.archive_open is False and pane_a._archive_tasks == {}
      and not os.path.exists(_pending_spool) and pane_b.source == SOURCE_LOCAL)

# ════════════════════════════════════════════════════════════════════════════
print("== §8 the family, the language files and the release ==")
# ════════════════════════════════════════════════════════════════════════════

check("§8 the archive cluster lives in the SHIPPED pane family (no second truth, no second writer)",
      pane_func_owner("_op_view_archive", ROOT) == "modules/sftp_pane_viewer.py"
      and pane_func_owner("_archive_answer", ROOT) == "modules/sftp_pane_viewer.py"
      and pane_func_owner("_build_context_menu", ROOT) == "modules/sftp_pane_dnd.py"
      and not hasattr(STAB.SftpTab, "_op_view_archive")
      and hasattr(STAB._SftpPane, "archive_key"))
check("§8 the pure half carries no Qt and no provider (the module is importable alone)",
      all(needle not in open(os.path.join(ROOT, "modules", "archive_view.py"),
                             encoding="utf-8").read()
          for needle in ("PySide6", "paramiko")))
check("§8 the dnd module reads the declared family through ONE table (the row's own question)",
      getattr(PDND, "archive", None) is AV
      and "archive_kind" in open(os.path.join(ROOT, "modules", "sftp_pane_dnd.py"),
                                 encoding="utf-8").read())

for _key in ("sftp.archive.open", "sftp.archive.header", "sftp.archive.cap",
             "sftp.archive.encrypted"):
    check(f"§8 {_key} is present and non-empty in every language",
          all(str(data.get(_key) or "").strip() for data in LANGS.values()),
          str({code: data.get(_key) for code, data in LANGS.items()}))
check_i18n_parity(LANGS)
check_i18n_format(LANGS)

check_release_state(ROOT)
check("§8 the pin names this release's line", releases_at_least(EXPECTED_APP_VERSION, "1.13"),
      EXPECTED_APP_VERSION)
check("§8 the archive surface's NINE keys are part of the pin (the READ half's four, the WRITE "
      "half's three, the slot's two)",
      EXPECTED_I18N_KEYS == 1118 + 9 + 8 + 9 + 18 + 4, str(EXPECTED_I18N_KEYS))
check("§8 the project schema did NOT move (the archive view is not project state)",
      'VERSION_FORMAT = "0.9"' in open(os.path.join(ROOT, "version.py"), encoding="utf-8").read())

tab.release()
worker.shutdown(wait_ms=2500)

finish()
