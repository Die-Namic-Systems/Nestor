"""The recording harness has to actually capture the demo, not just claim to.

``demo/record_demo.py`` is the "tooling built to answer a question" that
IDEAS §4.3 asked for — a script, so per docs/agent-guide.md it gets a test
even though nothing else in the codebase consumes it yet.

Skips outright if ``script(1)`` is not on PATH (the harness's one external
dependency, not a new one — util-linux, present on the Linux boxes this
project's CI runs on).
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
HARNESS = REPO / "demo" / "record_demo.py"

pytestmark = pytest.mark.skipif(
    shutil.which("script") is None,
    reason="script(1) [util-linux] is not on PATH — the harness needs it to allocate a pty",
)


def run(*args):
    return subprocess.run([sys.executable, str(HARNESS), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=180,
                          check=False)


def test_it_captures_the_fast_run_and_every_beat_is_in_the_transcript(tmp_path):
    out = tmp_path / "out"
    done = run("--fast", "--out", str(out))
    assert done.returncode == 0, done.stdout + done.stderr

    cast_path = out / "sixty_seconds.cast"
    txt_path = out / "sixty_seconds.txt"
    assert cast_path.exists() and txt_path.exists()

    lines = cast_path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    assert header["version"] == 2
    assert header["width"] > 0 and header["height"] > 0
    for line in lines[1:]:
        event = json.loads(line)
        assert len(event) == 3
        assert event[1] == "o"
        assert isinstance(event[0], (int, float))

    transcript = txt_path.read_text(encoding="utf-8")
    for beat in ("Ask it something nobody has verified",
                 "A human verifies it. Once.",
                 "Ask again",
                 "A rewrite that means the same thing",
                 "the part a demo usually leaves out",
                 "forges a seal",
                 "the chain holds",
                 "edit the trail",
                 "Sixty seconds."):
        assert beat in transcript, f"missing beat in captured transcript: {beat}"
    # the pty renders color; a plain-text transcript should not carry escapes
    assert "\x1b[" not in transcript


def test_a_failing_beat_propagates_a_nonzero_exit(tmp_path, monkeypatch):
    """The recording step must not launder a broken demo into a clean artifact."""
    broken = tmp_path / "broken_demo.py"
    broken.write_text(
        "import sys\n"
        "print('this is not a real beat')\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(REPO / "demo"))
    import record_demo
    try:
        monkeypatch.setattr(record_demo, "DEMO_SCRIPT", broken)
        out = tmp_path / "out"
        result = record_demo.capture(out, fast=True)
        assert result.returncode == 3
        # the artifacts are still written — a failing run is still captured, not hidden
        assert (out / "sixty_seconds.cast").exists()
        assert "this is not a real beat" in (out / "sixty_seconds.txt").read_text(encoding="utf-8")
    finally:
        sys.path.remove(str(REPO / "demo"))
        sys.modules.pop("record_demo", None)


def test_it_does_not_write_the_default_store_or_touch_the_repo(tmp_path):
    """Same guarantee as the demo it wraps: no writes outside the directory it's given."""
    before = _snapshot(REPO / "data")
    out = tmp_path / "out"
    assert run("--fast", "--out", str(out)).returncode == 0
    assert _snapshot(REPO / "data") == before, "the harness wrote into the working tree"


def _snapshot(directory):
    if not directory.exists():
        return None
    return {p.relative_to(directory): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(directory.rglob("*")) if p.is_file()}
