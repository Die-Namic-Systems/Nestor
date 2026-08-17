"""Getting the memory out, and getting it back in somewhere else.

``Curator.export`` answers "show me what I have". This answers the harder pair
of questions: **can I leave**, and **can this memory move between instances
without laundering trust on the way?**

Export is easy. Import is the interesting half, because a bundle is a file, and
a file is exactly the thing a seal signature exists to distrust. A row in a JSON
document saying ``"status": "sealed", "verifier": "rita"`` is a claim by whoever
wrote the file — the same claim a forged database row makes, and Nestor already
refuses to serve that. So import applies the identical rule rather than a softer
one:

* A sealed row whose ``seal_sig`` verifies **under the importing instance's own
  key** lands sealed. That is the case the signature was designed for: two
  instances sharing a key can move verified pairs between them and the
  verification survives, because it was never in the row to begin with.
* A sealed row whose signature does not verify lands as a **draft**, in the
  review queue, counted and reported. Nothing is discarded and nothing is
  trusted — a human decides, which is the whole product.
* With signing disabled the importing instance has no key to check against, so
  it is trusting the file's word. That is the same degrade
  ``signing.seal_is_valid`` already makes for stored rows, and it warns here for
  the same reason.

Rejections import unconditionally. Honoring a rejection only ever withholds an
answer, which is the safe direction — the asymmetry ``memory.rejected_ids``
documents, applied to files.

**The ledger does not merge.** A hash chain has one history by construction, and
splicing another instance's entries into it would produce a chain that verifies
while describing events that never happened here. A bundle carries the source
chain for *reading*; the import itself is what gets appended locally.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
import warnings
from datetime import datetime, timezone
from typing import Any, Optional, cast

from . import cascade, ledger as ledger_mod, memory, signing
from .matcher import Matcher, matcher_audit_fields
from .storage import (EvidenceStorage, Storage, get_store, supports_curation,
                      supports_evidence, supports_rejection,
                      supports_rejection_listing)

#: Version 2 carries ``reopen_when`` on rejections. Bumped rather than added
#: silently because the field changes the payload the digest is taken over, and
#: a bundle whose integrity check depends on which build wrote it is not an
#: integrity check.
#: Version 3 carries ``evidence`` (docs/evidence-edge.md). Bumped, not added
#: silently, for the same reason 2 was: evidence joins the payload the digest is
#: taken over, so a bundle's integrity check depends on which build wrote it.
BUNDLE_VERSION = 3

#: All are readable. Writing is always the current version; a version-1 or -2
#: bundle keeps verifying against the fields it was hashed with, so upgrading
#: this build does not invalidate bundles already in circulation.
SUPPORTED_BUNDLE_VERSIONS = (1, 2, 3)

PAIR_FIELDS = ("id", "source_text", "source_norm", "source_lang", "target_text",
               "target_lang", "status", "verifier", "weight", "origin",
               "created_at", "seal_sig")

_REJECTION_FIELDS_V1 = ("id", "query_norm", "source_lang", "target_lang", "pair_id",
                        "target_text", "verifier", "reason", "created_at", "reject_sig")
#: ``reopen_when`` is N5's never-vs-not-yet, and without it a deferral crossed
#: an instance boundary as a permanent refusal — the one distinction the column
#: exists to preserve, lost by the transfer that was supposed to preserve it.
REJECTION_FIELDS = _REJECTION_FIELDS_V1 + ("reopen_when",)

_REJECTION_FIELDS_BY_VERSION = {1: _REJECTION_FIELDS_V1, 2: REJECTION_FIELDS,
                                3: REJECTION_FIELDS}

#: Evidence carried in a version-3+ bundle (docs/evidence-edge.md). No signature
#: field: evidence holds no authority, so unlike a pair there is nothing to
#: verify on import — the row is a reference, re-added as-is.
EVIDENCE_FIELDS = ("id", "pair_id", "kind", "locator", "attaches_to", "reason",
                   "attached_by", "created_at")

#: Rejections get their own default cap, deliberately not `limit`'s. A cap
#: sized for pairs says nothing about how many times those pairs were argued
#: over, and sharing one silently truncated whichever list was longer.
_REJECTION_LIMIT = 1_000_000


class BundleError(ValueError):
    """The bundle is not one, or is not intact."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    """One textual form per value, whatever JSON implementation produced it.

    Hashing ``json.dumps`` of the parsed rows directly was wrong in a way that
    only showed up when a bundle went through a browser: JavaScript has one
    number type, so ``"weight": 1.0`` comes back from ``JSON.parse`` as ``1``
    and re-serializes as ``1``, and the digest of a payload nobody had touched
    no longer matched. An integrity check that fails on a lossless round-trip
    trains people to ignore it, which is worse than not having one.

    So values are compared as text, with integral floats folded to integers —
    the one place JSON implementations legitimately disagree. Every field Nestor
    carries is a string, an id, a status or that single float.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if value is None:
        return ""
    return str(value)


