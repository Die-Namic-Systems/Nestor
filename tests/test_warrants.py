"""Gates for the warrant relation (docs/warrants.md, decision 0164).

Every test exercises surface new in this change, so all fail against ``HEAD~1``
for the trivial reason that ``nestor.warrant`` and the ``decision_warrants``
table did not exist. The ones that earn their place are the adversarial guards
and the three structural claims the memo rests on:

* **attestation is not storable.** A sealed pair already is one, signed under a
  key this store does not hold; a second stored representation would be the
  forgeable one. ``attach`` refuses the kind outright, and ``warrants_for``
  composes the seal in on read instead — so a seal is never counted twice.
* **a construction warrant cannot be minted as a bare assertion.** Without an
  expected digest it says "the shape proves it" while giving a reader no shape
  to run, which is jeles' ``asserted`` rung wearing a proof's clothes. Refused.
  And a *citation* carrying a digest is refused for the mirror reason: it would
  read as though Nestor had checked the source.
* **warrants are a set, never a ladder.** ``kinds_held`` returns a ``set``; there
  is no strongest-warrant accessor to test because there must not be one.

Plus the same orthogonality checks evidence earned: a warrant changes no seal
state, and warranting is not evidencing (the two tables do not see each other).
"""
from __future__ import annotations

import pytest

from nestor import cascade, evidence, ledger, memory, storage, warrant
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    # No seal key, for the reason test_evidence gives: add_pair trusts a stored
    # 'sealed' status, so a test can build sealed rows without signing.
    monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.memory_init()
    storage.set_store(s)
    yield s
    s.close()
    storage.set_store(None)


def _sealed(store, q, c="yes", verifier="rita"):
    return memory.add_pair(q, c, "decision", "decision", status="sealed",
                           verifier=verifier, store=store)


def _draft(store, q, c="maybe"):
    return memory.add_pair(q, c, "decision", "decision", status="draft",
                           store=store)


# -- the capability is present on the shipped store --------------------------

def test_the_sqlite_store_supports_warrants(store):
    assert storage.supports_warrants(store) is True


# -- attach records a warrant, and it reads back -----------------------------

def test_citation_attaches_and_reads_back(store):
    pair = _draft(store, "who owns the arrears clause")
    w = warrant.attach(pair["id"], "citation", "Crossref",
                       "https://doi.org/10.1000/xyz", attached_by="agent-7",
                       store=store)
    assert w["kind"] == "citation"
    assert w["authority"] == "Crossref"
    back = warrant.warrants_for(pair["id"], store=store)
    assert [r["id"] for r in back] == [w["id"]]
    assert back[0]["stored"] is True


def test_construction_requires_and_keeps_its_expected_digest(store):
    pair = _draft(store, "does the scan reach the network")
    w = warrant.attach(pair["id"], "construction", "redential-scan",
                       "npx redential scan .", check="compare the merkle root",
                       expected_digest="9f2b" * 8, store=store)
    back = warrant.warrants_for(pair["id"], store=store)[0]
    assert back["expected_digest"] == w["expected_digest"] == "9f2b" * 8
    # The column is check_procedure in SQL (CHECK is a keyword); the recipe's
    # vocabulary must not leak that.
    assert back["check"] == "compare the merkle root"
    assert "check_procedure" not in back


# -- attestation is the seal's, and is never stored --------------------------

def test_attestation_is_refused_as_a_stored_kind(store):
    pair = _sealed(store, "arrears defined")
    with pytest.raises(ValueError, match="already is one"):
        warrant.attach(pair["id"], "attestation", "rita", "n/a", store=store)
    assert store.memory_warrants_for(pair["id"]) == []


def test_a_seal_composes_in_as_attestation_without_being_stored(store):
    pair = _sealed(store, "arrears defined", verifier="rita")
    held = warrant.warrants_for(pair["id"], store=store)
    assert [w["kind"] for w in held] == ["attestation"]
    att = held[0]
    assert att["authority"] == "rita"
    # `stored: False` is what the export path keys on so a seal does not travel
    # twice — once as a seal with its signature, once as a warrant without one.
    assert att["stored"] is False
    assert store.memory_warrants_for(pair["id"]) == []


def test_a_draft_has_no_attestation(store):
    pair = _draft(store, "still open")
    assert warrant.kinds_held(pair["id"], store=store) == set()


