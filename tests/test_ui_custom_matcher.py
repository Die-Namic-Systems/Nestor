"""The surface, aimed at a domain that brought its own matcher (IDEAS §6.40).

`nestor ui` takes the domain's *tags* — `--source-lang`, `--target-lang` — and
for a long time that was all it took. A domain is not its tags; it is the tags
**and** the matcher that keys it, and a surface holding only half of that filed
every decision a human made under the process-wide default's key instead of the
domain's own.

The consequence was not an error. It was an HTTP 200, a real signature, a true
ledger entry, and a verification nobody could reach — which is the one failure
mode a hash chain cannot catch, because nothing was tampered with.

These tests are the measured table from §6.40, run as assertions. Each is
written so it fails on the *old* behaviour rather than merely passing on the
new: a test that only checks the row exists would have passed throughout.
"""
from __future__ import annotations

import os

import pytest

from nestor import cascade, memory, storage, ui
from nestor.sqlite_store import SqliteStore

DOMAIN = "incident"


class SerialMatcher:
    """The documented two-method seam, and nothing else.

    An incident report keys to the device serial it names, so two reports of one
    incident — worded nothing alike — are one key and one adjudication. It
    deliberately does NOT implement the optional `score(raw_a, raw_b)`: that is
    the variable §6.41 isolated, and a matcher that offers it never consults the
    key at all, so it would have survived the defect these tests pin and proven
    nothing.
    """

    name = "serial"

    def normalize(self, text: str) -> str:
        digits = "".join(ch for ch in str(text).upper() if ch.isalnum())
        marker = digits.find("CH")
        return digits[marker:marker + 6] if marker >= 0 else digits[:6]

    def similarity(self, a: str, b: str) -> float:
        return 1.0 if a and a == b else 0.0


SERIALS = SerialMatcher()

REPORT = "Pump SN CH-4471 over-delivered on the night run."
RESTATED = "CH4471 free-flow, ward 6, sister's report."
ADJUDICATION = "Free-flow on the giving set. Reportable under MDR Annex VII."
OTHER_EVENT = "Occlusion alarm on CH-4471, theatre 2."


@pytest.fixture()
def desk(tmp_path, seal_key):
    """A surface aimed at the incident domain, told the matcher that keys it."""
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return ui.App(store=store, source_lang=DOMAIN, target_lang=DOMAIN,
                  matcher=SERIALS, db_path=":memory:")


def post(app, path, **payload):
    return ui.dispatch(app, "POST", path, {}, payload)


def _draft(app, source=REPORT, target=ADJUDICATION):
    return memory.add_pair(source, target, DOMAIN, DOMAIN, status="draft",
                           store=app.store, matcher=SERIALS)


# ── the seal ────────────────────────────────────────────────────────────────

def test_sealing_a_draft_upgrades_that_row_rather_than_inserting_a_second(desk):
    """§6.40's first row: the draft and the seal must be one row.

    `add_pair` recomputes the key from `source_text`. With the wrong matcher the
    recomputed key misses the draft, so the write is an insert — two rows for one
    incident, and the human never sees a hint of it.
    """
    draft = _draft(desk)
    status, body = post(desk, "/api/seal-draft", pair_id=draft["id"], verifier="ines")
    assert status == 200
    assert body["pair"]["id"] == draft["id"], "sealing inserted a second row"
    assert body["pair"]["status"] == "sealed"

    rows = desk.store.memory_candidates(DOMAIN, DOMAIN)
    assert len(rows) == 1, f"one incident must be one row, found {len(rows)}"
    assert not [r for r in rows if r["status"] == "draft"], (
        "the draft she sealed is still queued")


def test_the_key_the_domain_computed_survives_the_seal(desk):
    draft = _draft(desk)
    _, body = post(desk, "/api/seal-draft", pair_id=draft["id"], verifier="ines")
    assert body["pair"]["source_norm"] == draft["source_norm"] == "CH4471"