def digest(pairs: list[dict], rejections: list[dict],
           evidence: Optional[list[dict]] = None,
           version: int = BUNDLE_VERSION) -> str:
    """A stable sha256 over the bundle's payload, as ``version`` defines it.

    ``version`` selects the rejection field set, and it is not decoration: a
    version-1 bundle was hashed over rejections with no ``reopen_when``, so
    recomputing it with version 2's fields adds an empty column the original
    digest never saw and reports a mismatch on a file nobody touched. That is
    the same failure ``_canonical`` exists to prevent — an integrity check that
    fails on an untouched payload trains people to ignore it.

    Canonical: rows sorted by id, keys sorted, values reduced to one textual
    form (see :func:`_canonical`). Two exports of the same memory produce the
    same digest, so instances can be compared without diffing 10k rows by eye, a
    truncated transfer is obvious, and a bundle survives a trip through any JSON
    implementation.

    It is **not** a signature. Anyone can recompute it after editing the file —
    that is what ``seal_sig`` is for, and why import checks signatures rather
    than this. It answers "is this the same bundle", never "is this authentic".
    """
    if version not in _REJECTION_FIELDS_BY_VERSION:
        raise BundleError(
            f"cannot digest bundle version {version!r} — this build knows "
            f"{', '.join(str(v) for v in sorted(_REJECTION_FIELDS_BY_VERSION))}. "
            f"A digest computed with the wrong field set is not an integrity check.")

    def rows(raw: list[dict], fields: tuple) -> list[dict]:
        return sorted(({f: _canonical(r.get(f)) for f in fields} for r in raw),
                      key=lambda r: r.get("id", ""))

    payload_dict = {"pairs": rows(pairs, PAIR_FIELDS),
                    "rejections": rows(rejections,
                                       _REJECTION_FIELDS_BY_VERSION[version])}
    # Version-gated so v1/v2 digests are byte-identical to before: a bundle
    # written without evidence must recompute to the same hash, exactly as the
    # reopen_when bump was gated. Only v3+ folds evidence into the payload.
    if version >= 3:
        payload_dict["evidence"] = rows(evidence or [], EVIDENCE_FIELDS)
    payload = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row(raw: dict, fields: tuple) -> dict:
    return {f: raw.get(f, "") for f in fields}


