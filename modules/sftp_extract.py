# -*- coding: utf-8 -*-
"""The container's ARCHIVE EXTRACTOR (`ARCHIVES.md` §6) — the engine, the stage and the delivery.

`SftpExtractMixin` is the container's half of the WRITE half of the archive surface: it owns the ONE
`LocalFsWorker` an extraction runs on (`extract_provider()`), the record of every extraction in flight,
and the delivery of the staged tree into the destination pane through the shipped batch machine. The
destination is always the pane whose LISTING is on screen (`preview_source()`), which is what makes
"extract here" unreachable; an encrypted archive is refused before a byte is written. The whole
pipeline lives here rather than in `modules/sftp_tab.py` because the facade carries a size budget.

Contract — `ARCHIVES.md` §6; mechanism — `DOCUMENTATION.md` §77.
"""
import sys

try:
    from i18n import t as _t
except Exception:  # noqa: BLE001 — import outside the project tree (flat run)
    def _t(key, **kwargs):  # type: ignore
        return key

try:  # v1.13.1: the extract engine, the READ half's copy rule and the LOCAL provider it runs on
    from . import archive_extract
    from . import archive_view
    from . import local_fs_worker as local_fs
    from .sftp_worker import MAX_TREE_ENTRIES, TREE_ERROR_TOO_BIG, parse_task_payload
except ImportError:  # flat launch from the project root
    import archive_extract  # type: ignore
    import archive_view  # type: ignore
    import local_fs_worker as local_fs  # type: ignore
    from sftp_worker import (MAX_TREE_ENTRIES, TREE_ERROR_TOO_BIG,  # type: ignore
                             parse_task_payload)


def _facade(name, default=None):
    """A SHIPPED name of `modules/sftp_tab.py` at call time — the facade seam of the pane family.

    This module is imported BY the facade, so it can never import the facade back (`AGENTS.md` §4.1):
    the module object is read from `sys.modules` instead, which is the same seam
    `modules/sftp_pane_dnd.py` uses for the two names it needs.
    """
    for mod_name in ("modules.sftp_tab", "sftp_tab"):
        mod = sys.modules.get(mod_name)
        if mod is not None:
            return getattr(mod, name, default)
    return default


