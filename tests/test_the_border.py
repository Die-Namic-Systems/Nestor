"""`demo/the_border.py` has to keep being true about somebody else's code.

Most fixtures here assert against this package. This one asserts against
**jeles** as well — that a nugget crosses in as a draft, that a seal goes back
as an assertion, that landing it without an id duplicates and with one is
refused. Those are claims about a repository this one does not control, which
makes them the claims most likely to quietly stop being true.

So the failure mode this file exists for is not "nestor broke". It is "jeles
moved and nobody noticed" — and the fixture says so in those words rather than
reporting a generic red.

Skipped when jeles is absent rather than mocked. CI has no clone of it, the
package is deliberately not a dependency, and a fixture that mocked the system
under test would prove the mock works.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO = REPO / "demo" / "the_border.py"

jeles = pytest.importorskip("jeles.corpus",
                            reason="jeles not installed in this environment")


#: The fixture colours its output, so a phrase the eye reads as one string can
#: have an escape sequence through the middle of it. Asserting on raw stdout
#: made a true claim look false; stripping is the fix, not a looser assertion.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run(*args):
    return subprocess.run([sys.executable, str(DEMO), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=180)


def plain(text: str) -> str:
    return _ANSI.sub("", text)


def test_every_claim_still_holds():
    done = run()
    assert done.returncode == 0, done.stdout + done.stderr
    assert "DEMO CLAIM FAILED" not in plain(done.stdout)
    assert "CHANGED ON THEIR SIDE" not in plain(done.stdout), (
        "jeles no longer behaves the way this fixture and "
        "recipes/jeles_bridge.py describe — re-read it and update both, in the "
        "same change:\n" + done.stdout)


def test_it_walks_the_beats_it_promises():
    out = plain(run().stdout)
    for beat in ("jeles holds it, and serves it",
                 "It crosses, and arrives as a draft",
                 "A human reads it and seals it here",
                 "It goes back, and the evidence does not",
                 "Landing it, route A",
                 "Landing it, route B",
                 "Nobody is wrong"):
        assert beat in out, f"missing beat: {beat}"


def test_it_shows_the_loss_in_both_directions():
    """The two numbers the whole argument rests on, as printed."""
    out = plain(run().stdout)
    assert "0 sealed, 1 demoted to draft" in out, "the inbound demotion"
    assert "'asserted'" in out, "the outbound degradation"
    assert "dropped at the border" in out and "seal_sig" in out
    assert "kind_downgrade_refused" in out


def test_it_leaves_nothing_behind_unless_told_to(tmp_path):
    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    assert (kept / "nestor.db").exists() and (kept / "ledger.jsonl").exists()
    assert (kept / "willow").is_dir(), "the jeles corpus is temporary too"

    before = set(pathlib.Path("/tmp").glob("nestor-border-*"))
    assert run().returncode == 0
    assert not (set(pathlib.Path("/tmp").glob("nestor-border-*")) - before), \
        "the default run must not leave a store behind"


def test_it_does_not_touch_an_ambient_corpus(tmp_path, monkeypatch):
    """It sets WILLOW_STORE_ROOT itself, so a real corpus on this machine is safe.

    The direction that matters: a fixture writing into somebody's actual jeles
    store would be putting invented rows in a corpus people ask questions of.
    """
    poisoned = tmp_path / "do-not-touch"
    poisoned.mkdir()
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(poisoned))
    done = subprocess.run([sys.executable, str(DEMO)], capture_output=True,
                          text=True, cwd=REPO, timeout=180,
                          env={**dict(__import__("os").environ),
                               "WILLOW_STORE_ROOT": str(poisoned)})
    assert done.returncode == 0, done.stdout + done.stderr
    assert not list(poisoned.rglob("*.db")), \
        "the fixture must not write into the corpus it was pointed at"
