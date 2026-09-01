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
import os
import threading
import urllib.error
import urllib.request

import pytest

from nestor import cascade, memory, storage, ui
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def app(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
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


def test_seal_draft_seals_existing_row(filled):
    draft = memory.add_pair(
        "Phase 1 gate · G3 — test",
        "A) do thing\n---seal---\nA|DECISION G3: do thing\n---end---",
        "fleet-gap",
        "fleet-gap",
        status="draft",
        store=filled.store,
    )
    status, out = post(
        filled,
        "/api/seal-draft",
        pair_id=draft["id"],
        target="DECISION G3: do thing",
        verifier="rita",
    )
    assert status == 200
    row = filled.store.memory_get(draft["id"])
    assert row["status"] == "sealed"
    assert row["target_text"] == "DECISION G3: do thing"
    assert out["pair"]["id"] == draft["id"]


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
             if json.loads(x).get("kind") == "segment_sealed"][-1]
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
    status, out = post(filled, "/api/match", text="x", matcher="vector")
    assert status == 400 and "unknown matcher" in out["error"]


def test_semantic_without_extra_is_refused_not_defaulted(filled, without_fastembed):
    status, out = post(filled, "/api/match", text="x", matcher="semantic")
    assert status == 400
    assert "semantic" in out["error"].lower()
    assert "[semantic]" in out["error"] or "optional" in out["error"].lower()


@pytest.mark.semantic
def test_semantic_match_when_extra_installed(filled):
    from conftest import semantic_tests_enabled

    if not semantic_tests_enabled():
        pytest.skip("set NESTOR_SEMANTIC_TEST=1 and install the semantic extra")
    status, out = post(filled, "/api/match", text="hello", matcher="semantic")
    assert status == 200
    assert out["matcher"] == "semantic"


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


