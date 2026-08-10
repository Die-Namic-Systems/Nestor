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
from .matcher import Matcher, NumericMatcher, StringMatcher, matcher_audit_fields
from .persona import Persona, get_persona
from .reconcile import Reconciler
from .storage import Storage

MATCHERS = ("string", "numeric", "semantic", "ollama")


def build_matcher(name: str = "string", abs_tol: float = 0.0,
                  pct_tol: float = 0.05, persist: bool = True) -> Matcher:
    """One of the shipped matchers, by name.

    A custom matcher is injected in code (``memory.set_matcher``); a name coming
    off a wire cannot conjure one, so an unknown name is refused rather than
    quietly resolved to the default — the default would score a completely
    different notion of similarity under a name the caller chose deliberately.

    ``semantic`` needs ``pip install nestor[semantic]`` (fastembed). ``ollama``
    needs a reachable Ollama daemon with ``nomic-embed-text`` (stdlib HTTP; no
    pip extra). Thresholds tuned for :class:`~nestor.matcher.StringMatcher` are
    not portable — measure with ``nestor calibrate`` on your corpus.

    ``persist=False`` stops the semantic / ollama matcher writing its embedding
    cache; the other matchers never write anything and ignore it.
    """
    if name == "string":
        return StringMatcher()
    if name == "numeric":
        return NumericMatcher(abs_tol=abs_tol, pct_tol=pct_tol)
    if name == "semantic":
        from .semantic_matcher import SemanticMatcher
        try:
            return SemanticMatcher(persist=persist)
        except ImportError as exc:
            raise ValueError(str(exc)) from exc
    if name == "ollama":
        from .semantic_matcher import SemanticMatcher
        try:
            return SemanticMatcher(backend="ollama", persist=persist)
        except (ImportError, RuntimeError) as exc:
            raise ValueError(str(exc)) from exc
    raise ValueError(f"unknown matcher {name!r} — the shipped matchers are "
                     f"{', '.join(MATCHERS)}; a custom one is named "
                     f"'module:attribute' (see load_matcher).")


def load_matcher(spec: str, abs_tol: float = 0.0, pct_tol: float = 0.05,
                 persist: bool = True) -> Optional[Matcher]:
    """A shipped matcher by name, or a custom one by ``'module:attribute'``.

    ``ui.App`` can be handed a matcher because a host constructs it in Python.
    ``nestor serve`` and ``nestor ask`` cannot: they *are* the process, so there
    is no earlier moment at which a host could call ``memory.set_matcher()``, and
    a name off a command line cannot conjure a class nobody shipped. That left a
    custom domain unable to use either surface at all — a model asking over MCP
    got ``pending`` for a phrase a human had just sealed through the fixed UI.
    IDEAS §6.41; this is the half §6.40 did not reach.

    So a spec containing ``:`` is an import path::

        nestor serve --matcher acme.incidents:SERIALS      # a module attribute
        nestor ask   --matcher acme.incidents:SerialMatcher  # or a callable

    The attribute may be a ready matcher or something callable that returns one;
    a class is the common case and is called with no arguments. Whatever comes
    back must offer ``normalize`` and ``similarity``, and is refused here if it
    does not — a matcher that fails the seam at the first *query* fails it after
    the operator has already been told the server started.

    ``"string"`` returns ``None``, not a ``StringMatcher``: None means "defer to
    the process-wide matcher", which is what a host that installed one is
    entitled to expect, and constructing one here would silently override it.

    **This imports and runs the module named.** That is the same authority the
    command line already has — an operator who can pass this flag can pass
    ``python -c`` — so it is not a new privilege, but it is the reason the spec
    is a flag and never a value read from a request, a bundle or a stored row.
    """
    spec = (spec or "").strip()
    if not spec or spec == "string":
        return None
    if ":" not in spec:
        return build_matcher(spec, abs_tol=abs_tol, pct_tol=pct_tol, persist=persist)

    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise ValueError(
            f"matcher {spec!r} is not a usable import path — it wants "
            f"'module:attribute', e.g. 'acme.incidents:SERIALS'")
    import importlib
    # Every failure below becomes a ValueError naming the spec, because every
    # caller of this function turns a ValueError into "refusing to start: …" and
    # anything else into a traceback. The list of ways this can go wrong is long
    # and dull — a class whose __init__ takes arguments, a leading dot, a module
    # that raises at import, a syntax error, a factory that throws — and the
    # first of those is the single most likely mistake a user makes with this
    # feature. Catching only ImportError meant the common case tracebacked out
    # of a stdio server, which is a broken pipe to whatever launched it.
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise ValueError(
            f"cannot import {module_name!r} for matcher {spec!r}: "
            f"{type(exc).__name__}: {exc}") from exc
    try:
        found = getattr(module, attr)
    except AttributeError as exc:
        raise ValueError(f"{module_name!r} has no attribute {attr!r}") from exc

    # A class or factory is the common case; a module-level instance is the other.
    #
    # `isinstance(found, type)` rather than "does it look like a matcher yet":
    # a *class* already has `normalize` and `similarity` as attributes — they are
    # the unbound functions — so duck-typing here silently accepts the class
    # itself and every later call arrives one argument short.
    if isinstance(found, type) or (callable(found)
                                   and not hasattr(found, "normalize")):
        try:
            found = found()
        except Exception as exc:
            raise ValueError(
                f"calling {spec} to build a matcher raised "
                f"{type(exc).__name__}: {exc}") from exc
    # Re-asked after the call, not only before it: a factory that returns the
    # class rather than an instance lands here still a class, with `normalize`
    # present as an unbound function, and would pass the seam check below only
    # to fail at the first query — which is the exact failure this validation
    # exists to move forward to startup.
    if isinstance(found, type):
        raise ValueError(
            f"{spec} produced the class {found.__name__} rather than an "
            f"instance of it — a factory has to return a built matcher")
    missing = [m for m in ("normalize", "similarity") if not callable(getattr(found, m, None))]
    if missing:
        raise ValueError(
            f"{spec} is not a Matcher — the seam is normalize(value) and "
            f"similarity(a_norm, b_norm), and this is missing: {', '.join(missing)}")
    return found


