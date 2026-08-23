"""`nestor.persona` — the voice Nestor uses when Nestor is the speaker.

Four things are pinned here, and only the first is about prose:

1. **The engine cannot reach it.** Ground rule 2b says a translation sounds
   like the person who wrote the source. A persona that could reach
   :func:`nestor.engine.system_prompt` would be a mechanism for overriding
   that, so the import graph is walked and the edge is forbidden.
2. **The act vocabulary is closed**, and mirrored rather than imported — the
   `tests/test_ledger_kinds.py` rule. Importing the frozenset would make the
   pin true by construction and catch nothing.
3. **A persona is complete or it is refused.** No per-act fallback, because the
   act that silently fell back is the act nobody would test.
4. **A refusal still reads as one**, at every value its facts can take.

**Against the revision before `persona.py` existed, all of this is new** — there
is no before/after split to report because there was nothing to fail against.
What can be reported is the split for the behaviour it moved:
`tests/test_refusal_voice.py` was written first, against the strings in place,
and 1 of its 10 failed. This file is the module those strings moved into, and
it is scaffolding: it exists to make the *next* rewrite safe, not to prove this
one was needed.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from nestor import answer, memory, persona

SRC = pathlib.Path(__file__).resolve().parents[1] / "nestor"


# ------------------------------------------------------------- the fence ----

class TestTheEngineCannotReachThePersona:
    """The one structural rule: this voice must never become the engine's.

    Not a comment asking nicely. `engine.py` composes the system prompt that
    tells a model how to sound, and `VOICE_RULE` says that is the *speaker's*
    register, not Nestor's. If `persona` were importable from there, every
    later maintainer would have a plausible-looking way to make translations
    sound like the tool.
    """

    def _imports(self, module: str) -> set[str]:
        tree = ast.parse((SRC / f"{module}.py").read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.add(node.module.split(".")[0])
                names |= {a.name for a in node.names}
        return names

    def test_engine_does_not_import_persona(self):
        assert "persona" not in self._imports("engine"), (
            "nestor.engine imports nestor.persona — the module that decides how "
            "Nestor speaks must not be reachable from the one that tells a model "
            "how to sound. See engine.VOICE_RULE.")

    def test_persona_does_not_import_engine(self):
        """The other direction too. A persona that could read `VOICE_RULE` would
        be one edit away from templating it."""
        assert "engine" not in self._imports("persona"), (
            "nestor.persona imports nestor.engine — the two voices are separate "
            "objects and the seam is the point")

    def test_no_persona_reaches_a_system_prompt(self):
        """Belt to the import gate's braces: nothing in the package may pass a
        persona rendering into a `system=` argument."""
        for py in sorted(SRC.glob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if kw.arg != "system":
                        continue
                    src = ast.dump(kw.value)
                    assert "persona" not in src and "'say'" not in src, (
                        f"{py.name}: a persona rendering reached a system prompt")


# ------------------------------------------------------------- the pin ------

#: Mirrored, **not** imported — `tests/test_ledger_kinds.py`'s rule. Importing
#: `persona.SPEECH_ACTS` would make this true by construction and pin nothing.
PINNED_MACHINE_ACTS = {"below_threshold", "nothing_sealed", "nothing_in_domain"}
PINNED_HUMAN_ACTS = {"forged_seal", "rejected_outright", "suppressed"}


class TestTheVocabularyIsClosed:

    def test_the_acts_are_exactly_these(self):
        assert set(persona.SPEECH_ACTS) == PINNED_MACHINE_ACTS | PINNED_HUMAN_ACTS, (
            "a speech act was added or removed without updating this pin. Add "
            "the member, its first caller and this line in one change.")

    def test_the_partition_is_by_who_the_subject_is(self):
        """Which acts may be wry is not a style choice — it follows from the
        covenant. The machine may be laughed at because the machine is the
        junior party: it may propose and may not confirm. A human's signature
        or a curator's refusal is reported plainly."""
        assert set(persona.MACHINE_ACTS) == PINNED_MACHINE_ACTS
        assert set(persona.HUMAN_ACTS) == PINNED_HUMAN_ACTS
        assert not persona.MACHINE_ACTS & persona.HUMAN_ACTS

    def test_an_unknown_act_is_refused_not_rendered(self):
        with pytest.raises(persona.PersonaError, match="not a speech act"):
            persona.NESTOR.say("apology", count=1)


