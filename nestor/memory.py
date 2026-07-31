"""Nestor's ledger — the translation memory. Tier 1 of the cascade.

Verified pairs live in whatever store is injected. A pair is "sealed"
(human-verified or curated-corpus) or "draft" (machine, awaiting seal).
Tier-1 serving uses sealed pairs only; drafts may be offered as context to
the engine but never served as verified.

Storage inversion
-----------------
This module owns the *algorithm* — source-text normalization and difflib
fuzzy scoring — and delegates every persistence operation to an injected
``Storage`` (see :mod:`nestor.storage`). Each public function takes an
optional ``store=`` argument; when omitted the process-wide store from
``set_store`` is used.

The corpus-seeding path used to import ``_load_bilingual_pairs`` from the
host. That is now an injected, optional callable — set one with
:func:`set_bilingual_loader`, or pass ``loader=`` to :func:`seed_from_corpus`.
The default loader returns ``[]`` (nothing to seed).
"""
from __future__ import annotations

import hashlib
import uuid
import warnings
from datetime import datetime, timezone
from typing import Callable, Optional

from . import signing
from .matcher import Matcher, StringMatcher
from .storage import Storage, get_store, supports_rejection

EXACT = 1.0
SEAL_THRESHOLD = 0.92   # fuzzy similarity at/above which a sealed pair serves as tier 1
CONTEXT_THRESHOLD = 0.55  # pairs above this feed the engine as context


# --------------------------------------------------------------------------
# Injected matcher (the domain seam)
# --------------------------------------------------------------------------
#
# The memory used to hardcode text normalization (``_norm``) and difflib
# scoring. Both are now supplied by an injected :class:`~nestor.matcher.Matcher`
# so the same seal/serve/ledger mechanic works for translations, entities and
# numbers. The default is :class:`StringMatcher`, which reproduces the original
# translation behavior exactly — so every public signature stays
# backward-compatible.

_matcher: Matcher = StringMatcher()


def set_matcher(m: Matcher) -> None:
    """Install the process-wide matcher used when no explicit ``matcher=`` is passed."""
    global _matcher
    _matcher = m


def get_matcher(m: Optional[Matcher] = None) -> Matcher:
    """Resolve the matcher to use — an explicit argument wins, else the global."""
    return m if m is not None else _matcher


# --------------------------------------------------------------------------
# Injected bilingual-pair loader (was a host import of learn._load_bilingual_pairs)
# --------------------------------------------------------------------------

def _default_bilingual_loader() -> list[dict]:
    return []


_bilingual_loader: Callable[[], list[dict]] = _default_bilingual_loader


def set_bilingual_loader(fn: Callable[[], list[dict]]) -> None:
    """Install the callable that yields bilingual seed pairs.

    ``fn()`` must return a list of dicts, each with the keys
    ``front``, ``back``, ``lang_front``, ``lang_back`` and ``lesson`` —
    the shape produced by the host's ``learn._load_bilingual_pairs``.
    """
    global _bilingual_loader
    _bilingual_loader = fn


# --------------------------------------------------------------------------
# Translation-memory operations
# --------------------------------------------------------------------------

def init_tm(store: Optional[Storage] = None) -> None:
    store = get_store(store)
    store.memory_init()


def _norm(text: str) -> str:
    """Backward-compatible alias for the default StringMatcher normalization.

    The normalization algorithm now lives in :class:`nestor.matcher.StringMatcher`;
    this thin wrapper is kept so any host that imported ``memory._norm`` keeps
    working.
    """
    return StringMatcher().normalize(text)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RejectedPairError(RuntimeError):
    """Refusing to re-seal a pair a human previously rejected.

    Raised by :func:`add_pair` rather than silently overwriting the rejection.
    A host driving a review queue should catch this and surface it to the
    reviewer as a conflict — one human is asserting the opposite of another's
    recorded decision, which is exactly the moment that should not pass
    unnoticed. Pass ``override_rejection=True`` (or restore the pair first via
    ``Curator.restore``) to proceed deliberately.
    """


