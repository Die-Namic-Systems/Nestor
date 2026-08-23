import pytest
from conftest import read_ledger

from nestor.entity import EntityResolver
from nestor.memory import ConflictingDraftError


def _amazon_resolver(store):
    r = EntityResolver(store, domain="company")
    for surface in ["Amazon", "Amazon.com Inc", "AMZN", "AWS"]:
        r.seal(surface, "Amazon", verifier="analyst", origin="sec-filing")
    return r


# --- the flagship case -------------------------------------------------------

def test_amazon_aliases_resolve_to_canonical(store):
    r = _amazon_resolver(store)

    # A messy surface form of a sealed alias resolves to the canonical entity.
    res = r.resolve("amazon.com  inc.")
    assert res["canonical"] == "Amazon"
    assert res["sealed"] is True
    assert res["confidence"] == 1.0
    assert res["provenance"]["verifier"] == "analyst"
    assert res["provenance"]["sealed_surface"] == "Amazon.com Inc"

    # A ticker symbol resolves too, carrying the sealed mapping's provenance.
    res2 = r.resolve("AMZN")
    assert res2["canonical"] == "Amazon"
    assert res2["sealed"] is True
    assert res2["provenance"]["origin"] == "sec-filing"


def test_unseen_surface_returns_unsealed_suggestion(store):
    r = _amazon_resolver(store)
    res = r.resolve("Alphabet Inc")
    # Nothing sealed clears the threshold -> no canonical, flagged unsealed.
    assert res["canonical"] is None
    assert res["sealed"] is False
    assert res["provenance"]["draft"] is True


def test_add_alias_is_seal(store):
    r = EntityResolver(store, domain="company")
    r.add_alias("Big Blue", "IBM", verifier="curator")
    res = r.resolve("big  blue")
    assert res["canonical"] == "IBM"
    assert res["sealed"] is True


def test_entity_resolution_is_ledgered(store):
    r = _amazon_resolver(store)
    r.resolve("AMZN")
    kinds = [e["kind"] for e in read_ledger()]
    assert "entity_seal" in kinds
    assert "entity_resolve" in kinds


def test_domains_are_isolated(store):
    companies = EntityResolver(store, domain="company")
    people = EntityResolver(store, domain="person")
    companies.seal("Apple", "Apple Inc.", verifier="a")
    people.seal("Tim", "Tim Cook", verifier="b")
    # A person-domain lookup never sees the company alias.
    assert companies.resolve("apple")["canonical"] == "Apple Inc."
    assert people.resolve("apple")["canonical"] is None


# --- propose (IDEAS §6.39) ---------------------------------------------------

def test_propose_creates_draft_alias(store):
    """The basic case: propose an unverified alias, then resolve it."""
    r = EntityResolver(store, domain="person")
    result = r.propose("Tony", "Tony (b. 1972)", reason="aunt described him",
                       origin="phone-call")
    assert result["draft"] is True
    assert result["sealed"] is False
    assert result["surface"] == "Tony"
    assert result["canonical"] == "Tony (b. 1972)"
    assert "pair_id" in result

    # resolve sees the draft as an unsealed suggestion, not a canonical answer.
    res = r.resolve("Tony")
    assert res["canonical"] is None
    assert res["sealed"] is False
    assert res["provenance"]["draft"] is True
    assert res["provenance"]["suggestion"] == "Tony (b. 1972)"


def test_propose_does_not_append_to_ledger(store):
    """A proposal is not a decision — nothing is ledgered."""
    r = EntityResolver(store, domain="person")
    r.propose("Tony", "Tony (b. 1972)")
    kinds = [e["kind"] for e in read_ledger()]
    assert "entity_seal" not in kinds
    # No entity_propose kind either — propose writes no ledger entry at all.
    assert not any("propose" in k for k in kinds)


def test_propose_on_sealed_name_returns_sealed_row(store):
    """A draft landing on an already-sealed name returns the sealed row."""
    r = EntityResolver(store, domain="person")
    r.seal("Tony", "Antonio Ruiz", verifier="nieves")
    result = r.propose("Tony", "Tony (b. 1972)")
    # The existing sealed row is returned untouched.
    assert result["sealed"] is True
    assert result["draft"] is False
    # resolve still serves the sealed canonical.
    res = r.resolve("Tony")
    assert res["canonical"] == "Antonio Ruiz"
    assert res["sealed"] is True


def test_propose_conflicting_draft_raises(store):
    """A second, different draft for one surface raises ConflictingDraftError."""
    r = EntityResolver(store, domain="person")
    r.propose("Tony", "Tony (b. 1972)")
    with pytest.raises(ConflictingDraftError):
        r.propose("Tony", "Antonio Garcia")


def test_propose_same_answer_is_idempotent(store):
    """Re-proposing the same answer is not a conflict."""
    r = EntityResolver(store, domain="person")
    first = r.propose("Tony", "Tony (b. 1972)")
    second = r.propose("Tony", "Tony (b. 1972)")
    assert first["pair_id"] == second["pair_id"]
    assert second["draft"] is True


def test_propose_carries_no_verifier(store):
    """A proposal has no verifier — that is the whole distinction from seal."""
    r = EntityResolver(store, domain="person")
    r.propose("Tony", "Tony (b. 1972)")
    res = r.resolve("Tony")
    # The draft has no verifier; provenance reflects draft state.
    assert res["sealed"] is False
    assert res["provenance"]["draft"] is True
