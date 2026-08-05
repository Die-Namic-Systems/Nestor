"""Regressions for the two findings of 2026-08-05, from feeding a session's own
decisions through Nestor (IDEAS §6.14).

Two rounds, and the second is the interesting one.

**Round one** — the first 19 tests, against the unfixed revision: 15 failed.
That is `tests/test_findings_2026_07_31.py`'s rule and the reason it exists — a
test that passes before the fix is a description, not a gate. The other four
passed before *and* after and are labelled **no-regression guards**, not gates:
a pair-bound rejection already travelled, a version-1 bundle already verified,
an unknown version was already refused, and export was already stable across
runs. They are here because the fix rewrites the path all four depend on. None
would have caught the defect, and none is offered as if it would.

**Round two** — the last 10 tests, from an adversarial audit of round one,
which found five defects it had introduced or left. 8 of the 10 fail against
round one's fix. They are grouped at the bottom under "the audit's finds", and
what they have in common is worth more than any of them individually: round one
tested the defect it had just understood, on single-row stores, and every miss
lived immediately outside that. The superseded pair, the second row type
sharing a limit, the tenth candidate, the other way of saying no.

One of round two's tests initially passed against the broken code because it
did not reproduce the condition it named — the forged row scored 1.0 and so sat
on the very display page the test claimed it fell off. The scores in it are
measured now, and asserted.

  A  a rejection naming no pair_id never travelled in a bundle
  B  `reopen_when` did not travel either, so not-yet arrived as never
  C  `nestor match` reported "N candidate(s) below THRESHOLD" whatever the
     actual reason, including for a row scoring 1.0000

A and B are one defect seen twice. `reject_match` documents two ways to name
what is refused — `pair_id`, or `target_text` for "a raw engine draft with no
pair yet" — and treats both as first-class, signed and ledgered. Export reached
rejections only by walking `memory_rejections_for_pair()` over the exported
pairs, so the pair-less half was dropped in silence. It lands hardest on
decision memory, where a rejected *alternative* usually never became a pair.
That is §1.6–§1.8's shape in the transfer path: a guarantee held at one call
site, and a second kind of row that never reaches it.

C is §1.9's shape in a message rather than a query — the code answering a
narrower question than the one it was asked, and reporting the narrow answer as
the whole one.
"""
from __future__ import annotations

import hashlib
import json
import warnings

import pytest

from nestor import answer, memory, portable, storage


def _reject(store, question, alternative, reason="", reopen_when="", pair_id=""):
    return memory.reject_match(question, "decision", "decision", pair_id=pair_id,
                               target_text=alternative, verifier="rita",
                               reason=reason, reopen_when=reopen_when, store=store)


def _decision(store, question, commitment, status="draft"):
    return memory.add_pair(question, commitment, "decision", "decision",
                           status=status, verifier="rita" if status == "sealed" else "",
                           store=store)


# ---------------------------------------------------------------- A + B ----

class TestARejectionThatNamesNoPairStillTravels:
    """The finding: a signed, ledgered 'no' vanished at the instance boundary."""

    def test_pair_less_rejection_is_in_the_bundle(self, store):
        _decision(store, "which gate catches a rogue engine?", "an AST walk")
        _reject(store, "which gate catches a rogue engine?", "a regex over the source",
                reason="it flagged the phrase inside a docstring about the rule")

        bundle = portable.export_bundle(store)
        assert bundle["counts"]["rejections"] == 1, (
            "a rejection recorded against a raw candidate (no pair_id) did not travel — "
            "export walked pairs, and this row has no pair to be walked from")
        assert bundle["rejections"][0]["target_text"] == "a regex over the source"

    def test_pair_bound_rejection_still_travels(self, store):
        """The half that already worked must keep working — the fix replaces the
        pair-keyed walk, so this is the row most at risk from the change."""
        pair = _decision(store, "should the rule be a parameter?", "no")
        _reject(store, "should the rule be a parameter?", "yes, with a default",
                pair_id=pair["id"], reason="the only reason to make it optional "
                                           "would be to turn it off")
        bundle = portable.export_bundle(store)
        assert bundle["counts"]["rejections"] == 1
        assert bundle["rejections"][0]["pair_id"] == pair["id"]

    def test_both_kinds_travel_together_and_are_not_double_counted(self, store):
        pair = _decision(store, "q", "a")
        _reject(store, "q", "bound alternative", pair_id=pair["id"])
        _reject(store, "q", "free alternative")
        bundle = portable.export_bundle(store)
        assert bundle["counts"]["rejections"] == 2
        assert {r["target_text"] for r in bundle["rejections"]} == {
            "bound alternative", "free alternative"}

    def test_export_is_stable_across_runs(self, store):
        """Two exports of one store must agree, or the digest is not an integrity
        check. The domain walk orders by created_at then id for exactly this."""
        pair = _decision(store, "q", "a")
        _reject(store, "q", "one", pair_id=pair["id"])
        _reject(store, "q", "two")
        _reject(store, "q", "three")
        assert portable.export_bundle(store)["digest"] == \
               portable.export_bundle(store)["digest"]


class TestBNotYetDoesNotArriveAsNever:
    """`reopen_when` is N5's whole point: empty is never, non-empty is not-yet."""

    def test_reopen_when_survives_export_and_import(self, store, tmp_path):
        _decision(store, "should CLAUDE_MODEL change?", "not in this work")
        _reject(store, "should CLAUDE_MODEL change?", "bump it to the next model",
                reason="out of scope, and thinking-on-by-default caps output",
                reopen_when="the operator decides to migrate the engine model")

        bundle = portable.export_bundle(store)
        assert bundle["rejections"][0]["reopen_when"], (
            "reopen_when was dropped from the bundle — a deferral crossed the "
            "boundary as a permanent refusal, which is the one distinction the "
            "column exists to preserve")

        from nestor.sqlite_store import SqliteStore
        other = SqliteStore(str(tmp_path / "other.db"))
        other.init_db()
        other.memory_init()
        storage.set_store(other)
        portable.import_bundle(bundle, store=other, dry_run=False, verifier="rita")

        landed = other.memory_list_rejections(limit=10)
        assert len(landed) == 1
        assert landed[0]["reopen_when"] == \
               "the operator decides to migrate the engine model"

    def test_reopen_when_is_in_the_field_set(self):
        assert "reopen_when" in portable.REJECTION_FIELDS


