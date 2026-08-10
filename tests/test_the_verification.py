"""The verification demo — held to the one thing it must never do, and the trap.

`demo/the_verification.py` runs four real claims past jeles' corroboration bar
and lands them in this store. Three of the four are refutations of a published
article and the evidence backs them, which is exactly the situation where a
demo is tempted to reward itself with a seal.

Two gates matter:

* **it seals nothing.** Being right is not being checked. A demo that sealed its
  own findings because they were well-sourced would be the machine grading its
  own work, in the file that exists to say why that is not allowed.
* **the self-citation trap is detected.** The demo's finding is that a claim's
  own source can appear in its own evidence and be counted as an independent
  witness. If that detection silently stopped firing, the demo would go on
  printing a clean corroboration count and the finding would evaporate.

The claim data is fixture, not fetched, so these run offline. jeles supplies
`registrable_domain`, so the tests that need it skip without a checkout — and
the one that does not need it still runs, because "seals nothing" must hold in
every environment.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo import the_verification as DEMO           # noqa: E402
from tests._fleet_paths import jeles_checkout       # noqa: E402

JELES = jeles_checkout()
SCRIPT = ROOT / "demo" / "the_verification.py"


def test_the_demo_never_seals_anything():
    """Pinned on the source, so it holds without jeles installed.

    `status="sealed"` anywhere in this file would mean a machine promoted its
    own reading because the sources agreed with it.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    body = src.split('"""', 2)[-1]
    assert 'status="draft"' in body
    assert 'status="sealed"' not in body
    assert "verifier=" not in body, (
        "the demo must not name a verifier — nobody has checked these")


def test_every_claim_carries_its_own_citations():
    for c in DEMO.CLAIMS:
        assert c["sources"], f"{c['id']} has no citations"
        assert all(u.startswith("https://") for u in c["sources"])
        assert c["reached"] and c["article"]


def test_the_ribbit_row_still_contains_the_article_under_test():
    """The trap is data, not narration.

    The finding is that a search for this claim returned the article being
    checked. If that URL were quietly dropped from the fixture the demo would
    print a tidy six-source corroboration and the whole point would be gone —
    so the row is pinned to still contain it.
    """
    ribbit = next(c for c in DEMO.CLAIMS if c["id"] == "ribbit")
    assert any(DEMO.UNDER_TEST in u for u in ribbit["sources"]), (
        "the self-citation is the finding; without it this is an ordinary lookup")


def test_only_one_claim_is_recorded_as_holding():
    """Three refutations and one confirmation. A demo where the checker is
    right about everything is a demo with its thumb on the scale — the
    hollywood-frog row is here because the article got that one correct."""
    held = [c["id"] for c in DEMO.CLAIMS if c["holds"]]
    assert held == ["hollywood-frog"]


@pytest.mark.skipif(not JELES.exists(), reason="no jeles checkout present")
def test_it_runs_and_reports_zero_sealed():
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(JELES)}
    done = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                          text=True, timeout=300, env=env, cwd=str(ROOT))
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-400:]
    out = __import__("re").sub(r"\x1b\[[0-9;]*m", "", done.stdout)
    assert "0 sealed" in out
    assert "the trap" in out, "the self-citation finding must be reported"
    assert "wordsmarts.com" in out


@pytest.mark.skipif(not JELES.exists(), reason="no jeles checkout present")
def test_two_pages_repeating_one_claim_count_as_two_sources():
    """The measurement behind the trap, made directly against jeles' rule.

    Not a criticism of that rule — `_independence.py` already says it is "a
    cheap heuristic, deliberately weaker" than its constitution's Independent
    Witness, precisely because two domains can be one actor. This pins a
    concrete instance so the claim in the demo is measured rather than argued.
    """
    sys.path.insert(0, str(JELES))
    from jeles._independence import MIN_INDEPENDENT_SOURCES, registrable_domain
    original = "https://wordsmarts.com/animals-world/"
    quoting_it = "https://x.com/StephenBaldwin7/status/1818380587125645362"
    domains = {registrable_domain(original), registrable_domain(quoting_it)}
    assert len(domains) >= MIN_INDEPENDENT_SOURCES, (
        "one claim and a page quoting it clear the independence bar — which is "
        "the demo's finding, and the reason a count is not a verification")


@pytest.mark.skipif(not JELES.exists(), reason="no jeles checkout present")
def test_it_writes_nothing_into_this_repository():
    """A demo that leaves a store behind in the checkout is not a demo."""
    before = {p for p in ROOT.iterdir()}
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(JELES)}
    subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True,
                   timeout=300, env=env, cwd=str(ROOT))
    assert {p for p in ROOT.iterdir()} == before
