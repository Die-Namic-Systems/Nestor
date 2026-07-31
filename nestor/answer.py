"""What Nestor answers — one definition, several transports.

The browser (:mod:`nestor.ui`), the model-facing server (:mod:`nestor.serve`)
and the terminal (:mod:`nestor.cli`) all ask Nestor the same questions. They
must not be able to get *different* answers: the entire proposition is that a
served answer carries a human's verification, and a system that tells a model
"verified" while showing a curator "draft" has already lost that. So the
question-answering lives here, once, and the transports are thin.

Each function takes an injected store, returns a plain JSON-ready dict, and
answers with the state rather than only the value: whether a human verified it,
who, and what the candidates scored. Nothing here seals — every function is
either a read or a proposal for a human to look at. Sealing is a human act and
lives in :mod:`nestor.memory`, :mod:`nestor.cascade` and the surfaces a person
drives.
"""
from __future__ import annotations

from typing import Optional

from . import cascade, memory
from .engine import get_engine
from .entity import EntityResolver
from .matcher import Matcher, NumericMatcher, StringMatcher
from .reconcile import Reconciler
from .storage import Storage

MATCHERS = ("string", "numeric", "semantic")


def build_matcher(name: str = "string", abs_tol: float = 0.0,
                  pct_tol: float = 0.05) -> Matcher:
    """One of the shipped matchers, by name.

    A custom matcher is injected in code (``memory.set_matcher``); a name coming
    off a wire cannot conjure one, so an unknown name is refused rather than
    quietly resolved to the default — the default would score a completely
    different notion of similarity under a name the caller chose deliberately.

    ``semantic`` needs ``pip install nestor[semantic]`` (fastembed). Thresholds
    tuned for :class:`~nestor.matcher.StringMatcher` are not portable — measure
    with ``nestor calibrate`` on your corpus.
    """
    if name == "string":
        return StringMatcher()
    if name == "numeric":
        return NumericMatcher(abs_tol=abs_tol, pct_tol=pct_tol)
    if name == "semantic":
        from .semantic_matcher import SemanticMatcher
        try:
            return SemanticMatcher()
        except ImportError as exc:
            raise ValueError(str(exc)) from exc
    raise ValueError(f"unknown matcher {name!r} — the shipped matchers are "
                     f"{', '.join(MATCHERS)}; a custom one is injected in code.")


def _candidate(m: dict) -> dict:
    pair = m["pair"]
    return {"similarity": m["similarity"], "status": pair["status"],
            "servable": memory.is_verified_seal(pair), "id": pair["id"],
            "source_text": pair["source_text"], "target_text": pair["target_text"],
            "verifier": pair.get("verifier", "")}


def ask(store: Storage, text: str, source_lang: str = "en", target_lang: str = "es",
        engine_name: str = "offline") -> dict:
    """Run the cascade over one phrase: sealed, draft, or pending.

    Appends a passage to the ledger, exactly as any other serve does — an answer
    served without a trail is the thing Nestor exists to prevent, and neither a
    browser nor a model is an exception to that.
    """
    if not text.strip():
        raise ValueError("nothing to ask")
    passage = cascade.translate_segment(
        text, source_lang, target_lang, engine=get_engine(engine_name), store=store)
    return {
        "passage": {"source": passage.source, "target": passage.target,
                    "state": passage.state, "mark": passage.mark, "tier": passage.tier,
                    "engine": passage.engine, "confidence": passage.confidence,
                    "meta": passage.meta},
        "verified": passage.state == "sealed",
        "matches": [_candidate(m) for m in
                    memory.lookup(text, source_lang, target_lang, limit=5, store=store)],
        "threshold": memory.SEAL_THRESHOLD,
    }


def resolve(store: Storage, surface: str, domain: str = "entity") -> dict:
    """Alias → canonical entity, with the same three answers the cascade gives."""
    if not surface.strip():
        raise ValueError("nothing to resolve")
    result = EntityResolver(store, domain=domain).resolve(surface)
    result["domain"] = domain
    result["verified"] = bool(result.get("sealed"))
    result["candidates"] = [
        {**_candidate(m), "surface": m["pair"]["source_text"],
         "canonical": m["pair"]["target_text"]}
        for m in memory.lookup(surface, domain, domain, limit=5, store=store)]
    result["threshold"] = memory.SEAL_THRESHOLD
    return result


