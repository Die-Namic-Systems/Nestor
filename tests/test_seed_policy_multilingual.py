"""Multilingual policy seed fixtures — the FR / pt-PT / pt-BR / ar family.

Same coverage as ``tests/test_seed_policy.py`` but parametrized across the
four new seed modules (decision 0201). For each language the tests assert:

* Load-bearing counts match the shape ``docs/policy-brief.md`` promises
  (5 sealed + 1 draft translation, 4 aliases, 2 baselines, ≥1 queued).
* All three recipes present under the seed's lang pair.
* The one draft row is truly unsigned — no ``verifier``, no ``seal_sig``.
* Each seed's ``DEMO_VERIFIER`` is distinct from every other seed's
  (default, Spanish, and the other three multilingual seeds), so a
  reviewer opening a mixed store can tell which fixture wrote each row
  at a glance.
* Each seed's ``origin`` tag is distinct from every other seed's, same
  reason — the origin column is the second signal.
* The dispatched CLI actually plumbs the choice through to the right
  module (guards against a wiring drift in ``nestor/cli.py``).

The four modules are shipped separately (rather than a single
``seed_policy_multi`` module with a ``lang`` parameter) so each language's
lexicon lives in one file a reviewer can read as a unit — decision 0201 Q1.
"""
from __future__ import annotations

import pytest

from nestor import (
    cascade,
    memory,
    seed_policy,
    seed_policy_ar,
    seed_policy_fr,
    seed_policy_pt_br,
    seed_policy_pt_pt,
)
from nestor import (
    seed as default_seed,
)
from nestor.sqlite_store import SqliteStore

#: The four seeds under test. Every tuple is (module, scheme-name-on-cli,
#: target-lang-tag, origin-tag). Kept in one place so a new language later
#: is one row here plus a module and a CLI branch.
MULTILINGUAL_SEEDS = [
    (seed_policy_fr, "policy-fr", "fr", "demo-policy-fr"),
    (seed_policy_pt_pt, "policy-pt-pt", "pt-PT", "demo-policy-pt-pt"),
    (seed_policy_pt_br, "policy-pt-br", "pt-BR", "demo-policy-pt-br"),
    (seed_policy_ar, "policy-ar", "ar", "demo-policy-ar"),
]


def _fresh_store(tmp_path, ledger="ledger.jsonl"):
    cascade.set_ledger_path(str(tmp_path / ledger))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    return store


# --- per-seed shape ---------------------------------------------------------

@pytest.mark.parametrize("mod,scheme,lang,origin", MULTILINGUAL_SEEDS,
                         ids=[s[1] for s in MULTILINGUAL_SEEDS])
def test_seed_counts_match_the_policy_shape(mod, scheme, lang, origin, tmp_path):
    """Every multilingual seed must land the same 5+1+4+2+≥1 shape the
    policy-brief docs promise — anything else is a demo whose numbers a
    reader cannot verify."""
    store = _fresh_store(tmp_path)
    counts = mod.seed_store(store)

    assert counts["sealed"] == 5
    assert counts["draft"] == 1
    assert counts["aliases"] == 4
    assert counts["baselines"] == 2
    assert counts["queued"] >= 1
    assert counts["forged"] == 0  # signing off in tests


@pytest.mark.parametrize("mod,scheme,lang,origin", MULTILINGUAL_SEEDS,
                         ids=[s[1] for s in MULTILINGUAL_SEEDS])
def test_all_three_recipes_present(mod, scheme, lang, origin, tmp_path):
    """Translation, entity, and value all show up in ``memory.stats`` — the
    demo would be misleading if it opened with two recipes and no reader
    could tell which recipe was missing."""
    store = _fresh_store(tmp_path)
    mod.seed_store(store)

    stats = memory.stats(store=store)
    pairs = {(sl, tl) for sl, tl, _ in stats["lang_pairs"]}
    targets = {tl for _, tl, _ in stats["lang_pairs"]}
    assert ("en", lang) in pairs
    assert ("entity", "entity") in pairs
    assert "value" in targets


