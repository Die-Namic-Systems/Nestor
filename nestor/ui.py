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
* **Loopback by default, and authentication only if you set up keys.** With no
  keyring the verifier is *typed*, not proven: this UI seals as whatever you
  type, which is the same trust model as calling ``memory.add_pair(verifier=
  "rita")`` yourself. Set ``NESTOR_KEYRING`` (see :mod:`nestor.keyring`) and the
  "acting as" box becomes a sign-in — a verifier presents their own seal key and
  every decision in the session is signed with it, so the name on a seal is
  evidence about a person. Either way, binding to a non-loopback address
  requires ``--allow-remote`` and prints what it costs.
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
import contextlib
import ipaddress
import json
import os
import pathlib
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping, Optional

from . import answer, cascade, keyring, ledger as ledger_mod, memory, portable, signing, storage
from .curator import CurationUnsupportedError, Curator
from .entity import EntityResolver
from .matcher import Matcher, matcher_audit_fields
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


class Sessions:
    """Who is signed in, and until when.

    The "acting as" box was a text field: this UI could seal as any name,
    because ``verifier`` was a string and nothing anywhere could tell one from
    another. With a keyring installed it stops being a text field. Signing in
    means presenting the verifier's own seal key, and every decision made in
    that session is signed with it — so a seal by ``rita`` is evidence about
    rita rather than evidence that somebody typed "rita".

    What this is not: it is a shared secret, so it proves possession of a key
    rather than the presence of a person, and the server necessarily holds the
    keys it verifies against. The asymmetric upgrade — a signature the server
    checks with a public key it could not have produced — is the follow-on, and
    it is the same seam (``signing.sign_seal(..., key=)``) either way.

    Tokens live in memory only. Restarting the UI signs everyone out, which is
    also how a revocation takes effect.
    """

    def __init__(self, hours: float = 8.0) -> None:
        self.hours = hours
        self._lock = threading.Lock()
        self._tokens: dict[str, tuple[str, datetime]] = {}

    def open(self, verifier: str, key_hex: str) -> dict:
        """Check a verifier's key and hand back a token, or refuse."""
        ring = keyring.get_keyring()
        if ring is None:
            raise ApiError(400, "no keyring is configured, so there is nobody to "
                                "sign in as", code="no_keyring")
        try:
            expected = ring.signing_key(verifier)
        except keyring.UnknownVerifierError as exc:
            raise ApiError(403, str(exc), code="unknown_verifier") from exc
        except keyring.RevokedKeyError as exc:
            raise ApiError(403, str(exc), code="revoked_key") from exc
        try:
            offered = bytes.fromhex((key_hex or "").strip())
        except ValueError:
            offered = b""
        if not offered or not keyring.same_key(offered, expected):
            raise ApiError(403, f"that is not {verifier}'s key.", code="bad_key")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=self.hours)
        with self._lock:
            self._tokens[token] = (verifier, expires)
        return {"token": token, "verifier": verifier, "expires_at": expires.isoformat()}

    def close(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

    def whois(self, token: str) -> Optional[str]:
        """The verifier this token names, or ``None`` if it is unknown or stale."""
        with self._lock:
            found = self._tokens.get(token or "")
            if found is None:
                return None
            verifier, expires = found
            if datetime.now(timezone.utc) >= expires:
                del self._tokens[token]
                return None
        return verifier


@dataclass
class App:
    """Everything a request needs: the store, the domain, its matcher, and the policy.

    ``matcher`` is the domain's own, injected exactly like ``store`` — and it is
    not optional decoration. A domain is a *pair*: the tags that name it and the
    matcher that keys it. This surface used to take only the first half, so every
    decision a human made here was filed under the process-wide default's key
    rather than the domain's own, and IDEAS §6.40 measured what that costs: a
    seal lands as a second row under a key the domain will never compute, the
    draft it was meant to retire stays queued, and a rejection is recorded where
    nothing will ever ask for it — so the wrong match is served again.

    ``None`` means "use the process-wide matcher", which is both the historical
    behaviour and the right answer for a host running one domain. It stops being
    right the moment there are two (see ``demo/two_desks.py``), because a single
    global can only describe one of them.
    """

    store: Storage
    source_lang: str = "en"
    target_lang: str = "es"
    engine_name: str = "offline"
    matcher: Optional[Matcher] = None
    read_only: bool = False
    verifier_hint: str = ""
    db_path: str = ""
    gate_rollup_path: str = ""
    sessions: Sessions = field(default_factory=Sessions)

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

def _domain_matcher(app: "App", source_lang: str, target_lang: str) -> Optional[Matcher]:
    """``app.matcher`` — but only for the domain it actually describes.

    A matcher keys **one** domain. ``App`` holds the tags of one and the matcher
    of the same one, and several endpoints accept per-request tags: the Ask and
    Match views let a human retype them, and ``/api/reject-match`` is shared by
    every recipe, so the Entity view rejects through it carrying the *entity*
    domain.

    Handing ``app.matcher`` to a request about some other domain is the same
    category error as §6.40 itself, one level up — and it was a live regression
    for exactly one release: the Entity view's reject started keying alias
    rejections with the incident domain's matcher, so a human's "no" was
    recorded, signed, and filed where ``EntityResolver`` never looks. Same
    symptom as §6.40, reproduced by §6.40's fix, in the neighbouring recipe.

    So: the App's matcher for the App's domain, and ``None`` — defer to the
    process-wide default, which is what every recipe with its own matcher was
    already getting — for anything else. Except one case in between (§6.92
    finding 2): tags that equal this App's under case-folding but not exactly
    — ``Incident``/``Incident`` against a surface configured ``incident`` — are
    a typo, not another domain. Deferring one of those to the process-wide
    matcher is the same silent §6.40 failure back again, reachable this time by
    a capitalisation mistake instead of a wiring one, so it is refused rather
    than answered `pending`. Deliberately narrow: it takes BOTH tags matching
    case-insensitively to trigger. One tag matching and the other genuinely
    different is a different domain, and defers exactly as before — case-fold
    the tags to decide "near-miss" and this repo would be one step from
    case-folding them to decide identity, which a store holding two domains
    that differ only in case cannot afford (see decision 0076).
    """
    if app.matcher is None:
        return None
    if source_lang == app.source_lang and target_lang == app.target_lang:
        return app.matcher
    if (source_lang.casefold() == app.source_lang.casefold()
            and target_lang.casefold() == app.target_lang.casefold()):
        raise ApiError(
            400,
            f"{source_lang!r}/{target_lang!r} is not a domain this surface "
            f"knows — it differs from {app.source_lang!r}/{app.target_lang!r} "
            f"only in case. Did you mean {app.source_lang!r}/"
            f"{app.target_lang!r}?",
            code="domain_case_mismatch")
    return None


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


def _verifier(app: App, payload: Mapping[str, Any]) -> str:
    """The name a decision is recorded under — required, never defaulted.

    ``memory`` treats an empty verifier as *unknown* rather than as a person:
    two empty verifiers are not the same actor, so an anonymous re-seal is a
    conflict rather than a self-correction (see ``memory._same_verifier``).
    A UI that quietly sent ``""`` would file every decision under that unknown
    actor, so it asks instead.

    **With a keyring installed the name comes from the session, not the
    request.** The typed name is ignored entirely rather than checked against
    the session, because a field that must equal something already known is
    just a way to get a confusing error; the session is the answer to "who is
    this", and the seal is then signed with that verifier's own key.
    """
    if keyring.enabled():
        who = app.sessions.whois(_str(payload, "session"))
        if not who:
            raise ApiError(401, "Sign in first: this instance has a keyring, so a "
                                "decision is recorded under the verifier whose key "
                                "made it, not under a typed name.",
                           code="session_required")
        return who
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

def _willow_home() -> pathlib.Path:
    return pathlib.Path(os.environ.get("WILLOW_HOME", "~/github/.willow")).expanduser()


def _gate_echo(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Nestor seals → charter rollup → Hanuman dispatch handoffs (local files only)."""
    path = (app.gate_rollup_path or "").strip()
    if not path or not os.path.isfile(path):
        return {"rollup": path, "entries": []}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    entries: list[dict[str, Any]] = []
    wh = _willow_home()
    for seal in data.get("seals") or []:
        gate = seal.get("gate") or ""
        dispatch_id = (seal.get("hanuman_dispatch") or "").strip().upper() or None
        entry: dict[str, Any] = {
            "gate": gate,
            "note": seal.get("note"),
            "dispatch_id": dispatch_id,
            "status": None,
            "narrative": "",
            "written_at": "",
        }
        if dispatch_id:
            handoff = wh / "dispatch" / dispatch_id / "handoff.json"
            if handoff.is_file():
                with open(handoff, encoding="utf-8") as hf:
                    h = json.load(hf)
                entry["status"] = "complete"
                entry["narrative"] = h.get("narrative") or ""
                entry["written_at"] = h.get("written_at") or ""
            else:
                entry["status"] = "awaiting"
        entries.append(entry)
    return {"rollup": path, "entries": entries}


def _state(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """What the whole page needs to know before it renders anything."""
    ok, detail = ledger_mod.verify()
    caps = {"curation": supports_curation(app.store),
            "rejection": supports_rejection(app.store),
            "queue": supports_queue(app.store)}
    summary: dict = {}
    if caps["curation"]:
        summary = app.curator().summary()
    ring = keyring.get_keyring()
    # The verifier names are not a secret — they are printed on every seal the
    # memory holds. The keys are, and never leave the file.
    identity = {"required": ring is not None,
                "verifiers": [n for n in (ring.names() if ring else [])
                              if ring.status(n) == "active"],
                "signed_in": app.sessions.whois(_str(query, "session")) or ""}
    return {
        "read_only": app.read_only,
        "identity": identity,
        "signing_enabled": signing.signing_enabled(),
        "engine": app.engine_name,
        "db": app.db_path,
        "verifier_hint": app.verifier_hint,
        # The matcher belongs in the domain block because a domain IS the tags
        # and the matcher. Reporting only the tags is what made §6.40 invisible:
        # two surfaces keyed differently described themselves identically, and
        # nothing an operator could read said which one was filing their seals.
        "domain": {"source_lang": app.source_lang, "target_lang": app.target_lang,
                   "matcher": matcher_audit_fields(memory.get_matcher(app.matcher))["matcher"],
                   "matcher_source": "app" if app.matcher is not None else "process"},
        "capabilities": caps,
        "stats": memory.stats(store=app.store),
        "summary": summary,
        "ledger": {"ok": ok, "detail": detail, "path": str(cascade._ledger_path())},
    }


def _session_open(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Sign in as a verifier by presenting their seal key. See :class:`Sessions`."""
    return app.sessions.open(_str(payload, "verifier"), _str(payload, "key"))


def _session_end(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    app.sessions.close(_str(payload, "session"))
    return {"signed_out": True}


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

    ``unreadable`` is the third: ``verify`` names the *first* line that will not
    parse and then stops, and ``entries`` returns the rest of the file without
    it. Neither says how many are missing from the table, which is the question
    somebody looking at a short chain actually has.
    """
    ok, detail = ledger_mod.verify()
    kind = _str(query, "kind") or None
    rows = ledger_mod.entries(kind=kind, limit=max(1, min(_int(query, "limit", 200), 2000)))
    kinds = sorted({r.get("kind", "") for r in ledger_mod.entries(limit=2000) if r.get("kind")})
    # The tip travels with the verdict: the walk cannot vouch for the newest
    # entry, so a human who wants that guarantee has to pin this value somewhere
    # the ledger's writer cannot reach.
    return {"ok": ok, "detail": detail, "head": ledger_mod.head(),
            "entries": list(reversed(rows)), "kinds": kinds,
            "unreadable": ledger_mod.unreadable()}


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
    sl, tl = _str(query, "source_lang"), _str(query, "target_lang")
    # The matcher label the bundle records (§6.92 finding 1), which an import
    # elsewhere compares against its own. A DOMAIN-scoped request keys on that
    # domain, so `_domain_matcher` is right: `app.matcher` for the App's own
    # domain, defer for another. But the "Export bundle" button sends no tags —
    # a WHOLE-STORE export — and `_domain_matcher("","")` returns None, which
    # would relabel a custom-matcher surface's own rows with the process default
    # and reintroduce the silent mislabel this finding closes. For the unscoped
    # case the surface's own matcher is the honest label: it is what keyed the
    # rows this surface manages. (A store holding a SECOND domain keyed
    # differently cannot be captured by one label — the field is advisory and
    # per-domain labels are a separate change; see decision 0073.)
    matcher = _domain_matcher(app, sl, tl) if (sl or tl) else app.matcher
    return portable.export_bundle(app.store, source_lang=sl, target_lang=tl,
                                  include_ledger=_str(query, "ledger", "1") != "0",
                                  matcher=matcher)


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
    who = "" if dry_run else _verifier(app, payload)
    try:
        return portable.import_bundle(bundle, store=app.store, dry_run=dry_run,
                                      verifier=who,
                                      override_conflicts=bool(payload.get("override_conflicts")),
                                      # This surface's own matcher, to warn when
                                      # the bundle was keyed by another. §6.92.
                                      matcher=app.matcher)
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
    source_lang = _str(payload, "source_lang") or app.source_lang
    target_lang = _str(payload, "target_lang") or app.target_lang
    return answer.ask(app.store, text, source_lang, target_lang,
                      engine_name=app.engine_name,
                      matcher=_domain_matcher(app, source_lang, target_lang))


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
    entity_domain = _str(payload, "domain") or "entity"
    return answer.resolve(app.store, surface, entity_domain,
                          matcher=_domain_matcher(app, entity_domain, entity_domain))


def _entity_seal(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    surface = _str(payload, "surface")
    canonical = _str(payload, "canonical")
    if not surface or not canonical:
        raise ApiError(400, "an alias needs both a surface and a canonical entity",
                       code="bad_request")
    domain = _str(payload, "domain") or "entity"
    override = bool(payload.get("override"))
    return EntityResolver(app.store, domain=domain).seal(
        surface, canonical, verifier=_verifier(app, payload),
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
        label, value, verifier=_verifier(app, payload),
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
    source_lang = _str(payload, "source_lang") or app.source_lang
    target_lang = _str(payload, "target_lang") or app.target_lang
    named = _str(payload, "matcher")
    own = _domain_matcher(app, source_lang, target_lang)
    if own is not None:
        # A named matcher off the wire cannot conjure this domain's own, and
        # answering under a different one would be a confident wrong answer to
        # the only question Nestor is asked. Refuse rather than silently
        # substitute — a caller who asked for `numeric` on a domain keyed by
        # something else needs to know the two are not interchangeable.
        #
        # The page does not send `matcher` at all on such a surface (it shows the
        # matcher's name instead of the picker), so this refusal is for a
        # hand-rolled client. It reads the same `/api/state` the page does.
        if named and named != matcher_audit_fields(own)["matcher"]:
            raise ApiError(
                400,
                f"this surface serves a domain keyed by "
                f"{matcher_audit_fields(own)['matcher']!r}; it cannot score "
                f"{named!r} as well",
                code="bad_request")
        chosen: "str | Matcher" = own
    else:
        chosen = named or "string"
    return answer.match(app.store, text, source_lang, target_lang,
                        matcher=chosen,
                        abs_tol=_float(payload, "abs_tol", 0.0),
                        pct_tol=_float(payload, "pct_tol", 0.05),
                        # `persist=False` stops the semantic matcher writing its
                        # embedding cache, which is a write like any other. It is
                        # honoured only on the name path — an injected matcher was
                        # constructed by the host and owns its own persistence
                        # policy; this surface will not reach in and change it.
                        persist=not app.read_only)


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
    who = _verifier(app, payload)
    source_lang = _str(payload, "source_lang") or app.source_lang
    target_lang = _str(payload, "target_lang") or app.target_lang
    override = bool(payload.get("override"))
    pair = memory.add_pair(source, target, source_lang, target_lang, status="sealed",
                           verifier=who, origin=_str(payload, "origin", "ui"),
                           store=app.store,
                           matcher=_domain_matcher(app, source_lang, target_lang),
                           override_conflict=override,
                           override_rejection=override)
    # add_pair ledgers the seal itself. What it cannot know is that a human was
    # shown another human's decision and chose to overrule it anyway, so that —
    # and only that — is recorded here.
    if override:
        cascade._ledger_append({"kind": "seal_override", "pair_id": pair["id"],
                                "verifier": who, "source_lang": source_lang,
                                "target_lang": target_lang, "origin": "ui"})
    return {"pair": app.curator().get(pair["id"]) or pair}


def _seal_draft(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """Seal an existing draft pair — typical for fleet-gap commitment picks."""
    pair_id = _pair_id(payload)
    row = app.store.memory_get(pair_id)
    if row is None:
        raise ApiError(404, "no such pair", code="not_found")
    if row.get("status") != "draft":
        raise ApiError(400, "only draft pairs can be sealed in place", code="bad_request")
    target = _str(payload, "target") or (row.get("target_text") or "")
    if not target.strip():
        raise ApiError(400, "a seal needs a target commitment", code="bad_request")
    who = _verifier(app, payload)
    override = bool(payload.get("override"))
    pair = memory.add_pair(
        row["source_text"],
        target,
        row.get("source_lang", app.source_lang),
        row.get("target_lang", app.target_lang),
        status="sealed",
        verifier=who,
        origin=row.get("origin") or "ui:seal-draft",
        reason=_str(payload, "reason"),
        store=app.store,
        # The measured heart of §6.40. `add_pair` recomputes the key from the
        # text, so without the domain's matcher this "seal in place" inserts a
        # second row under the default's key and leaves the draft it was sealing
        # queued — a 200, a signed seal, and nothing retired. Keyed off the
        # ROW's domain, not the App's: a curator can seal a draft from any
        # domain the store holds, and only the App's own gets the App's matcher.
        matcher=_domain_matcher(app, row.get("source_lang", app.source_lang),
                                row.get("target_lang", app.target_lang)),
        override_conflict=override,
        override_rejection=override,
    )
    if override:
        cascade._ledger_append(
            {
                "kind": "seal_override",
                "pair_id": pair["id"],
                "verifier": who,
                "source_lang": row.get("source_lang", ""),
                "target_lang": row.get("target_lang", ""),
                "origin": "ui:seal-draft",
            }
        )
    return {"pair": app.curator().get(pair["id"]) or pair}


def _unseal(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    out = app.curator().unseal(_pair_id(payload), verifier=_verifier(app, payload),
                               reason=_str(payload, "reason"))
    if out is None:
        raise ApiError(404, "no such pair", code="not_found")
    return {"pair": out}


def _restore(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    out = app.curator().restore(_pair_id(payload), verifier=_verifier(app, payload),
                                reason=_str(payload, "reason"))
    if out is None:
        raise ApiError(404, "no such pair", code="not_found")
    return {"pair": out}


def _reject_pair(app: App, query: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    """The mapping itself is wrong — retire it everywhere."""
    _require_rejection(app)
    pair_id = _pair_id(payload)
    memory.reject_pair(pair_id, verifier=_verifier(app, payload),
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
    source_lang = _str(payload, "source_lang") or app.source_lang
    target_lang = _str(payload, "target_lang") or app.target_lang
    rejection = memory.reject_match(
        source, source_lang, target_lang,
        pair_id=_str(payload, "pair_id"), target_text=_str(payload, "target_text"),
        verifier=_verifier(app, payload), reason=_str(payload, "reason"), store=app.store,
        # A rejection is filed under the query's key, and `best_sealed` looks it
        # up under the domain's. Keyed by the default instead, the human's "no"
        # is recorded correctly, signed, and invisible — and the wrong match is
        # served again, which is the promise this endpoint exists to keep.
        #
        # Via `_domain_matcher`, because this endpoint is shared by every recipe:
        # the Entity view rejects an alias through it carrying the *entity*
        # domain, which `EntityResolver` keys with its own StringMatcher. Passing
        # the App's matcher there re-created §6.40 one recipe over.
        matcher=_domain_matcher(app, source_lang, target_lang))
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
    who = _verifier(app, payload)
    edited = _str(payload, "target")
    seg = app.store.get_segment(segment_id)
    if not seg or not (seg.get("candidate") or edited):
        raise ApiError(404, "no such segment, or it has no candidate to seal",
                       code="not_found")
    # A segment's domain is its document's, which need not be the App's.
    seg_doc = app.store.get_document(seg["document_id"]) or {}
    seg_matcher = _domain_matcher(app, seg_doc.get("source_lang", app.source_lang),
                                  seg_doc.get("target_lang", app.target_lang))
    if not edited or edited == seg.get("candidate"):
        pair = cascade.graduate_segment(segment_id, verifier=who, store=app.store,
                                        matcher=seg_matcher)
        if pair is None:
            raise ApiError(404, "no such segment, or it has no candidate to seal",
                           code="not_found")
        return {"pair": pair, "segment_id": segment_id, "edited": False}

    doc = seg_doc
    pair = memory.add_pair(
        seg["source_text"], edited, doc.get("source_lang", app.source_lang),
        doc.get("target_lang", app.target_lang), status="sealed", verifier=who,
        origin=f"doc:{seg['document_id'][:8]}", store=app.store, matcher=seg_matcher,
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
    seg = app.store.get_segment(segment_id) or {}
    doc = app.store.get_document(seg.get("document_id", "")) or {} if seg else {}
    rejection = cascade.reject_segment(
        segment_id, verifier=_verifier(app, payload),
        reason=_str(payload, "reason"), store=app.store,
        matcher=_domain_matcher(app, doc.get("source_lang", app.source_lang),
                                doc.get("target_lang", app.target_lang)))
    if rejection is None:
        raise ApiError(404, "no such segment, or it has no candidate to reject",
                       code="not_found")
    return {"segment_id": segment_id, "rejection_id": rejection["id"]}


Handler = Callable[[App, Mapping[str, Any], Mapping[str, Any]], dict]

# POSTs that record nothing, and so survive --read-only.
_NO_DECISION = ("/api/session", "/api/session/end")

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
    ("GET", "/api/gate-echo"): _gate_echo,
    ("POST", "/api/session"): _session_open,
    ("POST", "/api/session/end"): _session_end,
    ("POST", "/api/import"): _import,
    ("POST", "/api/ask"): _ask,
    ("POST", "/api/match"): _match,
    ("POST", "/api/entity/resolve"): _entity_resolve,
    ("POST", "/api/entity/seal"): _entity_seal,
    ("POST", "/api/reconcile/check"): _reconcile_check,
    ("POST", "/api/reconcile/seal"): _reconcile_seal,
    ("POST", "/api/seal"): _seal,
    ("POST", "/api/seal-draft"): _seal_draft,
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
    # Signing in records nothing and changes nothing, so it is not a "decision"
    # in the sense --read-only refuses. Refusing it would leave a read-only page
    # unable to say who is looking, which helps nobody.
    if method == "POST" and app.read_only and path not in _NO_DECISION:
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
    except keyring.UnknownVerifierError as exc:
        return 403, {"error": str(exc), "code": "unknown_verifier"}
    except keyring.RevokedKeyError as exc:
        return 403, {"error": str(exc), "code": "revoked_key"}
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


_UI_DEFAULT_LEDGER_VERIFY_SEC = 300.0


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
    p.add_argument("--matcher", default="string",
                   help="the matcher that keys this domain (default: string). A "
                        "domain is the tags AND the matcher; aiming this surface "
                        "at a domain keyed by a different one files every seal "
                        "and rejection where that domain will never look. A "
                        "shipped name (string, numeric, semantic), or a custom "
                        "matcher as 'module:attribute' — the same spec `nestor "
                        "serve` and `nestor ask` take. In-process hosts can still "
                        "pass the object: ui.App(matcher=...)")
    p.add_argument("--engine", default="offline", choices=("offline", "auto", "claude"),
                   help="draft engine used by the Ask view (default: offline — a click "
                        "in a browser should not silently call a paid API)")
    p.add_argument("--verifier", default="",
                   help="prefill the 'acting as' name (still asserted, never proven — "
                        "with a keyring, verifiers sign in with their key instead)")
    p.add_argument("--keyring", default="",
                   help="per-verifier seal keys (default: NESTOR_KEYRING). With one, "
                        "the 'acting as' box becomes a sign-in and a seal is signed "
                        "by the verifier it names")
    p.add_argument("--session-hours", dest="session_hours", type=float, default=8.0,
                   help="how long a sign-in lasts (default: 8 — a shift)")
    p.add_argument("--read-only", action="store_true",
                   help="refuse every decision; browse and audit only")
    p.add_argument("--allow-remote", action="store_true",
                   help="permit a non-loopback bind (this UI has no authentication)")
    p.add_argument("--open", action="store_true", dest="open_browser",
                   help="open the page in a browser once the server is up")
    p.add_argument("--gate-rollup", default="",
                   help="charter JSON listing Nestor seals → Hanuman dispatches "
                        "(default: NESTOR_GATE_ROLLUP or willow governance rollup if present)")
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
    if "NESTOR_LEDGER_VERIFY_INTERVAL_SEC" in os.environ:
        try:
            cascade.ledger_verify_interval_sec()
        except ValueError as exc:
            print(f"refusing to start: {exc}", file=sys.stderr)
            return 2
    else:
        cascade.set_ledger_verify_interval(_UI_DEFAULT_LEDGER_VERIFY_SEC)
    # Resolve identity before anything is opened or bound. A keyring that is
    # configured and unusable is a refusal either way, and the difference
    # between refusing here and refusing lazily is a clean message versus a
    # traceback under a banner that says the server started.
    try:
        if args.keyring:
            keyring.set_keyring(keyring.load(args.keyring))
        keyring.preflight()
    except keyring.KeyringError as exc:
        print(f"refusing to start: {exc}", file=sys.stderr)
        return 2

    # Resolved here, beside the keyring and before the store is opened, for the
    # same reason: a flag that cannot be honoured is a refusal, and refusing
    # before anything is opened costs nothing and leaks nothing. `--matcher
    # semantic` without the extra used to raise ValueError out of main() as a
    # traceback, leaving the store handle open behind it.
    #
    # `--matcher string` is the default and resolves to `None`, not to a fresh
    # StringMatcher: None means "defer to the process-wide matcher", which is
    # what a host that called memory.set_matcher() before launching this surface
    # is entitled to expect. Building one here would override that silently, and
    # substituting a matcher behind a host's back is the whole defect.
    # `redirect_stdout` because this runs somebody else's module when the spec is
    # an import path, and `--read-only` has to reach the matcher's constructor:
    # `answer.match` can only forward `persist` on the name path, so a semantic
    # matcher built here under --read-only must be built with persist=False or
    # its embedding cache writes on a surface that promised not to.
    try:
        with contextlib.redirect_stdout(sys.stderr):
            chosen_matcher = answer.load_matcher(args.matcher,
                                                 persist=not args.read_only)
    except ValueError as exc:
        print(f"refusing to start: {exc}", file=sys.stderr)
        return 2

    store = SqliteStore(args.db)
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    gate_rollup = (args.gate_rollup or os.environ.get("NESTOR_GATE_ROLLUP", "")).strip()
    if not gate_rollup:
        candidate = pathlib.Path(
            "~/github/willow/governance/decisions/nestor-phase1-gate-seals-2026-08-06.json"
        ).expanduser()
        if candidate.is_file():
            gate_rollup = str(candidate)

    app = App(store=store, source_lang=args.source_lang, target_lang=args.target_lang,
              engine_name=args.engine, matcher=chosen_matcher, read_only=args.read_only,
              verifier_hint=args.verifier, db_path=args.db,
              gate_rollup_path=gate_rollup,
              sessions=Sessions(hours=args.session_hours))

    httpd = serve(app, args.host, args.port)
    url = f"http://{args.host or '127.0.0.1'}:{args.port}/"
    print(f"Nestor UI  →  {url}")
    print(f"  store    {args.db}")
    print(f"  ledger   {cascade._ledger_path()}")
    print(f"  engine   {args.engine}")
    if args.read_only:
        print("  mode     read-only — no decision can be recorded")
    ring = keyring.get_keyring()
    if ring is not None:
        print(f"  keyring  {ring.path or '(injected)'} — "
              f"{len(ring.names())} verifier(s); a decision needs a sign-in")
    else:
        print("  verifier typed, not proven — anyone reaching this port can seal as "
              "any name (set NESTOR_KEYRING for per-verifier keys)")
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
        store.close()
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
