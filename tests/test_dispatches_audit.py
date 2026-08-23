"""demo/the_dispatches_audit.py — Nestor's loop, proved on an external corpus.

The demo measures three properties of the loop against a real audit corpus
(demo/dispatches_audit_corpus.json). These tests pin the two that are pure logic
(the provenance min(), the corpus shape) and then run the whole demo as one
gate: every ``claim`` in it must hold, or ``main()`` returns non-zero.
"""
from __future__ import annotations

import os

import pytest

# A fixture key is not a secret. The demo sets the same default on a direct run,
# where it takes effect before signing is imported and the seals verify cleanly.
os.environ.setdefault("NESTOR_SEAL_KEY", "dispatches-fixture-key-not-a-secret")

from demo import desks
from demo import the_dispatches_audit as demo


def test_weakest_is_min_over_assumed_fitted_measured():
    """A pooled view is worth its weakest input, never an average (Way 3)."""
    assert demo.weakest(["measured", "measured"]) == "measured"
    assert demo.weakest(["measured", "fitted"]) == "fitted"
    assert demo.weakest(["measured", "fitted", "assumed"]) == "assumed"
    # Monotone: piling measured rows onto a fitted pool never lifts it. This is
    # the whole point — averaging would hide the fitted row; min() cannot.
    assert demo.weakest(["fitted"] + ["measured"] * 9) == "fitted"


def test_corpus_is_well_formed_and_states_are_legal():
    data = demo.load_corpus()
    assert data["findings"], "no findings in the corpus"
    assert data["drift_probes"], "no drift probes in the corpus"
    for f in data["findings"]:
        assert f["provenance"] in demo.STATES, f"illegal state: {f['provenance']}"
        assert f["question"].strip() and f["finding"].strip()
    # The corpus must contain the within-file contradiction probe that Way 2
    # proves the matcher is blind to — otherwise Way 2 measures nothing.
    assert any(p["packet_claim"] == "not repeated in the packet"
               for p in data["drift_probes"])


# In a full pytest process, `signing` is imported by an earlier test before any
# NESTOR_SEAL_KEY is set, so seal_is_valid can't verify signatures and warns that
# it is trusting sealed rows unverified. That does not affect what this test
# checks — retrieval, the min() pooling, the matcher ceiling — and on a direct
# `python demo/the_dispatches_audit.py` the key is set first and the seals verify
# cleanly (zero warnings). Filter the one expected warning rather than let an
# import-order artifact stand in for a real problem.
@pytest.mark.filterwarnings("ignore:NESTOR_SEAL_KEY not set")
def test_the_whole_demo_passes_every_claim(capsys):
    """The ledger floor, the no-false-memory property, the matcher ceiling, and
    the min() pooling all hold — run end to end, sealing a throwaway store."""
    desks.FAILURES.clear()                      # isolate from any earlier demo run
    assert demo.main() == 0
    assert "Every claim above held." in capsys.readouterr().out
