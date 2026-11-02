# -*- coding: utf-8 -*-
"""The two channels of a run — stdout carries the report, stderr the diagnostics, in BOTH modes.

`prepare_streams()` gives a REDIRECTED pair UTF-8 with no newline translation (a console keeps its own);
`write_json()` sends the envelope as UTF-8 BYTES on every stream. `write_line()` is the ONE text writer —
a codepage that cannot carry a character REPLACES it and a closed pipe is a False, never a traceback — and
`report()` picks the shape of a run's answer. `AGENTS.md` §4.35; contract — `CLI.md` §3.0, §4.
"""
import sys

from . import envelope as ENV

#: The encoding of a REDIRECTED channel — a report is data, and its bytes never move with a locale.
CHANNEL_ENCODING = "utf-8"


def stream(name):
    """The live stream of a name (`stdout` / `stderr`); None when the process has none."""
    return getattr(sys, name, None)


def redirected(stream_):
    """Is this stream a FILE or a PIPE rather than a console? (a stream without `isatty()` is not one)."""
    try:
        return not stream_.isatty()
    except (AttributeError, OSError, ValueError):
        return False


def prepare_streams() -> list:
    """Bring the REDIRECTED channels to the declared bytes (UTF-8, no newline translation).

    A console is left alone: its plain lines need the text layer's newline translation, and only a
    machine reads a redirected report byte for byte. A stream that refuses `reconfigure()` keeps its own
    encoding — the surface still writes, it just cannot promise the bytes. Answers the names it moved.
    """
    moved = []
    for name in ("stdout", "stderr"):
        channel = stream(name)
        reconfigure = getattr(channel, "reconfigure", None)
        if channel is None or not redirected(channel) or not callable(reconfigure):
            continue
        try:
            reconfigure(encoding=CHANNEL_ENCODING, errors="replace", newline="")
            moved.append(name)
        except (OSError, ValueError):
            continue
    return moved


def _emit(stream_, text) -> bool:
    """One write on `stream_` — a codepage that cannot carry a character REPLACES it, a closed pipe is
    a False; never an exception (a report is data, and a broken pipe must not become a traceback)."""
    if stream_ is None:
        return False
    try:
        stream_.write(text)
        return True
    except UnicodeEncodeError:
        encoding = getattr(stream_, "encoding", None) or CHANNEL_ENCODING
        try:
            stream_.write(text.encode(encoding, "replace").decode(encoding, "replace"))
            return True
        except (OSError, ValueError):
            return False
    except (OSError, ValueError):
        return False


def write_bytes(stream_, data) -> bool:
    """Raw BYTES on the stream's own buffer; a stream without one receives the decoded text instead."""
    if stream_ is None:
        return False
    buffer = getattr(stream_, "buffer", None)
    if buffer is not None:
        try:
            buffer.write(data)
            flush = getattr(buffer, "flush", None)
            if callable(flush):
                flush()
            return True
        except (OSError, ValueError):
            return False
    return _emit(stream_, data.decode(CHANNEL_ENCODING, "replace"))


def write_line(stream_, text) -> bool:
    """One line on `stream_` (a newline appended); False when the stream refused or is absent."""
    return _emit(stream_, str(text if text is not None else "") + "\n")


def write_lines(stream_, lines) -> bool:
    """Every line of a report, in order; True when all of them landed."""
    written = True
    for line in lines or ():
        written = write_line(stream_, line) and written
    return written


def write_block(stream_, text) -> bool:
    """A pre-formed BLOCK on `stream_` verbatim (a table already carries its own row endings)."""
    return _emit(stream_, str(text if text is not None else ""))


def write_json(stream_, text) -> bool:
    """The `--json` document as UTF-8 BYTES on EVERY stream (RFC 8259 §8.1): one text + a newline."""
    return write_bytes(stream_, (str(text if text is not None else "") + "\n")
                       .encode(CHANNEL_ENCODING))


def report(envelope, lines, use_json, out=None, err=None) -> bool:
    """Emit ONE answer: the `--json` document on `out`, else the text form on `out` + the error on `err`.

    The envelope carries FACTS (a verb's data, or the failure record) and `lines` is the text form of the
    same run — the dispatcher asks the verb's renderer for it, so the two shapes never disagree. `lines` is
    either a list of lines or ONE pre-formed block (a table, whose rows carry their own endings). A failure
    has no lines and is reported by its `error` record: on stderr in text mode, inside the envelope in
    `--json` mode.
    """
    out = stream("stdout") if out is None else out
    err = stream("stderr") if err is None else err
    if use_json:
        return write_json(out, ENV.dumps(envelope))
    error = envelope.get("error")
    if error is not None:
        hint = error.get("hint")
        message = str(error.get("message", ""))
        return write_line(err, f"{message} ({hint})" if hint else message)
    if isinstance(lines, str):
        return write_block(out, lines)
    return write_lines(out, lines)
