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


# -- carriage: a warrant crosses the instance boundary (IDEAS 1.10(c),
#    docs/warrants.md section 4) ---------------------------------------------
#
# The rule the memo settled on is stronger than "strip": import MAY carry a
# warrant, and may NEVER carry a conclusion about it. These gates hold both
# halves — the citation survives the trip (stripping would destroy the only
# warrant that survives leaving the room), and nothing that arrives is marked
# checked here, because there is no field that could mark it.

def _fresh_dest(tmp_path, name):
    """A second instance: its own store, its own ledger."""
    cascade.set_ledger_path(tmp_path / f"{name}.jsonl")
    dest = SqliteStore(":memory:")
    dest.memory_init()
    return dest


def test_a_citation_survives_an_export_import_round_trip(store, tmp_path):
    from nestor import portable
    pair = _draft(store, "who owns the arrears clause")
    warrant.attach(pair["id"], "citation", "Crossref",
                   "https://doi.org/10.1000/xyz", check="follow the DOI",
                   attached_by="agent-7", store=store)
    bundle = portable.export_bundle(store=store)
    assert bundle["nestor_bundle"] == 4
    assert bundle["counts"]["warrants"] == 1
    ok, detail = portable.verify_bundle(bundle)
    assert ok, detail
    assert "1 warrant(s)" in detail

    dest = _fresh_dest(tmp_path, "dest_citation")
    report = portable.import_bundle(bundle, store=dest, dry_run=False,
                                    verifier="sam")
    assert report["warrants"] == 1
    landed = [w for w in warrant.warrants_for(pair["id"], store=dest)
              if w["stored"]]
    assert len(landed) == 1
    assert landed[0]["authority"] == "Crossref"
    assert landed[0]["locator"] == "https://doi.org/10.1000/xyz"
    assert landed[0]["check"] == "follow the DOI"
    # The conclusion half: nothing that arrived says it was checked, and there
    # is no column that could say so. Asserted over the stored row's own keys
    # rather than over a list this test wrote, so a future column that DID hold
    # a verdict would fail here.
    assert not ({"verified", "verified_at", "verified_by", "holds", "confirmed"}
                & set(landed[0]))
    dest.close()


def test_a_construction_warrant_carries_its_recipe_and_no_verdict(store, tmp_path):
    from nestor import portable
    pair = _draft(store, "the scan makes no network calls")
    warrant.attach(pair["id"], "construction", "redential",
                   "npx redential scan --json", check="compare the merkle root",
                   expected_digest="ab" * 16, store=store)
    bundle = portable.export_bundle(store=store)
    dest = _fresh_dest(tmp_path, "dest_construction")
    portable.import_bundle(bundle, store=dest, dry_run=False, verifier="sam")
    landed = next(w for w in warrant.warrants_for(pair["id"], store=dest)
                  if w["stored"])
    # What the reader needs to run it themselves, intact: what to run, and what
    # it must produce. Nestor holds the recipe; it does not hold the verdict.
    assert landed["locator"] == "npx redential scan --json"
    assert landed["expected_digest"] == "ab" * 16
    dest.close()


def test_the_seal_does_not_travel_twice(store, tmp_path):
    """``warrants_for`` composes an attestation on read, and export must NOT
    put that composed row in the bundle: the seal already travels in ``pairs``
    WITH its signature. An unsigned second copy would be a forgeable path into
    a destination's 'a person here checked'."""
    from nestor import portable
    pair = _sealed(store, "sealed and cited")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    bundle = portable.export_bundle(store=store)
    assert [w["kind"] for w in bundle["warrants"]] == ["citation"]
    assert not any(w["kind"] == "attestation" for w in bundle["warrants"])
    # The seal itself is still carried, on the pair, where it is signed.
    assert bundle["pairs"][0]["status"] == "sealed"