# ------------------------------------------------- complete or refused ------

class TestAPersonaIsAllOrNothing:
    """`storage.supports_rejection`'s rule, applied to prose: a capability is
    all-or-nothing because a partial one is indistinguishable from a working
    one until it matters."""

    def test_a_missing_act_is_refused_at_construction(self):
        partial = dict(persona.NESTOR.renderings)
        partial.pop("nothing_in_domain")
        with pytest.raises(persona.PersonaError, match="not complete"):
            persona.Persona(name="partial", renderings=partial)

    def test_an_unknown_act_is_refused_at_construction(self):
        extra = dict(persona.NESTOR.renderings)
        extra["apology"] = lambda **f: "no"
        with pytest.raises(persona.PersonaError, match="not complete"):
            persona.Persona(name="extra", renderings=extra)

    def test_a_duck_typed_stand_in_cannot_be_installed(self):
        class Sneaky:
            renderings: dict = {}  # noqa: RUF012 — intentional duck-type test

            def say(self, act, /, **facts):
                return "here you go!"

        with pytest.raises(persona.PersonaError, match="persona.Persona"):
            persona.set_persona(Sneaky())


# --------------------------------------------------- a refusal reads so ----

class TestARefusalStillReadsAsOne:
    """The guard a `warmth=` knob would have needed, and the reason there is no
    knob. Every act is a not-served outcome; a rendering that reads as
    reassuring is the exact lie this package exists not to tell."""

    CASES = {  # noqa: RUF012 — test data, not a mutable default
        "below_threshold": {"count": 20_000, "best": 0.71, "threshold": 0.92,
                            "shown": 8},
        "nothing_sealed": {"best": 1.0, "threshold": 0.92, "kinds": "draft"},
        "nothing_in_domain": {"source_lang": "en", "target_lang": "es"},
        "forged_seal": {"count": 2, "threshold": 0.92},
        "rejected_outright": {"count": 1},
        "suppressed": {"count": 3},
    }

    def test_every_shipped_act_renders(self):
        assert set(self.CASES) == set(persona.SPEECH_ACTS)
        for act, facts in self.CASES.items():
            assert persona.NESTOR.say(act, **facts)

    def test_a_reassuring_rendering_is_refused_at_say_time(self):
        """Checked on the *output*, not at construction, because a rendering is
        a callable: a sentence that negates at one count and not at another is
        precisely the failure this catches."""
        renderings = dict(persona.NESTOR.renderings)
        renderings["nothing_in_domain"] = \
            lambda *, source_lang, target_lang: "Still looking into that!"
        p = persona.Persona(name="cheerful", renderings=renderings)
        with pytest.raises(persona.PersonaError, match="no negation"):
            p.say("nothing_in_domain", source_lang="en", target_lang="es")

    def test_the_negation_check_is_not_satisfied_by_the_facts_alone(self):
        """A rendering that only negates because a caller happened to pass the
        word must not pass. The sentence has to carry it."""
        renderings = dict(persona.NESTOR.renderings)
        renderings["rejected_outright"] = lambda *, count: f"{count} of them!"
        p = persona.Persona(name="bare", renderings=renderings)
        with pytest.raises(persona.PersonaError):
            p.say("rejected_outright", count=4)


