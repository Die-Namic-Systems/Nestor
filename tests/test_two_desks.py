"""The two-desks fixture has to keep being true, in both directions.

`demo/two_desks.py` used to hold eight assertions that a **gap was still open**:
sealing through `nestor.ui` wrote a new row instead of upgrading one, the seal it
made was unreachable to the domain that drafted it, the draft stayed queued, a
recorded rejection suppressed nothing, and with a matcher installed process-wide
one desk's keys were computed by the other desk's parser. Its `gap()` helper
failed the build when one of them *stopped* being true, on the argument that a
demo narrating a gap somebody closed is the same defect as one narrating a fix
that never landed.

§6.40 is now closed, so all eight have flipped to ordinary `claim()`s of the
correct behaviour and the fixture runs green. That is the outcome the `gap()`
mechanism was built to force, and it worked: closing the fix without rewriting
the narrative would have stopped this build.

The beats are unchanged and the outcomes are inverted, which is why the fixture
is kept rather than deleted — it asks the same questions it asked when the answer
was no, so a regression puts the old answers back and this test says so. The two
remaining `§6.41` claims are not a gap: `DefectMatcher` still implements the
optional `score()` and `SerialMatcher` still does not, and the fixture records
that this difference is what kept the defect invisible to the desk that had it.

`IDEAS.md` §6.40 and §6.41 hold the arguments.

Run as a subprocess: the script installs a process-wide store, ledger path and
seal key, and is meant to be run that way.
"""
import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.xdist_group("two_desks_tmp")

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO = REPO / "demo" / "two_desks.py"


def run(*args):
    return subprocess.run([sys.executable, str(DEMO), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=180,
                          check=False)


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
                 "the same event, and her verification holds",
                 "She says no, durably, and it stops being served",
                 "The desk next door reviews the tool, and its seals work",
                 "Why his desk survived it",
                 "Two desks, one process, and each keyed by its own matcher",
                 "What the notified body asked for",
                 "What this fixture is for"):
        assert beat in out, f"missing beat: {beat}"


def test_the_fixture_measures_the_thing_that_regressed():
    """The outcomes, read out of the fixture's own printed evidence.

    Written this way after an audit: the first version of this test asserted the
    *absence* of the four sentences the fixture used to print. Every one of them
    had been deleted from the script in the same commit, so no code path could
    emit them and their absence was guaranteed by the diff rather than by the
    fix — the exact pattern `nestor/answer.py` records as a past incident, four
    dead negative assertions, reproduced in the change whose IDEAS entry
    congratulates itself for catching vacuous tests.

    So this asserts what the fixture *prints* instead, and each line only
    appears when the thing it describes actually happened.
    """
    out = run().stdout
    # Beat 2/3: the seal upgraded one row and the domain can reach it. The
    # serial IS the key, printed from the row the surface wrote.
    assert "sealed id" in out and "key 'CH4471'" in out, (
        "the sealed row is not keyed by the domain's own matcher")
    # Beat 3: served, not pending, for the restated wording.
    assert "verified" in out and "Nestor: \033[33mpending\033[0m" not in out.split("3.")[1].split("4.")[0], (
        "the restated incident came back pending — §6.40 has regressed")
    # Beat 7: both desks live in one process with neither matcher installed globally.
    assert "process-wide matcher: StringMatcher — neither desk's" in out
    assert "her surface keys with SerialMatcher" in out
    assert "his surface keys with DefectMatcher" in out


def test_no_gap_assertion_survives_unnoticed():
    """`gap()` fails the build when a gap closes. It now has no call sites, and
    that is a fact worth pinning rather than leaving to a reader: if somebody
    adds one back, it means they found a NEW gap, and this test tells them to
    say so in IDEAS rather than leaving it in a fixture nobody re-reads."""
    source = DEMO.read_text(encoding="utf-8")
    calls = [ln for ln in source.splitlines()
             if ln.lstrip().startswith("gap(")]
    assert not calls, (
        "demo/two_desks.py has gap() assertions again — a gap this fixture "
        "reports is either newly found (write it up in IDEAS) or newly closed "
        f"(rewrite the beat): {calls}")
    assert "GAP CLOSED" not in run().stdout


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
