"""A custom domain, reached from a process rather than from a host (IDEAS §6.41).

§6.40 gave `ui.App` a matcher, which works because a host constructs it in
Python. `nestor serve` and `nestor ask` *are* the process — there is no earlier
moment at which anyone could call `memory.set_matcher()`, and a shipped name off
a command line cannot conjure a class nobody shipped. So a custom domain could
not use either surface at all: a model asking over MCP got `pending` for a
phrase a human had just sealed through the fixed UI, and the terminal did the
same.

`answer.load_matcher` closes it with an import spec. These tests pin the loader's
refusals (a matcher that fails the seam must fail at startup, not at the first
query) and then drive the two surfaces end to end with a matcher no shipped name
could name.
"""
from __future__ import annotations

import os

import pytest

from nestor import answer, cascade, memory, serve, storage
from nestor.matcher import StringMatcher
from nestor.sqlite_store import SqliteStore

DOMAIN = "incident"
REPORT = "Pump SN CH-4471 over-delivered on the night run."
RESTATED = "CH4471 free-flow, ward 6, sister's report."
ADJUDICATION = "Free-flow on the giving set. Reportable under MDR Annex VII."


class SerialMatcher:
    """The documented two-method seam, and nothing else — no optional score()."""

    name = "serial"

    def normalize(self, text: str) -> str:
        digits = "".join(ch for ch in str(text).upper() if ch.isalnum())
        marker = digits.find("CH")
        return digits[marker:marker + 6] if marker >= 0 else digits[:6]

    def similarity(self, a: str, b: str) -> float:
        return 1.0 if a and a == b else 0.0


SERIALS = SerialMatcher()


def _make() -> SerialMatcher:
    return SerialMatcher()


class NotAMatcher:
    """Has one half of the seam. The half that is missing is the point."""

    def normalize(self, text: str) -> str:
        return str(text)


# ── the loader ──────────────────────────────────────────────────────────────

def test_a_shipped_name_still_works():
    from nestor.matcher import NumericMatcher

    assert isinstance(answer.load_matcher("numeric"), NumericMatcher)


def test_string_defers_rather_than_constructing_one():
    """`None` means 'use the process-wide matcher'. Building a StringMatcher
    would silently override a host that installed its own."""
    assert answer.load_matcher("string") is None
    assert answer.load_matcher("") is None


def test_an_import_spec_resolves_a_module_attribute():
    got = answer.load_matcher(f"{__name__}:SERIALS")
    assert got is SERIALS
    assert got.normalize(REPORT) == "CH4471"


def test_an_import_spec_resolves_a_class():
    got = answer.load_matcher(f"{__name__}:SerialMatcher")
    assert isinstance(got, SerialMatcher), "a class should be called with no arguments"


def test_an_import_spec_resolves_a_factory():
    assert isinstance(answer.load_matcher(f"{__name__}:_make"), SerialMatcher)


def test_an_unimportable_module_is_refused_with_the_spec_in_the_message():
    with pytest.raises(ValueError, match="cannot import"):
        answer.load_matcher("no.such.module:MATCHER")


def test_a_missing_attribute_is_refused():
    with pytest.raises(ValueError, match="has no attribute"):
        answer.load_matcher(f"{__name__}:NoSuchName")


def test_something_that_is_not_a_matcher_is_refused_at_load_time():
    """Not at the first query. By then the operator has been told it started."""
    with pytest.raises(ValueError, match="similarity"):
        answer.load_matcher(f"{__name__}:NotAMatcher")


def test_a_malformed_spec_says_what_the_shape_is():
    with pytest.raises(ValueError, match="module:attribute"):
        answer.load_matcher("acme.incidents:")


def test_an_unknown_bare_name_is_still_refused_rather_than_defaulted():
    with pytest.raises(ValueError, match="unknown matcher"):
        answer.load_matcher("vector")


# ── the MCP surface ─────────────────────────────────────────────────────────

@pytest.fixture()
def sealed_store(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    memory.add_pair(REPORT, ADJUDICATION, DOMAIN, DOMAIN, status="sealed",
                    verifier="ines", store=store, matcher=SERIALS)
    return store


def test_a_model_asking_gets_the_seal_a_human_made(sealed_store):
    """§6.41's measured consequence: `pending` for a phrase a human sealed."""
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                          matcher=SERIALS)
    out = server.call("nestor_ask", {"text": RESTATED})
    assert out["verified"] is True, "the model was told pending for a sealed phrase"
    assert out["passage"]["state"] == "sealed"
    assert out["passage"]["meta"]["verifier"] == "ines"