def export_bundle(store: Optional[Storage] = None, source_lang: str = "",
                  target_lang: str = "", include_ledger: bool = True,
                  limit: int = 1_000_000,
                  rejection_limit: Optional[int] = None,
                  matcher: Optional[Matcher] = None) -> dict:
    """The whole memory (or one domain) as a JSON-ready, re-importable bundle.

    Signatures travel with the rows. They are HMACs, not secrets: without the
    key they cannot be recomputed, which is precisely why exporting them is safe
    and why they are worth carrying — they are what lets the destination decide
    whether a seal is real instead of taking the file's word.

    ``limit`` caps pairs. ``rejection_limit`` caps rejections independently and
    does **not** default to ``limit`` — they count different row types, and a
    cap sized for one is meaningless for the other. Hitting either warns, and
    the bundle records ``partial_rejections`` so a JSON caller that never sees a
    warning still knows the file is short.

    ``matcher`` names — for the record only — the matcher that produced every
    ``source_norm`` in this bundle. A domain is its tags **and** its matcher
    (IDEAS §6.40): the ``source_norm`` the seals are signed over is that
    matcher's output, so a destination keying the same tags with a *different*
    matcher lands these rows in a key space it will never compute — sealed,
    signed, and unreachable. The label is written into the envelope (not the
    digest — ``matcher_audit_fields`` is explicitly not a stable identifier, so
    it cannot be an integrity field) so :func:`import_bundle` can warn on a
    mismatch that would otherwise be silent. Defaults to the process matcher.
    """
    store = get_store(store)
    store.memory_init()
    if not supports_curation(store):
        raise BundleError(
            f"{type(store).__name__} cannot list its pairs (see "
            f"storage.supports_curation), so there is nothing to export from it.")
    # Superseded rows are history, not stock: they share their key with the
    # live successor, so importing them would insert straight into a conflict
    # (or resurrect a replaced decision on a store without lineage). The
    # chain of what-replaced-what travels in the ledger (include_ledger),
    # which is where replacement history has always lived.
    #
    # Ask for one more than the cap so "exactly full" is distinguishable from
    # "truncated". `len(rows) >= limit` cannot tell those apart, and a warning
    # that cries wolf on a complete export is the failure `_canonical` names:
    # a check people learn to ignore is worse than no check.
    listed = store.memory_list(source_lang=source_lang, target_lang=target_lang,
                               limit=limit + 1)
    pairs_truncated = len(listed) > limit
    listed = listed[:limit]
    # `demo:`-origin rows never travel. The demo's forged seal (origin
    # `demo:forged`, `seal_sig=""`) would, on import into a store with signing
    # off, be trusted on stored status and served as a verified answer — a demo
    # artifact escaping as a real seal. Excluding it at the source is the simplest
    # guard; the seeded demo store is not a memory anyone should be exporting to
    # begin with, so dropping its other `demo:` rows costs nothing.
    pairs = [_row(p, PAIR_FIELDS) for p in listed
             if not p.get("superseded_by")
             and not str(p.get("origin") or "").startswith("demo:")]
    live_ids = {p["id"] for p in pairs}

    # TWO WALKS, each bounded by construction — not one walk with a filter.
    #
    # The history here is worth keeping, because two successive fixes each
    # introduced the bug the next one had to remove. A pair-keyed walk alone
    # could not see rejections that name no pair (`reject_match` documents
    # pair_id as "" for a candidate that never became one — the common shape for
    # a rejected *alternative*), so signed, ledgered "no"s did not travel.
    # Replacing it with a domain walk fixed that and lost the scope the old walk
    # had for free: it began carrying rejections against SUPERSEDED pairs, whose
    # ids the bundle deliberately omits, and `rejected_ids` matches on pair_id —
    # so importing suppressed a live sealed answer on the destination. Adding an
    # `exported_ids` filter to the domain walk fixed *that* and, combined with a
    # shared pair/rejection cap, produced the worst outcome yet: the pair window
    # is newest-first and the rejection walk oldest-first, so under any cap the
    # two sets were disjoint and NO pair-bound rejection travelled at all.
    #
    # Each of those is a filter interacting with a filter. So: collect the two
    # kinds from the two reads that can each answer completely, and union them.
    # The pair-keyed walk cannot return a rejection whose pair is absent — it
    # iterates the exported pairs — and the domain walk is asked only for the
    # pair-less rows, where no pair can dangle. The invariant "a bundle never
    # references a row it does not carry" then holds by construction rather
    # than by a filter that a later cap can undercut.
    rejections: list[dict] = []
    # Two different absences, two different flags. One shared flag reported
    # "SHORT: the exporter flagged missing rejections" on a bundle that was
    # missing PAIRS and no rejections at all — the field added so a short
    # bundle would say so, misstating which rows were short.
    partial_rejections = False
    if supports_rejection(store):
        cap = _REJECTION_LIMIT if rejection_limit is None else rejection_limit
        by_id: dict[str, dict] = {}
        # (a) pair-bound, from the exported pairs. Complete for this bundle
        #     whatever `limit` was, because its domain IS the exported pairs.
        for p in pairs:
            for r in store.memory_rejections_for_pair(p["id"]):
                if r.get("id") not in by_id:
                    by_id[r["id"]] = r
        # (b) pair-less, from the domain walk. Nothing here can dangle.
        if supports_rejection_listing(store):
            raw = store.memory_list_rejections(source_lang=source_lang,
                                               target_lang=target_lang, limit=cap + 1)
            if len(raw) > cap:
                partial_rejections = True
                warnings.warn(
                    f"export hit its rejection limit ({cap}); recorded 'no's are "
                    f"missing from this bundle. Raise `rejection_limit`.",
                    RuntimeWarning, stacklevel=2)
            for r in raw[:cap]:
                if r.get("id") in by_id:
                    continue
                pid = r.get("pair_id") or ""
                if not pid:
                    by_id[r["id"]] = r
                elif pid not in live_ids:
                    # Names a pair this bundle does not carry — superseded, or
                    # cut by `limit`. Dropping it lost a signed human "no"
                    # outright, and `revise_draft` made superseding routine, so
                    # this went from rare to ordinary. Carry it with the pointer
                    # BLANKED: the target-text suppression survives the trip and
                    # nothing dangles, which is the invariant either way.
                    by_id[r["id"]] = {**r, "pair_id": ""}
        else:
            # Without a domain read the pair-less half is unreachable. The
            # pair-bound half above is still complete; say what is missing.
            partial_rejections = True
            warnings.warn(
                f"{type(store).__name__} cannot list rejections by domain (see "
                f"storage.supports_rejection_listing), so this bundle carries only "
                f"rejections that name a pair_id. Any rejection recorded against a "
                f"raw candidate is NOT in it.", RuntimeWarning, stacklevel=2)
        rejections = [_row(r, REJECTION_FIELDS) for r in by_id.values()]
        rejections.sort(key=lambda r: (r.get("created_at", ""), r.get("id", "")))
    # Evidence for the exported pairs (docs/evidence-edge.md, v3+). Gathered
    # per-pair, so it carries only references whose pair is in this bundle —
    # nothing can dangle, the same by-construction invariant the pair-bound
    # rejection walk keeps.
    evidence: list[dict] = []
    if supports_evidence(store):
        ev_store = cast(EvidenceStorage, store)
        for p in pairs:
            evidence.extend(_row(e, EVIDENCE_FIELDS)
                            for e in ev_store.memory_evidence_for(p["id"]))
        evidence.sort(key=lambda e: (e.get("created_at", ""), e.get("id", "")))
    if pairs_truncated:
        warnings.warn(
            f"export hit its pair limit ({limit}); this bundle is a prefix of the "
            f"memory, not all of it. Raise `limit` to export the rest.",
            RuntimeWarning, stacklevel=2)
    bundle = {
        "nestor_bundle": BUNDLE_VERSION,
        "created_at": _now(),
        "domain": {"source_lang": source_lang or "*", "target_lang": target_lang or "*"},
        # The matcher that keyed these norms, for import to compare against its
        # own. Advisory, and deliberately outside the digest — see the docstring.
        "matcher": matcher_audit_fields(memory.get_matcher(matcher))["matcher"],
        "signing": {"enabled": signing.signing_enabled(), "algorithm": "hmac-sha256"},
        # In the bundle, not only in a warning. Python dedupes warnings by code
        # location, so a long-lived exporter (nestor.ui serves bundles from a
        # thread pool) warns on the first short export and stays silent for
        # every one after — and an HTTP caller reading JSON never sees a
        # warning at all. A bundle that is missing rows must say so in the
        # bundle, which is the only thing the destination actually reads.
        "partial_pairs": pairs_truncated,
        "partial_rejections": partial_rejections,
        "counts": {
            "pairs": len(pairs),
            "sealed": sum(1 for p in pairs if p["status"] == "sealed"),
            "servable": sum(1 for p in pairs if memory.is_verified_seal(p)),
            "rejections": len(rejections),
            "evidence": len(evidence),
        },
        "digest": digest(pairs, rejections, evidence, version=BUNDLE_VERSION),
        "pairs": pairs,
        "rejections": rejections,
        "evidence": evidence,
    }
    if include_ledger:
        # Carried for reading, never for splicing — see the module docstring.
        bundle["ledger"] = {
            "note": "the source instance's chain, for audit; it is not merged on import",
            "entries": ledger_mod.entries(limit=100_000),
            # The lines the chain holds that would not parse — carried because
            # without them the bundle is a shorter chain than the one on disk
            # with nothing marking where the difference is, and the reader of a
            # bundle is the one party who cannot go and look at the file.
            "unreadable": ledger_mod.unreadable(),
        }
    return bundle