def _candidate(m: dict) -> dict:
    pair = m["pair"]
    return {"similarity": m["similarity"], "status": pair["status"],
            "servable": memory.is_verified_seal(pair), "id": pair["id"],
            "source_text": pair["source_text"], "target_text": pair["target_text"],
            "verifier": pair.get("verifier", "")}


#: How many candidates `match` shows. A display page, deliberately not the set
#: the reason is computed over — classifying from the page is what let a forged
#: seal ranked ninth go unnamed.
_MATCH_DISPLAY = 8

#: "every eligible row". `lookup` slices after scoring, so this only has to
#: exceed any plausible domain; it is not a scan bound.
_ALL_CANDIDATES = 1_000_000


def _classify(store: Storage, matcher: Matcher, text: str, norm: str,
              source_lang: str, target_lang: str,
              candidates: list[dict], threshold: float) -> tuple[str, dict]:
    """Why this query would not be served — the actual reason, not a guess at it.

    Returns a :data:`nestor.persona.SPEECH_ACTS` member and the facts that act
    interpolates. **The act, not the sentence**: this used to return prose, so
    every test about *which* refusal happened was a substring match, and a
    reworded branch either broke tests that were about classification or left
    negative assertions passing vacuously. :func:`_why_not_served` renders.

    ``best_sealed`` can decline a row for five different reasons: it is not
    sealed, it is rejected for this query, it is under the context floor, it is
    under the seal threshold, or its signature does not verify. The surface
    reported one of them unconditionally — *"N candidate(s) below THRESHOLD"* —
    and could be wrong twice in the same sentence: ``matches`` is filled from
    ``lookup(context_threshold=0.0)``, which is unfiltered and therefore not
    "below" anything, while ``served`` comes from ``best_sealed``, which filters
    by **status**. An exact query scoring 1.0000 against a draft row printed
    ``8 candidate(s) below 0.92``: the count was unrelated to the threshold and
    the one row that mattered was above it. The true answer was "found it, it is
    not sealed."

    Nothing was bypassed and no rule was missed — the code answered a narrower
    question than the one it was asked, and reported the narrow answer as the
    whole one. That is IDEAS §1.9's shape, in a message rather than a query, and
    a review surface that misstates its own reason is worse than a silent one:
    it sends the reader to fix the wrong thing.

    ``candidates`` must therefore be **every** scored row, not a display page.
    The first version of this function classified from the top-8 shown to the
    reader, and a forged seal ranked ninth was invisible to it — so the branch
    written to name forged seals reported "nobody has verified this yet" while a
    row claiming to be sealed sat above the bar. That is the same defect one
    layer down, and it is the reason the caller now takes its display slice
    *after* this runs rather than before.

    The order below is not ``best_sealed``'s. That checks signatures last,
    because an HMAC is expensive and a row that cannot win need not be verified;
    this checks them first, because a forged seal is the most alarming thing
    that can be true of a query and it should not be buried under a note about
    drafts. The two agree on *whether* to serve; only the order of explanation
    differs.
    """
    above = [c for c in candidates if c["similarity"] >= threshold]
    if above:
        unverifiable = [c for c in above if c["status"] == "sealed" and not c["servable"]]
        if unverifiable:
            return "forged_seal", {"count": len(unverifiable), "threshold": threshold}
        return "nothing_sealed", {
            "best": max(c["similarity"] for c in above),
            "threshold": threshold,
            "kinds": ", ".join(sorted({c["status"] for c in above})),
        }
    if candidates:
        # `len(candidates)` is the whole eligible domain, not a page. Report the
        # shape the reader can act on: the closest score, how many were scored,
        # and — separately — how many of them they are being shown.
        return "below_threshold", {
            "count": len(candidates),
            "best": candidates[0]["similarity"],
            "threshold": threshold,
            "shown": min(len(candidates), _MATCH_DISPLAY),
        }
    # An empty candidate list can mean "absent" or "refused", and reporting a
    # refusal as an absence hides the very record that decided the question.
    # There are two ways to refuse and they live in different places:
    # `reject_pair` sets tm_pairs.status='rejected' (dropped by lookup at
    # memory.py's eligibility filter), while `reject_match` writes tm_rejections
    # (read by rejected_ids). Consulting only the second reported half the
    # rejection surface as "nothing matched at all".
    # SCORED, not key-matched. The first version of this looked up the exact
    # normalized key, which fixed the case that was reported and not the class:
    # one character off ("a bad mappingg" scores 0.963 against "a bad mapping")
    # and the old wrong sentence came straight back. Worse, under the numeric
    # matcher every unparseable input normalizes to one NaN sentinel, so an
    # exact-key hit could name a rejected pair the query had nothing to do with
    # — while asserting "this exact source". Scoring answers the question that
    # was actually asked.
    rejected_rows = [r for r in store.memory_candidates(source_lang, target_lang)
                     if r["status"] == "rejected"]
    if rejected_rows:
        raw_score, sims = memory._raw_score_sims(matcher, text, rejected_rows)
        near = [r for r in rejected_rows
                if round(memory._similarity_for_row(matcher, text, norm, r,
                                                    raw_score=raw_score, sims=sims),
                         3) >= threshold]
        if near:
            return "rejected_outright", {"count": len(near)}
    bad_pairs, bad_targets = memory.rejected_ids(norm, source_lang, target_lang, store)
    if bad_pairs or bad_targets:
        # Count the RECORDS, and say so. `rejected_ids` returns rejected pair
        # ids and rejected target texts, which is how many "no"s were recorded
        # — not how many rows they suppressed. A store holding one pair and
        # three rejections reported "3 candidate(s) are suppressed", which is
        # the same defect this function exists to fix: a number attached to a
        # noun it does not count.
        # The RECORDS, read from the table. `rejected_ids` returns two SETS
        # built from the same rows, so one rejection naming both a pair_id and
        # a target_text counted as 2, and two records naming the same target
        # collapsed to 1 — wrong in both directions. The previous fix for this
        # sentence reproduced its own bug one line lower.
        return "suppressed", {
            "count": len(store.memory_rejections(norm, source_lang, target_lang)),
        }
    return "nothing_in_domain", {"source_lang": source_lang,
                                 "target_lang": target_lang}