@pytest.mark.parametrize("mod,scheme,lang,origin", MULTILINGUAL_SEEDS,
                         ids=[s[1] for s in MULTILINGUAL_SEEDS])
def test_the_draft_row_is_truly_unsigned(mod, scheme, lang, origin, tmp_path):
    """The row the walk-through ends on — the covenant demonstration — must
    carry no verifier and no signature. Same invariant as
    ``test_seed_policy.py::test_the_draft_row_is_the_covenant_demonstration``.
    """
    store = _fresh_store(tmp_path)
    mod.seed_store(store)

    drafts = [p for p in store.memory_list() if p.get("status") == "draft"]
    assert len(drafts) >= 1
    for d in drafts:
        assert not d.get("verifier"), (
            f"draft row must carry no verifier — got {d.get('verifier')!r} on "
            f"{d.get('source_text')!r} in {scheme}")
        assert not d.get("seal_sig"), (
            f"draft row must carry no seal signature in {scheme}")


@pytest.mark.parametrize("mod,scheme,lang,origin", MULTILINGUAL_SEEDS,
                         ids=[s[1] for s in MULTILINGUAL_SEEDS])
def test_origin_tag_is_this_seed_and_no_other(mod, scheme, lang, origin, tmp_path):
    """Every sealed row's ``origin`` names the seed that wrote it. A row
    from ``policy-fr`` must not accidentally carry ``demo-policy`` or any
    of the other multilingual origins."""
    store = _fresh_store(tmp_path)
    mod.seed_store(store)

    origins = {p.get("origin") for p in store.memory_list()}
    assert origin in origins, f"{scheme} did not write any row with origin={origin!r}"
    # The other seed origins must not appear — no accidental cross-writes.
    other_origins = {o for _, _, _, o in MULTILINGUAL_SEEDS if o != origin}
    other_origins.add("demo")          # default seed
    other_origins.add("demo-policy")   # Spanish policy seed
    unexpected = origins & other_origins
    assert not unexpected, (
        f"{scheme} store leaked rows tagged with other-fixture origins: "
        f"{unexpected}")


# --- cross-fixture distinctness --------------------------------------------

def test_every_seed_verifier_is_distinct():
    """A mixed or copied store must be resolvable by verifier alone. The
    six shipped fixtures — default (``rita``), Spanish (``elena``), and the
    four multilingual ones — all use distinct fictional personas."""
    verifiers = [
        default_seed.DEMO_VERIFIER,
        seed_policy.DEMO_VERIFIER,
        seed_policy_fr.DEMO_VERIFIER,
        seed_policy_pt_pt.DEMO_VERIFIER,
        seed_policy_pt_br.DEMO_VERIFIER,
        seed_policy_ar.DEMO_VERIFIER,
    ]
    assert len(set(verifiers)) == len(verifiers), (
        f"verifier personas must all be distinct across the six seeds; "
        f"got {verifiers}")


