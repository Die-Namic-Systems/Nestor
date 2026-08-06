"""The shoebox fixture has to keep being true, in both directions.

`demo/shoebox.py` makes two kinds of claim and this runs both. The ordinary ones
— her correction is what serves, the store still holds what she replaced — fail
if somebody breaks lineage. The other two are claims that a **gap is still
open**: the replaced-seals view is blind to `supersede`, no human-facing surface
reads `reopen_when`, `entity.seal` overwrites where `reconcile` keeps, a short
term lock fires inside a longer word, and the entity recipe has no verb for an
unverified alias. Those fail when somebody closes the gap, which is
the good outcome and still has to stop the build, because a demo narrating a
gap that no longer exists is the same defect as one narrating a fix that never
landed.

`IDEAS.md` §6.35, §6.37, §6.38 and §6.39 hold the arguments — one per gap, and
the fixture is what makes their measurements executable rather than quoted. Run as a subprocess: the script installs a
process-wide store, ledger path and seal key, and is meant to be run that way.
"""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO = REPO / "demo" / "shoebox.py"


def run(*args):
    return subprocess.run([sys.executable, str(DEMO), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=180)


def test_every_claim_still_holds():
    done = run()
    assert done.returncode == 0, done.stdout + done.stderr
    assert "DEMO CLAIM FAILED" not in done.stdout
    assert "GAP CLOSED" not in done.stdout, (
        "a gap this fixture reports has been closed — update demo/shoebox.py "
        "and the IDEAS entry it names, in the same change:\n" + done.stdout)


def test_it_walks_the_beats_it_promises():
    out = run().stdout
    for beat in ("Fourteen months of evenings",
                 "A ruling, not a translation",
                 "She was wrong about something that mattered",
                 "where can she see that she changed her mind",
                 "a deferral, which is not the same as a no",
                 "The people in them are an entity graph",
                 "Two men called Pepe",
                 "The same collision, in the recipe notebook",
                 "The words the family keeps",
                 "Somebody living",
                 "What the fixture is for"):
        assert beat in out, f"missing beat: {beat}"


def test_it_says_it_is_fiction_before_it_says_anything_else(tmp_path):
    """An audit-trail product cannot ship a fixture that reads as a record.

    Pinned on the output rather than the docstring: the person who needs telling
    is looking at a terminal, not at the source.
    """
    out = run().stdout
    assert "Fiction" in out.split("1. Fourteen months")[0]

    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    rows = (kept / "ledger.jsonl").read_text(encoding="utf-8")
    assert "fixture:consuelo-shoebox" in rows, \
        "every row must carry the fixture origin, in the trail as well as the store"


def test_it_cleans_up_after_itself_unless_told_not_to(tmp_path):
    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    assert (kept / "nestor.db").exists() and (kept / "ledger.jsonl").exists()

    before = set(pathlib.Path("/tmp").glob("nestor-shoebox-*"))
    assert run().returncode == 0
    assert not (set(pathlib.Path("/tmp").glob("nestor-shoebox-*")) - before), \
        "the default run must not leave a store behind"