class TestRangeSafety:
    """A flat sentence is true across its whole format domain; a pointed one
    need not be. The first draft of `below_threshold` read "close enough to be
    tempting, which is why it is not served" — a good sentence, and false at
    0.11. Both pointed clauses are now about the *bar*, not about this row."""

    TEMPTATIONS = ("tempting", "almost", "nearly", "close enough")

    @pytest.mark.parametrize("count,best,shown", [(1, 0.919, 1), (3, 0.11, 3),
                                                  (20_000, 0.71, 8),
                                                  (20_000, 0.0, 8)])
    def test_below_threshold_holds_at_every_score(self, count, best, shown):
        said = persona.NESTOR.say("below_threshold", count=count, best=best,
                                  threshold=0.92, shown=shown)
        assert f"is {best}, below 0.92" in said
        for lie in self.TEMPTATIONS:
            assert lie not in said.lower(), f"{lie!r} is false at {best}: {said!r}"

    def test_the_slice_note_appears_only_when_something_was_sliced(self):
        sliced = persona.NESTOR.say("below_threshold", count=20_000, best=0.71,
                                    threshold=0.92, shown=8)
        whole = persona.NESTOR.say("below_threshold", count=3, best=0.11,
                                   threshold=0.92, shown=3)
        assert "showing 8" in sliced and sliced.count("20000") == 1
        assert "showing" not in whole

    @pytest.mark.parametrize("kinds", ["draft", "rejected", "draft, rejected"])
    def test_nothing_sealed_says_nothing_about_who_wrote_them(self, kinds):
        """`kinds` can be either or both, and a sentence true of a draft is a
        lie about a rejected row."""
        said = persona.NESTOR.say("nothing_sealed", best=1.0, threshold=0.92,
                                  kinds=kinds)
        for authorial in ("a machine wrote", "machine-written", "generated by"):
            assert authorial not in said.lower(), said


# ------------------------------------------------------ actually wired ------

class TestItIsInstalled:
    """`answer` renders through the seam rather than holding its own strings."""

    def _classify_node(self) -> ast.FunctionDef:
        tree = ast.parse((SRC / "answer.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_classify":
                return node
        pytest.fail("_classify is gone — the act/render split was undone")

    def test_classify_composes_no_prose(self):
        """The strings moved. If one comes back, `_classify` has grown a second
        voice no persona can override.

        The signal is the f-string: every branch that used to hold a sentence
        interpolated its facts, and nothing in a classifier needs to. Checking
        for f-strings rather than for words avoids the first version of this
        test, which searched for "below" and flagged the act named
        ``below_threshold``.
        """
        offenders = [ast.dump(n)[:60] for n in ast.walk(self._classify_node())
                     if isinstance(n, ast.JoinedStr)]
        assert not offenders, f"_classify is composing prose again: {offenders}"

    def test_every_act_classify_returns_is_a_pinned_one(self):
        """Statically, not by driving branches — a branch reachable only under
        a store state no test builds would otherwise ship an unpinned act."""
        returned = {n.value.elts[0].value
                    for n in ast.walk(self._classify_node())
                    if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple)
                    and isinstance(n.value.elts[0], ast.Constant)}
        assert returned, "no act literals found — did _classify stop returning tuples?"
        assert returned <= set(persona.SPEECH_ACTS), (
            f"_classify returns acts no persona has to render: "
            f"{sorted(returned - set(persona.SPEECH_ACTS))}")

    def test_classify_returns_an_act_not_a_sentence(self, store):
        act, facts = answer._classify(store, memory.get_matcher(), "q", "q",
                                      "nosuch", "nosuch", [], 0.92)
        assert act in persona.SPEECH_ACTS
        assert isinstance(facts, dict)

    def test_an_installed_persona_changes_what_a_surface_says(self, store):
        """The seam is real, not decorative — and it is the only way in."""
        renderings = dict(persona.NESTOR.renderings)
        renderings["nothing_in_domain"] = \
            lambda *, source_lang, target_lang: f"no rows for {source_lang}"
        persona.set_persona(persona.Persona(name="terse", renderings=renderings))
        try:
            result = answer.match(store, "anything", "nosuch", "nosuch")
            assert result["reason"] == "no rows for nosuch"
        finally:
            persona.set_persona(persona.NESTOR)

    def test_the_default_survives_a_failed_install(self):
        before = persona.get_persona()
        with pytest.raises(persona.PersonaError):
            persona.set_persona(object())
        assert persona.get_persona() is before
