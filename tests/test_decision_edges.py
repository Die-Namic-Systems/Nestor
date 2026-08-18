"""Gates for the decision graph (docs/decision-memory.md N6/N8).

Every test here exercises surface that did not exist before this change, so all
fail against ``HEAD~1`` for the trivial reason that ``nestor.decision`` and the
``decision_edges`` table are new. The ones that earn their place are the
adversarial guards, each attempting a forbidden act and asserting refusal:

* a machine-proposed (unsigned) edge does NOT constrain — only a sealed one is
  traversed as fact (the covenant, for edges);
* an edge signature that does not verify is surfaced, never traversed;
* a seal-domain signature cannot be replayed as an edge (domain separation);
* the machine cannot seal an edge — a public-only keyring can verify one and is
  structurally unable to sign it.
"""
from __future__ import annotations

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from nestor import cascade, keyring, ledger, signing, storage
from nestor.decision import DecisionMemory, EDGE_KINDS
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def ring(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    r = keyring.Keyring()
    keyring.set_keyring(r)
    yield r
    keyring.set_keyring(None)


@pytest.fixture()
def store(ring):
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    yield s
    s.close()


@pytest.fixture()
def sean(ring):
    """A public-only ed25519 verifier — the server can verify sean, never sign."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ring.add("sean", key=pub, kind="ed25519")
    return priv


def _sign_edge(priv, src_id, dst_id, kind):
    return priv.sign(signing._edge_message(src_id, dst_id, kind)).hex()


def _two_decisions(store):
    """A (genesis) and B, as rows the graph can relate. Draft is enough — the
    edge relates ids, not statuses."""
    dm = DecisionMemory(store)
    a = dm.propose("was the joke authored cold?", "yes — witnessed")
    b = dm.propose("may the machine seal its own work?", "no — author != witness")
    return dm, a["id"], b["id"]


# -- capability wiring -------------------------------------------------------

def test_sqlite_store_supports_edges(store):
    assert storage.supports_edges(store)


def test_bad_edge_kind_and_self_loop_are_refused(store):
    dm, a, b = _two_decisions(store)
    with pytest.raises(ValueError):
        dm.propose_edge(b, a, "grounds")          # not in EDGE_KINDS
    with pytest.raises(ValueError):
        dm.propose_edge(a, a, "depends_on")       # self loop
    assert "depends_on" in EDGE_KINDS


# -- the covenant: a proposed edge does not constrain ------------------------

def test_a_proposed_edge_is_surfaced_but_never_a_constraint(store):
    dm, a, b = _two_decisions(store)
    dm.propose_edge(b, a, "depends_on", reason="B depends on the genesis proof")

    on_a = dm.constraints_on("was the joke authored cold?")
    on_b = dm.constraints_on("may the machine seal its own work?")

    # Present in the graph, on both ends, but under `proposed` — not `constraints`.
    assert on_a["constraints"] == [] and on_b["constraints"] == []
    assert len(on_a["proposed"]) == 1 and len(on_b["proposed"]) == 1
    assert on_b["proposed"][0]["kind"] == "depends_on"
    assert on_b["proposed"][0]["direction"] == "out"


# -- a sealed edge does constrain --------------------------------------------

def test_a_sealed_edge_constrains_both_ends(store, sean):
    dm, a, b = _two_decisions(store)
    dm.propose_edge(b, a, "depends_on")
    sig = _sign_edge(sean, b, a, "depends_on")
    dm.seal_edge(b, a, "depends_on", "sean", sig)

    on_b = dm.constraints_on("may the machine seal its own work?")
    assert on_b["proposed"] == []
    assert len(on_b["constraints"]) == 1
    edge = on_b["constraints"][0]
    assert edge["kind"] == "depends_on" and edge["verifier"] == "sean"
    assert edge["other_commitment"] == "yes — witnessed"   # resolved A's text

    # and it shows on A as an inbound constraint
    on_a = dm.constraints_on("was the joke authored cold?")
    assert len(on_a["constraints"]) == 1
    assert on_a["constraints"][0]["direction"] == "in"


def test_seal_edge_is_ledgered_and_the_chain_verifies(store, sean):
    dm, a, b = _two_decisions(store)
    sig = _sign_edge(sean, b, a, "refines")
    dm.seal_edge(b, a, "refines", "sean", sig)
    assert ledger.entries(kind="edge_seal")     # the seal was ledgered
    ok, detail = ledger.verify()
    assert ok, detail


# -- forgery / tampering refused ---------------------------------------------

def test_seal_edge_refuses_a_signature_that_does_not_verify(store, sean):
    dm, a, b = _two_decisions(store)
    # a signature over DIFFERENT fields (wrong kind) must not ratify this edge
    wrong = _sign_edge(sean, b, a, "contradicts")
    with pytest.raises(ValueError):
        dm.seal_edge(b, a, "depends_on", "sean", wrong)


def test_a_tampered_sealed_edge_falls_out_of_constraints(store, sean):
    dm, a, b = _two_decisions(store)
    sig = _sign_edge(sean, b, a, "depends_on")
    dm.seal_edge(b, a, "depends_on", "sean", sig)
    # corrupt the stored signature directly, as a store-writer might
    with store._db() as conn:
        conn.execute("UPDATE decision_edges SET edge_sig=? WHERE src_id=?",
                     ("00" + sig[2:], b))
    on_b = dm.constraints_on("may the machine seal its own work?")
    assert on_b["constraints"] == []          # no longer traversed as fact
    assert len(on_b["proposed"]) == 1         # surfaced instead


def test_a_seal_signature_cannot_be_replayed_as_an_edge(store, sean):
    dm, a, b = _two_decisions(store)
    # sean signs a perfectly good SEAL message, then it is offered as an edge sig
    seal_sig = sean.sign(signing._message("may the machine seal its own work?",
                                           "no — author != witness", "sean")).hex()
    assert not signing.edge_is_valid(b, a, "depends_on", "sean", seal_sig)
    with pytest.raises(ValueError):
        dm.seal_edge(b, a, "depends_on", "sean", seal_sig)


def test_an_edge_signature_cannot_be_replayed_as_a_seal(store, sean):
    dm, a, b = _two_decisions(store)
    edge_sig = _sign_edge(sean, b, a, "depends_on")
    # the same bytes must not verify as a seal over any fields
    assert not signing.seal_is_valid(b, a, "sean", edge_sig)


# -- the machine cannot seal an edge -----------------------------------------

def test_a_public_only_instance_cannot_sign_an_edge(store, sean):
    dm, a, b = _two_decisions(store)
    # sean's private key never reached the keyring, so server-side signing raises
    with pytest.raises(Exception):
        signing.sign_edge(b, a, "depends_on", "sean")


def test_propose_edge_leaves_it_unsealed(store):
    dm, a, b = _two_decisions(store)
    edge = dm.propose_edge(b, a, "depends_on")
    assert edge["edge_sig"] == "" and edge["verifier"] == ""
    assert not signing.edge_is_valid(b, a, "depends_on", "", "")


# -- seal_edge refuses a relation nothing real backs -------------------------
# The forbidden acts, attempted with a VALID signature — a valid key does not
# buy the right to write a self-loop or an edge to a decision that does not
# exist. seal_edge must refuse both the way propose_edge already does (the
# security-review follow-up from the edge-confirmation ceremony).

def test_seal_edge_refuses_a_self_relation_even_with_a_valid_signature(store, sean):
    dm, a, b = _two_decisions(store)
    sig = _sign_edge(sean, a, a, "depends_on")     # a real signature over a->a
    with pytest.raises(ValueError, match="cannot relate to itself"):
        dm.seal_edge(a, a, "depends_on", "sean", sig)
    assert dm.all_edges([a]) == []                 # nothing written


def test_seal_edge_refuses_an_edge_to_a_decision_that_does_not_exist(store, sean):
    dm, a, b = _two_decisions(store)
    ghost = "00000000-0000-0000-0000-000000000000"
    sig = _sign_edge(sean, a, ghost, "depends_on")  # signature verifies over the ids
    assert signing.edge_is_valid(a, ghost, "depends_on", "sean", sig)  # the sig is real
    with pytest.raises(ValueError, match="no decision"):
        dm.seal_edge(a, ghost, "depends_on", "sean", sig)
    assert dm.all_edges([a, ghost]) == []          # no junk edge minted


def test_seal_edge_refuses_when_the_store_cannot_look_up_endpoints(store, sean):
    """supports_edges does not include memory_get, so a store can advertise the
    graph and lack it. Silently skipping the endpoint check then let a VALID
    signature seal an edge against ids nothing verifies (the fail-open the audit
    found). It now refuses — fail closed — the way evidence.attach does."""
    dm, a, b = _two_decisions(store)

    class NoGet:
        """Advertises the graph capability but hides memory_get."""
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            if name == "memory_get":
                raise AttributeError(name)
            return getattr(self._inner, name)

    blind = NoGet(store)
    assert storage.supports_edges(blind) is True           # it advertises edges
    dm2 = DecisionMemory(blind)
    sig = _sign_edge(sean, a, b, "depends_on")             # a real signature
    assert signing.edge_is_valid(a, b, "depends_on", "sean", sig)
    with pytest.raises(RuntimeError, match="memory_get"):
        dm2.seal_edge(a, b, "depends_on", "sean", sig)
    assert dm.all_edges([a, b]) == []                       # nothing sealed


# -- constraints_on carries the rest of the record ---------------------------

def test_constraints_on_reports_live_decision(store):
    dm, a, b = _two_decisions(store)
    on_b = dm.constraints_on("may the machine seal its own work?")
    assert on_b["live"]["commitment"] == "no — author != witness"
    assert on_b["live"]["sealed"] is False        # only proposed so far


# -- fuzzy constraints_on (§6.33/6.94/6.106) ---------------------------------

def test_exact_match_returns_exact(store):
    dm, _, _ = _two_decisions(store)
    result = dm.constraints_on("may the machine seal its own work?",
                               fuzzy_bar=0.45)
    assert result["match"] == "exact"
    assert result["similarity"] == 1.0
    assert result["live"]["commitment"] == "no — author != witness"


def test_fuzzy_match_finds_close_paraphrase(store):
    dm, _, _ = _two_decisions(store)
    result = dm.constraints_on("can the machine seal its own work?",
                               fuzzy_bar=0.45)
    assert result["match"] == "fuzzy"
    assert result["similarity"] >= 0.45
    assert result["live"]["commitment"] == "no — author != witness"
    assert result["live"]["matched_question"] == "may the machine seal its own work?"


def test_fuzzy_bar_none_falls_back_to_exact_only(store):
    dm, _, _ = _two_decisions(store)
    result = dm.constraints_on("can the machine seal its own work?",
                               fuzzy_bar=None)
    assert result["match"] == "none"
    assert result["live"] is None


def test_fuzzy_bar_on_instance_is_used_when_no_override(store):
    dm = DecisionMemory(store, fuzzy_bar=0.45)
    dm.propose("was the joke authored cold?", "yes — witnessed")
    dm.propose("may the machine seal its own work?", "no — author != witness")
    result = dm.constraints_on("can the machine seal its own work?")
    assert result["match"] == "fuzzy"
    assert result["live"]["commitment"] == "no — author != witness"


def test_fuzzy_match_too_distant_returns_none(store):
    dm, _, _ = _two_decisions(store)
    result = dm.constraints_on("how does the database handle transactions?",
                               fuzzy_bar=0.55)
    assert result["match"] == "none"
    assert result["live"] is None


def test_fuzzy_bar_zero_disables_fuzzy(store):
    dm = DecisionMemory(store, fuzzy_bar=0)
    dm.propose("was the joke authored cold?", "yes — witnessed")
    result = dm.constraints_on("was the joke authored cold or warm?")
    assert result["match"] == "none" or result["match"] == "exact"