class TestTheVersionBumpDoesNotOrphanOlderBundles:
    """Adding a field changes the payload the digest is taken over. A build that
    hashes an old bundle with new fields reports a mismatch on a file nobody
    touched — the failure `_canonical` already exists to prevent."""

    def test_a_version_1_bundle_still_verifies(self):
        # Built by hand, and hashed the way version 1 hashed it — computed here
        # rather than by calling portable.digest(), so this test would still
        # catch the code deciding every bundle is version 2.
        pairs = [{"id": "p1", "source_text": "q", "source_norm": "q",
                  "source_lang": "d", "target_lang": "d", "target_text": "a",
                  "status": "draft", "verifier": "", "weight": 1.0, "origin": "",
                  "created_at": "2026-01-01T00:00:00+00:00", "seal_sig": ""}]
        rejections = [{"id": "r1", "query_norm": "q", "source_lang": "d",
                       "target_lang": "d", "pair_id": "", "target_text": "no",
                       "verifier": "rita", "reason": "because",
                       "created_at": "2026-01-01T00:00:00+00:00", "reject_sig": ""}]
        v1_rejection_fields = ("id", "query_norm", "source_lang", "target_lang",
                               "pair_id", "target_text", "verifier", "reason",
                               "created_at", "reject_sig")

        def rows(raw, fields):
            return sorted(({f: portable._canonical(r.get(f)) for f in fields}
                           for r in raw), key=lambda r: r.get("id", ""))

        payload = json.dumps(
            {"pairs": rows(pairs, portable.PAIR_FIELDS),
             "rejections": rows(rejections, v1_rejection_fields)},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        bundle = {"nestor_bundle": 1, "pairs": pairs, "rejections": rejections,
                  "digest": hashlib.sha256(payload.encode("utf-8")).hexdigest()}

        ok, detail = portable.verify_bundle(bundle)
        assert ok, f"a version-1 bundle stopped verifying after the bump: {detail}"

    def test_the_current_build_writes_the_new_version(self, store):
        _decision(store, "q", "a")
        assert portable.export_bundle(store)["nestor_bundle"] == 2
        assert portable.BUNDLE_VERSION == 2
        assert set(portable.SUPPORTED_BUNDLE_VERSIONS) == {1, 2}

    def test_an_unknown_version_is_still_refused(self):
        ok, detail = portable.verify_bundle({"nestor_bundle": 99, "pairs": [],
                                             "rejections": []})
        assert not ok and "unsupported bundle version" in detail


class TestWideningACapabilityMustNotSwitchOneOff:
    """`_REJECTION_OPS` is all-or-nothing, so a fourth entry would report every
    host store implementing the existing three as having NO rejection capability
    — turning a bug about short bundles into `reject_match` raising on stores
    that work today. Hence a separate predicate."""

    class _NoListing:
        """Curation and all three rejection ops; no domain listing."""

        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            if name == "memory_list_rejections":
                raise AttributeError(name)
            return getattr(self._inner, name)

    def test_a_three_op_store_still_supports_rejection(self, store):
        legacy = self._NoListing(store)
        assert storage.supports_rejection(legacy), (
            "adding the listing op to _REJECTION_OPS would disable rejection "
            "entirely for stores that record and read it perfectly well")
        assert storage.supports_curation(legacy)
        assert not storage.supports_rejection_listing(legacy)

    def test_sqlite_store_supports_listing(self, store):
        assert storage.supports_rejection_listing(store)

    def test_a_store_without_listing_exports_but_says_so(self, store):
        pair = _decision(store, "q", "a")
        _reject(store, "q", "bound", pair_id=pair["id"])
        _reject(store, "q", "free")
        legacy = self._NoListing(store)

        with pytest.warns(RuntimeWarning, match="cannot list rejections by domain"):
            bundle = portable.export_bundle(legacy)
        # It still carries what it can reach — degraded, not broken, and loud.
        assert bundle["counts"]["rejections"] == 1
        assert bundle["rejections"][0]["target_text"] == "bound"


# -------------------------------------------------------------------- C ----

class TestCTheReasonIsTheRealReason:
    """`best_sealed` can decline a row for five reasons. The surface named one
    of them unconditionally, and could be wrong twice in one sentence."""

    def test_an_exact_match_on_a_draft_does_not_claim_it_was_below_threshold(self, store):
        _decision(store, "should the rule be a parameter?", "no")
        result = answer.match(store, "should the rule be a parameter?",
                              "decision", "decision")
        assert not result["served"]
        assert result["matches"][0]["similarity"] == 1.0
        assert "below" not in result["reason"], (
            f"a row scoring 1.0 was reported as below the threshold: "
            f"{result['reason']!r}")
        # Not `"sealed" in reason` — that is a substring of "unsealed" and
        # "nothing sealed" and would pass for almost any wrong message.
        assert "nothing sealed" in result["reason"]
        # Reworded 2026-08-05 with the branch itself. This assertion used to
        # read "the best candidate is draft", pinning a phrase that was wrong:
        # the value it names is the set of statuses across EVERY row above the
        # bar, not the best one's. The test passed because it agreed with the
        # sentence, not because the sentence was right.
        assert "above the bar there is only draft" in result["reason"]
        assert "1.0" in result["reason"], "the score it did match should be quoted"

    def test_a_genuine_near_miss_says_below_threshold_with_the_real_score(self, store):
        _decision(store, "which layer owns the voice rule?", "the tier")
        result = answer.match(store, "who owns the voice rule, the class?",
                              "decision", "decision")
        assert not result["served"]
        # The number quoted must be the closest candidate's, not a count — and
        # not the threshold, which also appears in the sentence. Pin the whole
        # clause so a similarity that happened to equal 0.92 could not pass on
        # the threshold text alone.
        closest = result["matches"][0]["similarity"]
        assert closest < result["threshold"]
        assert f"is {closest}, below {result['threshold']}" in result["reason"]

    def test_an_empty_domain_says_so(self, store):
        result = answer.match(store, "anything", "nosuch", "nosuch")
        assert not result["served"]
        assert "nothing in this domain" in result["reason"]

    def test_a_suppressed_candidate_is_not_reported_as_absent(self, store, seal_key):
        """`lookup` drops rejected rows before scoring, so 'nothing matched' would
        hide the very record that decided the question."""
        pair = _decision(store, "suppressed question", "an answer", status="sealed")
        memory.reject_match("suppressed question", "decision", "decision",
                            pair_id=pair["id"], verifier="rita",
                            reason="wrong register", store=store)
        result = answer.match(store, "suppressed question", "decision", "decision")
        assert not result["served"]
        assert "recorded rejection" in result["reason"]
        assert "nothing in this domain" not in result["reason"]

    def test_a_forged_seal_is_named_as_one(self, store, seal_key):
        _decision(store, "forged question", "forged answer", status="sealed")
        row = store.memory_list(source_lang="decision", limit=5)[0]
        with store._db() as conn:
            conn.execute("UPDATE tm_pairs SET seal_sig=? WHERE id=?",
                         ("deadbeef" * 8, row["id"]))
        result = answer.match(store, "forged question", "decision", "decision")
        assert not result["served"]
        assert "does not verify" in result["reason"]

    def test_a_served_answer_carries_no_reason(self, store, seal_key):
        """The reason must never contradict the verdict."""
        _decision(store, "served question", "served answer", status="sealed")
        result = answer.match(store, "served question", "decision", "decision")
        assert result["served"]
        assert result["reason"] == ""

    def test_the_cli_prints_the_reason(self, store, capsys):
        """The finding was on a review surface, so the surface is what is pinned."""
        from nestor import cli
        _decision(store, "a question nobody sealed", "a commitment")
        # --db, not storage.set_store: the CLI builds its own store from the
        # flag. Setting the global instead silently reads data/nestor.db, which
        # is how the first version of this test "passed" against the wrong rows.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            code = cli.main(["--db", store.db_path, "match", "a question nobody sealed",
                             "--from", "decision", "--to", "decision"])
        out = capsys.readouterr().out
        assert code != 0
        assert "would not be served" in out
        assert "candidate(s) below" not in out, (
            "the CLI is still printing the old unconditional message")
        assert "draft" in out


