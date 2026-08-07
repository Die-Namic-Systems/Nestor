"""The filing-cabinet fixture has to keep being true, in both directions.

`demo/filing_cabinet.py` makes two kinds of claim and this runs both. The
ordinary ones — an unadjudicated vehicle is not served, a draft scoring 1.000 is
still not served, a seal made at the surface is reachable by the VIN tail — fail
if somebody breaks the loop. The other three are claims that a **gap is still
open**: a suffix does not separate two men (§6.22), the entity graph still has
only `seal` (§6.39), and any name at all can be sealed under because there is no
verifier policy. Those fail when somebody closes the gap, which is the good
outcome and still has to stop the build.

All three proven by mutation before commit. Giving `EntityResolver` a `propose`
turns §6.39's red; making `add_pair` refuse a seal from an unenrolled verifier
turns the policy one red. The first version of that second gate did **not** go
red — it died with a traceback, because the mutation makes `add_pair` raise and
the fixture called it unguarded. A gate that crashes where it owes a verdict is
not a gate, and it now catches and reports.

Run as a subprocess: the script installs a process-wide store, ledger path,
matcher and seal key, and is meant to be run that way.
"""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO = REPO / "demo" / "filing_cabinet.py"


def run(*args):
    return subprocess.run([sys.executable, str(DEMO), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=180)


def test_every_claim_still_holds():
    done = run()
    assert done.returncode == 0, done.stdout + done.stderr
    assert "DEMO CLAIM FAILED" not in done.stdout
    assert "GAP CLOSED" not in done.stdout, (
        "a gap this fixture reports has been closed — update "
        "demo/filing_cabinet.py and the entry it names, in the same change:\n"
        + done.stdout)


def test_it_walks_the_beats_it_promises():
    out = run().stdout
    for beat in ("A question nobody has adjudicated",
                 "A perfect score, and still not served",
                 "A human seals it, and a phone call reaches it",
                 "the name is the first problem",
                 "Four documents agreeing against three",
                 "The only document that matters is a draft",
                 "A signature bound to a name that was removed",
                 "An alias with one witness, and the witness is dead",
                 "What he actually asked for, and the refusal",
                 "What this fixture is for"):
        assert beat in out, f"missing beat: {beat}"


def test_the_two_numbers_the_name_beat_turns_on():
    """Mirrored, not imported.

    Pinning these by recomputing them from the package would make them true by
    construction (CLAUDE.md, `tests/test_ledger_kinds.py`). They are the printed
    output, which is what a reader sees and what the argument rests on.
    """
    out = run().stdout
    assert "0.985" in out, "II vs III must still land above the seal threshold"
    assert "0.292" in out, "'Big Jim' must still fail to reach his own record"


def test_it_says_it_is_fiction_before_it_says_anything_else(tmp_path):
    """An audit-trail product cannot ship a fixture that reads as a record."""
    out = run().stdout
    assert "Fiction" in out.split("1. A question")[0]

    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    trail = (kept / "lot" / "ledger.jsonl").read_text(encoding="utf-8")
    assert "fixture:filing-cabinet" in trail, \
        "every row must carry the fixture origin, in the trail as well as the store"


def test_the_fixture_signs_nothing_in_his_name(tmp_path):
    """The covenant, on the desk holding the man's own papers.

    The one row on the papers desk carrying a verifier is the beat-9
    demonstration, which is deliberately signed by nobody real.
    """
    import sqlite3

    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    con = sqlite3.connect(str(kept / "papers" / "nestor.db"))
    try:
        rows = con.execute(
            "SELECT status, verifier, source_lang FROM tm_pairs").fetchall()
    finally:
        con.close()
    assert rows, "the papers desk must hold something"
    dossier = [r for r in rows if r[2] == "dossier"]
    assert dossier, "the dossier readings must be there"
    assert all(r[0] == "draft" for r in dossier), \
        "every reading of his papers is a draft"
    assert all(not r[1] for r in dossier), \
        "and none of them carries a verifier's name"


def test_it_cleans_up_after_itself_unless_told_not_to(tmp_path):
    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    for desk in ("lot", "papers"):
        assert (kept / desk / "nestor.db").exists()

    before = set(pathlib.Path("/tmp").glob("nestor-cabinet-*"))
    assert run().returncode == 0
    assert not (set(pathlib.Path("/tmp").glob("nestor-cabinet-*")) - before), \
        "the default run must not leave a store behind"
