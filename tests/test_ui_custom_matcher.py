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


def test_match_refuses_to_score_a_named_matcher_on_a_custom_domain(desk):
    """Silently substituting would answer the only question Nestor is asked under
    a different notion of similarity than the one that sealed the row."""
    status, out = post(desk, "/api/match", text=REPORT, matcher="numeric")
    assert status == 400
    assert "its own matcher" in out["error"]


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
