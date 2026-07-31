"""Nestor in a browser — the queue, the memory and the ledger, for a human.

Nestor's whole claim is that a human checked the answer. Until now that human
had to write Python to do their job: the reviewer worked the tier-2 queue
through ``graduate_segment`` calls typed into a REPL, and the curator browsed
the sealed memory through :class:`~nestor.curator.Curator`. Both are library
surfaces. Neither is a place a person can sit down at.

This is that place. One local page, five views, each one a surface the package
already has and nobody could see:

* **Queue** — the segments the cascade left for review. Seal one as drafted,
  correct it and seal that, or reject it; every decision is signed and ledgered,
  and the segment leaves the queue.
* **Memory** — the curator's view over any domain in the store: browse, filter,
  inspect provenance and every rejection recorded against a pair, unseal, reject,
  restore, seal one by hand, export a bundle and import one. Every row reports
  ``servable`` beside ``status``, so a seal that would *not* be served is visible
  rather than inferred.
* **Ask** — the mechanic in whichever recipe you pick: translate (the cascade),
  resolve an entity, reconcile a figure, or run the bare seam over any domain.
  The state is the point: ✓ sealed, ~ draft, ! pending — with the ranked
  candidates that produced it and what each one scored.
* **Signals** — three things the package records that no single row shows:
  seals somebody overwrote (which the store keeps no trace of at all), queries
  the reviewers keep refusing (evidence about the *threshold* in this domain),
  and pairs refused against many unrelated queries (evidence the pair is junk,
  while it is still being served).
* **Ledger** — the chain's verify result, its head, and the entries themselves,
  so the audit trail can be read where the decisions are made.

Deliberate properties, in the same spirit as the rest of the package:

* **Stdlib only.** ``http.server`` and one inlined page. Nestor's runtime
  dependency count stays zero, and the page loads nothing from the network — a
  Content-Security-Policy of ``default-src 'none'`` is served with it, so an
  audit surface cannot phone anywhere.
* **Loopback by default, and no authentication.** The verifier is *typed*, not
  proven: this UI can seal as any name. That is the same trust model as calling
  ``memory.add_pair(verifier="rita")`` yourself, and it is why binding to a
  non-loopback address requires ``--allow-remote`` and prints what it costs.
  Seal *signatures* (``NESTOR_SEAL_KEY``) are what make a seal unforgeable by
  someone with database access; nothing here weakens or replaces them.
* **Read-only mode.** ``--read-only`` refuses every mutating call at the API
  layer, for showing the memory to someone without handing them the ability to
  change it.

Run it::

    nestor ui --db data/nestor.db                    # http://127.0.0.1:8765
    python -m nestor.ui --db data/nestor.db          # same, without the console script
    nestor-ui --db data/nestor.db --open             # and its own entry point

The questions it answers are defined once in :mod:`nestor.answer`, shared with
the terminal (:mod:`nestor.cli`) and the model-facing server
(:mod:`nestor.serve`) — a system that tells a model "verified" while showing a
curator "draft" has already lost the argument.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import sys
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping, Optional

from . import answer, cascade, ledger as ledger_mod, memory, portable, signing, storage
from .curator import CurationUnsupportedError, Curator
from .entity import EntityResolver
from .reconcile import Reconciler
from .sqlite_store import SqliteStore
from .storage import Storage, supports_curation, supports_queue, supports_rejection
from .ui_page import PAGE

MAX_BODY = 1 << 20          # 1 MiB — a review decision is never larger than this


class ApiError(Exception):
    """A refusal with an HTTP status and a message meant for a human to read."""

    def __init__(self, status: int, message: str, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


@dataclass
class App:
    """Everything a request needs: the store, the domain, and the policy."""

    store: Storage
    source_lang: str = "en"
    target_lang: str = "es"
    engine_name: str = "offline"
    read_only: bool = False
    verifier_hint: str = ""
    db_path: str = ""

    def curator(self, source_lang: str = "", target_lang: str = "") -> Curator:
        """A curator over one domain, or over every domain when both are empty.

        Curation is an optional Storage capability; a store without it gets a
        501 rather than a page of empty tables, because "nothing verified yet"
        and "this store cannot tell you what was verified" are different facts.
        """
        try:
            return Curator(self.store, source_lang, target_lang)
        except CurationUnsupportedError as exc:
            raise ApiError(501, str(exc), code="unsupported") from exc


# --------------------------------------------------------------------------
# Request helpers
# --------------------------------------------------------------------------

def _str(params: Mapping[str, Any], key: str, default: str = "") -> str:
    value = params.get(key, default)
    return value.strip() if isinstance(value, str) else default


def _int(params: Mapping[str, Any], key: str, default: int) -> int:
    try:
        return int(params.get(key, default))
    except (TypeError, ValueError):
        return default


def _float(params: Mapping[str, Any], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def _verifier(payload: Mapping[str, Any]) -> str:
    """The name a decision is recorded under — required, never defaulted.

    ``memory`` treats an empty verifier as *unknown* rather than as a person:
    two empty verifiers are not the same actor, so an anonymous re-seal is a
    conflict rather than a self-correction (see ``memory._same_verifier``).
    A UI that quietly sent ``""`` would file every decision under that unknown
    actor, so it asks instead.
    """
    who = _str(payload, "verifier")
    if not who:
        raise ApiError(400, "Who is making this decision? Set a name in the "
                            "'acting as' box — an empty verifier is recorded as "
                            "unknown, not as you.", code="verifier_required")
    return who


def _pair_id(payload: Mapping[str, Any]) -> str:
    pair_id = _str(payload, "pair_id")
    if not pair_id:
        raise ApiError(400, "pair_id is required", code="bad_request")
    return pair_id


def _require_rejection(app: App) -> None:
    if not supports_rejection(app.store):
        raise ApiError(501, f"{type(app.store).__name__} cannot record rejections "
                            f"(see storage.supports_rejection) — refusing a 'no' it "
                            f"would drop.", code="unsupported")


def _require_queue(app: App) -> None:
    if not supports_queue(app.store):
        raise ApiError(501, f"{type(app.store).__name__} cannot list the review queue "
                            f"(see storage.supports_queue).", code="unsupported")


# --------------------------------------------------------------------------
# Read endpoints
# --------------------------------------------------------------------------

def _state(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """What the whole page needs to know before it renders anything."""
    ok, detail = ledger_mod.verify()
    caps = {"curation": supports_curation(app.store),
            "rejection": supports_rejection(app.store),
            "queue": supports_queue(app.store)}
    summary: dict = {}
    if caps["curation"]:
        summary = app.curator().summary()
    return {
        "read_only": app.read_only,
        "signing_enabled": signing.signing_enabled(),
        "engine": app.engine_name,
        "db": app.db_path,
        "verifier_hint": app.verifier_hint,
        "domain": {"source_lang": app.source_lang, "target_lang": app.target_lang},
        "capabilities": caps,
        "stats": memory.stats(store=app.store),
        "summary": summary,
        "ledger": {"ok": ok, "detail": detail, "path": str(cascade._ledger_path())},
    }


def _pairs(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    c = app.curator(_str(query, "source_lang"), _str(query, "target_lang"))
    limit = max(1, min(_int(query, "limit", 50), 500))
    if _str(query, "unverifiable") == "1":
        # Rows that SAY sealed and would not be served. The curator's sharpest
        # question, so it gets a filter of its own rather than a column to scan.
        rows = c.unverifiable(limit=limit)
    else:
        rows = c.list(status=_str(query, "status"), verifier=_str(query, "verifier"),
                      contains=_str(query, "contains"), limit=limit,
                      offset=_int(query, "offset", 0))
    return {"pairs": rows, "count": len(rows)}


def _pair(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    detail = app.curator().get(_str(query, "id"))
    if detail is None:
        raise ApiError(404, "no such pair", code="not_found")
    return {"pair": detail}


def _queue(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Segments still awaiting a decision, grouped under their document."""
    _require_queue(app)
    status = _str(query, "status", "pending")
    segments = app.store.list_segments(status=status,
                                       limit=max(1, min(_int(query, "limit", 200), 1000)))
    docs: dict[str, dict] = {}
    for seg in segments:
        doc_id = seg.get("document_id", "")
        if doc_id not in docs:
            doc = app.store.get_document(doc_id) or {"id": doc_id, "title": "(unknown document)"}
            docs[doc_id] = {**doc, "segments": []}
        docs[doc_id]["segments"].append(seg)
    return {"documents": list(docs.values()),
            "pending": sum(len(d["segments"]) for d in docs.values())}