def test_without_the_matcher_the_model_is_told_pending(sealed_store):
    """The control. This is what every custom domain got before this change."""
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN)
    out = server.call("nestor_ask", {"text": RESTATED})
    assert out["verified"] is False
    assert out["passage"]["state"] == "pending"


def test_nestor_match_scores_with_the_servers_matcher(sealed_store):
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                          matcher=SERIALS)
    out = server.call("nestor_match", {"text": RESTATED})
    assert out["normalized"] == "CH4471"
    assert out["served"] is True
    assert out["matcher"] == "serial"


def test_nestor_match_refuses_a_matcher_name_that_disagrees(sealed_store):
    """A model is less able than a human to notice a confidently wrong answer."""
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                          matcher=SERIALS)
    with pytest.raises(ValueError, match="cannot score 'numeric'"):
        server.call("nestor_match", {"text": REPORT, "matcher": "numeric"})


def test_nestor_match_honours_a_name_that_agrees(sealed_store):
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                          matcher=SERIALS)
    out = server.call("nestor_match", {"text": REPORT, "matcher": "serial"})
    assert out["served"] is True


def test_the_servers_matcher_describes_the_servers_domain_and_no_other(sealed_store):
    """Same rule as ui.App, and it is here because the same mistake was
    available: every tool takes per-call domain tags."""
    memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                    status="sealed", verifier="rita", store=sealed_store)
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                          matcher=SERIALS)
    assert server.domain_matcher(DOMAIN, DOMAIN) is SERIALS
    assert server.domain_matcher("en", "es") is None
    out = server.call("nestor_ask", {"text": "the annual invoice",
                                     "source_lang": "en", "target_lang": "es"})
    assert out["verified"] is True, (
        "a foreign-domain ask was scored with the incident matcher and missed")


def test_propose_needs_no_matcher(sealed_store):
    """It writes a segment, not a pair — nothing is keyed, so nothing to get
    wrong. Pinned so a future change that starts keying here is noticed."""
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                          matcher=SERIALS)
    out = server.call("nestor_propose", {"source_text": "CH-9002 stalled.",
                                         "candidate": "Motor stall."})
    assert out["segment_id"]
    assert not sealed_store.memory_candidates(DOMAIN, DOMAIN) or all(
        r["source_norm"] != "CH9002" for r in sealed_store.memory_candidates(DOMAIN, DOMAIN))


# ── the flags that reach them ───────────────────────────────────────────────

def test_serve_accepts_a_custom_matcher_spec():
    args = serve.build_parser().parse_args(["--matcher", f"{__name__}:SERIALS"])
    assert answer.load_matcher(args.matcher) is SERIALS


def test_serve_defaults_to_deferring():
    assert answer.load_matcher(serve.build_parser().parse_args([]).matcher) is None


def test_the_ui_and_the_cli_take_the_same_spec():
    """One sentence for a user to learn, and one loader to get wrong."""
    from nestor import cli, ui

    for parser, argv in ((ui.build_parser(), ["--matcher", f"{__name__}:SERIALS"]),
                         (cli.build_parser(), ["ask", "x", "--matcher", f"{__name__}:SERIALS"]),
                         (cli.build_parser(), ["match", "x", "--matcher", f"{__name__}:SERIALS"])):
        assert answer.load_matcher(parser.parse_args(argv).matcher) is SERIALS


def test_the_ui_no_longer_restricts_the_flag_to_shipped_names():
    """It used to be `choices=answer.MATCHERS`, which made a custom matcher
    unnameable at the one surface that could already take one."""
    from nestor import ui

    args = ui.build_parser().parse_args(["--matcher", f"{__name__}:SERIALS"])
    assert args.matcher == f"{__name__}:SERIALS"


def test_a_bad_spec_refuses_to_start_rather_than_raising(tmp_path, capsys):
    """A traceback out of a stdio server is a broken pipe to whatever launched
    it; a message is something an operator can act on."""
    rc = serve.main(["--db", str(tmp_path / "n.db"), "--matcher", "no.such:THING"])
    assert rc == 2
    assert "refusing to start" in capsys.readouterr().err


def test_the_process_wide_matcher_is_still_honoured_when_no_flag_is_given(sealed_store):
    """`--matcher string` defers, so a library caller that set one keeps it."""
    was = memory.get_matcher()
    memory.set_matcher(SERIALS)
    try:
        server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                              matcher=answer.load_matcher("string"))
        out = server.call("nestor_ask", {"text": RESTATED})
        assert out["verified"] is True
    finally:
        memory.set_matcher(was)
    assert isinstance(memory.get_matcher(), StringMatcher)
