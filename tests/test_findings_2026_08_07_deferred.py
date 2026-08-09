"""Regressions for IDEAS.md §6.92 — the three findings the §6.40/§6.41 audits
deferred into merged-PR prose, filed into the queue on 2026-08-07.

Finding 3 is a genuine bug, unrelated to the matcher work: ``memory.add_pair``'s
race-retry re-called itself without forwarding ``reason=``. A seal that lost the
insert race therefore had its rationale silently dropped — and, worse, skipped
the ``memory_set_reason`` refusal path a store lacking the op is supposed to hit.

Written against the *unfixed* revision first and observed to fail (the sealed row
came back with an empty ``reason``), per the house rule that a test which passes
before the fix is a description, not a gate.
"""
from __future__ import annotations

import json
import os

import pytest

from nestor import cascade, cli, memory, portable, serve, storage, ui
from nestor.matcher import NumericMatcher, StringMatcher
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def signed(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'shared-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    return tmp_path


def fresh(path=":memory:"):
    s = SqliteStore(path)
    s.init_db()
    s.memory_init()
    return s


def test_a_seal_that_loses_the_insert_race_keeps_its_reason(signed, tmp_path):
    """The winner lands a draft; the loser retries, upgrades that draft to a
    seal, and its ``reason`` must ride along. The retry dropped it.

    The race is made deterministic by lying to the first ``memory_find``: it
    reports nothing, so the seal takes the insert path and collides with the
    draft already in the store — the exact window ``add_pair`` retries around.
    """
    store = fresh(str(tmp_path / "race.db"))
    storage.set_store(store)

    # The winner of the race: a draft for the source, already committed.
    memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                    status="draft", store=store)

    real_find = store.memory_find
    calls = {"n": 0}

    def find_that_hides_the_first_time(norm, source_lang, target_lang):
        calls["n"] += 1
        if calls["n"] == 1:
            return None            # the check-then-write window, forced open
        return real_find(norm, source_lang, target_lang)

    store.memory_find = find_that_hides_the_first_time
    try:
        memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                        status="sealed", verifier="rita",
                        reason="confirmed against the signed PO", store=store)
    finally:
        store.memory_find = real_find

    row = store.memory_find(memory._norm("the annual invoice"), "en", "es")
    assert row["status"] == "sealed"
    assert row["reason"] == "confirmed against the signed PO", (
        "a seal that lost the insert race dropped its recorded reason on retry")


# --- Finding 1: a bundle carries a domain's tags but not its matcher -------
#
# A domain is its tags AND its matcher (§6.40): the source_norm a seal is signed
# over is the matcher's output, so a bundle keyed by one matcher landing in a
# domain keyed by another lands sealed rows in a key space the destination never
# computes — and, before this, reported {"sealed": n} with no warning. The fix
# records an advisory matcher label in the bundle and warns on mismatch at
# import; it never refuses (the label is not a stable identifier) and never
# re-normalizes (that would invalidate every seal signature in transit).


def test_export_records_the_matcher_that_keyed_the_bundle(signed):
    store = fresh()
    storage.set_store(store)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", verifier="rita",
                    store=store)
    bundle = portable.export_bundle(store)
    assert bundle["matcher"] == "StringMatcher"
    # Advisory, and outside the digest: recomputing the digest without it must
    # still verify, or the label would be an integrity field it cannot be.
    ok, _ = portable.verify_bundle(bundle)
    assert ok


def test_import_under_a_different_matcher_warns_but_still_lands(signed):
    src = fresh()
    storage.set_store(src)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", verifier="rita",
                    store=src)
    bundle = portable.export_bundle(src)

    dst = fresh()
    with pytest.warns(RuntimeWarning, match="keyed by"):
        report = portable.import_bundle(bundle, store=dst, dry_run=False,
                                        verifier="ops", matcher=NumericMatcher())

    assert report["matcher_mismatch"] is True
    assert report["source_matcher"] == "StringMatcher"
    assert report["dest_matcher"] == "NumericMatcher"
    # Warned, NOT refused: the rows are trusted verbatim and land, because
    # re-normalizing would break the seal signature they carry.
    assert report["sealed"] == 1
    assert dst.memory_find(memory._norm("hello"), "en", "es") is not None