def _ledger_view(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """The chain and its verdict, together.

    ``entries`` deliberately does not verify and ``verify`` deliberately does not
    read entries back — an investigator needs both answers at once, so this is
    the one place they are joined.
    """
    ok, detail = ledger_mod.verify()
    kind = _str(query, "kind") or None
    rows = ledger_mod.entries(kind=kind, limit=max(1, min(_int(query, "limit", 200), 2000)))
    kinds = sorted({r.get("kind", "") for r in ledger_mod.entries(limit=2000) if r.get("kind")})
    # The tip travels with the verdict: the walk cannot vouch for the newest
    # entry, so a human who wants that guarantee has to pin this value somewhere
    # the ledger's writer cannot reach.
    return {"ok": ok, "detail": detail, "head": ledger_mod.head(),
            "entries": list(reversed(rows)), "kinds": kinds}


def _replaced_seals(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Seals somebody overwrote — the one thing the store keeps no trace of.

    ``add_pair`` refuses a different verifier's overwrite, so an entry here with
    ``same_verifier: false`` means a human was shown another human's decision and
    chose to overrule it. That is the highest-signal event the curator surface
    has, and it lived in a library method with no view.
    """
    return {"replaced": app.curator().replaced_seals(
        conflicts_only=_str(query, "all") != "1",
        limit=max(1, min(_int(query, "limit", 200), 2000)))}


def _rejections(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """The aggregate the recorded "no"s add up to. See Curator.rejection_signals."""
    return app.curator(_str(query, "source_lang"), _str(query, "target_lang")
                       ).rejection_signals(min_query=max(1, _int(query, "min_query", 2)),
                                           min_pair=max(1, _int(query, "min_pair", 2)))


def _export(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    return app.curator(_str(query, "source_lang"), _str(query, "target_lang")).export()


def _bundle(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """The portable, re-importable form — signatures and all."""
    return portable.export_bundle(app.store, source_lang=_str(query, "source_lang"),
                                  target_lang=_str(query, "target_lang"),
                                  include_ledger=_str(query, "ledger", "1") != "0")


def _import(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Bring a bundle in — as a report first, and only then for real.

    ``dry_run`` defaults to true here as it does in the library: an import
    decides what this instance will serve as human-verified, so the human sees
    the report (what would land sealed, what would be demoted for failing to
    verify, what conflicts) before anything is written. Committing it is a
    verification decision, so it needs a name like every other one.
    """
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict):
        raise ApiError(400, "send the bundle as a JSON object under 'bundle'",
                       code="bad_request")
    dry_run = payload.get("dry_run", True) is not False
    who = "" if dry_run else _verifier(payload)
    try:
        return portable.import_bundle(bundle, store=app.store, dry_run=dry_run,
                                      verifier=who,
                                      override_conflicts=bool(payload.get("override_conflicts")))
    except portable.BundleError as exc:
        raise ApiError(400, str(exc), code="bad_bundle") from exc


# --------------------------------------------------------------------------
# Write endpoints
# --------------------------------------------------------------------------

def _ask(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Run the cascade over one phrase and show what came back, and why.

    A write endpoint despite reading like a read: a passage is appended to the
    ledger, exactly as it is for any other serve. An answer served without a
    trail is the thing Nestor exists to prevent, and a browser is not an
    exception to that.
    """
    text = _str(payload, "text")
    if not text:
        raise ApiError(400, "nothing to ask", code="bad_request")
    return answer.ask(app.store, text,
                      _str(payload, "source_lang") or app.source_lang,
                      _str(payload, "target_lang") or app.target_lang,
                      engine_name=app.engine_name)


def _domains(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Every graph in the store, as domain tag pairs with their sizes.

    ``source_lang`` / ``target_lang`` are generic domain tags — languages for
    translation, the entity type for a graph, ``label``/``domain`` for a numeric
    bucket — so one store holds several disjoint graphs. This is how a human
    sees which ones are actually in there instead of guessing tag names.

    The recipe is NOT inferred from the tags. ``("company", "company")`` is
    probably an entity graph and ``("en", "es")`` probably a translation, but
    nothing enforces either, and a UI that guessed wrong would mislabel someone's
    data with total confidence. The human picks the recipe; this only reports
    what exists.
    """
    stats = memory.stats(store=app.store)
    return {"domains": [{"source_lang": sl, "target_lang": tl, "count": n}
                        for sl, tl, n in stats.get("lang_pairs", [])],
            "total": stats.get("total", 0)}


def _entity_resolve(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Alias → canonical entity, with the same three answers the cascade gives."""
    surface = _str(payload, "surface")
    if not surface:
        raise ApiError(400, "nothing to resolve", code="bad_request")
    return answer.resolve(app.store, surface, _str(payload, "domain") or "entity")


def _entity_seal(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    surface = _str(payload, "surface")
    canonical = _str(payload, "canonical")
    if not surface or not canonical:
        raise ApiError(400, "an alias needs both a surface and a canonical entity",
                       code="bad_request")
    domain = _str(payload, "domain") or "entity"
    override = bool(payload.get("override"))
    return EntityResolver(app.store, domain=domain).seal(
        surface, canonical, verifier=_verifier(payload),
        origin=_str(payload, "origin", "ui"),
        override_conflict=override, override_rejection=override)


def _reconciler(payload: Mapping[str, Any], app: App) -> Reconciler:
    return Reconciler(app.store, domain=_str(payload, "domain") or "value",
                      abs_tol=_float(payload, "abs_tol", 0.0),
                      pct_tol=_float(payload, "pct_tol", 0.05))


def _reconcile_check(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """A figure against its sealed baseline: within tolerance, flagged, or nothing."""
    label = _str(payload, "label")
    observed = _str(payload, "observed")
    if not label or not observed:
        raise ApiError(400, "a check needs a label and an observed value",
                       code="bad_request")
    return answer.check(app.store, label, observed,
                        domain=_str(payload, "domain") or "value",
                        abs_tol=_float(payload, "abs_tol", 0.0),
                        pct_tol=_float(payload, "pct_tol", 0.05))


def _reconcile_seal(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    label = _str(payload, "label")
    value = _str(payload, "value")
    if not label or not value:
        raise ApiError(400, "a baseline needs a label and a value", code="bad_request")
    override = bool(payload.get("override"))
    return _reconciler(payload, app).seal_baseline(
        label, value, verifier=_verifier(payload),
        origin=_str(payload, "origin", "ui"),
        override_conflict=override, override_rejection=override)


def _match(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """The bare mechanic over any domain: normalize, score, serve or don't.

    No engine, no queue, no recipe — the seam itself, for a domain someone built
    with the shipped matchers. It answers the only question Nestor ever answers:
    would this be served as verified, and what did the candidates score?
    """
    text = _str(payload, "text")
    if not text:
        raise ApiError(400, "nothing to match", code="bad_request")
    return answer.match(app.store, text,
                        _str(payload, "source_lang") or app.source_lang,
                        _str(payload, "target_lang") or app.target_lang,
                        matcher=_str(payload, "matcher", "string"),
                        abs_tol=_float(payload, "abs_tol", 0.0),
                        pct_tol=_float(payload, "pct_tol", 0.05))


def _seal(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Seal a pair directly — the tier-3 decision, made by hand.

    ``ConflictingSealError`` and ``RejectedPairError`` are reported as 409 with
    the library's own message, and the page offers an explicit override. Both
    are moments where one human is contradicting another's recorded decision;
    the whole point of the guard is that it takes a second, deliberate click.
    """
    source = _str(payload, "source")
    target = _str(payload, "target")
    if not source or not target:
        raise ApiError(400, "a seal needs both a source and a target", code="bad_request")
    who = _verifier(payload)
    source_lang = _str(payload, "source_lang") or app.source_lang
    target_lang = _str(payload, "target_lang") or app.target_lang
    override = bool(payload.get("override"))
    pair = memory.add_pair(source, target, source_lang, target_lang, status="sealed",
                           verifier=who, origin=_str(payload, "origin", "ui"),
                           store=app.store, override_conflict=override,
                           override_rejection=override)
    # add_pair ledgers the seal itself. What it cannot know is that a human was
    # shown another human's decision and chose to overrule it anyway, so that —
    # and only that — is recorded here.
    if override:
        cascade._ledger_append({"kind": "seal_override", "pair_id": pair["id"],
                                "verifier": who, "source_lang": source_lang,
                                "target_lang": target_lang, "origin": "ui"})
    return {"pair": app.curator().get(pair["id"]) or pair}


def _unseal(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    out = app.curator().unseal(_pair_id(payload), verifier=_verifier(payload),
                               reason=_str(payload, "reason"))
    if out is None:
        raise ApiError(404, "no such pair", code="not_found")
    return {"pair": out}


def _restore(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    out = app.curator().restore(_pair_id(payload), verifier=_verifier(payload),
                                reason=_str(payload, "reason"))
    if out is None:
        raise ApiError(404, "no such pair", code="not_found")
    return {"pair": out}


def _reject_pair(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """The mapping itself is wrong — retire it everywhere."""
    _require_rejection(app)
    pair_id = _pair_id(payload)
    memory.reject_pair(pair_id, verifier=_verifier(payload),
                       reason=_str(payload, "reason"), store=app.store)
    return {"pair": app.curator().get(pair_id)}


def _reject_match(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Right pair, wrong query — suppress it here and leave the seal standing.

    This is what a false seal actually is, and it is the one the UI makes easy:
    from the Ask view, where the human is looking at the match that should not
    have been served.
    """
    _require_rejection(app)
    source = _str(payload, "source")
    if not source:
        raise ApiError(400, "reject-match needs the query it was wrong for",
                       code="bad_request")
    rejection = memory.reject_match(
        source, _str(payload, "source_lang") or app.source_lang,
        _str(payload, "target_lang") or app.target_lang,
        pair_id=_str(payload, "pair_id"), target_text=_str(payload, "target_text"),
        verifier=_verifier(payload), reason=_str(payload, "reason"), store=app.store)
    return {"rejection": {k: v for k, v in rejection.items() if k != "reject_sig"}}


def _queue_seal(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Seal a queued segment — as drafted, or as the reviewer corrected it.

    Review is usually neither "yes" nor "no" but "nearly": the draft is right
    apart from one term. Without an edit path that reviewer has to reject the
    segment, then seal the corrected text by hand somewhere else, and the trail
    records a refusal where a correction happened.

    A corrected seal does not go through ``graduate_segment``, which seals the
    stored candidate by definition. It seals the reviewer's text against the
    segment's source and says so in the ledger (``edited``, plus the digest of
    the draft that was *not* sealed), so the trail distinguishes "a human
    accepted the machine's answer" from "a human wrote the answer" — two very
    different facts about a verification.
    """
    _require_queue(app)
    segment_id = _str(payload, "segment_id")
    who = _verifier(payload)
    edited = _str(payload, "target")
    seg = app.store.get_segment(segment_id)
    if not seg or not (seg.get("candidate") or edited):
        raise ApiError(404, "no such segment, or it has no candidate to seal",
                       code="not_found")
    if not edited or edited == seg.get("candidate"):
        pair = cascade.graduate_segment(segment_id, verifier=who, store=app.store)
        if pair is None:
            raise ApiError(404, "no such segment, or it has no candidate to seal",
                           code="not_found")
        return {"pair": pair, "segment_id": segment_id, "edited": False}

    doc = app.store.get_document(seg["document_id"]) or {}
    pair = memory.add_pair(
        seg["source_text"], edited, doc.get("source_lang", app.source_lang),
        doc.get("target_lang", app.target_lang), status="sealed", verifier=who,
        origin=f"doc:{seg['document_id'][:8]}", store=app.store,
        override_conflict=bool(payload.get("override")),
        override_rejection=bool(payload.get("override")))
    app.store.update_segment_status(segment_id, "verified")
    cascade._ledger_append({"kind": "segment_sealed", "segment_id": segment_id,
                            "document_id": seg["document_id"], "pair_id": pair["id"],
                            "verifier": who, "edited": True,
                            "draft_sha": memory._sha(seg.get("candidate", "")),
                            "origin": "ui:queue"})
    return {"pair": pair, "segment_id": segment_id, "edited": True}


def _queue_reject(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    _require_queue(app)
    _require_rejection(app)
    segment_id = _str(payload, "segment_id")
    rejection = cascade.reject_segment(segment_id, verifier=_verifier(payload),
                                       reason=_str(payload, "reason"), store=app.store)
    if rejection is None:
        raise ApiError(404, "no such segment, or it has no candidate to reject",
                       code="not_found")
    return {"segment_id": segment_id, "rejection_id": rejection["id"]}


Handler = Callable[[App, Mapping[str, Any], Mapping[str, Any]], dict]

_ROUTES: dict[tuple[str, str], Handler] = {
    ("GET", "/api/state"): _state,
    ("GET", "/api/pairs"): _pairs,
    ("GET", "/api/pair"): _pair,
    ("GET", "/api/queue"): _queue,
    ("GET", "/api/ledger"): _ledger_view,
    ("GET", "/api/replaced-seals"): _replaced_seals,
    ("GET", "/api/rejections"): _rejections,
    ("GET", "/api/export"): _export,
    ("GET", "/api/domains"): _domains,
    ("GET", "/api/bundle"): _bundle,
    ("POST", "/api/import"): _import,
    ("POST", "/api/ask"): _ask,
    ("POST", "/api/match"): _match,
    ("POST", "/api/entity/resolve"): _entity_resolve,
    ("POST", "/api/entity/seal"): _entity_seal,
    ("POST", "/api/reconcile/check"): _reconcile_check,
    ("POST", "/api/reconcile/seal"): _reconcile_seal,
    ("POST", "/api/seal"): _seal,
    ("POST", "/api/unseal"): _unseal,
    ("POST", "/api/restore"): _restore,
    ("POST", "/api/reject-pair"): _reject_pair,
    ("POST", "/api/reject-match"): _reject_match,
    ("POST", "/api/queue/seal"): _queue_seal,
    ("POST", "/api/queue/reject"): _queue_reject,
}


def dispatch(app: App, method: str, path: str, query: Mapping[str, Any],
             payload: Optional[Mapping[str, Any]] = None) -> tuple[int, dict]:
    """Route one API call. Pure over ``app`` — no sockets, so it is testable.

    Every failure comes back as ``{"error": ...}`` with a status, including the
    library's own refusals: a ``ConflictingSealError`` reaching a browser as a
    stack trace would hide the one message the human needs to read.
    """
    handler = _ROUTES.get((method, path))
    if handler is None:
        return 404, {"error": f"no such endpoint: {method} {path}", "code": "not_found"}
    if method == "POST" and app.read_only:
        return 403, {"error": "this UI is running --read-only; no decision can be "
                              "recorded from it.", "code": "read_only"}
    try:
        return 200, handler(app, query, payload or {})
    except ApiError as exc:
        return exc.status, {"error": exc.message, "code": exc.code}
    except memory.ConflictingSealError as exc:
        return 409, {"error": str(exc), "code": "conflicting_seal"}
    except memory.RejectedPairError as exc:
        return 409, {"error": str(exc), "code": "rejected_pair"}
    except (ValueError, RuntimeError) as exc:
        return 400, {"error": f"{type(exc).__name__}: {exc}", "code": "refused"}


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

def csrf_reason(method: str, headers: Mapping[str, str], host: str) -> Optional[str]:
    """Why this mutating request must be refused, or ``None`` to allow it.

    No cookies are involved, but the UI is reachable at a predictable localhost
    address, so a page in another tab could otherwise POST a seal or an unseal
    into it. Two cheap checks close that: a custom header (a cross-origin form
    post cannot set one, and a cross-origin ``fetch`` that tries is blocked by
    the preflight this server never approves), and an ``Origin`` that must match
    the address the request arrived on when the browser sends one.
    """
    if method != "POST":
        return None
    if (headers.get("X-Nestor-UI") or "") != "1":
        return "missing X-Nestor-UI header — refusing a cross-site request"
    origin = headers.get("Origin")
    if origin:
        netloc = urllib.parse.urlsplit(origin).netloc
        if netloc and host and netloc != host:
            return f"Origin {origin!r} does not match host {host!r}"
    return None


def _make_handler(app: App) -> type[BaseHTTPRequestHandler]:

    class NestorHandler(BaseHTTPRequestHandler):
        server_version = "nestor-ui"
        protocol_version = "HTTP/1.1"

        # -- plumbing --------------------------------------------------------

        def log_message(self, fmt: str, *args) -> None:      # noqa: A003
            sys.stderr.write("  %s %s\n" % (self.address_string(), fmt % args))

        def _send(self, status: int, body: bytes, content_type: str,
                  extra: Optional[dict[str, str]] = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            # The page is entirely self-contained; this says so in a way the
            # browser enforces. An audit surface must not be able to exfiltrate
            # the memory it is showing, even if something is injected into it.
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; "
                "img-src data:; base-uri 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _send_json(self, status: int, payload: dict,
                       extra: Optional[dict[str, str]] = None) -> None:
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8", extra)

        # -- routing ---------------------------------------------------------

        def do_GET(self) -> None:                              # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if not parsed.path.startswith("/api/"):
                self._send_json(404, {"error": "not found", "code": "not_found"})
                return
            query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            status, payload = dispatch(app, "GET", parsed.path, query)
            extra = None
            if parsed.path in ("/api/export", "/api/bundle") and status == 200:
                name = "nestor-export.json" if parsed.path == "/api/export" else "nestor-bundle.json"
                extra = {"Content-Disposition": f'attachment; filename="{name}"'}
            self._send_json(status, payload, extra)

        def do_HEAD(self) -> None:                             # noqa: N802
            self.do_GET()

        def do_POST(self) -> None:                             # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            refusal = csrf_reason("POST", self.headers, self.headers.get("Host", ""))
            if refusal:
                self._send_json(403, {"error": refusal, "code": "csrf"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self._send_json(413, {"error": "request too large", "code": "too_large"})
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError) as exc:
                self._send_json(400, {"error": f"invalid JSON body: {exc}",
                                      "code": "bad_request"})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "JSON body must be an object",
                                      "code": "bad_request"})
                return
            query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            status, out = dispatch(app, "POST", parsed.path, query, payload)
            self._send_json(status, out)

    return NestorHandler


def serve(app: App, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Build a server bound to ``host:port``. The caller runs it."""
    return ThreadingHTTPServer((host, port), _make_handler(app))


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def _is_loopback(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nestor-ui",
        description="Nestor's review queue, curated memory and ledger, in a browser.")
    p.add_argument("--db", default="data/nestor.db",
                   help="SQLite database for the reference store (default: data/nestor.db)")
    p.add_argument("--ledger", default="",
                   help="hash-chained ledger path (default: NESTOR_LEDGER or data/ledger.jsonl)")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8765, help="bind port (default: 8765)")
    p.add_argument("--source-lang", default="en", help="default source domain tag")
    p.add_argument("--target-lang", default="es", help="default target domain tag")
    p.add_argument("--engine", default="offline", choices=("offline", "auto", "claude"),
                   help="draft engine used by the Ask view (default: offline — a click "
                        "in a browser should not silently call a paid API)")
    p.add_argument("--verifier", default="",
                   help="prefill the 'acting as' name (still asserted, never proven)")
    p.add_argument("--read-only", action="store_true",
                   help="refuse every decision; browse and audit only")
    p.add_argument("--allow-remote", action="store_true",
                   help="permit a non-loopback bind (this UI has no authentication)")
    p.add_argument("--open", action="store_true", dest="open_browser",
                   help="open the page in a browser once the server is up")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if not _is_loopback(args.host) and not args.allow_remote:
        print(f"refusing to bind {args.host}: this UI has no authentication — anyone "
              f"who can reach the port can seal, unseal and reject as any verifier. "
              f"Re-run with --allow-remote if that is genuinely what you want.",
              file=sys.stderr)
        return 2

    if args.ledger:
        cascade.set_ledger_path(args.ledger)

    store = SqliteStore(args.db)
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    app = App(store=store, source_lang=args.source_lang, target_lang=args.target_lang,
              engine_name=args.engine, read_only=args.read_only,
              verifier_hint=args.verifier, db_path=args.db)

    httpd = serve(app, args.host, args.port)
    url = f"http://{args.host or '127.0.0.1'}:{args.port}/"
    print(f"Nestor UI  →  {url}")
    print(f"  store    {args.db}")
    print(f"  ledger   {cascade._ledger_path()}")
    print(f"  engine   {args.engine}")
    if args.read_only:
        print("  mode     read-only — no decision can be recorded")
    if not signing.signing_enabled():
        print("  WARNING  NESTOR_SEAL_KEY is not set: seals are trusted on stored "
              "status alone, and this UI cannot tell a real one from a forged row.")
    if not _is_loopback(args.host):
        print("  WARNING  bound to a non-loopback address with no authentication.")
    if args.open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