def verify_bundle(bundle: Any) -> tuple[bool, str]:
    """Is this a bundle, and is it the one that was exported? ``(ok, detail)``."""
    if not isinstance(bundle, dict):
        return False, "not a JSON object"
    version = bundle.get("nestor_bundle")
    # `in` alone accepts True as version 1 — bool is an int, so `True in (1, 2)`
    # is True — and a boolean is not a version. An integral FLOAT is, though:
    # `_canonical` in this same file exists because a bundle through a browser
    # comes back with 1.0 where 1 went in, and its rule is that an integrity
    # check failing on a lossless round trip is worse than none. Refusing 2.0
    # while accepting `weight: 2.0` would apply that rule in one place and
    # contradict it in another.
    if isinstance(version, bool) or not isinstance(version, (int, float)) \
            or float(version) != int(version) \
            or int(version) not in SUPPORTED_BUNDLE_VERSIONS:
        return False, (f"unsupported bundle version {version!r} (this build reads "
                       f"{', '.join(str(v) for v in SUPPORTED_BUNDLE_VERSIONS)} "
                       f"and writes {BUNDLE_VERSION})")
    version = int(version)
    pairs, rejections = bundle.get("pairs"), bundle.get("rejections", [])
    evidence = bundle.get("evidence", [])
    if not isinstance(pairs, list) or not isinstance(rejections, list) \
            or not isinstance(evidence, list):
        return False, "'pairs', 'rejections' and 'evidence' must be lists"
    for row in pairs:
        missing = [f for f in ("id", "source_norm", "source_lang", "target_lang",
                               "target_text", "status") if f not in row]
        if missing:
            return False, f"pair {row.get('id', '?')} is missing {', '.join(missing)}"
    want = bundle.get("digest")
    got = digest(pairs, rejections, evidence, version=version)
    if want and want != got:
        return False, (f"digest mismatch: the payload is not the one exported "
                       f"(expected {want[:16]}…, computed {got[:16]}…)")
    missing = [w for w, f in (("pairs", "partial_pairs"),
                              ("rejections", "partial_rejections"))
               if bundle.get(f)]
    short = f" — SHORT: the exporter flagged missing {' and '.join(missing)}" \
        if missing else ""
    ev_note = f", {len(evidence)} evidence row(s)" if version >= 3 else ""
    return True, (f"{len(pairs)} pair(s), {len(rejections)} rejection(s)"
                  f"{ev_note}, digest {got[:16]}…{short}")