class ConflictingSealError(RuntimeError):
    """Refusing to overwrite a sealed pair with a different verifier's answer.

    Same structural moment as :class:`RejectedPairError`, one step earlier:
    before a rejection is ever recorded, a second seal for the same source
    with a *different* target is itself "one human asserting the opposite of
    another's recorded decision." Without this guard ``add_pair`` used to
    call ``store.memory_seal`` right over the old row — same pair id, old
    target simply gone, nothing raised.

    The signal used to tell a *correction* (proceed) from a *conflict*
    (raise) is verifier identity: the same non-empty verifier re-sealing its
    own prior answer is assumed to be a self-correction. Everything else —
    including an empty verifier on either side — is treated as unknown and
    therefore conflicting, because an empty ``verifier`` proves nothing about
    who is asserting it; see :func:`add_pair` for the full reasoning.

    Pass ``override_conflict=True`` to proceed deliberately (mirrors
    ``override_rejection``).
    """


def _same_verifier(a: str, b: str) -> bool:
    """Whether two verifier strings may be assumed to name the same actor.

    Deliberately conservative: two *empty* verifiers do NOT count as the same
    actor. ``verifier`` defaults to ``""`` and is by far the most common value
    an unauthenticated or scripted caller supplies, so treating "" == "" as
    "the same person correcting themselves" would silently wave through every
    anonymous re-seal — exactly the conflict this guard exists to catch. An
    empty verifier asserts no identity, so it can prove neither sameness nor
    difference; the safe read is "unknown," which resolves to conflicting.
    """
    return bool(a) and bool(b) and a == b


