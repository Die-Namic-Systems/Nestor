"""The browser surface: the queue, the memory and the ledger, for a human.

These tests drive :func:`nestor.ui.dispatch` directly — it is pure over an
``App``, so the whole API is exercised without a socket. One test at the bottom
does start a real server on loopback, because the handler's own wiring
(headers, CSRF refusal, the page itself) is the part dispatch cannot cover.

What is pinned here is not "the endpoints return 200". It is that the UI cannot
launder a decision past the guards the library spent its design on: an empty
verifier is refused rather than recorded as unknown, a conflicting seal comes
back as a 409 the human must override deliberately, and --read-only means no
decision is recorded at all.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from nestor import cascade, memory, storage, ui
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_SEAL_KEY", "test-key")
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return ui.App(store=store, source_lang="en", target_lang="es", db_path=":memory:")


@pytest.fixture()
def filled(app):
    memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                    status="sealed", verifier="rita", store=app.store)
    memory.add_pair("a draft phrase", "una frase", "en", "es", store=app.store)
    return app


def get(app, path, **query):
    return ui.dispatch(app, "GET", path, query)


def post(app, path, **payload):
    return ui.dispatch(app, "POST", path, {}, payload)


def queued(app):
    return [seg for doc in get(app, "/api/queue")[1]["documents"] for seg in doc["segments"]]


def queue_a_segment(app, source="the monthly report", candidate="el informe mensual"):
    doc = app.store.create_document("a document", "en", "es")
    return doc, app.store.create_segment(doc["id"], 0, source, candidate, 0.8)


# --- what the page needs before it renders ---------------------------------

def test_state_reports_capabilities_counts_and_the_chain(filled):
    status, state = get(filled, "/api/state")
    assert status == 200
    assert state["capabilities"] == {"curation": True, "rejection": True, "queue": True}
    assert state["summary"]["sealed"] == 1 and state["summary"]["draft"] == 1
    assert state["signing_enabled"] is True
    assert state["ledger"]["ok"] is True
    assert state["read_only"] is False


def test_unknown_endpoint_is_a_404_not_a_traceback(app):
    status, out = get(app, "/api/nope")
    assert status == 404 and out["code"] == "not_found"


# --- browsing the memory ---------------------------------------------------

def test_pairs_list_filters_and_reports_servability(filled):
    assert get(filled, "/api/pairs")[1]["count"] == 2
    assert get(filled, "/api/pairs", status="sealed")[1]["count"] == 1
    assert get(filled, "/api/pairs", contains="invoice")[1]["count"] == 1
    rows = get(filled, "/api/pairs", status="sealed")[1]["pairs"]
    assert rows[0]["servable"] is True and rows[0]["signature_valid"] is True


def test_unverifiable_filter_surfaces_a_row_that_says_sealed_and_would_not_serve(app):
    app.store.memory_insert({
        "id": "forged-1", "source_text": "forged phrase",
        "source_norm": memory._norm("forged phrase"), "source_lang": "en",
        "target_text": "forjado", "target_lang": "es", "status": "sealed",
        "verifier": "mallory", "weight": 1.0, "origin": "", "created_at": "2026-01-01",
        "seal_sig": "",
    })
    rows = get(app, "/api/pairs", unverifiable="1")[1]["pairs"]
    assert [r["id"] for r in rows] == ["forged-1"]
    assert rows[0]["status"] == "sealed" and rows[0]["servable"] is False


def test_pair_detail_carries_provenance_and_every_rejection(filled):
    pair = get(filled, "/api/pairs", contains="invoice")[1]["pairs"][0]
    memory.reject_match("the annual invoices", "en", "es", pair_id=pair["id"],
                        verifier="rita", reason="different year", store=filled.store)
    status, out = get(filled, "/api/pair", id=pair["id"])
    assert status == 200 and out["pair"]["rejection_count"] == 1
    assert out["pair"]["rejections"][0]["verifier"] == "rita"
    assert get(filled, "/api/pair", id="nope")[0] == 404


# --- the decisions ---------------------------------------------------------

def test_a_decision_without_a_name_is_refused(filled):
    """An empty verifier is recorded as *unknown*, not as you — so it is asked for."""
    status, out = post(filled, "/api/seal", source="hello", target="hola")
    assert status == 400 and out["code"] == "verifier_required"
    assert get(filled, "/api/pairs", contains="hello")[1]["count"] == 0


def test_seal_serves_afterwards_and_lands_in_the_ledger(filled, tmp_path):
    status, _ = post(filled, "/api/seal", source="good evening", target="buenas noches",
                     verifier="rita")
    assert status == 200
    hit = memory.best_sealed("Good evening.", "en", "es", store=filled.store)
    assert hit and hit["pair"]["target_text"] == "buenas noches"
    kinds = [json.loads(x)["kind"]
             for x in (tmp_path / "ledger.jsonl").read_text().strip().split("\n")]
    assert "seal" in kinds, "a seal made in the UI is audited like any other"


def test_a_conflicting_seal_is_a_409_and_takes_a_deliberate_override(filled):
    status, out = post(filled, "/api/seal", source="the annual invoice",
                       target="otra cosa", verifier="sam")
    assert status == 409 and out["code"] == "conflicting_seal"
    assert "rita" in out["error"], "the human must see whose decision they are overruling"
    # The memory is untouched until the override is explicit.
    assert memory.best_sealed("the annual invoice", "en", "es",
                              store=filled.store)["pair"]["target_text"] == "la factura anual"

    status, _ = post(filled, "/api/seal", source="the annual invoice", target="otra cosa",
                     verifier="sam", override=True)
    assert status == 200
    assert memory.best_sealed("the annual invoice", "en", "es",
                              store=filled.store)["pair"]["target_text"] == "otra cosa"


def test_unseal_reject_and_restore_are_three_different_things(filled):
    pair = get(filled, "/api/pairs", contains="invoice")[1]["pairs"][0]

    assert post(filled, "/api/unseal", pair_id=pair["id"], verifier="rita",
                reason="stale")[1]["pair"]["status"] == "draft"
    assert memory.best_sealed("the annual invoice", "en", "es", store=filled.store) is None

    assert post(filled, "/api/reject-pair", pair_id=pair["id"], verifier="rita",
                reason="wrong")[1]["pair"]["status"] == "rejected"
    with pytest.raises(memory.RejectedPairError):
        memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                        status="sealed", verifier="rita", store=filled.store)

    assert post(filled, "/api/restore", pair_id=pair["id"], verifier="sam",
                reason="rita was mistaken")[1]["pair"]["status"] == "draft"


def test_reject_match_suppresses_one_query_and_leaves_the_seal_standing(filled):
    pair = get(filled, "/api/pairs", contains="invoice")[1]["pairs"][0]
    status, _ = post(filled, "/api/reject-match", source="the annual invoices",
                     source_lang="en", target_lang="es", pair_id=pair["id"],
                     target_text=pair["target_text"], verifier="rita",
                     reason="different year")
    assert status == 200
    assert memory.best_sealed("the annual invoices", "en", "es", store=filled.store) is None
    assert memory.best_sealed("the annual invoice", "en", "es", store=filled.store)


def test_unknown_pair_is_a_404(filled):
    assert post(filled, "/api/unseal", pair_id="nope", verifier="rita")[0] == 404


# --- the queue -------------------------------------------------------------

def test_queue_lists_pending_segments_under_their_document(app):
    doc, seg = queue_a_segment(app)
    status, out = get(app, "/api/queue")
    assert status == 200 and out["pending"] == 1
    assert out["documents"][0]["id"] == doc["id"]
    assert out["documents"][0]["segments"][0]["id"] == seg["id"]


def test_sealing_from_the_queue_serves_and_clears_the_item(app):
    """The accept side of the attention tax: a sealed segment must leave the queue."""
    _, seg = queue_a_segment(app)
    status, _ = post(app, "/api/queue/seal", segment_id=seg["id"], verifier="rita")
    assert status == 200
    assert memory.best_sealed("the monthly report", "en", "es", store=app.store)
    assert queued(app) == [], "a segment already sealed must not be offered for review again"
    assert app.store.get_segment(seg["id"])["status"] == "verified"


def test_rejecting_from_the_queue_clears_the_item_and_suppresses_the_candidate(app):
    _, seg = queue_a_segment(app)
    status, _ = post(app, "/api/queue/reject", segment_id=seg["id"], verifier="rita",
                     reason="mistranslation")
    assert status == 200
    assert queued(app) == []
    assert app.store.get_segment(seg["id"])["status"] == "rejected"
    # And the candidate is not offered for that source text again.
    memory.add_pair("the monthly report", "el informe mensual", "en", "es",
                    status="sealed", verifier="sam", store=app.store)
    assert memory.best_sealed("the monthly report", "en", "es", store=app.store) is None


def test_a_reviewer_can_correct_a_draft_before_sealing_it(app, tmp_path):
    """Review is usually 'nearly'. What gets sealed is the corrected text, and
    the ledger records that a human wrote it rather than accepting the draft."""
    _, seg = queue_a_segment(app, candidate="el reporte mensual")
    status, out = post(app, "/api/queue/seal", segment_id=seg["id"], verifier="rita",
                       target="el informe mensual")
    assert status == 200 and out["edited"] is True
    hit = memory.best_sealed("the monthly report", "en", "es", store=app.store)
    assert hit["pair"]["target_text"] == "el informe mensual"
    assert queued(app) == []

    entry = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines()
             if json.loads(x).get("kind") == "seal"][-1]
    assert entry["edited"] is True and entry["draft_sha"] == memory._sha("el reporte mensual")


def test_sealing_an_unchanged_candidate_is_still_the_plain_graduation_path(app):
    _, seg = queue_a_segment(app)
    status, out = post(app, "/api/queue/seal", segment_id=seg["id"], verifier="rita",
                       target="el informe mensual")
    assert status == 200 and out["edited"] is False


def test_queue_seal_on_an_unknown_segment_is_a_404(app):
    assert post(app, "/api/queue/seal", segment_id="nope", verifier="rita")[0] == 404


# --- asking ----------------------------------------------------------------

def test_ask_reports_the_state_and_the_candidates_behind_it(filled):
    status, out = post(filled, "/api/ask", text="the annual invoice")
    assert status == 200
    assert out["passage"]["state"] == "sealed" and out["passage"]["mark"] == "✓"
    assert out["passage"]["meta"]["verifier"] == "rita"
    assert out["matches"][0]["similarity"] == 1.0

    status, out = post(filled, "/api/ask", text="something never verified")
    assert out["passage"]["state"] == "pending" and out["passage"]["mark"] == "!"
    assert out["matches"] == []


def test_ask_with_nothing_to_ask_is_refused(filled):
    assert post(filled, "/api/ask", text="  ")[0] == 400


# --- the other recipes -----------------------------------------------------
#
# Translation is one instance of the mechanic, and the UI is not allowed to be
# translation-shaped. These drive the entity graph, the numeric reconciler and
# the bare seam through the same API, against the same memory.

def test_domains_lists_every_graph_in_the_store_without_guessing_the_recipe(filled):
    post(filled, "/api/entity/seal", surface="AMZN", canonical="Amazon",
         domain="company", verifier="analyst")
    post(filled, "/api/reconcile/seal", label="ceiling", value="$1,000,000",
         domain="contract", verifier="auditor")

    domains = {(d["source_lang"], d["target_lang"]): d["count"]
               for d in get(filled, "/api/domains")[1]["domains"]}
    assert domains[("en", "es")] == 2            # the translation memory
    assert domains[("company", "company")] == 1  # an entity graph
    assert domains[("ceiling", "contract")] == 1  # a numeric bucket, keyed by label


def test_entity_resolution_gives_the_same_three_answers(app):
    unknown = post(app, "/api/entity/resolve", surface="Amazon", domain="company")[1]
    assert unknown["canonical"] is None and unknown["sealed"] is False

    post(app, "/api/entity/seal", surface="Amazon.com Inc", canonical="Amazon",
         domain="company", verifier="analyst")

    sealed = post(app, "/api/entity/resolve", surface="amazon.com  inc.", domain="company")[1]
    assert sealed["canonical"] == "Amazon" and sealed["sealed"] is True
    assert sealed["provenance"]["verifier"] == "analyst"

    # Below the threshold the top candidate comes back as a suggestion to seal,
    # never as an answer.
    near = post(app, "/api/entity/resolve", surface="Amazon.com Incorporated",
                domain="company")[1]
    assert near["canonical"] is None and near["provenance"]["suggestion"] == "Amazon"


def test_entity_domains_stay_disjoint_through_the_api(app):
    post(app, "/api/entity/seal", surface="Apple", canonical="Apple Inc.",
         domain="company", verifier="a")
    post(app, "/api/entity/seal", surface="Tim", canonical="Tim Cook",
         domain="person", verifier="b")
    assert post(app, "/api/entity/resolve", surface="apple", domain="person")[1]["canonical"] is None
    assert post(app, "/api/entity/resolve", surface="apple", domain="company")[1]["canonical"] == "Apple Inc."


def test_two_analysts_disagreeing_about_an_alias_is_a_409(app):
    post(app, "/api/entity/seal", surface="AWS", canonical="Amazon",
         domain="company", verifier="analyst")
    status, out = post(app, "/api/entity/seal", surface="AWS", canonical="Amazon Web Services",
                       domain="company", verifier="other")
    assert status == 409 and out["code"] == "conflicting_seal"
    assert post(app, "/api/entity/resolve", surface="AWS", domain="company")[1]["canonical"] == "Amazon"

    status, _ = post(app, "/api/entity/seal", surface="AWS", canonical="Amazon Web Services",
                     domain="company", verifier="other", override=True)
    assert status == 200


def test_numeric_reconciliation_reports_variation_not_just_a_verdict(app):
    none_yet = post(app, "/api/reconcile/check", label="ceiling", observed="$900,000",
                    domain="contract")[1]
    assert none_yet["baseline"] is None and none_yet["flagged"] is False

    post(app, "/api/reconcile/seal", label="ceiling", value="$1,000,000",
         domain="contract", verifier="auditor")

    ok = post(app, "/api/reconcile/check", label="ceiling", observed="$1,030,000",
              domain="contract", pct_tol=0.05)[1]
    assert ok["within_tolerance"] is True and ok["flagged"] is False
    assert ok["variation"] == 30_000.0 and round(ok["variation_pct"], 3) == 0.03

    bad = post(app, "/api/reconcile/check", label="ceiling", observed="1250000",
               domain="contract", pct_tol=0.05)[1]
    assert bad["flagged"] is True and bad["variation"] == 250_000.0
    assert bad["ambiguous"] is False and [b["value"] for b in bad["baselines"]] == ["$1,000,000"]


def test_a_second_baseline_from_another_auditor_is_a_409(app):
    """The figure that would excuse the deviation cannot be added quietly."""
    post(app, "/api/reconcile/seal", label="ceiling", value="$1,000,000",
         domain="contract", verifier="auditor")
    status, out = post(app, "/api/reconcile/seal", label="ceiling", value="$1,250,000",
                       domain="contract", verifier="someone-else")
    assert status == 409 and out["code"] == "conflicting_seal"
    assert post(app, "/api/reconcile/check", label="ceiling", observed="$1,240,000",
                domain="contract")[1]["flagged"] is True


def test_match_is_the_bare_seam_over_any_domain(filled):
    hit = post(filled, "/api/match", text="THE ANNUAL INVOICE!!", source_lang="en",
               target_lang="es")[1]
    assert hit["served"] is True and hit["target"] == "la factura anual"
    assert hit["normalized"] == "the annual invoice", "the key the matcher reduced it to"

    post(filled, "/api/reconcile/seal", label="ceiling", value="1000000",
         domain="contract", verifier="auditor")
    numeric = post(filled, "/api/match", text="1,000,001", source_lang="ceiling",
                   target_lang="contract", matcher="numeric", pct_tol=0.05)[1]
    assert numeric["served"] is True, "inside the tolerance band the numeric matcher scores 1.0"
    assert post(filled, "/api/match", text="2,000,000", source_lang="ceiling",
                target_lang="contract", matcher="numeric", pct_tol=0.001)[1]["served"] is False


def test_an_unknown_matcher_is_refused_rather_than_defaulted(filled):
    status, out = post(filled, "/api/match", text="x", matcher="semantic")
    assert status == 400 and "custom one is injected in code" in out["error"]


def test_the_recipes_ask_who_is_sealing_too(app):
    assert post(app, "/api/entity/seal", surface="AMZN", canonical="Amazon",
                domain="company")[1]["code"] == "verifier_required"
    assert post(app, "/api/reconcile/seal", label="ceiling", value="1",
                domain="contract")[1]["code"] == "verifier_required"


# --- policy ----------------------------------------------------------------

def test_read_only_refuses_every_decision(filled):
    filled.read_only = True
    for path, payload in [("/api/seal", {"source": "a", "target": "b", "verifier": "rita"}),
                          ("/api/unseal", {"pair_id": "x", "verifier": "rita"}),
                          ("/api/ask", {"text": "the annual invoice"}),
                          ("/api/entity/seal", {"surface": "a", "canonical": "b",
                                                "verifier": "rita"}),
                          ("/api/reconcile/seal", {"label": "l", "value": "1",
                                                   "verifier": "rita"}),
                          ("/api/match", {"text": "the annual invoice"})]:
        status, out = ui.dispatch(filled, "POST", path, {}, payload)
        assert status == 403 and out["code"] == "read_only"
    # Reading still works, and nothing was written.
    assert get(filled, "/api/pairs")[1]["count"] == 2


def test_a_store_without_the_optional_capabilities_says_so(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_SEAL_KEY", "k")
    cascade.set_ledger_path(tmp_path / "l.jsonl")

    class _Legacy(SqliteStore):
        memory_list = None
        list_segments = None

    legacy = _Legacy(":memory:")
    legacy.init_db()
    app = ui.App(store=legacy)
    assert get(app, "/api/state")[1]["capabilities"] == {
        "curation": False, "rejection": True, "queue": False}
    assert get(app, "/api/pairs")[0] == 501
    assert get(app, "/api/queue")[0] == 501


# --- transport -------------------------------------------------------------

def test_csrf_refuses_a_cross_site_post_and_allows_the_page_itself():
    assert ui.csrf_reason("GET", {}, "127.0.0.1:8765") is None
    assert "X-Nestor-UI" in ui.csrf_reason("POST", {}, "127.0.0.1:8765")
    headers = {"X-Nestor-UI": "1", "Origin": "http://evil.example"}
    assert "does not match host" in ui.csrf_reason("POST", headers, "127.0.0.1:8765")
    headers = {"X-Nestor-UI": "1", "Origin": "http://127.0.0.1:8765"}
    assert ui.csrf_reason("POST", headers, "127.0.0.1:8765") is None


def test_the_page_is_self_contained():
    """No CDN, no fonts, no beacons — and no innerHTML for text a stranger wrote."""
    from nestor.ui_page import PAGE
    assert "http://" not in PAGE and "https://" not in PAGE
    assert "innerHTML =" not in PAGE and "insertAdjacentHTML" not in PAGE


def test_main_refuses_a_non_loopback_bind_without_an_explicit_flag(capsys):
    assert ui.main(["--host", "0.0.0.0", "--db", ":memory:"]) == 2
    assert "no authentication" in capsys.readouterr().err


def test_a_real_request_over_loopback(filled):
    """The handler's own wiring: the page, the headers, and a refused POST."""
    httpd = ui.serve(filled, "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/") as res:
            body = res.read().decode()
            assert res.headers["Content-Security-Policy"].startswith("default-src 'none'")
            assert "<title>Nestor</title>" in body

        with urllib.request.urlopen(base + "/api/state") as res:
            assert json.loads(res.read())["capabilities"]["curation"] is True

        # A POST without the UI's own header is refused, so another tab cannot
        # seal into this server.
        req = urllib.request.Request(base + "/api/seal", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req)
        assert exc.value.code == 403

        req = urllib.request.Request(
            base + "/api/seal",
            data=json.dumps({"source": "good evening", "target": "buenas noches",
                             "verifier": "rita"}).encode(),
            headers={"Content-Type": "application/json", "X-Nestor-UI": "1"})
        with urllib.request.urlopen(req) as res:
            assert res.status == 200
        assert memory.best_sealed("good evening", "en", "es", store=filled.store)
    finally:
        httpd.shutdown()
        httpd.server_close()
