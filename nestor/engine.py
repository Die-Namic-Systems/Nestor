"""Tier 2 — the draft engine. Interpretation is consulted, never owned.

Pluggable: ClaudeEngine (cloud, v1) and OfflineEngine (TM-composite, for the
test bench and as the eventual local-model slot). Engines return a Draft or
None; the cascade decides what to do with the absence.

Output-voice rule (ground rule 2b): the engine is instructed to sound like
the speaker, never like a persona. Drafts are always marked unverified.
Both halves are enforced rather than described — see :data:`VOICE_RULE` and
:func:`system_prompt` for the first, and :class:`Draft` for the second.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from . import glossary, memory

CLAUDE_MODEL = "claude-opus-4-8"

#: Ground rule 2b, in the words the model is actually given.
#:
#: The rule used to exist twice in this file — once as prose in the module
#: docstring, once as a retyped literal inside the one engine that had a system
#: prompt — and neither was executed by anything. A rule stated in two places
#: and checked in none is two rules that have not drifted *yet*; this constant
#: is the one place it is defined, and ``tests/test_engine.py`` pins that the
#: docstring above still says what this says.
#:
#: The numbering is the fleet's; the text is Nestor's, and this is where it
#: lives. :mod:`nestor.engine` is the only module in this package that addresses
#: a model, so a voice rule that is not in :func:`system_prompt` is not in
#: effect anywhere.
VOICE_RULE = (
    "Preserve the speaker's register, tone, and formatting. The translation "
    "must sound like the original speaker, not like an assistant."
)


@dataclass
class Draft:
    """What an engine is allowed to return — and the second half of ground rule 2b.

    There is deliberately no ``state``, ``verified`` or ``seal_sig`` field here.
    An engine cannot mark its own output verified because it has nothing to mark
    it *with*: :class:`nestor.cascade.Passage` is what carries ``state``, and the
    cascade sets it to ``"draft"`` for everything that arrives through this
    class. So "drafts are always marked unverified" is not a convention the
    engine is trusted to honour — it is the only shape available to it.

    ``confidence`` is the engine's own rough signal and is not evidence about
    anything. It is not a seal, it does not accumulate into one, and nothing
    downstream may promote a draft on the strength of it.
    """

    text: str
    engine: str
    confidence: float  # 0..1 — engine's own rough signal, not a seal


def system_prompt(source_lang: str, target_lang: str,
                  locks: dict[str, str] | None = None,
                  context: list[dict] | None = None) -> str:
    """The system prompt for every model-backed engine. Module-level on purpose.

    This was a private method on :class:`ClaudeEngine`, which made ground rule
    2b a property of one class rather than of the tier. The engine slot is
    pluggable by design — :func:`get_engine` dispatches, and :class:`OfflineEngine`
    is documented as the eventual local-model slot — so the next engine that
    addresses a model would have written its own prompt, with nothing it was
    obliged to include. That is the defect shape ``TODO.md`` names: a guarantee
    enforced by convention at call sites, and a second path in that never
    passes it.

    So the rule is not a parameter. There is no ``voice=`` argument and no way
    to compose this prompt without :data:`VOICE_RULE` in it, because the only
    reason to make it optional would be to turn it off.

    The honest limit: this cannot stop somebody writing a brand-new prompt
    string somewhere else. It makes the shared builder the path of least
    resistance and the rule non-optional within it, and ``tests/test_engine.py``
    fails any ``system=`` in this package that was not built here. That is a
    choke point, not a proof — the same distinction
    :func:`nestor.cascade.ledger_append` draws about its file lock.
    """
    lines = [
        (f"You are a translation engine. Translate the user's text from "
         f"{source_lang} to {target_lang}."),
        ("Respond with ONLY the translated text — no preamble, no notes, "
         "no quotation marks around the output."),
        VOICE_RULE,
    ]
    if locks:
        lines.append("Locked terminology — always render these terms exactly as given:")
        lines += [f'  "{t}" -> "{tr}"' for t, tr in sorted(locks.items())]
    if context:
        lines.append("Reference translations from the verified memory "
                     "(match their terminology and style):")
        for m in context:
            p = m["pair"]
            lines.append(f'  {source_lang}: {p["source_text"]}')
            lines.append(f'  {target_lang}: {p["target_text"]}')
    return "\n".join(lines)


def _context_pairs(text: str, source_lang: str, target_lang: str,
                   limit: int = 3, store=None, matcher=None) -> list[dict]:
    """Nearby verified-sealed TM pairs, fed to the engine as style/terminology
    context. Verified only: a forged "sealed" row must not reach the engine's
    system prompt as authoritative TM (Nestor#2 follow-up).

    ``matcher`` for the same reason ``translate`` takes one — see there."""
    return memory.verified_sealed(
        memory.lookup(text, source_lang, target_lang, limit=limit, store=store,
                      matcher=matcher))


class OfflineEngine:
    """Deterministic fallback: serve the best fuzzy TM match as a low-confidence
    draft. No network, no model — honest about what it is.

    No system prompt, and therefore no voice rule: this engine copies a target
    a human already sealed rather than composing one, so the register it serves
    is the register that was ratified. Ground rule 2b constrains what a model is
    told, and there is no model here.
    """

    name = "offline-tm"

    def translate(self, text: str, source_lang: str, target_lang: str,
                  store=None, matcher=None) -> Draft | None:
        # Forged seals are filtered here for the same reason `_context_pairs`
        # filters them: a row nobody signed must not be copied verbatim into the
        # first thing a reviewer reads. `without_forged_seals` rather than
        # `verified_sealed` because this path is *entitled* to draft rows — the
        # asymmetry with the context path is deliberate and now written down,
        # which is what the previous version was missing more than the filter.
        #
        # `limit` is raised before filtering: taking the top 1 and then dropping
        # it returns None where a legitimate second-best match existed, which
        # would turn a forgery into a denial of service.
        matches = memory.without_forged_seals(
            memory.lookup(text, source_lang, target_lang, limit=5, store=store,
                          matcher=matcher))
        if not matches:
            return None
        m = matches[0]
        return Draft(text=m["pair"]["target_text"], engine=self.name,
                     confidence=round(m["similarity"] * 0.8, 3))


class ClaudeEngine:
    """Cloud draft via the Anthropic SDK. Requires ANTHROPIC_API_KEY (or an
    `ant auth login` profile). Glossary locks and sealed TM context are
    injected into the system prompt; output is the bare translation.

    The prompt itself is :func:`system_prompt` and not a method here — see its
    docstring for why the tier's voice rule must not belong to one class."""

    name = f"claude:{CLAUDE_MODEL}"

    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "ClaudeEngine needs the anthropic SDK: pip install anthropic "
                "(or use --engine offline)"
            ) from exc
        self._anthropic = anthropic
        self._client = anthropic.Anthropic()

    def translate(self, text: str, source_lang: str, target_lang: str,
                  store=None, matcher=None) -> Draft | None:
        locks = glossary.locks_in_text(text, source_lang, target_lang)
        context = _context_pairs(text, source_lang, target_lang, store=store,
                                 matcher=matcher)
        a = self._anthropic
        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=system_prompt(source_lang, target_lang, locks, context),
                messages=[{"role": "user", "content": text}],
            )
        except a.AuthenticationError as exc:
            raise RuntimeError(f"Anthropic auth failed: {exc.message}") from exc
        except a.RateLimitError as exc:
            raise RuntimeError("Anthropic rate limit (SDK retries exhausted)") from exc
        except a.APIStatusError as exc:
            raise RuntimeError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except a.APIConnectionError as exc:
            raise RuntimeError(f"Network error reaching Anthropic: {exc}") from exc

        if response.stop_reason == "refusal":
            return None
        draft = next((b.text for b in response.content if b.type == "text"), "").strip()
        if not draft:
            return None
        return Draft(text=draft, engine=self.name, confidence=0.75)


def get_engine(name: str = "auto"):
    """auto → Claude if credentials are plausibly present, else offline."""
    if name == "claude":
        return ClaudeEngine()
    if name == "offline":
        return OfflineEngine()
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        try:
            return ClaudeEngine()
        except RuntimeError:
            pass
    return OfflineEngine()
