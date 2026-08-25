"""The sixty-second demo has to keep being true.

A demo is a claim about the product, made to people who will not read the
source. This one asserts each of its beats as it goes and exits non-zero if one
does not hold; running it here means a change that quietly breaks the story —
the near miss starting to serve, the forgery getting through, the chain failing
to notice an edit — fails the build rather than the next recording.

Run as a subprocess: the script installs a process-wide store, ledger path and
keyring, and it is meant to be run that way.
"""
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO = REPO / "demo" / "sixty_seconds.py"
DOGFOODING = REPO / "demo" / "the_dogfooding.py"


def run(*args):
    return subprocess.run([sys.executable, str(DEMO), "--fast", *args],
                          capture_output=True, text=True, cwd=REPO, timeout=180,
                          check=False)


def run_dogfooding(*args):
    return subprocess.run([sys.executable, str(DOGFOODING), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=180,
                          check=False)


def _snapshot(directory):
    """Every file under ``directory``, by size and mtime. ``None`` if absent."""
    if not directory.exists():
        return None
    return {p.relative_to(directory): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(directory.rglob("*")) if p.is_file()}


def test_every_beat_still_holds():
    done = run()
    assert done.returncode == 0, done.stdout + done.stderr
    for beat in ("Ask it something nobody has verified",
                 "A human verifies it. Once.",
                 "Ask again",
                 "A rewrite that means the same thing",
                 "the part a demo usually leaves out",
                 "forges a seal",
                 "the chain holds",
                 "edit the trail"):
        assert beat in done.stdout, f"missing beat: {beat}"
    assert "DEMO CLAIM FAILED" not in done.stdout


def test_it_cleans_up_after_itself_unless_told_not_to(tmp_path):
    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    assert (kept / "nestor.db").exists() and (kept / "ledger.jsonl").exists()

    before = set(pathlib.Path("/tmp").glob("nestor-demo-*"))
    assert run().returncode == 0
    assert not (set(pathlib.Path("/tmp").glob("nestor-demo-*")) - before), \
        "the default run must not leave a store behind"


@pytest.fixture(scope="module")
def dogfooding_result():
    """Run the_dogfooding.py once; both dogfooding tests share the result."""
    committed = REPO / "docs" / "dogfood"
    before = _snapshot(committed)
    done = run_dogfooding()
    return done, before, committed


@pytest.mark.slow
def test_the_dogfooding_measures_and_every_claim_holds(dogfooding_result):
    """The measurement of the decision store against itself has to stay true.

    Like the sixty-second demo, it asserts each beat and exits non-zero if one
    fails — so a change that quietly breaks retrieval on Nestor's own decisions
    (the floor cracking, a paraphrase starting to serve the wrong decision, a new
    collision appearing) fails the build here rather than misleading a viewer.
    Run plain, not ``--fast``: this demo does not pace, it measures.
    """
    done = dogfooding_result[0]
    assert done.returncode == 0, done.stdout + done.stderr
    for beat in ("The corpus is real",
                 "In the store that ships, nothing serves",
                 "The floor",
                 "asking in their own words",
                 "authoring-free",
                 "WOULD serve the wrong decision",
                 "not a free win",
                 "How well does Nestor do on its own code"):
        assert beat in done.stdout, f"missing beat: {beat}"
    assert "DEMO CLAIM FAILED" not in done.stdout


@pytest.mark.slow
def test_the_dogfooding_never_touches_the_committed_store(dogfooding_result):
    """It reads docs/dogfood/nestor.db by copying it; the original must not move."""
    done, before, committed = dogfooding_result
    assert done.returncode == 0
    assert _snapshot(committed) == before, "the demo wrote into docs/dogfood/"


def test_it_never_touches_the_repo():
    """It runs from the repo root, so a stray default path would land in data/.

    The assertion cannot be "data/ does not exist". That directory is gitignored
    precisely because it is where a real store lives — every launch command in
    the README points at ``data/nestor.db`` — so anyone who has started the UI
    from this checkout has one, and asserting its absence turns their ordinary
    setup into a test failure. A false alarm dressed as a regression is worse
    than the regression: it teaches people the suite is unreliable.

    So snapshot it and assert the demo left it exactly as it found it, which is
    the thing actually being claimed.
    """
    before = _snapshot(REPO / "data")
    assert run().returncode == 0
    assert _snapshot(REPO / "data") == before, "the demo wrote into the working tree"