def add_pair(source_text: str, target_text: str, source_lang: str, target_lang: str,
             status: str = "draft", verifier: str = "", weight: float = 1.0,
             origin: str = "", store: Optional[Storage] = None,
             matcher: Optional[Matcher] = None,
             override_rejection: bool = False,
             override_conflict: bool = False,
             audit: bool = True, _racing: bool = False) -> dict:
    """Insert or upgrade a pair. A sealed insert replaces a draft for the same source.

    ``source_lang`` / ``target_lang`` are generic DOMAIN tags: for translation
    they are languages; for entity resolution or numeric reconciliation they
    carry the entity-type / label bucket. The ``matcher`` (default
    :class:`StringMatcher`) decides how ``source_text`` is normalized.

    Re-sealing an existing SEALED row with a different ``target_text`` raises
    :class:`ConflictingSealError` unless ``verifier`` matches the existing
    row's verifier (a same-actor correction) or ``override_conflict=True`` is
    passed explicitly. See :class:`ConflictingSealError` for the full
    rationale, in particular why an empty verifier does not count as a match.

    **A seal made here is ledgered here.** This is the one function that turns a
    pair into a sealed one, and for a long time it recorded nothing: the seal
    entries in the chain came from the *callers* that happened to write them
    (``graduate_segment``, the recipes, the UI), so a host calling ``add_pair``
    directly — the shortest path to a sealed row, and the one every importer
    takes — produced a verified answer with no trail, while the README promised
    every seal was appended. The entry is written from here now, so the promise
    holds regardless of the entry point. ``audit=False`` is for bulk paths that
    record their own aggregate entry instead; :func:`seed_from_corpus` is the
    only caller that uses it, so that a 10k-pair import writes one line rather
    than ten thousand.
    """
    store = get_store(store)
    matcher = get_matcher(matcher)
    store.memory_init()
    # A seal has to be auditable to be a seal. Refuse before touching the store,
    # so a broken or unwritable chain cannot leave a verified row with no trail.
    if status == "sealed" and audit:
        _ledger_preflight()
    norm = matcher.normalize(source_text)
    # Bind the seal to a key the store does not hold (Nestor#2). Signing is
    # opt-in: with no NESTOR_SEAL_KEY, sign_seal returns "" and nothing changes.
    seal_sig = signing.sign_seal(norm, target_text, verifier) if status == "sealed" else ""
    existing = store.memory_find(norm, source_lang, target_lang)
    if existing:
        # A rejected pair must not be resurrected by a routine re-seal. Without
        # this, a curator rejects a bad mapping and the next graduate_segment
        # over the same source text silently seals it again — the exact leak
        # rejection exists to close.
        if (existing["status"] == "rejected" and status == "sealed"
                and not override_rejection):
            raise RejectedPairError(
                f"pair {existing['id']} was rejected by "
                f"{existing.get('verifier') or 'a reviewer'!r} and will not be "
                f"re-sealed implicitly. Restore it first (Curator.restore) or "
                f"pass override_rejection=True."
            )
        # A different verifier asserting a different target for an already-
        # SEALED source is a conflict, not a routine upgrade — this is the
        # overwrite the RejectedPairError check above does not catch, because
        # there was never a rejection recorded, just a second seal silently
        # clobbering the first. Runs BEFORE the overwrite below, same as the
        # rejection guard.
        if (status == "sealed" and existing["status"] == "sealed"
                and existing["target_text"] != target_text
                and not override_conflict
                and not _same_verifier(existing.get("verifier", ""), verifier)):
            raise ConflictingSealError(
                f"pair {existing['id']} was sealed by "
                f"{existing.get('verifier') or 'an unknown verifier'!r} as "
                f"{existing['target_text']!r}; {verifier or 'an unknown verifier'!r} "
                f"is now asserting {target_text!r} for the same source. This "
                f"will not be sealed implicitly. Reject/restore the pair first, "
                f"reseal as the SAME verifier if this is a self-correction, or "
                f"pass override_conflict=True."
            )
        if status == "sealed" and (
            existing["status"] != "sealed" or existing["target_text"] != target_text
        ):
            replaced_target = existing["target_text"]
            replaced_status = existing["status"]
            replaced_verifier = existing.get("verifier", "")
            store.memory_seal(existing["id"], target_text, verifier, weight, seal_sig)
            existing = store.memory_find(norm, source_lang, target_lang)
            # Overwriting a seal destroys a previous human decision, and the
            # memory keeps only one row per normalized source — so without this
            # entry the earlier verification would leave no trace anywhere. A
            # ledger that records every grant of trust and no replacement of one
            # cannot answer "what did this used to say, and who said it".
            #
            # Reaching here with a DIFFERENT verifier means the guard above was
            # explicitly overridden, so `same_verifier: False` in the trail marks
            # a deliberate overrule rather than an accident. Curator.replaced_seals
            # surfaces exactly those.
            if audit:
                _log_seal_event({
                    "kind": "seal", "pair_id": existing["id"], "verifier": verifier,
                    "source_lang": source_lang, "target_lang": target_lang,
                    "source_sha": _sha(norm), "origin": origin,
                    "upgraded_from": replaced_status,
                })
            if replaced_status == "sealed":
                _log_seal_event({
                    "kind": "seal_replaced", "pair_id": existing["id"],
                    "source_lang": source_lang, "target_lang": target_lang,
                    "replaced_verifier": replaced_verifier, "verifier": verifier,
                    "replaced_target_sha": _sha(replaced_target),
                    "target_sha": _sha(target_text),
                    "source_sha": _sha(norm),
                    "same_verifier": replaced_verifier == verifier,
                })
        return existing
    pair = dict(id=str(uuid.uuid4()), source_text=source_text, source_norm=norm,
                source_lang=source_lang, target_text=target_text, target_lang=target_lang,
                status=status, verifier=verifier, weight=weight, origin=origin,
                created_at=_now(), seal_sig=seal_sig)
    try:
        store.memory_insert(pair)
    except Exception:
        # Somebody inserted the same normalized source between our memory_find
        # above and this line. That window is real — nestor.ui seals from a
        # thread pool — and it used to end with two sealed rows for one source,
        # no ConflictingSealError, and no answer to which one serves.
        #
        # A store that enforces uniqueness on (source_norm, source_lang,
        # target_lang) turns that race into this failure, and the failure into
        # the correct outcome: re-run, take the existing-row path above, and let
        # the ordinary guards decide — which raises ConflictingSealError when the
        # winner is a different verifier with a different answer. `_racing`
        # bounds it to one retry, so a genuine insert error still surfaces.
        if _racing or not store.memory_find(norm, source_lang, target_lang):
            raise
        return add_pair(source_text, target_text, source_lang, target_lang,
                        status=status, verifier=verifier, weight=weight,
                        origin=origin, store=store, matcher=matcher,
                        override_rejection=override_rejection,
                        override_conflict=override_conflict, audit=audit,
                        _racing=True)
    if status == "sealed" and audit:
        _log_seal_event({
            "kind": "seal", "pair_id": pair["id"], "verifier": verifier,
            "source_lang": source_lang, "target_lang": target_lang,
            "source_sha": _sha(norm), "origin": origin, "upgraded_from": "",
        })
    return pair