def test_import_refuses_a_bundle_claiming_an_attestation_warrant(store, tmp_path):
    """The laundering case. Export cannot write this row; a hand-edited or
    hostile bundle can. Accepting it would let a file assert 'a person checked
    this' with no signature for the destination to check — which is exactly the
    power the seal is the only thing allowed to carry."""
    from nestor import portable
    pair = _draft(store, "trust me")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    bundle = portable.export_bundle(store=store)
    forged = dict(bundle["warrants"][0], id="forged-1", kind="attestation",
                  authority="rita")
    bundle["warrants"].append(forged)
    bundle["digest"] = portable.digest(bundle["pairs"], bundle["rejections"],
                                       bundle["evidence"], bundle["warrants"],
                                       version=bundle["nestor_bundle"])
    dest = _fresh_dest(tmp_path, "dest_forged")
    with pytest.warns(RuntimeWarning, match="warrant"):
        report = portable.import_bundle(bundle, store=dest, dry_run=False,
                                        verifier="sam")
    assert report["warrants"] == 1                      # the citation, and only it
    assert [r["kind"] for r in report["refused_warrants"]] == ["attestation"]
    assert "attestation is not a stored warrant" in \
        report["refused_warrants"][0]["reason"]
    kinds = {w["kind"] for w in warrant.warrants_for(pair["id"], store=dest)}
    assert kinds == {"citation"}                        # the pair is a draft there
    dest.close()


def test_import_refuses_the_same_rows_attach_refuses(store, tmp_path):
    """A rule enforced locally and not on the import path is not a rule. Both
    call ``warrant.refuse_reason``; this pins that they agree on the three
    cases most worth agreeing on."""
    from nestor import portable
    pair = _draft(store, "agreement")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    bundle = portable.export_bundle(store=store)
    good = bundle["warrants"][0]
    bundle["warrants"] += [
        dict(good, id="bad-kind", kind="vibes"),
        dict(good, id="bad-authority", authority="   "),
        dict(good, id="bad-construction", kind="construction",
             expected_digest=""),
    ]
    bundle["digest"] = portable.digest(bundle["pairs"], bundle["rejections"],
                                       bundle["evidence"], bundle["warrants"],
                                       version=bundle["nestor_bundle"])
    dest = _fresh_dest(tmp_path, "dest_rules")
    with pytest.warns(RuntimeWarning, match="refused"):
        report = portable.import_bundle(bundle, store=dest, dry_run=False,
                                        verifier="sam")
    assert report["warrants"] == 1
    assert {r["id"] for r in report["refused_warrants"]} == {
        "bad-kind", "bad-authority", "bad-construction"}
    # And each one is refused locally too, by the same function.
    for kind, authority, digest_ in (("vibes", "Crossref", ""),
                                     ("citation", "   ", ""),
                                     ("construction", "redential", "")):
        with pytest.raises(ValueError):
            warrant.attach(pair["id"], kind, authority, "somewhere",
                           expected_digest=digest_, store=store)
    dest.close()


def test_the_digest_covers_warrants_so_an_edit_is_caught(store):
    """A warrant is inside the v4 integrity digest, not bolted on beside it —
    the same gate evidence earned at v3."""
    from nestor import portable
    pair = _draft(store, "tamper")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/real",
                   store=store)
    bundle = portable.export_bundle(store=store)
    assert portable.verify_bundle(bundle)[0]
    bundle["warrants"][0]["locator"] = "https://doi.org/forged"
    ok, detail = portable.verify_bundle(bundle)
    assert not ok and "digest mismatch" in detail


def test_import_drops_a_warrant_naming_a_pair_the_bundle_does_not_carry(store,
                                                                       tmp_path):
    from nestor import portable
    pair = _draft(store, "carried")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    bundle = portable.export_bundle(store=store)
    bundle["warrants"][0]["pair_id"] = "ghost-pair-id-not-in-bundle"
    bundle["digest"] = portable.digest(bundle["pairs"], bundle["rejections"],
                                       bundle["evidence"], bundle["warrants"],
                                       version=bundle["nestor_bundle"])
    dest = _fresh_dest(tmp_path, "dest_dangling")
    report = portable.import_bundle(bundle, store=dest, dry_run=False,
                                    verifier="sam")
    assert report["warrants"] == 0
    assert report["dangling_warrants"] == ["ghost-pair-id-not-in-bundle"]
    dest.close()


def test_a_dry_run_import_reports_warrants_and_writes_none(store, tmp_path):
    from nestor import portable
    pair = _draft(store, "dry")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    bundle = portable.export_bundle(store=store)
    dest = _fresh_dest(tmp_path, "dest_dry")
    report = portable.import_bundle(bundle, store=dest, dry_run=True)
    assert report["warrants"] == 1
    assert warrant.warrants_for(pair["id"], store=dest) == []
    dest.close()