# ------------------------------------------------------ the audit's finds ----
#
# An adversarial audit of the first fix found five defects the tests above did
# not cover. Each one below reproduces a case the auditor drove by hand; every
# one of them fails against that first fix and passes against this one. The
# lesson generalizing across them: the first pass tested the defect it had just
# understood, on single-row stores, and every miss lived just outside that.

class TestTheDomainWalkMustNotWidenWhatTravels:
    """The pair-keyed walk was scoped by the exported pairs — which exclude
    superseded rows — and the domain walk inherited no such scope."""

    def test_a_rejection_naming_a_superseded_pair_does_not_travel(self, store, seal_key):
        old = memory.add_pair("policy question", "policy v1", "decision", "decision",
                              status="sealed", verifier="rita", store=store)
        memory.supersede_pair("policy question", "policy v2", "decision", "decision",
                              verifier="rita", reason="v1 was wrong", store=store)
        _reject(store, "policy question", "policy v1", pair_id=old["id"],
                reason="superseded")

        bundle = portable.export_bundle(store)
        exported = {p["id"] for p in bundle["pairs"]}
        assert old["id"] not in exported, "superseded pairs are history, not stock"
        dangling = [r for r in bundle["rejections"]
                    if r["pair_id"] and r["pair_id"] not in exported]
        assert not dangling, (
            "a rejection travelled naming a pair this bundle does not carry. On a "
            "destination still holding that id live, importing it suppresses a "
            "sealed, signature-verified answer while the successor pair is refused "
            "as a conflict — the destination loses an answer and gains nothing")

    def test_a_bundle_never_references_a_pair_it_does_not_carry(self, store):
        """The invariant, stated once so it holds for cases nobody enumerated."""
        keep = _decision(store, "kept", "a")
        _reject(store, "kept", "no", pair_id=keep["id"])
        _reject(store, "kept", "free-standing no")
        _reject(store, "other", "a no against a pair from another domain",
                pair_id="an-id-that-is-not-here")

        bundle = portable.export_bundle(store)
        exported = {p["id"] for p in bundle["pairs"]}
        for r in bundle["rejections"]:
            assert not r["pair_id"] or r["pair_id"] in exported


