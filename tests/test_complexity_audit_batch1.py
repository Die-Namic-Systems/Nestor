"""Batch-1 fixes from the 2026-08-17 complexity audit (FINDINGS-2026-08-17).

Each test pins one behaviour the audit asked for, so the fix cannot silently
regress. Grouped in one file because the changes are cross-cutting (cli, answer,
cascade, storage, errors) but land as a single reviewable unit.
"""
from __future__ import annotations

import warnings

import pytest

import nestor
from nestor import answer, cascade
from nestor.cli import build_parser, split_delegated
from nestor.errors import NestorError
from nestor.sqlite_store import SqliteStore


# --- the common refusal base ------------------------------------------------

# The policy refusals that must share the NestorError base, imported from where
# each lives so a move that drops one from the base fails here. FrankUnavailable
# was missed in the first pass (found by review) — it belongs to the family: a
# strict-mode FRANK forward failure is a refusal a host may want to catch.
def _refusals():
    from nestor.config import ConfigError
    from nestor.curator import CurationUnsupportedError
    from nestor.frank import FrankUnavailable
    from nestor.home_paths import HomeRelocationRefused
    from nestor.keyring import KeyringError, RevokedKeyError, UnknownVerifierError
    from nestor.ledger import LedgerError
    from nestor.memory import (
        ConflictingDraftError,
        ConflictingSealError,
        InvalidSealSignatureError,
        RejectedPairError,
    )
    from nestor.signing import SigningRequiredError
    from nestor.sqlite_store import (
        RowRetiredError,
        StoreClosedError,
        StoreSchemaTooNewError,
    )
    return [
        ConfigError, CurationUnsupportedError, FrankUnavailable, HomeRelocationRefused,
        KeyringError, UnknownVerifierError, RevokedKeyError, LedgerError, RejectedPairError,
        ConflictingDraftError, ConflictingSealError, InvalidSealSignatureError,
        SigningRequiredError, StoreClosedError, StoreSchemaTooNewError, RowRetiredError,
    ]


@pytest.mark.parametrize("exc", _refusals(), ids=lambda e: e.__name__)
def test_every_refusal_shares_the_nestor_base(exc):
    assert issubclass(exc, NestorError)
    # ...and still RuntimeError, so `except RuntimeError` that worked before works.
    assert issubclass(exc, RuntimeError)


def test_nestor_error_is_a_runtime_error_and_is_exported():
    assert issubclass(NestorError, RuntimeError)
    assert nestor.NestorError is NestorError            # public surface
    assert "NestorError" in nestor.__all__


def test_format_errors_stay_value_errors_not_refusals():
    """A malformed bundle or persona spec is bad input, not a policy refusal —
    conflating them would change which `except` clause catches them."""
    from nestor.persona import PersonaError
    from nestor.portable import BundleError
    for exc in (PersonaError, BundleError):
        assert issubclass(exc, ValueError)
        assert not issubclass(exc, NestorError)


def test_except_nestor_error_catches_a_concrete_refusal():
    from nestor.curator import CurationUnsupportedError
    with pytest.raises(NestorError):
        raise CurationUnsupportedError("x")


# --- CLI ergonomics ---------------------------------------------------------

