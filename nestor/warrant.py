"""Warrants — why a claim is trustworthy, when the reason is not "someone here checked".

Seal state answers *has a human checked this, here?*. Evidence
(:mod:`nestor.evidence`) answers *what does it point at?*. Neither answers
*what entitles a stranger to believe it?* — and that is a third question, with
three known answers (IDEAS §1.10, ``docs/warrants.md``, decision 0164):

===============  ==========================  ===============================
warrant          what makes it good          who can check it
===============  ==========================  ===============================
**attestation**  a person here checked       whoever trusts that person
**citation**     a named authority asserted  anyone who can follow the source
**construction** the shape proves it         anyone, trusting nobody
===============  ==========================  ===============================

**Two stored kinds, not three.** ``attestation`` is deliberately absent from
:data:`WARRANT_KINDS`: a sealed pair *already is* an attestation, carrying a
signature bound to a key this store does not hold. Storing it a second time
would be two representations of one fact, and one of them forgeable — the
two-paths-into-the-store defect this package has fixed four times (IDEAS
§1.6-1.8). :func:`warrants_for` composes the seal in on read instead, so a
caller still sees the whole set.

**Warrants accumulate and never rank.** One claim can be sealed *and* cited
*and* constructed, and is then stronger than a claim holding any one alone.
"Sealed by Rita" and "cited to Crossref" do not compare, so this is a set, not
a ladder — there is no ``max()`` here, not even for display. jeles reached the
same conclusion from the other side: its ``_KIND_RANK`` ranks only the three
kinds it judges for itself, and ``put_nugget`` structurally *refuses* to write
the unrankable fourth (``jeles/corpus.py:449``) rather than rank it.

**Nestor never marks a warrant satisfied.** There is no ``verified`` column and
no method that would set one. A warrant row is the *claim that a warrant
exists*, plus what a reader needs to check it themselves. That is the same
posture the seal already takes — the store holds the signature and does not
hold the key — and it is what makes a warrant safe to carry between instances
while a *conclusion* about it is not (``portable.py``: import may carry a
warrant, and may never carry a conclusion about it).

**How this differs from evidence, in one line.** Evidence is a pointer that
"carries no authority and needs none". A warrant names an authority and says how
to check it. That is why they are different tables and why they cross an
instance boundary under different rules.

See ``docs/warrants.md`` and decision 0164.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional, cast

from .storage import Storage, WarrantStorage, get_store, require_capability

#: The warrant kinds that may be *stored*. ``attestation`` is not here on
#: purpose — see the module docstring. A kind outside this set is refused at
#: attach time rather than stored, the same posture as ``EVIDENCE_KINDS`` and
#: ``EDGE_KINDS``: a typo must not silently grow an unqueryable taxonomy.
WARRANT_KINDS = frozenset({"citation", "construction"})

#: The kind :func:`warrants_for` composes from the pair's own seal. Never
#: stored, never accepted by :func:`attach`.
ATTESTATION = "attestation"

_MAX_AUTHORITY = 512
_MAX_LOCATOR = 4096
_MAX_CHECK = 4096


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_warrants(store: Storage) -> None:
    require_capability(
        store, "warrants",
        f"{type(store).__name__} does not implement Nestor's warrants "
        f"capability (memory_add_warrant, memory_warrants_for — see "
        f"nestor.storage).")


def refuse_reason(kind: str, authority: str, locator: str, check: str,
                  expected_digest: str) -> str:
    """Why this warrant may not be written, or ``""`` if it may.

    Returns rather than raises because it has two callers with two duties.
    :func:`attach` raises the string at a local caller who can fix the argument.
    :func:`nestor.portable.import_bundle` cannot — the row came from another
    instance and there is nobody here to correct — so it refuses that one row,
    names the reason in its report, and imports the rest.

    Both must refuse the *same* set, which is the whole reason this is one
    function. A rule enforced on the local path and not on the import path is
    not a rule; it is a preference with a hole in it, and the hole is the side
    a stranger's file arrives on.
    """
    if kind == ATTESTATION:
        return ("attestation is not a stored warrant — a sealed pair already "
                "is one, signed under a key this store does not hold. Seal the "
                "pair; warrants_for() composes it in on read.")
    if kind not in WARRANT_KINDS:
        return f"unknown warrant kind {kind!r} — one of {sorted(WARRANT_KINDS)}"
    if not authority or not authority.strip():
        return ("a warrant needs an authority — who vouches (the naming "
                "institution, or the tool that would recompute). A warrant "
                "with nobody behind it is evidence; use nestor.evidence.attach.")
    if not locator or not locator.strip():
        return "a warrant needs a locator — where a reader goes to check it"
    if len(authority) > _MAX_AUTHORITY or len(locator) > _MAX_LOCATOR \
            or len(check) > _MAX_CHECK:
        return (f"authority (max {_MAX_AUTHORITY}), locator (max "
                f"{_MAX_LOCATOR}) or check (max {_MAX_CHECK}) is too long; a "
                f"warrant is a pointer and a procedure, not the document")
    if kind == "construction" and not expected_digest.strip():
        return ("a construction warrant needs an expected_digest — what the "
                "recomputation must produce. Without it the warrant asserts "
                "that the shape proves the claim while giving a reader no way "
                "to run the shape, which is an assertion, not a proof.")
    if kind == "citation" and expected_digest.strip():
        return ("a citation warrant takes no expected_digest — there is "
                "nothing here to recompute, and carrying one would read as "
                "though Nestor had checked the source. It has not; that is the "
                "reader's to do.")
    return ""


def attach(pair_id: str, kind: str, authority: str, locator: str, *,
           check: str = "", expected_digest: str = "", attached_by: str = "",
           store: Optional[Storage] = None) -> dict:
    """Record that ``pair_id`` holds a warrant of ``kind``. Confirms nothing.

    ``authority`` is who vouches — the naming institution for a ``citation``,
    the tool that would recompute for a ``construction``. ``locator`` is where a
    reader goes: a URL or DOI, or the recipe to run. ``check`` is what they do
    when they get there, in prose, and may be empty for a citation whose locator
    speaks for itself.

    ``expected_digest`` is **required for construction and refused for
    citation**. A construction warrant that does not say what the recomputation
    must produce is an assertion wearing a proof's clothes — it is the string
    "constructed" and nothing more, which is exactly the rung jeles had to add
    ``asserted`` *below*. A citation has no digest to expect; accepting one
    would invite a caller to believe Nestor checked it.

    Returns the stored row. Refuses — with nothing written — an unknown kind,
    ``attestation`` (that is the seal's job), an empty authority or locator, an
    over-long field, a missing or misplaced digest, a pair that does not exist,
    or a ledger that cannot take the entry.
    """
    store = get_store(store)
    _require_warrants(store)
    if not callable(getattr(store, "memory_get", None)):
        raise RuntimeError(
            f"{type(store).__name__} implements the warrants capability but not "
            f"memory_get, which attach() needs to confirm a pair exists before "
            f"warranting it (the curation capability — see "
            f"nestor.storage.supports_curation).")
    refusal = refuse_reason(kind, authority, locator, check, expected_digest)
    if refusal:
        raise ValueError(refusal)
    pair = store.memory_get(pair_id)
    if pair is None:
        raise ValueError(f"no pair {pair_id!r} in this store")

    w = {
        "id": str(uuid.uuid4()), "pair_id": pair_id, "kind": kind,
        "authority": authority, "locator": locator, "check": check,
        "expected_digest": expected_digest, "attached_by": attached_by,
        "created_at": _now(),
    }
    # Refuse before the store write if the trail will not take the entry, so a
    # warrant row can never outlive its ledger line — the rule every other write
    # path here holds. Lazy import for the same reason evidence.py does it.
    from .cascade import _ledger_append, ledger_preflight
    ledger_preflight()
    cast(WarrantStorage, store).memory_add_warrant(w)
    _ledger_append({
        "kind": "attach_warrant", "pair_id": pair_id, "warrant_id": w["id"],
        "warrant_kind": kind, "authority": authority,
        "attached_by": attached_by,
        # Tamper-evidence over the mutable content, exactly as attach_evidence
        # takes. NOT a signature: this records that a warrant was claimed, never
        # that it holds. Nothing here confirms anything.
        "content_sha": _content_sha(kind, authority, locator, check,
                                    expected_digest),
    })
    return w


def _content_sha(kind: str, authority: str, locator: str, check: str,
                 expected_digest: str) -> str:
    """A stable hash of a warrant row's mutable content fields."""
    return hashlib.sha256("\n".join(
        (kind, authority, locator, check, expected_digest)).encode(
            "utf-8")).hexdigest()


def warrants_for(pair_id: str, store: Optional[Storage] = None) -> list[dict]:
    """Every warrant ``pair_id`` holds — the stored rows, plus its seal.

    The seal is composed in as a synthetic ``attestation`` row rather than read
    from the warrants table, because that is where it actually lives. It carries
    the sealing verifier as its ``authority`` and is marked ``stored: False`` so
    a caller can tell a composed warrant from a written one — the export path
    depends on that distinction (a seal travels as a seal, with its signature;
    it must not travel twice).

    Newest first among stored rows, with the attestation last: the list is a
    set, and its order is presentation, never precedence.
    """
    store = get_store(store)
    _require_warrants(store)
    rows = [dict(r, stored=True)
            for r in cast(WarrantStorage, store).memory_warrants_for(pair_id)]
    pair = store.memory_get(pair_id) if callable(
        getattr(store, "memory_get", None)) else None
    if pair and pair.get("status") == "sealed":
        rows.append({
            "id": "", "pair_id": pair_id, "kind": ATTESTATION,
            "authority": pair.get("verifier", ""),
            "locator": "", "check": "",
            "expected_digest": "", "attached_by": "",
            "created_at": pair.get("created_at", ""), "stored": False,
        })
    return rows


def kinds_held(pair_id: str, store: Optional[Storage] = None) -> set[str]:
    """The set of warrant kinds ``pair_id`` holds. A set, deliberately —
    there is no ordering over warrant kinds and no strongest one."""
    return {w["kind"] for w in warrants_for(pair_id, store)}