class _PairDisposition:
    """What an incoming pair does against the local row keyed the same way.

    ``report_key``/``entry`` name the report update the caller must apply —
    ``"existing"`` bumps a counter, any other key appends ``entry`` to that
    report list, ``None`` means no report update from this call. ``skip``
    tells the loop whether to move to the next pair without importing this
    one.
    """

    __slots__ = ("report_key", "entry", "skip")

    def __init__(self, report_key: Optional[str], entry: Any, skip: bool) -> None:
        self.report_key = report_key
        self.entry = entry
        self.skip = skip


def _resolve_incoming_pair(existing: dict, row: dict, override_conflicts: bool,
                           override_rejections: bool) -> _PairDisposition:
    """Compare an incoming pair to the local row already keyed the same source/langs.

    Called only when a local row exists for this ``(source_norm, source_lang,
    target_lang)``. Returns the disposition to report, plus whether the pair
    is settled here (``skip=True``) or should continue on to the seal/draft
    classification below — a brand-new pair falling through unchanged, an
    override taking the incoming answer, or a local draft being upgraded by a
    verified incoming seal.
    """
    if existing["status"] == "rejected":
        # A pair a human here rejected is not a disagreement for the import to
        # settle. `override_conflicts` must not reach it: that flag means
        # "their answer wins where we disagree", and a rejection is not a
        # competing answer, it is a decision that this mapping is wrong.
        # Overwriting it would resurrect exactly what rejection exists to
        # retire — the same leak `add_pair` raises RejectedPairError for,
        # arriving through a file instead. The deliberate way back is
        # Curator.restore, or this second, separate flag, mirroring
        # add_pair's two.
        entry = {
            "source_text": row["source_text"],
            "source_lang": row["source_lang"], "target_lang": row["target_lang"],
            "rejected_by": existing.get("verifier", ""),
            "incoming": {"target_text": row["target_text"],
                         "status": row["status"],
                         "verifier": row.get("verifier", "")},
        }
        return _PairDisposition("rejected_here", entry, not override_rejections)

    if existing["target_text"] == row["target_text"]:
        # Same answer on both sides — but not necessarily the same standing. A
        # sealed, signature-verified row arriving over a local *draft* is a
        # verification this instance does not have, and reporting it as
        # "already present" threw away the one thing the bundle was carrying.
        # Upgrade instead; anything else here genuinely is a no-op.
        if (existing["status"] != "sealed" and row["status"] == "sealed"
                and signing.seal_is_valid(row["source_norm"], row["target_text"],
                                          row.get("verifier", ""), row.get("seal_sig", ""))):
            return _PairDisposition(None, None, False)
        return _PairDisposition("existing", None, True)

    entry = {
        "source_text": row["source_text"],
        "source_lang": row["source_lang"], "target_lang": row["target_lang"],
        "here": {"target_text": existing["target_text"],
                 "status": existing["status"],
                 "verifier": existing.get("verifier", "")},
        "incoming": {"target_text": row["target_text"],
                     "status": row["status"],
                     "verifier": row.get("verifier", "")},
    }
    return _PairDisposition("conflicts", entry, not override_conflicts)