def rejected_ids(query_norm: str, source_lang: str, target_lang: str,
                 store: Storage) -> tuple[set, set]:
    """``(rejected pair ids, rejected target texts)`` for one query key.

    Returns empty sets when the store has no rejection capability, so a host
    predating it keeps working unchanged.

    Every recorded rejection is honored, **including one whose signature does
    not verify**. That is deliberate and the opposite of how seals are treated,
    because the two fail in opposite directions: honoring a forged seal serves
    unverified content as verified, while honoring a forged rejection only
    withholds an answer. Withholding degrades to tier 2 and a human look —
    Nestor's defined safe state. It also grants an attacker nothing new: writing
    a forged rejection requires store write access, and anyone with that could
    simply delete the sealed row instead. Signatures are still recorded and
    checkable via :func:`rejection_signature_report` for audit.
    """
    if not supports_rejection(store):
        return set(), set()
    rows = store.memory_rejections(query_norm, source_lang, target_lang)
    return ({r["pair_id"] for r in rows if r.get("pair_id")},
            {r["target_text"] for r in rows if r.get("target_text")})


def rejection_signature_report(query_norm: str, source_lang: str,
                               target_lang: str,
                               store: Optional[Storage] = None) -> list[dict]:
    """Per-rejection signature validity, for audit and curator surfaces.

    Serving never consults this — see :func:`rejected_ids` — but an unverifiable
    rejection is still worth surfacing to a human, because it means somebody
    suppressed an answer without the seal key.
    """
    store = get_store(store)
    if not supports_rejection(store):
        return []
    out = []
    for r in store.memory_rejections(query_norm, source_lang, target_lang):
        out.append({
            "pair_id": r.get("pair_id", ""),
            "target_text": r.get("target_text", ""),
            "verifier": r.get("verifier", ""),
            "reason": r.get("reason", ""),
            "signature_valid": signing.rejection_is_valid(
                query_norm, r.get("pair_id", ""), r.get("target_text", ""),
                r.get("verifier", ""), r.get("reject_sig", "")),
        })
    return out


def lookup(source_text: str, source_lang: str, target_lang: str,
           limit: int = 5, store: Optional[Storage] = None,
           matcher: Optional[Matcher] = None,
           context_threshold: Optional[float] = None) -> list[dict]:
    """Ranked matches: [{pair, similarity}], best first. Sealed and draft both returned.

    Scoring is delegated to the injected ``matcher`` (default StringMatcher, so
    translation behavior is unchanged). ``context_threshold`` overrides the
    module-level :data:`CONTEXT_THRESHOLD` floor below which candidates are
    dropped — pass ``0.0`` to keep every candidate (used by the numeric
    reconciler so a far-off figure is still returned for variation reporting).
    """
    store = get_store(store)
    matcher = get_matcher(matcher)
    ctx = CONTEXT_THRESHOLD if context_threshold is None else context_threshold
    store.memory_init()
    norm = matcher.normalize(source_text)
    rows = store.memory_candidates(source_lang, target_lang)
    # Rejection is enforced HERE, in the one function every serve path goes
    # through — best_sealed, the engine's TM context, the entity resolver and
    # the reconciler all call lookup(). Filtering in best_sealed alone would
    # leave a rejected pair still reaching the engine's system prompt as
    # authoritative reference material.
    bad_pairs, bad_targets = rejected_ids(norm, source_lang, target_lang, store)
    scored = []
    for row in rows:
        if row["status"] == "rejected":
            continue
        if row["id"] in bad_pairs or row["target_text"] in bad_targets:
            continue
        sim = matcher.similarity(norm, row["source_norm"])
        if sim >= ctx:
            scored.append({"pair": row, "similarity": round(sim, 3)})
    scored.sort(key=lambda m: (-m["similarity"], m["pair"]["status"] != "sealed"))
    return scored[:limit]


