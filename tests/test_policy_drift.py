"""Policy drift across the covenant documents (issue #167, piece 4).

The covenant — *You may propose. You may not confirm.*, plus the sealing rule
(no ``status="sealed"`` and no ``verifier=`` carrying a human's name unless
that human signed in ``nestor ui``) — is stated in several places on purpose:
``CLAUDE.md`` is what an agent is *made* to read, ``hooks/seat.md`` is the
Cursor/Codex-facing seat, ``docs/agent-guide.md`` is the full statement both
point at, ``AGENTS.md`` is a cold-start pointer, and ``hooks/reinject.py`` /
``hooks/before_authority.py`` carry it in code because a hook cannot ``import``
a markdown file. ``FINDINGS-2026-08-17-complexity-audit.md`` counted these as
"six copies" and flagged the risk by name: the same sentence living in many
places is drift risk. This file is the regression test for that finding.

**What this test does and does not prove.** It reads the documents as text and
checks that each still carries *some* accepted phrasing of the covenant, and
that none of them has grown a sentence that contradicts it (an agent granted
the ability to seal). It does **not** check that the code actually enforces
the covenant — that is ``tests/test_before_authority.py``,
``tests/test_onboarding.py::TestNeverSeals`` and the hash-chained ledger. A
document could pass every check here and the enforcement code could still have
a bug; conversely, enforcement could be perfect while a document quietly starts
telling an agent something false. This test catches a fork in the *stated*
rule, not a fork in *behaviour* — that is a narrower and cheaper claim, and it
is the one the complexity audit actually asked for.

Wording is deliberately not required to be byte-identical across documents —
``AGENTS.md`` says "You may propose; you may not confirm seals" where
``CLAUDE.md`` says "You may propose. You may not confirm." because one is a
pointer and the other is canonical, and that difference is legitimate. What
must not happen is one document dropping the rule, or acquiring a sentence
that grants an agent confirming/sealing power the others deny it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# The six places the complexity audit found the covenant living in, and the
# ones this test polices. Paths are relative to the repo root. `kind` is only
# used to shape assertion messages; every document is read as plain text.
COVENANT_DOCUMENTS = {
    "CLAUDE.md": "prose",
    "AGENTS.md": "prose",
    "docs/agent-guide.md": "prose",
    "hooks/seat.md": "prose",
    "hooks/reinject.py": "code",
    "hooks/before_authority.py": "code",
}

# Documents that state the covenant in full (the rule *and* the sealing
# mechanism it forbids an agent from writing), as opposed to a short pointer
# or a code paraphrase. These three are where the sealing detail must not go
# missing; the other three are allowed to just point at the rule.
FULL_STATEMENT_DOCUMENTS = ("CLAUDE.md", "docs/agent-guide.md", "hooks/seat.md")

# A small set of accepted formulations, not a demand for identical wording.
# Markdown emphasis markers ("**word**") are stripped before matching, so a
# doc that bolds "propose" and "confirm" separately still matches.
_ACCEPTED_COVENANT_PATTERNS = [
    re.compile(r"may propose[.;,]?\s+(?:you\s+)?(?:and\s+)?may not confirm", re.I),
    re.compile(r"may propose,?\s+not confirm", re.I),
]

# Phrases that would contradict the covenant if any of the six documents
# acquired one — an agent (or "the machine") granted the power to confirm,
# ratify, or seal on its own. This is intentionally a small, explicit list
# rather than a single clever regex: each entry names one concrete way the
# rule could be reversed, so a hit is easy to read and act on.
_CONTRADICTION_PATTERNS = [
    re.compile(r"agents?\s+may\s+(?:also\s+)?confirm", re.I),
    re.compile(r"agents?\s+may\s+seal", re.I),
    re.compile(r"the\s+machine\s+may\s+(?:also\s+)?confirm", re.I),
    re.compile(r"the\s+machine\s+may\s+seal", re.I),
    re.compile(r"you\s+may\s+confirm\b", re.I),
    re.compile(r"you\s+may\s+seal\b", re.I),
    re.compile(r"an?\s+agent\s+may\s+ratify", re.I),
]

_SEALING_MECHANISM_PATTERNS = [
    re.compile(r'status\s*=\s*"sealed"'),
    re.compile(r"verifier\s*="),
    re.compile(r"nestor\s+ui|nestor\.ui", re.I),
]


def _text(rel_path: str) -> str:
    path = REPO / rel_path
    assert path.is_file(), f"{rel_path} is one of the six covenant documents and must exist"
    return path.read_text(encoding="utf-8")


def _strip_markdown_emphasis(text: str) -> str:
    """Remove ``*`` so "may **propose**" and "may propose" match the same way."""
    return text.replace("*", "")


@pytest.mark.parametrize("rel_path", sorted(COVENANT_DOCUMENTS))
def test_document_carries_an_accepted_covenant_phrase(rel_path):
    """Every document in the set must still state propose/not-confirm, in one
    of the accepted formulations. A document that fails this has forked away
    from the rule — either it was edited and the sentence was lost, or it was
    rewritten into something no longer recognizable as the same rule.
    """
    text = _strip_markdown_emphasis(_text(rel_path))
    matched = any(p.search(text) for p in _ACCEPTED_COVENANT_PATTERNS)
    assert matched, (
        f"{rel_path} no longer carries an accepted formulation of the covenant "
        '("You may propose. You may not confirm." or a close variant). '
        "Either the sentence was edited away, or it drifted far enough from "
        "the accepted phrasing that this test can no longer recognize it — "
        "in either case, a human needs to look at this document."
    )


@pytest.mark.parametrize("rel_path", sorted(COVENANT_DOCUMENTS))
def test_document_contains_no_contradiction(rel_path):
    """None of the six documents may grant an agent the power the covenant
    denies it. This is the other half of "drift": not just losing the rule,
    but acquiring language that reverses it.
    """
    text = _text(rel_path)
    hits = [p.pattern for p in _CONTRADICTION_PATTERNS if p.search(text)]
    assert not hits, (
        f"{rel_path} contains language that contradicts the covenant "
        f"(matched pattern(s): {hits}). If this is a legitimate change to "
        "who may seal, it has to happen everywhere at once, not drift in "
        "through one document."
    )


@pytest.mark.parametrize("rel_path", FULL_STATEMENT_DOCUMENTS)
def test_full_statement_documents_carry_the_sealing_mechanism(rel_path):
    """CLAUDE.md, docs/agent-guide.md and hooks/seat.md are where the covenant
    is stated in full, not just pointed at — each must still name the actual
    mechanism it forbids an agent from writing (`status="sealed"`, `verifier=`)
    and the one place that may (`nestor ui`). Losing this from one of the
    three while it survives in the others is exactly the fork this test is
    for.
    """
    text = _text(rel_path)
    missing = [p.pattern for p in _SEALING_MECHANISM_PATTERNS if not p.search(text)]
    assert not missing, (
        f"{rel_path} is one of the documents that states the covenant in "
        f"full, but is missing: {missing}. Compare against the other two "
        f"documents in {FULL_STATEMENT_DOCUMENTS!r} to see what fell out."
    )


def test_claude_md_carries_only_the_two_pointer_lines():
    """CLAUDE.md states its own anti-duplication rule: 'Do not duplicate
    policy here — it drifts. Change docs/agent-guide.md, hooks/seat.md, and
    AGENTS.md instead.' It then names exactly two lines that are allowed to
    stay verbatim (the covenant, and the decisions-go-in-the-store rule).
    This test enforces CLAUDE.md's own instruction: if a third policy bullet
    shows up, that is policy prose growing back into the pointer file the
    project explicitly decided to keep thin.
    """
    text = _text("CLAUDE.md")
    anti_duplication_sentence = "Do not duplicate policy here — it drifts."
    assert anti_duplication_sentence in text, (
        "CLAUDE.md no longer states its own anti-duplication rule "
        f'("{anti_duplication_sentence}") — without it there is nothing for '
        "this test (or the next editor) to hold the file to."
    )

    # The two lines that are allowed to stay are top-level markdown bullets
    # ("- ..."), per CLAUDE.md's own formatting — the covenant line is bold,
    # the decisions-go-in-the-store line is not, so match either.
    policy_bullets = [
        line for line in text.splitlines() if line.strip().startswith("- ")
    ]
    assert len(policy_bullets) == 2, (
        "CLAUDE.md says, in its own words, "
        f'"{anti_duplication_sentence} Change docs/agent-guide.md, '
        'hooks/seat.md, and AGENTS.md instead." but now carries '
        f"{len(policy_bullets)} policy bullet(s), not the two pointer lines "
        f"it promises to keep. Found: {policy_bullets!r}. Move the new "
        "prose into docs/agent-guide.md, hooks/seat.md, or AGENTS.md instead "
        "of leaving it here."
    )


def test_reinject_governance_constant_matches_canonical_phrase():
    """`hooks/reinject.py::GOVERNANCE` is a Python constant, not a read of
    seat.md, specifically so the rule still lands if seat.md is unreadable at
    the moment an agent needs it (see the module's own docstring). That means
    it is its own copy and can drift on its own — pin it to the exact
    canonical sentence, not just "an accepted formulation".
    """
    from hooks import reinject

    assert reinject.GOVERNANCE == "You may propose. You may not confirm."


def test_before_authority_paraphrase_still_names_propose_and_confirm():
    """`hooks/before_authority.py` paraphrases the covenant (it is denial
    text shown to a human and to an agent, not a policy document), but the
    paraphrase must still name both halves of the rule — otherwise the one
    place an agent actually meets a live refusal has quietly stopped saying
    what it is refusing.
    """
    text = _text("hooks/before_authority.py")
    assert "propose" in text.lower()
    assert "confirm" in text.lower() or "seal" in text.lower()