def _why_not_served(store: Storage, matcher: Matcher, text: str, norm: str,
                    source_lang: str, target_lang: str,
                    candidates: list[dict], threshold: float,
                    persona: "Optional[Persona]" = None) -> str:
    """The sentence for :func:`_classify`'s verdict, in the installed persona.

    Two functions rather than one because a classifier that returns prose can
    only be tested through prose. Every assertion about *which* refusal this is
    used to be a substring match on the sentence — so rewording a branch either
    broke tests that were about classification, or, worse, left four negative
    assertions in ``tests/test_findings_2026_08_05.py`` passing while checking
    nothing, because no branch could produce the phrase whose absence they
    asserted. The act is the fact; the sentence is a rendering of it.
    """
    act, facts = _classify(store, matcher, text, norm, source_lang, target_lang,
                           candidates, threshold)
    return get_persona(persona).say(act, **facts)


def ask(store: Storage, text: str, source_lang: str = "en", target_lang: str = "es",
        engine_name: str = "offline", matcher: Optional[Matcher] = None) -> dict:
    """Run the cascade over one phrase: sealed, draft, or pending.

    Appends a passage to the ledger, exactly as any other serve does — an answer
    served without a trail is the thing Nestor exists to prevent, and neither a
    browser nor a model is an exception to that.

    ``matcher`` must be the domain's own wherever one is in use. The cascade and
    the candidate list below both key off it, and a read keyed differently from
    the writes is how a sealed row stops being found (IDEAS §6.40).
    """
    if not text.strip():
        raise ValueError("nothing to ask")
    passage = cascade.translate_segment(
        text, source_lang, target_lang, engine=get_engine(engine_name), store=store,
        matcher=matcher)
    return {
        "passage": {"source": passage.source, "target": passage.target,
                    "state": passage.state, "mark": passage.mark, "tier": passage.tier,
                    "engine": passage.engine, "confidence": passage.confidence,
                    "meta": passage.meta},
        "verified": passage.state == "sealed",
        "matches": [_candidate(m) for m in
                    memory.lookup(text, source_lang, target_lang, limit=5, store=store,
                                  matcher=matcher)],
        "threshold": memory.SEAL_THRESHOLD,
    }


