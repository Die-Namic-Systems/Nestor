"""Calibration: the measured threshold numbers, finally consumed.

IDEAS §1.3 swept the threshold across corpora and found no value that is both
safe and useful everywhere — then the numbers sat in bench/results/ with nothing
reading them. This measures the same trade against the memory a deployment
actually has.
"""

import os
import pytest

from nestor import calibrate, memory
from nestor.cli import main as cli_main


def seal(store, source, target, verifier="rita"):
    return memory.add_pair(source, target, "en", "es", status="sealed",
                           verifier=verifier, store=store)


@pytest.fixture
def distinct(store):
    """A corpus whose sealed pairs do not resemble each other."""
    for src, tgt in [
        ("the invoice is overdue", "la factura está vencida"),
        ("shipping confirmation attached", "confirmación de envío adjunta"),
        ("please update your address", "por favor actualice su dirección"),
        ("the warranty expires in June", "la garantía vence en junio"),
        ("we received your complaint", "hemos recibido su queja"),
    ]:
        seal(store, src, tgt)
    return store


@pytest.fixture
def colliding(store):
    """Sealed sources that read alike and mean different things.

    This is what a false seal *is*, and here both sides were deliberately
    verified by a human — so it is not a hypothetical, it is already in the
    memory and already servable.
    """
    for src, tgt in [
        ("the payment is due on the first of the month", "el pago vence el primero del mes"),
        ("the payment is due on the first of the year", "el pago vence el primero del año"),
        ("the payment was due on the first of the month", "el pago venció el primero del mes"),
        ("the invoice is due on the first of the month", "la factura vence el primero del mes"),
    ]:
        seal(store, src, tgt)
    return store


def test_a_clean_corpus_needs_no_more_than_the_shipped_threshold(distinct):
    out = calibrate.calibrate(distinct, "en", "es", sample=0)
    assert out["corpus"] == 5 and out["sampled"] == 5
    assert out["current_rate"] == 0.0
    assert out["recommended"] == min(r["threshold"] for r in out["sweep"]), (
        "nothing collides even at the loosest cutoff, so the loosest is enough")
    assert out["examples"] == []


def test_a_colliding_corpus_reports_the_pairs_and_the_rate(colliding):
    out = calibrate.calibrate(colliding, "en", "es", sample=0)
    assert out["current_rate"] > 0, "0.92 already serves the wrong verified answer here"
    top = out["examples"][0]
    assert top["source"] != top["collides_with"]
    assert top["would_serve"] != top["target"], "a collision is a *different* answer"
    assert top["score"] >= out["floor"]


def test_the_recommendation_is_the_cheapest_cutoff_that_meets_the_target(colliding):
    out = calibrate.calibrate(colliding, "en", "es", target_rate=0.0, sample=0)
    rates = {r["threshold"]: r["collision_rate"] for r in out["sweep"]}
    if out["recommended"] is not None:
        assert rates[out["recommended"]] == 0.0
        lower = [t for t in rates if t < out["recommended"]]
        assert all(rates[t] > 0.0 for t in lower), "a cheaper cutoff would have done"


def test_an_unseparable_corpus_says_so_rather_than_recommending_a_number(store):
    """Two verified pairs one word apart, meaning different things. No cutoff
    below 1.0 separates them, and pretending otherwise would be the whole
    failure this package exists to avoid."""
    seal(store, "please transfer the outstanding balance of the quarterly invoice "
                "to account number 4471",
         "transfiera el saldo pendiente de la factura trimestral a la cuenta 4471")
    seal(store, "please transfer the outstanding balance of the quarterly invoice "
                "to account number 4472",
         "transfiera el saldo pendiente de la factura trimestral a la cuenta 4472")
    out = calibrate.calibrate(store, "en", "es", target_rate=0.0, sample=0)
    assert out["recommended"] is None
    assert "no cutoff separates them" in calibrate.summarize(out)


def test_a_duplicate_is_not_a_collision(store):
    """Two sources that score alike and give the SAME answer are a duplicate.
    Serving either is correct, and counting it would inflate the rate with rows
    nobody should change."""
    seal(store, "the invoice is overdue", "la factura está vencida")
    seal(store, "the invoice is over due", "la factura está vencida")
    out = calibrate.calibrate(store, "en", "es", sample=0)
    assert out["current_rate"] == 0.0 and out["examples"] == []


def test_only_servable_seals_are_measured(store, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'k'
    forged = seal(store, "the payment is due on the first of the month",
                  "el pago vence el primero del mes")
    seal(store, "the payment is due on the first of the year",
         "el pago vence el primero del año")
    store.memory_seal(forged["id"], forged["target_text"], "rita", 1.0, "deadbeef")
    out = calibrate.calibrate(store, "en", "es", sample=0)
    assert out["corpus"] == 1, "a row that would not be served cannot cause a false seal"


def test_sampling_is_deterministic_and_bounded(distinct):
    a = calibrate.calibrate(distinct, "en", "es", sample=3, seed=7)
    b = calibrate.calibrate(distinct, "en", "es", sample=3, seed=7)
    assert a["sampled"] == 3 and a["sweep"] == b["sweep"]


def test_an_empty_domain_says_there_is_nothing_to_calibrate(store):
    out = calibrate.calibrate(store, "en", "es")
    assert out["corpus"] == 0 and out["recommended"] is not None
    assert "nothing to calibrate" in calibrate.summarize(out)


def test_the_cli_exits_non_zero_when_no_threshold_is_safe(store, tmp_path, capsys, seal_key):
    from nestor import cascade

    seal(store, "please transfer the outstanding balance of the quarterly invoice "
                "to account number 4471",
         "transfiera el saldo pendiente de la factura trimestral a la cuenta 4471")
    seal(store, "please transfer the outstanding balance of the quarterly invoice "
                "to account number 4472",
         "transfiera el saldo pendiente de la factura trimestral a la cuenta 4472")
    db = tmp_path / "nestor.db"
    ledger = cascade._ledger_path()

    assert cli_main([
        "--db", str(db), "--ledger", str(ledger),
        "calibrate", "--from", "en", "--to", "es", "--target", "0",
    ]) == 1
    assert "no cutoff separates them" in capsys.readouterr().out