def check(store: Storage, label: str, observed, domain: str = "value",
          abs_tol: float = 0.0, pct_tol: float = 0.05) -> dict:
    """A figure against its sealed baseline: within tolerance, flagged, or nothing."""
    if not str(label).strip() or not str(observed).strip():
        raise ValueError("a check needs a label and an observed value")
    rc = Reconciler(store, domain=domain, abs_tol=abs_tol, pct_tol=pct_tol)
    result = rc.check(label, observed)
    result["domain"] = domain
    result["verified"] = result["baseline"] is not None
    result["tolerance"] = {"abs_tol": rc.matcher.abs_tol, "pct_tol": rc.matcher.pct_tol}
    result["baselines"] = [
        {"value": r["target_text"], "verifier": r.get("verifier", ""),
         "created_at": r.get("created_at", ""), "id": r["id"]}
        for r in rc.sealed_baselines(label)]
    return result


def match(store: Storage, text: str, source_lang: str, target_lang: str,
          matcher: str = "string", abs_tol: float = 0.0, pct_tol: float = 0.05) -> dict:
    """The bare mechanic over any domain: normalize, score, would it be served?"""
    if not text.strip():
        raise ValueError("nothing to match")
    m = build_matcher(matcher, abs_tol=abs_tol, pct_tol=pct_tol)
    hit = memory.best_sealed(text, source_lang, target_lang, store=store, matcher=m,
                             context_threshold=0.0)
    return {
        "normalized": m.normalize(text),
        "served": bool(hit),
        "verified": bool(hit),
        "target": hit["pair"]["target_text"] if hit else "",
        "verifier": hit["pair"].get("verifier", "") if hit else "",
        "confidence": hit["similarity"] if hit else 0.0,
        "threshold": memory.SEAL_THRESHOLD,
        "matcher": matcher,
        "matches": [_candidate(mm) for mm in
                    memory.lookup(text, source_lang, target_lang, limit=8, store=store,
                                  matcher=m, context_threshold=0.0)],
    }


def provenance(store: Storage, pair_id: str) -> Optional[dict]:
    """Who verified a pair, when, and every rejection recorded against it.

    The question an auditor asks months later, and the one a model should be
    able to quote instead of asserting confidence. ``None`` if the id is unknown.
    """
    from .curator import Curator                 # local: curation is optional
    from .storage import supports_curation
    if not supports_curation(store):
        pair = store.memory_get(pair_id) if hasattr(store, "memory_get") else None
        return dict(pair) if pair else None
    return Curator(store).get(pair_id)


def propose(store: Storage, source_text: str, candidate: str, source_lang: str = "en",
            target_lang: str = "es", title: str = "", origin: str = "proposal") -> dict:
    """Queue a candidate for a human to review. The only write a machine gets.

    This is tier 2 reached by another road: a model that has produced an answer
    can put it where a reviewer will see it, and it lands as a ``draft`` like
    every other machine output. It cannot seal, and nothing here can be made to
    seal by passing a different argument — the parameter does not exist.
    """
    if not source_text.strip():
        raise ValueError("a proposal needs the source text it answers")
    store.init_db()
    doc = store.create_document(title=title or f"proposals: {source_text[:32]}",
                                source_lang=source_lang, target_lang=target_lang)
    seg = store.create_segment(document_id=doc["id"], position=0,
                               source_text=source_text, candidate=candidate,
                               jeles_score=0.0)
    cascade._ledger_append({"kind": "proposal", "document_id": doc["id"],
                            "segment_id": seg["id"], "origin": origin,
                            "source_lang": source_lang, "target_lang": target_lang,
                            "source_sha": memory._sha(source_text)})
    return {"document_id": doc["id"], "segment_id": seg["id"], "state": "draft",
            "verified": False,
            "note": "queued for human review — a proposal is never served as verified"}