def is_verified_seal(pair: dict) -> bool:
    """The single definition of "a sealed row we may serve": status is
    ``sealed`` AND its signature verifies. Every serve path must go through
    this — ``best_sealed``, the reconciler, and the engine's TM context — so
    the Nestor#2 signature check can't be bypassed by a bare ``status ==
    'sealed'`` filter one file over (that regression is the reason this exists).
    Signing-disabled ⇒ ``seal_is_valid`` is True ⇒ legacy behavior unchanged.
    """
    return (pair.get("status") == "sealed" and signing.seal_is_valid(
        pair["source_norm"], pair["target_text"], pair["verifier"],
        pair.get("seal_sig", "")))


def verified_sealed(matches: list[dict]) -> list[dict]:
    """Filter ``lookup()`` results to sealed rows whose signature verifies."""
    return [m for m in matches if is_verified_seal(m["pair"])]


def without_forged_seals(matches: list[dict]) -> list[dict]:
    """Drop rows that *claim* ``sealed`` but whose signature does not verify.

    The weaker sibling of :func:`verified_sealed`, for paths entitled to draw on
    drafts. ``verified_sealed`` keeps *only* verified sealed rows, which is right
    for the engine's TM context — that context is presented to the model as
    authoritative — and wrong for the offline draft path, which the README
    explicitly permits to draw on drafts. Using it there would close a forgery
    hole by deleting a documented feature.

    What a forged row actually buys an attacker is worth stating precisely: not
    a serve. It lands as ``state='draft'`` in the review queue and a human sees
    it before anything is sealed. But **reviewers anchor hardest on the text
    they are shown first**, so a forged row reaching the draft influences the
    outcome more than the system prompt it was deliberately kept out of. A row
    asserting a status it cannot prove should not be the first thing a person
    reads.

    A genuine draft is untouched. Only the claim to be sealed is checked.
    """
    return [m for m in matches
            if m["pair"].get("status") != "sealed" or is_verified_seal(m["pair"])]


def best_sealed(source_text: str, source_lang: str, target_lang: str,
                store: Optional[Storage] = None,
                matcher: Optional[Matcher] = None,
                seal_threshold: Optional[float] = None,
                context_threshold: Optional[float] = None) -> Optional[dict]:
    """Tier-1 check: the best sealed match at/above the seal threshold, else None.

    ``seal_threshold`` overrides the module-level :data:`SEAL_THRESHOLD`.
    """
    seal = SEAL_THRESHOLD if seal_threshold is None else seal_threshold
    for m in lookup(source_text, source_lang, target_lang, store=store,
                    matcher=matcher, context_threshold=context_threshold):
        if m["similarity"] >= seal and is_verified_seal(m["pair"]):
            return m
    return None


