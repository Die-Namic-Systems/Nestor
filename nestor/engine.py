"""Tier 2 — the draft engine. Interpretation is consulted, never owned.

Pluggable: ClaudeEngine (cloud, v1) and OfflineEngine (TM-composite, for the
test bench and as the eventual local-model slot). Engines return a Draft or
None; the cascade decides what to do with the absence.

Output-voice rule (ground rule 2b): the engine is instructed to sound like
the speaker, never like a persona. Drafts are always marked unverified.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from . import glossary, memory

CLAUDE_MODEL = "claude-opus-4-8"


@dataclass
class Draft:
    text: str
    engine: str
    confidence: float  # 0..1 — engine's own rough signal, not a seal


def _context_pairs(text: str, source_lang: str, target_lang: str,
                   limit: int = 3, store=None) -> list[dict]:
    """Nearby verified-sealed TM pairs, fed to the engine as style/terminology
    context. Verified only: a forged "sealed" row must not reach the engine's
    system prompt as authoritative TM (Nestor#2 follow-up)."""
    return memory.verified_sealed(
        memory.lookup(text, source_lang, target_lang, limit=limit, store=store))


class OfflineEngine:
    """Deterministic fallback: serve the best fuzzy TM match as a low-confidence
    draft. No network, no model — honest about what it is."""

    name = "offline-tm"

    def translate(self, text: str, source_lang: str, target_lang: str,
                  store=None) -> Draft | None:
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
            memory.lookup(text, source_lang, target_lang, limit=5, store=store))
        if not matches:
            return None
        m = matches[0]
        return Draft(text=m["pair"]["target_text"], engine=self.name,
                     confidence=round(m["similarity"] * 0.8, 3))


class ClaudeEngine:
    """Cloud draft via the Anthropic SDK. Requires ANTHROPIC_API_KEY (or an
    `ant auth login` profile). Glossary locks and sealed TM context are
    injected into the system prompt; output is the bare translation."""

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

    def _system(self, source_lang: str, target_lang: str,
                locks: dict[str, str], context: list[dict]) -> str:
        lines = [
            f"You are a translation engine. Translate the user's text from "
            f"{source_lang} to {target_lang}.",
            "Respond with ONLY the translated text — no preamble, no notes, "
            "no quotation marks around the output.",
            "Preserve the speaker's register, tone, and formatting. The "
            "translation must sound like the original speaker, not like an assistant.",
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

    def translate(self, text: str, source_lang: str, target_lang: str,
                  store=None) -> Draft | None:
        locks = glossary.locks_in_text(text, source_lang, target_lang)
        context = _context_pairs(text, source_lang, target_lang, store=store)
        a = self._anthropic
        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=self._system(source_lang, target_lang, locks, context),
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
