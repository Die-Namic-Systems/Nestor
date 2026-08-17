"""The Graph tab (nestor ui) — a read-only view over the decision store.

nodes = decisions, edges = the four typed relations between them
(supersedes | refines | depends_on | contradicts). Everything here drives
:func:`nestor.ui.dispatch` directly, same as ``tests/test_ui.py`` — pure over
an :class:`~nestor.ui.App`, no socket needed except for the one test that pins
the served page and its headers.

What is pinned here is not "the endpoint returns 200". It is the covenant this
whole surface exists to hold: sealed and draft read as visibly different
things, a store this store never sealed cannot appear sealed here, and —
the adversarial half, per the testing skill — nothing reachable through this
surface can seal, write, or mutate anything, however the request is shaped.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from nestor import cascade, decision, memory, signing, storage, ui
from nestor.decision import DecisionMemory
from nestor.sqlite_store import SqliteStore


def get(app, path, **query):
    return ui.dispatch(app, "GET", path, query)


def post(app, path, **payload):
    return ui.dispatch(app, "POST", path, {}, payload)


@pytest.fixture()
def app(tmp_path, seal_key):
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return ui.App(store=store, source_lang="en", target_lang="es", db_path=":memory:")


# --- the shape of the data ---------------------------------------------------

def test_graph_is_empty_and_honest_on_a_fresh_store(app):
    """No decisions, no edges — {"nodes": [], "edges": []}, not a 404 or a 501.

    "Nothing to show" and "this failed" are different facts, and only one of
    them is true of an empty store.
    """
    status, out = get(app, "/api/graph")
    assert status == 200
    assert out == {"nodes": [], "edges": []}


def test_graph_reports_every_decision_as_a_node(app):
    dm = DecisionMemory(app.store)
    dm.propose("should the graph tab be read-only?", "yes — nodes and edges only")
    dm.seal("was the joke authored cold?", "yes — witnessed", "rita", seal_sig="")

    status, out = get(app, "/api/graph")
    assert status == 200
    assert len(out["nodes"]) == 2
    by_q = {n["question"]: n for n in out["nodes"]}
    draft = by_q["should the graph tab be read-only?"]
    sealed = by_q["was the joke authored cold?"]
    assert draft["status"] == "draft" and draft["verifier"] is None
    assert sealed["status"] == "sealed" and sealed["verifier"] == "rita"
    assert sealed["commitment"] == "yes — witnessed"
    # every node carries a distinct id and a display number
    assert len({n["id"] for n in out["nodes"]}) == 2
    assert {n["number"] for n in out["nodes"]} == {1, 2}


def test_graph_reports_edges_by_kind_sealed_or_merely_proposed(app):
    """Both a sealed and a proposed edge appear — /api/graph's contract has no
    ``sealed`` field on an edge, only ``source``/``target``/``kind``, so this
    only pins that BOTH show up as edges at all (constraints_on is the surface
    that separates sealed-fact from proposed for a single question; the graph
    view draws the whole thing)."""
    dm = DecisionMemory(app.store)
    a = dm.propose("A", "commit A")
    b = dm.propose("B", "commit B")
    c = dm.propose("C", "commit C")
    dm.propose_edge(a["id"], b["id"], "depends_on")
    # seal_edge, unlike seal(), never auto-signs — the caller (a human's
    # client, normally) always supplies the signature. NESTOR_SEAL_KEY is set
    # (the `seal_key` fixture) and no keyring is configured, so this is the
    # legacy shared-secret HMAC path: exactly what `_seal`'s server-side
    # auto-sign for plain pairs uses under the hood, just called explicitly.
    sig = signing.sign_edge(b["id"], c["id"], "refines", "rita")
    dm.seal_edge(b["id"], c["id"], "refines", "rita", sig)

    status, out = get(app, "/api/graph")
    assert status == 200
    kinds = {(e["source"], e["target"], e["kind"]) for e in out["edges"]}
    assert (a["id"], b["id"], "depends_on") in kinds
    assert (b["id"], c["id"], "refines") in kinds
    assert len(out["edges"]) == 2


def test_contradicts_edges_are_present_and_kind_labelled(app):
    """The one relation the spec calls out as needing to visually block —
    proven here only at the data layer (the CSS/Cytoscape styling that makes
    it look alarming is markup, not something this suite executes; see
    graphStylesheet in nestor/ui_page.py)."""
    dm = DecisionMemory(app.store)
    a = dm.propose("ship without a migration?", "no")
    b = dm.propose("ship without a migration, revisited", "yes, behind a flag")
    dm.propose_edge(a["id"], b["id"], "contradicts")

    out = get(app, "/api/graph")[1]
    assert out["edges"] == [{"source": a["id"], "target": b["id"], "kind": "contradicts"}]


def test_edges_outside_the_returned_node_set_are_dropped_not_passed_through(app):
    """An edge whose other end is not a decision-shaped domain this walk
    recognises must not ask the front end to draw a line to a node it was
    never sent."""
    dm = DecisionMemory(app.store)
    a = dm.propose("A", "commit A")
    # A second, non-"decision" domain that also rides the same tag on both
    # sides (the entity/numeric shape) — propose_edge only checks the id
    # exists via memory_get, not that it belongs to a decision domain.
    stray = memory.add_pair("ACME Corp", "ACME Corp", "entity", "entity", store=app.store)
    dm.propose_edge(a["id"], stray["id"], "depends_on")

    out = get(app, "/api/graph")[1]
    assert out["edges"] == []                     # the stray edge is dropped
    assert len(out["nodes"]) == 1                  # and the entity row is not a node


def test_multiple_decision_domains_all_appear(app):
    """decision:architecture and decision:governance both show — not only the
    unnamed default (nestor.decision's own docstring names this convention)."""
    DecisionMemory(app.store, domain="decision:architecture").propose("A?", "yes")
    DecisionMemory(app.store, domain="decision:governance").propose("G?", "no")
    DecisionMemory(app.store).propose("default?", "sure")

    out = get(app, "/api/graph")[1]
    assert len(out["nodes"]) == 3


def test_a_store_without_edge_support_still_shows_its_nodes(app, monkeypatch):
    """supports_edges(False) — the graph degrades to nodes-only, not a 501.

    Patched where it is actually READ: :meth:`DecisionMemory.all_edges` calls
    the ``supports_edges`` name bound into ``nestor.decision`` at import time
    (``from .storage import ... supports_edges``), which is a separate
    reference from ``nestor.storage.supports_edges`` — patching the latter
    would leave decision.py's own copy untouched and this test would pass
    for the wrong reason (not exercising the code path it claims to).
    """
    DecisionMemory(app.store).propose("A?", "yes")
    monkeypatch.setattr(decision, "supports_edges", lambda _store: False)

    status, out = get(app, "/api/graph")
    assert status == 200
    assert len(out["nodes"]) == 1
    assert out["edges"] == []


def test_entity_and_numeric_domains_never_leak_into_the_graph(app):
    """domain, domain is not sufficient to be a "decision" — EntityResolver and
    the numeric recipe use the same shape (nestor/entity.py, nestor/reconcile.py)."""
    memory.add_pair("ACME Corp", "ACME Corp", "entity", "entity", store=app.store)
    memory.add_pair("1000000", "1000000", "value", "value", store=app.store)
    DecisionMemory(app.store).propose("the only real decision", "yes")

    out = get(app, "/api/graph")[1]
    assert len(out["nodes"]) == 1
    assert out["nodes"][0]["question"] == "the only real decision"


# --- the refusal: read-only means read-only ---------------------------------

def test_graph_post_is_refused(app):
    """There is no mutating route at this path — POST /api/graph is a plain
    404, the same refusal any unregistered endpoint gets. Read-only here is
    not "writes are checked and denied" — it is "there is no write to make",
    which this test tries and fails to find a way around."""
    status, out = post(app, "/api/graph")
    assert status == 404
    assert out["code"] == "not_found"


def test_graph_query_and_payload_cannot_seal_or_forge_a_verifier(app):
    """Attempt the forbidden act: hand /api/graph the exact fields a seal
    would need (status, verifier, seal_sig, pair_id) and confirm the store
    is untouched — no row is created, no row's status moves, and the
    response never even looks at these fields (the handler takes no query
    parameters at all)."""
    dm = DecisionMemory(app.store)
    a = dm.propose("still just a draft?", "yes")
    before = app.store.memory_get(a["id"])

    status, out = get(
        app, "/api/graph",
        status="sealed", verifier="attacker", seal_sig="deadbeef",
        pair_id=a["id"], question="still just a draft?", commitment="forged",
    )
    assert status == 200                    # unknown query params are just ignored

    after = app.store.memory_get(a["id"])
    assert before == after                  # nothing moved
    assert after["status"] == "draft" and after["verifier"] == ""
    node = next(n for n in out["nodes"] if n["id"] == a["id"])
    assert node["status"] == "draft" and node["verifier"] is None


def test_graph_is_reachable_and_unmutating_under_read_only(app):
    app.read_only = True
    dm = DecisionMemory(app.store)
    dm.propose("A?", "yes")
    status, out = get(app, "/api/graph")
    assert status == 200 and len(out["nodes"]) == 1


# --- the served page ---------------------------------------------------------

def test_the_page_carries_the_graph_tab_and_the_vendored_library():
    from nestor.ui_page import PAGE
    assert '["graph",   "Graph"]' in PAGE
    assert "function viewGraph" in PAGE
    assert "cytoscape({" in PAGE
    assert '"/api/graph"' in PAGE
    # the vendored file's own version string, proof the bytes are really in there
    assert 'version="3.34.1"' in PAGE


def test_csp_header_is_unchanged_by_the_graph_view(app):
    """A regression test that the viewer did NOT loosen the CSP: pinned
    byte-for-byte, the exact string nestor/ui.py sends today. Vendoring a
    third-party library is exactly the kind of change that tempts a
    `script-src 'self'` or a CDN host onto this line — this fails the moment
    either happens."""
    httpd = ui.serve(app, "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/") as res:
            csp = res.headers["Content-Security-Policy"]
            assert csp == (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; "
                "img-src data:; base-uri 'none'")
            body = res.read().decode()
            assert "cytoscape" in body
            assert '<div id="graph-canvas">' not in body   # built by JS, not served statically

        with urllib.request.urlopen(base + "/api/graph") as res:
            out = json.loads(res.read())
            assert out == {"nodes": [], "edges": []}

        # And the refusal holds over the real socket too, not just dispatch().
        req = urllib.request.Request(
            base + "/api/graph", data=json.dumps({"status": "sealed"}).encode(),
            headers={"Content-Type": "application/json", "X-Nestor-UI": "1"})
        try:
            urllib.request.urlopen(req)
            assert False, "POST /api/graph should have been refused"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
