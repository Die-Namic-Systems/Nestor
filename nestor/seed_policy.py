"""A seeded demo store shaped for a public-sector audience.

Same shape as :mod:`nestor.seed` — a small, honest memory across all three
recipes so ``nestor ui --db data/nestor-demo.db`` opens on live subject matter
— but the sentences, aliases, and baselines are policy-register rather than
office-register. A ministry chief-of-staff, a policy analyst, or a foreign-
ministry official opening the demo sees their own vocabulary reflected back,
not ``"Good night."`` and ``"IBM"``.

**Fictional-shaped, on purpose.** No sentence here is from any real treaty,
report, or law. No baseline names a real country, year, or statistic — the
labels are policy-shaped, the numbers are round-fictional so nothing could
mislead a reader about a real figure. If a real figure needs to be
demonstrated, the operator seals their own row against their own source and
signs as themselves — which is the whole point Nestor makes about the
difference between a demo and a working memory.

**Same covenant demonstration as the default seed.** One row is deliberately
left as a draft: the cascade produced it, no human signed it, and ``ask``
returns ``pending`` for it. The tour that ends at the draft is the tour that
teaches what Nestor refuses to do.

See ``docs/policy-brief.md`` for the audience this fixture is written for and
what running the demo on it is meant to show.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import cascade, memory, signing
from .entity import EntityResolver
from .reconcile import Reconciler
from .storage import Storage, supports_queue

#: The name every demo seal is recorded under. A fictional persona so a
#: reviewer never mistakes a demo signature for a real one. Consistent with
#: ``nestor.seed.DEMO_VERIFIER`` — same rule, same convention.
DEMO_VERIFIER = "elena"

#: Translation (en → es), sealed. Policy-register sentences a ministry or
#: international-body reader would recognise as their vocabulary. Every one
#: is generic — no treaty title, no regulation number.
_TRANSLATIONS = [
    ("The agreement enters into force on ratification.",
     "El acuerdo entra en vigor tras la ratificación."),
    ("Public consultation is required for this measure.",
     "Se requiere consulta pública para esta medida."),
    ("The report is subject to legislative review.",
     "El informe está sujeto a revisión legislativa."),
    ("Ministerial approval is pending.",
     "La aprobación ministerial está pendiente."),
    ("The delegation submitted its findings.",
     "La delegación presentó sus conclusiones."),
]

#: A draft the cascade left for a human — so Memory shows a `~ draft`, and
#: the covenant reads as a *refusal*, not an absence. This is the row a
#: walk-through ends on: the machine proposed a translation, the store
#: keeps it, and ``ask`` returns pending until a human seals it in
#: ``nestor ui``.
_DRAFTS = [
    ("The measure takes effect immediately.",
     "La medida entra en vigor de inmediato."),
]

#: Entity aliases (surface → canonical). International-body acronyms whose
#: expansions are public knowledge and unambiguous; no living person's
#: name, no controversial acronym.
_ALIASES = [
    ("UN", "United Nations"),
    ("IMF", "International Monetary Fund"),
    ("WHO", "World Health Organization"),
    ("OECD", "Organisation for Economic Co-operation and Development"),
]

#: Numeric baselines (label → figure). **Fictional-shaped:** labels are
#: policy-register but figures are round, not real. A demo that quoted a
#: real national statistic would either be wrong (they change) or steal
#: attribution (they are somebody's measurement). Round-fictional lets
#: the ``check`` recipe demonstrate variation-and-tolerance without
#: pretending to speak for any government.
_BASELINES = [
    ("ministry-budget-line-2024", "$4.20B"),
    ("registered-participants-2024", "48,700"),
]

#: A short document in policy register whose lines are NOT in the sealed
#: memory, so the cascade leaves them as review drafts. The Queue thus
#: opens on real work rather than an empty page, matching the same
#: rationale in :mod:`nestor.seed`.
_QUEUE_TITLE = "Draft minutes (extraordinary session, excerpt)"
_QUEUE_TEXT = (
    "The undersigned parties agree to convene an extraordinary session.\n"
    "Deliberations shall be recorded and made publicly available within "
    "thirty days.\n"
    "The presiding officer will circulate the minutes for review."
)

#: A forged seal — a row written straight into the store as ``sealed`` by a
#: trusted name, with a signature that name could never have produced.
#: Same shape and rationale as :mod:`nestor.seed`'s forged row: seeded
#: only when signing is on, so the row is refused by its *signature* rather
#: than trusted on stored status. Deliberately harmless content.
_FORGED_SOURCE = "The session convenes at noon."
_FORGED_TARGET = "La sesión se convoca a medianoche."


def seed_store(store: Storage, verifier: str = DEMO_VERIFIER,
               include_forged: bool = False) -> dict:
    """Fill ``store`` with the policy-shaped demo memory. Returns a counts dict.

    Same signature and semantics as :func:`nestor.seed.seed_store`. Safe to
    re-run: every seal is by the same ``verifier`` against the same source,
    which is treated as a same-actor correction rather than a conflict.
    """
    counts = {"sealed": 0, "draft": 0, "aliases": 0, "baselines": 0,
              "queued": 0, "forged": 0}

    for src, tgt in _TRANSLATIONS:
        memory.add_pair(src, tgt, "en", "es", status="sealed",
                        verifier=verifier, origin="demo-policy", store=store)
        counts["sealed"] += 1

    for src, tgt in _DRAFTS:
        memory.add_pair(src, tgt, "en", "es", status="draft",
                        origin="demo-policy", store=store)
        counts["draft"] += 1

    ent = EntityResolver(store, domain="entity")
    for surface, canonical in _ALIASES:
        ent.seal(surface, canonical, verifier=verifier, origin="demo-policy")
        counts["aliases"] += 1

    rec = Reconciler(store, domain="value", pct_tol=0.05)
    for label, value in _BASELINES:
        rec.seal_baseline(label, value, verifier=verifier, origin="demo-policy")
        counts["baselines"] += 1

    if supports_queue(store):
        _doc, passages = cascade.translate_text(
            _QUEUE_TEXT, "es", source_lang="en", engine_name="offline",
            title=_QUEUE_TITLE, store=store)
        counts["queued"] = sum(1 for p in passages if p.tier != 1)

    if include_forged and signing.signing_enabled():
        store.memory_insert({
            "id": "demo-policy-forged-0001",
            "source_text": _FORGED_SOURCE,
            "source_norm": memory._norm(_FORGED_SOURCE),
            "source_lang": "en",
            "target_text": _FORGED_TARGET,
            "target_lang": "es",
            "status": "sealed",
            "verifier": verifier,
            "weight": 1.0,
            "origin": "demo-policy:forged",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seal_sig": "",
        })
        counts["forged"] = 1

    return counts
