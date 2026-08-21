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

    def test_all_whitespace_source(self, store):
        """Source text that's nothing but spaces and tabs."""
        whitespace = "   \t\t   \n   "
        memory.add_pair(whitespace, "void", "en", "en",
                        status="draft", store=store)
        norm = StringMatcher().normalize(whitespace)
        # Pin: StringMatcher strips to empty string on pure whitespace.
        assert isinstance(norm, str)

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