class SftpExtractMixin:
    """The archive extraction of ONE container (mixed into `SftpTab`)."""

    def extract_provider(self):
        """The container's extract engine — ONE `LocalFsWorker`, created on the first `Extract`.

        The extraction reads a LOCAL copy and writes a LOCAL tree, so it runs on a local provider of
        its own rather than on a pane's: the destination is the pane that OWNS the archive, and a
        task's answers belong to the pane BOUND to the provider that queued it (`LOCAL_PANE.md` §5).
        The thread starts with the first extraction and stops with `release()`.
        """
        provider = getattr(self, "_extract_provider", None)
        if provider is None:
            provider = local_fs.LocalFsWorker(parent=self)
            provider.task_error.connect(self._on_extract_error)
            provider.task_cancelled.connect(self._on_extract_cancelled)
            provider.extract_ready.connect(self._on_extract_ready)
            provider.task_started.connect(self._on_extract_started)
            provider.start()
            self._extract_provider = provider
        return provider

    def begin_extract(self, pane) -> bool:
        """Unpack the archive `pane` shows into the destination pane's directory; False — nothing ran.

        The destination is the pane whose LISTING is on the screen — the pane that opened the archive
        when the panel moved into its neighbour, and the pane itself when there is no second one —
        which is what makes "extract here" unreachable by construction. The archive is written into a
        STAGE (a temp folder of its own) and the stage is handed to that pane's provider by
        `ship_staged_tree()`, so the conflict question, the progress, the cancel and the report are
        the SHIPPED ones. An encrypted archive is refused BEFORE a byte is written.
        """
        state = pane.archive_state if pane is not None else None
        if not state or not state.get("local"):
            return False
        if state.get("encrypted"):
            pane.message.emit(_t("sftp.archive.encrypted"))
            return False
        dest_pane = self.preview_source() or pane
        dest_dir = str(getattr(dest_pane, "current_dir", "") or "")
        if not dest_dir:
            pane.message.emit(_t("sftp.waiting_connection"))
            return False
        # The directory and the names the conflict question is asked over are ONE moment (the
        # `_remote_batch()` rule): an extraction outlives the listing it was started from, so the
        # names read at the ANSWER would belong to whatever directory the pane shows by then.
        known = dest_pane._names_in_current_dir()
        stage = archive_extract.create_stage()
        if not stage:
            pane.message.emit(_t("sftp.op.error", error="stage"))
            return False
        name = archive_extract.extract_folder(state.get("path") or state["local"])
        task_id = self.extract_provider().queue_extract(
            state["local"], stage, limits=archive_extract.extract_limits())
        if task_id is None:
            archive_extract.drop_stage(stage)
            pane.message.emit(_t("sftp.op.error", error="queue"))
            return False
        self._extracts[int(task_id)] = {"pane": pane, "dest_pane": dest_pane, "dest_dir": dest_dir,
                                        "known": known, "name": name, "stage": stage,
                                        "local": str(state["local"]),
                                        "spool": str(state.get("spool") or ""), "closed": False}
        pane.message.emit(_t("sftp.viewer.reading",
                             name=dest_pane.paths.basename(state.get("path") or state["local"])))
        return True

    def take_archive_copy(self, local: str) -> bool:
        """Hand the LOCAL copy of a running extraction to THIS container; True — it owns it now.

        EVERY extraction of that copy is marked: two extractions can read ONE local file (a second
        `Extract` before the first answers), and a view that closes then owes the copy to both of
        them — marking only the first would let the first answer delete the file the second is still
        reading. True means the container keeps the copy and drops it with the LAST answer (a
        plaintext duplicate of a server file outlives no more than the operations it was made for).
        """
        if not local:
            return False
        marked = [record for record in self._extracts.values() if record.get("local") == local]
        for record in marked:
            record["closed"] = True
        return bool(marked)

    def extract_active(self) -> bool:
        """Is an extraction still running (the topical seam of the container's own engine)?"""
        return bool(self._extracts)

    def _on_extract_started(self, _task_id: int, _kind: str, _label: str):
        return   # the shipped `task_started` shape: nothing of the container's depends on it

    def _on_extract_ready(self, task_id: int, tree: str, written: int, skipped: list):
        """The extraction wrote its tree: hand it to the destination — and SAY NOTHING.

        `tree` IS the stage (`modules/local_fs_worker.py` writes the members straight into it) and the
        delivery pane owns it from the hand-over: the success and the skip sentences belong to the
        ANSWER of that task (`_report_staged()`), the only moment they are true — a `Skip`, a
        cancelled `Rename`, an elevated or a provider refusal report themselves and nothing landed.
        A destination pane that is GONE (the two-pane mode went off while the archive was unpacking)
        costs the tree and no traceback: its widgets cannot be asked a conflict question any more.
        """
        record = self._extracts.pop(int(task_id), None)
        if record is None:
            archive_extract.drop_stage(tree)
            return
        dest_pane = record.get("dest_pane")
        if dest_pane is None or dest_pane not in self._panes:
            archive_extract.drop_stage(tree)
            self._drop_extract_copy(record)
            return
        try:
            delivered = dest_pane.ship_staged_tree(tree, record.get("dest_dir") or "",
                                                   record.get("name") or "",
                                                   record.get("known") or set(),
                                                   written=int(written),
                                                   skipped=list(skipped))
        except RuntimeError:
            delivered = ""   # the pane died between the liveness check and the delivery
        if not delivered:
            archive_extract.drop_stage(tree)
        self._drop_extract_copy(record)

    def _on_extract_error(self, task_id: int, _kind: str, message: str):
        """A refused extraction: ONE sentence, and the stage it may have touched is dropped."""
        record = self._extracts.pop(int(task_id), None)
        if record is None:
            return
        archive_extract.drop_stage(record.get("stage") or "")
        self._say(record, self._extract_error_text(message))
        self._drop_extract_copy(record)

    def _on_extract_cancelled(self, task_id: int, _kind: str):
        record = self._extracts.pop(int(task_id), None)
        if record is None:
            return
        archive_extract.drop_stage(record.get("stage") or "")
        self._say(record, _t("sftp.transfer_cancelled"))
        self._drop_extract_copy(record)

    def _say(self, record: dict, text: str):
        """Emit ONE sentence on the pane that opened the archive — if it is still there. Never raises."""
        pane = record.get("pane")
        if pane is None or pane not in self._panes:
            return
        try:
            pane.message.emit(text)
        except RuntimeError:
            pass   # the C++ object went away with the pane

    @staticmethod
    def _extract_error_text(message: str) -> str:
        """The sentence of a refused extraction — the shipped code tables, then the local one.

        A cap the plan hit is one of two codes: the bomb has its OWN sentence (what the archive would
        expand to and the ceiling it crossed), and the walk bound reuses the shipped tree sentence;
        the reader's own two refusals keep the §4 sentences of the READ half.
        """
        data = parse_task_payload(message) or {}
        code = str(data.get("code") or "")
        if code == archive_extract.EXTRACT_ERROR_BOMB:
            format_size = _facade("format_size", str)
            return _t("sftp.archive.extract_bomb", size=format_size(int(data.get("total") or 0)),
                      count=int(data.get("count") or 0),
                      limit=format_size(int(data.get("limit") or 0)))
        if code == TREE_ERROR_TOO_BIG:
            return _t("sftp.cmd.tree_too_big",
                      limit=int(data.get("limit") or MAX_TREE_ENTRIES))
        if code == archive_view.ARCHIVE_ERROR_ENCRYPTED:
            return _t("sftp.archive.encrypted")
        return _facade("local_error_text", lambda text: _t("sftp.op.error", error=text))(message)

    def _drop_extract_copy(self, record: dict):
        """Drop the spool of an extraction whose view was CLOSED — by its LAST reader. Never raises.

        The record has already left `_extracts` when this runs, so a spool another extraction still
        names is kept: a plaintext copy goes with the last operation that reads it, never with the
        first one that ends.
        """
        spool = str(record.get("spool") or "")
        if not record.get("closed") or not spool:
            return
        if any(str(other.get("spool") or "") == spool for other in self._extracts.values()):
            return
        archive_view.drop_archive(spool)

    def _release_extracts(self):
        """Stop the extract engine and drop everything it still holds — the container's teardown.

        A stage belongs to an extraction that will never answer (its provider is going away), and a
        spool the container took over from a closed preview goes with it: nothing of either survives
        the container (`AGENTS.md` §4.8). Idempotent, never raises.
        """
        for record in list(self._extracts.values()):
            archive_extract.drop_stage(record.get("stage") or "")
            if record.get("closed"):
                archive_view.drop_archive(str(record.get("spool") or ""))
        self._extracts.clear()
        provider = getattr(self, "_extract_provider", None)
        self._extract_provider = None
        if provider is None:
            return
        try:
            provider.shutdown(local_fs.LOCAL_SHUTDOWN_WAIT_MS)
        except Exception:  # noqa: BLE001 — teardown robustness
            pass
        try:
            if provider.isRunning():
                local_fs.register_orphan_local_provider(provider)
        except RuntimeError:
            pass   # the C++ object is already gone

    @property
    def _extracts(self) -> dict:
        """The record of every extraction in flight, keyed by its task id (created with the first)."""
        return self.__dict__.setdefault("_extract_records", {})
