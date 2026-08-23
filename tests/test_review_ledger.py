"""The review ledger derives its place from the rows (issue #167, piece 1).

The 654 rows extracted from git history live in 22 per-repository stores, and
a review of them spans sessions and machines. The obvious design is a cursor
file recording where the reader stopped. These tests pin the design that was
chosen instead: **nothing is remembered.** A row is a draft until a human
seals or rejects it, so the drafts remaining *are* the rows still to look at,
and the ledger is a read over the stores rather than an account kept beside
them.

That matters for a reason this repository keeps rediscovering: a second copy
of a fact is a thing that can disagree with the first. A cursor would go stale
the moment somebody decided a row in ``nestor ui`` without telling the script,
and it would then confidently report a place that was not where the review
was. Decision 0163 states the general rule; this is it applied.
"""
from __future__ import annotations

import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from git_decisions.run_all import next_rung, review_state


def _store(path: pathlib.Path, **counts: int) -> pathlib.Path:
    """A store holding ``counts`` rows per status, and nothing else."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE tm_pairs (id INTEGER PRIMARY KEY, status TEXT)")
    for status, n in counts.items():
        for _ in range(n):
            con.execute("INSERT INTO tm_pairs (status) VALUES (?)", (status,))
    con.commit()
    con.close()
    return path


def test_the_place_is_the_draft_count(tmp_path):
    """No cursor: what is left to review is what is still a draft."""
    st = review_state(_store(tmp_path / "s.db", draft=44, sealed=26))
    assert st["total"] == 70
    assert st["unreviewed"] == 44
    assert st["decided"] == 26
    assert st["started"] is True
    assert st["done"] is False


def test_a_rejected_row_counts_as_reviewed(tmp_path):
    """Deciding is not agreeing. A rejection is a row somebody looked at."""
    st = review_state(_store(tmp_path / "s.db", draft=1, sealed=2, rejected=3))
    assert st["decided"] == 5
    assert st["unreviewed"] == 1


def test_an_untouched_store_is_not_started(tmp_path):
    st = review_state(_store(tmp_path / "s.db", draft=10))
    assert st["started"] is False
    assert st["done"] is False


def test_a_fully_decided_store_is_done(tmp_path):
    st = review_state(_store(tmp_path / "s.db", sealed=3, rejected=1))
    assert st["done"] is True
    assert st["unreviewed"] == 0


def test_an_empty_store_is_not_done(tmp_path):
    """Nothing to review is not the same as having reviewed everything.

    ``done`` gates the congratulatory line and excludes a rung from ``next``.
    An empty store must not claim the first, and 0160's lesson is the reason:
    "nothing here" and "nothing left to do" are different claims.
    """
    st = review_state(_store(tmp_path / "s.db"))
    assert st["total"] == 0
    assert st["done"] is False


def test_a_missing_store_is_reported_not_counted(tmp_path):
    st = review_state(tmp_path / "never-extracted.db")
    assert st["missing"] is True
    assert st["unreviewed"] == 0


def test_an_unreadable_store_is_an_error_not_a_finished_rung(tmp_path):
    """The failure mode worth a test of its own.

    A corrupt store yields no rows. Counted naively that is zero drafts, which
    is exactly what a completed review looks like — the ledger would report a
    rung as finished because its file was broken. It must say so instead, and
    it must never be offered as the next thing to pick up.
    """
    bad = tmp_path / "corrupt.db"
    bad.write_bytes(b"this is not a database")
    st = review_state(bad)
    assert "error" in st
    assert st.get("done") is not True
    assert next_rung([("corrupt", st)]) is None


def test_next_rung_prefers_a_started_store_over_a_smaller_one(tmp_path):
    """A held context is worth more than a small one.

    The extraction ran smallest-first so a wrong shape would be caught cheaply.
    Reading is the opposite errand: dropping a half-read store means paying its
    context again, so finishing beats starting even when the unstarted rung is
    smaller.
    """
    started = review_state(_store(tmp_path / "a.db", draft=44, sealed=26))
    smaller = review_state(_store(tmp_path / "b.db", draft=3))
    name, _ = next_rung([("small-untouched", smaller), ("big-started", started)])
    assert name == "big-started"


def test_among_untouched_rungs_the_smallest_wins(tmp_path):
    a = review_state(_store(tmp_path / "a.db", draft=247))
    b = review_state(_store(tmp_path / "b.db", draft=3))
    name, _ = next_rung([("big", a), ("small", b)])
    assert name == "small"


def test_next_rung_is_none_when_everything_is_decided(tmp_path):
    """The honest answer to "what next" when the answer is nothing."""
    done = review_state(_store(tmp_path / "a.db", sealed=5))
    empty = review_state(_store(tmp_path / "b.db"))
    assert next_rung([("done", done), ("empty", empty)]) is None


def test_the_next_line_does_not_hand_the_human_a_read_only_ui(capsys, tmp_path):
    """The flag an agent uses would leave the sealer with a dead button.

    An agent opens a store `--read-only` so a stray click cannot seal what is
    not its to seal. This line is printed for the person who *does* the
    sealing, and a read-only server refuses that at the API — so the same flag
    in the same place would be exactly wrong.
    """
    from git_decisions.run_all import cmd_status
    _store(tmp_path / "owner__repo.db", draft=2)
    cmd_status([{"name": "owner/repo"}], tmp_path)
    out = capsys.readouterr().out
    assert " ui\n" in out
    assert "--read-only" not in out


def test_the_ledger_totals_match_the_stores(capsys, tmp_path):
    _store(tmp_path / "a__a.db", draft=10, sealed=5)
    _store(tmp_path / "b__b.db", draft=3)
    cmd = __import__("git_decisions.run_all", fromlist=["cmd_status"]).cmd_status
    assert cmd([{"name": "a/a"}, {"name": "b/b"}], tmp_path) == 0
    out = capsys.readouterr().out
    assert "18 row(s) across 2 store(s)" in out
    assert "5 decided" in out
    assert "13 left" in out
