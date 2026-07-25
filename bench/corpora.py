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
import pkgutil
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
# perturbations — "the same phrase, typed by a human on a different day"
# --------------------------------------------------------------------------

def perturb(text: str, rng: random.Random) -> str:
    """A realistic re-typing of ``text``: case, punctuation, spacing, one typo.

    A matcher SHOULD still serve the sealed pair for these — they are the same
    segment. Used to measure recall against the false-seal rate.
    """
    kind = rng.choice(("case", "punct", "space", "typo", "trail"))
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
