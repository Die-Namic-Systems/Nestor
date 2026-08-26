"""Jeles corpus as a second recognition source for the established lane.

The lexicon is exact-norm and domain-scoped. Jeles is corpus-backed Q&A —
its own ``ask_corpus`` runs against a set of nuggets each carrying
``verification_kind`` (``human`` / ``machine`` / ``asserted``),
``verified_by``, ``sources``, and ``tags``. Neither this bridge nor the
lexicon path ever seals: hits land as Nestor drafts with evidence rows and
a citation warrant when a URL source exists (see
``nestor.established.recognize.ensure_established_draft``).

The ``jeles`` package is an **optional** dependency: importing this module
imports it, so :mod:`nestor.established` itself imports this module lazily
(via ``nestor.established.recognize.recognize``). A deployment that does
not want the corpus lookup can pass ``use_jeles=False`` on every
recognizer entry point, or simply not install jeles.

Decisions: 0055 (the original bridge in ``nestor/frank.py``'s neighbour),
0205 (the cascade seam), 0206 (this subpackage).
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from jeles import corpus as jeles_corpus

#: Verification kinds Jeles reports where the bridge WILL consider the
#: nugget for recognition. ``asserted`` is deliberately excluded — an
#: asserted nugget is an unchecked write, and serving one as an
#: established draft would collapse the distinction the rung system draws.
_TRUSTED_KINDS = frozenset({"human", "machine"})


def _kind_of(nugget: dict[str, Any]) -> str:
    return (nugget.get("verification_kind") or "human").strip().lower()


def _sources_list(nugget: dict[str, Any]) -> list[str]:
    src = nugget.get("sources") or []
    if isinstance(src, str):
        return [src] if src else []
    return [str(s) for s in src if s]


def _primary_locator(sources: list[str]) -> str:
    """The first URL if present; otherwise the first source; otherwise a
    marker naming Jeles as the provider so the evidence row still points
    somewhere legible."""
    for s in sources:
        if s.startswith(("http://", "https://")):
            return s
    if sources:
        return sources[0]
    return "jeles:corpus"


def _authority(nugget: dict[str, Any], sources: list[str]) -> str:
    """A single string reviewer-readable authority: rung + who + where.

    ``jeles:human:demo-curator`` for a human-verified nugget with a named
    verifier; ``jeles:machine:iana.org`` for a machine-verified one where
    the source is an HTTP URL; ``jeles:human`` when neither is available.
    """
    kind = _kind_of(nugget)
    vb = (nugget.get("verified_by") or "").strip()
    if vb:
        return f"jeles:{kind}:{vb}"
    for s in sources:
        if s.startswith("http"):
            host = urlparse(s).netloc or "web"
            return f"jeles:{kind}:{host}"
    return f"jeles:{kind}"


def _domain_tags(source_lang: str, target_lang: str) -> set[str]:
    """Tag shapes the bridge treats as an explicit domain match. Both
    ``->`` and ``→`` accepted; both ``domain:`` prefixed and bare forms
    accepted; case-folded on comparison. A nugget without any domain-ish
    tag is treated as "not scoped" — the bridge allows it, on the same
    reasoning ``memory.lookup`` uses when a caller does not restrict.
    """
    return {
        f"domain:{source_lang}->{target_lang}",
        f"domain:{source_lang}→{target_lang}",
        f"{source_lang}->{target_lang}",
        f"{source_lang}→{target_lang}",
    }


def _nugget_matches_domain(
    nugget: dict[str, Any], source_lang: str, target_lang: str
) -> bool:
    """If the nugget carries domain tags, require an exact match against
    the (source_lang, target_lang) pair; if it carries none, allow. The
    default-allow keeps a naive corpus (or a corpus authored before this
    bridge existed) usable without a mass retag."""
    tags = {str(t).strip().lower() for t in (nugget.get("tags") or [])}
    domain_ish = {
        t for t in tags if t.startswith("domain:") or "->" in t or "→" in t
    }
    if not domain_ish:
        return True
    wanted = {t.lower() for t in _domain_tags(source_lang, target_lang)}
    return bool(domain_ish & wanted)


def recognize_from_jeles(
    source_text: str,
    source_lang: str,
    target_lang: str,
    *,
    include_asserted: bool = False,
    require_exact: bool = False,
    min_confidence: float | None = None,
) -> dict[str, Any] | None:
    """Ask the Jeles corpus. Returns an established-shaped hit or ``None``.

    ``include_asserted`` opens the door to unchecked-write nuggets; leave
    ``False`` outside of tests. ``require_exact`` refuses partial matches;
    useful when the caller has a domain where a near-match is worse than
    a miss. ``min_confidence`` refuses hits below the given cutoff (the
    default lets Jeles' own ``MIN_ASK_SCORE`` decide).
    """
    text = (source_text or "").strip()
    if not text:
        return None

    result = jeles_corpus.ask_corpus(text, include_asserted=include_asserted)
    if not result.get("found") or not result.get("nugget"):
        return None

    nugget = result["nugget"]
    kind = _kind_of(nugget)
    if not include_asserted and kind not in _TRUSTED_KINDS:
        return None
    if require_exact and not result.get("exact"):
        return None
    if not _nugget_matches_domain(nugget, source_lang, target_lang):
        return None

    sources = _sources_list(nugget)
    locator = _primary_locator(sources)
    conf = 1.0 if result.get("exact") else float(
        min_confidence if min_confidence is not None else jeles_corpus.MIN_ASK_SCORE
    )
    if min_confidence is not None and conf < min_confidence:
        return None

    answer = (nugget.get("answer") or "").strip()
    if not answer:
        return None

    return {
        "source_text": source_text,
        "source_norm": text.lower(),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "target_text": answer,
        "authority": _authority(nugget, sources),
        "locator": locator,
        "check": (
            f"Jeles corpus nugget ({kind}); "
            f"verified_by={nugget.get('verified_by')!r}; "
            f"exact={bool(result.get('exact'))}"
        ),
        "confidence": conf,
        # A machine-verified nugget is corroborated, not established —
        # names the rung the run-time recognizer chooses so a reviewer
        # opening the pair sees which class of trust it came from.
        "rung": "established" if kind == "human" else "corroborated",
        "provider": "jeles",
        "verification_kind": kind,
        "nugget_id": nugget.get("id") or nugget.get("nugget_id") or "",
        "sources": sources,
        "exact": bool(result.get("exact")),
    }


def seed_demo_nuggets() -> list[dict[str, Any]]:
    """Load a few trusted nuggets for demos. Idempotent-ish (Jeles'
    ``put_nugget`` handles conflicts by supersession)."""
    specs = [
        {
            "nugget_id": "demo-42-hitchhiker",
            "question": "What is the answer to life, the universe, and everything?",
            "answer": (
                "42 — from Douglas Adams' The Hitchhiker's Guide to the Galaxy"
            ),
            "sources": [
                "https://en.wikipedia.org/wiki/Phrases_from_The_Hitchhiker%27s_Guide_to_the_Galaxy"
            ],
            "verified_by": "demo-curator",
            "verification_kind": "human",
            "tags": ["domain:number->meaning", "cultural", "demo"],
        },
        {
            "nugget_id": "demo-404",
            "question": "What does HTTP 404 mean?",
            "answer": "Not Found — the server cannot find the requested resource.",
            "sources": [
                "https://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml"
            ],
            "verified_by": "demo-curator",
            "verification_kind": "human",
            "tags": ["domain:http->desc", "http", "demo"],
        },
        {
            "nugget_id": "demo-paris",
            "question": "What is the capital of France?",
            "answer": "Paris",
            "sources": ["https://en.wikipedia.org/wiki/Paris"],
            "verified_by": "demo-curator",
            "verification_kind": "human",
            "tags": ["domain:geo->desc", "geography", "demo"],
        },
        {
            "nugget_id": "demo-asserted-should-not-serve",
            "question": "What is the secret staging password?",
            "answer": "hunter2",
            "sources": [],
            "verified_by": "random-bot",
            "verification_kind": "asserted",
            "tags": ["demo", "should-not-answer"],
        },
    ]
    out = []
    for spec in specs:
        out.append(jeles_corpus.put_nugget(**spec))
    return out