def test_a_store_without_the_optional_capabilities_says_so(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'k'
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


def _strip_js_literals(js: str) -> str:
    """Blank out strings, template literals, regexes-as-strings and comments.

    Crude on purpose: it only has to leave the delimiters that structure the
    code, so the balance check below can see them.
    """
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if c in "\"'`":
            quote, i = c, i + 1
            while i < n and js[i] != quote:
                i += 2 if js[i] == "\\" else 1
            i += 1
            out.append('""')
        elif js.startswith("//", i):
            while i < n and js[i] != "\n":
                i += 1
        elif js.startswith("/*", i):
            i = js.find("*/", i) + 2 or n
        else:
            out.append(c)
            i += 1
    return "".join(out)


def test_the_pages_javascript_is_structurally_balanced():
    """The page ships as a Python string, so nothing else ever parses it.

    A stray paren in it is invisible to every other test here and fatal in the
    browser — the whole page renders blank. This is the cheap standing guard;
    it caught exactly that.

    Scoped to the LAST ``<script>...</script>`` block — nestor's own app
    script — not the vendored Cytoscape.js ahead of it. That bundle is a
    separately pinned, checksummed third-party artifact
    (nestor/vendor/README.md), already valid JS by construction (it is
    exactly what npm ships), and its minified body contains regex literals
    that ``_strip_js_literals`` — which only knows string and comment
    delimiters, not the string/regex ambiguity around ``/`` in JS — cannot
    tell from a stray bracket. A false positive there would say nothing about
    a paren this project's own contributors typed, which is the one thing
    this guard exists to catch.
    """
    from nestor.ui_page import PAGE
    js = _strip_js_literals(PAGE.rsplit("<script>", 1)[1].rsplit("</script>", 1)[0])
    pairs = {")": "(", "]": "[", "}": "{"}
    stack, line = [], 1
    for ch in js:
        if ch == "\n":
            line += 1
        elif ch in "([{":
            stack.append((ch, line))
        elif ch in pairs:
            assert stack, f"unbalanced {ch!r} at line {line} of the page script"
            opener, opened = stack.pop()
            assert opener == pairs[ch], (
                f"{ch!r} at line {line} closes {opener!r} opened at line {opened}")
    assert not stack, f"unclosed {stack[-1][0]!r} from line {stack[-1][1]}"


def test_the_page_is_self_contained():
    """No CDN, no fonts, no beacons — and no innerHTML for text a stranger wrote.

    The vendored Cytoscape.js bundle (nestor/vendor/README.md — pinned,
    checksummed, its own license audited separately) is excluded from the
    URL-substring check below: its minified body carries a handful of inert
    ``/*! ... */`` attribution comments for code it bundles (a Promises/A+
    shim, two easing-function generators), each an ``http://`` URL in a
    comment, never fed to a request of any kind. What actually forbids this
    page fetching anything is the CSP (``default-src 'none'``, no ``self`` on
    script-src) pinned byte-for-byte in
    test_csp_header_is_unchanged_by_the_graph_view — this assertion is the
    cheap grep-level smoke test over NESTOR's OWN markup and script, not a
    substitute for that.
    """
    from nestor import ui_page
    own = ui_page.PAGE.replace(ui_page._read_vendor_script(), "")
    # One exception, and it is a link target rather than a resource: the origin
    # strip turns `owner/repo@sha:PR #n` into the pull request and commit a
    # reader can open. `FORGE_BASE` is split across a concatenation in
    # ui_pure.js precisely so this grep keeps its meaning — nothing here is
    # fetched, and the CSP still forbids fetching (test_csp_header_is_unchanged).
    own = own.replace('"https://" + "github.com/"', "")
    assert "http://" not in own and "https://" not in own
    assert "innerHTML =" not in ui_page.PAGE and "insertAdjacentHTML" not in ui_page.PAGE


def test_a_draft_is_ratified_in_place_from_the_detail_panel():
    """Ratifying a draft happens where the curator is looking.

    The first cut bolted a draft picker onto "Seal a pair by hand" — a dropdown
    plus a disabled copy of the question plus the answer, three views of one
    decision on a form built to create *new* pairs. Instead the detail panel of
    a plain draft edits the proposed answer and seals it in place via
    ``/api/seal-draft``; the hand-seal card is new-pairs-only again.
    """
    from nestor.ui_page import PAGE

    assert "function sealDraftInPlace" in PAGE
    assert "Seal this decision" in PAGE
    assert '"/api/seal-draft"' in PAGE
    # the picker and its helpers are gone
    assert "seal-draft-pick" not in PAGE
    assert "sealDraftCandidates" not in PAGE
    # submitSeal creates new pairs only — no draft branch
    hand = PAGE.split("async function submitSeal()", 1)[1].split(
        "\nasync function ", 1
    )[0]
    assert "sealDraftId" not in hand
    assert '"/api/seal"' in hand


def test_batch_seal_all_drafts_is_a_browser_key_affordance():
    """598 unsigned imports need one confirm + client signatures, not 598 dialogs."""
    from nestor.ui_page import PAGE

    assert "function batchSealAllDrafts" in PAGE
    assert "Seal all drafts" in PAGE
    assert "function fetchAllPlainDrafts" in PAGE


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


def test_sealing_by_hand_can_open_a_brand_new_domain(filled):
    """The hand-seal form is domain-generic: the API takes any pair of tags,
    and a graph that does not exist yet is created by sealing into it."""
    status, _ = post(filled, "/api/seal", source="SKU-4471-B", target="Widget, 4-inch",
                     source_lang="sku", target_lang="product", verifier="ops")
    assert status == 200
    domains = {(d["source_lang"], d["target_lang"]): d["count"]
               for d in get(filled, "/api/domains")[1]["domains"]}
    assert domains[("sku", "product")] == 1
    assert memory.best_sealed("sku-4471-b", "sku", "product", store=filled.store)
    # And it stays out of the translation memory it has nothing to do with.
    assert memory.best_sealed("SKU-4471-B", "en", "es", store=filled.store) is None


# --- Signals: what the memory says that no single row does ------------------

def test_pairs_paginate_past_the_first_page(app):
    """The Memory list stopped at 50 rows with nothing to say it had."""
    for i in range(60):
        memory.add_pair(f"clause {i}", f"cláusula {i}", "en", "es",
                        status="sealed", verifier="rita", store=app.store)

    first = get(app, "/api/pairs", limit="51")[1]["pairs"]
    assert len(first) == 51, "the page asks for one extra row to learn there is more"
    second = get(app, "/api/pairs", limit="51", offset="50")[1]["pairs"]
    assert len(second) == 10
    ids = {p["id"] for p in first[:50]}
    assert not (ids & {p["id"] for p in second}), "pages must not overlap"


def test_replaced_seals_has_a_view(filled):
    memory.add_pair("the annual invoice", "la factura del año", "en", "es",
                    status="sealed", verifier="sam", override_conflict=True,
                    store=filled.store)
    status, out = get(filled, "/api/replaced-seals")
    assert status == 200
    assert len(out["replaced"]) == 1
    entry = out["replaced"][0]
    assert entry["replaced_verifier"] == "rita" and entry["verifier"] == "sam"
    assert entry["same_verifier"] is False
    # Digests, not text: nestor.frank mirrors entries verbatim elsewhere.
    assert "la factura anual" not in json.dumps(entry)


def test_replaced_seals_hides_self_corrections_unless_asked(filled):
    memory.add_pair("the annual invoice", "la factura del año", "en", "es",
                    status="sealed", verifier="rita", store=filled.store)
    assert get(filled, "/api/replaced-seals")[1]["replaced"] == []
    assert len(get(filled, "/api/replaced-seals", all="1")[1]["replaced"]) == 1


def test_rejections_are_summarised_for_the_page(filled):
    for target in ("la factura anual", "una frase"):
        memory.reject_match("the yearly bill", "en", "es", target_text=target,
                            verifier="sam", reason="no", store=filled.store)
    status, out = get(filled, "/api/rejections")
    assert status == 200
    assert [q["query_norm"] for q in out["queries"]] == ["the yearly bill"]
    assert out["queries"][0]["rejections"] == 2


# --- staleness listing (§6.49) ---------------------------------------------

def test_due_for_reverification_returns_rows_for_aged_seals(filled):
    """A sealed pair older than the threshold shows up in the listing."""
    # The filled fixture sealed "the annual invoice" just now, so it is
    # 0 days old.  Ask for seals >= 0 days to include it.
    status, out = get(filled, "/api/due-for-reverification", older_than="0")
    assert status == 200
    assert out["chain_ok"] is True
    assert out["threshold_days"] == 0
    assert out["total"] >= 1
    assert len(out["rows"]) >= 1
    row = out["rows"][0]
    assert "pair_id" in row and "verifier" in row and "last" in row
    assert row["days"] >= 0
    assert isinstance(row["tail"], bool)


def test_due_for_reverification_older_than_filters(filled):
    """The default 90-day threshold excludes a just-sealed pair."""
    status, out = get(filled, "/api/due-for-reverification")
    assert status == 200
    assert out["chain_ok"] is True
    assert out["threshold_days"] == 90
    # The sealed pair was created moments ago — it must NOT appear at 90 days.
    assert out["rows"] == []
    assert out["total"] == 0


def test_due_for_reverification_respects_limit(filled):
    """The limit parameter caps the returned rows while total reflects all."""
    status, out = get(filled, "/api/due-for-reverification",
                      older_than="0", limit="1")
    assert status == 200
    assert len(out["rows"]) <= 1
    assert out["total"] >= len(out["rows"])


def test_due_for_reverification_survives_read_only(filled):
    """GET endpoints survive --read-only; this one must too."""
    filled.read_only = True
    status, out = get(filled, "/api/due-for-reverification", older_than="0")
    assert status == 200
    assert out["chain_ok"] is True


def test_the_numeric_check_tells_the_page_the_figure_was_half_read(filled):
    """The matcher searches for a number rather than requiring one, so a typo
    becomes a real figure. The page can only warn about it if the API says so."""
    post(filled, "/api/reconcile/seal", label="ceiling", value="$1,000,000",
         verifier="rita", domain="contract")
    status, out = post(filled, "/api/reconcile/check", label="ceiling",
                       observed="$1,00o,000", domain="contract")
    assert status == 200
    assert out["observed"] == 100.0 and out["observed_partial"] is True
    assert out["observed_text"] == "$1,00o,000"
    assert out["baseline_partial"] is False and out["flagged"] is True