def resolve(store: Storage, surface: str, domain: str = "entity",
            matcher: Optional[Matcher] = None) -> dict:
    """Alias → canonical entity, with the same three answers the cascade gives.

    ``matcher`` reaches both halves, and it has to, because this function used to
    use **two** in one response: the verdict came from ``EntityResolver`` (which
    hardcodes ``StringMatcher`` when given none) while ``candidates`` came from
    ``memory.lookup`` with no matcher at all — the process-wide one. With a
    custom matcher installed, one payload could carry ``verified: False`` beside
    a candidate scoring ``1.0``, which is two answers to one question.

    Passing it also stops a server that was *told* how its domain is keyed from
    contradicting itself: ``nestor_ask`` honoured the matcher and
    ``nestor_resolve`` did not, so a model got "no human verified this mapping"
    for a mapping a human had sealed.
    """
    if not surface.strip():
        raise ValueError("nothing to resolve")
    resolver = EntityResolver(store, domain=domain, matcher=matcher)
    result = resolver.resolve(surface)
    result["domain"] = domain
    result["verified"] = bool(result.get("sealed"))
    # `resolver.matcher`, not `matcher`: it is the one the verdict above was
    # reached with, including the StringMatcher default when none was given, so
    # the two halves of this payload cannot disagree about what a match is.
    result["candidates"] = [
        {**_candidate(m), "surface": m["pair"]["source_text"],
         "canonical": m["pair"]["target_text"]}
        for m in memory.lookup(surface, domain, domain, limit=5, store=store,
                               matcher=resolver.matcher)]
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
          matcher: "str | Matcher" = "string", abs_tol: float = 0.0,
          pct_tol: float = 0.05, persist: bool = True) -> dict:
    """The bare mechanic over any domain: normalize, score, would it be served?

    ``matcher`` is a shipped matcher's **name** when it came off a wire, or a
    :class:`~nestor.matcher.Matcher` when the caller holds the domain's own. A
    name cannot conjure a custom matcher, so a host serving a custom domain has
    to be able to hand over the object — otherwise this endpoint answers "would
    this be served?" under a different notion of similarity than the one that
    sealed the row, which is a confident wrong answer to the only question
    Nestor is asked (IDEAS §6.40).
    """
    if not text.strip():
        raise ValueError("nothing to match")
    if isinstance(matcher, str):
        m = build_matcher(matcher, abs_tol=abs_tol, pct_tol=pct_tol, persist=persist)
        matcher_name = matcher
    else:
        m = matcher
        # The same label the ledger records for a tier-1 serve, so the two agree
        # and neither invents a second naming rule. Not a stable identifier —
        # see matcher_audit_fields.
        matcher_name = matcher_audit_fields(m)["matcher"]
    hit = memory.best_sealed(text, source_lang, target_lang, store=store, matcher=m,
                             context_threshold=0.0)
    norm = m.normalize(text)
    # Every scored row, not a page of them: the reason is classified over the
    # whole set (see _why_not_served), and `matches` is sliced for display
    # afterwards. Still one lookup call, as before.
    scored = memory.lookup(text, source_lang, target_lang, limit=_ALL_CANDIDATES,
                           store=store, matcher=m, context_threshold=0.0)
    candidates = [_candidate(mm) for mm in scored]
    return {
        "normalized": norm,
        "served": bool(hit),
        "verified": bool(hit),
        "target": hit["pair"]["target_text"] if hit else "",
        "verifier": hit["pair"].get("verifier", "") if hit else "",
        "confidence": hit["similarity"] if hit else 0.0,
        "threshold": memory.SEAL_THRESHOLD,
        "matcher": matcher_name,
        "matches": candidates[:_MATCH_DISPLAY],
        "reason": "" if hit else _why_not_served(
            store, m, text, norm, source_lang, target_lang, candidates,
            memory.SEAL_THRESHOLD),
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