def test_a_sealed_row_is_reachable_by_the_domain_that_drafted_it(desk):
    """The README's first promise — verified once, served forever."""
    draft = _draft(desk)
    post(desk, "/api/seal-draft", pair_id=draft["id"], verifier="ines")

    exact = memory.best_sealed(REPORT, DOMAIN, DOMAIN, store=desk.store, matcher=SERIALS)
    assert exact is not None, "the exact wording she sealed came back pending"

    restated = memory.best_sealed(RESTATED, DOMAIN, DOMAIN, store=desk.store,
                                  matcher=SERIALS)
    assert restated is not None, "the same incident, restated, came back pending"
    assert restated["pair"]["verifier"] == "ines"


def test_a_direct_seal_is_keyed_by_the_domains_matcher_too(desk):
    """`/api/seal` takes raw text rather than a draft id, and had the same defect."""
    status, body = post(desk, "/api/seal", source=REPORT, target=ADJUDICATION,
                        verifier="ines")
    assert status == 200
    assert body["pair"]["source_norm"] == "CH4471"


# ── the rejection ───────────────────────────────────────────────────────────

def test_a_rejection_recorded_through_the_ui_actually_suppresses(desk):
    """The README's second promise — a wrong match is never served again.

    A rejection is filed under the *query's* key and `best_sealed` looks it up
    under the domain's. Keyed by the default instead, the "no" is recorded,
    signed, and invisible.
    """
    memory.add_pair(REPORT, ADJUDICATION, DOMAIN, DOMAIN, status="sealed",
                    verifier="ines", store=desk.store, matcher=SERIALS)
    served = memory.best_sealed(OTHER_EVENT, DOMAIN, DOMAIN, store=desk.store,
                                matcher=SERIALS)
    assert served is not None, "fixture: the near miss must be served before the no"

    status, out = post(desk, "/api/reject-match", source=OTHER_EVENT,
                       target_text=ADJUDICATION, verifier="ines",
                       reason="Occlusion is not free-flow.")
    assert status == 200
    assert out["rejection"]["query_norm"] == SERIALS.normalize(OTHER_EVENT)

    after = memory.best_sealed(OTHER_EVENT, DOMAIN, DOMAIN, store=desk.store,
                               matcher=SERIALS)
    assert after is None, "the wrong match is served again after a recorded no"

    ids = memory.rejected_ids(SERIALS.normalize(OTHER_EVENT), DOMAIN, DOMAIN, desk.store)
    assert ids != (set(), set()), "the no is filed where the domain never asks"


# ── reads must agree with writes ────────────────────────────────────────────

def test_ask_uses_the_domains_matcher(desk):
    """A read keyed differently from the writes reports a sealed row as pending."""
    draft = _draft(desk)
    post(desk, "/api/seal-draft", pair_id=draft["id"], verifier="ines")
    status, out = post(desk, "/api/ask", text=RESTATED)
    assert status == 200
    assert out["verified"] is True, "the restated incident was not served as verified"
    assert out["passage"]["state"] == "sealed"


def test_match_scores_with_the_domains_matcher(desk):
    draft = _draft(desk)
    post(desk, "/api/seal-draft", pair_id=draft["id"], verifier="ines")
    status, out = post(desk, "/api/match", text=RESTATED)
    assert status == 200
    assert out["normalized"] == "CH4471"
    assert out["served"] is True
    assert out["matcher"] == "serial", "the report must name the matcher that scored it"


def test_match_refuses_to_score_a_different_named_matcher(desk):
    """Silently substituting would answer the only question Nestor is asked under
    a different notion of similarity than the one that sealed the row."""
    status, out = post(desk, "/api/match", text=REPORT, matcher="numeric")
    assert status == 400
    assert "keyed by 'serial'" in out["error"]
    assert "'numeric'" in out["error"]


def test_match_accepts_a_name_that_agrees_with_the_domains_matcher(desk):
    """A refusal is for a caller asking for something else, not for one asking
    for what is already in force. The first version of this refused any named
    matcher at all — which broke the browser, because the Match view's picker is
    a `<select>` that always sends a value."""
    status, out = post(desk, "/api/match", text=REPORT, matcher="serial")
    assert status == 200
    assert out["normalized"] == "CH4471"


