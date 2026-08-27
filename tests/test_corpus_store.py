"""Extracted corpus stores consolidate without acquiring authority."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from nestor import cli, corpus, memory
from nestor.sqlite_store import SqliteStore

REPO = Path(__file__).resolve().parent.parent


def _source(path, rows):
    store = SqliteStore(str(path))
    store.init_db()
    store.memory_init()
    for source, target, source_lang, target_lang, origin in rows:
        memory.add_pair(
            source,
            target,
            source_lang,
            target_lang,
            status="draft",
            origin=origin,
            store=store,
        )
    store.close()


def test_sync_preserves_cross_repository_drift_in_one_household_db(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    _source(
        sources / "one.db",
        [("Ratification", "requires a human signature", "term", "term", "one@a:rules.md")],
    )
    _source(
        sources / "two.db",
        [("Ratification", "happens automatically", "term", "term", "two@b:rules.md")],
    )
    household = tmp_path / "household.db"

    report = corpus.sync(sources, household)
    found = corpus.CorpusRetriever(household).search(
        "human ratification signature", limit=8
    )

    assert report.claims == 2
    assert report.drift_keys == 1
    assert {claim.repository for claim in found.claims} == {"one", "two"}
    assert all("drift" in claim.comparison_labels for claim in found.claims)
    assert all(claim.authority == "none" for claim in found.claims)


def test_sync_is_idempotent_and_never_migrates_source_stores(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    source = sources / "one.db"
    _source(source, [("boundary", "humans seal", "term", "term", "one@a:rules.md")])
    household = tmp_path / "household.db"
    before = source.read_bytes()
    sidecars = {
        suffix: path.read_bytes() if path.exists() else None
        for suffix in ("-wal", "-shm")
        for path in (source.with_name(source.name + suffix),)
    }

    first = corpus.sync(sources, household)
    second = corpus.sync(sources, household)

    assert first.snapshot_sha256 == second.snapshot_sha256
    assert first.changed is True
    assert second.changed is False
    assert source.read_bytes() == before
    for suffix, contents in sidecars.items():
        path = source.with_name(source.name + suffix)
        assert (path.read_bytes() if path.exists() else None) == contents


def test_corrupt_source_rolls_back_without_erasing_last_good_snapshot(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    _source(sources / "one.db", [("boundary", "humans seal", "term", "term", "one")])
    household = tmp_path / "household.db"
    corpus.sync(sources, household)
    before = corpus.CorpusRetriever(household).count()
    (sources / "broken.db").write_text("not sqlite", encoding="utf-8")

    with pytest.raises(corpus.CorpusError, match="broken"):
        corpus.sync(sources, household)

    assert corpus.CorpusRetriever(household).count() == before


def test_active_source_wal_is_refused_instead_of_reading_a_stale_snapshot(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    source = sources / "one.db"
    _source(source, [("boundary", "humans seal", "term", "term", "one")])
    household = tmp_path / "household.db"
    corpus.sync(sources, household)
    source.with_name(source.name + "-wal").write_bytes(b"active writer")

    with pytest.raises(corpus.CorpusError, match="active WAL"):
        corpus.sync(sources, household)

    assert corpus.CorpusRetriever(household).count() == 1


def test_source_seal_claim_remains_inert_and_cannot_enter_memory(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    source = sources / "claimed.db"
    _source(
        source,
        [(
            "rule",
            "machine says sealed",
            "decision",
            "decision",
            "/home/alice/private/rules.md",
        )],
    )
    conn = sqlite3.connect(source)
    conn.execute(
        "UPDATE tm_pairs SET status='sealed', verifier='forged', seal_sig='forged'"
    )
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    household = tmp_path / "household.db"

    corpus.sync(sources, household)
    result = corpus.CorpusRetriever(household).search("rule", limit=3)
    memory_store = SqliteStore(str(household))
    memory_store.memory_init()

    assert result.claims[0].source_status == "sealed"
    assert result.claims[0].authority == "none"
    assert result.claims[0].origin == "claimed:rules.md"
    assert memory_store.memory_list(limit=10) == []


def test_long_queries_require_more_than_one_meaningful_token(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    _source(
        sources / "one.db",
        [
            (
                "local agents draft",
                "a human may verify and seal decisions",
                "term",
                "term",
                "one:relevant",
            ),
            (
                "human resources",
                "unrelated office policy",
                "term",
                "term",
                "one:noise",
            ),
        ],
    )
    household = tmp_path / "household.db"
    corpus.sync(sources, household)

    found = corpus.CorpusRetriever(household).search(
        "Explain why local agents may draft but only a human may verify or seal decisions",
        limit=8,
    )

    assert [claim.origin for claim in found.claims] == ["one:relevant"]
    assert found.claims[0].matched_terms == (
        "agent",
        "decision",
        "draft",
        "human",
        "local",
        "seal",
        "verify",
    )
    assert found.eligible_count == 1


def test_meaningful_tokens_normalize_common_plural_and_verb_endings():
    assert corpus.meaningful_tokens(
        "agents decisions reaches switches processes uses"
    ) == ("agent", "decision", "reach", "switch", "process", "use")


def test_large_repository_cannot_crowd_out_smaller_sources(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    _source(
        sources / "large.db",
        [
            (
                f"shared boundary {number}",
                f"large claim {number}",
                "term",
                "term",
                f"l:{number}",
            )
            for number in range(5)
        ],
    )
    _source(
        sources / "small.db",
        [("shared boundary", "small claim", "term", "term", "s:1")],
    )
    household = tmp_path / "household.db"
    corpus.sync(sources, household)

    found = corpus.CorpusRetriever(household).search("shared boundary", limit=4)

    assert "small" in {claim.repository for claim in found.claims}
    assert sum(claim.repository == "large" for claim in found.claims) <= 2


def test_cli_syncs_selected_sources_into_selected_household_db(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    _source(sources / "one.db", [("rule", "humans seal", "term", "term", "one")])
    household = tmp_path / "household.db"

    code = cli.main([
        "--db",
        str(household),
        "corpus",
        "sync",
        "--source-dir",
        str(sources),
    ])

    assert code == 0
    assert corpus.CorpusRetriever(household).count() == 1


def test_semantic_rerank_is_bounded_cached_and_explicit(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    _source(
        sources / "one.db",
        [
            ("boundary storage", "irrelevant storage detail", "term", "term", "one:a"),
            ("boundary authority", "preferred human authority", "term", "term", "one:b"),
        ],
    )
    household = tmp_path / "household.db"
    corpus.sync(sources, household)
    calls = []

    def embed(text):
        calls.append(text)
        return (1.0, 0.0) if (
            text == "boundary authority" or "preferred" in text
        ) else (0.0, 1.0)

    retriever = corpus.CorpusRetriever(household, semantic=True, embedder=embed)
    first = retriever.search("boundary authority", limit=2)
    first_call_count = len(calls)
    second = retriever.search("boundary authority", limit=2)

    assert first.mode == "fts+semantic"
    assert first.claims[0].target_text == "preferred human authority"
    assert second.claims == first.claims
    assert len(calls) == first_call_count


@pytest.mark.slow
@pytest.mark.performance
def test_full_local_corpus_sync_and_query_stay_bounded(tmp_path):
    household = tmp_path / "household.db"

    sync_started = time.perf_counter()
    report = corpus.sync(REPO / "data" / "corpus", household)
    sync_seconds = time.perf_counter() - sync_started
    query_started = time.perf_counter()
    found = corpus.CorpusRetriever(household).search(
        "why local agents may draft but only humans verify and seal",
        limit=8,
    )
    query_seconds = time.perf_counter() - query_started

    assert report.sources == 24
    assert report.claims >= 9_000
    assert found.claims
    assert sync_seconds < 10.0
    assert query_seconds < 1.0