class TestTruncationIsNeverSilent:
    """One `limit` fed two reads that count different rows and are ordered in
    opposite directions, so it truncated the two lists from opposite ends."""

    def test_hitting_the_rejection_cap_warns(self, store):
        _decision(store, "q", "a")
        for i in range(6):
            _reject(store, "q", f"alternative {i}")
        with pytest.warns(RuntimeWarning, match="rejection limit"):
            bundle = portable.export_bundle(store, rejection_limit=3)
        assert bundle["counts"]["rejections"] == 3

    def test_hitting_the_pair_cap_warns_and_keeps_every_reachable_rejection(self, store):
        for i in range(4):
            pair = _decision(store, f"question {i}", "a")
            _reject(store, f"question {i}", "no", pair_id=pair["id"])
        with pytest.warns(RuntimeWarning, match="pair limit"):
            bundle = portable.export_bundle(store, limit=2)
        assert bundle["counts"]["pairs"] == 2
        # Every "no" travels — the two whose pairs are carried keep their
        # pair_id, and the two whose pairs fell outside the cap travel with the
        # pointer blanked rather than being dropped (a signed human refusal is
        # not the pair cap's business). The first version asserted only that a
        # warning fired, and a build shipping zero rejections passed it.
        assert bundle["counts"]["rejections"] == 4
        assert {r["pair_id"] != "" for r in bundle["rejections"]} == {True, False}
        assert bundle["partial_pairs"] is True
        assert bundle["partial_rejections"] is False   # no rejection was lost

    def test_rejections_are_not_capped_by_the_pair_count(self, store):
        """The shape that hid it: few pairs, many rejections, one shared limit.

        The first version of this test never passed a `limit` at all, so it ran
        on the 1,000,000 default and passed against the very build whose shared
        cap it claimed to gate. The regression lived exactly in the gap it left.
        """
        _decision(store, "q", "a")
        for i in range(8):
            _reject(store, "q", f"alternative {i}")
        bundle = portable.export_bundle(store, limit=1)
        assert bundle["counts"]["pairs"] == 1
        assert bundle["counts"]["rejections"] == 8, (
            "a cap on PAIRS decided how many REJECTIONS travelled")


class TestImportReadsTheBundlesOwnVersion:
    """`digest()` selects fields by version; the importer did not, so a field
    the v1 digest never covered could be added after export and still land."""

    def test_a_v1_bundle_cannot_smuggle_a_v2_field(self, store):
        pairs = [{"id": "p1", "source_text": "q", "source_norm": "q",
                  "source_lang": "d", "target_lang": "d", "target_text": "a",
                  "status": "draft", "verifier": "", "weight": 1.0, "origin": "",
                  "created_at": "2026-01-01T00:00:00+00:00", "seal_sig": ""}]
        rejections = [{"id": "r1", "query_norm": "q", "source_lang": "d",
                       "target_lang": "d", "pair_id": "", "target_text": "no",
                       "verifier": "rita", "reason": "because",
                       "created_at": "2026-01-01T00:00:00+00:00", "reject_sig": ""}]
        bundle = {"nestor_bundle": 1, "pairs": pairs, "rejections": rejections,
                  "digest": portable.digest(pairs, rejections, version=1)}
        # Added AFTER the digest was taken. v1 hashing does not cover the key,
        # so the bundle still verifies — the importer must not read it anyway.
        bundle["rejections"][0]["reopen_when"] = "ATTACKER CONTROLLED"
        assert portable.verify_bundle(bundle)[0]

        portable.import_bundle(bundle, store=store, dry_run=False, verifier="rita")
        landed = store.memory_list_rejections(limit=10)
        assert len(landed) == 1
        assert landed[0]["reopen_when"] == "", (
            "a version-1 bundle injected a version-2 field past its own digest")

    def test_a_version_field_must_be_a_whole_number(self):
        """`True` is not a version even though `bool` is an `int`. An integral
        float IS one: `_canonical` in the same module exists because a bundle
        through a browser comes back with 1.0 where 1 went in, and refusing 2.0
        while accepting `weight: 2.0` would apply that rule in one place and
        contradict it in another."""
        for bogus in (True, False, "1", None, 2.5, [2]):
            ok, _ = portable.verify_bundle({"nestor_bundle": bogus, "pairs": [],
                                            "rejections": []})
            assert not ok, f"{bogus!r} was accepted as a bundle version"
        for good in (1, 2, 2.0):
            ok, detail = portable.verify_bundle({"nestor_bundle": good, "pairs": [],
                                                 "rejections": []})
            assert ok, f"{good!r} was refused as a bundle version: {detail}"


class TestTheReasonIsClassifiedOverEveryRowNotAPage:
    """The first fix classified from the top-8 shown to the reader, so a forged
    seal ranked ninth was invisible to the branch written to name forged seals."""

    def test_a_forged_seal_below_the_display_page_is_still_named(self, store, seal_key):
        # The forged row must outrank the threshold and UNDERRANK the page, or
        # the test does not reproduce the defect. The first version of this test
        # made the forged row score 1.0 — it ranked first, was on the page, and
        # passed against the broken code. Scores below are measured, not assumed.
        base = "the quick brown fox jumps over the lazy dog and keeps running"
        for c in "abcdefghi":                       # 9 drafts, each ~0.99
            _decision(store, base[:-1] + c, "a draft")
        forged_src = "the quick brown fox jumps over the lazy dog and keeps walking"
        memory.add_pair(forged_src, "a forged answer", "decision", "decision",
                        status="sealed", verifier="rita", store=store)
        row = [p for p in store.memory_list(source_lang="decision", limit=50)
               if p["source_text"] == forged_src][0]
        with store._db() as conn:
            conn.execute("UPDATE tm_pairs SET seal_sig=? WHERE id=?",
                         ("deadbeef" * 8, row["id"]))

        result = answer.match(store, base, "decision", "decision")
        forged = [c for c in result["matches"] if c["id"] == row["id"]]
        assert not forged, ("the forged row is on the display page, so this test is "
                            "not exercising the defect it was written for")
        assert not result["served"]
        assert "does not verify" in result["reason"], (
            f"a row claiming to be sealed sat above the bar, off the display page, "
            f"and the reason said nobody had verified anything: {result['reason']!r}")

    def test_the_display_page_is_still_bounded(self, store):
        for i in range(12):
            _decision(store, f"question {i:02d}", "a")
        result = answer.match(store, "question 00", "decision", "decision")
        assert len(result["matches"]) == 8   # not <=: [] would pass that


