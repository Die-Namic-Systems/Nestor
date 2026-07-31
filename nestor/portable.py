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
from typing import Any, Optional

from . import cascade, ledger as ledger_mod, memory, signing
from .storage import Storage, get_store, supports_curation, supports_rejection

BUNDLE_VERSION = 1

PAIR_FIELDS = ("id", "source_text", "source_norm", "source_lang", "target_text",
               "target_lang", "status", "verifier", "weight", "origin",
               "created_at", "seal_sig")
REJECTION_FIELDS = ("id", "query_norm", "source_lang", "target_lang", "pair_id",
                    "target_text", "verifier", "reason", "created_at", "reject_sig")


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


def digest(pairs: list[dict], rejections: list[dict]) -> str:
    """A stable sha256 over the bundle's payload.

    Canonical: rows sorted by id, keys sorted, values reduced to one textual
    form (see :func:`_canonical`). Two exports of the same memory produce the
    same digest, so instances can be compared without diffing 10k rows by eye, a
    truncated transfer is obvious, and a bundle survives a trip through any JSON
    implementation.

    It is **not** a signature. Anyone can recompute it after editing the file —
    that is what ``seal_sig`` is for, and why import checks signatures rather
    than this. It answers "is this the same bundle", never "is this authentic".
    """
    def rows(raw: list[dict], fields: tuple) -> list[dict]:
        return sorted(({f: _canonical(r.get(f)) for f in fields} for r in raw),
                      key=lambda r: r.get("id", ""))

    payload = json.dumps(
        {"pairs": rows(pairs, PAIR_FIELDS),
         "rejections": rows(rejections, REJECTION_FIELDS)},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row(raw: dict, fields: tuple) -> dict:
    return {f: raw.get(f, "") for f in fields}


def export_bundle(store: Optional[Storage] = None, source_lang: str = "",
                  target_lang: str = "", include_ledger: bool = True,
                  limit: int = 1_000_000) -> dict:
    """The whole memory (or one domain) as a JSON-ready, re-importable bundle.

    Signatures travel with the rows. They are HMACs, not secrets: without the
    key they cannot be recomputed, which is precisely why exporting them is safe
    and why they are worth carrying — they are what lets the destination decide
    whether a seal is real instead of taking the file's word.
    """
    store = get_store(store)
    store.memory_init()
    if not supports_curation(store):
        raise BundleError(
            f"{type(store).__name__} cannot list its pairs (see "
            f"storage.supports_curation), so there is nothing to export from it.")
    pairs = [_row(p, PAIR_FIELDS) for p in store.memory_list(
        source_lang=source_lang, target_lang=target_lang, limit=limit)]
    rejections: list[dict] = []
    if supports_rejection(store):
        seen = set()
        for p in pairs:
            for r in store.memory_rejections_for_pair(p["id"]):
                if r.get("id") not in seen:
                    seen.add(r.get("id"))
                    rejections.append(_row(r, REJECTION_FIELDS))
    bundle = {
        "nestor_bundle": BUNDLE_VERSION,
        "created_at": _now(),
        "domain": {"source_lang": source_lang or "*", "target_lang": target_lang or "*"},
        "signing": {"enabled": signing.signing_enabled(), "algorithm": "hmac-sha256"},
        "counts": {
            "pairs": len(pairs),
            "sealed": sum(1 for p in pairs if p["status"] == "sealed"),
            "servable": sum(1 for p in pairs if memory.is_verified_seal(p)),
            "rejections": len(rejections),
        },
        "digest": digest(pairs, rejections),
        "pairs": pairs,
        "rejections": rejections,
    }
    if include_ledger:
        # Carried for reading, never for splicing — see the module docstring.
        bundle["ledger"] = {
            "note": "the source instance's chain, for audit; it is not merged on import",
            "entries": ledger_mod.entries(limit=100_000),
        }
    return bundle


def verify_bundle(bundle: Any) -> tuple[bool, str]:
    """Is this a bundle, and is it the one that was exported? ``(ok, detail)``."""
    if not isinstance(bundle, dict):
        return False, "not a JSON object"
    version = bundle.get("nestor_bundle")
    if version != BUNDLE_VERSION:
        return False, (f"unsupported bundle version {version!r} "
                       f"(this build reads version {BUNDLE_VERSION})")
    pairs, rejections = bundle.get("pairs"), bundle.get("rejections", [])
    if not isinstance(pairs, list) or not isinstance(rejections, list):
        return False, "'pairs' and 'rejections' must be lists"
    for row in pairs:
        missing = [f for f in ("id", "source_norm", "source_lang", "target_lang",
                               "target_text", "status") if f not in row]
        if missing:
            return False, f"pair {row.get('id', '?')} is missing {', '.join(missing)}"
    want = bundle.get("digest")
    got = digest(pairs, rejections)
    if want and want != got:
        return False, (f"digest mismatch: the payload is not the one exported "
                       f"(expected {want[:16]}…, computed {got[:16]}…)")
    return True, (f"{len(pairs)} pair(s), {len(rejections)} rejection(s), "
                  f"digest {got[:16]}…")


def import_bundle(bundle: Any, store: Optional[Storage] = None, dry_run: bool = True,
                  verifier: str = "", override_conflicts: bool = False) -> dict:
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
         "rejections": n, "dry_run": bool, "digest": "..."}

    Conflicts are never resolved silently. A bundle asserting a different target
    for a source this instance has already sealed is two humans disagreeing
    through a file, which is exactly the case ``ConflictingSealError`` exists to
    stop; they are listed for a person, and ``override_conflicts=True`` is the
    deliberate way to take the incoming answer.
    """
    store = get_store(store)
    ok, detail = verify_bundle(bundle)
    if not ok:
        raise BundleError(detail)
    store.memory_init()

    signing_on = signing.signing_enabled()
    report: dict[str, Any] = {"sealed": 0, "demoted": 0, "drafts": 0, "existing": 0,
                              "conflicts": [], "rejections": 0, "dry_run": dry_run,
                              "digest": bundle.get("digest", ""),
                              "signing_enabled": signing_on}

    for raw in bundle["pairs"]:
        row = _row(raw, PAIR_FIELDS)
        existing = store.memory_find(row["source_norm"], row["source_lang"],
                                     row["target_lang"])
        if existing:
            if existing["target_text"] == row["target_text"]:
                report["existing"] += 1
                continue
            report["conflicts"].append({
                "source_text": row["source_text"],
                "source_lang": row["source_lang"], "target_lang": row["target_lang"],
                "here": {"target_text": existing["target_text"],
                         "status": existing["status"],
                         "verifier": existing.get("verifier", "")},
                "incoming": {"target_text": row["target_text"],
                             "status": row["status"],
                             "verifier": row.get("verifier", "")},
            })
            if not override_conflicts:
                continue

        claims_sealed = row["status"] == "sealed"
        # The load-bearing line: a seal is honored only if it verifies HERE.
        # `seal_is_valid` returns True when signing is off, which is the same
        # trust-the-stored-status degrade the rest of the package makes.
        verifies = claims_sealed and signing.seal_is_valid(
            row["source_norm"], row["target_text"], row.get("verifier", ""),
            row.get("seal_sig", ""))
        if claims_sealed and verifies:
            report["sealed"] += 1
        elif claims_sealed:
            report["demoted"] += 1
        else:
            report["drafts"] += 1

        if dry_run:
            continue
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

    if supports_rejection(store):
        for raw in bundle.get("rejections", []):
            report["rejections"] += 1
            if not dry_run:
                rejection = _row(raw, REJECTION_FIELDS)
                rejection["id"] = rejection.get("id") or str(uuid.uuid4())
                try:
                    store.memory_add_rejection(rejection)
                except Exception:                  # noqa: BLE001 — a duplicate id is not a failure
                    report["rejections"] -= 1

    if not dry_run:
        cascade._ledger_append({
            "kind": "bundle_import", "digest": report["digest"],
            "verifier": verifier, "sealed": report["sealed"],
            "demoted": report["demoted"], "drafts": report["drafts"],
            "existing": report["existing"], "conflicts": len(report["conflicts"]),
            "rejections": report["rejections"],
            "source_created_at": bundle.get("created_at", ""),
        })
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