def _classify_seal_claim(row: dict) -> tuple[bool, bool]:
    """Does this incoming row claim to be sealed, and does that seal verify here?

    The load-bearing check: a seal is honored only if it verifies HERE.
    ``seal_is_valid`` returns True when signing is off, which is the same
    trust-the-stored-status degrade the rest of the package makes.
    """
    claims_sealed = row["status"] == "sealed"
    verifies = claims_sealed and signing.seal_is_valid(
        row["source_norm"], row["target_text"], row.get("verifier", ""),
        row.get("seal_sig", ""))
    return claims_sealed, verifies


def _write_incoming_pair(store: Storage, existing: Optional[dict], row: dict,
                         claims_sealed: bool, verifies: bool) -> str:
    """Commit one incoming pair to the store. Returns the id to record in id_map.

    Called only when not a dry run.
    """
    incoming = dict(row)
    incoming["id"] = existing["id"] if existing else (row.get("id") or str(uuid.uuid4()))
    if claims_sealed and not verifies:
        # Demoted, and its signature dropped with it: a draft row carrying a
        # live-looking signature is a seal waiting to be reactivated by
        # anything that flips the status column back (the same reason
        # memory_unseal clears it).
        incoming["status"] = "draft"
        incoming["seal_sig"] = ""
        incoming["origin"] = (f"imported-unverifiable:{row.get('verifier') or '?'}")[:200]
    if existing:
        store.memory_seal(existing["id"], incoming["target_text"],
                          incoming.get("verifier", ""),
                          float(incoming.get("weight") or 1.0),
                          incoming.get("seal_sig", ""))
    else:
        store.memory_insert(incoming)
    return incoming["id"]


def _import_rejections(store: Storage, bundle: dict, id_map: dict, dry_run: bool,
                       report: dict) -> None:
    """Import the bundle's rejections. Unconditional: honoring a rejection only
    ever withholds an answer, which is the safe direction (see module docstring).
    """
    if not supports_rejection(store):
        return
    for raw in bundle.get("rejections", []):
        named = raw.get("pair_id") or ""
        if named and named not in id_map:
            # A rejection naming a pair this bundle does not carry. Export
            # cannot produce one, but a hand-edited bundle, a third-party one,
            # or one written by an earlier build can — and honouring it is
            # exactly the documented harm: on a destination still holding that
            # id live, it suppresses a sealed, signature-verified answer. The
            # export-side invariant is only half an invariant if the read side
            # takes the file's word, which is the mistake the seal signature
            # exists to refuse.
            report["dangling_rejections"].append(named)
            continue
        report["rejections"] += 1
        if not dry_run:
            # The bundle's OWN version, not this build's. A version-1 bundle
            # was hashed over version-1 fields, so reading it with version-2
            # fields lets a key the digest never covered — `reopen_when`,
            # which decides never-vs-not-yet — be added to the file after
            # export, verify cleanly, and land in the store. The digest is
            # explicitly not a signature, so this is hygiene rather than an
            # auth break; but a check that covers less than the importer
            # consumes is the wrong way round, and version plumbing that stops
            # short of the read is not plumbing.
            rejection = _row(raw, _REJECTION_FIELDS_BY_VERSION[
                bundle.get("nestor_bundle", BUNDLE_VERSION)])
            rejection["id"] = rejection.get("id") or str(uuid.uuid4())
            if named:
                rejection["pair_id"] = id_map[named]
            try:
                store.memory_add_rejection(rejection)
            except Exception:                  # noqa: BLE001 — a duplicate id is not a failure
                report["rejections"] -= 1