def test_a_version_3_bundle_still_verifies_after_the_bump(store):
    """The gate the v2->v3 bump earned, one version on: three bundles in this
    repository were written at 3, and a digest that fails on an untouched
    payload trains people to ignore it."""
    from nestor import portable
    pair = _draft(store, "legacy")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    bundle = portable.export_bundle(store=store)
    legacy = {k: v for k, v in bundle.items() if k != "warrants"}
    legacy["nestor_bundle"] = 3
    legacy["digest"] = portable.digest(bundle["pairs"], bundle["rejections"],
                                       bundle["evidence"], version=3)
    ok, detail = portable.verify_bundle(legacy)
    assert ok, detail
    assert "warrant(s)" not in detail


# -- IDEAS §1.10(a): what warrants change about SERVING, decision 0164 -------
#
# The answer recorded in 0164 is "pending stays". A warrant is said alongside
# the seal and never instead of it, so the whole of the change on this path is
# a display fact on a row that already won on its seal. The first two tests are
# the ones that matter: they pin what did NOT move.

def test_a_citation_changes_nothing_about_what_is_served(store):
    """§1.10(a), answered: a citation does not make a row servable.

    This is the laundering door, and it is why `pending` stays. A row warranted
    by Crossref and sealed by nobody has had no human *here* check it — the only
    question `sealed` answers and the only one tier 1 reads. Admitting it would
    let an agent that can attach a warrant promote its own draft, which is
    `nestor_propose` with extra steps.

    Asserted as a before/after on the same query rather than against a hardcoded
    state, because the state an unsealed row produces is tier 2's business and
    not this feature's: with the offline engine and a near TM row the cascade
    drafts, and the first version of this test asserted `pending` and caught
    that draft instead of the thing it was written to catch. What §1.10(a) turns
    on is that attaching the warrant moves *nothing* — whatever the cascade said
    before, it says exactly that after.
    """
    from nestor import cascade as cascade_mod
    q = "who owns the arrears clause"
    pair = _draft(store, q)
    before = cascade_mod.translate_segment(q, "decision", "decision", store=store)

    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/10.1000/xyz",
                   store=store)
    assert warrant.kinds_held(pair["id"], store=store) == {"citation"}
    after = cascade_mod.translate_segment(q, "decision", "decision", store=store)

    assert (after.state, after.tier, after.target) == \
           (before.state, before.tier, before.target)
    assert after.state != "sealed" and after.tier != 1
    assert memory.best_sealed(q, "decision", "decision", store=store) is None


def test_a_construction_warrant_does_not_promote_a_draft_either(store):
    """The same gate for the warrant that needs no authority at all. A recipe
    and a digest are checkable by anyone — and still by nobody here, yet."""
    pair = _draft(store, "the scan makes no network calls")
    warrant.attach(pair["id"], "construction", "redential", "npx redential scan",
                   expected_digest="ab" * 16, store=store)
    assert memory.best_sealed("the scan makes no network calls", "decision",
                              "decision", store=store) is None


def test_best_sealed_says_warranted_how_for_the_row_it_found(store):
    pair = _sealed(store, "arrears defined")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    hit = memory.best_sealed("arrears defined", "decision", "decision", store=store)
    assert hit["pair"]["id"] == pair["id"]
    # Sorted, and carrying the attestation composed from the seal: the same set
    # `kinds_held` reports everywhere else. A set that meant something narrower
    # on the serve path would be a second vocabulary for one fact.
    assert hit["warrant_kinds"] == ["attestation", "citation"]


def test_an_unwarranted_seal_still_serves_and_says_so_emptily(store):
    """No warrant beyond the seal is not a defect and must not read as one:
    `attestation` alone is a complete answer to "warranted how"."""
    pair = _sealed(store, "plainly sealed")
    hit = memory.best_sealed("plainly sealed", "decision", "decision", store=store)
    assert hit["pair"]["id"] == pair["id"]
    assert hit["warrant_kinds"] == ["attestation"]


def test_the_served_passage_carries_the_warrant_kinds(store):
    from nestor import cascade as cascade_mod
    pair = _sealed(store, "sealed and cited")
    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    passage = cascade_mod.translate_segment("sealed and cited", "decision",
                                            "decision", store=store)
    assert passage.state == "sealed"
    assert passage.meta["warrant_kinds"] == ["attestation", "citation"]
    # state is untouched — there is no fourth value, and `mark` still maps.
    assert passage.mark == "✓"