class TestBothWaysOfRefusingAreReported:
    """`reject_pair` sets tm_pairs.status='rejected'; `reject_match` writes
    tm_rejections. Consulting only the second called the first 'nothing'."""

    def test_a_pair_rejected_outright_is_not_reported_as_absent(self, store, seal_key):
        pair = _decision(store, "a bad mapping", "a wrong answer", status="sealed")
        memory.reject_pair(pair["id"], verifier="rita", reason="wrong outright",
                           store=store)
        result = answer.match(store, "a bad mapping", "decision", "decision")
        assert not result["served"]
        assert "nothing in this domain" not in result["reason"], (
            f"a pair somebody explicitly rejected was reported as never having "
            f"existed: {result['reason']!r}")
        assert "reject_pair" in result["reason"]


# ----------------------------------------------------- the second audit ------
#
# A second adversarial audit of the round-two fix found five more, including a
# second critical regression IN THE FIX: `rejection_limit` defaulted back to
# `limit`, and combined with the exported-pairs filter — pairs read newest-first,
# rejections oldest-first — the two windows were disjoint under any cap, so NO
# pair-bound rejection travelled at all. Three successive fixes, each a filter
# interacting with the last. The answer was to stop filtering: two walks, each
# bounded by construction. These tests are the shape of that argument.

class TestACapOnPairsNeverDecidesWhichRejectionsTravel:

    def test_a_pair_cap_does_not_empty_the_rejections(self, store):
        """The regression, exactly: master and the first fix both carried N."""
        for i in range(10):
            pair = _decision(store, f"question {i:02d}", "a")
            _reject(store, f"question {i:02d}", "no", pair_id=pair["id"])
        for cap in (10, 5, 3):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                bundle = portable.export_bundle(store, limit=cap)
            assert bundle["counts"]["pairs"] == cap
            # Never zero, and never governed by the pair cap: the regression
            # exported 0. Rejections whose pair was cut travel with a blanked
            # pointer, so the count is the whole domain's, not the window's.
            assert bundle["counts"]["rejections"] == 10, (
                f"limit={cap} exported {bundle['counts']['rejections']} of 10 "
                f"recorded rejections")
            assert not [r for r in bundle["rejections"]
                        if r["pair_id"] and r["pair_id"] not in
                        {p["id"] for p in bundle["pairs"]}]

    def test_rejection_limit_is_independent_of_limit(self, store):
        _decision(store, "q", "a")
        for i in range(5):
            _reject(store, "q", f"free alternative {i}")
        bundle = portable.export_bundle(store, limit=1)      # tight pair cap
        assert bundle["counts"]["rejections"] == 5           # untouched by it

    def test_an_exactly_full_export_does_not_cry_wolf(self, store):
        """`len(rows) >= limit` cannot tell 'full' from 'truncated'."""
        for i in range(3):
            _decision(store, f"question {i}", "a")
        with warnings.catch_warnings():
            warnings.simplefilter("error")                   # any warning fails
            bundle = portable.export_bundle(store, limit=3)
        assert bundle["counts"]["pairs"] == 3
        assert bundle["partial_pairs"] is False
        assert bundle["partial_rejections"] is False

    def test_a_genuinely_truncated_export_still_warns(self, store):
        for i in range(4):
            _decision(store, f"question {i}", "a")
        with pytest.warns(RuntimeWarning, match="pair limit"):
            bundle = portable.export_bundle(store, limit=3)
        # partial_PAIRS. The two were one flag, so a bundle missing pairs and
        # no rejections announced "missing rejections".
        assert bundle["partial_pairs"] is True
        assert bundle["partial_rejections"] is False

    def test_superseded_rows_do_not_trigger_a_false_truncation_warning(self, store, seal_key):
        """The pair check ran before the superseded filter, so a bundle carrying
        every live row still warned."""
        memory.add_pair("q", "v1", "decision", "decision", status="sealed",
                        verifier="rita", store=store)
        memory.supersede_pair("q", "v2", "decision", "decision", verifier="rita",
                              reason="replaced", store=store)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            portable.export_bundle(store, limit=2)


class TestTheInvariantHoldsOnTheReadSideToo:
    """Export-side enforcement is half an invariant. A hand-edited bundle, a
    third-party one, or one written by an earlier build can still name a pair it
    does not carry — and honouring it is the documented harm."""

    def test_a_dangling_rejection_is_refused_on_import(self, store, seal_key):
        _decision(store, "live question", "live answer", status="sealed")
        bundle = portable.export_bundle(store)
        bundle["rejections"] = [{
            "id": "r-x", "query_norm": "live question", "source_lang": "decision",
            "target_lang": "decision", "pair_id": "an-id-not-in-this-bundle",
            "target_text": "", "verifier": "x", "reason": "forged",
            "created_at": "2026-01-01T00:00:00+00:00", "reject_sig": "",
            "reopen_when": ""}]
        bundle["digest"] = portable.digest(bundle["pairs"], bundle["rejections"],
                                           version=bundle["nestor_bundle"])
        assert portable.verify_bundle(bundle)[0], "the digest is not a signature"

        report = portable.import_bundle(bundle, store=store, dry_run=False,
                                        verifier="rita")
        assert report["dangling_rejections"] == ["an-id-not-in-this-bundle"]
        assert report["rejections"] == 0

    def test_a_rejection_survives_a_full_round_trip(self, store, tmp_path):
        """Import maps an incoming pair onto the DESTINATION's id; a rejection
        names the SOURCE's. Without remapping it lands inert and the
        destination's own next export drops it — the signed 'no' surviving one
        hop and dying on the second."""
        from nestor.sqlite_store import SqliteStore
        pair = _decision(store, "q", "a")
        _reject(store, "q", "no", pair_id=pair["id"])
        bundle = portable.export_bundle(store)

        other = SqliteStore(str(tmp_path / "other.db"))
        other.init_db()
        other.memory_init()
        memory.add_pair("q", "a", "decision", "decision", store=other)   # same key
        dest_id = other.memory_list(limit=5)[0]["id"]
        assert dest_id != pair["id"]

        portable.import_bundle(bundle, store=other, dry_run=False, verifier="rita")
        landed = other.memory_list_rejections(limit=5)
        assert len(landed) == 1
        assert landed[0]["pair_id"] == dest_id, "the rejection points at a stranger"
        assert portable.export_bundle(other)["counts"]["rejections"] == 1, (
            "hop two dropped it")


