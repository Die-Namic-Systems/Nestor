"""The two-desks fixture has to keep being true, in both directions.

`demo/two_desks.py` makes two kinds of claim and this runs both. The ordinary
ones — the review desk still serves the fix a human sealed, each desk keeps its
own chain, the fixture proposes rather than seals — fail if somebody breaks the
recipe seam. The other eight are claims that a **gap is still open**: sealing
through `nestor.ui` writes a new row instead of upgrading one, the seal it makes
is unreachable to the domain that drafted it, the draft stays queued, a recorded
rejection suppresses nothing, and with a matcher installed process-wide one
desk's keys are computed by the other desk's parser. Those fail when somebody
closes the gap, which is the good outcome and still has to stop the build,
because a demo narrating a gap that no longer exists is the same defect as one
narrating a fix that never landed.

`IDEAS.md` §6.40 and §6.41 hold the arguments, and the fixture is what makes
their measurements executable rather than quoted. Both were proven by mutation
before commit — implementing the §6.40 fix (`ui.App.matcher`, threaded through
`_seal`, `_seal_draft` and `_reject_match`) turns all eight gap assertions red;
giving `SerialMatcher` the optional `score()` and touching nothing in the
package turns §6.41's red along with the two that say her seals are lost.

Run as a subprocess: the script installs a process-wide store, ledger path and
seal key, and is meant to be run that way.
"""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO = REPO / "demo" / "two_desks.py"


def run(*args):
    return subprocess.run([sys.executable, str(DEMO), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=180)


def test_every_claim_still_holds():
    done = run()
    assert done.returncode == 0, done.stdout + done.stderr
    assert "DEMO CLAIM FAILED" not in done.stdout
    assert "GAP CLOSED" not in done.stdout, (
        "a gap this fixture reports has been closed — update demo/two_desks.py "
        "and the IDEAS entry it names, in the same change:\n" + done.stdout)


def test_it_walks_the_beats_it_promises():
    out = run().stdout
    for beat in ("The intake desk, and a question nobody has adjudicated",
                 "She verifies it, at the only surface she is allowed to use",
                 "the same event, and her verification is gone",
                 "She says no, durably, and it is served anyway",
                 "The desk next door reviews the tool, and its seals work",
                 "Why his desk survives it",
                 "The rescue exists, and it is one per process",
                 "What the notified body asked for",
                 "What this fixture is for"):
        assert beat in out, f"missing beat: {beat}"


def test_it_says_it_is_fiction_before_it_says_anything_else(tmp_path):
    """An audit-trail product cannot ship a fixture that reads as a record.

    Pinned on the output rather than the docstring: the person who needs telling
    is looking at a terminal, not at the source.
    """
    out = run().stdout
    assert "Fiction" in out.split("1. The intake desk")[0]

    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    for desk in ("intake", "review"):
        rows = (kept / desk / "ledger.jsonl").read_text(encoding="utf-8")
        assert "fixture:attercliffe-two-desks" in rows, (
            f"every row must carry the fixture origin, in the {desk} trail as "
            f"well as the store")


def test_the_two_desks_keep_separate_chains(tmp_path):
    """The point of two desks is that they are two, including on disk.

    Not asserted through the script's own output: this reads the two files. One
    process holds one `cascade` ledger path, so a fixture that set it once would
    write both desks into one chain — which it did, in the first draft of this
    demo, and beat 8 then counted the total as hers.
    """
    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    a = (kept / "intake" / "ledger.jsonl").read_text(encoding="utf-8")
    b = (kept / "review" / "ledger.jsonl").read_text(encoding="utf-8")
    assert a and b, "both desks must have written a chain"
    assert a != b, "the two desks must not share one chain"
    assert "incident" in a and "incident" not in b, (
        "the intake desk's domain must not appear in the review desk's chain")


def test_the_fixture_proposes_and_does_not_seal(tmp_path):
    """The covenant, applied to the fixture that found the covenant's own gap.

    Every row this script writes to the review desk is a draft. Mirrored rather
    than imported — importing `patch_review.DOMAIN` would make the pin true by
    construction (CLAUDE.md, and `tests/test_ledger_kinds.py`).
    """
    import sqlite3

    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    con = sqlite3.connect(str(kept / "review" / "nestor.db"))
    try:
        rows = con.execute(
            "SELECT status, verifier FROM tm_pairs WHERE source_lang = 'defect'"
        ).fetchall()
    finally:
        con.close()
    assert rows, "the review desk must hold something"
    unsealed = [r for r in rows if r[0] == "draft"]
    assert unsealed, "the finding must go in as a draft awaiting a human"
    assert all(r[1] in ("", None) for r in unsealed), (
        "a draft this script wrote must not carry a verifier's name")


def test_it_cleans_up_after_itself_unless_told_not_to(tmp_path):
    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    for desk in ("intake", "review"):
        assert (kept / desk / "nestor.db").exists()
        assert (kept / desk / "ledger.jsonl").exists()

    before = set(pathlib.Path("/tmp").glob("nestor-two-desks-*"))
    assert run().returncode == 0
    assert not (set(pathlib.Path("/tmp").glob("nestor-two-desks-*")) - before), \
        "the default run must not leave a store behind"
