#!/usr/bin/env python3
"""Capture ``demo/sixty_seconds.py`` as a reproducible recording (IDEAS §4.3).

    python demo/record_demo.py                  # paced capture -> demo/recordings/sixty_seconds.{cast,txt}
    python demo/record_demo.py --fast            # --fast pacing, for a quick sanity capture
    python demo/record_demo.py --out DIR         # write the two artifacts elsewhere

WHAT THIS PRODUCES
-------------------
Two files, from one run of the demo:

* ``sixty_seconds.cast`` — an asciinema v2 cast file: a JSON header line
  followed by one ``[time, "o", text]`` JSON line per chunk of terminal
  output, with real inter-beat timing. It is genuinely replayable —
  ``asciinema play sixty_seconds.cast``, or any asciinema-compatible web
  player — with the original color and pacing, and it was built with **no
  new dependency**: the cast format is a documented, static JSON-lines
  spec (https://docs.asciinema.org/manual/asciicast/v2/), not a library.
* ``sixty_seconds.txt`` — the same run, ANSI escapes stripped and CRLF
  normalized to LF, for reading, grepping or diffing without a terminal
  emulator.

HOW IT WORKS
------------
This container has no ``asciinema`` binary and ``asciinema rec`` needs a
TTY it does not have either way. What it does have is ``script(1)``
(util-linux, present on every Linux box this project runs CI on), which
allocates a **pty for the child process** regardless of whether this
process itself has a controlling terminal — so the demo's ANSI color and
its own ``time.sleep`` pacing both come through unmodified, headlessly.
``script --log-out`` captures the raw pty bytes; ``script --log-timing``
captures ``(delay, byte-count)`` pairs for them. This module reassembles
those two files into the cast format above. That reassembly, not a
terminal capture library, is the only code here.

THE HUMAN STEP THIS DOES NOT DO
--------------------------------
Turning the ``.cast`` into a GIF needs a renderer this repo does not
carry and should not start carrying (``agg``, ``asciicast2gif`` — Rust or
Node tooling; core stays dependency-light, see CLAUDE.md). On a machine
that has one:

    agg demo/recordings/sixty_seconds.cast demo/recordings/sixty_seconds.gif

That is the one command. It is not run here, and nothing in this module
claims it was.

LIMITS (read before trusting the artifact)
-------------------------------------------
* **Not byte-identical between runs.** The demo prints its own scratch
  directory path (``tempfile.mkdtemp``), which is different every run by
  design (see ``sixty_seconds.py``) — this harness does not paper over
  that, and a diff between two captures will show it in that one line.
* **Fixed 80x24 pty**, not whatever terminal a human eventually watches
  this in — see ``PTY_WIDTH``/``PTY_HEIGHT`` below. A real recording on a
  narrower terminal will wrap lines the cast does not.
* **The cast header's ``env`` is a fixed placeholder**, not read from
  this host's actual shell — so two captures made on different machines
  produce the same header instead of leaking whoever ran the capture.
* **Coarser timing than a native asciinema recording.** ``script``'s
  timing file buckets by write, not by keystroke, so it is accurate for
  this demo (which paces with ``time.sleep`` between prints) but would
  not be for an interactively-typed session.
* **Only runs where ``script(1)`` exists** — Linux with util-linux. It
  raises :class:`RuntimeError` with a plain message rather than a stack
  trace if the binary is missing; there is no fallback renderer.
* **Exit code is the demo's.** If a beat's claim fails, ``sixty_seconds.py``
  exits non-zero and so does this — the recording step does not launder a
  broken demo into a clean-looking artifact.

RECORD, per repo convention (docs/agent-guide.md, "Tooling you built to
answer a question ships with the answer"): used to produce the artifacts
committed under ``demo/recordings/``, one capture, at HEAD as of the commit
that added this file. Re-run it to refresh them after a change to the demo.
"""
from __future__ import annotations

import argparse
import codecs
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO_SCRIPT = REPO / "demo" / "sixty_seconds.py"

PTY_WIDTH = 80
PTY_HEIGHT = 24
# Fixed, not read from the capturing host — see LIMITS above.
CAST_ENV = {"SHELL": "/bin/bash", "TERM": "xterm-256color"}

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _read_timing(timing_path: pathlib.Path) -> list[tuple[float, int]]:
    pairs = []
    for line in timing_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        delay_str, count_str = line.split()
        pairs.append((float(delay_str), int(count_str)))
    return pairs