class TestTheRejectedPairReasonIsScoredNotKeyed:

    def test_a_fuzzy_query_against_a_rejected_pair_says_so(self, store, seal_key):
        """One character off, and the sentence the fix removed came back."""
        pair = _decision(store, "a bad mapping", "a wrong answer", status="sealed")
        memory.reject_pair(pair["id"], verifier="rita", reason="wrong", store=store)
        result = answer.match(store, "a bad mappingg", "decision", "decision")
        assert not result["served"]
        assert "rejected outright" in result["reason"], result["reason"]
        assert "nothing in this domain" not in result["reason"]

    def test_the_numeric_sentinel_does_not_name_an_unrelated_pair(self, store):
        """NumericMatcher collapses every unparseable input to one sentinel, so
        an exact-key hit could name a pair the query never matched — under a
        message asserting 'this exact source'.

        The pair must be STORED with the numeric matcher, or its `source_norm`
        is the plain string and the sentinel never collides. The first version
        of this test used the default matcher and passed for that reason —
        against the build that had the defect.
        """
        from nestor.matcher import NumericMatcher
        pair = memory.add_pair("revenue for the quarter", "100", "n", "n",
                               store=store, matcher=NumericMatcher())
        stored = store.memory_list(source_lang="n", limit=5)[0]["source_norm"]
        assert "nestor:nan" in stored, "the sentinel collision is not set up"
        memory.reject_pair(pair["id"], verifier="rita", reason="x", store=store)

        result = answer.match(store, "a completely different label", "n", "n",
                              matcher="numeric")
        assert "rejected outright" not in result["reason"], (
            f"a rejected pair the query never matched was named, because both "
            f"normalize to the NaN sentinel: {result['reason']!r}")


# ---------------------------------------------------- the Nestor loop --------
#
# Feeding the fix rounds back through the store (IDEAS §6.18) found that an
# agent cannot record a changed mind at all: supersede needs a seal, and
# add_pair over a draft was a silent no-op that returned the PREVIOUS proposal
# as if it were yours. Running the loop a second time, after the refusal
# landed, found the miscount below.

class TestAProposalIsNeverAnsweredWithSomebodyElses:

    def test_a_different_draft_for_the_same_source_is_refused(self, store):
        _decision(store, "Q", "FIRST answer")
        with pytest.raises(memory.ConflictingDraftError, match="already holds the draft"):
            _decision(store, "Q", "SECOND answer")
        assert store.memory_list(limit=5)[0]["target_text"] == "FIRST answer"

    def test_re_proposing_the_same_answer_is_idempotent(self, store):
        """A retrying host must not trip the guard."""
        first = _decision(store, "Q", "same answer")
        again = _decision(store, "Q", "same answer")
        assert first["id"] == again["id"]

    def test_the_returned_row_is_never_a_proposal_the_caller_did_not_make(self, store):
        """The defect itself: `p = add_pair(...)` handed back a stranger's row.

        Whatever draft revision should mean, returning success for a write that
        did not happen is wrong under every answer to it.
        """
        _decision(store, "Q", "FIRST answer")
        try:
            out = _decision(store, "Q", "SECOND answer")
        except memory.ConflictingDraftError:
            return                                    # refused: nothing to lie about
        assert out["target_text"] == "SECOND answer", (
            f"add_pair returned {out['target_text']!r} to a caller that proposed "
            f"'SECOND answer', with no exception and no warning")

    def test_sealing_over_a_draft_is_untouched(self, store, seal_key):
        """The upgrade path must not be caught by the new guard — a human
        checking a machine's draft is the product."""
        _decision(store, "Q", "a machine guess")
        out = memory.add_pair("Q", "what the human decided", "decision", "decision",
                              status="sealed", verifier="rita", store=store)
        assert out["status"] == "sealed"
        assert out["target_text"] == "what the human decided"


class TestTheSuppressedCountCountsRejectionsNotCandidates:

    def test_the_number_matches_the_noun(self, store):
        """One pair, three rejections: the message said '3 candidate(s)'."""
        _decision(store, "Q", "an answer")
        for i in range(3):
            _reject(store, "Q", f"refused alternative {i}")
        _reject(store, "Q", "an answer")          # suppress the live one too
        result = answer.match(store, "Q", "decision", "decision")
        assert not result["served"]
        assert "recorded rejection(s)" in result["reason"]
        assert "candidate(s) are suppressed" not in result["reason"], result["reason"]


# --------------------------------------------- the missing third verb --------
#
# §6.18/§6.19: supersede_pair covers sealed→sealed, add_pair covers
# draft→sealed, and draft→draft had nothing — so an agent could not record a
# changed mind. `revise_draft` is that verb. It needed no new Storage
# operation: memory_mark_superseded and memory_insert already existed for
# supersede_pair, so §6.19's claim that "the Protocol was never given the verb"
# was wrong. `memory` was withholding it.