def _import_evidence(store: Storage, bundle: dict, id_map: dict, dry_run: bool,
                     report: dict) -> None:
    """Import the bundle's evidence rows, dropping any referencing a pair id the
    bundle doesn't carry.
    """
    if not supports_evidence(store):
        return
    ev_store = cast(EvidenceStorage, store)
    for raw in bundle.get("evidence", []):
        named = raw.get("pair_id") or ""
        if named and named not in id_map:
            # A reference naming a pair this bundle does not carry. Export
            # cannot make one (evidence is gathered per exported pair), but a
            # hand-edited or third-party bundle can — and adding it would
            # leave a reference pointing at nothing here. Evidence confers no
            # authority, so this is not the security hazard a dangling
            # rejection is; it is dropped for the same tidiness reason.
            report["dangling_evidence"].append(named)
            continue
        report["evidence"] += 1
        if not dry_run:
            ev = _row(raw, EVIDENCE_FIELDS)
            ev["id"] = ev.get("id") or str(uuid.uuid4())
            if named:
                ev["pair_id"] = id_map[named]
            try:
                ev_store.memory_add_evidence(ev)
            except Exception:                  # noqa: BLE001 — a duplicate id is not a failure
                report["evidence"] -= 1


def import_bundle(bundle: Any, store: Optional[Storage] = None, dry_run: bool = True,
                  verifier: str = "", override_conflicts: bool = False,
                  override_rejections: bool = False,
                  matcher: Optional[Matcher] = None) -> dict:
    """Bring a bundle into this instance. Reports first, writes only if told to.

    ``dry_run=True`` is the default deliberately: an import decides what this
    instance will serve as human-verified, and every other decision of that
    weight in Nestor takes two steps. Run it once to read the report, once more
    with ``dry_run=False`` to commit.

    Returns a report::

        {"sealed": n,        # signature verified here — imported as sealed
         "demoted": n,       # claimed sealed, would not verify — imported as draft
         "drafts": n,        # already drafts in the bundle
         "existing": n,      # same source, same target — nothing to do
         "conflicts": [...], # same source, DIFFERENT target — skipped, listed
         "rejected_here": [...],  # a human here rejected this pair — skipped, listed
         "matcher_mismatch": bool,  # bundle keyed by a different matcher than this instance
         "source_matcher": "...", "dest_matcher": "...",  # the two labels compared
         "rejections": n, "dry_run": bool, "digest": "..."}

    Conflicts are never resolved silently. A bundle asserting a different target
    for a source this instance has already sealed is two humans disagreeing
    through a file, which is exactly the case ``ConflictingSealError`` exists to
    stop; they are listed for a person, and ``override_conflicts=True`` is the
    deliberate way to take the incoming answer.

    A pair **rejected here** is stronger than a disagreement and gets its own
    flag. ``override_conflicts`` deliberately cannot reach it — mirroring
    ``add_pair``, where ``override_conflict`` and ``override_rejection`` are two
    switches precisely because "their answer wins" and "revive the mapping a
    human called wrong" are not the same decision.

    ``matcher`` names the matcher this instance keys with, to check against the
    ``matcher`` label the bundle carries (see :func:`export_bundle`). A mismatch
    is **warned, never refused** — the label is not a stable identifier, so it
    cannot bear a refusal, and the rows still import correctly under a shared
    matcher. But a bundle keyed by one matcher landing in a domain keyed by
    another is IDEAS §6.40 arriving through a file: the ``source_norm`` a seal is
    signed over is the *source's* matcher's output, so the destination will key
    the same tags into a space it never computes and serve nothing. The warning
    also rides in the report (``matcher_mismatch``, ``source_matcher``,
    ``dest_matcher``) because Python dedupes warnings by code location and an
    HTTP caller reading JSON never sees one — the same reason ``partial_pairs``
    is a field and not only a warning. Defaults to the process matcher.
    """
    store = get_store(store)
    ok, detail = verify_bundle(bundle)
    if not ok:
        raise BundleError(detail)
    store.memory_init()

    # Advisory, before the row loop: a whole-bundle property, not a per-row one.
    # ``source_matcher`` is "" for a bundle written before this field existed —
    # not a mismatch, just unknown, so a legacy bundle imports without a false
    # alarm. Only two named-and-different labels warn.
    dest_matcher = matcher_audit_fields(memory.get_matcher(matcher))["matcher"]
    source_matcher = str(bundle.get("matcher") or "")
    matcher_mismatch = bool(source_matcher and source_matcher != dest_matcher)
    if matcher_mismatch:
        warnings.warn(
            f"this bundle was keyed by {source_matcher!r} and this instance keys "
            f"by {dest_matcher!r}. A seal's source_norm is the source matcher's "
            f"output, so rows imported here may key into a space this matcher "
            f"never computes and serve nothing — even though the import reports "
            f"success. Import under the matcher that keyed the bundle, or expect "
            f"to re-key. (The label is advisory; matchers that agree but were "
            f"renamed will also trip this.)",
            RuntimeWarning, stacklevel=2)

    signing_on = signing.signing_enabled()
    report: dict[str, Any] = {"sealed": 0, "demoted": 0, "drafts": 0, "existing": 0,
                              "conflicts": [], "rejected_here": [], "rejections": 0,
                              "dangling_rejections": [],
                              "evidence": 0, "dangling_evidence": [],
                              "partial_source": bool(bundle.get("partial_rejections")
                                                     or bundle.get("partial_pairs")),
                              "source_matcher": source_matcher,
                              "dest_matcher": dest_matcher,
                              "matcher_mismatch": matcher_mismatch,
                              "dry_run": dry_run, "digest": bundle.get("digest", ""),
                              "signing_enabled": signing_on}
    #: source pair id -> the id it is stored under HERE. See the rejection loop.
    id_map: dict[str, str] = {}

    for raw in bundle["pairs"]:
        row = _row(raw, PAIR_FIELDS)
        existing = store.memory_find(row["source_norm"], row["source_lang"],
                                     row["target_lang"])
        # Mapped HERE, before any branch, because four of them `continue`:
        # already-present, rejected-here, conflict, and dry run. A rejection
        # names its pair by the SOURCE's id while this import may store that
        # pair under the destination's, so without the map the rejection lands
        # pointing at an id that does not exist here — suppressing nothing, and
        # dropped by the destination's own next export. The signed "no" survives
        # one hop and dies on the second. The no-op branch is the one that
        # caught this: nothing is written, so it is the easiest to forget, and
        # it is the commonest case in a real re-import.
        id_map[row.get("id") or ""] = (existing["id"] if existing
                                       else row.get("id") or "")

        if existing:
            disposition = _resolve_incoming_pair(existing, row, override_conflicts,
                                                 override_rejections)
            if disposition.report_key == "existing":
                report["existing"] += 1
            elif disposition.report_key is not None:
                report[disposition.report_key].append(disposition.entry)
            if disposition.skip:
                continue

        claims_sealed, verifies = _classify_seal_claim(row)
        if claims_sealed and verifies:
            report["sealed"] += 1
        elif claims_sealed:
            report["demoted"] += 1
        else:
            report["drafts"] += 1

        if dry_run:
            continue
        id_map[row.get("id") or ""] = _write_incoming_pair(store, existing, row,
                                                            claims_sealed, verifies)

    _import_rejections(store, bundle, id_map, dry_run, report)
    _import_evidence(store, bundle, id_map, dry_run, report)

    if not dry_run:
        cascade._ledger_append({
            "kind": "bundle_import", "digest": report["digest"],
            "verifier": verifier, "sealed": report["sealed"],
            "demoted": report["demoted"], "drafts": report["drafts"],
            "existing": report["existing"], "conflicts": len(report["conflicts"]),
            "rejections": report["rejections"], "evidence": report["evidence"],
            "source_created_at": bundle.get("created_at", ""),
        })
        if report["rejected_here"] and not override_rejections:
            warnings.warn(
                f"{len(report['rejected_here'])} pair(s) in this bundle were "
                f"rejected on this instance and were NOT imported. Restore them "
                f"deliberately (Curator.restore) if that rejection no longer "
                f"stands.", RuntimeWarning, stacklevel=2)
        if report["demoted"]:
            warnings.warn(
                f"{report['demoted']} pair(s) claimed 'sealed' but their signatures "
                f"do not verify here; they were imported as drafts for review. "
                f"Curator.list(status='draft') shows them.", RuntimeWarning, stacklevel=2)
        if not signing_on and report["sealed"]:
            warnings.warn(
                f"NESTOR_SEAL_KEY is not set, so {report['sealed']} imported seal(s) "
                f"were trusted on the bundle's word alone. Set a key on both "
                f"instances to make an import verifiable.", RuntimeWarning, stacklevel=2)
    return report


def pairs_csv(bundle: dict) -> str:
    """The pairs as CSV, for the spreadsheet a compliance reviewer will ask for.

    Lossy on purpose — it drops signatures, so a CSV round-trip cannot carry a
    verifiable seal. Use the JSON bundle to move a memory; use this to read one.
    """
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=[f for f in PAIR_FIELDS if f != "seal_sig"]
                            + ["servable"], extrasaction="ignore")
    writer.writeheader()
    for p in bundle.get("pairs", []):
        writer.writerow({**p, "servable": memory.is_verified_seal(p)})
    return out.getvalue()