def test_the_match_view_does_not_send_a_matcher_on_a_custom_domain():
    """The page's half of the same fix, pinned on the page source.

    `submitMatch` builds its body from a `<select>` that is only rendered when
    the surface has no matcher of its own; on a custom-matcher surface it shows
    the matcher's name instead and omits the field. A test at the API layer
    cannot catch a client that sends the wrong thing, which is exactly how this
    regression shipped.
    """
    from nestor import ui_page

    assert 'd.matcher_source === "app"' in ui_page.PAGE, (
        "the Match view must not offer a picker on a surface with its own matcher")
    assert "...(picker ? { matcher: picker.value } : {})" in ui_page.PAGE, (
        "submitMatch must omit `matcher` when there is no picker")


# ── the surface says which matcher it is using ──────────────────────────────

def test_state_reports_the_matcher_so_the_mismatch_is_visible(desk):
    """What made §6.40 invisible: two surfaces keyed differently described
    themselves identically, and nothing an operator could read said which one
    was filing their seals."""
    _, state = ui.dispatch(desk, "GET", "/api/state", {})
    assert state["domain"]["matcher"] == "serial"
    assert state["domain"]["matcher_source"] == "app"


def test_state_says_when_the_matcher_came_from_the_process(desk):
    plain = ui.App(store=desk.store, source_lang=DOMAIN, target_lang=DOMAIN)
    _, state = ui.dispatch(plain, "GET", "/api/state", {})
    assert state["domain"]["matcher_source"] == "process"
    assert state["domain"]["matcher"] == "StringMatcher"


# ── nothing changes for a surface that never had the problem ────────────────

def test_an_app_without_a_matcher_defers_to_the_process_wide_one(desk):
    """`None` means defer, not "use StringMatcher" — a host that installed one
    globally before launching the surface keeps what it set."""
    plain = ui.App(store=desk.store, source_lang=DOMAIN, target_lang=DOMAIN)
    was = memory.get_matcher()
    memory.set_matcher(SERIALS)
    try:
        draft = _draft(plain)
        _, body = post(plain, "/api/seal-draft", pair_id=draft["id"], verifier="ines")
        assert body["pair"]["id"] == draft["id"]
        assert body["pair"]["source_norm"] == "CH4471"
    finally:
        memory.set_matcher(was)


def test_two_desks_in_one_process_keep_their_own_keys(tmp_path, seal_key):
    """The sentence that used to have to be written down: two custom-matcher
    domains were two deployments, because the only rescue was a module global."""
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")

    class WordMatcher:
        name = "words"

        def normalize(self, text: str) -> str:
            return " ".join(sorted(str(text).lower().split()))

        def similarity(self, a: str, b: str) -> float:
            return 1.0 if a == b else 0.0

    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    incidents = ui.App(store=store, source_lang=DOMAIN, target_lang=DOMAIN,
                       matcher=SERIALS)
    notes = ui.App(store=store, source_lang="note", target_lang="note",
                   matcher=WordMatcher())

    a = memory.add_pair(REPORT, ADJUDICATION, DOMAIN, DOMAIN, status="draft",
                        store=store, matcher=SERIALS)
    b = memory.add_pair(REPORT, "a note about the same text", "note", "note",
                        status="draft", store=store, matcher=notes.matcher)

    _, sealed_a = post(incidents, "/api/seal-draft", pair_id=a["id"], verifier="ines")
    _, sealed_b = post(notes, "/api/seal-draft", pair_id=b["id"], verifier="ruaridh")

    assert sealed_a["pair"]["source_norm"] == "CH4471"
    assert sealed_b["pair"]["source_norm"] == notes.matcher.normalize(REPORT)
    assert sealed_a["pair"]["source_norm"] != sealed_b["pair"]["source_norm"], (
        "one process, two domains, and the same text keyed two different ways")
    assert memory.get_matcher() is not SERIALS, (
        "neither desk had to install its matcher process-wide")


# ── the App's matcher describes the App's domain and no other ───────────────
#
# Found by audit, after the first version of this fix shipped: `/api/reject-match`
# is shared by every recipe, and the Entity view rejects an alias through it
# carrying the *entity* domain — which `EntityResolver` keys with its own
# StringMatcher. Passing `app.matcher` there re-created §6.40 one recipe over:
# HTTP 200, a real signature, and a rejection filed where nothing looks it up.

