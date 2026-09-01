"""Local drafts expose corpus context without laundering its authority."""
from __future__ import annotations

from test_corpus_store import _source

from nestor import corpus, engine, memory, serve
from nestor.sqlite_store import SqliteStore


def test_draft_tool_returns_separate_unverified_corpus_basis(
    tmp_path, monkeypatch,
):
    sources = tmp_path / "sources"
    sources.mkdir()
    _source(
        sources / "local.db",
        [(
            "authority boundary",
            "Only a human seals; models draft.",
            "decision",
            "decision",
            "local@abc:rules.md#boundary",
        )],
    )
    household = tmp_path / "household.db"
    store = SqliteStore(str(household))
    store.init_db()
    store.memory_init()
    corpus.sync(sources, household)

    class FakeOllama:
        def __init__(self, model):
            self.model = model

        def draft_task(self, task, *, excerpts, sealed_context, corpus_context):
            assert task == "Explain the authority boundary"
            assert excerpts == []
            assert sealed_context == []
            assert len(corpus_context) == 1
            claim = corpus_context[0]
            assert claim["authority"] == "none"
            assert claim["citation_token"] == "C1"
            provenance = engine.DraftProvenance(
                provider="ollama",
                model=self.model,
                prompt_sha256="prompt",
                input_sha256="input",
                context_pair_ids=(),
                endpoint_scope="loopback",
                transport="ollama:/api/chat",
                temperature=0.0,
                max_output_tokens=1024,
                input_chars=12,
                truncated=False,
                created_at="now",
                corpus_context_ids=(f"{claim['repository']}:{claim['id']}",),
            )
            return engine.TaskDraft(
                "Humans seal; models draft [C1].", self.model, provenance
            )

    monkeypatch.setattr(engine, "OllamaEngine", FakeOllama)
    retrieval_limits = []
    retriever = corpus.CorpusRetriever(household)

    class RecordingRetriever:
        def search(self, task, *, limit):
            retrieval_limits.append(limit)
            return retriever.search(task, limit=limit)

    server = serve.Server(
        store=store,
        source_lang="decision",
        target_lang="decision",
        source_lang_explicit=True,
        target_lang_explicit=True,
        engine_name="ollama",
        ollama_model="small-code",
        corpus_retriever=RecordingRetriever(),
    )

    out = server.call("nestor_draft", {"task": "Explain the authority boundary"})

    assert out["state"] == "draft"
    assert out["verified"] is False
    assert out["basis"]["sealed_guidance"] == []
    assert len(out["basis"]["unverified_corpus_excerpts"]) == 1
    assert out["basis"]["unverified_corpus_excerpts"][0]["authority"] == "none"
    assert out["basis"]["unverified_corpus_excerpts"][0]["citation_token"] == "C1"
    assert out["retrieval"]["mode"] == "fts"
    assert out["retrieval"]["selected_count"] == 1
    assert retrieval_limits == [4]
    assert out["grounding"]["citation_compliant"] is True
    assert out["grounding"]["cited_tokens"] == ["C1"]
    assert out["pattern_support"]["unsupported_sentences"] == []
    assert out["pattern_support"]["sentences"][0]["candidates"][0]["token"] == "C1"


def test_related_verified_guidance_can_ground_a_draft_without_becoming_a_task_seal(
    tmp_path, monkeypatch,
):
    store = SqliteStore(str(tmp_path / "household.db"))
    store.memory_init()
    related = {
        "pair": {
            "id": "sealed-1",
            "status": "sealed",
            "source_text": "Local models draft behind deterministic gates",
            "target_text": "Only a human may verify or seal the result.",
        },
        "similarity": 0.368,
    }
    seen = {}

    def lookup(*_args, **kwargs):
        seen["threshold"] = kwargs["context_threshold"]
        return [related]

    monkeypatch.setattr(memory, "lookup", lookup)
    monkeypatch.setattr(memory, "verified_sealed", lambda matches: matches)
    server = serve.Server(store=store)

    found = server._draft_sealed_context(
        "Explain why local agents draft but humans verify and seal decisions",
        "decision",
        "decision",
    )

    assert seen["threshold"] == 0.0
    assert found[0]["pair"]["id"] == "sealed-1"
    assert found[0]["context_matched_terms"] == [
        "draft",
        "human",
        "local",
        "seal",
        "verify",
    ]
    assert found[0]["context_only"] is True


