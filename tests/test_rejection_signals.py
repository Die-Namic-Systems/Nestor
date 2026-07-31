"""Reading the rejections back (IDEAS 1.2, the "remaining" line).

Serving consumes rejections one at a time: not this answer, for this query.
In aggregate the same records say two further things, and nothing asked.
"""
import pytest

from nestor import memory
from nestor.cli import main as cli_main
from nestor.curator import Curator
from nestor.ui import App, dispatch


@pytest.fixture
def rejected(store):
    """One query refused three times; one pair refused for four queries."""
    for src, tgt in [
        ("the invoice is overdue", "la factura está vencida"),
        ("the payment is overdue", "el pago está vencido"),
        ("kindly remit payment", "sírvase remitir el pago"),
    ]:
        memory.add_pair(src, tgt, "en", "es", status="sealed", verifier="rita", store=store)
    junk = memory.add_pair("terms and conditions apply", "aplican términos",
                           "en", "es", status="sealed", verifier="rita", store=store)

    # One query, three different answers, all wrong: the threshold is letting
    # too much through for this domain.
    for target in ("la factura está vencida", "el pago está vencido",
                   "sírvase remitir el pago"):
        memory.reject_match("the account is in arrears", "en", "es",
                            target_text=target, verifier="sam",
                            reason="not what this says", store=store)

    # One pair, four unrelated queries: the pair is junk.
    for query in ("shipping notice", "delivery window", "payment terms", "late fee"):
        memory.reject_match(query, "en", "es", pair_id=junk["id"],
                            verifier="sam", reason="irrelevant", store=store)
    return junk


def test_a_repeatedly_refused_query_is_reported(store, rejected):
    out = Curator(store, "en", "es").rejection_signals()
    hot = [q for q in out["queries"] if q["query_norm"] == "the account is in arrears"]
    assert len(hot) == 1
    assert hot[0]["rejections"] == 3
    assert hot[0]["distinct_answers"] == 0, "rejected by target text, not by pair id"
    assert hot[0]["verifiers"] == ["sam"]


def test_a_pair_refused_for_many_queries_is_reported_with_its_row(store, rejected):
    out = Curator(store, "en", "es").rejection_signals()
    junk = [p for p in out["pairs"] if p["pair_id"] == rejected["id"]]
    assert len(junk) == 1
    assert junk[0]["queries"] == 4
    assert junk[0]["source_text"] == "terms and conditions apply"
    assert junk[0]["status"] == "sealed" and junk[0]["servable"] is True, (
        "the point: it is still being served while four reviewers refused it")


def test_the_thresholds_are_the_caller_s(store, rejected):
    c = Curator(store, "en", "es")
    assert c.rejection_signals(min_query=4)["queries"] == []
    assert c.rejection_signals(min_pair=5)["pairs"] == []
    # min=1 reports everything, including the single-rejection noise the
    # defaults exist to keep out.
    assert len(c.rejection_signals(min_query=1)["queries"]) == 5


def test_a_quiet_memory_reports_nothing_rather_than_guessing(store):
    memory.add_pair("hola", "hello", "es", "en", status="sealed",
                    verifier="rita", store=store)
    out = Curator(store, "es", "en").rejection_signals()
    assert out == {"queries": [], "pairs": [], "rejections": 0,
                   "domain": {"source_lang": "es", "target_lang": "en"},
                   "thresholds": {"min_query": 2, "min_pair": 2}}


def test_signals_are_scoped_to_the_curator_s_domain(store, rejected):
    memory.add_pair("guten tag", "buenos días", "de", "es", status="sealed",
                    verifier="rita", store=store)
    for _ in range(3):
        memory.reject_match("guten morgen", "de", "es", target_text="buenos días",
                            verifier="sam", reason="no", store=store)

    en = Curator(store, "en", "es").rejection_signals()
    assert all(q["query_norm"] != "guten morgen" for q in en["queries"])
    de = Curator(store, "de", "es").rejection_signals()
    assert [q["query_norm"] for q in de["queries"]] == ["guten morgen"]
    # And a curator over every domain sees both.
    every = Curator(store).rejection_signals()
    assert len(every["queries"]) == 2


def test_a_retired_pair_still_reports_but_says_it_is_gone(store, rejected):
    memory.reject_pair(rejected["id"], verifier="sam", reason="junk", store=store)
    out = Curator(store, "en", "es").rejection_signals()
    junk = [p for p in out["pairs"] if p["pair_id"] == rejected["id"]][0]
    assert junk["status"] == "rejected" and junk["servable"] is False


def test_the_ui_serves_the_same_answer(store, rejected):
    app = App(store=store, source_lang="en", target_lang="es")
    status, out = dispatch(app, "GET", "/api/rejections", {})
    assert status == 200
    assert out["pairs"][0]["pair_id"] == rejected["id"]
    assert [q["query_norm"] for q in out["queries"]] == ["the account is in arrears"]


def test_the_cli_reports_it(store, rejected, tmp_path, capsys, seal_key):
    from nestor import cascade

    db = tmp_path / "nestor.db"
    ledger = cascade._ledger_path()
    assert cli_main([
        "--db", str(db), "--ledger", str(ledger),
        "rejections", "--from", "en", "--to", "es",
    ]) == 0
    out = capsys.readouterr().out
    assert "the account is in arrears" in out
    assert "terms and conditions apply" in out
