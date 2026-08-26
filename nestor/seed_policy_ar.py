"""A seeded demo store shaped for an Arabic-speaking public-sector audience.

Same shape as :mod:`nestor.seed_policy`. Rendered in **Modern Standard
Arabic** (MSA, ar) — the register a ministry, an Arab-League body, or an
Arab-speaking desk at an international organisation would recognise. The
covenant, the fictional-shaped-content rule, and the walk-through's role
for the draft row are all unchanged from :mod:`nestor.seed_policy`.

**The composition dependency.** Formal Arabic uses combining marks (tashkeel,
shadda, sukun) freely. Precomposed forms are usual in editor-saved sources,
but PDF-paste and some keyboard layouts produce decomposed sequences. The
match seam relies on ``StringMatcher.normalize`` NFC-folding before its
regex pipeline (decision 0200); without that fold, a query for
``يَسري`` (u + fatha) would key differently from a stored
precomposed form. This module's strings are stored as their editor-saved NFC
form; the NFC seam is what makes matching against a decomposed query work at
serve time.

**Same covenant demonstration.** One draft translation, the row a
walk-through ends on.

**Reviewer note.** These translations follow the register used across
publicly-published Arab-League and UN-Arabic policy corpora — the same
"collective vetting" premise that the Spanish seed rests on. A native-speaker
review is welcome as a follow-up git change; nothing about the demo's shape
depends on any single line's exact phrasing.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import cascade, memory, signing
from .entity import EntityResolver
from .reconcile import Reconciler
from .storage import Storage, supports_queue

#: A fictional persona so a reviewer never mistakes a demo signature for a
#: real one. Distinct from every other seed's verifier.
DEMO_VERIFIER = "salma"

#: Translation (en → ar), sealed. Modern Standard Arabic in the register
#: used by Arab-League and UN-Arabic policy publications.
_TRANSLATIONS = [
    ("The agreement enters into force on ratification.",
     "يدخل الاتفاق حيز النفاذ عند التصديق."),
    ("Public consultation is required for this measure.",
     "المشاورات العامة مطلوبة لهذا الإجراء."),
    ("The report is subject to legislative review.",
     "يخضع التقرير للمراجعة التشريعية."),
    ("Ministerial approval is pending.",
     "الموافقة الوزارية معلقة."),
    ("The delegation submitted its findings.",
     "قدم الوفد استنتاجاته."),
]

_DRAFTS = [
    ("The measure takes effect immediately.",
     "يسري هذا الإجراء فوراً."),
]

#: Entity aliases (surface → canonical). Arabic expansions of the same four
#: international-body acronyms the other seeds use, so a reviewer comparing
#: across languages sees the same set of organisations.
_ALIASES = [
    ("UN", "الأمم المتحدة"),
    ("IMF", "صندوق النقد الدولي"),
    ("WHO", "منظمة الصحة العالمية"),
    ("OECD", "منظمة التعاون الاقتصادي والتنمية"),
]

#: Numeric baselines. Figures kept in Western digits so the ``check``
#: recipe's numeric parser reads them unchanged; currency and label live
#: in Arabic script.
_BASELINES = [
    ("بند-الميزانية-الوزارية-2024", "$4.20B"),
    ("المشاركون-المسجلون-2024", "48,700"),
]

_QUEUE_TITLE = "مسودة محضر (جلسة استثنائية، مقتطف)"
_QUEUE_TEXT = (
    "توافق الأطراف الموقعة على عقد جلسة استثنائية.\n"
    "ستُسجَّل المداولات وتُتاح للعموم في غضون ثلاثين يوماً.\n"
    "سيقوم الرئيس المُدير للجلسة بتعميم المحضر للمراجعة."
)

_FORGED_SOURCE = "The session convenes at noon."
_FORGED_TARGET = "تُعقد الجلسة في منتصف الليل."


def seed_store(store: Storage, verifier: str = DEMO_VERIFIER,
               include_forged: bool = False) -> dict:
    counts = {"sealed": 0, "draft": 0, "aliases": 0, "baselines": 0,
              "queued": 0, "forged": 0}

    for src, tgt in _TRANSLATIONS:
        memory.add_pair(src, tgt, "en", "ar", status="sealed",
                        verifier=verifier, origin="demo-policy-ar", store=store)
        counts["sealed"] += 1

    for src, tgt in _DRAFTS:
        memory.add_pair(src, tgt, "en", "ar", status="draft",
                        origin="demo-policy-ar", store=store)
        counts["draft"] += 1

    ent = EntityResolver(store, domain="entity")
    for surface, canonical in _ALIASES:
        ent.seal(surface, canonical, verifier=verifier, origin="demo-policy-ar")
        counts["aliases"] += 1

    rec = Reconciler(store, domain="value", pct_tol=0.05)
    for label, value in _BASELINES:
        rec.seal_baseline(label, value, verifier=verifier, origin="demo-policy-ar")
        counts["baselines"] += 1

    if supports_queue(store):
        _doc, passages = cascade.translate_text(
            _QUEUE_TEXT, "ar", source_lang="en", engine_name="offline",
            title=_QUEUE_TITLE, store=store)
        counts["queued"] = sum(1 for p in passages if p.tier != 1)

    if include_forged and signing.signing_enabled():
        store.memory_insert({
            "id": "demo-policy-ar-forged-0001",
            "source_text": _FORGED_SOURCE,
            "source_norm": memory._norm(_FORGED_SOURCE),
            "source_lang": "en",
            "target_text": _FORGED_TARGET,
            "target_lang": "ar",
            "status": "sealed",
            "verifier": verifier,
            "weight": 1.0,
            "origin": "demo-policy-ar:forged",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seal_sig": "",
        })
        counts["forged"] = 1

    return counts