def test_the_ledger_records_what_the_answer_was_warranted_by_at_serve_time(store):
    """A warrant attached tomorrow is not one this answer went out with, and
    the trail is the only place that distinction survives."""
    from nestor import cascade as cascade_mod
    pair = _sealed(store, "warranted at serve time")
    cascade_mod.translate_segment("warranted at serve time", "decision",
                                  "decision", store=store)
    first = [e for e in ledger.entries(kind="passage")][-1]
    assert first["warrant_kinds"] == ["attestation"]

    warrant.attach(pair["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    cascade_mod.translate_segment("warranted at serve time", "decision",
                                  "decision", store=store)
    second = [e for e in ledger.entries(kind="passage")][-1]
    assert second["warrant_kinds"] == ["attestation", "citation"]
    # The earlier line did NOT acquire the citation retroactively.
    assert first["warrant_kinds"] == ["attestation"]


def test_a_warrant_lookup_that_raises_cannot_withhold_a_verified_answer(store,
                                                                        monkeypatch):
    """The annotation is commentary on a row that already won on its seal. If
    reading it fails, the answer still goes out — a serve path that can be
    broken by an optional relation is worse than one that says nothing about
    it."""
    pair = _sealed(store, "resilient")

    def boom(*a, **k):
        raise RuntimeError("the warrants table is on fire")
    monkeypatch.setattr(warrant, "kinds_held", boom)
    hit = memory.best_sealed("resilient", "decision", "decision", store=store)
    assert hit is not None and hit["pair"]["id"] == pair["id"]
    assert hit["warrant_kinds"] == []


def test_there_is_still_no_fourth_state(store):
    """The vocabulary is three words, and 0164 turned on it staying three."""
    from nestor.cascade import Passage
    assert set(Passage(source="", target="", tier=0, state="pending").mark) == {"!"}
    for state in ("sealed", "draft", "pending"):
        Passage(source="", target="", tier=0, state=state).mark      # noqa: B018 — verifying attribute access succeeds
    with pytest.raises(KeyError):
        Passage(source="", target="", tier=0, state="cited").mark  # noqa: B018 — verifying this raises


def test_a_pending_answer_can_say_a_candidate_is_cited(store):
    """The other half of §1.10(a), from docs/warrants.md §2: "the reader sees
    `pending`, and beside it 'cited to Crossref, unsealed here.'"

    Safe to say precisely because of what the payload already carried. A
    candidate's `target_text` has always been in `matches` — this annotation
    exposes nothing new — and it arrives beside `status` and `servable`, which
    have said "do not serve this" all along. What changes is that a reader can
    tell an unsealed row nobody vouched for from an unsealed row a named
    institution stands behind. Neither is servable.
    """
    from nestor import answer as answer_mod
    cited = _draft(store, "who owns the arrears clause", "clause 4")
    _draft(store, "who owns the arrears clauses", "clause 9")   # near, unwarranted
    warrant.attach(cited["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)

    result = answer_mod.ask(store, "who owns the arrears clause",
                            "decision", "decision")
    by_id = {m["id"]: m for m in result["matches"]}
    assert by_id[cited["id"]]["warrant_kinds"] == ["citation"]
    # And the verdict is untouched: nothing verified matched, and the cited row
    # is still not servable.
    assert result["verified"] is False
    assert by_id[cited["id"]]["servable"] is False
    assert by_id[cited["id"]]["status"] == "draft"


def test_an_unwarranted_candidate_is_distinguishable_from_a_cited_one(store):
    from nestor import answer as answer_mod
    cited = _draft(store, "arrears, cited", "clause 4")
    plain = _draft(store, "arrears, plain", "clause 4")
    warrant.attach(cited["id"], "citation", "Crossref", "https://doi.org/1",
                   store=store)
    result = answer_mod.ask(store, "arrears", "decision", "decision")
    by_id = {m["id"]: m for m in result["matches"]}
    assert by_id[cited["id"]]["warrant_kinds"] == ["citation"]
    assert by_id[plain["id"]]["warrant_kinds"] == []
    assert all(m["servable"] is False for m in result["matches"])


def test_the_older_one_argument_candidate_call_still_works(store):
    """`_candidate(m)` without a store predates this and is called that way in
    two other places; it must degrade to no annotation, never to a wrong one."""
    from nestor import answer as answer_mod
    pair = _draft(store, "no store passed")
    row = answer_mod._candidate({"pair": pair, "similarity": 1.0})
    assert "warrant_kinds" not in row
    assert row["servable"] is False
