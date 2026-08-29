"""A rejection annotates a row; it must not overwrite the row's history.

Measured on the live tool-oracle store 2026-08-28. The operator rejected three
routes with reasons, and the reasons were nowhere a reader would look:

    sealed    whoami             origin = imported-unverifiable:willow-build
    rejected  willow_web_search  origin = rejected:Jeles carries web search
                                 reason = ''

`memory_reject_pair` wrote ``origin = f"rejected:{reason}"[:200]``. Two costs.

**Provenance destroyed.** Every sealed sibling still records the import it came
from; the rejected ones no longer record it at all. The ledger keeps the
*reason*, so nothing was lost about the decision — what was lost was the fact
the decision was made *about*, and it is not recoverable from the ledger.

**The reason unfindable.** `reason` sat empty while the text lived under a
prefix in a column named for something else. Querying `reason` returns blank,
and the obvious conclusion — "no reason was given" — is wrong. That is exactly
what happened when these were first read back.

`reason`'s own schema comment calls it "the rationale for the YES", because
`tm_rejections` always carried one for the no. But that table belongs to
`reject_match`, keyed on `query_norm` for "right pair, wrong query"; a
pair-level rejection writes no row there and had nowhere else to go.
"""
from __future__ import annotations

import pytest

from nestor import memory
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path):
    st = SqliteStore(str(tmp_path / "t.db"))
    st.memory_init()
    return st


SOURCE = "open web search via duckduckgo"


def _pair(store, source=SOURCE, target="willow_web_search",
          origin="imported-unverifiable:willow-build", reason=""):
    pair = memory.add_pair(source, target, "tool", "tool", status="draft",
                           origin=origin, reason=reason, store=store)
    return pair["id"]


def _row(store, pair_id, source=SOURCE):
    """Read the row back through the store's own lookup rather than raw SQL."""
    matcher = memory.get_matcher(None)
    return store.memory_find(matcher.normalize(source), "tool", "tool")


# ── the property that was broken ───────────────────────────────────────────

def test_a_rejection_leaves_origin_untouched(store):
    """The row still records where it came from. This is the regression."""
    pid = _pair(store)
    memory.reject_pair(pid, verifier="sean campbell",
                       reason="Jeles carries web search", store=store)
    assert _row(store, pid)["origin"] == "imported-unverifiable:willow-build"


def test_the_reason_is_in_the_reason_column(store):
    """Where a reader looks first, and where the schema's own vocabulary puts
    the rationale for a decision."""
    pid = _pair(store)
    memory.reject_pair(pid, verifier="sean campbell",
                       reason="Jeles carries web search", store=store)
    assert "Jeles carries web search" in _row(store, pid)["reason"]


def test_the_old_shape_would_have_failed_this(store):
    """Prove-it-can-fail against the real prior behaviour: writing the reason
    into origin loses the import string, which is what this pins."""
    pid = _pair(store)
    before = _row(store, pid)["origin"]
    memory.reject_pair(pid, verifier="x", reason="anything", store=store)
    after = _row(store, pid)
    assert after["origin"] == before, "origin was overwritten — the old defect"
    assert after["origin"] != "rejected:anything"


def test_the_rejection_still_takes_effect(store):
    pid = _pair(store)
    memory.reject_pair(pid, verifier="sean campbell", reason="r", store=store)
    row = _row(store, pid)
    assert row["status"] == "rejected"
    assert row["verifier"] == "sean campbell"


# ── both halves of a reversal survive ──────────────────────────────────────

def test_a_prior_rationale_is_kept_alongside_the_rejection(store):
    """A pair sealed with a reason and later rejected keeps both. The argument
    for and the argument against are exactly the pair a future reader needs;
    keeping only the second is how a reversal becomes unreviewable."""
    pid = _pair(store, reason="sealed because the catalog shipped it")
    memory.reject_pair(pid, verifier="sean campbell",
                       reason="Jeles carries web search", store=store)
    got = _row(store, pid)["reason"]
    assert "sealed because the catalog shipped it" in got
    assert "Jeles carries web search" in got


def test_an_empty_reason_still_records_that_it_was_rejected(store):
    """A "no" with no words is still a no, and must be visible as one rather
    than leaving the field blank and indistinguishable from never-decided."""
    pid = _pair(store)
    memory.reject_pair(pid, verifier="sean campbell", reason="", store=store)
    assert _row(store, pid)["reason"].startswith("rejected")


def test_a_very_long_reason_is_capped_but_not_silently_lost_at_200(store):
    """The old cap was 200 characters on a column also holding the prefix. The
    reason is the operator's own words and should not be clipped mid-sentence
    by a limit chosen for a different field."""
    pid = _pair(store)
    long_reason = "because " + ("x" * 500)
    memory.reject_pair(pid, verifier="v", reason=long_reason, store=store)
    got = _row(store, pid)["reason"]
    assert len(got) > 200, "clipped at the old origin-sized cap"
    assert got.startswith("rejected: because ")
