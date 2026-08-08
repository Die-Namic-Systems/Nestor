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


# ── the wiring the flags actually go through ────────────────────────────────
#
# Found by audit: every test above either exercised `load_matcher` or handed a
# Server a matcher in Python — both of which already worked. The user-visible
# half (cmd_ask, cmd_match, serve.main) had NO coverage, and all three flags
# could be made inert without a single test going red. These drive the entry
# points, so deleting the wiring fails the build.

def _cli_store(tmp_path, matcher, source=REPORT, target=ADJUDICATION):
    from nestor import storage
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(str(tmp_path / "n.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    memory.add_pair(source, target, DOMAIN, DOMAIN, status="sealed",
                    verifier="ines", store=store, matcher=matcher)
    return store


def test_cmd_ask_honours_the_matcher_flag(tmp_path, seal_key, capsys):
    from nestor import cli

    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    _cli_store(tmp_path, SERIALS)
    argv = ["--db", str(tmp_path / "n.db"), "--json",
            "ask", RESTATED, "--from", DOMAIN, "--to", DOMAIN]

    rc = cli.main(argv + ["--matcher", f"{__name__}:SERIALS"])
    assert rc == 0, "nestor ask --matcher did not reach the seal"
    assert '"verified": true' in capsys.readouterr().out.lower()

    assert cli.main(argv) == 1, "the control must miss — otherwise this proves nothing"


def test_cmd_match_honours_the_matcher_flag(tmp_path, seal_key, capsys):
    from nestor import cli

    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    _cli_store(tmp_path, SERIALS)
    argv = ["--db", str(tmp_path / "n.db"), "--json",
            "match", RESTATED, "--from", DOMAIN, "--to", DOMAIN]

    assert cli.main(argv + ["--matcher", f"{__name__}:SERIALS"]) == 0
    out = capsys.readouterr().out
    assert '"normalized": "CH4471"' in out
    assert cli.main(argv) == 1


def test_cmd_match_still_reports_a_shipped_name_as_the_name(tmp_path, seal_key, capsys):
    """`--matcher numeric --json` reported "NumericMatcher" for one release —
    a machine-readable field changed in what was billed as a pure addition."""
    from nestor import cli

    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    from nestor import answer as _a
    _cli_store(tmp_path, _a.build_matcher("numeric"), source="1000", target="ceiling")
    cli.main(["--db", str(tmp_path / "n.db"), "--json", "match", "1000",
              "--from", DOMAIN, "--to", DOMAIN, "--matcher", "numeric"])
    assert '"matcher": "numeric"' in capsys.readouterr().out


def test_cmd_match_still_honours_tolerances_for_a_shipped_matcher(tmp_path, seal_key, capsys):
    from nestor import answer as _a, cli

    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    _cli_store(tmp_path, _a.build_matcher("numeric"), source="1000", target="ceiling")
    argv = ["--db", str(tmp_path / "n.db"), "--json", "match", "1500",
            "--from", DOMAIN, "--to", DOMAIN, "--matcher", "numeric"]
    assert cli.main(argv + ["--abs-tol", "1000"]) == 0, "abs_tol was not applied"
    assert cli.main(argv) == 1


def test_serve_main_hands_its_matcher_to_the_server(tmp_path, seal_key, monkeypatch):
    """`serve.main` is the only place `--matcher` becomes a `Server.matcher`,
    and nothing exercised it."""
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    _cli_store(tmp_path, SERIALS)
    built = {}

    real = serve.Server

    def capture(**kwargs):
        built.update(kwargs)
        server = real(**kwargs)
        server.run = lambda *a, **k: None      # do not take over stdio
        return server

    monkeypatch.setattr(serve, "Server", capture)
    rc = serve.main(["--db", str(tmp_path / "n.db"), "--source-lang", DOMAIN,
                     "--target-lang", DOMAIN, "--matcher", f"{__name__}:SERIALS"])
    assert rc == 0
    assert built["matcher"] is SERIALS, "--matcher never reached the Server"
    assert built["matcher_spec"] == f"{__name__}:SERIALS", (
        "the spec must survive, or a name that agrees gets refused")


def test_serve_main_defaults_leave_the_server_deferring(tmp_path, seal_key, monkeypatch):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    _cli_store(tmp_path, SERIALS)
    built = {}
    real = serve.Server

    def capture(**kwargs):
        built.update(kwargs)
        server = real(**kwargs)
        server.run = lambda *a, **k: None
        return server

    monkeypatch.setattr(serve, "Server", capture)
    serve.main(["--db", str(tmp_path / "n.db")])
    assert built["matcher"] is None


# ── what the first version of this change got wrong ─────────────────────────

def test_a_shipped_name_that_agrees_is_honoured_on_a_shipped_server(sealed_store):
    """The refusal compared against the matcher's CLASS name, so on a server
    started `--matcher numeric` the tool schema offered `string|numeric|semantic`
    and every one of them was refused, while `NumericMatcher` — advertised
    nowhere — worked. A model reading the enum could not get a right answer."""
    server = serve.Server(store=sealed_store, source_lang="fig", target_lang="fig",
                          matcher=answer.load_matcher("numeric"),
                          matcher_spec="numeric")
    enum = [t for t in server.tools() if t["name"] == "nestor_match"][0][
        "inputSchema"]["properties"]["matcher"]["enum"]
    assert "numeric" in enum
    out = server.call("nestor_match", {"text": "1000", "source_lang": "fig",
                                       "target_lang": "fig", "matcher": "numeric"})
    assert out["matcher"] == "numeric", "the name the model is told to send was refused"


def test_tolerances_still_reach_a_shipped_server_matcher(sealed_store):
    """`answer.match` can only apply abs_tol/pct_tol while it still has a NAME to
    rebuild from. Handing it the object made them silently inert: the same call
    on the same store answered True without --matcher and False with it."""
    memory.add_pair("1000", "ceiling", "fig", "fig", status="sealed",
                    verifier="rita", store=sealed_store,
                    matcher=answer.build_matcher("numeric"))
    server = serve.Server(store=sealed_store, source_lang="fig", target_lang="fig",
                          matcher=answer.load_matcher("numeric"),
                          matcher_spec="numeric")
    args = {"text": "1500", "source_lang": "fig", "target_lang": "fig"}
    assert server.call("nestor_match", {**args, "abs_tol": 1000})["served"] is True
    assert server.call("nestor_match", args)["served"] is False


def test_tolerances_are_refused_for_a_custom_matcher_rather_than_ignored(sealed_store):
    """A custom matcher owns its own notion of nearness. Accepting a number that
    changes nothing is the confident-wrong-answer shape this entry is about."""
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                          matcher=SERIALS, matcher_spec=f"{__name__}:SERIALS")
    with pytest.raises(ValueError, match="abs_tol and pct_tol"):
        server.call("nestor_match", {"text": REPORT, "abs_tol": 5})