def test_unknown_or_missing_citation_tokens_are_reported():
    contexts = [{"citation_token": "C1"}, {"citation_token": "C2"}]

    missing = serve._citation_report("A claim without a citation.", contexts)
    unknown = serve._citation_report("A claim [C9].", contexts)

    assert missing["citation_compliant"] is False
    assert missing["uncited_tokens"] == ["C1", "C2"]
    assert unknown["citation_compliant"] is False
    assert unknown["unknown_tokens"] == ["C9"]
    assert "do not apply it as grounded" in serve._grounding_note(missing)


def test_pattern_support_names_sentence_candidates_and_leaves_claims_open():
    contexts = [
        {
            "citation_token": "S1",
            "authority": "human-sealed-statement",
            "source_text": "Local models draft behind deterministic gates",
            "target_text": "Only a human may seal the result.",
        },
        {
            "citation_token": "C1",
            "authority": "none",
            "source_text": "records/sealing.py::seal",
            "target_text": "A named human stands behind the draft.",
        },
    ]

    report = serve._pattern_support_report(
        "Local models use deterministic gates. The moon is made of cheese.\n\n"
        "A human stands behind the sealed draft.",
        contexts,
    )

    assert report["method"] == "sentence-meaningful-token-overlap"
    assert report["candidate_only"] is True
    assert report["sentences"][0]["candidates"][0]["token"] == "S1"
    assert report["sentences"][1]["candidates"] == []
    assert report["sentences"][1]["text_excerpt"] == "The moon is made of cheese."
    assert "moon" in report["sentences"][1]["unmatched_terms"]
    assert report["sentences"][2]["candidates"][0]["token"] == "C1"
    assert report["unsupported_sentences"] == [2]


def test_pattern_support_reports_negation_polarity_mismatch():
    contexts = [{
        "citation_token": "C1",
        "authority": "none",
        "source_text": "seal",
        "target_text": "The seal is signed by a named human.",
    }]

    report = serve._pattern_support_report(
        "The seal is not signed by a named human.",
        contexts,
    )

    assert report["sentences"][0]["candidates"][0]["token"] == "C1"
    assert report["sentences"][0]["candidates"][0]["negation_mismatch"] is True
    assert report["negation_mismatch_sentences"] == [1]


def test_pattern_support_compares_polarity_with_the_nearest_basis_sentence():
    contexts = [{
        "citation_token": "C1",
        "authority": "none",
        "source_text": "seal states",
        "target_text": "Drafts are not verified. Human-sealed pairs are verified.",
    }]

    report = serve._pattern_support_report(
        "Human-sealed pairs are verified.",
        contexts,
    )

    candidate = report["sentences"][0]["candidates"][0]
    assert candidate["token"] == "C1"
    assert candidate["negation_mismatch"] is False
    assert candidate["basis_negated_terms"] == []
    assert report["negation_mismatch_sentences"] == []


def test_mcp_startup_refreshes_operator_selected_corpus(tmp_path, monkeypatch):
    sources = tmp_path / "sources"
    sources.mkdir()
    _source(sources / "one.db", [("rule", "humans seal", "term", "term", "one")])
    household = tmp_path / "household.db"
    monkeypatch.setattr(serve.keyring, "preflight", lambda: None)
    monkeypatch.setattr(serve.Server, "run", lambda self, stdin, stdout: None)

    code = serve.main([
        "--db",
        str(household),
        "--ledger",
        str(tmp_path / "ledger.jsonl"),
        "--corpus-dir",
        str(sources),
    ])

    assert code == 0
    assert corpus.CorpusRetriever(household).count() == 1
