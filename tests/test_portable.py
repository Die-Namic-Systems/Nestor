"""Getting the memory out, and getting it back in without laundering trust.

The load-bearing property: a bundle is a *file*, and a file claiming
``status: sealed`` is making exactly the claim a seal signature exists to
distrust. Import must therefore apply the same rule the serve path does — a
seal is honored only if it verifies here — and demote what it cannot verify
rather than trusting it or dropping it.
"""
from __future__ import annotations

import os

import json

import pytest

from nestor import cascade, memory, portable, storage
from nestor.curator import Curator
from nestor.sqlite_store import SqliteStore

from conftest import read_ledger


def fresh_store():
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    return s


@pytest.fixture()
def source(tmp_path, seal_key):
    """An instance with something worth exporting."""
    os.environ['NESTOR_SEAL_KEY'] = 'shared-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = fresh_store()
    storage.set_store(s)
    memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                    status="sealed", verifier="rita", store=s)
    memory.add_pair("the monthly report", "el informe mensual", "en", "es",
                    status="sealed", verifier="sam", store=s)
    memory.add_pair("a draft phrase", "una frase", "en", "es", store=s)
    memory.reject_match("the annual invoices", "en", "es",
                        pair_id=s.memory_list(contains="annual")[0]["id"],
                        verifier="rita", reason="different year", store=s)
    return s


# --- export ----------------------------------------------------------------

def test_export_carries_pairs_rejections_signatures_and_a_digest(source):
    b = portable.export_bundle(source)
    assert b["nestor_bundle"] == portable.BUNDLE_VERSION
    assert b["counts"] == {"pairs": 3, "sealed": 2, "servable": 2, "rejections": 1}
    assert all(p["seal_sig"] for p in b["pairs"] if p["status"] == "sealed")
    json.dumps(b)                                   # must round-trip
    ok, detail = portable.verify_bundle(b)
    assert ok, detail


def test_an_edited_bundle_fails_its_digest(source):
    b = portable.export_bundle(source)
    b["pairs"][0]["target_text"] = "algo completamente distinto"
    ok, detail = portable.verify_bundle(b)
    assert not ok and "digest mismatch" in detail


def test_export_can_be_scoped_to_one_domain(source):
    from nestor.entity import EntityResolver
    EntityResolver(source, domain="company").seal("AMZN", "Amazon", verifier="analyst")
    everything = portable.export_bundle(source)
    just_es = portable.export_bundle(source, source_lang="en", target_lang="es")
    assert everything["counts"]["pairs"] == 4
    assert just_es["counts"]["pairs"] == 3


def test_csv_is_readable_and_says_what_it_drops(source):
    text = portable.pairs_csv(portable.export_bundle(source))
    assert "seal_sig" not in text, "a CSV round-trip must not look like it carries a seal"
    assert "servable" in text.splitlines()[0]
    assert "la factura anual" in text


# --- import ----------------------------------------------------------------

def test_a_bundle_moves_between_instances_that_share_a_key(source, tmp_path, seal_key):
    bundle = portable.export_bundle(source)
    destination = fresh_store()

    report = portable.import_bundle(bundle, store=destination, dry_run=False,
                                    verifier="ops")
    assert report["sealed"] == 2 and report["demoted"] == 0 and report["drafts"] == 1
    # And the imported seals genuinely serve — the signature verified here.
    assert memory.best_sealed("the annual invoice", "en", "es",
                              store=destination)["pair"]["verifier"] == "rita"
    assert report["rejections"] == 1
    assert memory.best_sealed("the annual invoices", "en", "es", store=destination) is None


def test_a_seal_that_does_not_verify_here_lands_as_a_draft(source, seal_key):
    """The whole point. A file's word is not a verification."""
    bundle = portable.export_bundle(source)
    bundle["pairs"].append({
        "id": "forged-1", "source_text": "wire the funds", "source_norm": "wire the funds",
        "source_lang": "en", "target_lang": "es", "target_text": "transfiera los fondos",
        "status": "sealed", "verifier": "mallory", "weight": 1.0, "origin": "",
        "created_at": "2026-01-01", "seal_sig": "not-a-real-signature",
    })
    bundle["digest"] = portable.digest(bundle["pairs"], bundle["rejections"])

    destination = fresh_store()
    with pytest.warns(RuntimeWarning, match="do not verify here"):
        report = portable.import_bundle(bundle, store=destination, dry_run=False)

    assert report["sealed"] == 2 and report["demoted"] == 1
    landed = destination.memory_find("wire the funds", "en", "es")
    assert landed["status"] == "draft", "an unverifiable seal is reviewed, not trusted"
    assert landed["seal_sig"] == "", "and it does not keep a signature to be reactivated"
    assert memory.best_sealed("wire the funds", "en", "es", store=destination) is None