def test_a_factory_that_returns_the_class_is_refused(tmp_path):
    """The class-instantiation fix checked before the call and not after, so a
    factory returning the class sailed through and failed at the first query —
    which is exactly what load-time validation exists to prevent."""
    mod = tmp_path / "returns_class.py"
    mod.write_text(
        "class M:\n"
        "    def normalize(self, v): return str(v)\n"
        "    def similarity(self, a, b): return 1.0\n"
        "def factory(): return M\n", encoding="utf-8")
    import sys
    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(ValueError, match="rather than an instance"):
            answer.load_matcher("returns_class:factory")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("returns_class", None)


def test_a_class_needing_constructor_arguments_is_refused_not_tracebacked(tmp_path):
    """The most likely first mistake with this feature. It used to raise
    TypeError straight out of main()."""
    mod = tmp_path / "needs_args.py"
    mod.write_text(
        "class M:\n"
        "    def __init__(self, threshold): self.t = threshold\n"
        "    def normalize(self, v): return str(v)\n"
        "    def similarity(self, a, b): return 1.0\n", encoding="utf-8")
    import sys
    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(ValueError, match="TypeError"):
            answer.load_matcher("needs_args:M")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("needs_args", None)


def test_a_module_that_raises_at_import_is_refused_not_tracebacked(tmp_path):
    mod = tmp_path / "explodes.py"
    mod.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    import sys
    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(ValueError, match="cannot import"):
            answer.load_matcher("explodes:M")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("explodes", None)


def test_a_matcher_module_printing_does_not_corrupt_the_protocol_stream(tmp_path, seal_key, capsys):
    """stdout is the JSON-RPC channel and the handshake has not happened yet, so
    an ordinary print() in a user's matcher module would land in front of it and
    most hosts drop the connection. This hazard did not exist before --matcher
    could import third-party code."""
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    _cli_store(tmp_path, SERIALS)
    mod = tmp_path / "chatty.py"
    mod.write_text(
        "print('loading acme matcher v2.1 ...')\n"
        "class M:\n"
        "    def normalize(self, v): return str(v)\n"
        "    def similarity(self, a, b): return 1.0\n"
        "MATCHER = M()\n", encoding="utf-8")
    import sys
    sys.path.insert(0, str(tmp_path))
    capsys.readouterr()
    try:
        real = serve.Server
        import unittest.mock as mock
        with mock.patch.object(serve, "Server") as fake:
            def capture(**kwargs):
                s = real(**kwargs)
                s.run = lambda *a, **k: None
                return s
            fake.side_effect = capture
            serve.main(["--db", str(tmp_path / "n.db"), "--matcher", "chatty:MATCHER"])
        captured = capsys.readouterr()
        assert "loading acme matcher" not in captured.out, (
            "a matcher module's print() landed on the JSON-RPC channel")
        assert "loading acme matcher" in captured.err
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("chatty", None)


def test_resolve_does_not_contradict_ask_on_the_same_server(sealed_store):
    """One server, one domain, one sealed row: nestor_ask honoured the matcher
    and nestor_resolve did not, so a model was told no human had verified a
    mapping a human had sealed."""
    server = serve.Server(store=sealed_store, source_lang=DOMAIN, target_lang=DOMAIN,
                          matcher=SERIALS, matcher_spec=f"{__name__}:SERIALS")
    asked = server.call("nestor_ask", {"text": RESTATED})
    resolved = server.call("nestor_resolve", {"surface": RESTATED, "domain": DOMAIN})
    assert asked["verified"] is True
    assert resolved["verified"] is True, (
        "nestor_resolve says unverified for what nestor_ask serves as sealed")


def test_resolve_scores_its_candidates_with_the_matcher_that_reached_the_verdict(sealed_store):
    """It used to use two: EntityResolver's for the verdict, the process-wide one
    for `candidates`. One payload could carry verified=False beside a 1.0."""
    was = memory.get_matcher()
    memory.set_matcher(SERIALS)
    try:
        out = answer.resolve(sealed_store, RESTATED, DOMAIN)
    finally:
        memory.set_matcher(was)
    top = max((c["similarity"] for c in out["candidates"]), default=0.0)
    assert not (out["verified"] is False and top >= memory.SEAL_THRESHOLD), (
        f"verified={out['verified']} beside a candidate scoring {top}")