def test_a_sealed_and_cited_pair_holds_both(store):
    pair = _sealed(store, "arrears defined")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    # The case the memo says segregation cannot represent and accumulation can.
    assert warrant.kinds_held(pair["id"], store=store) == {
        "attestation", "citation"}


# -- adversarial guards: each refuses with nothing written -------------------

@pytest.mark.parametrize("kind,authority,locator,digest,needle", [
    ("bogus", "a", "b", "", "unknown warrant kind"),
    ("citation", "", "https://x", "", "needs an authority"),
    ("citation", "Crossref", "", "", "needs a locator"),
    ("construction", "tool", "recipe", "", "needs an expected_digest"),
    ("citation", "Crossref", "https://x", "deadbeef", "takes no expected_digest"),
])
def test_refusals_write_nothing(store, kind, authority, locator, digest, needle):
    pair = _draft(store, "a question")
    before = len(ledger.entries(kind="attach_warrant"))
    with pytest.raises(ValueError, match=needle):
        warrant.attach(pair["id"], kind, authority, locator,
                       expected_digest=digest, store=store)
    assert store.memory_warrants_for(pair["id"]) == []
    assert len(ledger.entries(kind="attach_warrant")) == before


def test_a_ghost_pair_is_refused(store):
    with pytest.raises(ValueError, match="no pair"):
        warrant.attach("no-such-id", "citation", "Crossref", "https://x",
                       store=store)


def test_an_over_long_locator_is_refused_not_truncated(store):
    pair = _draft(store, "a question")
    with pytest.raises(ValueError, match="too long"):
        warrant.attach(pair["id"], "citation", "Crossref", "u" * 5000,
                       store=store)
    assert store.memory_warrants_for(pair["id"]) == []


# -- orthogonality: a warrant is not a seal and not evidence -----------------

def test_warranting_changes_no_seal_state(store):
    pair = _draft(store, "still open")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    assert store.memory_get(pair["id"])["status"] == "draft"


def test_a_warrant_is_not_evidence_and_evidence_is_not_a_warrant(store):
    pair = _sealed(store, "arrears defined")
    evidence.attach(pair["id"], "url", "https://example.test/doc", store=store)
    assert store.memory_warrants_for(pair["id"]) == []
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    # Attaching a warrant must not satisfy the evidence queue, and vice versa:
    # they answer different questions and neither stands in for the other.
    assert len(evidence.evidence_for(pair["id"], store=store)) == 1
    assert len([w for w in warrant.warrants_for(pair["id"], store=store)
                if w["stored"]]) == 1


# -- the ledger records it, and records no verdict ---------------------------

def test_the_ledger_records_the_attachment_and_confirms_nothing(store):
    pair = _draft(store, "a question")
    w = warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                       attached_by="agent-7", store=store)
    rows = ledger.entries(kind="attach_warrant")
    assert len(rows) == 1
    entry = rows[0]
    assert entry["warrant_id"] == w["id"]
    assert entry["authority"] == "Crossref"
    assert entry["attached_by"] == "agent-7"
    assert entry["content_sha"]
    # No signature and no verdict: the row says a warrant was CLAIMED, never
    # that it holds. Nothing in Nestor may mark one satisfied.
    assert "warrant_sig" not in entry
    assert "verified" not in entry


def test_warrants_accumulate_and_are_never_rewritten(store):
    pair = _draft(store, "a question")
    a = warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                       store=store)
    b = warrant.attach(pair["id"], "citation", "OpenAlex", "https://openalex/2",
                       store=store)
    held = [w for w in warrant.warrants_for(pair["id"], store=store)
            if w["stored"]]
    assert {w["id"] for w in held} == {a["id"], b["id"]}


# -- the shape of the answer: a set, deliberately ----------------------------

def test_kinds_held_is_a_set_with_no_ordering(store):
    pair = _sealed(store, "arrears defined")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    warrant.attach(pair["id"], "construction", "redential", "npx redential scan",
                   expected_digest="ab" * 16, store=store)
    held = warrant.kinds_held(pair["id"], store=store)
    assert isinstance(held, set)
    assert held == {"attestation", "citation", "construction"}
    # There is no strongest-warrant accessor, and this test exists to say that
    # is deliberate: "sealed by Rita" and "cited to Crossref" do not compare.
    assert not hasattr(warrant, "strongest")