def test_import_under_the_same_matcher_is_silent(signed, recwarn):
    src = fresh()
    storage.set_store(src)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", verifier="rita",
                    store=src)
    bundle = portable.export_bundle(src)

    dst = fresh()
    report = portable.import_bundle(bundle, store=dst, dry_run=False,
                                    verifier="ops", matcher=StringMatcher())
    assert report["matcher_mismatch"] is False
    assert not [w for w in recwarn.list if "keyed by" in str(w.message)]


def test_a_legacy_bundle_without_a_matcher_label_does_not_false_alarm(signed, recwarn):
    """A bundle written before this field existed carries no matcher label.
    Unknown is not a mismatch — it must import without a warning, or every
    pre-existing bundle would cry wolf on first import."""
    src = fresh()
    storage.set_store(src)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", verifier="rita",
                    store=src)
    bundle = portable.export_bundle(src)
    bundle.pop("matcher")                       # as an older exporter left it

    dst = fresh()
    report = portable.import_bundle(bundle, store=dst, dry_run=False,
                                    verifier="ops", matcher=NumericMatcher())
    assert report["source_matcher"] == ""
    assert report["matcher_mismatch"] is False
    assert not [w for w in recwarn.list if "keyed by" in str(w.message)]


# --- Finding 1, the wiring an audit caught -------------------------------
#
# The portable mechanism above is only honest if the matcher LABEL reaches it
# on the surfaces people actually use. An audit found it did not: the UI's
# "Export bundle" button sends no domain tags, so `_domain_matcher("","")`
# returned None and a custom-matcher surface relabelled its OWN rows with the
# process default — the mislabel this finding closes, arriving on the export
# side. The CLI export/import had no `--matcher` at all, so they always used the
# process default. Both are gated below; each fails on the pre-wiring revision.


def test_ui_export_button_labels_with_the_surface_matcher(signed, tmp_path):
    """The bare button is a whole-store export with no tags. A surface keyed by
    a custom matcher must label its own rows with THAT matcher, not the default."""
    store = fresh(str(tmp_path / "num.db"))
    storage.set_store(store)
    memory.add_pair("pay 1000 USD", "x", "num", "num", status="sealed",
                    verifier="rita", matcher=NumericMatcher(), store=store)
    app = ui.App(store=store, source_lang="num", target_lang="num",
                 matcher=NumericMatcher(), db_path=":memory:")
    bundle = ui._bundle(app, {}, {})                 # the button: empty query
    assert bundle["matcher"] == "NumericMatcher"


def test_ui_export_scoped_to_a_foreign_domain_still_defers(signed, tmp_path):
    """The fix must not lend the surface's matcher LABEL to a domain it does not
    key — the §6.40 guard, on the label. A request explicitly about another
    domain defers to the process default, exactly as `_domain_matcher` does."""
    store = fresh(str(tmp_path / "f.db"))
    storage.set_store(store)
    app = ui.App(store=store, source_lang="en", target_lang="es",
                 matcher=NumericMatcher(), db_path=":memory:")
    bundle = ui._bundle(app, {"source_lang": "fr", "target_lang": "de"}, {})
    assert bundle["matcher"] == "StringMatcher"


def test_cli_export_matcher_flag_labels_the_bundle(signed, tmp_path):
    db = tmp_path / "cli.db"
    store = fresh(str(db))
    memory.add_pair("pay 1000 USD", "x", "num", "num", status="sealed",
                    verifier="rita", matcher=NumericMatcher(), store=store)
    store.close()
    out = tmp_path / "b.json"
    cli.main(["--db", str(db), "--ledger", str(tmp_path / "ledger.jsonl"),
              "export", "--matcher", "numeric", "--out", str(out)])
    bundle = json.loads(out.read_text())
    assert bundle["matcher"] == "NumericMatcher"


