#!/usr/bin/env python3
"""A real, human-authored alias corpus — extracted from `terpsi-music`.

IDEAS.md §3.4 stage 3. Stages 1 and 2 both ran on `corpora.aliased`, which is
synthetic and therefore only tests **derivation**: a model given
`jarvale robotics group 41` can manipulate that string but cannot *know* what
the thing is called. §3.4's own "still untested" list names the two gaps this
module exists to close — **real corpora** and **human-authored probes**.

Where the strings come from
---------------------------
Every surface and every probe in this corpus is a **verbatim span of prose one
person wrote** across fourteen documents of `terpsi-music`, at a time when none
of it was going to be used for matching. Claude's only role is *annotation* —
deciding which existing human phrase refers to which file. It authors nothing.

That distinction is the whole point of stage 3, so it is enforced rather than
promised: :func:`gate` re-reads the named source file and discards any span that
is not a literal substring of it. An agent that paraphrases, tidies, or invents
a plausible alternate is dropped by the gate and counted in the rejection tally.
The tally is reported every run — **a 0% rejection rate is a reason to distrust
the gate, not a clean bill of health.**

What this corpus can express that `aliased` cannot
--------------------------------------------------
The knowledge case. Hand-measured against :class:`StringMatcher`:

    "the sensitivity ladder"     -> docs/SENSITIVITY.md   sim 0.615
    "the eight text-only checks" -> craft/                sim 0.067

Nothing about the canonical string gets you to either. `aliased`'s families are
all reachable by string manipulation; four of five, at least. Here most are not.

The seal/probe split
--------------------
Surfaces are partitioned by **the document they appear in**, never by referent.
Seal the surfaces written in document set A, probe with the surfaces written in
document set B. No string is ever both sealed and probed, so recall measures
generalisation to unseen phrasing rather than lookup — the failure that produced
stage 1's flattering `K=5 -> 1.000` (§3.4, blind #2).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
from collections import Counter, defaultdict

# The corpus lives in another repository, and that is a real limitation rather
# than a configuration detail: **this bench cannot run in Nestor's CI.** The
# verbatim gate's whole value is that it re-reads the source text, so without
# the clone the gate cannot execute and the "human-authored" claim has nothing
# behind it. It degrades loudly — every span is rejected as "source_file does
# not exist" — rather than skipping to a green run on an empty corpus.
#
# Point `TERPSI_ROOT` at a checkout of `rudi193-cmd/terpsi-music`. The recorded
# result carries the revision, because a later revision is a different corpus.
TERPSI = pathlib.Path(os.environ.get("TERPSI_ROOT", "/workspace/terpsi-music"))

MIN_LEN, MAX_LEN = 8, 90

# Anaphora, not names. A person writing "this document", "that document" or
# "the previous version of this section" is *pointing*, not naming, and nobody
# types any of them into a search box. They arrive from an extractor doing
# exactly what it was told — they are referring expressions — so they are
# removed by a rule rather than by an agent's taste or by a blocklist grown to
# fit the results.
#
# The rule: reject a span whose tokens are ALL drawn from these two closed sets.
# One content word anywhere ("the *lane* model", "`CLAUDE.md`'s one-line gloss")
# and the span survives.
_POINTERS = {
    "a", "an", "the", "this", "that", "these", "those", "its", "it", "of",
    "in", "and", "s", "own", "previous", "earlier", "first", "last", "entire",
    "same", "one", "line", "above", "below", "here", "current",
}
_GENERIC_NOUNS = {
    "document", "documents", "doc", "docs", "file", "files", "map", "survey",
    "sweep", "repo", "repository", "section", "sections", "list", "table",
    "tables", "schema", "design", "plan", "thesis", "revision", "version",
    "entry", "note", "notes", "text", "page", "gloss", "part", "piece", "thing",
}
_WORD = re.compile(r"[a-z0-9]+")


def is_generic(span: str) -> bool:
    """True when every token is a pointer or a generic document noun."""
    toks = _WORD.findall(span.lower())
    return bool(toks) and all(t in _POINTERS or t in _GENERIC_NOUNS for t in toks)

_DIGITS = re.compile(r"\d+")


def template_key(span: str, matcher) -> str:
    """The span with every run of digits removed — its template family.

    `§14 of the capability map` and `§20 of the capability map` share a key, as
    do `CLAUDE.md #17` and `CLAUDE.md #19`. Sealing one and probing another is a
    lookup with a character changed — blind #2 (§3.4) through a third door, and
    on this corpus it carried the *entire* non-zero recall of the first complete
    run (0.585 at threshold 0.80, all of it from this family).

    Two rules were tried and rejected before this one, and both failures are
    worth keeping:

    * A regex for `^§N of the ...` was too narrow and arbitrary — it caught
      "§8.1 of the architecture" and missed "CLAUDE.md #17", for no reason
      except that the section form happened to be noticed first.
    * "Drop any span containing its own canonical" was too wide. It also drops
      "the sensitivity ladder" and "the lane model", which are what the human
      actually calls those files. Keeping only spans that share *no* substring
      with the canonical would leave a corpus a character matcher cannot
      possibly match, and report the resulting 0.000 as a finding. A benchmark
      that guarantees its own conclusion is not measuring anything.

    Removing digits targets the artifact and nothing else.
    """
    return _DIGITS.sub("", matcher.normalize(span)).strip()


def _canonical(referent: str, deslug: bool = True) -> str:
    """The name a person would give if asked what the artifact is called.

    The stem, not the path: a search box gets `SENSITIVITY`, not
    `docs/SENSITIVITY.md`. Using the full path would inflate the canonical-only
    arm's *distance* from every probe for a reason that has nothing to do with
    aliasing (two constant path components every probe lacks), which would flatter
    the multi-surface arms by comparison.

    **De-slugged by default, and that choice matters.** `StringMatcher.normalize`
    strips punctuation without inserting a space, so `CAPABILITY-MAP` collapses to
    `capabilitymap` — one token where the probe has two::

        sim("CAPABILITY-MAP",  "the capability map") = 0.839
        sim("capability map",  "the capability map") = 0.875

    That penalty is a filename convention, not an aliasing failure, and it falls
    entirely on the baseline arm this bench is trying to beat. Turning hyphens and
    underscores into spaces removes it, which makes the comparison *harder* for
    the hypothesis — the conservative direction, and the only defensible one when
    an artifact happens to point the way you want.
    """
    stem = referent.rstrip("/").split("/")[-1]
    if stem.endswith(".md"):
        stem = stem[:-3]
    return re.sub(r"[-_.]+", " ", stem).strip() if deslug else stem


def corpus_revision(root: pathlib.Path = TERPSI) -> str:
    """The corpus revision, recorded into every result.

    A result that names a corpus but not its revision is not reproducible: the
    prose is the data here, and one commit to `terpsi-music` changes it.
    """
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip()[:12] or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def load(path: str | pathlib.Path) -> list[dict]:
    """Read the raw extraction records. No filtering — :func:`gate` does that."""
    return json.loads(pathlib.Path(path).read_text())["records"]


def gate(records: list[dict], root: pathlib.Path = TERPSI,
         matcher=None) -> tuple[list[dict], dict]:
    """Keep only spans that are literally present in the file they claim to be from.

    This is the mechanism the corpus's "human-authored" claim rests on. It can
    fail, and the report says how often it did.
    """
    cache: dict[str, str] = {}
    kept, rejects = [], Counter()
    seen: set[tuple[str, str]] = set()

    # Deterministic order, so which document a repeated phrase is attributed to
    # does not depend on which extraction agent finished first. See the dedup
    # rule below — that attribution decides which side of the split it lands on.
    records = sorted(records, key=lambda r: (r.get("source_file", ""),
                                             r.get("referent", ""),
                                             r.get("span", "")))

    for r in records:
        src, span, ref = r.get("source_file", ""), r.get("span", ""), r.get("referent", "")
        f = root / src
        if not f.is_file():
            rejects["source_file does not exist"] += 1
            continue
        if not (root / ref.rstrip("/")).exists():
            rejects["referent does not exist"] += 1
            continue
        if src == ref:
            # A document referring to itself is a real thing people write
            # ("this document's parent"), but it is not an alias anyone would
            # search with, and it lets a referent be sealed from its own text.
            rejects["self-reference"] += 1
            continue
        if not MIN_LEN <= len(span) <= MAX_LEN:
            rejects["length out of range"] += 1
            continue
        if is_generic(span):
            rejects["generic anaphora"] += 1
            continue
        text = cache.setdefault(src, f.read_text(errors="replace"))
        if span not in text:
            rejects["NOT VERBATIM"] += 1
            continue
        # Only exact record duplicates are dropped — same span, same source,
        # same referent, reported twice by two extraction passes.
        #
        # An earlier version deduplicated on (span, referent) *across* documents,
        # to stop the human's repeated "the capability map" from landing on both
        # sides of the split as an exact-match lookup. That was the right worry
        # and the wrong mechanism: it silently starved whichever side sorted
        # later, and the recall it produced was a property of the alphabet.
        # The lookup case is removed where it actually arises — at split time,
        # against the sealed set, counted and reported. See :func:`split`.
        if (span, src, ref) in seen:
            rejects["duplicate record"] += 1
            continue
        seen.add((span, src, ref))
        kept.append({"span": span, "source_file": src, "referent": ref})

    return kept, {"in": len(records), "kept": len(kept),
                  "rejected": len(records) - len(kept), "by_reason": dict(rejects)}


def split(records: list[dict], seal_docs: set[str], matcher=None,
          strict: bool = False) -> tuple[dict[str, list[str]], list[tuple[str, str]], dict]:
    """Partition by source document, never by referent.

    Returns ``(surfaces_by_referent, probes, report)`` where each probe is
    ``(span, referent)``. A referent with no sealed surface still contributes
    probes — dropping those would silently restrict the query distribution to
    the meanings the seal set happened to cover, which is the coverage effect
    this bench exists to measure.

    **The lookup case is removed here.** The human writes "the capability map"
    in five documents, so the same string lands on both sides of the split; left
    alone it would be found by exact match and recall would be measuring whether
    a string was sealed, not whether the matcher bridges phrasings. That is
    stage 1's blind #2 arriving through a different door. Any probe whose
    normalized form is already in the sealed set is dropped, and the count is
    reported — a large `exact_dropped` means the split is doing less work than
    it appears to.

    Dropping is computed against the FULL sealed set (canonical plus every
    human surface) once, so every arm answers the same probe list.
    """
    surfaces: dict[str, list[str]] = defaultdict(list)
    probes: list[tuple[str, str]] = []
    for r in records:
        if r["source_file"] in seal_docs:
            surfaces[r["referent"]].append(r["span"])
        else:
            probes.append((r["span"], r["referent"]))

    report = {"probes_before_drop": len(probes), "exact_dropped": 0,
              "template_sibling_dropped": 0}
    if matcher is not None and surfaces:
        sealed = [s for ref, ss in surfaces.items() for s in [_canonical(ref)] + ss]
        sealed_norm = {matcher.normalize(s) for s in sealed}
        kept = [(p, ref) for p, ref in probes if matcher.normalize(p) not in sealed_norm]
        report["exact_dropped"] = len(probes) - len(kept)

        # Template siblings, dropped for the same reason as exact matches and
        # counted separately so the two are never confused for each other.
        sealed_keys = {template_key(s, matcher) for s in sealed}
        kept2 = [(p, ref) for p, ref in kept
                 if template_key(p, matcher) not in sealed_keys]
        report["template_sibling_dropped"] = len(kept) - len(kept2)

        # `strict`: also drop a probe that CONTAINS a sealed surface, or is
        # contained by one. "§14 of the capability map" against a sealed "The
        # capability map" is not the matcher bridging two phrasings — the
        # answer is sitting inside the query as a substring.
        #
        # This is reported as a second cut rather than applied by default,
        # because it is not obviously the right one. It also removes "the
        # sensitivity ladder" against the canonical `SENSITIVITY`, which *is*
        # what the human calls that file — substring inclusion is the easy half
        # of real aliasing, not a fake version of it. The inclusive cut flatters
        # the mechanism; the strict cut selects for cases a character matcher
        # cannot do and would report its own conclusion. Neither number is the
        # answer alone, so both are printed.
        if strict:
            kept3 = [(p, ref) for p, ref in kept2
                     if not any(n and (n in matcher.normalize(p)
                                       or matcher.normalize(p) in n)
                                for n in sealed_norm)]
            report["containment_dropped"] = len(kept2) - len(kept3)
            kept2 = kept3
        probes = kept2
    report["probes"] = len(probes)
    return dict(surfaces), probes, report


def dispersion(records: list[dict], matcher) -> dict:
    """Measure the corpus property every result depends on, in the harness.

    Two numbers, both of which have been an artifact before (§3.4, blinds #1
    and #2):

    ``canonical_sim`` — how far the human's alternate names sit from the
    canonical. If this clusters high the corpus cannot express aliasing at all.

    ``exact_rate`` — the fraction of spans that normalize *identically* to the
    canonical. Those are lookups wearing a fuzzy-match costume. Stage 1 shipped
    a number where this was 100% for one probe tier.
    """
    sims = []
    exact = 0
    for r in records:
        a = matcher.normalize(r["span"])
        b = matcher.normalize(_canonical(r["referent"]))
        sims.append(matcher.similarity(a, b))
        if a == b:
            exact += 1
    sims.sort()
    n = len(sims) or 1

    def q(p):
        return round(sims[min(len(sims) - 1, int(p * len(sims)))], 4) if sims else 0.0

    return {"n": len(sims), "p10": q(0.10), "p50": q(0.50), "p90": q(0.90),
            "max": round(sims[-1], 4) if sims else 0.0,
            "exact_rate": round(exact / n, 4),
            "above_0.92": round(sum(1 for s in sims if s >= 0.92) / n, 4)}