def _sha(text: str) -> str:
    """Short digest of a value for the ledger.

    Targets and source text can be long and can carry content a host would
    rather not mirror into shared provenance (``nestor.frank`` forwards ledger
    entries verbatim). A digest still proves *which* text was replaced to anyone
    holding the original, without putting it in the trail.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _ledger_preflight() -> None:
    """Refuse now if the trail will not take the entry we are about to earn.

    Imported lazily for the same reason as :func:`_log_rejection`.
    """
    from .cascade import ledger_preflight
    ledger_preflight()


def _log_seal_event(entry: dict) -> None:
    """Append a seal-lifecycle entry to the hash-chained ledger.

    Called *after* the store write, so it cannot raise: the pair is already
    committed by the time we get here, and raising would hand the caller a
    completed write plus an exception — a sealed row and a traceback, which is
    worse than either.

    That is only defensible because the write is preceded by
    :func:`_ledger_preflight`, which applies the same refusals *before* anything
    is written. Without it this was a silent hole with the priorities exactly
    inverted: withdrawing trust (``reject_pair``, ``unseal``) failed closed on a
    broken chain while granting it sailed through unrecorded, so the one
    decision the trail exists to capture was the one it could miss.

    What is left is a genuine edge — the ledger becoming unwritable in the
    window between the preflight and here — and it warns rather than passing
    silently, because a sealed row with no entry is exactly the thing a curator
    needs to hear about.
    """
    try:
        _log_rejection(entry)
    except Exception as exc:              # noqa: BLE001 — never fail a seal on audit
        warnings.warn(
            f"a seal was written but its ledger entry was not: {type(exc).__name__}: "
            f"{exc}. The store and the trail now disagree; run "
            f"nestor.ledger.verify() and reconcile before trusting this row.",
            RuntimeWarning, stacklevel=2)


def _log_rejection(entry: dict) -> None:
    """Append a rejection to the hash-chained ledger.

    Imported lazily: ``cascade`` imports ``memory`` at module load, so a
    top-level import here would be circular. By the time any rejection can be
    recorded, ``cascade`` is loaded.

    A rejection is a verification decision exactly as a seal is — "a human
    looked and said no" belongs in the audit trail beside "a human looked and
    said yes", or the trail only ever records agreement.
    """
    from .cascade import _ledger_append
    _ledger_append(entry)


def _require_rejection(store: Storage) -> None:
    if not supports_rejection(store):
        raise RuntimeError(
            f"{type(store).__name__} does not implement Nestor's rejection "
            f"capability. Implement memory_reject_pair, memory_add_rejection "
            f"and memory_rejections (see nestor.storage.Storage) — refusing to "
            f"accept a rejection that would be silently discarded."
        )


def reject_match(source_text: str, source_lang: str, target_lang: str,
                 pair_id: str = "", target_text: str = "", verifier: str = "",
                 reason: str = "", store: Optional[Storage] = None,
                 matcher: Optional[Matcher] = None) -> dict:
    """Record that a candidate is the WRONG answer for ``source_text``.

    Identify what is being rejected by ``pair_id`` (a memory pair that matched
    this query — the false-seal case) or by ``target_text`` (a raw engine draft
    with no pair yet), or both. The pair itself stays valid for its own source
    text; use :func:`reject_pair` when the mapping is wrong in its own right.

    Raises ``RuntimeError`` if the store cannot persist rejections, rather than
    accepting a "no" it would drop on the floor.
    """
    store = get_store(store)
    _require_rejection(store)
    _ledger_preflight()          # refuse before recording, not after
    matcher = get_matcher(matcher)
    store.memory_init()
    if not pair_id and not target_text:
        raise ValueError("reject_match needs pair_id or target_text — "
                         "otherwise there is nothing to suppress")
    norm = matcher.normalize(source_text)
    rejection = dict(
        id=str(uuid.uuid4()), query_norm=norm, source_lang=source_lang,
        target_lang=target_lang, pair_id=pair_id, target_text=target_text,
        verifier=verifier, reason=reason, created_at=_now(),
        reject_sig=signing.sign_rejection(norm, pair_id, target_text, verifier),
    )
    store.memory_add_rejection(rejection)
    _log_rejection({"kind": "reject_match", "query_norm": norm,
                    "source_lang": source_lang, "target_lang": target_lang,
                    "pair_id": pair_id, "verifier": verifier, "reason": reason,
                    "rejection_id": rejection["id"]})
    return rejection


def reject_pair(pair_id: str, verifier: str = "", reason: str = "",
                store: Optional[Storage] = None) -> None:
    """Mark a pair's mapping itself wrong — never served or offered again.

    Use for a bad seal or a bad draft. For "right pair, wrong query" — which is
    what a false seal actually is — use :func:`reject_match` instead, so a
    correct verification is not destroyed.
    """
    store = get_store(store)
    _require_rejection(store)
    _ledger_preflight()          # a refusal must not follow a completed write
    store.memory_init()
    store.memory_reject_pair(pair_id, verifier, reason)
    _log_rejection({"kind": "reject_pair", "pair_id": pair_id,
                    "verifier": verifier, "reason": reason})


def seed_from_corpus(loader: Optional[Callable[[], list[dict]]] = None,
                     store: Optional[Storage] = None) -> int:
    """Seed sealed pairs from bilingual lessons supplied by an injected loader.

    ``loader`` (or the one set via :func:`set_bilingual_loader`) returns the
    curated bilingual pairs; both directions of each pair are sealed into the
    memory. Returns the number of pairs written.

    **A human's decision beats the corpus, and cannot stop the load.** Seeding
    uses the fixed verifier ``"corpus"``, which never matches a person, so a
    phrase a human already sealed differently raises
    :class:`ConflictingSealError` and one they *rejected* raises
    :class:`RejectedPairError`. Either escaping would abort a bulk import
    partway and leave a half-loaded memory, so both are skipped and the rest of
    the corpus still lands — a curated file must not overrule a person, and must
    not be able to halt the load either.

    Skips are never silent: each is written to the ledger as ``seed_conflict``
    or ``seed_rejected`` — kept distinct, because "already sealed differently"
    and "previously rejected" are different facts about the corpus — and the
    call warns once with both totals. A seeding run that quietly dropped rows
    would be the same "absence reported as success" this codebase refuses
    everywhere else.
    """
    store = get_store(store)
    loader = loader or _bilingual_loader
    count = 0
    skipped = 0
    rejected = 0

    def _seal(src: str, tgt: str, sl: str, tl: str, origin: str) -> int:
        nonlocal skipped, rejected
        try:
            add_pair(src, tgt, sl, tl, status="sealed", verifier="corpus",
                     origin=origin, store=store, audit=False)
            return 1
        except (ConflictingSealError, RejectedPairError) as exc:
            # Both are the same fact — a person already decided about this
            # phrase and a curated file does not get to overrule them — so both
            # get the same treatment the docstring's reasoning demands: skip,
            # log, count, keep loading. `RejectedPairError` was raised a few
            # lines earlier in `add_pair` and escaped, which aborted the import
            # at the first previously-rejected phrase and left the rest of the
            # file silently unloaded. That is precisely the failure the conflict
            # catch exists to prevent.
            #
            # The two `kind`s stay distinct in the ledger. "already sealed
            # differently by a human" and "previously rejected by a human" are
            # different facts about the corpus, and collapsing them into one
            # entry would erase the difference the rejection machinery exists to
            # preserve.
            is_conflict = isinstance(exc, ConflictingSealError)
            if is_conflict:
                skipped += 1
            else:
                rejected += 1
            _log_seal_event({
                "kind": "seed_conflict" if is_conflict else "seed_rejected",
                "source_lang": sl, "target_lang": tl,
                "source_sha": _sha(get_matcher().normalize(src)),
                "target_sha": _sha(tgt), "origin": origin,
                "verifier": "corpus",
            })
            return 0

    for item in loader():
        if item.get("front") and item.get("back"):
            origin = item.get("lesson", "")
            count += _seal(item["front"], item["back"],
                           item["lang_front"], item["lang_back"], origin)
            count += _seal(item["back"], item["front"],
                           item["lang_back"], item["lang_front"], origin)
    # One entry for the run, rather than one per pair: a curated file is a
    # single act by a single (non-human) verifier, and `audit=False` above keeps
    # a 10k-pair import from burying every human decision in the chain.
    if count:
        _log_seal_event({"kind": "corpus_seed", "verifier": "corpus",
                         "sealed": count, "skipped_conflict": skipped,
                         "skipped_rejected": rejected})
    if skipped or rejected:
        parts = []
        if skipped:
            parts.append(f"{skipped} already sealed differently by a human "
                         f"(see 'seed_conflict' ledger entries)")
        if rejected:
            parts.append(f"{rejected} previously rejected by a human "
                         f"(see 'seed_rejected' ledger entries)")
        warnings.warn(
            f"seed_from_corpus skipped {skipped + rejected} pair(s): "
            f"{'; '.join(parts)}. {count} pair(s) written.",
            RuntimeWarning, stacklevel=2)
    return count


def stats(store: Optional[Storage] = None) -> dict:
    store = get_store(store)
    store.memory_init()
    return store.memory_stats()
