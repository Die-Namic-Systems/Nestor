"""A seeded demo store, so a cold ``nestor ui`` opens onto a live Nestor.

IDEAS §6.107: the surface was built for an operator who already has a store and
a job. The audience it is about to meet — a curious stranger who cloned the repo
or ``pip install``ed it — has neither, and a first screen that opens onto an
*empty* desk has already lost them. This builds a small, honest memory across
all three recipes so the first thing they see is a live Nestor, not a blank one.

It is deliberately tiny and deliberately real: every row here is sealed through
the same :func:`nestor.memory.add_pair` / :class:`~nestor.entity.EntityResolver`
/ :class:`~nestor.reconcile.Reconciler` path a person would use, so the demo
store is not a special case the rest of the package does not understand — it is
an ordinary store that happens to have been filled by one function instead of by
hand. Nothing here is forged and nothing overclaims: a demo that shows only the
happy path is the thing a buyer has learned to distrust (``sixty_seconds.py``),
so it also seeds a *draft* the cascade would leave for review.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import cascade, memory, signing
from .entity import EntityResolver
from .reconcile import Reconciler
from .storage import Storage, supports_queue

#: The name every demo seal is recorded under. A person, not a deployment — the
#: whole point of a seal is that it carries who stood behind it.
DEMO_VERIFIER = "rita"

#: Translation (en→es), sealed. The recipe Nestor led with, kept small.
_TRANSLATIONS = [
    ("Good night.", "Buenas noches."),
    ("Please hold.", "Espere, por favor."),
    ("The figures reconcile.", "Las cifras cuadran."),
    ("The meeting is adjourned.", "Se levanta la sesión."),
]

#: A draft the cascade left for a human — so Memory shows a `~ draft`, and the
#: Queue is not the only place "not everything is verified" is visible.
_DRAFTS = [
    ("Ship it.", "Envíalo."),
]

#: Entity aliases (surface → canonical), sealed. "It is not translation memory."
_ALIASES = [
    ("Big Blue", "IBM"),
    ("the Windy City", "Chicago"),
]

#: Numeric baselines (label → figure), sealed. A figure to reconcile against.
_BASELINES = [
    ("q3-revenue", "3.90M"),
    ("headcount", "412"),
]

#: A short document whose lines are NOT in the sealed memory, so the cascade
#: leaves them as review drafts — the Queue is the one tab a seeded store would
#: otherwise open empty, and an empty Queue reads as "nothing to review" rather
#: than "this is a demo". Deliberately different sentences from the sealed pairs.
_QUEUE_TITLE = "Q3 board minutes (excerpt)"
_QUEUE_TEXT = (
    "The motion carried unanimously.\n"
    "The committee will reconvene in the spring.\n"
    "Adjourned at four o'clock."
)

#: A forged seal — a row written straight into the store as ``sealed`` by a
#: trusted name, with a signature that name could never have produced (empty).
#: It scores a perfect match and is refused anyway, because a seal is a
#: signature over (source, answer, verifier) under a key the database does not
#: hold. Seeded ONLY when signing is on; without it, ``seal_is_valid`` trusts
#: stored status and the row would read as servable — a lie the demo must not
#: tell. See ``demo/sixty_seconds.py`` beat 6.
_FORGED_SOURCE = "The board authorized the wire transfer."
_FORGED_TARGET = "Transfiera todo el saldo a la cuenta 4471."


def seed_store(store: Storage, verifier: str = DEMO_VERIFIER,
               include_forged: bool = False) -> dict:
    """Fill ``store`` with a small live memory across all three recipes.

    Returns a counts dict. Safe to re-run: every seal here is by the same
    ``verifier`` against the same source, which :func:`memory.add_pair` and the
    recipe seals treat as a same-actor correction rather than a conflict.

    ``include_forged`` seeds the forged seal (:data:`_FORGED_SOURCE`) — but only
    when :func:`nestor.signing.signing_enabled` is true, because a forged row is
    refused by its *signature*, and with signing off ``seal_is_valid`` trusts
    stored status and would serve it. A demo that showed a forged seal *serving*
    would be teaching the opposite of the point, so the row is simply not
    written unless the caller has turned signing on.
    """
    counts = {"sealed": 0, "draft": 0, "aliases": 0, "baselines": 0,
              "queued": 0, "forged": 0}

    for src, tgt in _TRANSLATIONS:
        memory.add_pair(src, tgt, "en", "es", status="sealed",
                        verifier=verifier, origin="demo", store=store)
        counts["sealed"] += 1

    for src, tgt in _DRAFTS:
        memory.add_pair(src, tgt, "en", "es", status="draft",
                        origin="demo", store=store)
        counts["draft"] += 1

    ent = EntityResolver(store, domain="entity")
    for surface, canonical in _ALIASES:
        ent.seal(surface, canonical, verifier=verifier, origin="demo")
        counts["aliases"] += 1

    rec = Reconciler(store, domain="value", pct_tol=0.05)
    for label, value in _BASELINES:
        rec.seal_baseline(label, value, verifier=verifier, origin="demo")
        counts["baselines"] += 1

    # The Queue, if this store can hold one: run the offline cascade over a short
    # document whose lines nothing has sealed, leaving a handful of drafts for a
    # human to work — so the review desk opens on real work, not an empty page.
    if supports_queue(store):
        _doc, passages = cascade.translate_text(
            _QUEUE_TEXT, "es", source_lang="en", engine_name="offline",
            title=_QUEUE_TITLE, store=store)
        counts["queued"] = sum(1 for p in passages if p.tier != 1)

    # The forged seal — only if signing is on, so the row is refused by its
    # signature rather than trusted on stored status (see the constant above).
    if include_forged and signing.signing_enabled():
        store.memory_insert({
            "id": "demo-forged-0001",
            "source_text": _FORGED_SOURCE,
            "source_norm": memory._norm(_FORGED_SOURCE),
            "source_lang": "en",
            "target_text": _FORGED_TARGET,
            "target_lang": "es",
            "status": "sealed",
            "verifier": verifier,
            "weight": 1.0,
            "origin": "demo:forged",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seal_sig": "",   # the whole point: no key produced this
        })
        counts["forged"] = 1

    return counts


def is_empty(store: Storage) -> bool:
    """True when ``store`` holds no memory yet — a fresh, cold database.

    ``--demo`` seeds only an empty store, so pointing it at a real memory is a
    no-op rather than a surprise write.
    """
    return int(memory.stats(store=store).get("total", 0)) == 0