def test_a_different_key_demotes_everything_rather_than_serving_it(source, seal_key):
    bundle = portable.export_bundle(source)
    os.environ['NESTOR_SEAL_KEY'] = 'a-different-instance-key'
    destination = fresh_store()
    with pytest.warns(RuntimeWarning):
        report = portable.import_bundle(bundle, store=destination, dry_run=False)
    assert report["sealed"] == 0 and report["demoted"] == 2
    assert Curator(destination).list(status="sealed") == []


def test_import_is_a_dry_run_until_told_otherwise(source):
    bundle = portable.export_bundle(source)
    destination = fresh_store()
    report = portable.import_bundle(bundle, store=destination)
    assert report["dry_run"] is True and report["sealed"] == 2
    assert destination.memory_list() == [], "a dry run writes nothing"


def test_a_disagreement_is_listed_not_resolved(source):
    destination = fresh_store()
    memory.add_pair("the annual invoice", "otra factura", "en", "es",
                    status="sealed", verifier="local-rita", store=destination)
    bundle = portable.export_bundle(source)

    report = portable.import_bundle(bundle, store=destination, dry_run=False,
                                    verifier="ops")
    assert len(report["conflicts"]) == 1
    conflict = report["conflicts"][0]
    assert conflict["here"]["target_text"] == "otra factura"
    assert conflict["incoming"]["target_text"] == "la factura anual"
    assert memory.best_sealed("the annual invoice", "en", "es",
                              store=destination)["pair"]["target_text"] == "otra factura"

    portable.import_bundle(bundle, store=destination, dry_run=False, verifier="ops",
                           override_conflicts=True)
    assert memory.best_sealed("the annual invoice", "en", "es",
                              store=destination)["pair"]["target_text"] == "la factura anual"


def test_importing_twice_changes_nothing_the_second_time(source):
    bundle = portable.export_bundle(source)
    destination = fresh_store()
    portable.import_bundle(bundle, store=destination, dry_run=False, verifier="ops")
    again = portable.import_bundle(bundle, store=destination, dry_run=False, verifier="ops")
    assert again["existing"] == 3 and again["sealed"] == 0 and again["conflicts"] == []


def test_the_chain_does_not_merge_but_the_import_is_recorded(source, tmp_path):
    bundle = portable.export_bundle(source)
    assert bundle["ledger"]["entries"], "the source chain travels for reading"
    destination = fresh_store()
    before = len(read_ledger())
    portable.import_bundle(bundle, store=destination, dry_run=False, verifier="ops")
    entries = read_ledger()
    assert len(entries) == before + 1, "one entry: the import itself, not the source's history"
    assert entries[-1]["kind"] == "bundle_import" and entries[-1]["verifier"] == "ops"
    from nestor.ledger import verify
    ok, detail = verify(str(tmp_path / "ledger.jsonl"))
    assert ok, detail


def test_junk_is_refused_with_a_reason(source):
    for junk, expected in [("not a bundle", "not a JSON object"),
                           ({"nestor_bundle": 99, "pairs": []}, "unsupported bundle version"),
                           ({"nestor_bundle": 1, "pairs": "nope"}, "must be lists"),
                           ({"nestor_bundle": 1, "pairs": [{"id": "x"}]}, "is missing")]:
        ok, detail = portable.verify_bundle(junk)
        assert not ok and expected in detail
        with pytest.raises(portable.BundleError):
            portable.import_bundle(junk, store=fresh_store())


def test_the_digest_survives_a_javascript_round_trip(source):
    """JS has one number type: JSON.parse turns 1.0 into 1 and writes it back as 1.

    The UI reads a bundle in the browser and posts it back, so a digest that
    depended on Python's float repr rejected payloads nobody had touched. An
    integrity check that cries wolf on a lossless round-trip is worse than none.
    """
    bundle = portable.export_bundle(source)
    as_javascript_saw_it = json.loads(
        json.dumps(bundle).replace('"weight": 1.0', '"weight": 1'))
    ok, detail = portable.verify_bundle(as_javascript_saw_it)
    assert ok, detail
    assert portable.digest(as_javascript_saw_it["pairs"],
                           as_javascript_saw_it["rejections"]) == bundle["digest"]


def test_the_digest_still_notices_an_actual_edit(source):
    bundle = portable.export_bundle(source)
    before = bundle["digest"]
    bundle["pairs"][0]["verifier"] = "mallory"
    assert portable.digest(bundle["pairs"], bundle["rejections"]) != before
