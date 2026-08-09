#!/usr/bin/env python3
"""How well a Nestor memory answers its own questions back — the recall half.

    python bench/retrieval_quality.py --demo
    python bench/retrieval_quality.py --store PATH --from en --to es --matcher string

``nestor.calibrate`` already answers one half of "is this memory trustworthy":
sample sealed rows, sweep the seal threshold, count how often a DIFFERENT
sealed row would serve as the wrong verified answer. That is the false-serve
half, and this module does not reimplement it — every collision number below
comes from calling :func:`nestor.calibrate.calibrate` on the same sealed store
this module built, not from a second scan written here.

What calibrate's own docstring names as the thing it cannot see is the other
half: *"your memory contains no record of the paraphrases nobody asked yet."*
This is that record, generalised past the one corpus ``demo/the_dogfooding.py``
measured it on. Three questions, corpus- and matcher-agnostic:

1. **Verbatim floor.** Seal every row, query each by its own ``source_text``,
   count how many serve back their own ``target_text``. Should be ~100% — a
   miss here means serving is broken, not that the corpus is hard. Everything
   below stands on this.
2. **Recall under query compression.** Query each row by a mechanically
   shortened form of its source — first sentence only, or the first N
   characters — and count served / wrong / pending at the seal bar. A human
   asking the gist months later does not retype the sealed sentence; this is
   the authoring-free version of that, run over the whole corpus rather than a
   hand-picked list of paraphrases.
3. **Collisions**, delegated whole to :func:`nestor.calibrate.calibrate`. This
   module surfaces its numbers and its ``summarize()`` text; it does not scan
   for collisions itself.

Matcher- and corpus-agnostic
-----------------------------
Nothing here reads a language pair, a store schema, or a matcher class by
name. It takes ``[{"source_text", "target_text"}, ...]``, a ``(source_lang,
target_lang)`` domain and any object satisfying :class:`nestor.matcher.Matcher`,
and reports the same three numbers regardless of what produced them — the CLI
below is one convenience wrapper (a store path, or ``--demo``'s tiny seeded
corpus) over a function that does not know the CLI exists.

**Nothing here seals in a real store.** Every measurement seals a throwaway
temp copy under a fixture key, exactly the technique
``demo/the_dogfooding.py``'s ``seal_a_copy`` uses, and every number is produced
by running the queries here, not asserted from memory — the house rule
(``docs/agent-guide.md`` "Checked, not assumed") applies to a bench file same
as anywhere else.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
from typing import Callable, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# A fixture's key is not a secret. Seals below are really signed so the serve
# path is really exercised — a bench that measured retrieval with signing off
# would be measuring a store that serves rows nobody could have sealed. Set
# with setdefault (not assignment) so a caller's own NESTOR_SEAL_KEY wins, and
# repeated at the top of seal_corpus() because pytest's isolate_globals fixture
# pops this variable between tests, so a module-level setdefault alone is only
# good for one process's first import, not for every test that imports it.
os.environ.setdefault("NESTOR_SEAL_KEY", "retrieval-quality-fixture-key-not-a-secret")

from nestor import cascade, calibrate, memory                   # noqa: E402
from nestor.matcher import Matcher, StringMatcher, matcher_audit_fields  # noqa: E402
from nestor.sqlite_store import SqliteStore                     # noqa: E402
from recipes import patch_review                                # noqa: E402

FIXTURE_KEY = "retrieval-quality-fixture-key-not-a-secret"
FIXTURE_VERIFIER = "retrieval-quality-fixture"
ORIGIN = "bench:retrieval-quality"

DEFAULT_CHARS = 40

_SENTENCE_END = re.compile(r"(.+?[.?!])(\s|$)")


# --------------------------------------------------------------------------
# Compression — the mechanical stand-in for "a human asked the gist"
# --------------------------------------------------------------------------

def first_sentence(text: str) -> str:
    """The first sentence of ``text``, or the whole (stripped) text if it has
    no sentence-ending punctuation. Same rule ``demo/the_dogfooding.py``'s
    sweep uses, lifted here so a second copy of this regex does not drift from
    the one it was measured with."""
    m = _SENTENCE_END.match(text.strip())
    return m.group(1) if m else text.strip()


def first_chars(text: str, n: int) -> str:
    """The first ``n`` characters of ``text``, stripped.

    Cruder than :func:`first_sentence` on purpose — no notion of grammar, just
    "a human typed less of it", which is a different (and for some prose,
    more realistic) way a query gets short.
    """
    return text.strip()[:n].strip()


def _compressor(name: str, chars: int) -> Callable[[str], str]:
    if name == "first-sentence":
        return first_sentence
    if name == "chars":
        return lambda text: first_chars(text, chars)
    raise ValueError(f"unknown compression {name!r}; choose 'first-sentence' or 'chars'")


# --------------------------------------------------------------------------
# The temp-seal helper — nothing here ever touches a store the caller owns
# --------------------------------------------------------------------------

def seal_corpus(root: pathlib.Path, rows: list[dict], source_lang: str,
                target_lang: str, matcher: Matcher) -> SqliteStore:
    """Seal every row of ``rows`` into a fresh store at ``root``, under ``matcher``.

    Mirrors ``demo/the_dogfooding.py``'s ``seal_a_copy``: nothing this module
    measures is servable until something is sealed, and this seals a store it
    just created, never one the caller passed in. ``verifier`` names the
    fixture, not a person — nothing here is a human's decision, and the
    covenant (``docs/agent-guide.md``: "you may propose, you may not confirm")
    applies to a measurement tool exactly as it applies to an agent.
    """
    os.environ.setdefault("NESTOR_SEAL_KEY", FIXTURE_KEY)
    root.mkdir(parents=True, exist_ok=True)
    cascade.set_ledger_path(str(root / "ledger.jsonl"))
    store = SqliteStore(str(root / "nestor.db"))
    store.init_db()
    store.memory_init()
    for row in rows:
        memory.add_pair(row["source_text"], row["target_text"], source_lang,
                        target_lang, status="sealed", verifier=FIXTURE_VERIFIER,
                        origin=ORIGIN, store=store, matcher=matcher)
    return store


# --------------------------------------------------------------------------
# The measurements — each returns counts, and prints nothing it did not count
# --------------------------------------------------------------------------

def verbatim_floor(store, matcher: Matcher, rows: list[dict], source_lang: str,
                   target_lang: str) -> dict:
    """Query every row in the exact words it was sealed under.

    Should be ~100%. This is the floor everything else stands on: a miss here
    means serving itself is broken, not that the corpus or the compression is
    hard, and every number below only means something once this one is clean.
    """
    served = wrong = pending = 0
    for row in rows:
        best = memory.best_sealed(row["source_text"], source_lang, target_lang,
                                  store=store, matcher=matcher)
        if best is None:
            pending += 1
        elif best["pair"]["target_text"] == row["target_text"]:
            served += 1
        else:
            wrong += 1
    n = len(rows)
    return {"n": n, "served": served, "wrong": wrong, "pending": pending,
            "rate": (served / n) if n else None}


def recall_under_compression(store, matcher: Matcher, rows: list[dict],
                             source_lang: str, target_lang: str,
                             compression: str = "first-sentence",
                             chars: int = DEFAULT_CHARS) -> dict:
    """Query every row by a mechanically shortened form of its source.

    The half ``nestor.calibrate`` does not measure — not "does the wrong thing
    serve" but "does the RIGHT thing stop serving when a human asks the gist
    instead of the exact sealed sentence". A row whose compression is a no-op
    (already at or under the cut, or has no second sentence to drop) is
    skipped and counted separately, because shortening nothing measures
    nothing — the same guard ``demo/the_dogfooding.py``'s sweep uses.
    """
    compress = _compressor(compression, chars)
    served = wrong = pending = skipped = 0
    for row in rows:
        original = row["source_text"].strip()
        compressed = compress(row["source_text"])
        if compressed == original:
            skipped += 1
            continue
        best = memory.best_sealed(compressed, source_lang, target_lang,
                                  store=store, matcher=matcher)
        if best is None:
            pending += 1
        elif best["pair"]["target_text"] == row["target_text"]:
            served += 1
        else:
            wrong += 1
    n = served + wrong + pending
    return {"compression": compression,
            "chars": chars if compression == "chars" else None,
            "n": n, "skipped": skipped, "served": served, "wrong": wrong,
            "pending": pending, "rate": (served / n) if n else None}


# --------------------------------------------------------------------------
# The corpus — from a real store's sealed rows, or the built-in demo seed
# --------------------------------------------------------------------------

def load_corpus_from_store(db_path: pathlib.Path, source_lang: str,
                           target_lang: str, *, work: pathlib.Path) -> list[dict]:
    """Sealed ``(source_text, target_text)`` rows read from an existing store.

    Read-only by construction: ``db_path`` is copied into ``work`` first (the
    same defence ``demo/the_dogfooding.py`` beat 2 uses before touching the
    committed store) and every open below is against the copy, so the caller's
    file is never opened for write. Only rows :func:`nestor.memory.is_verified_seal`
    accepts are returned — the same filter ``nestor.calibrate.calibrate`` uses to
    pick its own corpus, so this and the collision half measure the same rows.

    **Caveat inherited from that filter, not introduced by this function:**
    verifying a signature depends on whatever ``NESTOR_SEAL_KEY`` (or keyring)
    is configured in this process. This module's own ``setdefault`` above only
    fires when nothing else set the variable first — reading a store signed
    under a real deployment key needs that key exported before this runs, the
    same as any other reader of that store.
    """
    copy_dir = work / "source-corpus"
    copy_dir.mkdir(parents=True, exist_ok=True)
    copy_path = copy_dir / "nestor.db"
    shutil.copy(db_path, copy_path)
    store = SqliteStore(str(copy_path))
    store.memory_init()
    rows = [r for r in store.memory_candidates(source_lang, target_lang)
            if memory.is_verified_seal(r)]
    store.close()
    return [{"source_text": r["source_text"], "target_text": r["target_text"]}
            for r in rows]


def demo_corpus() -> list[dict]:
    """A tiny, deterministic, invented corpus — not real, unlike
    ``demo/the_dogfooding.py``'s. It exists only so ``--demo`` has something to
    run the mechanism on with zero arguments: a few multi-sentence rows so the
    compression sweep has something to shorten, and two sources that read
    almost alike with different answers so the delegated collision half has
    something to find. Nothing here is asserted about a real memory.
    """
    return [
        {"source_text": "Where does the ledger keep its hash chain? It is one "
                        "append-only JSONL file, and each line chains to the "
                        "hash of the line before it, so a deletion is detectable.",
         "target_text": "One append-only JSONL file; each line embeds the "
                        "previous line's hash."},
        {"source_text": "What happens when a stored row fails to parse? It is "
                        "skipped and counted in the report, never silently "
                        "dropped from the count.",
         "target_text": "A row that fails to parse is skipped and counted, "
                        "not dropped."},
        {"source_text": "Why does calibrate sample instead of scanning the "
                        "whole corpus? Because the cost is sample times corpus "
                        "comparisons, and sample=0 asks for the exact number "
                        "at full cost.",
         "target_text": "Sampling keeps the sweep cheap; sample=0 runs the "
                        "whole corpus for the exact answer."},
        {"source_text": "Does best_sealed ever revise a draft?",
         "target_text": "No. best_sealed only reads; add_pair is what can "
                        "replace a draft with a sealed row."},
        {"source_text": "does the store accept a sealed entry with no verifier field",
         "target_text": "yes for a draft; a sealed row always requires a "
                        "non-empty verifier"},
        {"source_text": "does the store accept a sealed entry with no verifier value",
         "target_text": "no, a sealed row with an empty verifier is rejected "
                        "before it is written"},
    ]


# --------------------------------------------------------------------------
# The whole measurement
# --------------------------------------------------------------------------

def measure(rows: list[dict], source_lang: str, target_lang: str,
           matcher: Optional[Matcher] = None, *,
           compression: str = "first-sentence", chars: int = DEFAULT_CHARS,
           calibrate_kwargs: Optional[dict] = None,
           keep: Optional[pathlib.Path] = None) -> dict:
    """Run all three measurements against ``rows`` sealed under ``matcher``.

    ``rows`` is ``[{"source_text", "target_text"}, ...]`` — the only shape this
    function knows about. It does not read a store or a corpus file itself;
    that is :func:`load_corpus_from_store` / :func:`demo_corpus` / the CLI's
    job, so the measurement stays reusable against any corpus that fits the
    shape.

    Seals a throwaway copy (via :func:`seal_corpus`), measures the verbatim
    floor and the compression recall directly, then calls
    :func:`nestor.calibrate.calibrate` on that SAME sealed store for the
    collision half — one store, three views of it, and the third is somebody
    else's function.

    Pass ``keep`` (a directory) to leave the sealed fixture store behind for
    inspection; otherwise it is removed before this returns.
    """
    matcher = memory.get_matcher(matcher)
    work = keep or pathlib.Path(tempfile.mkdtemp(prefix="nestor-retrieval-quality-"))
    work.mkdir(parents=True, exist_ok=True)
    store = seal_corpus(work, rows, source_lang, target_lang, matcher)
    try:
        floor = verbatim_floor(store, matcher, rows, source_lang, target_lang)
        recall = recall_under_compression(store, matcher, rows, source_lang,
                                          target_lang, compression=compression,
                                          chars=chars)
        collisions = calibrate.calibrate(store, source_lang, target_lang,
                                         matcher=matcher, **(calibrate_kwargs or {}))
    finally:
        store.close()
        if keep is None:
            shutil.rmtree(work, ignore_errors=True)
    return {
        "domain": {"source_lang": source_lang, "target_lang": target_lang},
        "corpus": len(rows),
        "verbatim_floor": floor,
        "recall_under_compression": recall,
        "collisions": collisions,
        **matcher_audit_fields(matcher),
    }


def summarize(result: dict) -> str:
    """The measurement as a human reads it — verbatim floor first, then
    recall, then the collision half in ``nestor.calibrate``'s own words."""
    d = result["domain"]
    vf = result["verbatim_floor"]
    rc = result["recall_under_compression"]
    lines = [f"{result['corpus']} row(s) in {d['source_lang']}->{d['target_lang']}, "
             f"matcher {result['matcher']}"]
    if not result["corpus"]:
        return lines[0] + "\n  nothing to measure — the corpus is empty."
    lines.append("")
    lines.append("  1. verbatim floor — queried in the words it was sealed under")
    floor_line = (f"     {vf['served']}/{vf['n']} served, {vf['wrong']} wrong, "
                 f"{vf['pending']} pending")
    if vf["n"] and vf["served"] != vf["n"]:
        floor_line += "   <-- serving is broken, not the corpus"
    lines.append(floor_line)
    lines.append("")
    tag = (f"{rc['compression']}" if rc["compression"] != "chars"
          else f"chars, first {rc['chars']}")
    lines.append(f"  2. recall under query compression ({tag})")
    if rc["n"] == 0:
        lines.append(f"     no row's source changed under this compression "
                     f"({rc['skipped']} skipped) — nothing measured")
    else:
        lines.append(f"     {rc['served']}/{rc['n']} served, {rc['wrong']} wrong, "
                     f"{rc['pending']} pending  ({rc['skipped']} skipped, no-op)")
        lines.append("     recall falling toward pending rather than wrong is "
                     "the product working, not failing.")
    lines.append("")
    lines.append("  3. collisions at the seal bar — nestor.calibrate.calibrate(), verbatim:")
    lines.append("     " + calibrate.summarize(result["collisions"]).replace("\n", "\n     "))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_matcher(name: str) -> Matcher:
    """``"string"`` -> :class:`nestor.matcher.StringMatcher`; ``"defect"`` ->
    ``recipes.patch_review.MATCHER``. The two matchers ``demo/the_dogfooding.py``
    compared, named the way this repo's other CLIs name a shipped matcher."""
    key = (name or "string").strip().lower()
    if key == "string":
        return StringMatcher()
    if key == "defect":
        return patch_review.MATCHER
    raise SystemExit(f"unknown matcher {name!r}; choose 'string' or 'defect'")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", default="", help="path to an existing store .db "
                    "to read sealed rows from (read-only; a copy is opened)")
    ap.add_argument("--source-lang", "--from", dest="source_lang", default="en")
    ap.add_argument("--target-lang", "--to", dest="target_lang", default="es")
    ap.add_argument("--matcher", default="string", choices=("string", "defect"),
                    help="string -> StringMatcher, defect -> "
                         "recipes.patch_review.MATCHER")
    ap.add_argument("--compression", default="first-sentence",
                    choices=("first-sentence", "chars"),
                    help="how the recall probe shortens each source_text")
    ap.add_argument("--chars", type=int, default=DEFAULT_CHARS,
                    help="cutoff for --compression chars (default %(default)s)")
    ap.add_argument("--sample", type=int, default=300,
                    help="rows sampled for the collision sweep; 0 = whole corpus")
    ap.add_argument("--target-rate", type=float, default=calibrate.DEFAULT_TARGET,
                    help="collision rate calibrate.py's sweep aims to reach")
    ap.add_argument("--demo", action="store_true",
                    help="measure a tiny built-in seeded corpus; ignores --store")
    ap.add_argument("--keep", default="", help="leave the sealed fixture store here")
    ap.add_argument("--json", action="store_true",
                    help="print the structured result as JSON instead of the summary")
    args = ap.parse_args(argv)

    if args.demo:
        rows = demo_corpus()
        source_lang = target_lang = "demo"
    elif args.store:
        source_lang, target_lang = args.source_lang, args.target_lang
        load_work = pathlib.Path(tempfile.mkdtemp(prefix="nestor-retrieval-quality-load-"))
        try:
            rows = load_corpus_from_store(pathlib.Path(args.store), source_lang,
                                          target_lang, work=load_work)
        finally:
            shutil.rmtree(load_work, ignore_errors=True)
    else:
        ap.error("pass --store PATH (with --from/--to) or --demo")
        return 2

    if not rows:
        print("No sealed rows found for that domain — nothing to measure.")
        return 1

    matcher = build_matcher(args.matcher)
    keep = pathlib.Path(args.keep) if args.keep else None
    result = measure(rows, source_lang, target_lang, matcher,
                     compression=args.compression, chars=args.chars,
                     calibrate_kwargs={"sample": args.sample,
                                       "target_rate": args.target_rate},
                     keep=keep)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(summarize(result))
    if args.keep:
        print(f"\nkept: {args.keep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
