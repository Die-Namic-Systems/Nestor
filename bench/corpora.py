"""Deterministic corpora for the bench, spanning diversity AND key length.

Three shapes. Diversity matters because Nestor's accuracy depends on how much
the sealed phrases resemble each other; **key length matters because difflib
behaves differently past 200 characters**, and for a long time nothing here
reached that far:

* :func:`boilerplate` — templated legal text drawn from a small word pool. Near
  worst case for a character-ratio matcher: every phrase shares most of its
  characters with every other phrase.
* :func:`prose` — real English sentences harvested from the Python standard
  library's docstrings. No network, no fixtures to vendor, and genuinely
  diverse vocabulary and length.

* :func:`code` — real Python function sources, every one normalizing to 200+
  characters. Exists because the other two do not: difflib's ``autojunk``
  engages at 200 elements, and StringMatcher was broken in exactly that regime
  (scores collapsing, `similarity` not symmetric) while this bench reported
  everything healthy. See :func:`length_coverage`.

All are seeded, so a bench run is reproducible.
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


# --------------------------------------------------------------------------
# code — the LONG end, which nothing else here reaches
# --------------------------------------------------------------------------
#
# Every other corpus normalizes well under 200 characters: boilerplate to ~70,
# prose to 40-180. That left difflib's ``autojunk`` regime — which engages once
# the compared sequence reaches 200 elements — completely untested, and it is
# where StringMatcher was found to be broken (scores collapsing from ~0.95 to
# ~0.55, and `similarity` not symmetric). A real code corpus found both defects
# in one pass; this bench could not have.
#
# Function bodies are the natural long unit: offline, deterministic, and shaped
# like a genuine Nestor use case (the entity/schema-mapping recipes match code
# identifiers and SQL).

_CODE_MODULES = ("json argparse logging inspect difflib pathlib datetime collections "
                 "functools statistics shutil socket sqlite3 subprocess threading "
                 "unittest csv configparser dataclasses decimal enum gzip hashlib "
                 "heapq http.client ipaddress mimetypes pickle pprint queue sched "
                 "shlex smtplib ssl string tarfile tempfile tokenize traceback uuid "
                 "zipfile asyncio base64 bdb calendar cmd codecs copy ftplib "
                 "getpass glob gettext imaplib io locale mailbox netrc nntplib "
                 "optparse os platform plistlib poplib pstats pydoc random re "
                 "secrets selectors shelve signal site stat struct symtable "
                 "textwrap timeit types typing warnings weakref webbrowser "
                 "xml.etree.ElementTree zoneinfo").split()

# Lower bound puts every unit past the autojunk threshold — the whole point.
# Upper bound keeps the bench tractable: with autojunk=False (now the default,
# and required for correctness) scoring costs ~43x at 400 characters and ~78x at
# 800, so unbounded 8k-character outliers would dominate a run without testing
# anything the 200-1500 band does not.
_CODE_MIN_NORM = 200
_CODE_MAX_NORM = 1500

_CODE_CACHE: "list[str] | None" = None


def _harvest_code() -> list[str]:
    """Function sources from the stdlib, sliced by line number.

    Deliberately NOT ``ast.get_source_segment``: that re-scans the whole file per
    node, which made harvesting ~31s and put that on every CI run through the
    coverage guard. Splitting each module once and slicing by ``lineno`` /
    ``end_lineno`` is the same result for whole statements, ~100x faster.
    """
    import ast
    import inspect
    out: list[str] = []
    m = _string_matcher()
    for name in _CODE_MODULES:
        try:
            src = inspect.getsource(importlib.import_module(name))
            tree = ast.parse(src)
        except Exception:
            continue
        lines = src.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            end = getattr(node, "end_lineno", None)
            if end is None:
                continue
            seg = "\n".join(lines[node.lineno - 1:end])
            if _CODE_MIN_NORM <= len(m.normalize(seg)) <= _CODE_MAX_NORM:
                out.append(seg)
    return out


def _string_matcher():
    from nestor.matcher import StringMatcher
    return StringMatcher()


def code(n: int, seed: int = 7, offset: int = 0) -> list[str]:
    """``n`` real Python function sources, every one normalizing to 200+ chars."""
    global _CODE_CACHE
    if _CODE_CACHE is None:
        uniq = sorted(set(_harvest_code()))
        random.Random(4321).shuffle(uniq)
        _CODE_CACHE = uniq
    pool = _CODE_CACHE
    if n > len(pool):
        raise ValueError(f"code corpus holds {len(pool)} functions; asked for {n}. "
                         f"Add modules to _CODE_MODULES or lower the requested size.")
    start = offset % len(pool)
    out = pool[start:start + n]
    if len(out) < n:
        out += pool[:n - len(out)]
    return out


def available_code() -> int:
    code(1)
    return len(_CODE_CACHE or [])


CORPORA = {"boilerplate": boilerplate, "prose": prose, "code": code}

# difflib engages its ``autojunk`` heuristic once the compared sequence reaches
# this many elements, changing scores materially. A corpus set that never
# crosses it cannot detect a defect that only appears above it.
AUTOJUNK_THRESHOLD = 200


def length_coverage(sample: int = 300) -> dict:
    """Normalized key-length stats per corpus, and whether the set spans the
    ``autojunk`` boundary.

    This exists so the blind spot that hid two real matcher bugs is *visible* in
    every result file rather than implicit in the choice of corpora. If
    ``spans_autojunk_threshold`` is False, this bench cannot see the regime where
    difflib changes behaviour, whatever else it reports.
    """
    m = _string_matcher()
    out: dict = {"autojunk_threshold": AUTOJUNK_THRESHOLD, "corpora": {}}
    any_over = False
    for name, gen in CORPORA.items():
        try:
            lens = sorted(len(m.normalize(x)) for x in gen(sample))
        except ValueError:                      # pool smaller than the sample
            lens = sorted(len(m.normalize(x)) for x in gen(50))
        at = lambda q: lens[min(len(lens) - 1, int(q * len(lens)))]  # noqa: E731
        over = sum(1 for x in lens if x >= AUTOJUNK_THRESHOLD)
        any_over = any_over or over > 0
        out["corpora"][name] = {
            "p10": at(.10), "p50": at(.50), "p90": at(.90),
            "min": lens[0], "max": lens[-1],
            "share_over_autojunk_threshold": round(over / len(lens), 3),
        }
    out["spans_autojunk_threshold"] = any_over
    return out

# --------------------------------------------------------------------------
# aliased — one meaning, several LEXICALLY DISJOINT surfaces (IDEAS.md §3.4)
# --------------------------------------------------------------------------
#
# boilerplate and prose both model "the same sentence, retyped." perturb()
# then varies them, and the variation lands at similarity 0.62-0.85 — a tight
# cluster around one canonical string.
#
# The miss class §3.4 is about is not that. `AWS` / `Amazon Web Services` score
# 0.273; `Q3 2025` / `September 30 2025` score 0.500. Those are the SAME
# referent wearing surfaces that share almost no characters, and no amount of
# perturbing one string produces the other. bench_surfaces.py was built before
# this generator existed and was consequently blind to its own subject: the
# canonical surface won 117 matches out of 117, because in a cluster geometry
# the centroid is always the best bridge.
#
# This generator emits the disjoint case directly. Each meaning is a LIST of
# surfaces drawn from distinct families, so the return shape differs from the
# other two corpora — list[list[str]] rather than list[str]. That is deliberate:
# a meaning with one surface cannot express this phenomenon at all, so the type
# refuses to represent it.

_CO_PLACE = ("northwind arden belmont crestline dunmore eastgate fairhaven "
             "glenrock harrowby inverness jarvale kestrel langmere marchford "
             "norbury oakhurst pendral quarrow ravensby stonebridge").split()
_CO_TRADE = ("logistics dynamics analytics foundry robotics textiles maritime "
             "aerospace chemical pharma networks systems holdings ventures "
             "minerals petroleum insurance shipping timber granite").split()
_CO_SUFFIX = ("corporation incorporated limited group partners holdings").split()
_LEG_FIRST = ("bergstrom caldwell delacroix ellsworth fairbanks garrity "
              "hollingsworth ivanov jorgensen kowalski lindqvist mortimer "
              "nakamura okonkwo petrov quillan rasmussen sandoval thackeray "
              "ueland").split()
_LEG_TRADE = ("freight bros trading works mills supply co brothers "
              "enterprises industries").split()


def _acronym(words: list[str]) -> str:
    return "".join(w[0] for w in words).upper()


def _ticker(words: list[str]) -> str:
    """A 4-letter ticker from the name's consonants — disjoint from the full
    form by construction, and stable for a given name."""
    letters = [c for c in "".join(words) if c not in "aeiou"]
    return "".join(letters[:4]).upper() or "".join(words)[:4].upper()


def aliased(n: int, seed: int = 7, offset: int = 0) -> list[list[str]]:
    """``n`` meanings, each a list of lexically disjoint surfaces for ONE referent.

    Five families per meaning, in a fixed priority order — roughly how often a
    real query would use each:

    ==  ==============  ==================================
    0   full            ``northwind logistics corporation``
    1   short           ``northwind logistics``
    2   acronym         ``NLC``
    3   ticker          ``NRTH``
    4   legacy name     ``bergstrom freight``
    ==  ==============  ==================================

    The legacy name shares no words with the others at all — a rename, which is
    the hardest and most realistic instance of the class: nothing about the
    current name lets you recover it.

    Unlike :func:`boilerplate` and :func:`prose` this returns a list of surface
    LISTS. Verify the defining property with :func:`aliased_dispersion` rather
    than trusting this docstring — the whole reason this generator exists is
    that a corpus property was once assumed and turned out to be false.
    """
    rng = random.Random(seed)
    out: list[list[str]] = []
    for i in range(n):
        place = rng.choice(_CO_PLACE)
        trade = rng.choice(_CO_TRADE)
        suffix = rng.choice(_CO_SUFFIX)
        # The section-style disambiguator keeps meanings distinct at scale
        # without making the surfaces resemble each other any more than they do.
        tag = str(offset + i)
        words = [place, trade]
        out.append([
            f"{place} {trade} {suffix} {tag}",
            f"{place} {trade} {tag}",
            f"{_acronym(words)}{tag}",
            f"{_ticker(words)}{tag}",
            f"{rng.choice(_LEG_FIRST)} {rng.choice(_LEG_TRADE)} {tag}",
        ])
    return out


_SUFFIX_ABBREV = {"corporation": "corp", "incorporated": "inc", "limited": "ltd",
                  "group": "grp", "partners": "ptnrs", "holdings": "hldgs"}


def aliased_query(surface: str, rng: random.Random) -> str:
    """Realistic non-exact rendering of one aliased surface.

    :func:`perturb` does not bite on these strings and silently returns them
    unchanged — 88% of surface-tier and 100% of paraphrase-tier probes
    normalized identically to their source, which turned the §3.4 bench into a
    test of whether the exact string was sealed. Its strategies assume long
    sentences: the synonym tables hold no company vocabulary, ``_reorder`` needs
    clauses, ``_telegraphic`` needs function words to drop, and the typo rule
    requires more than 12 characters, so a 3-character acronym passes straight
    through.

    This applies noise a *person* would introduce when typing a name they know:
    abbreviating the legal suffix, dotting an acronym, dropping the suffix
    entirely, or a single typo. Always returns something that differs after
    normalization when it can — verify with :func:`aliased_query_bite` rather
    than trusting this docstring.
    """
    words = surface.split()
    choices = []

    if len(words) > 1 and words[-2].lower() in _SUFFIX_ABBREV:
        choices.append(lambda: " ".join(
            words[:-2] + [_SUFFIX_ABBREV[words[-2].lower()], words[-1]]))
        choices.append(lambda: " ".join(words[:-2] + [words[-1]]))   # drop it
    if len(words) > 2:
        choices.append(lambda: " ".join(words[:-2] + [words[-1]]))   # drop a word
    head = words[0]
    if head.isupper() and len(head) >= 2:
        choices.append(lambda: ".".join(head) + ". " + " ".join(words[1:]))
        choices.append(lambda: head[0] + head[1:].lower() + " " + " ".join(words[1:]))
    if len(surface) > 6:
        def typo():
            i = rng.randrange(1, len(surface) - 1)
            return surface[:i] + rng.choice("aeiourstn") + surface[i + 1:]
        choices.append(typo)

    rng.shuffle(choices)
    for fn in choices:
        out = fn().strip()
        if out and out.lower() != surface.lower():
            return out
    return surface


def aliased_query_bite(meanings: list[list[str]], rng_seed: int = 7,
                       matcher=None) -> dict:
    """How far :func:`aliased_query` actually moves a surface, measured.

    ``identical`` is the number that matters: if it is high the bench is testing
    exact lookup, not matching, and every recall figure computed on it is void.
    """
    if matcher is None:
        from nestor.matcher import StringMatcher
        matcher = StringMatcher()
    rng = random.Random(rng_seed)
    sims, identical = [], 0
    for meaning in meanings:
        for surf in meaning:
            probe = aliased_query(surf, rng)
            a, b = matcher.normalize(probe), matcher.normalize(surf)
            if a == b:
                identical += 1
            sims.append(matcher.similarity(a, b))
    sims.sort()
    return {"n": len(sims), "identical": identical,
            "identical_pct": round(identical / max(1, len(sims)), 4),
            "p50": round(sims[len(sims) // 2], 3),
            "p10": round(sims[int(len(sims) * 0.1)], 3)}


def aliased_dispersion(meanings: list[list[str]], matcher=None) -> dict:
    """Measured pairwise similarity WITHIN each meaning's surface set.

    The point of :func:`aliased` is that its surfaces are lexically disjoint.
    That is a claim about the data, so it is measured here and reported into the
    bench results rather than asserted in a docstring. If ``median`` drifts up
    into perturb's 0.62-0.85 band, this corpus has stopped modelling the
    disjoint case and any §3.4 number computed on it is void.
    """
    if matcher is None:
        from nestor.matcher import StringMatcher
        matcher = StringMatcher()
    sims = []
    for surfaces in meanings:
        norms = [matcher.normalize(s) for s in surfaces]
        for a in range(len(norms)):
            for b in range(a + 1, len(norms)):
                sims.append(matcher.similarity(norms[a], norms[b]))
    if not sims:
        return {}
    sims.sort()
    return {
        "n_pairs": len(sims),
        "min": round(sims[0], 3),
        "p50": round(sims[len(sims) // 2], 3),
        "p90": round(sims[int(len(sims) * 0.9)], 3),
        "max": round(sims[-1], 3),
        "mean": round(sum(sims) / len(sims), 3),
    }



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