class TestRevisingADraftKeepsWhatItReplaced:

    def test_the_live_row_is_the_revision_and_the_old_one_is_history(self, store):
        memory.add_pair("Q", "first attempt", "d", "d", status="draft",
                        reason="the original", store=store)
        new = memory.revise_draft("Q", "second attempt", "d", "d",
                                  reason="the first was wrong because X", store=store)
        live = [p for p in store.memory_list(source_lang="d", limit=10)
                if not p["superseded_by"]]
        assert len(live) == 1
        assert live[0]["target_text"] == "second attempt" == new["target_text"]
        chain = store.memory_lineage(new["id"])
        assert [c["target_text"] for c in chain] == ["first attempt"]
        assert chain[0]["reason"] == "the original", (
            "the abandoned proposal lost the reason it was abandoned for, which "
            "is the only thing distinguishing 'we tried this' from 'we never "
            "thought of it'")

    def test_a_chain_of_revisions_walks_back_newest_first(self, store):
        memory.add_pair("Q", "v1", "d", "d", status="draft", reason="r1", store=store)
        for target, reason in (("v2", "r2"), ("v3", "r3"), ("v4", "r4")):
            new = memory.revise_draft("Q", target, "d", "d", reason=reason, store=store)
        assert [c["target_text"] for c in store.memory_lineage(new["id"])] == \
               ["v3", "v2", "v1"]

    def test_the_successor_is_a_draft_and_grants_no_trust(self, store, seal_key):
        """The covenant: the machine may propose and may not confirm. A revision
        must not be able to launder a proposal into a verification."""
        memory.add_pair("Q", "first", "d", "d", status="draft", store=store)
        new = memory.revise_draft("Q", "second", "d", "d", store=store)
        assert new["status"] == "draft"
        assert new["verifier"] == ""
        assert new["seal_sig"] == ""
        assert not memory.is_verified_seal(new)

    def test_it_ledgers_a_supersede_and_never_a_seal(self, store):
        """A seal entry would say a human had acted. Nobody did."""
        from tests.conftest import read_ledger
        memory.add_pair("Q", "first", "d", "d", status="draft", store=store)
        memory.revise_draft("Q", "second", "d", "d", reason="why", store=store)
        kinds = [e["kind"] for e in read_ledger()]
        assert "supersede" in kinds
        assert "seal" not in kinds, f"a draft revision claimed a seal: {kinds}"
        entry = [e for e in read_ledger() if e["kind"] == "supersede"][0]
        assert entry["verifier"] == ""
        assert entry["replaced_status"] == "draft"

    def test_superseded_drafts_do_not_travel_in_a_bundle(self, store):
        """Same rule as superseded seals: history, not stock."""
        memory.add_pair("Q", "first", "d", "d", status="draft", store=store)
        memory.revise_draft("Q", "second", "d", "d", store=store)
        bundle = portable.export_bundle(store)
        assert bundle["counts"]["pairs"] == 1
        assert bundle["pairs"][0]["target_text"] == "second"

    def test_a_sealed_row_is_sent_to_supersede_pair(self, store, seal_key):
        memory.add_pair("Q", "checked", "d", "d", status="sealed",
                        verifier="rita", store=store)
        with pytest.raises(ValueError, match="supersede_pair"):
            memory.revise_draft("Q", "something else", "d", "d", store=store)

    def test_a_rejected_row_is_refused(self, store, seal_key):
        pair = memory.add_pair("Q", "bad", "d", "d", status="sealed",
                               verifier="rita", store=store)
        memory.reject_pair(pair["id"], verifier="rita", reason="wrong", store=store)
        with pytest.raises(memory.RejectedPairError):
            memory.revise_draft("Q", "something else", "d", "d", store=store)

    def test_revising_to_the_same_target_is_refused(self, store):
        memory.add_pair("Q", "same", "d", "d", status="draft", store=store)
        with pytest.raises(ValueError, match="nothing to revise"):
            memory.revise_draft("Q", "same", "d", "d", store=store)

    def test_the_conflict_error_points_at_the_verb(self, store):
        """The refusal added in §6.19 was a dead end until this existed."""
        memory.add_pair("Q", "first", "d", "d", status="draft", store=store)
        with pytest.raises(memory.ConflictingDraftError, match="revise_draft"):
            memory.add_pair("Q", "second", "d", "d", status="draft", store=store)


# ------------------------------------------------- the third audit ----------
#
# A third audit found two CRITICAL races in `revise_draft`, both reproducible
# with ordinary threads and no fault injection: an unverified caller could
# retire a human's seal (282/300 trials), and two concurrent revisions
# destroyed the winner's lineage (184/200). Both were the branch's recurring
# shape — a Python-side condition guarding a store-side write that could not
# re-assert it. The fix is compare-and-set: the precondition travels with the
# write, and a store that cannot express that is refused rather than raced.

