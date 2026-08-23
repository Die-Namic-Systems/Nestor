"""`scripts/retrieval_rank.py` and `scripts/corpus_contamination.py`.

Both are apparatus: they were written to reach IDEAS §6.106 and §6.102, and
`docs/agent-guide.md` says tooling built to answer a question ships with the
answer. They get tests for the reason that section gives — otherwise they are
scaffolding with nothing holding them to their claims.

What is worth gating is the distinction each exists to draw, because in both
cases the two sides print similar things and mean opposite ones:

* rank 1 below the bar (calibrate and it serves the right row) against rank
  N below the bar (calibrate and it serves a *wrong* row);
* a store with no contamination against a store that could not be read.

Neither harness is asserted to be correct about a real corpus here; the
fixtures are tiny and built in the test.
"""
from __future__ import annotations

import pathlib
import sqlite3
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RANK = ROOT / "scripts" / "retrieval_rank.py"
CONTAM = ROOT / "scripts" / "corpus_contamination.py"


def make_store(path: pathlib.Path, rows: list[tuple[str, str]]) -> None:
    """`rows` is (source_text, origin); source_norm is left for the harness."""
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE tm_pairs (source_text TEXT, source_norm TEXT, "
                "source_lang TEXT, target_lang TEXT, origin TEXT)")
    con.executemany("INSERT INTO tm_pairs VALUES (?,?,?,?,?)",
                    [(text, "", "decision", "decision", origin) for text, origin in rows])
    con.commit()
    con.close()


def run(script: pathlib.Path, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *argv],
                          capture_output=True, text=True, cwd=str(ROOT),
                          check=False)


# --- retrieval_rank --------------------------------------------------------

def test_a_missing_store_says_it_could_not_look(tmp_path):
    done = run(RANK, "--db", str(tmp_path / "nope.db"), "--probe", "x", "--expect", "y")
    assert done.returncode == 1
    assert "could not look" in done.stdout


def test_mismatched_probe_and_expect_counts_are_refused(tmp_path):
    db = tmp_path / "s.db"
    make_store(db, [("anything at all", "o")])
    done = run(RANK, "--db", str(db), "--probe", "a", "--probe", "b", "--expect", "a")
    assert done.returncode == 2
    assert "same number of times" in done.stdout


def test_the_expected_row_ranking_first_is_reported_as_rank_one(tmp_path):
    db = tmp_path / "s.db"
    make_store(db, [("the embedder stand-in and its drift", "o"),
                    ("something else entirely about ledgers", "o")])
    done = run(RANK, "--db", str(db), "--probe", "the embedder stand-in and its drift",
               "--expect", "embedder stand-in")
    assert done.returncode == 0
    assert "rank 1/2" in done.stdout


def test_a_row_that_loses_reports_its_rank_and_who_beat_it(tmp_path):
    """The distinction the harness exists for: not rank 1, so lowering the bar
    would serve one of the rows above instead."""
    db = tmp_path / "s.db"
    make_store(db, [("Should the ledger be a decaying weight column?", "o"),
                    ("Should the fixture stay one single file?", "o"),
                    ("licences reported by a model need checking", "o")])
    done = run(RANK, "--db", str(db), "--probe", "Should I trust a licence?",
               "--expect", "licences reported by a model")
    assert done.returncode == 0
    assert "rank 3/3" in done.stdout
    assert "beaten by" in done.stdout
    assert "would serve one of the rows above" in done.stdout


def test_an_absent_expected_row_is_unfindable_not_last(tmp_path):
    """'The answer is not here' says nothing about the matcher; 'the answer is
    here and ranked last' does. They must not print the same."""
    db = tmp_path / "s.db"
    make_store(db, [("a row", "o"), ("another row", "o")])
    done = run(RANK, "--db", str(db), "--probe", "anything",
               "--expect", "a string that appears in no row")
    assert done.returncode == 0
    assert "unfindable" in done.stdout
    assert "rank" not in done.stdout.split("unfindable")[1].split("\n")[0]


def test_an_empty_domain_is_read_and_empty_not_unreadable(tmp_path):
    db = tmp_path / "s.db"
    make_store(db, [])
    done = run(RANK, "--db", str(db), "--probe", "x", "--expect", "y")
    assert done.returncode == 0
    assert "0 row(s)" in done.stdout
    assert "Read, and empty" in done.stdout
    # The empty message *quotes* the other phrase while distinguishing itself
    # from it, so the tell is the refusal wording, which only the absent case
    # prints. Asserting on the quoted phrase is what this line got wrong first.
    assert "refusing rather than reporting" not in done.stdout


# --- corpus_contamination --------------------------------------------------

def test_a_vendored_origin_is_counted_and_named(tmp_path):
    db = tmp_path / "c.db"
    make_store(db, [("a", "Nestor@abc:.venv/lib/python3.11/site-packages/PIL/x.py#f"),
                    ("b", "Nestor@abc:nestor/memory.py#add_pair")])
    done = run(CONTAM, "--db", str(db))
    assert done.returncode == 0
    assert ".venv/" in done.stdout
    assert "contaminated" in done.stdout


def test_a_clean_store_states_its_basis_in_words(tmp_path):
    """A clean report must state the basis of its claim, not just say 'clean'.
    The check is now git-ls-files-scoped (#96), a stronger claim than the old
    build-artefact pattern stub: it says, in words, that every placeable origin
    was verified against the commit it names."""
    db = tmp_path / "c.db"
    make_store(db, [("a", "Nestor@abc:nestor/memory.py#add_pair")])
    done = run(CONTAM, "--db", str(db))
    assert done.returncode == 0
    assert "every origin names a git-tracked path" in done.stdout
    assert "git ls-files" in done.stdout
    assert "every placeable origin path is in the commit it claims" in done.stdout


def test_an_unreadable_store_is_not_reported_as_clean(tmp_path):
    """A store that could not be opened must never be counted among the clean —
    the same distinction the corpus readers themselves owe (IDEAS 6.101)."""
    db = tmp_path / "broken.db"
    db.write_text("this is not a sqlite database")
    done = run(CONTAM, "--db", str(db))
    assert "could not read" in done.stdout
    assert "nothing about these stores is known" in done.stdout.lower()
    assert "no known build-artefact path" not in done.stdout


def test_fail_on_contamination_is_a_gate(tmp_path):
    db = tmp_path / "c.db"
    make_store(db, [("a", "X@abc:node_modules/left-pad/index.js#f")])
    assert run(CONTAM, "--db", str(db)).returncode == 0
    assert run(CONTAM, "--db", str(db), "--fail-on-contamination").returncode == 1
