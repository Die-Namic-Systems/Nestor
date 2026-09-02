"""Established-knowledge recognition — lexicon first, then Jeles.

Recognition is a pure lookup: it returns a hit dict or ``None`` and never
touches the store. The writer lives in :func:`ensure_established_draft`,
which composes recognition with the store side-effects (draft row + evidence
+ citation warrant) that make the recognized fact durable and reviewable.

Neither path ever seals — decision 0205 fixed that at the cascade seam
(a recognizer returning ``state="sealed"`` is refused by
``nestor.cascade._run_tier15_recognizer``), and decision 0206 preserves
it here at the writer's boundary as well (``ensure_established_draft`` only
ever writes ``status="draft"``).
"""
from __future__ import annotations

from typing import Any

from .. import evidence, memory, warrant
from ..matcher import Matcher, StringMatcher
from ..storage import Storage, get_store

#: (source_lang, target_lang, source_norm) → record. Keying on ``source_norm``
#: (not the raw source text) lets the lexicon and the domain matcher share one
#: keyspace, so ``Room 42`` under (number, meaning) does NOT hit the ``42``
#: entry — the normalization has to agree with the operator's own key.
Lexicon = dict[tuple[str, str, str], dict[str, Any]]

DEFAULT_LEXICON: Lexicon = {
    ("number", "meaning", "42"): {
        "target_text": (
            "the answer to life, the universe, and everything "
            "(Hitchhiker's Guide)"
        ),
        "authority": "cultural:hitchhiker",
        "locator": (
            "https://en.wikipedia.org/wiki/Phrases_from_The_Hitchhiker%27s_"
            "Guide_to_the_Galaxy#Answer_to_the_Ultimate_Question_of_Life,"
            "_the_Universe,_and_Everything_(42)"
        ),
        "check": "Confirm the association is the well-known Adams reference.",
        "confidence": 1.0,
    },
    ("math", "value", "pi"): {
        "target_text": "approximately 3.141592653589793 (the ratio of a circle's circumference to its diameter)",
        "authority": "math:constants",
        "locator": "https://en.wikipedia.org/wiki/Pi",
        "check": "Universal mathematical constant; commonly rounded to 3.14.",
        "confidence": 1.0,
    },
    ("math", "value", "314"): {
        "target_text": "a common decimal approximation of π (pi), the circle constant",
        "authority": "math:constants",
        "locator": "https://en.wikipedia.org/wiki/Pi",
        "check": "Rounded form of pi — StringMatcher normalizes '3.14' to '314'.",
        "confidence": 1.0,
    },
    ("physics", "law", "newton first law"): {
        "target_text": (
            "An object remains at rest or in uniform motion in a straight line "
            "unless acted upon by a net external force (law of inertia)."
        ),
        "authority": "physics:newton",
        "locator": "https://en.wikipedia.org/wiki/Newton%27s_laws_of_motion",
        "check": "First of Newton's three laws of motion (1687, Principia).",
        "confidence": 1.0,
    },
    ("physics", "law", "newton second law"): {
        "target_text": "The net force on an object equals its mass times its acceleration (F = ma).",
        "authority": "physics:newton",
        "locator": "https://en.wikipedia.org/wiki/Newton%27s_laws_of_motion",
        "check": "Second of Newton's three laws of motion.",
        "confidence": 1.0,
    },
    ("physics", "law", "newton third law"): {
        "target_text": (
            "For every action there is an equal and opposite reaction — "
            "forces always occur in interacting pairs."
        ),
        "authority": "physics:newton",
        "locator": "https://en.wikipedia.org/wiki/Newton%27s_laws_of_motion",
        "check": "Third of Newton's three laws of motion.",
        "confidence": 1.0,
    },
    ("physics", "constant", "speed of light"): {
        "target_text": "299,792,458 meters per second in vacuum (exact by SI definition since 1983)",
        "authority": "physics:si",
        "locator": "https://en.wikipedia.org/wiki/Speed_of_light",
        "check": "Fundamental physical constant.",
        "confidence": 1.0,
    },
    ("physics", "constant", "c"): {
        "target_text": "the speed of light in vacuum: 299,792,458 m/s",
        "authority": "physics:si",
        "locator": "https://en.wikipedia.org/wiki/Speed_of_light",
        "check": "Standard symbol for the speed of light.",
        "confidence": 1.0,
    },
    ("http", "desc", "404"): {
        "target_text": "not found",
        "authority": "iana:http-status",
        "locator": (
            "https://www.iana.org/assignments/http-status-codes/"
            "http-status-codes.xhtml"
        ),
        "check": "IANA HTTP status code registry.",
        "confidence": 1.0,
    },
    ("geo", "desc", "paris"): {
        "target_text": "capital of France",
        "authority": "cultural:geography",
        "locator": "https://en.wikipedia.org/wiki/Paris",
        "check": "Common-knowledge capital city.",
        "confidence": 1.0,
    },
    ("entity", "entity", "big blue"): {
        "target_text": "IBM",
        "authority": "cultural:nickname",
        "locator": "https://en.wikipedia.org/wiki/IBM",
        "check": "Long-standing corporate nickname.",
        "confidence": 1.0,
    },
}