class TestARevisionCannotRetireASeal:

    def test_a_row_sealed_after_the_read_is_not_retired(self, store, seal_key):
        """The TOCTOU, made deterministic: seal lands between find and mark."""
        memory.add_pair("Q", "hola", "decision", "decision", status="draft", store=store)
        row = store.memory_list(source_lang="decision", limit=5)[0]
        memory.add_pair("Q", "hola", "decision", "decision", status="sealed",
                        verifier="rita", store=store)          # the human, first
        with pytest.raises(ValueError, match="supersede_pair"):
            memory.revise_draft("Q", "hallo", "decision", "decision", store=store)
        after = store.memory_get(row["id"])
        assert after["status"] == "sealed"
        assert after["superseded_by"] == "", "a human's seal was pushed into history"

    def test_the_mark_itself_refuses_a_row_that_changed(self, store, seal_key):
        """Straight at the store op: the guard must live in the WHERE clause,
        because that is the only place a concurrent writer cannot step past."""
        memory.add_pair("Q", "hola", "decision", "decision", status="draft", store=store)
        row = store.memory_list(source_lang="decision", limit=5)[0]
        assert store.memory_mark_superseded_if(row["id"], "x", "sealed", "") is False
        assert store.memory_get(row["id"])["superseded_by"] == ""
        assert store.memory_mark_superseded_if(row["id"], "x", "draft", "") is True
        assert store.memory_get(row["id"])["superseded_by"] == "x"

    def test_a_seal_cannot_land_on_a_row_already_retired(self, store, seal_key):
        """The other interleaving, and the one the first fix missed: the CAS
        stopped us retiring a sealed row, and nothing stopped a seal landing on
        a row we had just retired — the verification applied to history."""
        from nestor.sqlite_store import RowRetiredError
        memory.add_pair("Q", "hola", "decision", "decision", status="draft", store=store)
        row = store.memory_list(source_lang="decision", limit=5)[0]
        store.memory_mark_superseded_if(row["id"], "gone", "draft", "")
        with pytest.raises(RowRetiredError):
            store.memory_seal(row["id"], "hola", "rita", 1.0, "sig")
        assert store.memory_get(row["id"])["status"] == "draft"

    def test_it_refuses_a_store_that_cannot_do_it_atomically(self, store):
        """Refused, not degraded: the operation it would otherwise perform can
        destroy a human's verification."""
        class _NoCas:
            def __init__(self, inner): self._inner = inner
            def __getattr__(self, name):
                if name == "memory_mark_superseded_if":
                    raise AttributeError(name)
                return getattr(self._inner, name)
        memory.add_pair("Q", "first", "decision", "decision", status="draft", store=store)
        blind = _NoCas(store)
        assert not storage.supports_atomic_supersede(blind)
        with pytest.raises(RuntimeError, match="conditionally"):
            memory.revise_draft("Q", "second", "decision", "decision", store=blind)
        assert store.memory_list(source_lang="decision", limit=5)[0]["superseded_by"] == ""


class TestConcurrentRevisionsKeepTheWinnersLineage:

    def test_two_revisions_leave_one_live_row_and_an_intact_chain(self, store):
        import threading
        memory.add_pair("Q", "v0", "decision", "decision", status="draft", store=store)
        errs = []

        def rev(t):
            try:
                memory.revise_draft("Q", t, "decision", "decision", store=store)
            except Exception as e:               # noqa: BLE001 — one is expected to lose
                errs.append(type(e).__name__)

        threads = [threading.Thread(target=rev, args=(t,)) for t in ("A", "B")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        rows = store.memory_list(source_lang="decision", limit=10)
        live = [r for r in rows if not r["superseded_by"]]
        assert len(live) == 1, "the partial unique index should permit exactly one"
        assert not [r for r in rows if r["superseded_by"].startswith("pending:")], (
            "an abandoned revision left the predecessor pointing at a row that "
            "was never inserted — the lineage this verb exists to keep")
        assert store.memory_lineage(live[0]["id"]), "the winner lost its history"

    def test_a_failed_insert_does_not_vandalise_a_finished_revision(self, store):
        """The loser's rollback used to fire unconditionally and could overwrite
        the winner's successor pointer with its own abandoned marker."""
        memory.add_pair("Q", "v0", "decision", "decision", status="draft", store=store)
        first = memory.revise_draft("Q", "v1", "decision", "decision", store=store)
        old_id = store.memory_lineage(first["id"])[0]["id"]
        # Someone else's stale rollback attempt must be a no-op now.
        assert store.memory_mark_superseded_if(old_id, "", "draft",
                                               "pending:whatever") is False
        assert store.memory_get(old_id)["superseded_by"] == first["id"]


class TestARevisionCannotInstallARefusedAnswer:

    def test_a_target_a_human_rejected_is_refused(self, store, seal_key):
        """reject_pair was checked; reject_match was not — so an agent could
        install a target somebody signed a 'no' against, after which lookup
        suppresses it and the store stops answering at all."""
        memory.add_pair("Q", "good draft", "decision", "decision",
                        status="draft", store=store)
        memory.reject_match("Q", "decision", "decision", target_text="refused answer",
                            verifier="rita", reason="wrong", store=store)
        with pytest.raises(memory.RejectedPairError, match="refused"):
            memory.revise_draft("Q", "refused answer", "decision", "decision", store=store)
        assert store.memory_list(source_lang="decision",
                                 limit=5)[0]["target_text"] == "good draft"


class TestTheLedgerDoesNotAssertWhatItDidNotCheck:

    def test_same_verifier_is_computed_not_hardcoded(self, store, seal_key):
        """memory_unseal clears seal_sig and KEEPS verifier, so a revised
        once-sealed row has a predecessor verifier while this caller has none."""
        from tests.conftest import read_ledger
        pair = memory.add_pair("Q", "v0", "decision", "decision", status="sealed",
                               verifier="bob", store=store)
        from nestor.curator import Curator
        Curator(store).unseal(pair["id"], verifier="bob", reason="reconsidering")
        memory.revise_draft("Q", "v1", "decision", "decision", store=store)
        entry = [e for e in read_ledger() if e["kind"] == "supersede"][-1]
        assert entry["replaced_verifier"] == "bob"
        assert entry["verifier"] == ""
        assert entry["same_verifier"] is False, (
            "the trail asserted the same verifier acted on both sides when "
            "nobody verified this one at all")


class TestARejectionOutlivesThePairItNamed:

    def test_a_no_whose_pair_was_revised_still_travels(self, store):
        """revise_draft made superseding routine, so a rejection naming a
        superseded pair went from rare to ordinary — and it was dropped."""
        pair = _decision(store, "Q", "first draft")
        _reject(store, "Q", "first draft", pair_id=pair["id"], reason="a human said no")
        memory.revise_draft("Q", "second draft", "decision", "decision", store=store)

        bundle = portable.export_bundle(store)
        assert bundle["counts"]["rejections"] == 1, "the signed 'no' was dropped"
        carried = bundle["rejections"][0]
        assert carried["pair_id"] == "", "it must not dangle"
        assert carried["target_text"] == "first draft", (
            "blanking the pointer must keep the target-text suppression, which "
            "is the half that still binds on the destination")
