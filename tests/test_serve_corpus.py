"""The corpus lane on the MCP surface — pointers, never an answer.

The property the two new tools have to keep is the one 0213 established: no
corpus operation writes ``tm_pairs``, the ledger, a verifier, or a signature,
and no return shape carries a field a model could mistake for a verdict. So
every return shape here is asserted for the *absence* of a state field, a
verdict, a would_serve, an answer — the same shape absence tests
``test_serve.py`` uses for the sealing verbs. The refusal shape at the edge
(unknown repository, oversize limit, empty query, no ``--corpus-dir``) is
tested the same way, because a facet added loosely is harder to remove than
a kind (see ``nestor/warrant.py``'s WARRANT_KINDS posture).
"""
from __future__ import annotations

import json
import os

import pytest

from nestor import cascade, corpus, memory, serve, storage
from nestor.sqlite_store import SqliteStore


def _extractor(path, rows):
    store = SqliteStore(str(path))
    store.init_db()
    store.memory_init()
    for source, target, source_lang, target_lang, origin in rows:
        memory.add_pair(source, target, source_lang, target_lang,
                        status="draft", origin=origin, store=store)
    store.close()


@pytest.fixture()
def server(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    sources = tmp_path / "sources"
    sources.mkdir()
    _extractor(sources / "faa.db", [
        ("cabin pressurization starts", "at 8000 feet", "en", "en",
         "faa@a:rules.md"),
        ("oxygen masks deploy", "above 14000 feet", "en", "en",
         "faa@a:rules.md"),
    ])
    _extractor(sources / "icao.db", [
        ("cabin pressurization starts", "around 2400 metres", "en", "en",
         "icao@b:annex.md"),
    ])
    household = tmp_path / "household.db"
    corpus.sync(sources, household)
    store = SqliteStore(str(household))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                    status="sealed", verifier="rita", store=store)
    retriever = corpus.CorpusRetriever(household)
    return serve.Server(store=store, corpus_retriever=retriever)


def call(server, name, **args):
    reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": args}})
    result = reply["result"]
    text = result["content"][0]["text"]
    if result.get("isError"):
        return {"error": text}
    return json.loads(text)


# --- corpus_map ------------------------------------------------------------

def test_corpus_map_lists_repositories_with_counts_and_snapshot_sha(server):
    out = call(server, "nestor_corpus_map")
    assert out["claims_total"] == 3
    assert out["sources_total"] == 2
    assert out["snapshot_sha256"] and len(out["snapshot_sha256"]) == 64
    assert out["authority"] == "none", (
        "the map is discovery, not verification — every row is authority-free")
    names = sorted(row["repository"] for row in out["repositories"])
    assert names == ["faa", "icao"]
    faa = next(row for row in out["repositories"] if row["repository"] == "faa")
    assert faa["claims"] == 2
    assert faa["source_langs"] == ["en"]
    assert faa["target_langs"] == ["en"]


def test_corpus_map_is_absent_when_no_corpus_dir(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    server_without_corpus = serve.Server(store=store)
    names = [tool["name"] for tool in server_without_corpus.tools()]
    assert "nestor_corpus_map" not in names
    assert "nestor_corpus_search" not in names
    # A model that tries anyway reads a named refusal, not silence.
    out = call(server_without_corpus, "nestor_corpus_map")
    assert "requires --corpus-dir" in out["error"]


# --- corpus_search ---------------------------------------------------------

def test_corpus_search_returns_pointers_never_an_answer(server):
    out = call(server, "nestor_corpus_search",
               query="cabin pressurization altitude")
    assert out["selected_count"] >= 1
    for forbidden in ("state", "verdict", "would_serve", "answer",
                      "suggested_next", "verified"):
        assert forbidden not in out, (
            f"corpus_search must not carry {forbidden!r} — this is a locator, "
            f"not a verdict")
    for claim in out["claims"]:
        assert claim["authority"] == "none"
        assert "verifier" not in claim
        assert claim["source_status"] in ("draft", "sealed", "rejected")
        assert claim["repository"] in ("faa", "icao")
        assert isinstance(claim["matched_terms"], list) and claim["matched_terms"]


def test_corpus_search_scopes_to_one_repository_when_asked(server):
    out = call(server, "nestor_corpus_search",
               query="cabin pressurization", repository="icao")
    assert out["repository"] == "icao"
    assert out["selected_count"] >= 1
    assert {claim["repository"] for claim in out["claims"]} == {"icao"}


def test_corpus_search_refuses_an_unknown_repository_with_the_taxonomy(server):
    out = call(server, "nestor_corpus_search",
               query="anything", repository="oops")
    assert "unknown repository" in out["error"]
    assert "faa" in out["error"] and "icao" in out["error"], (
        "the refusal names the whole list so a caller can recover")


def test_corpus_search_refuses_a_whitespace_repository(server):
    """A whitespace-only value must not silently unscope (adversarial review finding).

    The earlier version gated on the raw truthiness — ``if repository_raw:`` —
    then re-checked the stripped value with ``if repository:``. A ``"   "``
    argument passes the first check (truthy), strips to ``""``, and skips
    the second entirely: ``search()`` receives ``repository=None`` and returns
    unscoped results while the caller had every reason to think they had
    scoped. Refuse instead.
    """
    out = call(server, "nestor_corpus_search",
               query="cabin pressurization", repository="   ")
    assert "unknown repository" in out["error"]
    assert "faa" in out["error"] and "icao" in out["error"], (
        "a whitespace argument reads as an unknown filter, "
        "not as an absent filter")


def test_corpus_search_refuses_an_oversize_limit(server):
    out = call(server, "nestor_corpus_search", query="cabin", limit=99999)
    assert "limit" in out["error"]


def test_corpus_search_refuses_a_blank_query(server):
    out = call(server, "nestor_corpus_search", query="   ")
    assert "query" in out["error"]


# --- covenant --------------------------------------------------------------

def test_no_corpus_verb_writes_anything(server):
    """Two-layer property: no tm_pairs delta, no ledger delta."""
    from nestor import ledger as ledger_mod
    from nestor.curator import Curator

    before_summary = Curator(server.store).summary()
    before_chain_ok, _ = ledger_mod.verify()
    call(server, "nestor_corpus_map")
    call(server, "nestor_corpus_search", query="cabin pressurization")
    call(server, "nestor_corpus_search",
         query="cabin", repository="faa")
    after_summary = Curator(server.store).summary()
    after_chain_ok, _ = ledger_mod.verify()
    assert after_summary == before_summary
    assert after_chain_ok == before_chain_ok


def test_describe_names_present_tools_and_absent_ones_with_reasons(server):
    text = serve.describe(server)
    assert "nestor_corpus_map" in text
    assert "nestor_corpus_search" in text
    # nestor_draft and nestor_propose are conditional; in this fixture the
    # engine is offline (draft withheld) and not read-only (propose present).
    assert "nestor_draft" in text
    assert "engine is not ollama" in text
    assert "nestor_propose" in text  # present, named in the enumeration


def test_describe_names_the_two_corpus_tools_when_no_corpus_dir(tmp_path, seal_key):
    """The withheld line has to name the two tools, so a caller reads a refusal
    rather than concluding the server has no such path (adversarial review gap)."""
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    server_without_corpus = serve.Server(store=store)
    text = serve.describe(server_without_corpus)
    assert "nestor_corpus_map" in text
    assert "nestor_corpus_search" in text
    assert "no --corpus-dir" in text