def test_cli_import_matcher_flag_reports_a_mismatch(signed, tmp_path, capsys):
    src = fresh()
    storage.set_store(src)
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=src)
    bundle = portable.export_bundle(src)                 # labelled StringMatcher
    assert bundle["matcher"] == "StringMatcher"
    path = tmp_path / "b.json"
    path.write_text(json.dumps(bundle))

    code = cli.main(["--db", str(tmp_path / "dst.db"),
                     "--ledger", str(tmp_path / "led.jsonl"), "--json", "import",
                     str(path), "--apply", "--verifier", "ops",
                     "--matcher", "numeric"])
    report = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert report["matcher_mismatch"] is True
    assert report["source_matcher"] == "StringMatcher"
    assert report["dest_matcher"] == "NumericMatcher"


# --- Finding 2: a case-only near-miss refuses instead of falling back -----
#
# `ui._domain_matcher` and `serve.Server.domain_matcher` decided "is this
# request about my domain?" with `==`. A caller sending `Incident` against a
# surface configured `incident` failed that check and fell through to `None`
# — the process-wide matcher — which answered `pending` rather than refusing:
# the §6.40 failure, reachable by a capitalisation typo, and just as silent.
#
# Case-folding the tags themselves was rejected (decision 0076): a store may
# hold two domains that differ only in case, and folding would merge them.
# Instead: a NEAR-MISS — both tags equal to the surface's own under
# case-folding, but not exactly — is refused, naming the surface's real
# domain. A GENUINELY different domain (one tag doesn't even agree
# case-insensitively) still defers to the process-wide matcher exactly as
# before — the §6.40 guard these tests exist to keep from being broken by
# this fix's own over-reach.

DOMAIN2 = "incident"


def _incident_pair(store, matcher):
    """A sealed row under the correctly-cased domain, so a near-miss test can
    show it stays unreachable rather than merely absent."""
    memory.add_pair("pump SN CH-4471 over-delivered", "acknowledged, escalated",
                    DOMAIN2, DOMAIN2, status="sealed", verifier="ines",
                    store=store, matcher=matcher)


def test_ui_near_miss_refuses_and_writes_nothing(signed, tmp_path):
    store = fresh(str(tmp_path / "ui-nearmiss.db"))
    storage.set_store(store)
    app = ui.App(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                 matcher=StringMatcher(), db_path=":memory:")
    status, out = ui.dispatch(
        app, "POST", "/api/seal", {},
        {"source": "a brand new incident", "target": "acknowledged",
         "source_lang": "Incident", "target_lang": "Incident", "verifier": "rita"})
    assert status == 400
    assert out["code"] == "domain_case_mismatch"
    assert "incident" in out["error"] and "Incident" in out["error"]
    # The refusal happened before `add_pair` ran at all — nothing landed under
    # either casing, and the store's row count did not move.
    assert memory.stats(store=store)["total"] == 0
    assert store.memory_find(memory._norm("a brand new incident"),
                             "Incident", "Incident") is None
    assert store.memory_find(memory._norm("a brand new incident"),
                             DOMAIN2, DOMAIN2) is None


def test_ui_domain_matcher_near_miss_raises_apierror(signed, tmp_path):
    store = fresh(str(tmp_path / "ui-nm2.db"))
    app = ui.App(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                 matcher=StringMatcher(), db_path=":memory:")
    with pytest.raises(ui.ApiError, match="only in case") as excinfo:
        ui._domain_matcher(app, "Incident", "Incident")
    assert excinfo.value.status == 400
    assert excinfo.value.code == "domain_case_mismatch"


