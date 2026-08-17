"""The Triage tab (nestor ui) — nestor.triage, brought to the review desk.

Read-only, GET /api/triage only. This is the "what needs you" view over the
SERVED store's own decision-domain pairs (never the docs/dogfood/decisions/
files nestor.triage.load_decisions() reads — see nestor.ui._triage's
docstring): the same clustering/supersession organ scripts/decision_triage.py
already prints as text, called through nestor.triage.triage() unmodified, with
the ordering derived from the Report it returns rather than a new score.

Same discipline as tests/test_ui_graph.py, which this mirrors: what is pinned
here is not "the endpoint returns 200" but the covenant — proposed reads as
proposed, an entity/numeric domain never leaks in, and nothing reachable
through this surface can seal, write, or mutate anything, however the request
is shaped.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from nestor import cascade, memory, storage, ui
from nestor.decision import DecisionMemory
from nestor.sqlite_store import SqliteStore


def get(app, path, **query):
    return ui.dispatch(app, "GET", path, query)


def post(app, path, **payload):
    return ui.dispatch(app, "POST", path, {}, payload)


@pytest.fixture()
def app(tmp_path):
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return ui.App(store=store, source_lang="en", target_lang="es", db_path=":memory:")


def _seed_cluster_and_contradiction(store) -> None:
    """A near-duplicate pair (-> a multi-member cluster + supersedes) and a
    paraphrased pair with diverging commitments (-> a contradicts edge),
    scored and picked with nestor.matcher.StringMatcher directly (see the
    similarities pinned in the comments) so the fixture is not a guess about
    where the 0.55 bar falls.
    """
    dm = DecisionMemory(store)
    # question q-sim 0.93 >= 0.55, commitment sim >= 0.55 -> supersedes
    dm.propose("Should the seal use HMAC or ed25519?", "Use ed25519 for new keyrings.")
    dm.propose("Should the seal use HMAC or Ed25519 keys?",
               "Use ed25519 for new keyrings going forward.")
    # question q-sim 0.77 >= 0.55, commitment sim ~0.28 < 0.55 -> contradicts
    dm.propose("Should draft decisions in this store expire automatically after a "
              "time limit?",
              "No, drafts never expire; a human must seal them by hand eventually.")
    dm.propose("Should draft decisions automatically expire after some time limit?",
              "Yes, unsealed drafts get purged after ninety days without review.")
    # unrelated to both -> a singleton, last in the open ranking
    dm.propose("What log level does the ledger use?", "INFO by default.")


# --- the shape of the data ---------------------------------------------------

def test_triage_is_empty_and_honest_on_a_fresh_store(app):
    """No decisions -> every list empty, every count zero, not an error — the
    same "nothing to show" vs "this failed" distinction /api/graph makes."""
    status, out = get(app, "/api/triage")
    assert status == 200
    assert out["open"] == out["clusters"] == out["proposed_edges"] == []
    assert out["counts"] == {"decisions": 0, "groups": 0, "edges": 0,
                             "open": 0, "resolved": 0}
    assert out["bar"] == pytest.approx(0.55)


def test_triage_finds_a_cluster_and_a_contradiction(app):
    _seed_cluster_and_contradiction(app.store)
    status, out = get(app, "/api/triage")
    assert status == 200

    assert out["counts"]["decisions"] == 5
    multi = [c for c in out["clusters"] if len(c["member_ids"]) > 1]
    assert len(multi) == 2                      # the ed25519 pair and the expiry pair
    for c in multi:
        assert c["representative_id"] in c["member_ids"]
        assert c["label"]                        # never blank for a real cluster

    kinds = {e["kind"] for e in out["proposed_edges"]}
    assert kinds == {"supersedes", "contradicts"}
    contradiction = next(e for e in out["proposed_edges"] if e["kind"] == "contradicts")
    assert 0.0 <= contradiction["score"] <= 1.0

    # supersession resolves exactly its dst — that decision drops out of "open"
    supersession = next(e for e in out["proposed_edges"] if e["kind"] == "supersedes")
    open_ids = {row["id"] for row in out["open"]}
    assert supersession["dst_id"] not in open_ids
    assert supersession["src_id"] in open_ids
    assert out["counts"]["resolved"] == 1
    assert out["counts"]["open"] == 4


def test_ordering_puts_contradicts_and_clusters_ahead_of_singletons(app):
    """The ranked "what needs you" list: a decision touched by a contradicts
    proposal sorts first, a decision merely in a multi-member cluster sorts
    next, and a plain singleton — nothing proposed about it at all — sorts
    last. Derived from the Report's own edges/clusters, not a new score."""
    _seed_cluster_and_contradiction(app.store)
    out = get(app, "/api/triage")[1]

    contradiction = next(e for e in out["proposed_edges"] if e["kind"] == "contradicts")
    contradicted_ids = {contradiction["src_id"], contradiction["dst_id"]}
    clustered_ids = {mid for c in out["clusters"] if len(c["member_ids"]) > 1
                     for mid in c["member_ids"]}

    ranks = [row["id"] for row in out["open"]]
    # both contradiction endpoints are open (neither is a supersedes dst) and
    # must lead the list
    assert set(ranks[:2]) == contradicted_ids
    # the singleton (log level) trails everyone touched by a cluster or edge
    singleton_id = next(row["id"] for row in out["open"]
                        if row["question"].startswith("What log level"))
    assert ranks[-1] == singleton_id
    # every clustered-but-not-contradicted open id sits strictly between
    for mid in clustered_ids - contradicted_ids:
        if mid in ranks:
            assert ranks.index(mid) > ranks.index(next(iter(contradicted_ids)))
            assert ranks.index(mid) < ranks.index(singleton_id)


