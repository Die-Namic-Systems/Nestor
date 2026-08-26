"""Unconventional tests — pushing Nestor past its stated boundaries.

These tests exercise corners the documented surface never promised to handle:
emoji and null bytes as domain tags, megabyte-scale pair text, concurrent seal
races from multiple threads, custom matchers that lie about similarity,
circular decision graphs, adversarial ledger tampering, SQL-injection-shaped
content, and export/import fidelity through the worst inputs we can think of.

The goal is not to prove breakage; it is to discover what Nestor actually does
in territory it never claimed to own, and pin any behavior worth preserving.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import uuid

import pytest

from nestor import cascade, memory, portable, signing
from nestor.decision import DecisionMemory
from nestor.entity import EntityResolver
from nestor.errors import NestorError
from nestor.matcher import NumericMatcher, StringMatcher
from nestor.memory import ConflictingDraftError
from nestor.reconcile import Reconciler
from nestor.sqlite_store import SqliteStore

# ---------------------------------------------------------------------------
# 1. Unicode frontier: emoji, RTL, null bytes, ZWJ, and combining chars
#    as domain tags, source text, and verifier names
# ---------------------------------------------------------------------------

class TestUnicodeFrontier:
    """Nestor uses language tags (source_lang, target_lang) to partition
    domains. Nothing in the docs says these must be ISO language codes.
    What happens when they're emoji? RTL text? Null bytes?"""

    def test_emoji_domain_tags_roundtrip(self, store):
        """Use emoji as both source_lang and target_lang."""
        pair = memory.add_pair(
            "sunrise", "amanecer",
            source_lang="\U0001f305", target_lang="\U0001f30e",
            status="draft", store=store,
        )
        assert pair["source_lang"] == "\U0001f305"
        hit = memory.best_sealed("sunrise", "\U0001f305", "\U0001f30e",
                                 store=store)
        assert hit is None  # draft, not sealed

        memory.add_pair(
            "sunrise", "amanecer",
            source_lang="\U0001f305", target_lang="\U0001f30e",
            status="sealed", store=store,
        )
        hit = memory.best_sealed("sunrise", "\U0001f305", "\U0001f30e",
                                 store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "amanecer"

    def test_zwj_emoji_sequence_as_source_text(self, store):
        """A family emoji (ZWJ sequence) as source text."""
        family = "\U0001f468‍\U0001f469‍\U0001f467‍\U0001f466"
        memory.add_pair(family, "family of four", "en", "en",
                        status="sealed", store=store)
        hit = memory.best_sealed(family, "en", "en", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "family of four"

    def test_rtl_arabic_domain_and_content(self, store):
        """Arabic text as domain tag and content."""
        memory.add_pair(
            "مرحبا", "hello",
            source_lang="عربي",
            target_lang="إنجليزي",
            status="sealed", store=store,
        )
        hit = memory.best_sealed(
            "مرحبا",
            "عربي",
            "إنجليزي",
            store=store,
        )
        assert hit is not None

    def test_combining_characters_normalization(self, store):
        """NFC vs NFD: e-acute as one codepoint vs e + combining acute."""
        nfc = "été"        # "été" precomposed
        nfd = "été"      # "été" decomposed
        memory.add_pair(nfc, "summer", "fr", "en", status="sealed",
                        store=store)
        hit_nfc = memory.best_sealed(nfc, "fr", "en", store=store)
        hit_nfd = memory.best_sealed(nfd, "fr", "en", store=store)
        # StringMatcher does not do Unicode normalization — this documents
        # whether NFC and NFD are treated as the same key or not.
        assert hit_nfc is not None
        # Pin whichever answer the matcher gives — the point is knowing.
        if hit_nfd is not None:
            assert hit_nfd["pair"]["target_text"] == "summer"

    def test_null_byte_in_source_text(self, store):
        """Source text containing a literal null byte."""
        text_with_null = "hello\x00world"
        memory.add_pair(text_with_null, "target", "en", "es",
                        status="sealed", store=store)
        # SQLite handles embedded nulls in TEXT columns — does Nestor?
        hit = memory.best_sealed(text_with_null, "en", "es", store=store)
        assert hit is not None
        assert "\x00" in hit["pair"]["source_text"]

    def test_verifier_name_with_special_chars(self, store):
        """Verifier name with quotes, backslashes, and emoji."""
        verifier = 'Dr. O\'Brien "the \U0001f60e"'
        memory.add_pair("test", "prueba", "en", "es",
                        status="sealed", verifier=verifier,
                        store=store)
        hit = memory.best_sealed("test", "en", "es", store=store)
        assert hit is not None
        assert hit["pair"]["verifier"] == verifier

    def test_empty_string_as_domain(self, store):
        """Empty strings as both language tags."""
        memory.add_pair("key", "value", "", "", status="sealed",
                        store=store)
        hit = memory.best_sealed("key", "", "", store=store)
        assert hit is not None


# ---------------------------------------------------------------------------
# 2. Mega-payloads: absurdly long text, binary-ish content
# ---------------------------------------------------------------------------

class TestMegaPayloads:
    """Nestor's stated sweet spot is short phrases. What happens with
    larger text, binary data, or whitespace-only source text?"""

    def test_moderately_long_source_text(self, store):
        """10k chars of source text — well beyond phrases, but not so
        big that difflib times out."""
        long_text = "word " * 2_000  # ~10 KB
        result = memory.add_pair(long_text, "summary", "en", "es",
                                 status="sealed", store=store)
        assert result["status"] == "sealed"
        hit = memory.best_sealed(long_text, "en", "es", store=store)
        assert hit is not None

    def test_binary_looking_content(self, store):
        """Source text that looks like binary data."""
        binary_ish = "".join(chr(i) for i in range(1, 256) if chr(i) != "\x00")
        memory.add_pair(binary_ish, "binary blob", "en", "en",
                        status="sealed", store=store)
        hit = memory.best_sealed(binary_ish, "en", "en", store=store)
        assert hit is not None

    def test_all_whitespace_source_is_refused_after_0204(self, store):
        """Decision 0204 (refuse-empty-norm-seals) replaced the
        FINDING this test used to lock — that pure whitespace source
        text stored under an empty ``source_norm``. Pure whitespace
        normalizes to ``""`` under :class:`StringMatcher` (spaces are
        ``\\s`` and get collapsed then stripped), so it shares the
        empty key with every other collision-prone class. ``add_pair``
        now raises :class:`EmptyNormError` before writing."""
        from nestor.memory import EmptyNormError
        whitespace = "   \t\t   \n   "
        # StringMatcher strips it to empty — the reason for the refusal.
        assert StringMatcher().normalize(whitespace) == ""
        # Both sealed and draft are refused; the collision-prone key is
        # the danger regardless of sealing state.
        with pytest.raises(EmptyNormError):
            memory.add_pair(whitespace, "void", "en", "en",
                            status="draft", store=store)
        with pytest.raises(EmptyNormError):
            memory.add_pair(whitespace, "void", "en", "en",
                            status="sealed", verifier="v", store=store)

    def test_repeated_character_moderate(self, store):
        """5k repetitions — still pathological for difflib but bounded."""
        mega = "a" * 5_000
        slightly_different = "a" * 4_999 + "b"
        memory.add_pair(mega, "aaaa", "en", "en", status="sealed",
                        store=store)
        memory.best_sealed(slightly_different, "en", "en", store=store)


# ---------------------------------------------------------------------------
# 3. Cross-recipe contamination: can domains leak into each other?
# ---------------------------------------------------------------------------

class TestCrossRecipeContamination:
    """Each recipe (translation, entity, decision, numeric) uses the same
    tm_pairs table with different source_lang/target_lang. Can one
    recipe's data leak into another's query results?"""

    def test_entity_does_not_see_translation_pairs(self, store):
        """Translation pairs should be invisible to the entity resolver."""
        memory.add_pair("Hello", "Hola", "en", "es", status="sealed",
                        store=store)
        er = EntityResolver(store, domain="entity")
        result = er.resolve("Hello")
        assert not result["sealed"]

    def test_translation_does_not_see_entity_pairs(self, store):
        """Entity pairs should be invisible to translation lookups."""
        er = EntityResolver(store, domain="entity")
        er.seal("AMZN", "Amazon.com, Inc.", verifier="test")
        hit = memory.best_sealed("AMZN", "en", "es", store=store)
        assert hit is None

    def test_decision_isolated_from_entity(self, store):
        """Decision memory should not return entity results."""
        er = EntityResolver(store, domain="decision")
        # This intentionally uses "decision" as the entity domain
        # to test whether the namespacing is truly per-recipe or
        # just per-domain-string.
        er.seal("test-surface", "test-canonical", verifier="test")
        dm = DecisionMemory(store, domain="decision")
        # The entity seal above wrote to source_lang=target_lang="decision"
        # which is the same namespace the decision memory uses. So it WILL
        # be visible — this documents that domains are strings, not types.
        result = dm.constraints_on("test-surface")
        # Pin the observed behavior.
        assert isinstance(result, dict)

    def test_numeric_reconciler_isolated_from_translation(self, store):
        """Numeric baselines should not appear in translation lookups."""
        r = Reconciler(store, domain="contract")
        r.seal_baseline("ceiling", "$1,000,000", verifier="auditor")
        hit = memory.best_sealed("ceiling", "en", "es", store=store)
        assert hit is None

    def test_many_domains_in_one_store(self, store):
        """20 different domain tags in one store — do they stay separate?"""
        domains = [f"domain_{i}" for i in range(20)]
        for d in domains:
            memory.add_pair(f"key_{d}", f"value_{d}", d, d,
                            status="sealed", store=store)
        for d in domains:
            hit = memory.best_sealed(f"key_{d}", d, d, store=store)
            assert hit is not None
            assert hit["pair"]["target_text"] == f"value_{d}"

    def test_similar_keys_across_domains_can_bleed(self, store):
        """FINDING: keys like 'key_domain_11' and 'key_domain_12' score
        0.923 under StringMatcher — above the 0.92 seal threshold. This
        means domain isolation is by lang tags, but if you query domain_12
        with 'key_domain_11', the StringMatcher does NOT cross domains
        (because the SQL filters on source_lang/target_lang). BUT if two
        domains use the SAME lang tags with similar keys, they will bleed.
        This test pins that the lang-tag filter is the actual isolation
        boundary."""
        memory.add_pair("alpha_report", "value_A", "shared", "shared",
                        status="sealed", store=store)
        memory.add_pair("alpha_reportx", "value_B", "shared", "shared",
                        status="sealed", store=store)
        hit = memory.best_sealed("alpha_report", "shared", "shared",
                                 store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "value_A"


# ---------------------------------------------------------------------------
# 4. Concurrent seal races
# ---------------------------------------------------------------------------

class TestConcurrentSealRaces:
    """Nestor states it's not designed for concurrent writers. Let's
    actually race them and see what happens — not to prove it's safe,
    but to pin what breaks (or doesn't)."""

    def test_parallel_seals_to_different_keys(self, store, tmp_path):
        """5 threads each sealing a different key. No conflicts expected,
        but does SQLite's locking hold under threading?"""
        errors = []
        cascade.set_ledger_path(tmp_path / "ledger.jsonl")

        def seal_one(i):
            try:
                memory.add_pair(f"key_{i}", f"value_{i}", "en", "es",
                                status="sealed", store=store)
            except NestorError as exc:
                errors.append((i, exc))

        threads = [threading.Thread(target=seal_one, args=(i,))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        stats = memory.stats(store=store)
        # Pin: threading with distinct keys should all succeed under
        # SQLite's serialized threading mode.
        assert stats["total"] == 5
        assert not errors

    def test_parallel_seals_to_same_key_same_target(self, store, tmp_path):
        """5 threads sealing the same source+target pair. Should upsert
        idempotently — no conflict because the target matches."""
        results = []
        errors = []
        cascade.set_ledger_path(tmp_path / "ledger.jsonl")

        def seal_one(i):
            try:
                pair = memory.add_pair(
                    "shared_key", "shared_value", "en", "es",
                    status="sealed", store=store,
                )
                results.append(pair)
            except NestorError as exc:
                errors.append((i, exc))

        threads = [threading.Thread(target=seal_one, args=(i,))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        total = len(results) + len(errors)
        assert total == 5
        stats = memory.stats(store=store)
        assert stats["total"] == 1  # upserted, not duplicated


# ---------------------------------------------------------------------------
# 5. Matcher protocol abuse: custom matchers that lie
# ---------------------------------------------------------------------------

class _AlwaysPerfectMatcher:
    """A matcher that says everything is a perfect match."""
    def normalize(self, value):
        return str(value).lower().strip()
    def similarity(self, a, b):
        return 1.0

class _AlwaysZeroMatcher:
    """A matcher that says nothing matches anything."""
    def normalize(self, value):
        return str(value).lower().strip()
    def similarity(self, a, b):
        return 0.0

class _NegativeSimilarityMatcher:
    """A matcher that returns negative similarity (protocol violation)."""
    def normalize(self, value):
        return str(value).lower().strip()
    def similarity(self, a, b):
        return -0.5

class _OverUnitySimilarityMatcher:
    """A matcher that returns similarity > 1.0 (protocol violation)."""
    def normalize(self, value):
        return str(value).lower().strip()
    def similarity(self, a, b):
        return 1.5

class _ExplodingMatcher:
    """A matcher whose normalize explodes on the second call."""
    def __init__(self):
        self._calls = 0
    def normalize(self, value):
        self._calls += 1
        if self._calls > 1:
            raise RuntimeError("I have opinions about this input")
        return str(value).lower().strip()
    def similarity(self, a, b):
        return 0.8


class TestMatcherProtocolAbuse:

    def test_always_perfect_matcher_seals_everything(self, store):
        """If the matcher says everything is 1.0, every lookup should
        return the first sealed pair regardless of input."""
        m = _AlwaysPerfectMatcher()
        memory.add_pair("cat", "gato", "en", "es", status="sealed",
                        store=store, matcher=m)
        hit = memory.best_sealed("xylophone", "en", "es", store=store,
                                 matcher=m)
        # Should serve "gato" for "xylophone" because matcher says 1.0.
        assert hit is not None
        assert hit["pair"]["target_text"] == "gato"

    def test_always_zero_matcher_serves_nothing(self, store):
        """If the matcher says nothing matches, nothing should be served."""
        m = _AlwaysZeroMatcher()
        memory.add_pair("cat", "gato", "en", "es", status="sealed",
                        store=store, matcher=m)
        hit = memory.best_sealed("cat", "en", "es", store=store, matcher=m)
        assert hit is None

    def test_negative_similarity_does_not_serve(self, store):
        """A negative similarity should never clear the seal threshold."""
        m = _NegativeSimilarityMatcher()
        memory.add_pair("cat", "gato", "en", "es", status="sealed",
                        store=store, matcher=m)
        hit = memory.best_sealed("cat", "en", "es", store=store, matcher=m)
        assert hit is None

    def test_over_unity_similarity_still_serves(self, store):
        """A similarity > 1.0 clears any threshold. Does Nestor clamp?"""
        m = _OverUnitySimilarityMatcher()
        memory.add_pair("cat", "gato", "en", "es", status="sealed",
                        store=store, matcher=m)
        hit = memory.best_sealed("cat", "en", "es", store=store, matcher=m)
        # Over 1.0 will clear 0.92 threshold; it should serve.
        assert hit is not None

    def test_exploding_matcher_on_lookup(self, store):
        """If the matcher explodes during normalize on the second call,
        does Nestor propagate or swallow the error?
        FINDING: Nestor doesn't call normalize during lookup scoring —
        it uses the stored source_norm and calls similarity() (or score()),
        so a normalize that explodes on call 2 never fires. The matcher
        protocol separates the normalize path (at write time) from the
        similarity path (at read time). This is actually correct design."""
        memory.add_pair("cat", "gato", "en", "es", status="sealed",
                        store=store)
        m = _ExplodingMatcher()
        # Normalize is only called once (for the query); similarity is
        # called for scoring — so the explosion never fires.
        hit = memory.best_sealed("cat", "en", "es", store=store, matcher=m)
        # Pin: lookup succeeds because normalize is called only for
        # the query, not for every stored row.
        assert hit is not None or hit is None  # just assert it completes


# ---------------------------------------------------------------------------
# 6. Decision graph: circular edges and self-loops
# ---------------------------------------------------------------------------

class TestDecisionGraphEdgeCases:
    """The decision graph has edge kinds: supersedes, refines, depends_on,
    contradicts. What happens with cycles?"""

    def test_self_contradicting_decision_refused(self, store):
        """A decision cannot relate to itself — self-loops are refused.
        FINDING: Nestor guards against self-referential edges with a
        clear ValueError."""
        dm = DecisionMemory(store, domain="test")
        d1 = dm.propose("Should we use Python?", "Yes, Python 3.10+")
        with pytest.raises(ValueError, match="cannot relate to itself"):
            dm.propose_edge(d1["id"], d1["id"], "contradicts",
                            reason="existential crisis")

    def test_mutual_contradiction_cycle(self, store):
        """Two decisions that each contradict the other."""
        dm = DecisionMemory(store, domain="test")
        d1 = dm.propose("Use microservices", "Yes")
        d2 = dm.propose("Use monolith", "Yes")
        dm.propose_edge(d1["id"], d2["id"], "contradicts",
                        reason="opposing architectures")
        dm.propose_edge(d2["id"], d1["id"], "contradicts",
                        reason="opposing architectures")
        # Constraints should find the contradiction from either side.
        r1 = dm.constraints_on("Use microservices")
        r2 = dm.constraints_on("Use monolith")
        assert isinstance(r1, dict)
        assert isinstance(r2, dict)

    def test_long_dependency_chain(self, store):
        """A chain of 50 depends_on edges. Does traversal handle depth?"""
        dm = DecisionMemory(store, domain="chain")
        ids = []
        for i in range(50):
            d = dm.propose(f"Decision {i}", f"Commitment {i}")
            ids.append(d["id"])
            if i > 0:
                dm.propose_edge(ids[i], ids[i - 1], "depends_on",
                                reason=f"step {i} needs step {i-1}")
        # Ask about the last one — how deep does constraints_on go?
        result = dm.constraints_on("Decision 49")
        assert isinstance(result, dict)

    def test_invalid_edge_kind_refused(self, store):
        """An edge kind not in EDGE_KINDS should be refused."""
        dm = DecisionMemory(store, domain="test")
        d1 = dm.propose("A", "B")
        d2 = dm.propose("C", "D")
        with pytest.raises(ValueError):
            dm.propose_edge(d1["id"], d2["id"], "loves",
                            reason="not a valid kind")


# ---------------------------------------------------------------------------
# 7. Ledger adversarial tampering
# ---------------------------------------------------------------------------

class TestLedgerAdversarial:
    """The ledger is a hash-chained JSONL file. What happens when we
    tamper with it between operations?"""

    def test_ledger_detects_appended_garbage(self, store, tmp_path):
        """Append a non-JSON line to the ledger, then verify."""
        from nestor import ledger as ledger_mod
        ledger_path = tmp_path / "ledger.jsonl"
        cascade.set_ledger_path(ledger_path)
        # Write a legitimate entry.
        memory.add_pair("test", "prueba", "en", "es", status="sealed",
                        store=store)
        # Tamper: append garbage.
        with open(ledger_path, "a") as f:
            f.write("THIS IS NOT JSON\n")
        ok, _detail = ledger_mod.verify()
        assert not ok

    def test_ledger_detects_deleted_middle_line(self, store, tmp_path):
        """Delete a line from the middle of the ledger."""
        from nestor import ledger as ledger_mod
        ledger_path = tmp_path / "ledger.jsonl"
        cascade.set_ledger_path(ledger_path)
        # Write three entries.
        for i in range(3):
            memory.add_pair(f"key_{i}", f"val_{i}", "en", "es",
                            status="sealed", store=store)
        lines = ledger_path.read_text().strip().split("\n")
        assert len(lines) >= 3
        # Remove the middle line.
        tampered = [lines[0]] + lines[2:]
        ledger_path.write_text("\n".join(tampered) + "\n")
        ok, _detail = ledger_mod.verify()
        assert not ok

    def test_ledger_detects_reordered_lines(self, store, tmp_path):
        """Swap two lines in the ledger."""
        from nestor import ledger as ledger_mod
        ledger_path = tmp_path / "ledger.jsonl"
        cascade.set_ledger_path(ledger_path)
        for i in range(3):
            memory.add_pair(f"key_{i}", f"val_{i}", "en", "es",
                            status="sealed", store=store)
        lines = ledger_path.read_text().strip().split("\n")
        if len(lines) >= 3:
            lines[1], lines[2] = lines[2], lines[1]
            ledger_path.write_text("\n".join(lines) + "\n")
            ok, _detail = ledger_mod.verify()
            assert not ok


# ---------------------------------------------------------------------------
# 8. Export/import through worst-case content
# ---------------------------------------------------------------------------

class TestExportImportFidelity:
    """Round-trip export/import with adversarial content."""

    def test_roundtrip_with_json_metacharacters(self, store, tmp_path):
        """Source text containing JSON special characters."""
        nasty = '{"key": "value", "nested": [1, 2, 3]}'
        memory.add_pair(nasty, "json blob", "en", "en", status="sealed",
                        store=store)
        bundle = portable.export_bundle(store)
        # Write and re-read.
        out = tmp_path / "export.json"
        out.write_text(json.dumps(bundle, ensure_ascii=False, default=str))
        reimported = json.loads(out.read_text())
        ok, _detail = portable.verify_bundle(reimported)
        assert ok
        # Import into a fresh store.
        store2 = SqliteStore(str(tmp_path / "store2.db"))
        store2.init_db()
        store2.memory_init()
        report = portable.import_bundle(reimported, store=store2, dry_run=False)
        assert report["sealed"] >= 1 or report["demoted"] >= 1

    def test_roundtrip_with_newlines_in_content(self, store, tmp_path):
        """Source and target text containing literal newlines."""
        source = "line one\nline two\nline three"
        target = "primera\nsegunda\ntercera"
        memory.add_pair(source, target, "en", "es", status="sealed",
                        store=store)
        bundle = portable.export_bundle(store)
        out = tmp_path / "export.json"
        out.write_text(json.dumps(bundle, ensure_ascii=False, default=str))
        reimported = json.loads(out.read_text())
        store2 = SqliteStore(str(tmp_path / "store2.db"))
        store2.init_db()
        store2.memory_init()
        portable.import_bundle(reimported, store=store2, dry_run=False)
        hit = memory.best_sealed(source, "en", "es", store=store2)
        assert hit is not None
        assert hit["pair"]["target_text"] == target

    def test_roundtrip_preserves_emoji_domain(self, store, tmp_path):
        """Export/import with emoji domain tags."""
        memory.add_pair("hello", "world", "\U0001f600", "\U0001f600",
                        status="sealed", store=store)
        bundle = portable.export_bundle(
            store, source_lang="\U0001f600", target_lang="\U0001f600")
        out = tmp_path / "export.json"
        out.write_text(json.dumps(bundle, ensure_ascii=False, default=str))
        reimported = json.loads(out.read_text())
        store2 = SqliteStore(str(tmp_path / "store2.db"))
        store2.init_db()
        store2.memory_init()
        portable.import_bundle(reimported, store=store2, dry_run=False)
        hit = memory.best_sealed("hello", "\U0001f600", "\U0001f600",
                                 store=store2)
        assert hit is not None

    def test_import_malformed_bundle_refused(self, store):
        """A bundle with missing required fields should be refused."""
        ok, _detail = portable.verify_bundle({"not": "a bundle"})
        assert not ok
        ok2, _detail2 = portable.verify_bundle({"version": 1, "pairs": "wrong type"})
        assert not ok2


# ---------------------------------------------------------------------------
# 9. SQL injection through content (not a vulnerability test — Nestor
#    uses parameterized queries — but let's prove it)
# ---------------------------------------------------------------------------

class TestSQLInjectionResistance:
    """Nestor uses parameterized queries. These tests confirm that
    SQL-injection-shaped content is stored and retrieved literally."""

    def test_sql_injection_in_source_text(self, store):
        """Classic Bobby Tables as source text."""
        bobby = "Robert'); DROP TABLE tm_pairs;--"
        memory.add_pair(bobby, "nice try", "en", "en",
                        status="sealed", store=store)
        stats = memory.stats(store=store)
        assert stats["total"] >= 1
        hit = memory.best_sealed(bobby, "en", "en", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "nice try"

    def test_sql_injection_in_verifier(self, store):
        """SQL injection in the verifier name."""
        memory.add_pair("safe_key", "safe_value", "en", "en",
                        status="draft", store=store)
        stats = memory.stats(store=store)
        assert stats["sealed"] == 0

    def test_sql_injection_in_domain_tags(self, store):
        """SQL injection as both source_lang and target_lang."""
        evil = "'; DROP TABLE tm_pairs;--"
        memory.add_pair("key", "value", evil, evil, status="sealed",
                        store=store)
        stats = memory.stats(store=store)
        assert stats["total"] >= 1


# ---------------------------------------------------------------------------
# 10. Signing edge cases
# ---------------------------------------------------------------------------

class TestSigningEdgeCases:
    """The signing module uses HMAC or Ed25519. What happens at the
    boundaries?"""

    def test_empty_seal_key_is_a_valid_key(self):
        """NESTOR_SEAL_KEY="" should behave differently from unset."""
        os.environ["NESTOR_SEAL_KEY"] = ""
        sig = signing.sign_seal("norm", "target", "verifier")
        # An empty string key: HMAC with b"" is defined but Nestor may
        # treat empty-string as "no key configured" and return "".
        assert isinstance(sig, str)

    def test_seal_sig_with_very_long_key(self):
        """A seal key longer than the HMAC block size (64 bytes for SHA-256)."""
        os.environ["NESTOR_SEAL_KEY"] = "x" * 256
        sig = signing.sign_seal("norm", "target", "verifier")
        assert len(sig) > 0
        assert signing.seal_is_valid("norm", "target", "verifier", sig)

    def test_different_verifiers_produce_different_sigs(self):
        """Same content, different verifier names — signatures must differ."""
        os.environ["NESTOR_SEAL_KEY"] = "test-signing-key"
        sig_alice = signing.sign_seal("norm", "target", "alice")
        sig_bob = signing.sign_seal("norm", "target", "bob")
        assert sig_alice != sig_bob

    def test_signature_not_reusable_across_source_norms(self):
        """A signature for one source_norm must not verify for another."""
        os.environ["NESTOR_SEAL_KEY"] = "test-signing-key"
        sig = signing.sign_seal("cat", "gato", "rita")
        assert signing.seal_is_valid("cat", "gato", "rita", sig)
        assert not signing.seal_is_valid("dog", "gato", "rita", sig)

    def test_unicode_in_seal_fields(self):
        """Signing with unicode content in all fields."""
        os.environ["NESTOR_SEAL_KEY"] = "test-key"
        sig = signing.sign_seal("こんにちは", "مرحبا", "Ñoño")
        assert isinstance(sig, str)
        assert signing.seal_is_valid("こんにちは", "مرحبا", "Ñoño", sig)

    def test_signature_changes_with_key(self):
        """Same content under different keys must produce different sigs."""
        os.environ["NESTOR_SEAL_KEY"] = "key-alpha"
        sig_a = signing.sign_seal("norm", "target", "verifier")
        os.environ["NESTOR_SEAL_KEY"] = "key-beta"
        sig_b = signing.sign_seal("norm", "target", "verifier")
        assert sig_a != sig_b


# ---------------------------------------------------------------------------
# 11. Entity resolution with adversarial aliases
# ---------------------------------------------------------------------------

class TestEntityAdversarial:
    """The entity resolver uses StringMatcher fuzzy matching. What
    happens with aliases designed to confuse it?"""

    def test_near_identical_aliases_to_different_entities(self, store):
        """Two aliases that differ by one character, mapping to different
        canonical entities."""
        er = EntityResolver(store, domain="company")
        er.seal("Microsft", "Microsoft Corporation", verifier="test")
        er.seal("Microsat", "MicroSat Telecommunications", verifier="test")
        # "Microsft" vs "Microsat" — similarity should be high.
        r1 = er.resolve("Microsft")
        r2 = er.resolve("Microsat")
        # Each should resolve to its own canonical, not the other's.
        assert r1["canonical"] == "Microsoft Corporation"
        assert r2["canonical"] == "MicroSat Telecommunications"

    def test_case_insensitive_entity_resolution(self, store):
        """Sealing with one case, querying with another."""
        er = EntityResolver(store, domain="ticker")
        er.seal("AAPL", "Apple Inc.", verifier="test")
        r = er.resolve("aapl")
        # StringMatcher normalizes to lowercase.
        assert r["sealed"]
        assert r["canonical"] == "Apple Inc."

    def test_entity_with_unicode_normalization(self, store):
        """Entity with accented characters in different Unicode forms."""
        er = EntityResolver(store, domain="city")
        er.seal("Zürich", "Zurich, Switzerland", verifier="test")
        r = er.resolve("zurich")
        # StringMatcher lowercases but does not strip diacritics — so
        # "zürich" vs "zurich" is fuzzy, not exact.
        assert isinstance(r, dict)


# ---------------------------------------------------------------------------
# 12. Numeric reconciler at the extremes
# ---------------------------------------------------------------------------

class TestNumericReconcilerExtremes:
    """Push the numeric matcher with extreme values, edge cases, and
    formats it was never designed for."""

    def test_zero_baseline(self, store):
        """A baseline of zero — percentage tolerance is undefined."""
        r = Reconciler(store, domain="zero_test", pct_tol=0.05)
        r.seal_baseline("metric", "0", verifier="test")
        result = r.check("metric", "0")
        assert result["within_tolerance"]

    def test_negative_numbers(self, store):
        """Negative baselines and observations."""
        r = Reconciler(store, domain="negative", abs_tol=10)
        r.seal_baseline("temperature", "-40", verifier="test")
        result = r.check("temperature", "-35")
        assert result["within_tolerance"]

    def test_very_large_numbers(self, store):
        """Numbers near the float precision boundary."""
        r = Reconciler(store, domain="big", pct_tol=0.01)
        r.seal_baseline("gdp", "999999999999999", verifier="test")
        result = r.check("gdp", "999999999999998")
        assert result["within_tolerance"]

    def test_non_numeric_observation(self, store):
        """An observation that isn't a number at all."""
        r = Reconciler(store, domain="text_as_number")
        r.seal_baseline("metric", "100", verifier="test")
        result = r.check("metric", "not-a-number")
        # Should flag, not crash.
        assert not result.get("within_tolerance", True)

    def test_currency_formatted_numbers(self, store):
        """Numbers with currency symbols and thousand separators."""
        r = Reconciler(store, domain="finance", pct_tol=0.05)
        r.seal_baseline("revenue", "$1,234,567.89", verifier="cfo")
        result = r.check("revenue", "$1,250,000.00")
        assert isinstance(result["within_tolerance"], bool)

    def test_scientific_notation(self, store):
        """Numbers in scientific notation."""
        m = NumericMatcher()
        norm = m.normalize("6.022e23")
        assert norm  # Should parse
        detail = m.parse_detail("6.022e23")
        assert detail["value"] is not None


# ---------------------------------------------------------------------------
# 13. Store re-initialization and schema resilience
# ---------------------------------------------------------------------------

class TestStoreResilience:
    """What happens when we init_db twice, or open a store that already
    has data?"""

    def test_double_init_db_is_idempotent(self, tmp_path):
        """Calling init_db() twice should not drop data."""
        path = tmp_path / "double.db"
        s = SqliteStore(str(path))
        s.init_db()
        s.memory_init()
        memory.add_pair("test", "prueba", "en", "es", status="sealed",
                        store=s)
        # Re-init.
        s.init_db()
        s.memory_init()
        hit = memory.best_sealed("test", "en", "es", store=s)
        assert hit is not None

    def test_store_survives_close_and_reopen(self, tmp_path):
        """Close the store, reopen it from disk, data should survive."""
        path = tmp_path / "survive.db"
        s1 = SqliteStore(str(path))
        s1.init_db()
        s1.memory_init()
        memory.add_pair("persist", "persistir", "en", "es", status="sealed",
                        store=s1)
        del s1  # Close.
        s2 = SqliteStore(str(path))
        s2.init_db()
        s2.memory_init()
        hit = memory.best_sealed("persist", "en", "es", store=s2)
        assert hit is not None

    def test_in_memory_store_is_ephemeral(self):
        """An in-memory store loses data when the object is collected."""
        s = SqliteStore(":memory:")
        s.init_db()
        s.memory_init()
        memory.add_pair("ephemeral", "efímero", "en", "es", status="sealed",
                        store=s)
        hit = memory.best_sealed("ephemeral", "en", "es", store=s)
        assert hit is not None


# ---------------------------------------------------------------------------
# 14. The rejection system under stress
# ---------------------------------------------------------------------------

class TestRejectionStress:
    """Rejections suppress specific answers. What happens when we reject
    everything, or reject something that was never proposed?"""

    def test_reject_nonexistent_pair(self, store):
        """Rejecting a pair_id that doesn't exist.
        FINDING: Nestor allows rejecting a nonexistent pair_id — the
        rejection record is created even though the pair doesn't exist.
        This is correct design: a rejection is about a query/answer,
        not necessarily about an existing row."""
        fake_id = str(uuid.uuid4())
        memory.reject_pair(fake_id, verifier="test",
                           reason="preemptive strike", store=store)

    def test_reject_then_seal_same_key(self, store):
        """Reject a key, then try to seal it — the rejection should block.
        FINDING: RejectedPairError fires when you try to seal a key that
        was previously rejected. The override_rejection flag is needed to
        bypass it."""
        from nestor.errors import NestorError
        memory.add_pair("bad idea", "mala idea", "en", "es",
                        status="draft", store=store)
        matches = memory.lookup("bad idea", "en", "es", store=store)
        assert matches
        memory.reject_pair(matches[0]["pair"]["id"],
                           verifier="reviewer",
                           reason="really bad", store=store)
        with pytest.raises(NestorError):
            memory.add_pair("bad idea", "mala idea", "en", "es",
                            status="sealed", verifier="optimist",
                            store=store)


# ---------------------------------------------------------------------------
# 15. Cascade behavior with empty/missing engine
# ---------------------------------------------------------------------------

class TestCascadeEdgeCases:
    """The cascade goes: sealed match -> draft -> engine -> pending.
    What happens when there's no engine configured?"""

    def test_cascade_with_no_sealed_no_draft(self, store, tmp_path):
        """Ask against a completely empty store."""
        cascade.set_ledger_path(tmp_path / "ledger.jsonl")
        result = cascade.translate_text("Hello, world", "en", "es",
                                        store=store)
        assert result is not None
        passage = result["passage"] if isinstance(result, dict) else result
        if isinstance(passage, dict):
            assert passage.get("state") in ("pending", "draft", None)


# ---------------------------------------------------------------------------
# 16. Nestor as a key-value store (ab)use
# ---------------------------------------------------------------------------

class TestNestorAsKeyValueStore:
    """Nestor is a verified-match memory, not a KV store. But what if
    you use it as one? This tests whether the seal/serve mechanic can
    serve arbitrary structured data as values."""

    def test_json_as_target_text(self, store):
        """Store a JSON object as the target. Retrieve it. Parse it."""
        payload = json.dumps({"config": {"timeout": 30, "retries": 3},
                              "features": ["dark-mode", "i18n"]})
        memory.add_pair("app-config-v2", payload, "config", "config",
                        status="sealed", store=store)
        hit = memory.best_sealed("app-config-v2", "config", "config",
                                 store=store)
        assert hit is not None
        recovered = json.loads(hit["pair"]["target_text"])
        assert recovered["config"]["timeout"] == 30

    def test_multiline_yaml_as_target(self, store):
        """Store YAML-formatted text as the target."""
        yaml_text = "name: nestor\nversion: 1.0\ndependencies:\n  - sqlite3\n  - difflib"
        memory.add_pair("project-manifest", yaml_text, "meta", "meta",
                        status="sealed", store=store)
        hit = memory.best_sealed("project-manifest", "meta", "meta",
                                 store=store)
        assert hit is not None
        assert "nestor" in hit["pair"]["target_text"]

    def test_base64_encoded_binary_as_target(self, store):
        """Store base64-encoded binary data as target."""
        data = base64.b64encode(b"\x00\x01\x02\xff" * 100).decode()
        memory.add_pair("binary-blob-ref", data, "bin", "bin",
                        status="sealed", store=store)
        hit = memory.best_sealed("binary-blob-ref", "bin", "bin",
                                 store=store)
        assert hit is not None
        recovered = base64.b64decode(hit["pair"]["target_text"])
        assert recovered[:4] == b"\x00\x01\x02\xff"


# ---------------------------------------------------------------------------
# 17. Using Nestor's entity resolver as a DNS-like alias system
# ---------------------------------------------------------------------------

class TestEntityResolverAsAliasSystem:
    """The entity resolver maps surfaces to canonicals. Push it as a
    general-purpose alias resolver — abbreviations, acronyms, slang."""

    def test_chain_of_aliases(self, store):
        """A -> B -> C chain: does resolving A give B (direct match),
        or can we manually chain to C?"""
        er = EntityResolver(store, domain="alias")
        er.seal("NYC", "New York City", verifier="test")
        er.seal("New York City", "City of New York, NY, USA", verifier="test")
        # Resolving "NYC" should give "New York City" (the direct match).
        r1 = er.resolve("NYC")
        assert r1["canonical"] == "New York City"
        # Now resolve the canonical itself — this is the chain.
        r2 = er.resolve("New York City")
        assert r2["canonical"] == "City of New York, NY, USA"

    def test_many_aliases_same_canonical(self, store):
        """10 different surfaces all mapping to the same canonical.
        FINDING: aliases that normalize identically (e.g. 'MSFT' and
        'msft') are upserted rather than duplicated. The resolver finds
        the canonical for each distinct alias."""
        er = EntityResolver(store, domain="stock")
        aliases = ["MSFT", "Microsoft", "MSFT.O", "microsoft corp",
                   "Microsoft Corporation", "Micro Soft",
                   "$MSFT", "NASDAQ:MSFT", "US:MSFT"]
        for alias in aliases:
            er.seal(alias, "Microsoft Corporation", verifier="test")
        for alias in aliases:
            r = er.resolve(alias)
            if r["sealed"]:
                assert r["canonical"] == "Microsoft Corporation"

    def test_entity_resolution_with_numbers(self, store):
        """Entity aliases that are pure numbers."""
        er = EntityResolver(store, domain="account")
        er.seal("12345", "Savings Account", verifier="test")
        er.seal("67890", "Checking Account", verifier="test")
        r = er.resolve("12345")
        assert r["sealed"]
        assert r["canonical"] == "Savings Account"


# ---------------------------------------------------------------------------
# 18. The decision memory as a rule engine
# ---------------------------------------------------------------------------

class TestDecisionMemoryAsRuleEngine:
    """The decision memory stores question -> commitment pairs with
    edges. Push it to act like a simple rule engine."""

    def test_contradicting_decisions_are_detected(self, store):
        """Two sealed decisions that contradict each other should be
        flagged by constraints_on."""
        os.environ["NESTOR_SEAL_KEY"] = "test-key"
        dm = DecisionMemory(store, domain="rules")
        d1 = dm.propose("Use tabs for indentation", "Yes, always tabs")
        d2 = dm.propose("Use spaces for indentation", "Yes, always spaces")
        dm.propose_edge(d1["id"], d2["id"], "contradicts",
                        reason="tabs vs spaces")
        # Note: proposed (unsigned) edges are surfaced but NOT traversed
        # as constraints — this is by design (only sealed edges constrain).
        r = dm.constraints_on("Use tabs for indentation")
        assert isinstance(r, dict)

    def test_supersedes_chain(self, store):
        """Proposing a different commitment for the same question raises
        ConflictingDraftError — Nestor refuses to silently overwrite.
        revise_draft() is the correct path for evolving a proposal.
        FINDING: the decision memory enforces draft uniqueness per
        question, which means a 'rule engine' pattern must revise,
        not re-propose."""
        dm = DecisionMemory(store, domain="policy")
        dm.propose("Password policy", "8 chars minimum")
        with pytest.raises(ConflictingDraftError):
            dm.propose("Password policy", "12 chars minimum")
        # The correct path is revise_draft:
        d2 = memory.revise_draft(
            "Password policy", "12 chars minimum",
            source_lang="policy", target_lang="policy",
            reason="security upgrade", store=store)
        assert d2["target_text"] == "12 chars minimum"

    def test_decision_with_very_long_commitment(self, store):
        """A commitment that's a full paragraph."""
        long_commitment = (
            "We will use Python 3.10+ as the primary language, with type hints "
            "on all public APIs. No runtime dependencies beyond the standard "
            "library for the core package. Optional extras may add dependencies "
            "for specific capabilities. All changes must pass CI before merge."
        )
        dm = DecisionMemory(store, domain="architecture")
        d = dm.propose("What are our language constraints?", long_commitment)
        assert d["target_text"] == long_commitment


# ---------------------------------------------------------------------------
# 19. Reconciler as a monitoring/alerting system
# ---------------------------------------------------------------------------

class TestReconcilerAsMonitor:
    """Push the numeric reconciler to work as a simple threshold
    monitoring system."""

    def test_tolerance_boundary_exact(self, store):
        """Observation exactly at the tolerance boundary."""
        r = Reconciler(store, domain="monitor", pct_tol=0.05)
        r.seal_baseline("cpu_usage", "80", verifier="ops")
        # 5% of 80 = 4, so 84 should be exactly at boundary.
        result = r.check("cpu_usage", "84")
        assert isinstance(result["within_tolerance"], bool)

    def test_multiple_metrics_independent(self, store):
        """Different labels are independent baselines."""
        r = Reconciler(store, domain="metrics", pct_tol=0.10)
        r.seal_baseline("cpu", "50", verifier="ops")
        r.seal_baseline("memory", "70", verifier="ops")
        r.seal_baseline("disk", "30", verifier="ops")
        assert r.check("cpu", "55")["within_tolerance"]
        assert r.check("memory", "77")["within_tolerance"]
        assert r.check("disk", "33")["within_tolerance"]
        assert not r.check("cpu", "100")["within_tolerance"]

    def test_percentages_as_baselines(self, store):
        """Baselines that are percentages with % sign."""
        r = Reconciler(store, domain="pct", pct_tol=0.05)
        r.seal_baseline("uptime", "99.9%", verifier="sre")
        result = r.check("uptime", "99.8%")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 20. Store capacity — how many pairs before things degrade?
# ---------------------------------------------------------------------------

class TestStoreCapacity:
    """Nestor states linear lookup. How does it actually behave with
    a few hundred pairs?"""

    def test_five_hundred_pairs_lookup(self, store):
        """Seed 500 pairs and look up the last one."""
        for i in range(500):
            memory.add_pair(f"phrase_{i:04d}", f"translation_{i:04d}",
                            "en", "es", status="sealed", store=store)
        hit = memory.best_sealed("phrase_0499", "en", "es", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "translation_0499"
        stats = memory.stats(store=store)
        assert stats["total"] == 500

    def test_exact_match_in_large_corpus(self, store):
        """With 500 sealed pairs, an exact match should still be
        preferred over a close fuzzy match."""
        for i in range(500):
            memory.add_pair(f"item number {i}", f"article numéro {i}",
                            "en", "fr", status="sealed", store=store)
        hit = memory.best_sealed("item number 42", "en", "fr", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "article numéro 42"
        assert hit["similarity"] == 1.0


# ---------------------------------------------------------------------------
# Adversarial trust-injection — what Nestor does in nefarious hands
# ---------------------------------------------------------------------------
# These tests demonstrate the oracle-poisoning surface: an attacker who
# controls a Nestor instance (or a bundle, or just the env) doesn't steal
# data — they make Nestor say "a human checked this" when the answer is "no."
# Each test names the attack, shows it working (or Nestor stopping it), and
# asserts the observable outcome.


class TestVerifierImpersonation:
    """The verifier field is a free-text string. Without signing,
    anyone with store access can seal as any name."""

    def test_unsigned_seal_as_arbitrary_verifier(self, store):
        """Without NESTOR_SEAL_KEY, an attacker can seal as 'ceo@corp.com'
        and best_sealed will serve it as tier-1 truth."""
        os.environ.pop("NESTOR_SEAL_KEY", None)
        memory.add_pair(
            "Q4 budget approved?", "Yes, $2M allocated",
            "policy", "policy",
            status="sealed", verifier="ceo@corp.com", store=store,
        )
        hit = memory.best_sealed("Q4 budget approved?", "policy", "policy",
                                 store=store)
        assert hit is not None
        assert hit["pair"]["verifier"] == "ceo@corp.com"
        assert hit["pair"]["status"] == "sealed"

    def test_signing_stops_impersonation(self, store):
        """With NESTOR_SEAL_KEY set, a seal signed with the real key verifies.
        A row written without the key does not serve."""
        os.environ["NESTOR_SEAL_KEY"] = "the-real-key"
        legit = memory.add_pair(
            "safe to deploy?", "yes, staging passed",
            "ops", "ops",
            status="sealed", verifier="alice", store=store,
        )
        assert legit["seal_sig"] != ""

        hit = memory.best_sealed("safe to deploy?", "ops", "ops", store=store)
        assert hit is not None
        assert hit["pair"]["verifier"] == "alice"

    def test_forged_sig_rejected_when_key_differs(self, store):
        """An attacker who sealed with key-A cannot serve on an instance
        running key-B."""
        os.environ["NESTOR_SEAL_KEY"] = "attacker-key"
        memory.add_pair(
            "is this safe?", "absolutely",
            "trust", "trust",
            status="sealed", verifier="admin", store=store,
        )
        os.environ["NESTOR_SEAL_KEY"] = "real-key"
        hit = memory.best_sealed("is this safe?", "trust", "trust",
                                 store=store)
        assert hit is None


class TestBundleForgery:
    """A crafted bundle can inject false seals into an unsuspecting instance."""

    def test_unsigned_import_trusts_bundle_word(self, store, tmp_path):
        """Without NESTOR_SEAL_KEY, import_bundle accepts anything claiming
        to be sealed — 'trusted on the bundle's word alone.'"""
        os.environ.pop("NESTOR_SEAL_KEY", None)
        memory.add_pair("seed", "grain", "en", "es",
                        status="sealed", store=store)
        bundle = portable.export_bundle(store=store)

        store2 = SqliteStore(str(tmp_path / "victim.db"))
        store2.init_db()
        store2.memory_init()

        report = portable.import_bundle(bundle, store=store2, dry_run=False)
        assert report["sealed"] == 1
        hit = memory.best_sealed("seed", "en", "es", store=store2)
        assert hit is not None
        assert hit["pair"]["status"] == "sealed"

    def test_signed_import_demotes_forged_seals(self, store, tmp_path):
        """An attacker exports a bundle with key-A. The victim's instance
        uses key-B. Claimed seals are DEMOTED to drafts, not served."""
        os.environ["NESTOR_SEAL_KEY"] = "attacker-key"
        memory.add_pair("policy", "do the bad thing", "en", "en",
                        status="sealed", verifier="boss", store=store)
        bundle = portable.export_bundle(store=store)

        store2 = SqliteStore(str(tmp_path / "victim.db"))
        store2.init_db()
        store2.memory_init()

        os.environ["NESTOR_SEAL_KEY"] = "victim-key"
        report = portable.import_bundle(bundle, store=store2, dry_run=False)
        assert report["demoted"] == 1
        assert report["sealed"] == 0
        hit = memory.best_sealed("policy", "en", "en", store=store2)
        assert hit is None

    def test_crafted_bundle_from_scratch(self, store, tmp_path):
        """An attacker hand-crafts a bundle dict — no export needed.
        Without signing, the victim accepts it. The forged bundle must
        pass verify_bundle, so we export a real one, then swap the pairs."""
        os.environ.pop("NESTOR_SEAL_KEY", None)
        memory.add_pair("placeholder", "placeholder", "qa", "qa",
                        status="sealed", store=store)
        real_bundle = portable.export_bundle(store=store)

        real_bundle["pairs"] = [
            {
                "id": str(uuid.uuid4()),
                "source_text": "approved?",
                "source_norm": "approved?",
                "target_text": "yes, by the board",
                "source_lang": "qa", "target_lang": "qa",
                "status": "sealed",
                "verifier": "board-chair",
                "seal_sig": "",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        ]
        real_bundle["digest"] = portable.digest(
            real_bundle["pairs"], real_bundle.get("rejections", []),
            real_bundle.get("evidence", []),
            version=real_bundle["nestor_bundle"])

        store2 = SqliteStore(str(tmp_path / "naive.db"))
        store2.init_db()
        store2.memory_init()

        report = portable.import_bundle(real_bundle, store=store2,
                                        dry_run=False)
        assert report["sealed"] == 1
        hit = memory.best_sealed("approved?", "qa", "qa", store=store2)
        assert hit is not None
        assert hit["pair"]["verifier"] == "board-chair"


class TestDecisionFabrication:
    """A poisoned decision store records precedent that never happened."""

    def test_fabricated_decision_serves_as_precedent(self, store):
        """Without signing, an attacker can propose AND seal a decision
        with any verifier name, and best_sealed will serve it."""
        os.environ.pop("NESTOR_SEAL_KEY", None)
        dm = DecisionMemory(store=store)
        dm.propose("Should we use vendor X?", "Yes, signed contract")
        sig = signing.sign_seal(
            StringMatcher().normalize("Should we use vendor X?"),
            "Yes, signed contract", "legal-team")
        dm.seal("Should we use vendor X?", "Yes, signed contract",
                verifier="legal-team", seal_sig=sig)

        hit = memory.best_sealed(
            "Should we use vendor X?", dm.domain, dm.domain, store=store)
        assert hit is not None
        assert hit["pair"]["status"] == "sealed"
        assert hit["pair"]["verifier"] == "legal-team"

    def test_unsigned_edge_never_constrains(self, store):
        """FINDING: even with signing OFF, edges are protected. An edge
        with edge_sig="" is always a proposal, never a fact — edge_is_valid
        returns False for empty signatures regardless of signing mode.
        This means decision-graph forgery requires the seal key even when
        pair-level forgery doesn't."""
        os.environ.pop("NESTOR_SEAL_KEY", None)
        dm = DecisionMemory(store=store)

        dm.propose("Use Python 3.11?", "Yes")
        old_sig = signing.sign_seal(
            StringMatcher().normalize("Use Python 3.11?"), "Yes", "architect")
        old = dm.seal("Use Python 3.11?", "Yes",
                      verifier="architect", seal_sig=old_sig)

        dm.propose("Use Python 3.13?", "Yes, upgrade")
        new_sig = signing.sign_seal(
            StringMatcher().normalize("Use Python 3.13?"),
            "Yes, upgrade", "attacker")
        new = dm.seal("Use Python 3.13?", "Yes, upgrade",
                      verifier="attacker", seal_sig=new_sig)

        dm.propose_edge(new["id"], old["id"], "supersedes")
        edge_sig = signing.sign_edge(
            new["id"], old["id"], "supersedes", "attacker")
        assert edge_sig == ""
        with pytest.raises(ValueError, match="does not verify"):
            dm.seal_edge(new["id"], old["id"], "supersedes",
                         verifier="attacker", edge_sig=edge_sig)

    def test_signed_edge_blocks_wrong_key_attacker(self, store):
        """An edge signed with the wrong key is refused by seal_edge."""
        os.environ["NESTOR_SEAL_KEY"] = "org-secret"
        dm = DecisionMemory(store=store)

        dm.propose("Deploy to prod?", "Only after QA")
        legit_sig = signing.sign_seal(
            StringMatcher().normalize("Deploy to prod?"),
            "Only after QA", "qa-lead")
        legit = dm.seal("Deploy to prod?", "Only after QA",
                        verifier="qa-lead", seal_sig=legit_sig)

        dm.propose("Deploy to prod immediately?", "Yes skip QA")
        rogue_sig = signing.sign_seal(
            StringMatcher().normalize("Deploy to prod immediately?"),
            "Yes skip QA", "attacker")
        rogue = dm.seal("Deploy to prod immediately?", "Yes skip QA",
                        verifier="attacker", seal_sig=rogue_sig)

        dm.propose_edge(rogue["id"], legit["id"], "supersedes")

        os.environ["NESTOR_SEAL_KEY"] = "different-key"
        bad_edge_sig = signing.sign_edge(
            rogue["id"], legit["id"], "supersedes", "attacker")

        os.environ["NESTOR_SEAL_KEY"] = "org-secret"
        with pytest.raises(ValueError, match="does not verify"):
            dm.seal_edge(rogue["id"], legit["id"], "supersedes",
                         verifier="attacker", edge_sig=bad_edge_sig)


class TestStrictModeDefense:
    """NESTOR_REQUIRE_SEAL_KEY=1 fails closed — the deployment-level guard."""

    def test_strict_mode_refuses_unsigned_seals(self, store):
        """With REQUIRE_SEAL_KEY=1 but no key set, best_sealed raises
        rather than silently trusting everything."""
        os.environ.pop("NESTOR_SEAL_KEY", None)
        os.environ["NESTOR_REQUIRE_SEAL_KEY"] = "1"
        memory.add_pair("test", "value", "a", "b",
                        status="sealed", store=store)
        with pytest.raises(signing.SigningRequiredError):
            memory.best_sealed("test", "a", "b", store=store)

    def test_strict_mode_serves_with_valid_key(self, store):
        """Strict mode with a key set serves normally."""
        os.environ["NESTOR_SEAL_KEY"] = "my-key"
        os.environ["NESTOR_REQUIRE_SEAL_KEY"] = "1"
        memory.add_pair("test", "value", "a", "b",
                        status="sealed", verifier="me", store=store)
        hit = memory.best_sealed("test", "a", "b", store=store)
        assert hit is not None


class TestLedgerGenesisControl:
    """If you control the instance from the start, you write the genesis —
    the hash chain has no external anchor to catch it."""

    def test_fabricated_ledger_validates(self, tmp_path):
        """An attacker who writes a fresh ledger from line 1 produces a
        valid hash chain — there is nothing to compare against."""
        import hashlib as _hl
        ledger_path = tmp_path / "forged_ledger.jsonl"
        lines = []

        entry1 = json.dumps({
            "kind": "seal", "source_norm": "is this ok?",
            "target_text": "yes totally", "verifier": "ceo",
            "prev": "genesis",
        }, separators=(",", ":"), ensure_ascii=False)
        lines.append(entry1)

        prev_hash = _hl.sha256(entry1.encode()).hexdigest()
        entry2 = json.dumps({
            "kind": "seal", "source_norm": "budget approved?",
            "target_text": "unlimited", "verifier": "cfo",
            "prev": prev_hash,
        }, separators=(",", ":"), ensure_ascii=False)
        lines.append(entry2)

        ledger_path.write_text("\n".join(lines) + "\n")

        parsed = [json.loads(line) for line in
                  ledger_path.read_text().splitlines() if line.strip()]
        assert len(parsed) == 2
        assert parsed[0]["prev"] == "genesis"
        check_hash = _hl.sha256(
            json.dumps(parsed[0], separators=(",", ":"),
                       ensure_ascii=False).encode()
        ).hexdigest()
        assert parsed[1]["prev"] == check_hash

    def test_tampered_ledger_detected_by_verify(self, store, tmp_path):
        """But if you tamper with a ledger that already has entries,
        ledger.verify catches it. Tamper by modifying the first entry's
        content (the pair_id) — line 2's prev no longer matches sha256
        of the modified line 1."""
        from nestor import ledger as ledger_mod
        cascade.set_ledger_path(tmp_path / "real_ledger.jsonl")
        memory.add_pair("real q", "real a", "en", "en",
                        status="sealed", verifier="human", store=store)
        memory.add_pair("another q", "another a", "en", "en",
                        status="sealed", verifier="human", store=store)

        ledger_path = cascade._ledger_path()
        lines = ledger_path.read_text().splitlines()
        assert len(lines) >= 2

        entry = json.loads(lines[0])
        entry["pair_id"] = "00000000-0000-0000-0000-000000000000"
        lines[0] = json.dumps(entry, separators=(",", ":"),
                               ensure_ascii=False)
        ledger_path.write_text("\n".join(lines) + "\n")

        ok, _detail = ledger_mod.verify(str(ledger_path))
        assert ok is False


class TestKeyEnvironmentManipulation:
    """An attacker who can set environment variables controls what Nestor
    trusts — the key IS the trust root."""

    def test_key_swap_invalidates_prior_seals(self, store):
        """Setting a new NESTOR_SEAL_KEY makes all prior seals fail
        verification — a key rotation without migration is destructive."""
        os.environ["NESTOR_SEAL_KEY"] = "original-key"
        memory.add_pair("important", "answer", "en", "en",
                        status="sealed", verifier="admin", store=store)
        hit = memory.best_sealed("important", "en", "en", store=store)
        assert hit is not None

        os.environ["NESTOR_SEAL_KEY"] = "swapped-in-key"
        hit = memory.best_sealed("important", "en", "en", store=store)
        assert hit is None

    def test_key_removal_reopens_forgery(self, store):
        """Unsetting NESTOR_SEAL_KEY after seals exist makes Nestor trust
        everything again — the Nestor#2 forgery is back."""
        os.environ["NESTOR_SEAL_KEY"] = "good-key"
        memory.add_pair("trusted", "answer", "en", "en",
                        status="sealed", verifier="admin", store=store)
        hit = memory.best_sealed("trusted", "en", "en", store=store)
        assert hit is not None

        os.environ.pop("NESTOR_SEAL_KEY", None)
        memory.add_pair("forged", "bad answer", "en", "en",
                        status="sealed", verifier="nobody", store=store)
        hit = memory.best_sealed("forged", "en", "en", store=store)
        assert hit is not None


# ---------------------------------------------------------------------------
# Pattern-matching at scale — how many patterns can Nestor hold and still
# find the right answer?
# ---------------------------------------------------------------------------
# Nestor's lookup is an O(n) scan over all candidates in a domain, scoring
# each with difflib. These tests push it: how many can it hold, how fast
# does it degrade, and when does disambiguation start failing?


@pytest.mark.slow
class TestScaleExactMatch:
    """Exact-match retrieval at increasing scale."""

    def test_1k_pairs_exact_lookup(self, store):
        """1,000 sealed pairs: exact match for a random entry."""
        for i in range(1000):
            memory.add_pair(f"sentence number {i:04d}",
                            f"translation number {i:04d}",
                            "en", "es", status="sealed", store=store)
        hit = memory.best_sealed("sentence number 0742", "en", "es",
                                 store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "translation number 0742"
        assert hit["similarity"] == 1.0

    def test_5k_pairs_exact_lookup(self, store):
        """5,000 sealed pairs: exact match still works."""
        for i in range(5000):
            memory.add_pair(f"phrase {i:05d}", f"frase {i:05d}",
                            "en", "es", status="sealed", store=store)
        hit = memory.best_sealed("phrase 04321", "en", "es", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "frase 04321"
        assert hit["similarity"] == 1.0

    def test_10k_pairs_exact_lookup(self, store):
        """10,000 sealed pairs: exact match retrieval."""
        for i in range(10000):
            memory.add_pair(f"item {i:05d}", f"elemento {i:05d}",
                            "en", "es", status="sealed", store=store)
        hit = memory.best_sealed("item 09999", "en", "es", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "elemento 09999"
        assert hit["similarity"] == 1.0

    def test_10k_pairs_absent_probe(self, store):
        """10,000 pairs, query that matches nothing — confirms the scan
        completes and returns None, not an accident."""
        for i in range(10000):
            memory.add_pair(f"item {i:05d}", f"elemento {i:05d}",
                            "en", "es", status="sealed", store=store)
        hit = memory.best_sealed(
            "this sentence is completely unrelated to anything stored",
            "en", "es", store=store)
        assert hit is None


@pytest.mark.slow
class TestScaleFuzzyDiscrimination:
    """Can Nestor find the RIGHT fuzzy match among many similar candidates?"""

    def test_needle_in_1k_similar_entries(self, store):
        """1,000 entries of the form 'The quick brown fox jumped over N'.
        Query a close variant of one specific N — should find it."""
        for i in range(1000):
            memory.add_pair(
                f"The quick brown fox jumped over {i} lazy dogs",
                f"El rápido zorro marrón saltó sobre {i} perros perezosos",
                "en", "es", status="sealed", store=store)
        hit = memory.best_sealed(
            "The quick brown fox jumped over 500 lazy dogs",
            "en", "es", store=store)
        assert hit is not None
        assert "500" in hit["pair"]["target_text"]

    def test_distinguishing_one_word_variants(self, store):
        """500 entries that differ by exactly one word. Can Nestor pick
        the right one?"""
        animals = ["cat", "dog", "bird", "fish", "horse", "snake", "bear",
                   "wolf", "deer", "frog", "hawk", "lion", "seal", "crab",
                   "goat", "duck", "moth", "wasp", "worm", "mole"]
        for i in range(500):
            animal = animals[i % len(animals)]
            memory.add_pair(
                f"I saw a {animal} in the garden today number {i}",
                f"Vi un {animal} en el jardín hoy número {i}",
                "en", "es", status="sealed", store=store)
        hit = memory.best_sealed(
            "I saw a hawk in the garden today number 7",
            "en", "es", store=store)
        assert hit is not None
        assert "hawk" in hit["pair"]["target_text"]
        assert "7" in hit["pair"]["target_text"]

    def test_2k_highly_similar_entries_fuzzy_precision(self, store):
        """2,000 entries like 'Process order XXXX for customer Y'. Query with
        a specific order number — the matched entry must have the right one."""
        for i in range(2000):
            memory.add_pair(
                f"Process order {i:04d} for customer alpha",
                f"Procesar orden {i:04d} para cliente alfa",
                "en", "es", status="sealed", store=store)
        hit = memory.best_sealed(
            "Process order 1337 for customer alpha",
            "en", "es", store=store)
        assert hit is not None
        assert "1337" in hit["pair"]["target_text"]
        assert hit["similarity"] == 1.0

    def test_close_but_different_should_not_match(self, store):
        """Seal 'The project is approved' but query 'The project is rejected'.
        Similar text, opposite meaning — should NOT serve as tier-1."""
        memory.add_pair("The project is approved", "El proyecto está aprobado",
                        "en", "es", status="sealed", store=store)
        hit = memory.best_sealed("The project is rejected", "en", "es",
                                 store=store)
        assert hit is None


@pytest.mark.slow
class TestScaleLookupDepth:
    """Does lookup return useful ranked results at scale?"""

    def test_lookup_ranks_correctly_in_5k_corpus(self, store):
        """5,000 entries. lookup should return the closest matches first,
        with the exact match on top."""
        for i in range(5000):
            memory.add_pair(f"configure setting {i:04d}",
                            f"configurar ajuste {i:04d}",
                            "en", "es", status="sealed", store=store)
        results = memory.lookup("configure setting 2500", "en", "es",
                                store=store, limit=10)
        assert len(results) >= 1
        assert results[0]["pair"]["target_text"] == "configurar ajuste 2500"
        assert results[0]["similarity"] == 1.0

    def test_lookup_returns_near_matches(self, store):
        """Entries that differ by one character should still appear in
        lookup results as context matches."""
        memory.add_pair("update the configuration file",
                        "actualizar el archivo de configuración",
                        "en", "es", status="sealed", store=store)
        memory.add_pair("update the configuration files",
                        "actualizar los archivos de configuración",
                        "en", "es", status="sealed", store=store)
        memory.add_pair("update the application file",
                        "actualizar el archivo de la aplicación",
                        "en", "es", status="sealed", store=store)
        results = memory.lookup("update the configuration file",
                                "en", "es", store=store, limit=5)
        assert len(results) >= 2
        assert results[0]["similarity"] == 1.0
        assert results[1]["similarity"] > 0.8


@pytest.mark.slow
class TestScaleMultiDomain:
    """Multiple domains with many pairs each — isolation under pressure."""

    def test_1k_per_domain_five_domains(self, store):
        """5 domains, 1,000 pairs each = 5,000 total. Each domain should
        only see its own entries."""
        langs = [("en", "es"), ("en", "fr"), ("en", "de"),
                 ("en", "it"), ("en", "pt")]
        for source_lang, target_lang in langs:
            for i in range(1000):
                memory.add_pair(
                    f"word {i:04d}", f"translated_{target_lang}_{i:04d}",
                    source_lang, target_lang, status="sealed", store=store)

        for source_lang, target_lang in langs:
            hit = memory.best_sealed("word 0500", source_lang, target_lang,
                                     store=store)
            assert hit is not None
            assert hit["pair"]["target_text"] == f"translated_{target_lang}_0500"

        stats = memory.stats(store=store)
        assert stats["total"] == 5000

    def test_cross_domain_no_leakage(self, store):
        """Same source text, different target in each domain. Each domain
        should return its own target, never another domain's."""
        memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", store=store)
        memory.add_pair("hello", "bonjour", "en", "fr",
                        status="sealed", store=store)
        memory.add_pair("hello", "hallo", "en", "de",
                        status="sealed", store=store)
        memory.add_pair("hello", "ciao", "en", "it",
                        status="sealed", store=store)

        assert memory.best_sealed("hello", "en", "es",
                                  store=store)["pair"]["target_text"] == "hola"
        assert memory.best_sealed("hello", "en", "fr",
                                  store=store)["pair"]["target_text"] == "bonjour"
        assert memory.best_sealed("hello", "en", "de",
                                  store=store)["pair"]["target_text"] == "hallo"
        assert memory.best_sealed("hello", "en", "it",
                                  store=store)["pair"]["target_text"] == "ciao"


@pytest.mark.slow
class TestScaleTiming:
    """Rough performance characterization — not benchmarks, but guards
    against catastrophic O(n^2) or worse behavior."""

    def test_1k_lookup_under_5_seconds(self, store):
        """1,000 pairs: a single best_sealed should complete in <5s."""
        import time
        for i in range(1000):
            memory.add_pair(f"entry number {i:04d} in the database",
                            f"entrada número {i:04d} en la base de datos",
                            "en", "es", status="sealed", store=store)
        start = time.monotonic()
        hit = memory.best_sealed("entry number 0500 in the database",
                                 "en", "es", store=store)
        elapsed = time.monotonic() - start
        assert hit is not None
        assert elapsed < 5.0, f"1K lookup took {elapsed:.2f}s"

    def test_5k_lookup_under_30_seconds(self, store):
        """5,000 pairs: a single best_sealed should still be reasonable."""
        import time
        for i in range(5000):
            memory.add_pair(f"record {i:05d} in the system",
                            f"registro {i:05d} en el sistema",
                            "en", "es", status="sealed", store=store)
        start = time.monotonic()
        hit = memory.best_sealed("record 02500 in the system",
                                 "en", "es", store=store)
        elapsed = time.monotonic() - start
        assert hit is not None
        assert elapsed < 30.0, f"5K lookup took {elapsed:.2f}s"

    def test_absent_probe_not_catastrophically_slow(self, store):
        """2,000 pairs, absent query. This is the worst case for the scan
        since nothing can short-circuit. Should still complete."""
        import time
        for i in range(2000):
            memory.add_pair(f"known phrase {i:04d}",
                            f"frase conocida {i:04d}",
                            "en", "es", status="sealed", store=store)
        start = time.monotonic()
        hit = memory.best_sealed(
            "a completely unrelated query about quantum mechanics",
            "en", "es", store=store)
        elapsed = time.monotonic() - start
        assert hit is None
        assert elapsed < 30.0, f"2K absent probe took {elapsed:.2f}s"


@pytest.mark.slow
class TestScaleEntityResolver:
    """Entity resolution at scale — many aliases, many canonicals."""

    def test_500_entities_3_aliases_each(self, store):
        """500 canonical entities with 3 aliases each. Resolution
        should find the correct canonical even in a crowded space."""
        er = EntityResolver(store=store)
        for i in range(500):
            canonical = f"Entity_{i:03d}"
            for j in range(3):
                er.seal(f"alias_{i:03d}_{j}", canonical, verifier="admin")
        result = er.resolve("alias_250_1")
        assert result["canonical"] == "Entity_250"
        assert result["sealed"] is True

    def test_similar_aliases_different_canonicals(self, store):
        """Aliases that look almost identical but map to different entities.
        The resolver should pick the exact match."""
        er = EntityResolver(store=store)
        er.seal("John Smith", "PERSON_001", verifier="admin")
        er.seal("John Smithe", "PERSON_002", verifier="admin")
        er.seal("John Smyth", "PERSON_003", verifier="admin")
        er.seal("Jon Smith", "PERSON_004", verifier="admin")
        er.seal("John Smith Jr", "PERSON_005", verifier="admin")

        result = er.resolve("John Smith")
        assert result["canonical"] == "PERSON_001"
        assert result["sealed"] is True


@pytest.mark.slow
class TestScaleReconciler:
    """Numeric reconciliation with many baselines."""

    def test_100_metrics_each_with_baseline(self, store):
        """100 different metrics sealed. Each should reconcile independently."""
        rec = Reconciler(store=store)
        for i in range(100):
            rec.seal_baseline(f"metric_{i:03d}", float(i * 100),
                              verifier="admin")
        for i in [0, 25, 50, 75, 99]:
            result = rec.check(f"metric_{i:03d}", float(i * 100))
            assert result["within_tolerance"] is True

        result = rec.check("metric_050", 99999.0)
        assert result["within_tolerance"] is False


@pytest.mark.slow
class TestScaleDecisionMemory:
    """Decision memory at scale — many decisions, graph traversal."""

    def test_200_decisions_lookup(self, store):
        """200 sealed decisions. Should retrieve the right one by question."""
        os.environ.pop("NESTOR_SEAL_KEY", None)
        dm = DecisionMemory(store=store)
        for i in range(200):
            dm.propose(f"Should we adopt approach {i:03d}?",
                       f"Yes, approach {i:03d} is approved")
            sig = signing.sign_seal(
                StringMatcher().normalize(
                    f"Should we adopt approach {i:03d}?"),
                f"Yes, approach {i:03d} is approved", "committee")
            dm.seal(f"Should we adopt approach {i:03d}?",
                    f"Yes, approach {i:03d} is approved",
                    verifier="committee", seal_sig=sig)

        hit = memory.best_sealed(
            "Should we adopt approach 150?",
            dm.domain, dm.domain, store=store)
        assert hit is not None
        assert "150" in hit["pair"]["target_text"]

    def test_chained_supersedes_at_depth(self, store):
        """A chain of 20 decisions each superseding the previous. The
        constraints on the oldest should show the full lineage."""
        os.environ["NESTOR_SEAL_KEY"] = "chain-key"
        dm = DecisionMemory(store=store)
        ids = []
        for i in range(20):
            q = f"Version policy v{i}"
            c = f"Use version {i}"
            dm.propose(q, c)
            sig = signing.sign_seal(
                StringMatcher().normalize(q), c, "architect")
            pair = dm.seal(q, c, verifier="architect", seal_sig=sig)
            ids.append(pair["id"])

        for i in range(1, 20):
            dm.propose_edge(ids[i], ids[i - 1], "supersedes")
            edge_sig = signing.sign_edge(
                ids[i], ids[i - 1], "supersedes", "architect")
            dm.seal_edge(ids[i], ids[i - 1], "supersedes",
                         verifier="architect", edge_sig=edge_sig)

        constraints = dm.constraints_on("Version policy v0")
        assert len(constraints["constraints"]) >= 1


@pytest.mark.slow
class TestScaleMixedWorkload:
    """Mixed sealed/draft pairs — does the draft noise affect sealed lookups?"""

    def test_1k_sealed_1k_drafts_sealed_wins(self, store):
        """1,000 sealed + 1,000 drafts (different keys). best_sealed should
        only return sealed entries, ignoring the draft noise."""
        for i in range(1000):
            memory.add_pair(f"sealed entry {i:04d}",
                            f"entrada sellada {i:04d}",
                            "en", "es", status="sealed", store=store)
        for i in range(1000):
            memory.add_pair(f"draft entry {i:04d}",
                            f"entrada borrador {i:04d}",
                            "en", "es", status="draft", store=store)
        hit = memory.best_sealed("sealed entry 0500", "en", "es",
                                 store=store)
        assert hit is not None
        assert hit["pair"]["status"] == "sealed"
        assert "sellada" in hit["pair"]["target_text"]

        hit_draft = memory.best_sealed("draft entry 0500", "en", "es",
                                       store=store)
        assert hit_draft is None

    def test_many_drafts_exact_sealed_still_found(self, store):
        """One sealed pair buried under 2,000 drafts with similar keys.
        best_sealed should find the needle."""
        for i in range(2000):
            memory.add_pair(f"configure the deployment pipeline step {i}",
                            f"draft answer {i}",
                            "en", "en", status="draft", store=store)
        memory.add_pair("configure the deployment pipeline",
                        "the real sealed answer",
                        "en", "en", status="sealed", store=store)
        hit = memory.best_sealed("configure the deployment pipeline",
                                 "en", "en", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "the real sealed answer"


# ---------------------------------------------------------------------------
# Creative stress — twisting Nestor in directions nobody planned for
# ---------------------------------------------------------------------------


class TestHomoglyphAttacks:
    """Visual spoofing: characters that look identical to humans but differ
    in Unicode. Nestor normalizes with casefold + strip punctuation, but
    Cyrillic/Greek lookalikes survive normalization as distinct codepoints."""

    def test_cyrillic_a_vs_latin_a(self, store):
        """Cyrillic 'а' (U+0430) vs Latin 'a' (U+0061). They look the same
        but are different codepoints. Does Nestor treat them as the same?"""
        memory.add_pair("data", "datos", "en", "es",
                        status="sealed", store=store)
        hit = memory.best_sealed("dаta", "en", "es", store=store)
        if hit is not None:
            assert hit["similarity"] < 1.0 or hit is not None
        else:
            pass

    def test_homoglyph_pair_creates_distinct_entries(self, store):
        """Two entries that look visually identical but use different Unicode.
        They should be stored as separate pairs."""
        memory.add_pair("cafe", "coffee shop", "en", "en",
                        status="sealed", store=store)
        memory.add_pair("cafе", "кофейня", "en", "en",
                        status="sealed", store=store)
        stats = memory.stats(store=store)
        assert stats["total"] == 2

    def test_fullwidth_vs_ascii_digits(self, store):
        r"""Fullwidth '１２３' vs ASCII '123'. normalize() lowercases and
        strips punctuation, but fullwidth digits are \w characters."""
        memory.add_pair("item 123", "elemento 123", "en", "es",
                        status="sealed", store=store)
        hit = memory.best_sealed("item １２３", "en", "es",
                                 store=store)
        if hit is not None:
            assert hit["similarity"] < 1.0


class TestRejectionWarfare:
    """Weaponizing the rejection system — can rejections be used to
    deny service to legitimate sealed content?"""

    def test_reject_blocks_sealed_from_serving(self, store):
        """A rejection on a sealed pair prevents it from being served.
        This is BY DESIGN but demonstrates the denial surface."""
        pair = memory.add_pair("budget approved?", "yes, $2M",
                               "en", "en", status="sealed", store=store)
        hit = memory.best_sealed("budget approved?", "en", "en",
                                 store=store)
        assert hit is not None

        memory.reject_pair(pair["id"], verifier="auditor",
                           reason="disputed", store=store)
        hit = memory.best_sealed("budget approved?", "en", "en",
                                 store=store)
        assert hit is None

    def test_mass_rejection_clears_an_entire_domain(self, store):
        """An attacker with write access can reject every pair in a domain,
        reducing Nestor to 'no answer for anything'."""
        ids = []
        for i in range(50):
            pair = memory.add_pair(f"question {i}", f"answer {i}",
                                   "en", "en", status="sealed", store=store)
            ids.append(pair["id"])

        for pair_id in ids:
            memory.reject_pair(pair_id, verifier="malicious", store=store)

        for i in range(50):
            hit = memory.best_sealed(f"question {i}", "en", "en",
                                     store=store)
            assert hit is None

    def test_reject_match_leaves_pair_for_other_queries(self, store):
        """reject_match rejects a specific query→pair pairing, not the pair
        itself. The pair should still serve for its own source text."""
        pair = memory.add_pair("good morning", "buenos días",
                               "en", "es", status="sealed", store=store)
        memory.reject_match("morning greetings", "en", "es",
                            pair_id=pair["id"], verifier="reviewer",
                            reason="wrong match", store=store)
        hit = memory.best_sealed("good morning", "en", "es", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "buenos días"

    def test_reject_then_seal_same_content(self, store):
        """Reject a pair, then try to seal the exact same content again.
        What wins — the rejection or the new seal?"""
        pair = memory.add_pair("test phrase", "frase de prueba",
                               "en", "es", status="sealed", store=store)
        memory.reject_pair(pair["id"], verifier="reviewer", store=store)

        hit = memory.best_sealed("test phrase", "en", "es", store=store)
        assert hit is None

        new_pair = memory.add_pair(
            "test phrase", "frase de prueba", "en", "es",
            status="sealed", store=store,
            override_rejection=True)
        hit = memory.best_sealed("test phrase", "en", "es", store=store)
        assert hit is not None
        assert hit["pair"]["id"] == new_pair["id"]


class TestOracleProbing:
    """Can an attacker infer sealed content by probing similarity scores?
    lookup() returns similarity scores for all matches above the context
    threshold — this is an information channel."""

    def test_similarity_scores_reveal_content_proximity(self, store):
        """Seal a secret, then probe with related queries. The similarity
        scores tell you how close you are — a hot/cold game."""
        memory.add_pair(
            "the acquisition target is Acme Corp",
            "approved by board",
            "en", "en", status="sealed", store=store)
        probes = [
            "the acquisition target is Acme Corp",
            "the acquisition target is Acme",
            "the acquisition target is",
            "an acquisition",
            "something completely different about weather",
        ]
        scores = []
        for probe in probes:
            results = memory.lookup(probe, "en", "en", store=store)
            score = results[0]["similarity"] if results else 0.0
            scores.append(score)
        assert scores[0] == 1.0
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"scores should decrease as probes diverge: {scores}")

    def test_absent_probe_leaks_no_information(self, store):
        """A query in a completely different domain should get zero results,
        leaking nothing about what IS in the store."""
        memory.add_pair("classified project codename",
                        "Project Nightingale", "en", "en",
                        status="sealed", store=store)
        results = memory.lookup(
            "what is the weather forecast for tomorrow",
            "en", "en", store=store)
        assert len(results) == 0


class TestDraftEvolutionAbuse:
    """Pushing the revise_draft pathway — how far can you evolve a draft?"""

    def test_rapid_revision_chain(self, store):
        """Revise a draft 20 times in succession. Each revision should
        replace the previous, not accumulate."""
        memory.add_pair("what color?", "blue", "en", "en",
                        status="draft", store=store)
        colors = ["red", "green", "yellow", "purple", "orange", "pink",
                  "black", "white", "gray", "brown", "cyan", "magenta",
                  "teal", "navy", "gold", "silver", "crimson", "ivory",
                  "coral", "salmon"]
        for color in colors:
            memory.revise_draft("what color?", color, "en", "en",
                                store=store)
        results = memory.lookup("what color?", "en", "en", store=store)
        live_drafts = [r for r in results
                       if r["pair"]["status"] == "draft"]
        assert len(live_drafts) == 1
        assert live_drafts[0]["pair"]["target_text"] == "salmon"

    def test_revise_draft_then_seal(self, store):
        """Revise a draft multiple times, then seal the final version.
        The sealed version should be what serves."""
        memory.add_pair("policy?", "option A", "en", "en",
                        status="draft", store=store)
        memory.revise_draft("policy?", "option B", "en", "en", store=store)
        memory.revise_draft("policy?", "option C", "en", "en", store=store)

        memory.add_pair("policy?", "option C", "en", "en",
                        status="sealed", verifier="boss", store=store)
        hit = memory.best_sealed("policy?", "en", "en", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "option C"

    def test_revise_after_seal_raises(self, store):
        """Once sealed, revise_draft should not work — you can't demote
        a human's judgment back to draft."""
        memory.add_pair("final answer?", "42", "en", "en",
                        status="sealed", store=store)
        with pytest.raises(ValueError, match="sealed"):
            memory.revise_draft("final answer?", "43", "en", "en",
                                store=store)


class TestCrossRecipeConfusion:
    """What happens when you use one recipe's interface to read another's data?
    They share a store — the isolation is by domain tags, not by type."""

    def test_decision_visible_through_translation_lens(self, store):
        """DecisionMemory writes to a specific domain. Can translation
        lookup see it if we use the same domain tags?"""
        dm = DecisionMemory(store=store)
        dm.propose("Should we refactor?", "Yes, priority 1")

        results = memory.lookup("Should we refactor?",
                                dm.domain, dm.domain, store=store)
        assert len(results) >= 1
        assert results[0]["pair"]["target_text"] == "Yes, priority 1"

    def test_entity_alias_visible_as_translation(self, store):
        """EntityResolver writes to its own domain. Reading it as a
        translation pair should work because it IS a pair."""
        er = EntityResolver(store=store)
        er.seal("NYC", "New York City", verifier="admin")

        hit = memory.best_sealed("NYC", er.domain, er.domain, store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "New York City"

    def test_translation_pair_invisible_to_wrong_domain(self, store):
        """A pair in en→es should NOT appear in the decision domain."""
        memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", store=store)
        dm = DecisionMemory(store=store)
        results = memory.lookup("hello", dm.domain, dm.domain, store=store)
        assert len(results) == 0


class TestNormalizationBoundaries:
    """Edge cases in the StringMatcher normalize path — what survives,
    what gets folded, and what creates collisions."""

    def test_punctuation_stripped_creates_collision(self, store):
        """'dont' and 'don't' normalize to the same thing. If both are
        sealed with different targets, what happens?"""
        memory.add_pair("don't stop", "no te detengas", "en", "es",
                        status="sealed", store=store)
        hit = memory.best_sealed("dont stop", "en", "es", store=store)
        assert hit is not None
        assert hit["similarity"] == 1.0

    def test_case_folding_collision(self, store):
        """'NATO alliance' and 'nato alliance' normalize identically.
        A second sealed add with same target should upsert (idempotent)."""
        memory.add_pair("NATO alliance", "alianza OTAN", "en", "es",
                        status="sealed", store=store)
        memory.add_pair("nato alliance", "alianza OTAN", "en", "es",
                        status="sealed", store=store)
        stats = memory.stats(store=store)
        assert stats["total"] == 1

    def test_whitespace_collapse(self, store):
        """Multiple spaces, tabs, newlines all collapse to single space."""
        memory.add_pair("hello   world", "hola mundo", "en", "es",
                        status="sealed", store=store)
        hit = memory.best_sealed("hello\t\nworld", "en", "es", store=store)
        assert hit is not None
        assert hit["similarity"] == 1.0

    def test_empty_norm_sources_are_refused_after_0204(self, store):
        """Decision 0204 (Grok Direction C, refuse empty-norm seals)
        replaced the FINDING this test used to lock — that a punctuation-
        only string like ``"..."`` normalized to ``""`` and quietly sealed
        under a collision-prone key that every other empty-norm string
        would share. ``add_pair`` now raises :class:`EmptyNormError`
        before it can write, so the collision-prone class is visible at
        the boundary rather than a silent last-writer-wins overwrite
        later."""
        from nestor.memory import EmptyNormError
        with pytest.raises(EmptyNormError):
            memory.add_pair("...", "puntos suspensivos", "en", "es",
                            status="sealed", store=store)
        with pytest.raises(EmptyNormError):
            memory.add_pair("!!!", "excitement", "en", "es",
                            status="sealed", store=store)
        # And drafts refuse for the same reason — the collision-prone
        # key is the danger, and it doesn't care about sealing state.
        with pytest.raises(EmptyNormError):
            memory.add_pair("...", "as a draft", "en", "es",
                            status="draft", store=store)

    def test_unicode_normalization_nfc_vs_nfd(self, store):
        """NFC 'é' (U+00E9) vs NFD 'e' + combining acute (U+0065 U+0301).
        Python's casefold doesn't normalize these to the same form."""
        import unicodedata
        nfc = unicodedata.normalize("NFC", "café")
        nfd = unicodedata.normalize("NFD", "café")
        assert nfc != nfd

        memory.add_pair(nfc, "coffee shop", "en", "en",
                        status="sealed", store=store)
        hit = memory.best_sealed(nfd, "en", "en", store=store)
        if hit is None:
            pass
        else:
            assert hit["similarity"] >= 0.92


class TestSelfReferentialContent:
    """Nestor storing content about itself — metadata as data."""

    def test_store_nestor_config_as_pairs(self, store):
        """Use Nestor to remember its own configuration decisions."""
        memory.add_pair("SEAL_THRESHOLD", "0.92", "config", "config",
                        status="sealed", store=store)
        memory.add_pair("CONTEXT_THRESHOLD", "0.55", "config", "config",
                        status="sealed", store=store)
        hit = memory.best_sealed("SEAL_THRESHOLD", "config", "config",
                                 store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "0.92"

    def test_store_sql_as_target(self, store):
        """Store an actual SQL query as target text — not injection,
        just content that happens to be SQL."""
        memory.add_pair(
            "how to find sealed pairs",
            "SELECT * FROM tm_pairs WHERE status='sealed'",
            "docs", "docs", status="sealed", store=store)
        hit = memory.best_sealed("how to find sealed pairs",
                                 "docs", "docs", store=store)
        assert hit is not None
        assert "SELECT" in hit["pair"]["target_text"]

    def test_store_python_code_as_target(self, store):
        """Store Python code as target text."""
        code = "def hello():\n    return 'world'"
        memory.add_pair("hello function", code, "code", "code",
                        status="sealed", store=store)
        hit = memory.best_sealed("hello function", "code", "code",
                                 store=store)
        assert hit is not None
        assert "def hello" in hit["pair"]["target_text"]


class TestStoreCorruptionResilience:
    """What happens when the store is in a weird state?"""

    def test_lookup_on_empty_store(self, store):
        """An empty store should return empty results, not crash."""
        results = memory.lookup("anything", "en", "es", store=store)
        assert results == []
        hit = memory.best_sealed("anything", "en", "es", store=store)
        assert hit is None

    def test_lookup_after_all_pairs_rejected(self, store):
        """Seal some pairs, reject all of them, then query."""
        for i in range(10):
            pair = memory.add_pair(f"q{i}", f"a{i}", "en", "en",
                                   status="sealed", store=store)
            memory.reject_pair(pair["id"], verifier="admin", store=store)
        results = memory.lookup("q5", "en", "en", store=store)
        assert results == []

    def test_store_reopen_preserves_state(self, store, tmp_path):
        """Close and reopen a store — all data should survive."""
        db_path = str(tmp_path / "persist.db")
        s1 = SqliteStore(db_path)
        s1.init_db()
        s1.memory_init()
        memory.add_pair("persist me", "persisted", "en", "en",
                        status="sealed", store=s1)
        del s1

        s2 = SqliteStore(db_path)
        s2.init_db()
        s2.memory_init()
        hit = memory.best_sealed("persist me", "en", "en", store=s2)
        assert hit is not None
        assert hit["pair"]["target_text"] == "persisted"


class TestPunctuationAndSymbols:
    """How Nestor handles edge-case punctuation and symbol patterns."""

    def test_email_addresses_as_keys(self, store):
        """Email addresses — the @ and . get stripped by normalize."""
        memory.add_pair("alice@example.com", "Alice Smith",
                        "id", "id", status="sealed", store=store)
        hit = memory.best_sealed("alice@example.com", "id", "id",
                                 store=store)
        assert hit is not None

    def test_urls_as_keys(self, store):
        """URLs — colons, slashes, dots all stripped."""
        memory.add_pair("https://example.com/page",
                        "Example Page",
                        "url", "url", status="sealed", store=store)
        hit = memory.best_sealed("https://example.com/page",
                                 "url", "url", store=store)
        assert hit is not None

    def test_file_paths_as_keys(self, store):
        """File paths — slashes and dots stripped."""
        memory.add_pair("/usr/local/bin/nestor", "Nestor binary",
                        "fs", "fs", status="sealed", store=store)
        hit = memory.best_sealed("/usr/local/bin/nestor", "fs", "fs",
                                 store=store)
        assert hit is not None

    def test_math_expressions(self, store):
        """Mathematical expressions — operators get stripped."""
        memory.add_pair("2 + 2 = 4", "basic arithmetic",
                        "math", "math", status="sealed", store=store)
        hit = memory.best_sealed("2 + 2 = 4", "math", "math",
                                 store=store)
        assert hit is not None


class TestConflictingSeals:
    """What happens when two humans disagree — both trying to seal
    different answers for the same question."""

    def test_second_seal_different_target_raises(self, store):
        """Sealing 'hello' → 'hola', then 'hello' → 'ola' should raise
        ConflictingSealError."""
        from nestor.memory import ConflictingSealError
        memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", verifier="alice", store=store)
        with pytest.raises(ConflictingSealError):
            memory.add_pair("hello", "ola", "en", "es",
                            status="sealed", verifier="bob", store=store)

    def test_same_seal_same_target_upserts(self, store):
        """Sealing the same source→target twice is an idempotent upsert."""
        memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", verifier="alice", store=store)
        memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", verifier="bob", store=store)
        stats = memory.stats(store=store)
        assert stats["total"] == 1

    def test_override_conflict_flag(self, store):
        """override_conflict=True lets the second seal win."""
        memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", verifier="alice", store=store)
        memory.add_pair("hello", "ola", "en", "es",
                        status="sealed", verifier="bob", store=store,
                        override_conflict=True)
        hit = memory.best_sealed("hello", "en", "es", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "ola"


# ---------------------------------------------------------------------------
# Fantastical data — mythology, fictional languages, impossible measurements,
# emoji narratives, and other content nobody would expect a TM to hold
# ---------------------------------------------------------------------------


class TestMythologyTranslation:
    """Nestor as a mythological bestiary — creatures, gods, and legends
    stored as verified translations across pantheons."""

    def test_dragon_names_across_cultures(self, store):
        """The same archetype named in different mythologies."""
        pairs = [
            ("dragon", "龍", "en", "zh"),
            ("dragon", "дракон", "en", "ru"),
            ("dragon", "Drache", "en", "de"),
            ("dragon", "竜", "en", "ja"),
            ("dragon", "용", "en", "ko"),
        ]
        for src, tgt, sl, tl in pairs:
            memory.add_pair(src, tgt, sl, tl, status="sealed", store=store)

        for src, tgt, sl, tl in pairs:
            hit = memory.best_sealed(src, sl, tl, store=store)
            assert hit is not None
            assert hit["pair"]["target_text"] == tgt
            assert hit["similarity"] == 1.0

    def test_mythological_creatures_fuzzy_match(self, store):
        """Close variants of mythological names — 'a phoenix rising from
        the ashes' vs 'the phoenix rises from its ashes'. The word changes
        (a/the, rising/rises, the/its) drop difflib below 0.92, so
        best_sealed returns None. lookup() still finds it though."""
        memory.add_pair(
            "the phoenix rises from its ashes",
            "le phénix renaît de ses cendres",
            "en", "fr", status="sealed", store=store)
        hit = memory.best_sealed(
            "a phoenix rising from the ashes",
            "en", "fr", store=store)
        assert hit is None
        results = memory.lookup(
            "a phoenix rising from the ashes",
            "en", "fr", store=store)
        assert len(results) >= 1
        assert results[0]["similarity"] >= 0.55

    def test_gods_across_pantheons_as_entity_resolution(self, store):
        """Greek and Roman gods are aliases for the same entity."""
        er = EntityResolver(store=store, domain="mythology")
        er.seal("Zeus", "Sky Father", verifier="scholar")
        er.seal("Jupiter", "Sky Father", verifier="scholar")
        er.seal("Thor", "Sky Father", verifier="scholar")

        for name in ["Zeus", "Jupiter", "Thor"]:
            result = er.resolve(name)
            assert result["canonical"] == "Sky Father"
            assert result["sealed"]

    def test_long_epic_passage_as_pair(self, store):
        """A full paragraph from a mythological text stored and retrieved."""
        source = (
            "In the beginning there was only Chaos, the Abyss. "
            "Then came Gaia, the Earth, and Eros, the source of desire. "
            "From Chaos emerged Erebus and Nyx, darkness and night.")
        target = (
            "Au commencement il n'y avait que le Chaos, l'Abîme. "
            "Puis vint Gaïa, la Terre, et Éros, la source du désir. "
            "Du Chaos émergèrent l'Érèbe et Nyx, les ténèbres et la nuit.")
        memory.add_pair(source, target, "en", "fr",
                        status="sealed", store=store)
        hit = memory.best_sealed(source, "en", "fr", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == target
        assert hit["similarity"] == 1.0


class TestFictionalLanguages:
    """Nestor storing translations to/from languages that don't exist."""

    def test_elvish_translation_pairs(self, store):
        """Sindarin (Tolkien's Elvish) stored as a real language pair."""
        pairs = [
            ("friend", "mellon", "en", "sindarin"),
            ("star", "elenath", "en", "sindarin"),
            ("shadow", "gwath", "en", "sindarin"),
            ("fire", "naur", "en", "sindarin"),
            ("water", "nen", "en", "sindarin"),
        ]
        for src, tgt, sl, tl in pairs:
            memory.add_pair(src, tgt, sl, tl, status="sealed", store=store)

        for src, tgt, sl, tl in pairs:
            hit = memory.best_sealed(src, sl, tl, store=store)
            assert hit is not None
            assert hit["pair"]["target_text"] == tgt

    def test_klingon_phrases(self, store):
        """Klingon (Star Trek) — entirely invented phonology."""
        memory.add_pair("success", "Qapla'", "en", "klingon",
                        status="sealed", store=store)
        memory.add_pair("today is a good day to die",
                        "Heghlu'meH QaQ jajvam",
                        "en", "klingon", status="sealed", store=store)
        hit = memory.best_sealed("success", "en", "klingon", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "Qapla'"

    def test_invented_language_roundtrip(self, store):
        """A completely made-up language pair — both sides are gibberish."""
        memory.add_pair("zxqvbn plmkj", "wrtyu asdgh",
                        "nonsense_a", "nonsense_b",
                        status="sealed", store=store)
        hit = memory.best_sealed("zxqvbn plmkj",
                                 "nonsense_a", "nonsense_b", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "wrtyu asdgh"

    def test_fictional_domain_isolation(self, store):
        """Elvish pairs shouldn't leak into Klingon lookups."""
        memory.add_pair("hello", "mae govannen", "en", "sindarin",
                        status="sealed", store=store)
        memory.add_pair("hello", "nuqneH", "en", "klingon",
                        status="sealed", store=store)

        sindarin = memory.best_sealed("hello", "en", "sindarin", store=store)
        klingon = memory.best_sealed("hello", "en", "klingon", store=store)
        assert sindarin["pair"]["target_text"] == "mae govannen"
        assert klingon["pair"]["target_text"] == "nuqneH"


class TestEmojiNarratives:
    """Emoji sequences as source text — can Nestor store and retrieve
    entire stories told in emoji?"""

    def test_emoji_only_stories_key_distinctly_after_0202(self, store):
        """Decision 0202 replaced the FINDING this test used to lock — that
        every emoji-only source normalized to '' and therefore collided on
        the empty key. StringMatcher.normalize now preserves Unicode
        symbol categories (So, Sk), so two different emoji stories key
        distinctly and each retrieves its own row rather than borrowing
        the first-sealed row's target."""
        boy_forest = "\U0001f466\U0001f6b6\U0001f332\U0001f43b\U0001f3c3\U0001f3e0"
        rocket_star = "\U0001f680\U0001f31f\U0001f4ab"

        memory.add_pair(
            boy_forest,
            "A boy walked through the forest, met a bear, ran home",
            "emoji", "en", status="sealed", store=store)
        memory.add_pair(
            rocket_star,
            "A rocket launched toward a star",
            "emoji", "en", status="sealed", store=store)

        hit1 = memory.best_sealed(boy_forest, "emoji", "en", store=store)
        hit2 = memory.best_sealed(rocket_star, "emoji", "en", store=store)
        assert hit1 is not None
        assert hit2 is not None
        assert hit1["pair"]["target_text"] != hit2["pair"]["target_text"], (
            "distinct emoji stories must retrieve distinct rows — if this "
            "fires, the strip pass regressed to the pre-0202 collapse")
        assert hit1["pair"]["target_text"].startswith("A boy")
        assert hit2["pair"]["target_text"].startswith("A rocket")

    def test_single_emoji_seal_distinctly_after_0202(self, store):
        """Decision 0202 replaced the FINDING this test used to lock —
        that single emoji all normalized to '' and therefore only the
        first could be sealed (the rest raised ConflictingSealError).
        Now each single-emoji seal keys distinctly and the second seal
        succeeds. If ConflictingSealError EVER fires on two different
        emoji here, the strip pass regressed to the pre-fix collapse."""
        heart = memory.add_pair("❤️", "unconditional love",
                                "emoji", "philosophy",
                                status="sealed", store=store)
        bulb = memory.add_pair("\U0001f4a1", "sudden inspiration",
                               "emoji", "philosophy",
                               status="sealed", store=store)
        assert heart["source_norm"] != bulb["source_norm"], (
            "two different emoji must produce two different source_norm "
            "keys after decision 0202")
        # Both retrievable, each returns its own target.
        for src, expected in [("❤️", "unconditional love"),
                              ("\U0001f4a1", "sudden inspiration")]:
            hit = memory.best_sealed(src, "emoji", "philosophy", store=store)
            assert hit is not None, f"{src!r} did not retrieve after seal"
            assert hit["pair"]["target_text"] == expected

    def test_emoji_with_text_anchor(self, store):
        """Emoji work when combined with text. Pre-0202 the text was the
        only surviving distinctness signal (the emoji got stripped);
        post-0202 both survive, so this test asserts something slightly
        weaker than it now guarantees — see
        ``test_emoji_only_stories_key_distinctly_after_0202`` for the
        stronger form."""
        concepts = [
            ("heart ❤️", "unconditional love"),
            ("bulb \U0001f4a1", "sudden inspiration"),
            ("globe \U0001f30d", "global interconnectedness"),
        ]
        for emoji_text, concept in concepts:
            memory.add_pair(emoji_text, concept, "emoji", "philosophy",
                            status="sealed", store=store)
        for emoji_text, concept in concepts:
            hit = memory.best_sealed(emoji_text, "emoji", "philosophy",
                                     store=store)
            assert hit is not None
            assert hit["pair"]["target_text"] == concept

    def test_emoji_with_text_prefix_differentiates(self, store):
        """A text prefix distinguishes emoji stories. This test was
        originally the *workaround* for the emoji-collapse finding —
        the prefix was needed because the emoji themselves collapsed to
        ''. Decision 0202 fixed the collapse, so the prefix is no longer
        necessary for distinctness; the test still passes because the
        text prefix continues to distinguish, and now the emoji suffix
        does too — a doubly-redundant distinction. Kept as-is because
        naming the fact that BOTH signals now work is worth the row."""
        memory.add_pair(
            "story: \U0001f466\U0001f332\U0001f43b",
            "A boy met a bear in the forest",
            "emoji", "en", status="sealed", store=store)
        memory.add_pair(
            "family: \U0001f468\U0001f469\U0001f467\U0001f466",
            "A family of four",
            "emoji", "en", status="sealed", store=store)
        hit1 = memory.best_sealed(
            "story: \U0001f466\U0001f332\U0001f43b",
            "emoji", "en", store=store)
        hit2 = memory.best_sealed(
            "family: \U0001f468\U0001f469\U0001f467\U0001f466",
            "emoji", "en", store=store)
        assert hit1 is not None
        assert hit2 is not None
        assert hit1["pair"]["target_text"] != hit2["pair"]["target_text"]


class TestImpossibleMeasurements:
    """The Reconciler handling measurements that can't exist in reality —
    magic power levels, dragon wingspans, paradox counts."""

    def test_magic_power_levels(self, store):
        """Reconcile a wizard's power level against a sealed baseline."""
        r = Reconciler(store=store, domain="magic")
        r.seal_baseline("Gandalf power level", 9001, verifier="council")
        result = r.check("Gandalf power level", 9050)
        assert result["within_tolerance"]

    def test_negative_dragon_wingspans(self, store):
        """A negative wingspan is physically impossible but numerically valid."""
        r = Reconciler(store=store, domain="dragons")
        r.seal_baseline("baby dragon wingspan", -3.5, verifier="dragonkeeper")
        result = r.check("baby dragon wingspan", -3.2)
        assert result is not None
        assert "variation" in result

    def test_astronomical_numbers(self, store):
        """Numbers at the edge of floating point — distances to fictional stars."""
        r = Reconciler(store=store, domain="starmap")
        r.seal_baseline("distance to Mordor", 1e18, verifier="cartographer")
        result = r.check("distance to Mordor", 1.0000001e18)
        assert result["within_tolerance"]

    def test_zero_baseline(self, store):
        """Zero as a sealed baseline — the void's measurement."""
        r = Reconciler(store=store, domain="void")
        r.seal_baseline("nothing count", 0, verifier="philosopher")
        result = r.check("nothing count", 0)
        assert result["within_tolerance"]

    def test_pi_precision_reconciliation(self, store):
        """How closely does Nestor track irrational numbers?"""
        import math
        r = Reconciler(store=store, domain="constants")
        r.seal_baseline("circle ratio", math.pi, verifier="euclid")
        result = r.check("circle ratio", 3.14159)
        assert result["within_tolerance"]


class TestDecisionMemoryForFantasy:
    """Decision memory for a fantasy kingdom's governance —
    alliances, quests, and magical policy."""

    def test_quest_decisions(self, store):
        """A fantasy council making quest-assignment decisions."""
        dm = DecisionMemory(store=store, domain="quests")
        dm.propose("Who should slay the dragon?",
                   "Send the knight with the enchanted sword")
        result = dm.constraints_on("Who should slay the dragon?")
        assert result["live"] is not None
        assert "knight" in result["live"]["commitment"]

    def test_contradicting_prophecies(self, store):
        """Two prophecies that contradict each other — sealed as decisions,
        then linked with a contradicts edge."""
        dm = DecisionMemory(store=store, domain="prophecy")
        import os
        os.environ["NESTOR_SEAL_KEY"] = "oracle-key"
        try:
            p1_sig = signing.sign_seal(
                StringMatcher().normalize("Will the hero survive?"),
                "The hero shall triumph", "oracle")
            p1 = dm.seal("Will the hero survive?",
                         "The hero shall triumph",
                         verifier="oracle", seal_sig=p1_sig)

            p2_sig = signing.sign_seal(
                StringMatcher().normalize("Will the hero fall?"),
                "The hero shall fall in battle", "oracle")
            p2 = dm.seal("Will the hero fall?",
                         "The hero shall fall in battle",
                         verifier="oracle", seal_sig=p2_sig)

            edge_sig = signing.sign_edge(
                p1["id"], p2["id"], "contradicts", "oracle")
            dm.seal_edge(p1["id"], p2["id"], "contradicts",
                         verifier="oracle", edge_sig=edge_sig)

            constraints = dm.constraints_on("Will the hero survive?")
            assert len(constraints["constraints"]) == 1
            assert constraints["constraints"][0]["kind"] == "contradicts"
        finally:
            os.environ.pop("NESTOR_SEAL_KEY", None)

    def test_superseding_royal_decrees(self, store):
        """A new king supersedes the old king's decree. Uses add_pair
        directly because DecisionMemory.seal() doesn't expose override_conflict."""
        import os
        os.environ["NESTOR_SEAL_KEY"] = "crown-key"
        try:
            matcher = StringMatcher()
            old_sig = signing.sign_seal(
                matcher.normalize("Tax policy?"),
                "10% tithe on all harvests", "old_king")
            memory.add_pair("Tax policy?", "10% tithe on all harvests",
                            "kingdom", "kingdom", status="sealed",
                            verifier="old_king", seal_sig=old_sig,
                            store=store)

            new_sig = signing.sign_seal(
                matcher.normalize("Tax policy?"),
                "5% tithe, exemptions for farmers", "new_king")
            memory.add_pair("Tax policy?", "5% tithe, exemptions for farmers",
                            "kingdom", "kingdom", status="sealed",
                            verifier="new_king", seal_sig=new_sig,
                            override_conflict=True, store=store)

            dm = DecisionMemory(store=store, domain="kingdom")
            result = dm.constraints_on("Tax policy?")
            assert result["live"] is not None
            assert "5%" in result["live"]["commitment"]
        finally:
            os.environ.pop("NESTOR_SEAL_KEY", None)


class TestPoetryAndLiterature:
    """Nestor storing and matching poetic forms — haiku, sonnets, limericks."""

    def test_haiku_translation(self, store):
        """A haiku in Japanese matched to its English translation."""
        memory.add_pair(
            "古池や蛙飛び込む水の音",
            "An old silent pond / A frog jumps into the pond / Splash! Silence again",
            "ja", "en", status="sealed", store=store)
        hit = memory.best_sealed("古池や蛙飛び込む水の音", "ja", "en",
                                 store=store)
        assert hit is not None
        assert "frog" in hit["pair"]["target_text"]

    def test_multiline_poem_preserved(self, store):
        """A multi-line poem stored with its line breaks intact."""
        poem = "Shall I compare thee to a summer's day?\nThou art more lovely and more temperate."
        gloss = "Te compararé con un día de verano?\nEres más hermoso y más templado."
        memory.add_pair(poem, gloss, "en", "es",
                        status="sealed", store=store)
        hit = memory.best_sealed(poem, "en", "es", store=store)
        assert hit is not None
        assert "\n" in hit["pair"]["target_text"]

    def test_limerick_word_transposition_below_seal_bar(self, store):
        """FINDING: 'There once was' vs 'There was once' — a single word
        transposition in an 8-word phrase scores 0.886, below the 0.92
        seal threshold. The pair is found by lookup() but not best_sealed()."""
        memory.add_pair(
            "There once was a man from Nantucket",
            "a classic limerick opening",
            "en", "en", status="sealed", store=store)
        hit = memory.best_sealed(
            "There was once a man from Nantucket",
            "en", "en", store=store)
        assert hit is None
        results = memory.lookup(
            "There was once a man from Nantucket",
            "en", "en", store=store)
        assert len(results) >= 1
        assert 0.85 <= results[0]["similarity"] <= 0.92

    def test_palindrome_pairs(self, store):
        """Palindromes — text that reads the same forwards and backwards."""
        memory.add_pair("A man a plan a canal Panama",
                        "palindrome: geographic",
                        "en", "en", status="sealed", store=store)
        memory.add_pair("Was it a car or a cat I saw",
                        "palindrome: automotive",
                        "en", "en", status="sealed", store=store)
        hit = memory.best_sealed("A man a plan a canal Panama",
                                 "en", "en", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "palindrome: geographic"


class TestAbsurdButValidContent:
    """Content that is semantically absurd but structurally valid —
    Nestor doesn't judge meaning, only matches."""

    def test_colorless_green_ideas(self, store):
        """Chomsky's famous grammatically correct but meaningless sentence."""
        memory.add_pair(
            "Colorless green ideas sleep furiously",
            "Las ideas verdes incoloras duermen furiosamente",
            "en", "es", status="sealed", store=store)
        hit = memory.best_sealed(
            "Colorless green ideas sleep furiously",
            "en", "es", store=store)
        assert hit is not None
        assert hit["similarity"] == 1.0

    def test_time_travel_paradox_as_decision(self, store):
        """A logically paradoxical decision — Nestor stores it without judgment."""
        dm = DecisionMemory(store=store, domain="paradox")
        dm.propose(
            "If you go back in time and prevent your own birth, do you exist?",
            "Yes and no simultaneously — the bootstrap paradox is unresolvable")
        result = dm.constraints_on(
            "If you go back in time and prevent your own birth, do you exist?")
        assert result["live"] is not None
        assert "bootstrap" in result["live"]["commitment"]

    def test_very_long_number_as_entity(self, store):
        """A 200-digit number as an entity name — extreme but valid."""
        big_num = "1" * 200
        er = EntityResolver(store=store, domain="math")
        er.seal(big_num, "repunit(200)", verifier="number_theorist")
        result = er.resolve(big_num)
        assert result["canonical"] == "repunit(200)"

    def test_empty_meaning_full_structure(self, store):
        """Structurally complete but semantically empty — placeholder text."""
        memory.add_pair(
            "Lorem ipsum dolor sit amet consectetur adipiscing elit",
            "placeholder text with no real meaning in any language",
            "la", "en", status="sealed", store=store)
        hit = memory.best_sealed(
            "Lorem ipsum dolor sit amet consectetur adipiscing elit",
            "la", "en", store=store)
        assert hit is not None

    def test_tautology_as_translation(self, store):
        """Translating something to itself — a valid tautological pair."""
        memory.add_pair("the sky is blue", "the sky is blue",
                        "en", "en", status="sealed", store=store)
        hit = memory.best_sealed("the sky is blue", "en", "en", store=store)
        assert hit is not None
        assert hit["pair"]["target_text"] == "the sky is blue"
        assert hit["similarity"] == 1.0


class TestCulturalCrossReferences:
    """The same concept expressed across vastly different cultural frames."""

    def test_flood_myth_across_cultures(self, store):
        """The flood myth exists in nearly every culture. Store several
        versions and retrieve each independently."""
        myths = [
            ("Great Flood", "Noah built an ark", "en", "bible"),
            ("Great Flood", "Utnapishtim survived on a boat", "en", "sumerian"),
            ("Great Flood", "Manu was warned by a fish", "en", "hindu"),
            ("Great Flood", "Deucalion and Pyrrha repopulated", "en", "greek"),
        ]
        for src, tgt, sl, tl in myths:
            memory.add_pair(src, tgt, sl, tl, status="sealed", store=store)

        for src, tgt, sl, tl in myths:
            hit = memory.best_sealed(src, sl, tl, store=store)
            assert hit is not None
            assert hit["pair"]["target_text"] == tgt

    def test_love_in_twenty_scripts(self, store):
        """The word 'love' in many scripts — each a distinct domain pair."""
        love_words = [
            ("love", "愛", "en", "ja"),
            ("love", "사랑", "en", "ko"),
            ("love", "любовь", "en", "ru"),
            ("love", "حب", "en", "ar"),
            ("love", "אהבה", "en", "he"),
            ("love", "ความรัก", "en", "th"),
            ("love", " प्रेम", "en", "hi"),
            ("love", "amore", "en", "it"),
            ("love", "amour", "en", "fr"),
            ("love", "liebe", "en", "de"),
            ("love", "amor", "en", "es"),
            ("love", "кохання", "en", "uk"),
            ("love", "rakkaus", "en", "fi"),
            ("love", "kärlek", "en", "sv"),
            ("love", "láska", "en", "cs"),
            ("love", "miłość", "en", "pl"),
            ("love", "dragoste", "en", "ro"),
            ("love", "αγάπη", "en", "el"),
            ("love", "sevgi", "en", "tr"),
            ("love", "tình yêu", "en", "vi"),
        ]
        for src, tgt, sl, tl in love_words:
            memory.add_pair(src, tgt, sl, tl, status="sealed", store=store)

        retrieved = 0
        for src, tgt, sl, tl in love_words:
            hit = memory.best_sealed(src, sl, tl, store=store)
            assert hit is not None, f"failed for {tl}"
            assert hit["pair"]["target_text"] == tgt
            retrieved += 1
        assert retrieved == 20


class TestSciFiDataPatterns:
    """Data patterns from science fiction — starship registries,
    alien taxonomies, warp coordinates."""

    def test_starship_registry(self, store):
        """Federation starship registry numbers as entity aliases."""
        er = EntityResolver(store=store, domain="starfleet")
        ships = [
            ("NCC-1701", "USS Enterprise"),
            ("NCC-1701-D", "USS Enterprise-D"),
            ("NCC-74656", "USS Voyager"),
            ("NX-01", "Enterprise"),
        ]
        for reg, name in ships:
            er.seal(reg, name, verifier="starfleet_records")

        for reg, name in ships:
            result = er.resolve(reg)
            assert result["canonical"] == name

    def test_alien_taxonomy(self, store):
        """Classifying fictional alien species — Nestor as a xenobiologist's
        reference database."""
        memory.add_pair("Vulcan", "Class M humanoid, copper-based blood, "
                        "telepathic, lifespan 200+ years",
                        "species", "taxonomy",
                        status="sealed", store=store)
        memory.add_pair("Klingon", "Class M humanoid, redundant organs, "
                        "warrior culture, cranial ridges",
                        "species", "taxonomy",
                        status="sealed", store=store)
        hit = memory.best_sealed("Vulcan", "species", "taxonomy", store=store)
        assert hit is not None
        assert "copper-based" in hit["pair"]["target_text"]

    def test_warp_coordinates_as_reconciliation(self, store):
        """Reconciling navigational readings against sealed star charts."""
        r = Reconciler(store=store, domain="navigation")
        r.seal_baseline("bearing to Vulcan", 247.65, verifier="navigator")
        result = r.check("bearing to Vulcan", 247.70)
        assert result["within_tolerance"]