def test_pt_pt_and_pt_br_are_distinguishable_fixtures(tmp_path):
    """The whole point of shipping two Portuguese variants is that a
    reviewer can see the register difference (decision 0201 Q2).

    Two dialects of the same language legitimately converge on some
    formal-register phrasings — "É requerida consulta pública..." reads
    the same in Portugal and Brazil, and manufacturing a difference
    would be dishonest. What the test asserts instead is the set of
    signals a reviewer actually uses to tell the two fixtures apart:

    * The **OCDE** alias — ``Económico`` (pt-PT) vs ``Econômico``
      (pt-BR). One orthographic accent, but the load-bearing marker
      most Portuguese-speakers reach for when asked which variant a
      text was written in.
    * The **baseline currency** — ``€`` (pt-PT) vs ``R$`` (pt-BR).
    * A **majority** of the five sealed sentences must differ. At
      most one may be identical — more than that and the two fixtures
      have collapsed to the same register in prose, and the choice to
      ship both is unmotivated.
    * The **draft** target must differ (the walk-through beat).
    """
    pt = dict(seed_policy_pt_pt._TRANSLATIONS)
    br = dict(seed_policy_pt_br._TRANSLATIONS)
    assert set(pt) == set(br), (
        "pt-PT and pt-BR must translate the same five source sentences")

    # Load-bearing lexical/orthographic markers
    pt_ocde = dict(seed_policy_pt_pt._ALIASES)["OCDE"]
    br_ocde = dict(seed_policy_pt_br._ALIASES)["OCDE"]
    assert "Económico" in pt_ocde, f"pt-PT OCDE lost its acute-e: {pt_ocde!r}"
    assert "Econômico" in br_ocde, f"pt-BR OCDE lost its circumflex-e: {br_ocde!r}"
    assert pt_ocde != br_ocde

    pt_currency_baseline = seed_policy_pt_pt._BASELINES[0][1]
    br_currency_baseline = seed_policy_pt_br._BASELINES[0][1]
    assert pt_currency_baseline.startswith("€"), (
        f"pt-PT currency baseline must lead with €: {pt_currency_baseline!r}")
    assert br_currency_baseline.startswith("R$"), (
        f"pt-BR currency baseline must lead with R$: {br_currency_baseline!r}")

    # Majority-differ on prose
    identical = [src for src in pt if pt[src] == br[src]]
    assert len(identical) <= 1, (
        f"pt-PT and pt-BR share too many translations to justify separate "
        f"seeds — {len(identical)}/5 are identical: {identical}")

    # Draft target must differ
    pt_draft = dict(seed_policy_pt_pt._DRAFTS)
    br_draft = dict(seed_policy_pt_br._DRAFTS)
    assert set(pt_draft) == set(br_draft), (
        "pt-PT and pt-BR must draft from the same source sentence")
    for src, pt_target in pt_draft.items():
        assert pt_target != br_draft[src], (
            f"the covenant-demonstration draft target must differ between "
            f"pt-PT and pt-BR — {src!r} produces {pt_target!r} in both")


# --- CLI wiring -------------------------------------------------------------

@pytest.mark.parametrize("scheme,expected_verifier", [
    ("policy-fr", seed_policy_fr.DEMO_VERIFIER),
    ("policy-pt-pt", seed_policy_pt_pt.DEMO_VERIFIER),
    ("policy-pt-br", seed_policy_pt_br.DEMO_VERIFIER),
    ("policy-ar", seed_policy_ar.DEMO_VERIFIER),
])
def test_nestor_demo_dispatches_the_right_seed(scheme, expected_verifier,
                                               tmp_path, monkeypatch):
    """``nestor demo --seed <scheme>`` must reach the correct module. If a
    wiring rewrite in ``nestor/cli.py`` accidentally routes ``policy-fr``
    to the Spanish seed, this test catches it before a demo goes out.
    """
    import argparse

    from nestor import cli

    db = tmp_path / f"nestor-demo-{scheme}.db"
    ledger = tmp_path / f"nestor-demo-{scheme}.ledger.jsonl"
    args = argparse.Namespace(
        db=str(db), ledger=str(ledger), json=False, seed=scheme,
    )
    cli.cmd_demo(args)

    # The store is closed by cmd_demo — reopen and read the verifier of any
    # sealed row. All sealed rows in a seed share the same verifier.
    reopened = SqliteStore(str(db))
    try:
        sealed = [p for p in reopened.memory_list() if p.get("status") == "sealed"]
    finally:
        reopened.close()
    assert sealed, f"nestor demo --seed {scheme} produced no sealed rows"
    assert sealed[0].get("verifier") == expected_verifier, (
        f"nestor demo --seed {scheme} dispatched to a seed whose verifier "
        f"is {sealed[0].get('verifier')!r}; expected {expected_verifier!r}")