def test_an_alias_rejection_is_not_keyed_by_the_incident_domains_matcher(desk):
    """The regression §6.40's own fix introduced."""
    from nestor.entity import EntityResolver

    resolver = EntityResolver(desk.store, domain="entity")
    resolver.seal("AWS", "Amazon Web Services", verifier="ines")
    assert resolver.resolve("AWS")["sealed"], "fixture: the alias must resolve first"

    status, out = post(desk, "/api/reject-match", source="AWS",
                       source_lang="entity", target_lang="entity",
                       target_text="Amazon Web Services", verifier="ines",
                       reason="Wrong expansion in this context.")
    assert status == 200
    # StringMatcher's key, which is what EntityResolver asks with — NOT
    # SerialMatcher's, which would be 'AWS' unchanged.
    assert out["rejection"]["query_norm"] == "aws", (
        "the alias rejection was keyed by the App's matcher, not the recipe's")
    assert not resolver.resolve("AWS")["sealed"], (
        "the recorded no did not suppress the alias — §6.40, one recipe over")


def test_a_seal_for_another_domain_does_not_borrow_the_apps_matcher(desk):
    """The Ask and Match views let a human retype the domain tags, so a request
    can be about a domain this App's matcher does not describe."""
    status, body = post(desk, "/api/seal", source="the annual invoice",
                        target="la factura anual", source_lang="en", target_lang="es",
                        verifier="ines")
    assert status == 200
    assert body["pair"]["source_norm"] == "the annual invoice", (
        "a seal in another domain was keyed by this App's matcher")


def test_the_apps_own_domain_still_gets_the_apps_matcher(desk):
    """The guard must not be so broad that it disables the fix."""
    status, body = post(desk, "/api/seal", source=REPORT, target=ADJUDICATION,
                        source_lang=DOMAIN, target_lang=DOMAIN, verifier="ines")
    assert status == 200
    assert body["pair"]["source_norm"] == "CH4471"


def test_ask_in_another_domain_is_not_scored_by_the_apps_matcher(desk):
    memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                    status="sealed", verifier="ines", store=desk.store)
    status, out = post(desk, "/api/ask", text="the annual invoice",
                       source_lang="en", target_lang="es")
    assert status == 200
    assert out["verified"] is True, (
        "a foreign-domain ask was scored with the incident matcher and missed")


# ── tier 2 keys with the domain's matcher too ───────────────────────────────

def test_the_offline_engine_drafts_in_a_custom_matcher_domain(desk):
    """Found by audit: the threading stopped at the tier-1 boundary.

    `Engine.translate` had no matcher parameter, so the shipped engines called
    `memory.lookup` with the process-wide one. In a custom domain the query's
    norm and each row's stored norm are then two unrelated key spaces, so the
    offline engine matched nothing: every unsealed query landed `pending` and
    never entered the review queue. Silently — a reviewer just sees an empty
    queue and concludes the machine had no opinion.
    """
    memory.add_pair("Pump SN CH-9002 stalled mid-infusion.",
                    "Motor stall, batch CH-9002, returned to Sheffield.",
                    DOMAIN, DOMAIN, status="draft", store=desk.store, matcher=SERIALS)
    status, out = post(desk, "/api/ask", text="CH9002 stall, ward 3.")
    assert status == 200
    assert out["passage"]["tier"] == 2, (
        f"tier 2 found nothing to draft: {out['passage']}")
    assert out["passage"]["state"] == "draft"
    assert "Motor stall" in out["passage"]["target"]


def test_an_engine_written_against_the_old_signature_still_works(desk):
    """The widening is tolerated the same way `store=` already was."""
    class LegacyEngine:
        name = "legacy"

        def translate(self, text, source_lang, target_lang):   # no store=, no matcher=
            from nestor.engine import Draft
            return Draft(text="from a legacy engine", engine=self.name, confidence=0.4)

    passage = cascade.translate_segment("anything at all", DOMAIN, DOMAIN,
                                        engine=LegacyEngine(), store=desk.store,
                                        matcher=SERIALS)
    assert passage.tier == 2
    assert passage.target == "from a legacy engine"