def recognize_lexicon(
    source_text: str,
    source_lang: str,
    target_lang: str,
    *,
    matcher: Matcher | None = None,
    lexicon: Lexicon | None = None,
) -> dict[str, Any] | None:
    """Exact-norm lookup in the established lexicon. Never fuzzy.

    Returns a hit dict shaped like ``{"target_text", "authority", "locator",
    "check", "confidence", "rung": "established", "provider": "lexicon", ...}``
    or ``None`` if the (source_lang, target_lang, normalized-source) key is
    not in the lexicon. Empty norms (which
    :class:`~nestor.memory.EmptyNormError` refuses to seal anyway) return
    ``None`` — a lexicon with an empty-norm key would collide the same way.
    """
    m = matcher or StringMatcher()
    lex = lexicon if lexicon is not None else DEFAULT_LEXICON
    norm = m.normalize(source_text)
    if not norm:
        return None
    rec = lex.get((source_lang, target_lang, norm))
    if not rec:
        return None
    return {
        "source_text": source_text,
        "source_norm": norm,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "target_text": rec["target_text"],
        "authority": rec["authority"],
        "locator": rec["locator"],
        "check": rec.get("check", ""),
        "confidence": float(rec.get("confidence", 1.0)),
        "rung": "established",
        "provider": "lexicon",
    }


def recognize(
    source_text: str,
    source_lang: str,
    target_lang: str,
    *,
    matcher: Matcher | None = None,
    lexicon: Lexicon | None = None,
    use_jeles: bool = True,
    include_asserted: bool = False,
    jeles_require_exact: bool = False,
) -> dict[str, Any] | None:
    """Lexicon first, then Jeles. Never seals; never writes.

    The lexicon is exact-norm and cheap; consulting it first means a
    corpus round-trip only happens on a miss. ``use_jeles=False`` skips
    the corpus lookup entirely (useful in tests and in deployments that
    do not have jeles installed). ``include_asserted=False`` (the default)
    refuses Jeles nuggets whose ``verification_kind`` is ``asserted`` —
    asserted means an unchecked write, and serving it as an established
    draft would collapse the whole distinction the rung system draws.
    """
    hit = recognize_lexicon(
        source_text, source_lang, target_lang, matcher=matcher, lexicon=lexicon
    )
    if hit is not None:
        return hit
    if not use_jeles:
        return None
    # Lazy import: jeles is an optional dependency; the core module tree
    # does not hard-depend on it, so `from nestor.established import
    # recognize_lexicon` works without jeles installed.
    from .jeles_bridge import recognize_from_jeles

    return recognize_from_jeles(
        source_text,
        source_lang,
        target_lang,
        include_asserted=include_asserted,
        require_exact=jeles_require_exact,
    )


def _is_rejected(
    source_norm: str,
    source_lang: str,
    target_lang: str,
    store: Storage,
) -> bool:
    """Has any pair with this norm been rejected in this domain?

    Checks the store's ``memory_list_rejections`` surface where available
    (per-store capability), and falls back to a direct read of the
    ``tm_pairs`` row's rejected status for stores that expose ``db_path``
    (the reference SqliteStore). A store that offers neither is treated as
    "no rejections here" — the caller's downstream ``ensure_established_draft``
    still refuses to seal, which is the actual danger the check exists to
    prevent.
    """
    if memory.supports_rejection(store):
        pair_ids, _targets = memory.rejected_ids(
            source_norm, source_lang, target_lang, store
        )
        if pair_ids:
            return True

    db_path = getattr(store, "db_path", None)
    if db_path and db_path != ":memory:":
        import sqlite3

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT 1 FROM tm_pairs
                WHERE source_norm = ? AND source_lang = ? AND target_lang = ?
                  AND status = 'rejected'
                LIMIT 1
                """,
                (source_norm, source_lang, target_lang),
            ).fetchone()
        finally:
            conn.close()
        if row:
            return True
    return False


def _find_existing_pair(
    source_norm: str, source_lang: str, target_lang: str, store: Storage
) -> dict[str, Any] | None:
    """The current live pair for this domain key, if any.

    Used to make ``ensure_established_draft`` idempotent: a second call with
    the same source_norm reuses the existing draft rather than raising
    ``ConflictingSealError``. Prefers ``sealed`` over ``draft`` in the
    unlikely case that both exist (which would already be a bug the
    rest of the memory layer catches).
    """
    db_path = getattr(store, "db_path", None)
    if not db_path or db_path == ":memory:":
        return None
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, status, target_text FROM tm_pairs
            WHERE source_norm = ? AND source_lang = ? AND target_lang = ?
              AND (superseded_by = '' OR superseded_by IS NULL)
            ORDER BY CASE status
                WHEN 'sealed' THEN 0
                WHEN 'draft' THEN 1
                ELSE 2 END
            LIMIT 1
            """,
            (source_norm, source_lang, target_lang),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {"id": row[0], "status": row[1], "target_text": row[2]}


