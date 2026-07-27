"""Deterministic corpora for the bench, spanning the diversity spectrum.

Two shapes, because Nestor's accuracy depends almost entirely on how much the
sealed phrases resemble each other:

* :func:`boilerplate` — templated legal text drawn from a small word pool. Near
  worst case for a character-ratio matcher: every phrase shares most of its
  characters with every other phrase.
* :func:`prose` — real English sentences harvested from the Python standard
  library's docstrings. No network, no fixtures to vendor, and genuinely
  diverse vocabulary and length.

Both are seeded, so a bench run is reproducible.
"""
from __future__ import annotations

import importlib
import random
import re

# --------------------------------------------------------------------------
# boilerplate — the homogeneous end
# --------------------------------------------------------------------------

_NOUN = ("contract clause invoice vendor payment schedule warranty licence deposit "
         "penalty audit report term renewal notice breach remedy annex").split()
_VERB = ("terminates governs amends supersedes precedes limits waives assigns "
         "triggers suspends").split()
_ADJ = ("material initial annual mutual written prior joint final partial "
        "exclusive").split()


def boilerplate(n: int, seed: int = 7, offset: int = 0) -> list[str]:
    """``n`` templated contract phrases. ``offset`` shifts the section numbers so
    a held-out probe set never collides with the sealed set."""
    rng = random.Random(seed)
    return [
        f"the {rng.choice(_ADJ)} {rng.choice(_NOUN)} {rng.choice(_VERB)} "
        f"any {rng.choice(_ADJ)} {rng.choice(_NOUN)} under section {offset + i}"
        for i in range(n)
    ]


# --------------------------------------------------------------------------
# prose — the diverse end, harvested from stdlib docstrings
# --------------------------------------------------------------------------

_SENT = re.compile(r"(?<=[.!?])\s+")
_MODULES = ("json textwrap argparse logging inspect difflib pathlib datetime "
            "collections functools itertools statistics random shutil socket "
            "sqlite3 subprocess threading typing unittest urllib.parse csv "
            "configparser dataclasses decimal email.utils enum fractions "
            "gettext gzip hashlib heapq hmac http.client imaplib ipaddress "
            "mailbox mimetypes numbers operator optparse pickle pprint queue "
            "sched selectors shlex signal smtplib ssl string tarfile tempfile "
            "tokenize traceback uuid wave xml.dom zipfile").split()


def _harvest() -> list[str]:
    out: list[str] = []
    for name in _MODULES:
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        docs = [mod.__doc__]
        for attr in vars(mod).values():
            doc = getattr(attr, "__doc__", None)
            if isinstance(doc, str):
                docs.append(doc)
            if isinstance(attr, type):
                for sub in vars(attr).values():
                    sdoc = getattr(sub, "__doc__", None)
                    if isinstance(sdoc, str):
                        docs.append(sdoc)
        for doc in docs:
            if not doc:
                continue
            flat = re.sub(r"\s+", " ", doc).strip()
            for s in _SENT.split(flat):
                s = s.strip()
                # Long enough to be a real segment, short enough to be a TM unit.
                if 40 <= len(s) <= 180 and s.count(" ") >= 5:
                    out.append(s)
    return out


_CACHE: list[str] | None = None


def prose(n: int, seed: int = 7, offset: int = 0) -> list[str]:
    """``n`` distinct real English sentences, deterministically ordered."""
    global _CACHE
    if _CACHE is None:
        uniq = sorted(set(_harvest()))
        rng = random.Random(1234)
        rng.shuffle(uniq)
        _CACHE = uniq
    pool = _CACHE
    if n > len(pool):
        raise ValueError(f"prose corpus holds {len(pool)} sentences; asked for {n}. "
                         f"Add modules to _MODULES or lower the requested size.")
    start = offset % len(pool)
    out = pool[start:start + n]
    if len(out) < n:                       # wrap rather than fail
        out += pool[:n - len(out)]
    return out


def available_prose() -> int:
    prose(1)
    return len(_CACHE or [])


CORPORA = {"boilerplate": boilerplate, "prose": prose}


# --------------------------------------------------------------------------
# perturbations — "the same thing, expressed by a human on a different day"
# --------------------------------------------------------------------------
#
# Split into two TIERS, because they measure completely different things and
# reporting them together was actively misleading.
#
#   SURFACE     — case, punctuation, whitespace, one typo. Measured: 81% of
#                 these normalize to a byte-identical key, because
#                 StringMatcher.normalize strips case/punctuation/whitespace
#                 BEFORE scoring. They score exactly 1.0 and are recalled at
#                 every threshold, so "recall 100%" over this tier means only
#                 "near-identical input still matches" — never in doubt.
#
#   PARAPHRASE  — meaning-preserving rewrites that SURVIVE normalization:
#                 synonym substitution, clause reordering, contraction. These
#                 are what actually stresses a threshold, and what a real
#                 reviewer produces when they retype from memory rather than
#                 copy-paste.
#
# The paraphrase tier models a human who remembers the GIST and re-expresses it,
# not an adversary. Every transformation below is meaning-preserving by
# construction: a reviewer would seal the same target for the output as for the
# input. That is precisely the property recall is supposed to measure.

SURFACE_KINDS = ("case", "punct", "space", "typo", "trail")
PARAPHRASE_KINDS = ("synonym", "reorder", "contract")

