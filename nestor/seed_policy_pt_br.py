"""A seeded demo store shaped for a Portuguese (Brazilian) public-sector audience.

Same shape as :mod:`nestor.seed_policy`. Rendered in **Brazilian Portuguese**
(pt-BR), following the *Acordo Ortográfico de 1990* as adopted in Brazil —
the register a Brazilian federal ministry, the Congresso Nacional, or a
Brazilian-hosted lusophone body would recognise. The European variant is
:mod:`nestor.seed_policy_pt_pt`; the two ship separately per operator
direction (decision 0201 Q2).

Distinguishing lexicon relative to the European seed:

* **"está pendente"** — Brazilian phrasing where European takes
  ``encontra-se pendente``.
* **"apresentou suas conclusões"** — Brazilian drops the article on the
  third-person possessive; European retains it.
* **"registradas"** — Brazilian past participle for *registered/recorded*;
  European is ``registadas``.
* **"revisão legislativa"** — Brazilian institutional register.
* **"concordam em convocar"** — Brazilian agreement construction.
* **"Econômico"** in *OCDE* expansion — Brazilian accent placement;
  European is *Económico*.
* **"R$"** and Brazilian ``.`` thousands separator for the numeric baseline;
  European uses ``€`` and thin space.

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
DEMO_VERIFIER = "rafaela"

#: Translation (en → pt-BR), sealed.
_TRANSLATIONS = [
    ("The agreement enters into force on ratification.",
     "O acordo entra em vigor com a ratificação."),
    ("Public consultation is required for this measure.",
     "É requerida consulta pública para esta medida."),
    ("The report is subject to legislative review.",
     "O relatório está sujeito a revisão legislativa."),
    ("Ministerial approval is pending.",
     "A aprovação ministerial está pendente."),
    ("The delegation submitted its findings.",
     "A delegação apresentou suas conclusões."),
]

_DRAFTS = [
    ("The measure takes effect immediately.",
     "A medida entra em vigor imediatamente."),
]

#: The organisation-name expansions carry the pt-BR ``Econômico`` in OCDE.
_ALIASES = [
    ("ONU", "Organização das Nações Unidas"),
    ("FMI", "Fundo Monetário Internacional"),
    ("OMS", "Organização Mundial da Saúde"),
    ("OCDE", "Organização para a Cooperação e Desenvolvimento Econômico"),
]

#: Local currency framing. ``R$`` and ``.`` thousands separator per the
#: Brazilian convention; ``bi`` for *billion*.
_BASELINES = [
    ("dotacao-orcamentaria-ministerial-2024", "R$4,20 bi"),
    ("participantes-inscritos-2024", "48.700"),
]

_QUEUE_TITLE = "Minuta de ata (sessão extraordinária, trecho)"
_QUEUE_TEXT = (
    "As partes signatárias concordam em convocar uma sessão extraordinária.\n"
    "As deliberações serão registradas e disponibilizadas ao público no "
    "prazo de trinta dias.\n"
    "O oficial presidente fará circular a ata para revisão."
)

_FORGED_SOURCE = "The session convenes at noon."
_FORGED_TARGET = "A sessão se reúne à meia-noite."


def seed_store(store: Storage, verifier: str = DEMO_VERIFIER,
               include_forged: bool = False) -> dict:
    counts = {"sealed": 0, "draft": 0, "aliases": 0, "baselines": 0,
              "queued": 0, "forged": 0}

    for src, tgt in _TRANSLATIONS:
        memory.add_pair(src, tgt, "en", "pt-BR", status="sealed",
                        verifier=verifier, origin="demo-policy-pt-br", store=store)
        counts["sealed"] += 1

    for src, tgt in _DRAFTS:
        memory.add_pair(src, tgt, "en", "pt-BR", status="draft",
                        origin="demo-policy-pt-br", store=store)
        counts["draft"] += 1

    ent = EntityResolver(store, domain="entity")
    for surface, canonical in _ALIASES:
        ent.seal(surface, canonical, verifier=verifier, origin="demo-policy-pt-br")
        counts["aliases"] += 1

    rec = Reconciler(store, domain="value", pct_tol=0.05)
    for label, value in _BASELINES:
        rec.seal_baseline(label, value, verifier=verifier, origin="demo-policy-pt-br")
        counts["baselines"] += 1

    if supports_queue(store):
        _doc, passages = cascade.translate_text(
            _QUEUE_TEXT, "pt-BR", source_lang="en", engine_name="offline",
            title=_QUEUE_TITLE, store=store)
        counts["queued"] = sum(1 for p in passages if p.tier != 1)

    if include_forged and signing.signing_enabled():
        store.memory_insert({
            "id": "demo-policy-pt-br-forged-0001",
            "source_text": _FORGED_SOURCE,
            "source_norm": memory._norm(_FORGED_SOURCE),
            "source_lang": "en",
            "target_text": _FORGED_TARGET,
            "target_lang": "pt-BR",
            "status": "sealed",
            "verifier": verifier,
            "weight": 1.0,
            "origin": "demo-policy-pt-br:forged",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seal_sig": "",
        })
        counts["forged"] = 1

    return counts
