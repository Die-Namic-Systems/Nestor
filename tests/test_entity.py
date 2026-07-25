
from nestor.entity import EntityResolver

from conftest import read_ledger


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
