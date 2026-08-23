"""Nestor's ledger — the verified-match memory. Tier 1 of the cascade.

Verified pairs live in whatever store is injected. A pair is "sealed"
(human-verified or curated-corpus), "draft" (machine, awaiting seal) or
"rejected" (a human said no). Tier-1 serving uses sealed pairs only; drafts may
be offered as context to the engine but never served as verified.

Three things this module owns that its name does not suggest, all load-bearing:

* **"Sealed" is not a column, it is a predicate.** :func:`is_verified_seal` —
  status *and* a signature that verifies — is the single definition every serve
  path goes through, so a row that merely says ``sealed`` cannot be served by
  filtering on the column one file over. :func:`without_forged_seals` is its
  weaker sibling for paths entitled to draw on drafts.
* **A reviewer's "no" lives here too.** :func:`reject_pair` retires a mapping;
  :func:`reject_match` suppresses one answer for one query and leaves the seal
  standing, which is what a false seal actually needs. Enforcement is inside
  :func:`lookup`, the one function every serve path calls.
* **Contradiction is refused, not merged.** :class:`ConflictingSealError` and
  :class:`RejectedPairError` stop one human silently overwriting another's
  recorded decision; both take an explicit override, and both are ledgered.

The name is historical — this predates the recipes, and the memory holds
translations, entity aliases and numeric baselines alike (see
:mod:`nestor.matcher`).

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
from typing import Callable, Optional, cast

from . import signing
from .embedding_store import EmbeddingCapableStorage, supports_embedding_store
from .errors import NestorError
from .matcher import Matcher, StringMatcher, match_similarity, uses_raw_score
from .storage import (AtomicSupersedeStorage, LineageStorage, Storage,
                      VerifierPolicyStorage, get_store, require_capability,
                      supports_rejection, supports_verifier_policy)

EXACT = 1.0
SEAL_THRESHOLD = 0.92   # fuzzy similarity at/above which a sealed pair serves as tier 1
CONTEXT_THRESHOLD = 0.55  # pairs above this feed the engine as context

_warned_score_threshold = False


def _warn_score_matcher_default_threshold(matcher: Matcher,
                                        seal_threshold: Optional[float]) -> None:
    """Once per process: default SEAL_THRESHOLD is tuned for StringMatcher."""
    global _warned_score_threshold
    if _warned_score_threshold or seal_threshold is not None:
        return
    if not uses_raw_score(matcher):
        return
    _warned_score_threshold = True
    warnings.warn(
        f"SEAL_THRESHOLD={SEAL_THRESHOLD} was measured for StringMatcher "
        f"(character difflib), not for {type(matcher).__name__}.score() — "
        f"unrelated text often scores 0.7–0.8 on embedding matchers. Measure "
        f"with ``nestor calibrate --matcher …`` on your corpus before trusting "
        f"serves at the shipped default.",
        RuntimeWarning, stacklevel=3)


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


def _raw_score_sims(matcher: Matcher, query_text: str,
                    rows: list[dict], store: Optional[Storage] = None) -> tuple[bool, dict[str, float]]:
    """Map row id → raw similarity, batching ``scores_against`` when offered.

    Rows with no ``source_text`` are omitted from the map; they must be scored
    through :func:`~nestor.matcher.match_similarity` on stored norms so
    :func:`lookup` and :func:`best_sealed` stay aligned.
    """
    raw_score = uses_raw_score(matcher)
    sims: dict[str, float] = {}
    if not raw_score:
        return raw_score, sims
    batch = getattr(matcher, "scores_against", None)
    if not callable(batch):
        return raw_score, sims
    batched = [r for r in rows if (r.get("source_text") or "").strip()]
    if not batched:
        return raw_score, sims
    batch_rows = getattr(matcher, "scores_against_for_rows", None)
    if callable(batch_rows) and store is not None and supports_embedding_store(store):
        scores = batch_rows(query_text, batched, store)
    else:
        scores = batch(query_text, [r["source_text"] for r in batched])
    sims = dict(zip((r["id"] for r in batched), scores))
    return raw_score, sims


def _drop_stored_embeddings(store: Storage, pair_id: str) -> None:
    if supports_embedding_store(store):
        # Checked, not assumed: the predicate above confirmed the method
        # exists at runtime; embedding storage is intentionally outside the
        # core Storage Protocol (embedding_store.py's own docstring), so cast
        # rather than widen every store's declared type for one optional op.
        cast(EmbeddingCapableStorage, store).embedding_drop(pair_id)


def _similarity_for_row(matcher: Matcher, query_text: str, query_norm: str,
                        row: dict, *, raw_score: bool,
                        sims: dict[str, float]) -> float:
    if row["id"] in sims:
        return sims[row["id"]]
    return match_similarity(
        matcher, query_text, query_norm,
        row.get("source_text", ""), row["source_norm"],
        _raw_score=raw_score)


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


class RejectedPairError(NestorError):
    """Refusing to re-seal a pair a human previously rejected.

    Raised by :func:`add_pair` rather than silently overwriting the rejection.
    A host driving a review queue should catch this and surface it to the
    reviewer as a conflict — one human is asserting the opposite of another's
    recorded decision, which is exactly the moment that should not pass
    unnoticed. Pass ``override_rejection=True`` (or restore the pair first via
    ``Curator.restore``) to proceed deliberately.
    """


class ConflictingDraftError(NestorError):
    """Refusing to answer a proposal with somebody else's proposal.

    ``add_pair`` writes only when sealing, so a *draft* offered for a source
    that already holds a different draft fell through every branch and returned
    the stored row — no write, no ledger line, no warning, and **the return
    value was the previous proposal**. A caller doing ``p = add_pair(...)`` and
    reading ``p["target_text"]`` was handed an answer it had not proposed, with
    nothing to distinguish that from success. Found by feeding this repo's own
    revision history back through it (IDEAS §6.18): four successive answers to
    one question left one row, and it was the *first*.

    Which behaviour is right — keep the old draft, take the new one, or route
    to a draft-aware supersede — is a question about who may revise what, and
    it is not settled here. What is settled is that all three are better than
    telling the caller it succeeded. So this refuses, on the same terms
    :class:`ConflictingSealError` refuses one rung up: a second answer for the
    same source is a disagreement to surface, not to resolve silently.

    Two hazards make the silent path indefensible rather than merely untidy.
    Overwriting would let a machine swap the row under a reviewer who is
    mid-review, so they seal something they never read; no-op'ing lets a caller
    believe a proposal landed when it did not. Refusing does neither, and it
    costs the caller one explicit decision.

    **There is deliberately no override flag.** A first attempt offered
    ``override_draft=True``, and because every branch below it is a seal the
    flag fell through and returned the stored row — the same silent lie,
    rebuilt inside its own fix. The replacement is a named operation rather
    than a flag: :func:`revise_draft`, which keeps the old proposal as history
    with the reason it was abandoned. A flag would have discarded it.

    An identical target is not a conflict — re-proposing the same answer is
    idempotent, which is what a retrying host does.
    """


class ConflictingSealError(NestorError):
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


class VerifierNotAllowedError(NestorError):
    """Refusing to seal because ``verifier`` is not on this domain's policy
    (issue #167 piece 3).

    Today the sign-off field on a seal accepts any name a caller types, and
    no domain can say whose name is even eligible to be on it. This is the
    enforcement half of a per-domain verifier allowlist recorded in the store
    (``SqliteStore.memory_policy_add`` / ``nestor policy add``): a domain
    that has recorded at least one policy row refuses a seal from any
    verifier not on that list.

    Opt-in and backward compatible, same posture as :mod:`nestor.signing`'s
    default: a domain with NO policy rows is unrestricted — this is checked
    BEFORE any store read or write, mirroring
    :class:`InvalidSealSignatureError`, so a refused seal leaves no row
    behind, sealed or otherwise. Raised from the API layer (this module),
    never screened in a page — a UI that skips this check still hits it the
    moment it calls ``add_pair``/``supersede_pair``.
    """


class InvalidSealSignatureError(NestorError):
    """Refusing to record a seal under a CLIENT-PROVIDED signature that does
    not verify (Nestor#17, the client-signing seam).

    ``add_pair(..., seal_sig=...)`` is the path where the caller — not this
    process — produced the signature, typically because the verifier's
    keyring entry here holds only an ed25519 PUBLIC key (see
    :meth:`nestor.keyring.Keyring.signing_entry`) and this instance could not
    have signed on its behalf even if it wanted to. The server's only job on
    that path is to check the signature against ``signing._message(norm,
    target_text, verifier)`` with :func:`nestor.signing.seal_is_valid` — the
    same check a peer instance makes on import.

    Raised BEFORE ``store.memory_find``/``memory_insert``/``memory_seal`` ever
    run, so a forged or mismatched ``seal_sig`` leaves no row, sealed or
    otherwise — the load-bearing property this whole seam exists for. An
    unverified signature must never reach the store as ``status="sealed"``,
    which is the Nestor#2 forgery one call deeper: instead of the store
    merely *saying* ``sealed``, this would be the store believing a signature
    that never matched the fields it is bound to.
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


# --------------------------------------------------------------------------
# add_pair helpers — one per conflict-resolution step, in the order add_pair
# calls them. Split out so the orchestrator reads as a sequence of named
# decisions instead of one long function; see add_pair's docstring for the
# rationale behind each check.
# --------------------------------------------------------------------------

def _check_verifier_policy(store: Storage, source_lang: str, target_lang: str,
                           verifier: str) -> None:
    """Refuse a seal whose verifier is off this domain's allowlist.

    Called at seal time, before any store read or write — see
    :class:`VerifierNotAllowedError`. A store without the capability, or a
    domain with no policy rows recorded, is unrestricted: this is an opt-in
    gate, not a new requirement every deployment must configure before it can
    seal anything.
    """
    if not supports_verifier_policy(store):
        return
    store = cast(VerifierPolicyStorage, store)
    rows = store.memory_policy_list(source_lang, target_lang)
    if not rows:
        return
    allowed = sorted({r["verifier"] for r in rows})
    if verifier not in allowed:
        raise VerifierNotAllowedError(
            f"{verifier or 'an unknown verifier'!r} is not on the verifier "
            f"policy for domain {source_lang}->{target_lang}: allowed "
            f"verifier(s) are {allowed}. Nothing was sealed. Add "
            f"{verifier or '<name>'!r} to the policy first (nestor policy add "
            f"--from {source_lang} --to {target_lang} --verifier ..., or "
            f"store.memory_policy_add) or seal as one of the names above."
        )


def _resolve_seal_sig(status: str, norm: str, target_text: str, verifier: str,
                      seal_sig: str) -> str:
    """Bind the seal to a key the store does not hold (Nestor#2).

    Not sealing: no signature needed, return "". Sealing with a
    caller-supplied ``seal_sig`` (the client-signing seam, Nestor#17): verify
    it against :func:`nestor.signing.seal_is_valid` and raise
    :class:`InvalidSealSignatureError` if it does not verify — BEFORE any
    store read or write, so a forged or mismatched signature leaves no row at
    all. Otherwise (the default path): sign it ourselves via
    :func:`nestor.signing.sign_seal`.
    """
    if status != "sealed":
        return ""
    if seal_sig:
        if not signing.seal_is_valid(norm, target_text, verifier, seal_sig):
            raise InvalidSealSignatureError(
                f"the seal_sig provided for {verifier or 'an unknown verifier'!r} "
                f"does not verify against (source_norm={norm!r}, "
                f"target_text={target_text!r}, verifier={verifier!r}) — "
                f"refusing to record it as sealed. Nothing was written.")
        # Verified above: recorded as-is, exactly like a server-produced one.
        return seal_sig
    return signing.sign_seal(norm, target_text, verifier)


def _check_not_rejected(existing: dict, status: str, override_rejection: bool) -> None:
    """A rejected pair must not be resurrected by a routine re-seal."""
    if (existing["status"] == "rejected" and status == "sealed"
            and not override_rejection):
        raise RejectedPairError(
            f"pair {existing['id']} was rejected by "
            f"{existing.get('verifier') or 'a reviewer'!r} and will not be "
            f"re-sealed implicitly. Restore it first (Curator.restore) or "
            f"pass override_rejection=True."
        )


def _check_no_conflicting_seal(existing: dict, status: str, target_text: str,
                               verifier: str, override_conflict: bool) -> None:
    """A different verifier asserting a different target for an already-SEALED
    source is a conflict, not a routine upgrade."""
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


def _check_no_conflicting_draft(existing: dict, status: str, target_text: str) -> None:
    """A draft over a different draft. Below this point every branch is a
    seal, so without this the call would silently return the stored row."""
    if (status == "draft" and existing["status"] == "draft"
            and existing["target_text"] != target_text):
        raise ConflictingDraftError(
            f"pair {existing['id']} already holds the draft "
            f"{existing['target_text']!r} for this source; {target_text!r} is "
            f"a different proposal. add_pair writes only when sealing, so "
            f"this would have returned the stored draft as if it were yours. "
            f"Call revise_draft() to replace it — the old proposal is kept "
            f"as history with its reason, which is the point. Or seal it if "
            f"a human has checked it, or reject_match the one you do not want."
        )


def _upgrade_local_draft(store: Storage, existing: dict, norm: str, source_lang: str,
                         target_lang: str, target_text: str, verifier: str,
                         weight: float, seal_sig: str, reason: str, origin: str,
                         audit: bool) -> dict:
    """Seal ``existing`` (a draft, or a sealed row with a same-verifier
    correction) with ``target_text``, and ledger the upgrade.

    Re-reads the row after ``memory_seal`` and raises if it is gone — the
    read-after-write invariant this function relies on for the audit trail
    below. Overwriting a seal destroys a previous human decision, and the
    memory keeps only one row per normalized source, so without the ledger
    entries here the earlier verification would leave no trace anywhere.
    """
    replaced_target = existing["target_text"]
    replaced_status = existing["status"]
    replaced_verifier = existing.get("verifier", "")
    store.memory_seal(existing["id"], target_text, verifier, weight, seal_sig)
    # memory_seal predates N4 and its signature is frozen into every host's
    # Storage implementation, so the reason rides a separate optional op.
    # Losing it silently would recreate the asymmetry N4 closes, so a store
    # without the op refuses a reason instead.
    if reason:
        setter = getattr(store, "memory_set_reason", None)
        if not callable(setter):
            raise RuntimeError(
                f"{type(store).__name__} has no memory_set_reason; "
                f"refusing to drop the recorded reason for this seal "
                f"on the floor — omit reason= or extend the store.")
        setter(existing["id"], reason)
    refreshed = store.memory_find(norm, source_lang, target_lang)
    if refreshed is None:
        # The row this call just sealed above cannot legitimately be gone one
        # line later — this store violated the read-after-write invariant.
        # Surfacing that loudly beats a bare TypeError from the indexing that
        # follows.
        raise RuntimeError(
            f"{type(store).__name__} lost pair for {norm!r} "
            f"immediately after memory_seal — read-after-write "
            f"invariant violated.")
    existing = refreshed
    if audit:
        _log_seal_event({
            "kind": "seal", "pair_id": existing["id"], "verifier": verifier,
            "source_lang": source_lang, "target_lang": target_lang,
            "source_sha": _sha(norm), "origin": origin,
            "upgraded_from": replaced_status,
        })
    # Reaching here with a DIFFERENT verifier means the guard above was
    # explicitly overridden, so `same_verifier: False` in the trail marks a
    # deliberate overrule rather than an accident. Curator.replaced_seals
    # surfaces exactly those.
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


def _log_seal_countersign(existing: dict, verifier: str, source_lang: str,
                          target_lang: str, norm: str, target_text: str,
                          origin: str, seal_sig: str) -> None:
    """Reached only when the row is ALREADY sealed with THIS target.

    Nothing about the row changes here, and nothing about serving does. There
    is one ``verifier`` column and one ``seal_sig``, and they belong to
    whoever got there first; the second signature has nowhere to live but the
    chain.
    """
    first = (existing.get("verifier") or "")
    # NOT `not _same_verifier(first, verifier)`. That helper answers "may we
    # assume the same actor", and resolves unknown to *not the same* so a
    # guard fails closed. Negating it inherits the wrong polarity: two
    # anonymous re-seals would become a countersignature between two people
    # who never identified themselves. Both sides must NAME somebody before
    # this is evidence of anything.
    if first and verifier and first != verifier:
        _log_countersign({
            "kind": "countersign", "pair_id": existing["id"],
            "verifier": verifier, "countersigned": first,
            "source_lang": source_lang, "target_lang": target_lang,
            "source_sha": _sha(norm), "target_sha": _sha(target_text),
            "origin": origin,
            # The signature the row cannot carry. Computed above with this
            # caller's key, so with a keyring installed an unknown or revoked
            # countersigner is refused before the store is touched — same
            # refusal a seal gets, for the same reason.
            "sig": seal_sig,
        })


def _retry_insert_race(source_text: str, target_text: str, source_lang: str,
                       target_lang: str, status: str, verifier: str, weight: float,
                       origin: str, reason: str, store: Storage,
                       matcher: Optional[Matcher], override_rejection: bool,
                       override_conflict: bool, audit: bool, seal_sig: str,
                       norm: str, _racing: bool) -> dict:
    """Recover from a losing race on ``store.memory_insert``.

    Somebody inserted the same normalized source between our ``memory_find``
    and this line. That window is real — nestor.ui seals from a thread pool
    — and it used to end with two sealed rows for one source, no
    ConflictingSealError, and no answer to which one serves.

    A store that enforces uniqueness on (source_norm, source_lang,
    target_lang) turns that race into this failure, and the failure into the
    correct outcome: re-run, take the existing-row path, and let the
    ordinary guards decide — which raises ConflictingSealError when the
    winner is a different verifier with a different answer. ``_racing``
    bounds it to one retry, so a genuine insert error still surfaces. Must be
    called from within the ``except`` block it recovers, so the bare
    ``raise`` below re-raises that original exception.
    """
    if _racing or not store.memory_find(norm, source_lang, target_lang):
        raise
    return add_pair(source_text, target_text, source_lang, target_lang,
                    status=status, verifier=verifier, weight=weight,
                    origin=origin, reason=reason, store=store, matcher=matcher,
                    override_rejection=override_rejection,
                    override_conflict=override_conflict, audit=audit,
                    # Carry the ALREADY-RESOLVED signature into the retry —
                    # not the original `seal_sig` argument. On a race the
                    # existing-row branch above may resolve this call to a
                    # no-op (draft already sealed by somebody else) rather
                    # than a fresh write, so re-verifying a client signature
                    # or re-signing here is a redundant check, never a
                    # second act of signing/trust.
                    seal_sig=seal_sig, _racing=True)


def add_pair(source_text: str, target_text: str, source_lang: str, target_lang: str,
             status: str = "draft", verifier: str = "", weight: float = 1.0,
             origin: str = "", reason: str = "",
             store: Optional[Storage] = None,
             matcher: Optional[Matcher] = None,
             override_rejection: bool = False,
             override_conflict: bool = False,
             audit: bool = True, seal_sig: str = "",
             pair_id: str = "", created_at: str = "",
             _racing: bool = False) -> dict:
    """Insert or upgrade a pair. A sealed insert replaces a draft for the same source.

    ``source_lang`` / ``target_lang`` are generic DOMAIN tags: for translation
    they are languages; for entity resolution or numeric reconciliation they
    carry the entity-type / label bucket. The ``matcher`` (default
    :class:`StringMatcher`) decides how ``source_text`` is normalized.

    ``reason`` is the rationale FOR this pair (docs/decision-memory.md N4) —
    ``tm_rejections`` always recorded why a reviewer said no; this is the
    symmetric why-yes, and it survives supersession with the row it explains.

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

    ``seal_sig`` (Nestor#17, the client-signing seam): normally omitted, and
    the server signs the seal itself via :func:`nestor.signing.sign_seal`
    exactly as it always has — this parameter changes nothing for that,
    default, path. Pass it when a CLIENT already produced the signature (for
    instance, an ed25519 keyring entry here holds only the verifier's PUBLIC
    key, so this instance never could have signed for them). When supplied,
    ``add_pair`` never calls ``sign_seal`` — it only VERIFIES the given
    signature with :func:`nestor.signing.seal_is_valid`, against the same
    frozen wire message :func:`nestor.signing._message` documents, and raises
    :class:`InvalidSealSignatureError` if it does not verify. That check runs
    before any store read or write, so an invalid provided signature writes
    nothing — no row, sealed or otherwise. This is the only way a keyring
    entry holding just an ed25519 public key can produce a sealed row here:
    the private key never has to touch this process.
    """
    store = get_store(store)
    matcher = get_matcher(matcher)
    store.memory_init()
    # Verifier policy is checked before anything else that follows a "sealed"
    # status — same rung as the ledger preflight below, and for the same
    # reason: a refusal here must leave no row behind, sealed or otherwise.
    if status == "sealed":
        _check_verifier_policy(store, source_lang, target_lang, verifier)
    # A seal has to be auditable to be a seal. Refuse before touching the store,
    # so a broken or unwritable chain cannot leave a verified row with no trail.
    if status == "sealed" and audit:
        _ledger_preflight()
    norm = matcher.normalize(source_text)
    seal_sig = _resolve_seal_sig(status, norm, target_text, verifier, seal_sig)
    existing = store.memory_find(norm, source_lang, target_lang)
    if existing:
        if (existing.get("source_text") or "") != source_text:
            _drop_stored_embeddings(store, existing["id"])
        _check_not_rejected(existing, status, override_rejection)
        _check_no_conflicting_seal(existing, status, target_text, verifier, override_conflict)
        _check_no_conflicting_draft(existing, status, target_text)
        if status == "sealed" and (
            existing["status"] != "sealed" or existing["target_text"] != target_text
        ):
            existing = _upgrade_local_draft(
                store, existing, norm, source_lang, target_lang, target_text,
                verifier, weight, seal_sig, reason, origin, audit)
        elif status == "sealed" and audit:
            _log_seal_countersign(existing, verifier, source_lang, target_lang,
                                  norm, target_text, origin, seal_sig)
        return existing
    # `pair_id`/`created_at` default to a fresh uuid4 and now(); a caller that
    # rebuilds a derived, committed store from source (scripts/dogfood_store.py)
    # passes deterministic values instead, so the artifact does not churn every
    # rebuild. A seal signature covers (source_norm, target_text, verifier), never
    # the id or timestamp, so pinning them cannot affect what verifies.
    pair = dict(id=pair_id or str(uuid.uuid4()), source_text=source_text, source_norm=norm,
                source_lang=source_lang, target_text=target_text, target_lang=target_lang,
                status=status, verifier=verifier, weight=weight, origin=origin,
                reason=reason, created_at=created_at or _now(), seal_sig=seal_sig)
    try:
        store.memory_insert(pair)
    except Exception:
        # See _retry_insert_race: a losing race on a uniqueness constraint is
        # recovered by re-running through the existing-row path above.
        return _retry_insert_race(
            source_text, target_text, source_lang, target_lang, status, verifier,
            weight, origin, reason, store, matcher, override_rejection,
            override_conflict, audit, seal_sig, norm, _racing)
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


def _require_lineage(store: Storage) -> None:
    require_capability(
        store, "lineage",
        f"{type(store).__name__} does not implement Nestor's lineage "
        f"capability. Implement memory_mark_superseded and memory_lineage "
        f"(see nestor.storage.Storage) — refusing to fall back to the "
        f"destructive overwrite supersede_pair exists to replace."
    )


def supersede_pair(source_text: str, target_text: str, source_lang: str,
                   target_lang: str, verifier: str, reason: str = "",
                   weight: float = 1.0, origin: str = "",
                   store: Optional[Storage] = None,
                   matcher: Optional[Matcher] = None,
                   audit: bool = True) -> dict:
    """Replace the live sealed pair for ``source_text`` WITHOUT destroying it.

    The revision path ``add_pair`` never had (docs/decision-memory.md N3;
    ``test_seal_replacement.py`` documents what the overwrite loses). The old
    row keeps its text, verifier, signature and reason, gains
    ``superseded_by`` pointing at its successor, and falls out of the live
    unique index — so history accumulates while every serve path still sees
    exactly one row per source. ``memory_lineage(new_id)`` walks the chain
    back, newest first.

    Requires the lineage capability (:func:`nestor.storage.supports_lineage`)
    and raises without it rather than falling back to an overwrite. Requires
    a ``verifier``: replacing a sealed decision is itself a decision.

    A rejected pair is refused (a rejection is not a competing answer —
    restore it first, the same rule import follows); a draft is refused (a
    draft is upgraded by ``add_pair``, it holds no decision to keep).
    """
    store = get_store(store)
    _require_lineage(store)
    # _require_lineage raises unless supports_lineage(store) — the cast just
    # tells the type checker what that runtime check already established.
    store = cast(LineageStorage, store)
    matcher = get_matcher(matcher)
    store.memory_init()
    if not verifier:
        raise ValueError("supersede_pair requires a verifier — replacing a "
                         "sealed decision is itself a decision")
    _check_verifier_policy(store, source_lang, target_lang, verifier)
    if audit:
        _ledger_preflight()   # a supersede is a seal; refuse before writing
    norm = matcher.normalize(source_text)
    old = store.memory_find(norm, source_lang, target_lang)
    if old is None:
        raise ValueError(f"nothing to supersede for {source_text!r} "
                         f"({source_lang}->{target_lang}) — use add_pair")
    if old["status"] == "rejected":
        raise RejectedPairError(
            f"pair {old['id']} was rejected; a rejection is not a competing "
            f"answer to supersede. Restore it first (Curator.restore).")
    if old["status"] != "sealed":
        raise ValueError(f"pair {old['id']} is a draft — supersede replaces "
                         f"a sealed decision; upgrade drafts via add_pair")
    if old["target_text"] == target_text:
        raise ValueError(f"successor target equals the live target "
                         f"{target_text!r} — nothing to supersede")

    seal_sig = signing.sign_seal(norm, target_text, verifier)
    # A separate typed local rather than `new_pair["id"]` below: `new_pair`
    # mixes str and float values (weight), so mypy infers its value type as
    # `object` and the id needs its own `str` type to be used as one (string
    # concat, a str parameter) after it goes in.
    new_id: str = str(uuid.uuid4())
    new_pair = dict(id=new_id, source_text=source_text,
                    source_norm=norm, source_lang=source_lang,
                    target_text=target_text, target_lang=target_lang,
                    status="sealed", verifier=verifier, weight=weight,
                    origin=origin, reason=reason, created_at=_now(),
                    seal_sig=seal_sig)
    # The old row must leave the live index before the successor can enter it
    # (the partial unique index correctly refuses two live rows for one key).
    # Mark first, insert second, then point the marker at the real successor;
    # a failed insert restores the old row so a failed supersede leaves the
    # store exactly as it found it.
    store.memory_mark_superseded(old["id"], "pending:" + new_id)
    try:
        store.memory_insert(new_pair)
    except Exception:
        store.memory_mark_superseded(old["id"], "")
        raise
    store.memory_mark_superseded(old["id"], new_id)
    # A superseded row is never scored again; its cached vector is dead weight
    # (the reject_pair precedent — reject_match keeps vectors, this does not).
    _drop_stored_embeddings(store, old["id"])
    if audit:
        _log_seal_event({
            "kind": "seal", "pair_id": new_pair["id"], "verifier": verifier,
            "source_lang": source_lang, "target_lang": target_lang,
            "source_sha": _sha(norm), "origin": origin,
            "upgraded_from": "supersede",
        })
        _log_seal_event({
            "kind": "supersede", "old_pair_id": old["id"],
            "new_pair_id": new_pair["id"],
            "source_lang": source_lang, "target_lang": target_lang,
            "replaced_verifier": old.get("verifier", ""), "verifier": verifier,
            "replaced_target_sha": _sha(old["target_text"]),
            "target_sha": _sha(target_text), "source_sha": _sha(norm),
            "reason": reason,
            "same_verifier": old.get("verifier", "") == verifier,
        })
    return new_pair


def revise_draft(source_text: str, target_text: str, source_lang: str,
                 target_lang: str, reason: str = "", weight: float = 1.0,
                 origin: str = "", store: Optional[Storage] = None,
                 matcher: Optional[Matcher] = None,
                 audit: bool = True) -> dict:
    """Replace a live **draft** with a revised one, keeping the old as history.

    The missing third verb. :func:`supersede_pair` covers sealed→sealed and
    :func:`add_pair` covers draft→sealed; draft→draft had nothing, so an agent
    — which may propose and may not confirm — could not record a changed mind
    at all. It got :class:`ConflictingDraftError` and no way past it
    (IDEAS §6.18, §6.19).

    No ``verifier``, and that is the whole difference from ``supersede_pair``.
    That function demands one because *"replacing a sealed decision is itself a
    decision"* — a human's recorded judgment is being retired and somebody must
    own that. A draft is nobody's judgment. Requiring a verifier here would be
    the machine signing for a decision it is not allowed to make, which is the
    covenant inverted; the successor is therefore a **draft** too, unsealed and
    unsigned, and sealing it stays a separate human act through ``add_pair``.

    History is kept for the same reason it is kept for seals: the abandoned
    proposal carries the ``reason`` it was abandoned *for*, and that reasoning
    is the only thing distinguishing "we tried this and it was wrong" from "we
    never thought of it". ``memory_lineage`` walks the chain. Nothing new is
    needed in ``Storage`` to do it — ``memory_mark_superseded`` and
    ``memory_insert`` already exist for ``supersede_pair``, so this is a verb
    ``memory`` was withholding, not one the Protocol lacked. An earlier note in
    §6.19 said otherwise and was wrong.

    Requires the lineage capability, and refuses rather than overwriting
    without it — the same rule ``supersede_pair`` follows, for the same reason:
    losing what was proposed before is the failure this exists to prevent.
    """
    store = get_store(store)
    _require_lineage(store)
    require_capability(
        store, "atomic_supersede",
        f"{type(store).__name__} cannot retire a row conditionally (see "
        f"storage.supports_atomic_supersede), so this revision would have to "
        f"check the row in Python and then overwrite it blind. That race "
        f"retires a human's seal and installs an unverified draft in its "
        f"place, so it is refused rather than degraded.")
    # Same check-then-cast shape as supersede_pair above.
    store = cast(AtomicSupersedeStorage, store)
    matcher = get_matcher(matcher)
    store.memory_init()
    if audit:
        _ledger_preflight()   # a revision discards a proposal; refuse before writing
    norm = matcher.normalize(source_text)
    old = store.memory_find(norm, source_lang, target_lang)
    if old is None:
        raise ValueError(f"nothing to revise for {source_text!r} "
                         f"({source_lang}->{target_lang}) — use add_pair")
    if old["status"] == "rejected":
        raise RejectedPairError(
            f"pair {old['id']} was rejected; a rejection is not a competing "
            f"proposal to revise. Restore it first (Curator.restore).")
    if old["status"] == "sealed":
        raise ValueError(
            f"pair {old['id']} is sealed — a human checked it, so replacing it "
            f"is supersede_pair's job and needs a verifier. revise_draft only "
            f"touches proposals nobody has ratified.")
    if old["target_text"] == target_text:
        raise ValueError(f"revised target equals the live draft {target_text!r} "
                         f"— nothing to revise (add_pair is the idempotent path)")
    # A human may already have refused this exact answer for this query. The
    # status check above only catches reject_pair; reject_match lives in
    # tm_rejections, and without this an agent could install a target somebody
    # signed a "no" against — after which `lookup` suppresses the new live row
    # and the good draft is in history, so the store stops answering at all.
    if supports_rejection(store):
        _, bad_targets = rejected_ids(norm, source_lang, target_lang, store)
        if target_text in bad_targets:
            raise RejectedPairError(
                f"{target_text!r} was recorded as the wrong answer for this query "
                f"by a reviewer; revising a draft to it would install something a "
                f"human refused. Restore the rejection first if it no longer stands.")

    # See the matching comment in supersede_pair: a separate typed local
    # keeps the id a `str` for the string concat and store calls below,
    # where `new_pair["id"]` would type as `object`.
    new_id: str = str(uuid.uuid4())
    new_pair = dict(id=new_id, source_text=source_text,
                    source_norm=norm, source_lang=source_lang,
                    target_text=target_text, target_lang=target_lang,
                    status="draft", verifier="", weight=weight,
                    origin=origin, reason=reason, created_at=_now(),
                    seal_sig="")
    pending = "pending:" + new_id
    # COMPARE-AND-SET, not mark-and-hope. Every guard above ran against a read
    # from before this line, and the write that acts on them used to be an
    # unconditional UPDATE — so a human sealing the draft in between had their
    # seal retired by this call and replaced with an unsigned draft, 282 times
    # in 300 threaded trials. The precondition travels with the write now: if
    # the row is no longer the draft we read, nothing moves and we say so.
    if not store.memory_mark_superseded_if(old["id"], pending, "draft", ""):
        raise ConflictingDraftError(
            f"pair {old['id']} changed under this revision — it is no longer the "
            f"unsealed draft that was read (most likely a human sealed it, or "
            f"another revision won the race). Nothing was written. Re-read and "
            f"decide again.")
    try:
        store.memory_insert(new_pair)
    except Exception:
        # Roll back ONLY if we still own the marker. The unconditional restore
        # this replaces could overwrite the winner's successor pointer with our
        # own abandoned one — 184 of 200 concurrent trials ended with the
        # surviving revision's history pointing at a row that was never
        # inserted, which is the lineage this verb exists to keep. It could
        # also raise on its own and mask the real failure, so it is suppressed.
        try:
            store.memory_mark_superseded_if(old["id"], "", "draft", pending)
        except Exception:                        # noqa: BLE001 — never mask the cause
            pass
        raise
    store.memory_mark_superseded_if(old["id"], new_id, "draft", pending)
    _drop_stored_embeddings(store, old["id"])
    if audit:
        # `supersede`, not `seal`: nothing was verified here. No seal entry is
        # written at all, because a draft revision grants no trust — and a
        # ledger that logged one would say a human had acted.
        _log_seal_event({
            "kind": "supersede", "old_pair_id": old["id"],
            "new_pair_id": new_pair["id"],
            "source_lang": source_lang, "target_lang": target_lang,
            "replaced_verifier": old.get("verifier", ""), "verifier": "",
            "replaced_status": "draft",
            "replaced_target_sha": _sha(old["target_text"]),
            "target_sha": _sha(target_text), "source_sha": _sha(norm),
            "reason": reason,
            # Computed, not asserted. memory_unseal clears seal_sig and KEEPS
            # verifier, so a revised once-sealed row can have a non-empty
            # predecessor verifier while this caller has none — and the trail
            # is append-only and FRANK-mirrored, so a false field in it stays.
            "same_verifier": old.get("verifier", "") == "",
        })
    return new_pair


def lookup(source_text: str, source_lang: str, target_lang: str,
           limit: int = 5, store: Optional[Storage] = None,
           matcher: Optional[Matcher] = None,
           context_threshold: Optional[float] = None) -> list[dict]:
    """Ranked matches: [{pair, similarity}], best first. Sealed and draft both returned.

    Scoring is delegated to the injected ``matcher`` (default StringMatcher, so
    translation behavior is unchanged). When the matcher implements
    ``score(raw_a, raw_b)``, each candidate is scored from the query text and
    the row's ``source_text``; otherwise ``similarity`` on normalized keys.
    ``context_threshold`` overrides the module-level :data:`CONTEXT_THRESHOLD`
    floor below which candidates are dropped — pass ``0.0`` to keep every
    candidate (used by the numeric reconciler so a far-off figure is still
    returned for variation reporting).
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
    eligible = []
    for row in rows:
        if row["status"] == "rejected":
            continue
        if row["id"] in bad_pairs or row["target_text"] in bad_targets:
            continue
        eligible.append(row)

    scored: list[dict] = []
    raw_score, sims = _raw_score_sims(matcher, source_text, eligible, store)
    for row in eligible:
        sim = _similarity_for_row(matcher, source_text, norm, row,
                                  raw_score=raw_score, sims=sims)
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


# round(sim, 3) is what a candidate is judged on (see lookup), so a raw score of
# 0.91951 clears a 0.92 bar. A bound must not prune what rounding would have let
# through, so the cutoff sits this far below the bar.
_ROUNDING_SLACK = 0.001


def best_sealed(source_text: str, source_lang: str, target_lang: str,
                store: Optional[Storage] = None,
                matcher: Optional[Matcher] = None,
                seal_threshold: Optional[float] = None,
                context_threshold: Optional[float] = None) -> Optional[dict]:
    """Tier-1 check: the best sealed match at/above the seal threshold, else None.

    ``seal_threshold`` overrides the module-level :data:`SEAL_THRESHOLD`.

    **Its own scan, not a filter over** :func:`lookup`. Two reasons, and the
    second is a defect the first happened to fix:

    * *Speed.* This is the one question where the answer is not the argmax but
      "is anything at all above the bar", so the bar can seed the scan: every
      candidate is discardable on its upper bound from the very first row rather
      than only once a good match has turned up. Measured on absent probes —
      the case that pruned worst — 22.1 s → 2.5 s on 4,000 prose pairs, 94.2 s →
      15.5 s on 24,000 boilerplate, zero disagreements above the bar
      (IDEAS §2.1). ``lookup`` cannot do this: it owes the engine sub-threshold
      candidates as context, so it has to score everything.
    * *Correctness.* Going through ``lookup`` meant going through its ``limit``,
      which defaults to 5. A verified sealed pair ranked sixth behind five
      drafts was invisible to tier 1 — the memory held a human's verification,
      the query matched it above threshold, and Nestor drafted a fresh answer
      instead. Scanning the candidates directly has no top-N to fall out of.

    Rejection, the seal-signature check and the score itself are unchanged and
    still come from the same places (``rejected_ids``, :func:`is_verified_seal`,
    the injected matcher), so this is the same decision reached by a shorter
    road. A matcher that offers no ``similarity_bound`` simply scores every
    candidate, exactly as before.
    """
    store = get_store(store)
    matcher = get_matcher(matcher)
    store.memory_init()
    seal = SEAL_THRESHOLD if seal_threshold is None else seal_threshold
    _warn_score_matcher_default_threshold(matcher, seal_threshold)
    ctx = CONTEXT_THRESHOLD if context_threshold is None else context_threshold
    norm = matcher.normalize(source_text)
    bad_pairs, bad_targets = rejected_ids(norm, source_lang, target_lang, store)
    bound = getattr(matcher, "similarity_bound", None)
    raw_score = uses_raw_score(matcher)
    if not callable(bound) or raw_score:
        # Bounds are defined on normalized keys; invalid when score() sees raw text.
        bound = None

    best: Optional[dict] = None
    best_sim = 0.0
    candidates: list[dict] = []
    for row in store.memory_candidates(source_lang, target_lang):
        if row["status"] != "sealed":
            continue
        if row["id"] in bad_pairs or row["target_text"] in bad_targets:
            continue
        candidates.append(row)

    raw_score, sims = _raw_score_sims(matcher, source_text, candidates, store)
    for row in candidates:
        # Beat the bar, and then beat the incumbent.
        need = max(seal, ctx, best_sim) - _ROUNDING_SLACK
        if bound is not None and bound(norm, row["source_norm"], need) < need:
            continue
        raw = _similarity_for_row(matcher, source_text, norm, row,
                                  raw_score=raw_score, sims=sims)
        if raw < ctx:                      # lookup's context floor, unrounded
            continue
        sim = round(raw, 3)                # what lookup reports, and judges on
        if sim < seal or sim <= best_sim:
            continue
        # Checked last because it is the expensive one (an HMAC), and because a
        # row that cannot win does not need its signature verified.
        if is_verified_seal(row):
            best, best_sim = row, sim
    if best is None:
        return None
    return {"pair": best, "similarity": best_sim,
            "warrant_kinds": warrant_kinds_for(best["id"], store)}


def warrant_kinds_for(pair_id: str, store: Storage) -> list[str]:
    """The warrant kinds the served row holds — *"warranted how"*, sorted.

    IDEAS §1.10(a), decided in 0164: this is the whole of what warrants change
    about serving. ``best_sealed`` still gates on ``sealed`` and nothing else,
    so a cited-but-unsealed row is found here exactly as often as before —
    never. A fourth status, or a warrant admitted into the field tier 1 reads,
    would put a claim no local human vouched for into the top rung: jeles'
    laundering case arriving by a different door, and jeles fixed that by
    adding a rung *below*, never by widening what the top rung admits.

    So this is said **alongside** the seal, never instead of it. It is a
    display fact about a row that already won on its seal.

    Empty on a store without the warrants capability — which is the same fact
    as "this row holds none" and, unlike the provenance view, is safe to
    collapse here: the serve path is not making a claim about what is attached,
    it is annotating what it is already serving on other grounds. A caller who
    needs the distinction, the authority or the locator asks
    :func:`nestor.answer.provenance`, which keeps them apart.
    """
    from .storage import supports_warrants
    if not supports_warrants(store):
        return []
    from . import warrant
    try:
        return sorted(warrant.kinds_held(pair_id, store=store))
    except Exception:                      # noqa: BLE001 — never fail a served answer
        # An annotation must not be able to withhold a verified answer. The
        # seal is what entitles this row to be served; the warrant set is
        # commentary on it, and commentary that raises is dropped, not fatal.
        return []


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
        # Name the entry kind — hard-coding "seal" lied when any other kind
        # (or, before §6.26's split, a countersign) took this path.
        kind = str(entry.get("kind") or "entry")
        warnings.warn(
            f"a {kind} was written but its ledger entry was not: "
            f"{type(exc).__name__}: {exc}. The store and the trail now disagree; "
            f"run nestor.ledger.verify() and reconcile before trusting this row.",
            RuntimeWarning, stacklevel=2)


def _log_countersign(entry: dict) -> None:
    """Append a countersignature, and **raise** if the trail will not take it.

    The opposite posture to :func:`_log_seal_event`, on that function's own
    reasoning. It swallows because *"the pair is already committed by the time
    we get here"*, so raising would hand the caller a completed write plus an
    exception — the worst of both.

    A countersignature commits nothing. There is no row to leave behind: the
    ledger entry **is** the whole product (IDEAS §6.26 — `tm_pairs` has one
    `verifier` and one `seal_sig` and they belong to whoever sealed first). So
    an append that fails means the operation did not happen, and returning
    normally would silently reproduce the exact defect §6.26 exists to close,
    one edge over. Raising leaves the caller where they started.

    Found in review of the PR that added the countersignature: the swallowed
    path also warned *"a seal was written but its ledger entry was not"* on a
    call where no seal was written, so the one signal a curator got was false.
    Countersignatures no longer use that helper; its warning now names
    ``entry["kind"]`` so a future passenger cannot repeat the lie.
    """
    from .cascade import _ledger_append
    _ledger_append(entry)


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
    require_capability(
        store, "rejection",
        f"{type(store).__name__} does not implement Nestor's rejection "
        f"capability. Implement memory_reject_pair, memory_add_rejection "
        f"and memory_rejections (see nestor.storage.Storage) — refusing to "
        f"accept a rejection that would be silently discarded."
    )


def reject_match(source_text: str, source_lang: str, target_lang: str,
                 pair_id: str = "", target_text: str = "", verifier: str = "",
                 reason: str = "", reopen_when: str = "",
                 store: Optional[Storage] = None,
                 matcher: Optional[Matcher] = None) -> dict:
    """Record that a candidate is the WRONG answer for ``source_text``.

    Identify what is being rejected by ``pair_id`` (a memory pair that matched
    this query — the false-seal case) or by ``target_text`` (a raw engine draft
    with no pair yet), or both. The pair itself stays valid for its own source
    text; use :func:`reject_pair` when the mapping is wrong in its own right.

    ``reopen_when`` distinguishes NEVER from NOT YET (docs/decision-memory.md
    N5): empty keeps the rejection permanent, exactly as before; non-empty
    names the condition under which this "no" becomes an open question again.
    A reader that surfaces rejections should surface a non-empty
    ``reopen_when`` as a condition to re-check, not a closed door.

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
        verifier=verifier, reason=reason, reopen_when=reopen_when,
        created_at=_now(),
        reject_sig=signing.sign_rejection(norm, pair_id, target_text, verifier),
    )
    store.memory_add_rejection(rejection)
    _log_rejection({"kind": "reject_match", "query_norm": norm,
                    "source_lang": source_lang, "target_lang": target_lang,
                    "pair_id": pair_id, "verifier": verifier, "reason": reason,
                    "reopen_when": reopen_when,
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
    # A rejected pair is never scored again, so its cached vector is dead weight
    # that nothing else prunes. (`reject_match` deliberately does not do this:
    # it rejects one query against the pair, and the pair still answers others.)
    _drop_stored_embeddings(store, pair_id)
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