def test_ui_domain_matcher_exact_match_still_returns_the_apps_matcher(signed, tmp_path):
    store = fresh(str(tmp_path / "ui-exact.db"))
    matcher = StringMatcher()
    app = ui.App(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                 matcher=matcher, db_path=":memory:")
    assert ui._domain_matcher(app, DOMAIN2, DOMAIN2) is matcher


def test_ui_domain_matcher_genuinely_different_domain_still_defers(signed, tmp_path):
    """The §6.40 guard: a request about a REAL other domain — not a case
    variant of this one — must still get `None`, not a refusal."""
    store = fresh(str(tmp_path / "ui-diff.db"))
    app = ui.App(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                 matcher=NumericMatcher(), db_path=":memory:")
    assert ui._domain_matcher(app, "en", "es") is None
    # One tag agrees case-insensitively, the other genuinely differs — a
    # near-miss requires BOTH, so this is still a different domain.
    assert ui._domain_matcher(app, "Incident", "es") is None


def test_ui_reject_match_end_to_end_near_miss_also_refuses(signed, tmp_path):
    """`/api/reject-match` is the endpoint §6.40 itself was about (shared by
    every recipe) — pinned separately because it is the one this fix must not
    weaken back into a silent fall-back."""
    store = fresh(str(tmp_path / "ui-rm.db"))
    storage.set_store(store)
    matcher = StringMatcher()
    _incident_pair(store, matcher)
    app = ui.App(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                 matcher=matcher, db_path=":memory:")
    status, out = ui.dispatch(
        app, "POST", "/api/reject-match", {},
        {"source": "pump SN CH-4471 over-delivered",
         "source_lang": "Incident", "target_lang": "Incident", "verifier": "rita"})
    assert status == 400
    assert out["code"] == "domain_case_mismatch"


def test_serve_domain_matcher_near_miss_raises_valueerror(signed, tmp_path):
    store = fresh(str(tmp_path / "srv-nm.db"))
    server = serve.Server(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                          matcher=StringMatcher())
    with pytest.raises(ValueError, match="only in case"):
        server.domain_matcher("Incident", "Incident")


def test_serve_domain_matcher_exact_match_still_returns_the_servers_matcher(signed, tmp_path):
    store = fresh(str(tmp_path / "srv-exact.db"))
    matcher = StringMatcher()
    server = serve.Server(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                          matcher=matcher)
    assert server.domain_matcher(DOMAIN2, DOMAIN2) is matcher


def test_serve_domain_matcher_genuinely_different_domain_still_defers(signed, tmp_path):
    store = fresh(str(tmp_path / "srv-diff.db"))
    server = serve.Server(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                          matcher=NumericMatcher())
    assert server.domain_matcher("en", "es") is None
    assert server.domain_matcher("Incident", "es") is None


def test_serve_tool_call_near_miss_becomes_an_error_result_not_a_crash(signed, tmp_path):
    """Through `handle()`, the way a model actually reaches this: the refusal
    must arrive as an `isError` tool result a model can read, not a JSON-RPC
    protocol error and not a traceback — and nothing gets written."""
    store = fresh(str(tmp_path / "srv-e2e.db"))
    storage.set_store(store)
    server = serve.Server(store=store, source_lang=DOMAIN2, target_lang=DOMAIN2,
                          matcher=StringMatcher())
    response = server.handle({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "nestor_ask",
                   "arguments": {"text": "a brand new incident",
                                 "source_lang": "Incident", "target_lang": "Incident"}}})
    assert "error" not in response
    result = response["result"]
    assert result["isError"] is True
    assert "only in case" in result["content"][0]["text"]
    assert memory.stats(store=store)["total"] == 0
    # `answer.ask` -> `cascade.translate_segment` appends a ledger passage on
    # every path that actually runs the cascade; the refusal must pre-empt
    # that too, or "writes nothing" would be true of the pairs table only.
    ledger_path = cascade._ledger_path()
    assert not ledger_path.exists() or ledger_path.read_text() == ""
