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
        assert "the best candidate is draft" in result["reason"]
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
        assert "rejection" in result["reason"]
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

    def test_hitting_the_pair_cap_warns(self, store):
        for i in range(4):
            _decision(store, f"question {i}", "a")
        with pytest.warns(RuntimeWarning, match="pair limit"):
            portable.export_bundle(store, limit=2)

    def test_rejections_are_not_capped_by_the_pair_count(self, store):
        """The shape that hid it: few pairs, many rejections, one shared limit."""
        _decision(store, "q", "a")
        for i in range(8):
            _reject(store, "q", f"alternative {i}")
        bundle = portable.export_bundle(store)
        assert bundle["counts"]["rejections"] == 8


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

    def test_a_version_field_must_be_an_integer(self):
        for bogus in (True, 1.0, "1", None):
            ok, _ = portable.verify_bundle({"nestor_bundle": bogus, "pairs": [],
                                            "rejections": []})
            assert not ok, f"{bogus!r} was accepted as a bundle version"


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
        assert len(result["matches"]) <= 8


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