def test_open_rows_carry_a_stable_number_and_question(app):
    DecisionMemory(app.store).propose("only decision here", "yes")
    out = get(app, "/api/triage")[1]
    assert out["open"] == [{"id": out["open"][0]["id"], "number": 1,
                            "question": "only decision here", "status": "draft"}]


def test_multiple_decision_domains_all_appear(app):
    """decision:architecture and decision:governance both feed the same
    triage pass — not only the unnamed default (mirrors
    test_ui_graph.py::test_multiple_decision_domains_all_appear)."""
    DecisionMemory(app.store, domain="decision:architecture").propose("A?", "yes")
    DecisionMemory(app.store, domain="decision:governance").propose("G?", "no")
    DecisionMemory(app.store).propose("default?", "sure")

    out = get(app, "/api/triage")[1]
    assert out["counts"]["decisions"] == 3
    assert len(out["open"]) == 3


def test_entity_and_numeric_domains_never_leak_into_triage(app):
    """domain, domain is not sufficient to be a "decision" — reuses the exact
    _decision_domains selection the Graph tab uses (nestor/ui.py), asserted
    here at triage's own surface: an entity alias or a reconciled figure must
    never show up dressed as a question-and-commitment row."""
    memory.add_pair("ACME Corp", "ACME Corp", "entity", "entity", store=app.store)
    memory.add_pair("1000000", "1000000", "value", "value", store=app.store)
    DecisionMemory(app.store).propose("the only real decision", "yes")

    out = get(app, "/api/triage")[1]
    assert out["counts"]["decisions"] == 1
    assert out["open"][0]["question"] == "the only real decision"
    assert ui._decision_domains(app) == ["decision"]


def test_a_sealed_decision_reports_its_status(app):
    DecisionMemory(app.store).seal("sealed already?", "yes it is", "rita", seal_sig="")
    out = get(app, "/api/triage")[1]
    assert out["open"][0]["status"] == "sealed"


# --- the refusal: read-only means read-only ----------------------------------

def test_triage_post_is_refused(app):
    """No mutating route at this path — POST /api/triage is a plain 404, the
    same refusal any unregistered endpoint gets."""
    status, out = post(app, "/api/triage")
    assert status == 404
    assert out["code"] == "not_found"


def test_triage_writes_nothing_no_seal_no_verifier_no_edge(app):
    """The forbidden act, attempted: hand /api/triage the exact fields a seal
    or an edge-seal would need (status, verifier, seal_sig, pair_id, edge
    fields) via query params it never even reads, over a store that DOES
    produce a real proposed edge, and confirm the store is byte-for-byte
    unchanged — no row's status moves, no verifier is set, and no edge
    (proposed or sealed) is ever persisted where the store can see it, even
    though the response carries one as a computed ``ProposedEdge``."""
    _seed_cluster_and_contradiction(app.store)
    before = {row["id"]: dict(row) for row in DecisionMemory(app.store).all_decisions()}

    status, out = get(
        app, "/api/triage",
        status="sealed", verifier="attacker", seal_sig="deadbeef",
        src_id="x", dst_id="y", kind="supersedes", edge_sig="deadbeef",
    )
    assert status == 200                        # unknown query params are just ignored
    assert out["proposed_edges"]                 # the fixture does produce edges…

    after = {row["id"]: dict(row) for row in DecisionMemory(app.store).all_decisions()}
    assert before == after                       # …but nothing about the store moved
    assert all(r["status"] == "draft" and r["verifier"] == "" for r in after.values())
    assert memory.stats(store=app.store)["sealed"] == 0

    # No edge was ever persisted anywhere the store can see — the proposed
    # edges in the response are ProposedEdge dataclasses computed in memory,
    # never handed to DecisionMemory.propose_edge/seal_edge.
    for pid in after:
        assert app.store.memory_edges_from(pid) == []
        assert app.store.memory_edges_to(pid) == []


def test_triage_is_reachable_and_unmutating_under_read_only(app):
    app.read_only = True
    _seed_cluster_and_contradiction(app.store)
    status, out = get(app, "/api/triage")
    assert status == 200
    assert out["counts"]["decisions"] == 5


# --- the served page ----------------------------------------------------------

def test_the_page_carries_the_triage_tab(app):
    from nestor.ui_page import PAGE
    assert '["triage",  "Triage"]' in PAGE
    assert "function viewTriage" in PAGE
    assert '"/api/triage"' in PAGE
    # no confirm/reject/seal affordance is built for a proposal on this tab
    assert "seal-triage" not in PAGE
    assert "/api/triage/confirm" not in PAGE


def test_csp_and_page_are_unchanged_by_the_triage_view(app):
    """Live server, not just dispatch(): the CSP header nestor.ui sends is
    pinned byte-for-byte (same string tests/test_ui_graph.py pins for the
    Graph tab), and POST /api/triage is refused over the real socket too."""
    _seed_cluster_and_contradiction(app.store)
    httpd = ui.serve(app, "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/") as res:
            assert res.headers["Content-Security-Policy"] == (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; "
                "img-src data:; base-uri 'none'")

        with urllib.request.urlopen(base + "/api/triage") as res:
            out = json.loads(res.read())
            assert out["counts"]["decisions"] == 5
            assert out["bar"] == pytest.approx(0.55)

        req = urllib.request.Request(
            base + "/api/triage",
            data=json.dumps({"status": "sealed", "verifier": "attacker"}).encode(),
            headers={"Content-Type": "application/json", "X-Nestor-UI": "1"})
        try:
            urllib.request.urlopen(req)
            assert False, "POST /api/triage should have been refused"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