def ensure_established_draft(
    source_text: str,
    source_lang: str,
    target_lang: str,
    *,
    store: Storage | None = None,
    matcher: Matcher | None = None,
    lexicon: Lexicon | None = None,
    use_jeles: bool = True,
    include_asserted: bool = False,
    attached_by: str = "established-lane",
) -> dict[str, Any]:
    """Recognize + land as draft with evidence and citation warrant.

    Return shape ``{"action": ..., "recognized": bool, "hit": <dict>|None,
    "pair_id": str, "status": "draft"|"sealed", "evidence": [...],
    "warrant": {...}, "rung": str, "provider": str}``. ``action`` is one of:

    * ``"miss"`` — recognition returned nothing.
    * ``"suppressed_by_rejection"`` — a pair for this norm was rejected by
      a reviewer; the established lane respects the rejection rather than
      re-drafting an answer a human already said no to.
    * ``"already_sealed"`` — a pair for this norm is already sealed in the
      store, so there is nothing for the established lane to add. (Unusual
      in the cascade path because tier 1 would have caught this first, but
      a caller who invokes ``ensure_established_draft`` directly might hit
      it.)
    * ``"reused_draft"`` — a draft pair already exists for this norm;
      returned unchanged so repeat calls are idempotent.
    * ``"created_draft"`` — a fresh draft pair was written, evidence
      attached, citation warrant attached.
    """
    store = get_store(store)
    m = matcher or StringMatcher()
    hit = recognize(
        source_text,
        source_lang,
        target_lang,
        matcher=m,
        lexicon=lexicon,
        use_jeles=use_jeles,
        include_asserted=include_asserted,
    )
    if hit is None:
        return {"action": "miss", "recognized": False}

    source_norm = m.normalize(source_text) or source_text.strip().lower()

    if _is_rejected(source_norm, source_lang, target_lang, store):
        return {
            "action": "suppressed_by_rejection",
            "recognized": True,
            "hit": hit,
        }

    existing = _find_existing_pair(source_norm, source_lang, target_lang, store)
    if existing and existing["status"] == "sealed":
        return {
            "action": "already_sealed",
            "recognized": True,
            "hit": hit,
            "pair_id": existing["id"],
            "status": "sealed",
        }

    provider = hit.get("provider") or "lexicon"
    origin = f"established-{provider}"

    if existing and existing["status"] == "draft":
        pair_id = existing["id"]
        action = "reused_draft"
    else:
        pair = memory.add_pair(
            source_text=source_text,
            target_text=hit["target_text"],
            source_lang=source_lang,
            target_lang=target_lang,
            status="draft",
            origin=origin,
            reason=f"{hit.get('rung', 'established')}:{hit.get('authority', '')}",
            store=store,
            matcher=m,
        )
        pair_id = pair["id"]
        action = "created_draft"

    evidence_rows: list[Any] = []
    locators = [hit["locator"]]
    for s in hit.get("sources") or []:
        if s not in locators:
            locators.append(s)
    for loc in locators[:5]:
        kind = "url" if str(loc).startswith("http") else "document"
        try:
            evidence_rows.append(
                evidence.attach(
                    pair_id,
                    kind=kind,
                    locator=str(loc),
                    reason=f"{hit.get('rung')}:{hit.get('authority')}",
                    attached_by=attached_by,
                    store=store,
                )
            )
        except Exception as exc:  # noqa: BLE001
            evidence_rows.append(
                {"error": type(exc).__name__, "detail": str(exc), "locator": loc}
            )

    try:
        w = warrant.attach(
            pair_id,
            kind="citation",
            authority=str(hit.get("authority") or provider),
            locator=str(hit["locator"]),
            check=str(hit.get("check") or ""),
            attached_by=attached_by,
            store=store,
        )
    except Exception as exc:  # noqa: BLE001
        w = {"error": type(exc).__name__, "detail": str(exc)}

    return {
        "action": action,
        "recognized": True,
        "hit": hit,
        "pair_id": pair_id,
        "status": "draft",
        "evidence": evidence_rows,
        "warrant": w,
        "rung": hit.get("rung", "established"),
        "provider": provider,
    }
