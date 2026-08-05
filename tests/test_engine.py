"""Ground rule 2b — the output-voice rule, made executable.

`nestor/engine.py` has always *stated* 2b: "the engine is instructed to sound
like the speaker, never like a persona. Drafts are always marked unverified."
It stated it twice — once as prose in the module docstring, once as a retyped
literal inside the only class that had a system prompt — and executed it
nowhere. `test_docs.py` names the failure mode exactly: *a claim nobody
executes is a claim nobody maintains.* Two copies of a rule and no check is
not redundancy, it is a pending disagreement.

The second-order problem was worse than the drift. The engine slot is pluggable
by design — `get_engine` dispatches and `OfflineEngine` is documented as the
eventual local-model slot — so the rule lived on one class while the *tier* is
what it governs. The next engine to address a model would have composed its own
prompt with nothing it was obliged to include. That is the shape `TODO.md`
catalogues four times over: a guarantee enforced by convention at call sites,
and a second path in that never passes it. The answer there is the answer here
— move the rule into the one place that cannot be reached around, and then
check that nobody built a second door.

Four claims:

  * the rule is pinned EXACTLY — changing the words the model is given is a
    deliberate, reviewed act (this file changes in the same diff);
  * every prompt carries it, under every combination of locks and context,
    because it is not a parameter and there is no way to compose the prompt
    without it;
  * no module in `nestor/` hands a model a system prompt it did not build
    here — the source-level gate, and the one that actually catches a new
    engine;
  * drafts are unverified by *shape*, not by discipline: an engine has no
    field to claim otherwise with.
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from nestor import cascade, engine

#: Mirror, not import — the same rule `test_ledger_kinds.py` follows for
#: LEDGER_KINDS. Importing `engine.VOICE_RULE` here would make the pin true by
#: construction and therefore vacuous: the point is that editing what the model
#: is told requires touching two files in one reviewed diff.
PINNED_VOICE_RULE = (
    "Preserve the speaker's register, tone, and formatting. The translation "
    "must sound like the original speaker, not like an assistant."
)

SRC = pathlib.Path(engine.__file__).parent


def test_the_rule_is_pinned_exactly():
    assert engine.VOICE_RULE == PINNED_VOICE_RULE, (
        "engine.VOICE_RULE changed without updating the pinning test — the "
        "words a model is given about whose voice to use are the product's "
        "voice policy, and they change deliberately: constant + test in one "
        "diff (ground rule 2b)")


def test_the_docstring_still_states_both_halves():
    # The prose is what a reader meets first. If the constant is what governs,
    # the docstring must not be allowed to quietly stop claiming it — that is
    # how the two copies got out of sync in the first place.
    doc = engine.__doc__ or ""
    assert "ground rule 2b" in doc
    assert "sound like" in doc and "never like a persona" in doc
    assert "unverified" in doc


@pytest.mark.parametrize("locks", [None, {}, {"invoice": "facture"}])
@pytest.mark.parametrize("context", [None, [], [{"pair": {"source_text": "a", "target_text": "b"}}]])
def test_every_prompt_carries_the_rule(locks, context):
    # The combinatorial point: locks and context are the two things that vary
    # per call, and the rule survives all four corners. A rule that held only
    # when the glossary was empty would be the `best_sealed` defect again —
    # a guarantee that only holds where somebody thought to look.
    prompt = engine.system_prompt("en", "fr", locks, context)
    assert PINNED_VOICE_RULE in prompt


def test_the_rule_is_not_a_parameter():
    # There is no `voice=` and no `include_voice_rule=`, because the only
    # reason to make it optional would be to turn it off. Anything that would
    # let a caller drop it is a regression regardless of its default.
    import inspect
    params = set(inspect.signature(engine.system_prompt).parameters)
    assert params == {"source_lang", "target_lang", "locks", "context"}, (
        f"system_prompt grew a parameter: {sorted(params)} — if it is a way to "
        f"vary the voice rule, ground rule 2b is now optional")


def test_no_module_hands_a_model_a_prompt_built_elsewhere():
    """The gate that catches the engine nobody has written yet.

    `system=` is the Anthropic SDK's system-prompt keyword. Every occurrence in
    this package must be `system=system_prompt(...)`; a new engine calling
    `messages.create(system="You are ...")` with its own string fails here,
    which is the whole point — that call site is exactly the second path in
    that `TODO.md` warns about, and it would otherwise land silently.

    Parsed, not grepped. The first version of this test regexed the source and
    flagged the phrase ``system=`` inside a docstring one function above — prose
    about the rule tripping the check for the rule. "Is this a keyword argument
    in a call?" is a syntax question and the syntax tree answers it exactly,
    where a regex has to keep guessing which quotes it is inside.
    """
    offenders = []
    for py in sorted(SRC.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "system":
                    continue
                v = kw.value
                built_here = (isinstance(v, ast.Call)
                              and ((isinstance(v.func, ast.Name)
                                    and v.func.id == "system_prompt")
                                   or (isinstance(v.func, ast.Attribute)
                                       and v.func.attr == "system_prompt")))
                if not built_here:
                    offenders.append(
                        f"{py.name}:{kw.value.lineno}: system={ast.unparse(v)[:60]}")
    assert not offenders, (
        "a system prompt is being handed to a model without passing through "
        "engine.system_prompt:\n  " + "\n  ".join(offenders)
        + "\nGround rule 2b is enforced in system_prompt(); a prompt assembled "
          "anywhere else does not carry it.")


def test_the_rule_is_written_once():
    # Two copies is how this started. Pin that the distinctive phrase occurs in
    # exactly one place in the package — the constant's own definition.
    hits = []
    for py in sorted(SRC.glob("*.py")):
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if "not like an assistant" in line:
                hits.append(f"{py.name}:{n}")
    assert len(hits) == 1, (
        f"the voice rule is written {len(hits)} times ({hits}) — it is defined "
        f"in engine.VOICE_RULE and referenced, never retyped")


class TestDraftsAreUnverifiableByShape:
    """2b's second half. Not a convention the engine is trusted to honour."""

    def test_draft_has_no_field_that_could_claim_verification(self):
        fields = {f.name for f in dataclasses.fields(engine.Draft)}
        assert fields == {"text", "engine", "confidence"}
        # Named individually so the failure message says which door opened.
        for forbidden in ("state", "verified", "sealed", "seal_sig", "verifier"):
            assert forbidden not in fields, (
                f"Draft grew a {forbidden!r} field — an engine that can mark "
                f"its own output verified is the covenant inverted: the machine "
                f"may propose and may not confirm (ground rule 2b)")

    def test_confidence_is_not_a_seal(self):
        # A high-confidence draft is still a draft. The cascade decides state;
        # the engine's own number never promotes it.
        d = engine.Draft(text="facture", engine="offline-tm", confidence=1.0)
        assert not hasattr(d, "state")
        p = cascade.Passage(source="invoice", target=d.text, tier=2,
                            state="draft", engine=d.engine, confidence=d.confidence)
        assert p.state == "draft"
        assert p.mark == "~"


def test_offline_engine_returns_drafts_not_verdicts(store):
    # The engine that needs no credentials, exercised end to end: whatever it
    # finds, it comes back as a Draft — the type that cannot claim a seal.
    from nestor import memory
    memory.add_pair("invoice", "facture", "en", "fr", store=store)
    out = engine.OfflineEngine().translate("invoice", "en", "fr", store=store)
    if out is not None:
        assert isinstance(out, engine.Draft)
        assert out.confidence < 1.0   # 0.8 ceiling: a match is not a ratification
