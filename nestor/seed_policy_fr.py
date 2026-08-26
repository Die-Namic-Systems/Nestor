"""A seeded demo store shaped for a French-speaking public-sector audience.

Same shape as :mod:`nestor.seed_policy` — a small, honest memory across all
three recipes so ``nestor ui --db data/nestor-demo.db`` opens on live subject
matter — with the sentences, aliases, and baselines rendered in the vocabulary
a French ministry, an EU institution's francophone desk, or a francophone
inter-governmental body would recognise. Rationale for the language expansion
is decision 0201 (multilingual policy seeds); the covenant demonstration and
the fictional-shaped-content rule are unchanged from
:mod:`nestor.seed_policy`.

**Same covenant demonstration.** One row (`_DRAFTS`) is deliberately left as
a draft: the cascade produced it, no human signed it, and ``ask`` returns
``pending`` for it. The tour that ends at the draft is the tour that teaches
what Nestor refuses to do.

**Fictional-shaped, on purpose.** No sentence is from any real treaty,
regulation, or law; no baseline names a real country, year, or statistic. The
figures are round-fictional so nothing here could mislead a reader about a
real number. See :mod:`nestor.seed_policy` for the argument in full.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import cascade, memory, signing
from .entity import EntityResolver
from .reconcile import Reconciler
from .storage import Storage, supports_queue

#: The name every French seal is recorded under. A fictional persona so a
#: reviewer never mistakes a demo signature for a real one. Distinct from the
#: default (``rita``), Spanish (``elena``), pt-PT (``filipa``), pt-BR
#: (``rafaela``), and Arabic (``salma``) verifiers so a mixed or copied store
#: can be resolved by verifier alone.
DEMO_VERIFIER = "amelie"

#: Translation (en → fr), sealed. Policy-register sentences a French-speaking
#: ministry, an EU francophone desk, or a francophone international body
#: reader would recognise as their vocabulary.
_TRANSLATIONS = [
    ("The agreement enters into force on ratification.",
     "L'accord entre en vigueur dès la ratification."),
    ("Public consultation is required for this measure.",
     "Une consultation publique est requise pour cette mesure."),
    ("The report is subject to legislative review.",
     "Le rapport est soumis à un examen législatif."),
    ("Ministerial approval is pending.",
     "L'approbation ministérielle est en attente."),
    ("The delegation submitted its findings.",
     "La délégation a présenté ses conclusions."),
]

#: The draft the walk-through ends on.
_DRAFTS = [
    ("The measure takes effect immediately.",
     "La mesure prend effet immédiatement."),
]

#: Entity aliases (surface → canonical). International-body acronyms in their
#: French expansions.
_ALIASES = [
    ("ONU", "Organisation des Nations Unies"),
    ("FMI", "Fonds monétaire international"),
    ("OMS", "Organisation mondiale de la santé"),
    ("OCDE", "Organisation de coopération et de développement économiques"),
]

#: Numeric baselines (label → figure). Fictional-shaped labels; figures are
#: kept in Western digits so the ``check`` recipe's numeric parser reads them
#: unchanged from Spanish. Currency label is in the local vocabulary.
_BASELINES = [
    ("ligne-budgetaire-ministerielle-2024", "€4,20 mrd"),
    ("participants-inscrits-2024", "48 700"),
]

#: A short policy-register document whose lines are NOT in the sealed memory.
_QUEUE_TITLE = "Projet de procès-verbal (session extraordinaire, extrait)"
_QUEUE_TEXT = (
    "Les parties soussignées conviennent de convoquer une session extraordinaire.\n"
    "Les délibérations seront enregistrées et rendues publiques dans un délai "
    "de trente jours.\n"
    "L'officier président fera circuler le procès-verbal pour examen."
)

#: A forged seal — a row written straight into the store as ``sealed`` by a
#: trusted name, with a signature that name could never have produced.
_FORGED_SOURCE = "The session convenes at noon."
_FORGED_TARGET = "La séance se réunit à minuit."


def seed_store(store: Storage, verifier: str = DEMO_VERIFIER,
               include_forged: bool = False) -> dict:
    """Fill ``store`` with the French policy-shaped demo memory. Same
    signature and semantics as :func:`nestor.seed_policy.seed_store`.
    """
    counts = {"sealed": 0, "draft": 0, "aliases": 0, "baselines": 0,
              "queued": 0, "forged": 0}

    for src, tgt in _TRANSLATIONS:
        memory.add_pair(src, tgt, "en", "fr", status="sealed",
                        verifier=verifier, origin="demo-policy-fr", store=store)
        counts["sealed"] += 1

    for src, tgt in _DRAFTS:
        memory.add_pair(src, tgt, "en", "fr", status="draft",
                        origin="demo-policy-fr", store=store)
        counts["draft"] += 1

    ent = EntityResolver(store, domain="entity")
    for surface, canonical in _ALIASES:
        ent.seal(surface, canonical, verifier=verifier, origin="demo-policy-fr")
        counts["aliases"] += 1

    rec = Reconciler(store, domain="value", pct_tol=0.05)
    for label, value in _BASELINES:
        rec.seal_baseline(label, value, verifier=verifier, origin="demo-policy-fr")
        counts["baselines"] += 1

    if supports_queue(store):
        _doc, passages = cascade.translate_text(
            _QUEUE_TEXT, "fr", source_lang="en", engine_name="offline",
            title=_QUEUE_TITLE, store=store)
        counts["queued"] = sum(1 for p in passages if p.tier != 1)

    if include_forged and signing.signing_enabled():
        store.memory_insert({
            "id": "demo-policy-fr-forged-0001",
            "source_text": _FORGED_SOURCE,
            "source_norm": memory._norm(_FORGED_SOURCE),
            "source_lang": "en",
            "target_text": _FORGED_TARGET,
            "target_lang": "fr",
            "status": "sealed",
            "verifier": verifier,
            "weight": 1.0,
            "origin": "demo-policy-fr:forged",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seal_sig": "",
        })
        counts["forged"] = 1

    return counts
