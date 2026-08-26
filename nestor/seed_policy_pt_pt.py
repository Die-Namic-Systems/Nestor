"""A seeded demo store shaped for a Portuguese (European) public-sector audience.

Same shape as :mod:`nestor.seed_policy`. Rendered in **European Portuguese**
(pt-PT), following the *Acordo Ortográfico de 1990* as adopted in Portugal —
the register a Portuguese ministry, the Assembleia da República, or a
lusophone international body based in Portugal would recognise. The Brazilian
variant is :mod:`nestor.seed_policy_pt_br`; the two are shipped separately
per operator direction (decision 0201 Q2) rather than forcing one dialect on
readers of the other.

Distinguishing lexicon relative to the Brazilian seed:

* **"encontra-se pendente"** — European reflexive-mesoclisis phrasing where
  the Brazilian equivalent takes ``está``.
* **"apresentou as suas conclusões"** — European third-person possessive
  form retains the article; Brazilian drops it.
* **"registadas"** — European past participle for *registered/recorded*;
  Brazilian is ``registradas``.
* **"apreciação legislativa"** — European institutional register.
* **"acordam em convocar"** — European agreement construction.
* **"Económico"** in *OCDE* expansion — European accent placement;
  Brazilian is *Econômico*.
* **"€"** and European thousands-separator whitespace for the numeric
  baseline; Brazilian uses ``R$`` and a period thousands separator.

**Same covenant demonstration.** One draft translation, the row a
walk-through ends on.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import cascade, memory, signing
from .entity import EntityResolver
from .reconcile import Reconciler
from .storage import Storage, supports_queue

#: A fictional persona so a reviewer never mistakes a demo signature for a
#: real one. Distinct from every other seed's verifier.
DEMO_VERIFIER = "filipa"

#: Translation (en → pt-PT), sealed.
_TRANSLATIONS = [
    ("The agreement enters into force on ratification.",
     "O acordo entra em vigor após a ratificação."),
    ("Public consultation is required for this measure.",
     "É requerida consulta pública para esta medida."),
    ("The report is subject to legislative review.",
     "O relatório está sujeito a apreciação legislativa."),
    ("Ministerial approval is pending.",
     "A aprovação ministerial encontra-se pendente."),
    ("The delegation submitted its findings.",
     "A delegação apresentou as suas conclusões."),
]

_DRAFTS = [
    ("The measure takes effect immediately.",
     "A medida produz efeitos imediatamente."),
]

#: The organisation-name expansions carry the pt-PT ``Económico`` in OCDE.
_ALIASES = [
    ("ONU", "Organização das Nações Unidas"),
    ("FMI", "Fundo Monetário Internacional"),
    ("OMS", "Organização Mundial da Saúde"),
    ("OCDE", "Organização para a Cooperação e Desenvolvimento Económico"),
]

#: Local currency framing. ``€`` and thin-space thousands per the European
#: convention; ``mil milhões`` for *billion*, distinct from Brazil's ``bi``.
_BASELINES = [
    ("linha-orcamental-ministerial-2024", "€4,20 mil milhões"),
    ("participantes-inscritos-2024", "48 700"),
]

_QUEUE_TITLE = "Projeto de ata (sessão extraordinária, excerto)"
_QUEUE_TEXT = (
    "As partes signatárias acordam em convocar uma sessão extraordinária.\n"
    "As deliberações serão registadas e disponibilizadas ao público no "
    "prazo de trinta dias.\n"
    "O oficial presidente fará circular a ata para apreciação."
)

_FORGED_SOURCE = "The session convenes at noon."
_FORGED_TARGET = "A sessão reúne-se à meia-noite."


def seed_store(store: Storage, verifier: str = DEMO_VERIFIER,
               include_forged: bool = False) -> dict:
    counts = {"sealed": 0, "draft": 0, "aliases": 0, "baselines": 0,
              "queued": 0, "forged": 0}

    for src, tgt in _TRANSLATIONS:
        memory.add_pair(src, tgt, "en", "pt-PT", status="sealed",
                        verifier=verifier, origin="demo-policy-pt-pt", store=store)
        counts["sealed"] += 1

    for src, tgt in _DRAFTS:
        memory.add_pair(src, tgt, "en", "pt-PT", status="draft",
                        origin="demo-policy-pt-pt", store=store)
        counts["draft"] += 1

    ent = EntityResolver(store, domain="entity")
    for surface, canonical in _ALIASES:
        ent.seal(surface, canonical, verifier=verifier, origin="demo-policy-pt-pt")
        counts["aliases"] += 1

    rec = Reconciler(store, domain="value", pct_tol=0.05)
    for label, value in _BASELINES:
        rec.seal_baseline(label, value, verifier=verifier, origin="demo-policy-pt-pt")
        counts["baselines"] += 1

    if supports_queue(store):
        _doc, passages = cascade.translate_text(
            _QUEUE_TEXT, "pt-PT", source_lang="en", engine_name="offline",
            title=_QUEUE_TITLE, store=store)
        counts["queued"] = sum(1 for p in passages if p.tier != 1)

    if include_forged and signing.signing_enabled():
        store.memory_insert({
            "id": "demo-policy-pt-pt-forged-0001",
            "source_text": _FORGED_SOURCE,
            "source_norm": memory._norm(_FORGED_SOURCE),
            "source_lang": "en",
            "target_text": _FORGED_TARGET,
            "target_lang": "pt-PT",
            "status": "sealed",
            "verifier": verifier,
            "weight": 1.0,
            "origin": "demo-policy-pt-pt:forged",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seal_sig": "",
        })
        counts["forged"] = 1

    return counts