def test_misplaced_global_flag_explains_itself(capsys):
    """`nestor ask "hi" --db x` used to say only 'unrecognized arguments'."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ask", "hi", "--db", "/tmp/x.db"])
    err = capsys.readouterr().err
    assert "go BEFORE the subcommand" in err
    assert "--db" in err


def test_db_verb_defaults_but_decision_stays_required():
    # `db` has no trailing positional, so its single verb is safely optional.
    assert build_parser().parse_args(["db"]).db_command == "checkpoint"
    assert build_parser().parse_args(["db", "checkpoint"]).db_command == "checkpoint"
    # `decision` keeps the verb REQUIRED: it has a trailing required `question`,
    # so a lone token would be swallowed as the question and `nestor decision
    # check` would silently check the literal word "check" instead of erroring.
    dec = build_parser().parse_args(["decision", "check", "q"])
    assert dec.decision_command == "check" and dec.question == "q"
    with pytest.raises(SystemExit):          # verb given, question missing -> error, not a silent run
        build_parser().parse_args(["decision", "check"])
    with pytest.raises(SystemExit):          # a bare token that isn't the verb is refused
        build_parser().parse_args(["decision", "my question"])


def test_hint_matches_the_flag_exactly_not_as_a_substring(capsys):
    # A real misplaced global flag gets the hint...
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ask", "hi", "--db", "x"])
    assert "go BEFORE the subcommand" in capsys.readouterr().err
    # ...but an unrelated typo that merely CONTAINS '--db' as a substring does not.
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ask", "hi", "--dbg"])
    assert "go BEFORE the subcommand" not in capsys.readouterr().err


def test_json_flag_is_reported_dropped_for_delegated_surfaces(capsys):
    name, rest = split_delegated(["--json", "--db", "x.db", "ui", "--port", "9"])
    assert name == "ui"
    assert "--json" not in rest and rest[:2] == ["--db", "x.db"]
    assert "--json has no effect" in capsys.readouterr().err


# --- tolerance flags on a matcher that has no tolerance ---------------------

def test_tolerance_on_non_numeric_matcher_warns():
    with pytest.warns(RuntimeWarning, match="ignored by the 'string' matcher"):
        answer.build_matcher("string", abs_tol=5.0)


def test_tolerance_on_numeric_matcher_is_silent():
    with warnings.catch_warnings():
        warnings.simplefilter("error")          # any warning would fail the test
        answer.build_matcher("numeric", abs_tol=5.0, pct_tol=0.1)
        answer.build_matcher("string")           # defaults: nothing ignored


# --- engine signature probe (no more swallowed TypeErrors) ------------------

def test_accepted_kwargs_reads_the_signature():
    def both(text, s, t, store=None, matcher=None): ...
    def only_store(text, s, t, store=None): ...
    def neither(text, s, t): ...
    def var_kw(text, s, t, **kw): ...
    assert cascade._accepted_kwargs(both, store=1, matcher=2) == {"store": 1, "matcher": 2}
    assert cascade._accepted_kwargs(only_store, store=1, matcher=2) == {"store": 1}
    assert cascade._accepted_kwargs(neither, store=1, matcher=2) == {}
    assert cascade._accepted_kwargs(var_kw, store=1, matcher=2) == {"store": 1, "matcher": 2}


def test_accepted_kwargs_skips_positional_only_params():
    """A positional-only `store` (before `/`) matches by name but cannot take a
    keyword — passing it would raise the TypeError this helper exists to avoid."""
    def posonly(text, s, t, store=None, /, matcher=None): ...
    assert cascade._accepted_kwargs(posonly, store=1, matcher=2) == {"matcher": 2}


def test_a_real_engine_typeerror_is_not_swallowed():
    """The old try/except probe reinterpreted a genuine engine bug as 'this engine
    doesn't accept matcher=' and retried with fewer args. It must surface now."""
    class Boom:
        def translate(self, text, source_lang, target_lang, store=None, matcher=None):
            raise TypeError("a real bug inside the engine")

    store = SqliteStore(":memory:")
    with pytest.raises(TypeError, match="a real bug inside the engine"):
        cascade.translate_segment("hello", "en", "es", engine=Boom(), store=store)


# --- storage capability docstring cannot drift again ------------------------

def test_storage_docstring_names_every_capability_predicate():
    """The docstring said 'six' while the code had nine. Pin it: every
    supports_* predicate the package defines must be named in the docstring."""
    import inspect
    import pkgutil

    import nestor as pkg

    predicates = set()
    for mod in pkgutil.iter_modules(pkg.__path__):
        try:                                    # optional extras (cloud_seal → [gate])
            m = __import__(f"nestor.{mod.name}", fromlist=["_"])
        except ImportError:
            continue
        for name, obj in vars(m).items():
            if name.startswith("supports_") and inspect.isfunction(obj):
                predicates.add(name)
    assert predicates, "no supports_* predicates discovered — scan is broken"

    from nestor import storage
    doc = storage.__doc__ or ""
    missing = sorted(p for p in predicates if p not in doc)
    assert not missing, f"supports_* predicates absent from storage docstring: {missing}"
