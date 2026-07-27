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


def add_pair(source_text: str, target_text: str, source_lang: str, target_lang: str,
             status: str = "draft", verifier: str = "", weight: float = 1.0,
             origin: str = "", store: Optional[Storage] = None,
             matcher: Optional[Matcher] = None,
             override_rejection: bool = False) -> dict:
    """Insert or upgrade a pair. A sealed insert replaces a draft for the same source.

    ``source_lang`` / ``target_lang`` are generic DOMAIN tags: for translation
    they are languages; for entity resolution or numeric reconciliation they
    carry the entity-type / label bucket. The ``matcher`` (default
    :class:`StringMatcher`) decides how ``source_text`` is normalized.
    """
    store = get_store(store)
    matcher = get_matcher(matcher)
    store.memory_init()
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
    store.memory_insert(pair)
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


def _log_seal_event(entry: dict) -> None:
    """Append a seal-lifecycle entry to the hash-chained ledger.

    Best-effort by design. ``add_pair`` is called from bulk seeding paths
    (``seed_from_corpus``, host importers) where a ledger that is unwritable
    must not abort the import — the pair is already committed to the store by
    the time we get here, so raising would leave the caller with a completed
    write and an exception. The local ledger stays the source of truth for
    everything that *is* recorded; see :func:`_log_rejection`, which is called
    from paths where the write can still be refused.
    """
    try:
        _log_rejection(entry)
    except Exception:                     # noqa: BLE001 — never fail a seal on audit
        pass


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
    """
    store = get_store(store)
    loader = loader or _bilingual_loader
    count = 0
    for item in loader():
        if item.get("front") and item.get("back"):
            add_pair(item["front"], item["back"], item["lang_front"], item["lang_back"],
                     status="sealed", verifier="corpus", origin=item.get("lesson", ""),
                     store=store)
            add_pair(item["back"], item["front"], item["lang_back"], item["lang_front"],
                     status="sealed", verifier="corpus", origin=item.get("lesson", ""),
                     store=store)
            count += 2
    return count


def stats(store: Optional[Storage] = None) -> dict:
    store = get_store(store)
    store.memory_init()
    return store.memory_stats()