def _child_bytes(raw: bytes, expected_total: int) -> bytes:
    """The child process's own output, sliced out of ``script``'s log.

    ``script`` writes a one-line banner before and after the child's output
    that is not part of the timing stream (its byte count is not in any
    timing entry) — so instead of parsing the banner's exact wording, which
    varies by util-linux version, this trusts the timing file's own total
    and takes exactly that many bytes starting right after the banner's
    first newline.
    """
    first_nl = raw.index(b"\n")
    start = first_nl + 1
    return raw[start:start + expected_total]


def build_cast(raw: bytes, timing_path: pathlib.Path) -> str:
    """Reassemble a ``script --log-out``/``--log-timing`` pair into asciicast v2."""
    timing = _read_timing(timing_path)
    total = sum(count for _delay, count in timing)
    data = _child_bytes(raw, total)

    header = {"version": 2, "width": PTY_WIDTH, "height": PTY_HEIGHT, "env": CAST_ENV}
    lines = [json.dumps(header)]

    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    offset = 0
    t = 0.0
    for delay, count in timing:
        t += delay
        chunk = data[offset:offset + count]
        offset += count
        text = decoder.decode(chunk)
        if text:
            lines.append(json.dumps([round(t, 6), "o", text]))
    tail = decoder.decode(b"", final=True)
    if tail:
        lines.append(json.dumps([round(t, 6), "o", tail]))
    return "\n".join(lines) + "\n"


def cast_to_plain(cast_text: str) -> str:
    """The same output, ANSI-stripped and CRLF-normalized, for reading without a terminal."""
    out = []
    for line in cast_text.splitlines()[1:]:  # skip the header line
        event = json.loads(line)
        out.append(event[2])
    text = "".join(out).replace("\r\n", "\n").replace("\r", "\n")
    return _ANSI.sub("", text)


def capture(out_dir: pathlib.Path, fast: bool, python_exe: str = sys.executable) -> subprocess.CompletedProcess:
    """Run the demo under ``script(1)`` and write ``sixty_seconds.{cast,txt}`` into ``out_dir``.

    Returns the completed ``script`` invocation (``.returncode`` is the
    demo's own exit code — see LIMITS). Raises ``RuntimeError`` if
    ``script(1)`` is not on PATH.
    """
    if shutil.which("script") is None:
        raise RuntimeError(
            "script(1) is not on PATH — this harness needs util-linux's "
            "script(1) to allocate a pty for the demo. Nothing was captured."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [python_exe, str(DEMO_SCRIPT)]
    if fast:
        cmd.append("--fast")
    inner = " ".join(shlex.quote(c) for c in cmd)

    with tempfile.TemporaryDirectory(prefix="nestor-record-") as tmp:
        raw_path = pathlib.Path(tmp) / "raw.bin"
        timing_path = pathlib.Path(tmp) / "timing"
        result = subprocess.run(
            ["script", "--quiet", "--return",
             "--log-out", str(raw_path), "--log-timing", str(timing_path),
             "--command", inner],
            cwd=REPO, capture_output=True, text=True, timeout=180,
            env={**os.environ, "COLUMNS": str(PTY_WIDTH), "LINES": str(PTY_HEIGHT)},
        )
        raw = raw_path.read_bytes()
        cast_text = build_cast(raw, timing_path)

    plain_text = cast_to_plain(cast_text)
    (out_dir / "sixty_seconds.cast").write_text(cast_text, encoding="utf-8")
    (out_dir / "sixty_seconds.txt").write_text(plain_text, encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fast", action="store_true",
                     help="capture the --fast (no-pause) pacing instead of the recording pacing")
    ap.add_argument("--out", default=str(REPO / "demo" / "recordings"),
                     help="directory to write sixty_seconds.{cast,txt} into")
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out)
    result = capture(out_dir, fast=args.fast)

    if result.returncode != 0:
        print(f"demo exited {result.returncode} — the recording captures a failing run, not a lie:",
              file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return result.returncode

    print(f"wrote {out_dir / 'sixty_seconds.cast'}")
    print(f"wrote {out_dir / 'sixty_seconds.txt'}")
    print("\nThat is as far as this container goes: no GIF renderer here by design")
    print("(see this file's docstring). On a machine with `agg` installed, one command finishes it:")
    print(f"\n    agg {out_dir / 'sixty_seconds.cast'} {out_dir / 'sixty_seconds.gif'}\n")
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
