"""Wire the established-knowledge recognizer through the cascade seam.

The prototype forwarded from an external session monkeypatched
``cascade.translate_segment`` to insert a recognition step. Decision 0205
replaced that with a proper seam (``cascade.set_tier15_recognizer``);
this module registers through the seam. No monkeypatching; ``install()``
and ``uninstall()`` are one-line setters with no other side effects.

Contract with the seam (enforced by ``cascade._run_tier15_recognizer``):

* The recognizer returns a :class:`~nestor.cascade.Passage` or ``None``.
* A ``None`` return means "let the tier-2 engine handle it."
* A ``Passage`` return is served as-is and appended to the ledger; it
  MUST NOT carry ``state="sealed"`` (RuntimeError otherwise).

Ledger and store side-effects:

* The seam appends one passage entry per tier-1.5 draft (uniform with
  tier-1 and tier-2 passage entries).
* :func:`ensure_established_draft` writes the pair, the evidence rows,
  and the citation warrant. Each of those already appends its own ledger
  entry through the standard writers — no extra ledger work here.
"""
from __future__ import annotations

from .. import cascade
from ..cascade import Passage
from ..matcher import Matcher
from ..storage import Storage
from .recognize import ensure_established_draft


def _recognize_for_cascade(
    text: str,
    source_lang: str,
    target_lang: str,
    *,
    store: Storage,
    matcher: Matcher | None,
) -> Passage | None:
    """The registered tier-1.5 recognizer.

    Calls :func:`ensure_established_draft` (which is idempotent and
    respects rejections), then translates the report into a Passage:

    * ``miss`` → ``None`` (fall through to the engine).
    * ``suppressed_by_rejection`` → ``None`` (a reviewer already said no;
      the established lane must not re-propose the same draft).
    * ``already_sealed`` → ``None`` (would only occur if tier-1's own
      lookup missed a sealed row this recognizer found by a different
      route; falling through lets the engine's own memory.lookup catch
      it in the normal way).
    * ``created_draft`` / ``reused_draft`` → a tier-2 draft Passage
      carrying rung/provider/authority in ``meta`` so a reviewer opening
      the row sees which lane drafted it.
    """
    report = ensure_established_draft(
        text, source_lang, target_lang, store=store, matcher=matcher
    )
    if not report.get("recognized"):
        return None
    action = report.get("action")
    if action in ("suppressed_by_rejection", "already_sealed"):
        return None
    if action not in ("created_draft", "reused_draft"):
        return None

    hit = report["hit"]
    return Passage(
        source=text,
        target=hit["target_text"],
        tier=2,
        state="draft",
        engine="established",
        confidence=float(hit.get("confidence", 1.0)),
        meta={
            "pair_id": report.get("pair_id", ""),
            "rung": hit.get("rung", "established"),
            "provider": hit.get("provider", "lexicon"),
            "authority": hit.get("authority", ""),
            "locator": hit.get("locator", ""),
            "warrant_kinds": ["citation"],
            # No segment queue: an established draft is not the shape a
            # human seal queue wants at the top. Callers who need it
            # queued can seal it explicitly through the UI.
            "seal_queue": False,
        },
    )


def install() -> None:
    """Register the established recognizer through the cascade seam.

    Idempotent-ish: two consecutive installs replace the recognizer with
    itself, matching the seam's single-recognizer contract (decision 0205
    Q3). Not thread-safe against concurrent uninstall from a different
    thread, but neither is the seam itself — the setter is a module-level
    assignment.
    """
    cascade.set_tier15_recognizer(_recognize_for_cascade)


def uninstall() -> None:
    """Unregister the established recognizer if it is the currently-
    installed one. If some other recognizer has since been installed,
    leave that one alone rather than clobbering it silently.
    """
    if cascade.get_tier15_recognizer() is _recognize_for_cascade:
        cascade.set_tier15_recognizer(None)


def installed() -> bool:
    """True iff this module's recognizer is the currently-registered one."""
    return cascade.get_tier15_recognizer() is _recognize_for_cascade


# Re-exported for the top-level ``__all__`` in ``__init__``.
__all__ = ["install", "installed", "uninstall"]