# Interchangeable within the boilerplate vocabulary — the generator owns this
# word pool, so substitution is exactly meaning-preserving.
_SYN_BOILER = {
    "contract": "agreement", "clause": "provision", "invoice": "bill",
    "vendor": "supplier", "payment": "remittance", "schedule": "timetable",
    "warranty": "guarantee", "licence": "permit", "deposit": "advance",
    "penalty": "fine", "audit": "review", "report": "statement",
    "term": "condition", "renewal": "extension", "notice": "notification",
    "breach": "violation", "remedy": "cure", "annex": "appendix",
    "terminates": "ends", "governs": "controls", "amends": "modifies",
    "supersedes": "replaces", "precedes": "predates", "limits": "restricts",
    "waives": "forgoes", "assigns": "transfers", "triggers": "activates",
    "suspends": "pauses", "material": "significant", "initial": "first",
    "annual": "yearly", "mutual": "reciprocal", "written": "documented",
    "prior": "previous", "joint": "shared", "final": "last",
    "partial": "incomplete", "exclusive": "sole",
}

# Conservative substitutions for general technical English. Deliberately small:
# a wrong entry here turns a recall probe into a false-seal probe and silently
# corrupts the measurement.
_SYN_PROSE = {
    "returns": "gives back", "return": "give back", "cannot": "can not",
    "must": "has to", "each": "every", "optional": "not required",
    "specified": "given", "specify": "give", "contains": "holds",
    "creates": "makes", "removes": "deletes", "allows": "permits",
    "raises": "throws", "occurs": "happens", "begins": "starts",
    "additional": "extra", "identical": "the same", "entire": "whole",
    "attempt": "try", "obtain": "get", "require": "need", "requires": "needs",
}

_CONTRACTIONS = {
    "do not": "don't", "does not": "doesn't", "is not": "isn't",
    "are not": "aren't", "will not": "won't", "cannot": "can't",
    "it is": "it's", "that is": "that's", "has not": "hasn't",
}


def _substitute(text: str, table: dict, rng: random.Random) -> str:
    """Replace one word from ``table``. Returns ``text`` unchanged if none apply."""
    hits = [w for w in table if re.search(rf"\b{re.escape(w)}\b", text)]
    if not hits:
        return text
    w = rng.choice(sorted(hits))
    return re.sub(rf"\b{re.escape(w)}\b", table[w], text, count=1)


def _reorder(text: str, rng: random.Random) -> str:
    """Move a trailing clause to the front — meaning-preserving in English.

    ``the annual audit governs any notice under section 12``
    -> ``under section 12, the annual audit governs any notice``
    """
    for marker in (" under ", " when ", " if ", " unless ", " because ", " while "):
        i = text.find(marker)
        if i > 0:
            head, tail = text[:i], text[i + 1:]
            return f"{tail.rstrip('.')}, {head}"
    if ", " in text:                       # swap around the first comma
        a, b = text.split(", ", 1)
        return f"{b.rstrip('.')}, {a}"
    return text


_STOPWORDS = ("the", "a", "an", "of", "to", "that", "any", "this", "its", "then")


def _telegraphic(text: str, rng: random.Random) -> str:
    """Drop a function word — how people retype from memory rather than copy.

    ``Bind the socket to a local address`` -> ``Bind socket to a local address``

    The guaranteed fallback: applicable to essentially any English sentence, and
    meaning-preserving. Without it the paraphrase tier silently degraded into the
    identity function on 55% of prose, which would have measured nothing while
    looking like it measured something.
    """
    words = text.split()
    droppable = [i for i, w in enumerate(words)
                 if w.strip(".,;:()").lower() in _STOPWORDS]
    if not droppable:
        return text
    i = rng.choice(droppable)
    return " ".join(words[:i] + words[i + 1:])


def perturb(text: str, rng: random.Random, tier: str = "surface") -> str:
    """Re-express ``text``. ``tier`` is ``"surface"`` or ``"paraphrase"``.

    A matcher SHOULD still serve the sealed pair for either — they denote the
    same thing. See the tier discussion above for why they are reported apart.

    In the paraphrase tier the strategies are tried in a shuffled order and the
    first one that actually CHANGES the text wins. An unchanged "paraphrase" is
    an identity probe wearing a costume: it inflates recall while measuring
    nothing, which is exactly the flaw that made the surface tier unusable.
    """
    if tier == "paraphrase":
        strategies = [
            lambda t: _substitute(t, _SYN_BOILER, rng),
            lambda t: _substitute(t, _SYN_PROSE, rng),
            lambda t: _substitute(t, _CONTRACTIONS, rng),
            lambda t: _reorder(t, rng),
        ]
        rng.shuffle(strategies)
        strategies.append(lambda t: _telegraphic(t, rng))   # guaranteed fallback
        for fn in strategies:
            out = fn(text)
            if out != text:
                return out
        return text

    kind = rng.choice(SURFACE_KINDS)
    if kind == "case":
        return text.upper() if rng.random() < 0.5 else text.capitalize()
    if kind == "punct":
        return text.replace(",", "").replace(".", "") + "."
    if kind == "space":
        i = text.find(" ", len(text) // 2)
        return text[:i] + "  " + text[i + 1:] if i > 0 else text + " "
    if kind == "trail":
        return f"  {text}  "
    # single-character typo, away from the edges
    if len(text) > 12:
        i = rng.randrange(4, len(text) - 4)
        return text[:i] + rng.choice("aeioustr") + text[i + 1:]
    return text
