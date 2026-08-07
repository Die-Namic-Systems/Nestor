#!/usr/bin/env python3
"""Four claims, two rules — jeles' corroboration and Nestor's seal, on one page.

    python demo/the_verification.py            # needs jeles importable

Real material, arrived at by accident: an article about animal-sound
onomatopoeia crossed the operator's desk while this repo was being worked on,
and three of its word-origin claims looked wrong. That is a better test set than
anything invented, because the answers were not known when it started — one
claim turned out true, two false, and one is *contested by its own sources*,
which is the case both packages exist for.

**The two questions are not the same question, and this is the whole point.**

    jeles asks    do >= MIN_INDEPENDENT_SOURCES distinct sources back this?
    nestor asks   did a named human check it, and can the signature prove it?

A claim can pass the first and fail the second. Every row here lands as a
**draft** no matter how many sources agree, because corroboration is evidence
and verification is a decision. Nothing in this file seals anything.

**The citations are real URLs from a real search**, pasted in rather than
fetched, so this runs offline and deterministically. `jeles._egress` exists so
that jeles' own network access is a deliberate act; a demo that quietly opened
sockets to reproduce a number would be working around somebody else's gate.

**What it found that neither rule catches on its own** is at the bottom, and it
is the reason this file is worth keeping: the search for one claim returned
*the article under test* as a top result, and a tweet quoting that article
verbatim. Two distinct registrable domains. jeles' independence rule counts
them as two independent sources, and they are one.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

os.environ.setdefault("NESTOR_SEAL_KEY", "demo-fixture-key-not-a-secret")

from nestor import cascade, memory, storage                  # noqa: E402
from nestor.sqlite_store import SqliteStore                  # noqa: E402

BOLD, DIM, GREEN, AMBER, RED, CYAN, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[0m")

DOMAIN, TARGET = "claim", "verdict"

#: The article the claims come from. Named so the self-citation check below has
#: something to compare against — see `the trap` at the end.
UNDER_TEST = "wordsmarts.com"

#: Each claim: what the article said, what the evidence says, and the URLs a
#: real search returned. `reached` is this script's reading, which is a draft.
CLAIMS = [
    {
        "id": "squeak",
        "article": "'Squeak' comes from the Middle Swedish word skväka.",
        "reached": "Overstated. The source says 'probably of imitative origin' "
                   "and cites Middle Swedish skväka as a comparison, not a parent.",
        "holds": False,
        "sources": [
            "https://www.etymonline.com/word/squeak",
            "https://www.oxfordlearnersdictionaries.com/definition/english/squeak_1",
            "https://www.dictionary.com/browse/squeak",
            "https://etymology.en-academic.com/33146/squeak",
        ],
    },
    {
        "id": "woof",
        "article": "'Woof' has been in use since Old English, first related to "
                   "weaving wefts of fabric; in the early 19th century it gained "
                   "a new purpose as a dog's bark.",
        "reached": "Two unrelated homonyms welded into one history. Fabric woof "
                   "is Old English owef (o- 'on' + wefan 'to weave'); the bark is "
                   "a separate imitative formation from 1839. Nothing 'gained a "
                   "new purpose' — a different word arrived.",
        "holds": False,
        "sources": [
            "https://www.etymonline.com/word/woof",
            "https://en.wiktionary.org/wiki/woof",
            "https://www.thefreedictionary.com/woof",
            "https://www.collinsdictionary.com/us/dictionary/english/woof",
            "https://www.encyclopedia.com/sports-and-everyday-life/fashion-and-clothing/textiles-and-weaving/woof",
        ],
    },
    {
        "id": "ribbit",
        "article": "The word 'ribbit' was coined by writers for the Smothers "
                   "Brothers Comedy Hour.",
        "reached": "Contradicted by the earliest attestation. Benjamin Zimmer "
                   "dates it to a 1965 Gilligan's Island episode (Mel Blanc, "
                   "'Ribbit the Frog'); the Smothers Brothers used it in 1967. "
                   "Two years later is not coining it.",
        "holds": False,
        "sources": [
            "https://en.wikipedia.org/wiki/Ribbit",
            "https://www.cheatsheet.com/news/gilligans-island-a-1965-episode-introduced-frog-sound-ribbit-to-the-english-language.html/",
            "https://en.wiktionary.org/wiki/ribbit",
            "https://nowiknow.com/why-frogs-ribbit/",
            # The two that make this the interesting row.
            "https://wordsmarts.com/animals-world/",
            "https://x.com/StephenBaldwin7/status/1818380587125645362",
        ],
    },
    {
        "id": "hollywood-frog",
        "article": "American frogs 'ribbit' because the recorded sound chosen in "
                   "Hollywood was the Pacific tree frog.",
        "reached": "Holds, as far as several independent accounts go. This is the "
                   "one claim on the page the evidence supports.",
        "holds": True,
        "sources": [
            "https://en.wikipedia.org/wiki/Ribbit",
            "https://nowiknow.com/why-frogs-ribbit/",
            "https://smartscience.blog/what-does-frog-say",
        ],
    },
]


def main() -> int:
    try:
        from jeles._independence import MIN_INDEPENDENT_SOURCES, registrable_domain
    except ImportError:
        print(f"{RED}jeles is not importable{OFF}")
        print(f"   {DIM}'I could not look' — this demo needs jeles' independence "
              f"rule, and will not invent one.{OFF}")
        return 1

    work = pathlib.Path(tempfile.mkdtemp(prefix="nestor-verification-"))
    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    store = SqliteStore(str(work / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    print(f"\n{BOLD}four claims, two rules{OFF}")
    print(f"{DIM}   jeles: corroborated at >= {MIN_INDEPENDENT_SOURCES} distinct "
          f"registrable domains.  nestor: sealed only by a human.{OFF}")

    trap = []
    for c in CLAIMS:
        domains = sorted({d for d in (registrable_domain(u) for u in c["sources"]) if d})
        corroborated = len(domains) >= MIN_INDEPENDENT_SOURCES
        row = memory.add_pair(
            c["article"], c["reached"], DOMAIN, TARGET, status="draft",
            origin=f"wordsmarts:{c['id']}", store=store,
            reason=(f"{len(domains)} distinct source(s): {', '.join(domains)}. "
                    f"jeles bar is {MIN_INDEPENDENT_SOURCES}. "
                    f"Reading, not a human's decision."))
        mark = GREEN if corroborated else AMBER
        verdict = "the article is wrong" if not c["holds"] else "the article holds"
        print(f"\n{BOLD}{c['id']}{OFF}  {mark}{len(domains)} source(s)"
              f"{OFF}  {CYAN}{row['status']}{OFF}  {DIM}{verdict}{OFF}")
        print(f"   {DIM}article {OFF}{c['article'][:96]}")
        print(f"   {DIM}found   {OFF}{c['reached'][:96]}")
        print(f"   {DIM}domains {OFF}{', '.join(domains)}")
        if UNDER_TEST in domains:
            trap.append(c["id"])

    sealed = sum(1 for r in store.memory_candidates(DOMAIN, TARGET)
                 if r["status"] == "sealed")
    print(f"\n{BOLD}what is in the store{OFF}")
    print(f"   {len(CLAIMS)} row(s), {AMBER}{sealed} sealed{OFF}")
    print(f"   {DIM}Three of these four are refutations of a published claim, and "
          f"every one of them is a{OFF}")
    print(f"   {DIM}draft. Being right is not the same as having been checked, "
          f"which is the only thing{OFF}")
    print(f"   {DIM}this package sells.{OFF}")

    if trap:
        print(f"\n{BOLD}{RED}the trap{OFF}  {DIM}found by running this, not by "
              f"designing it{OFF}")
        print(f"   The search for {', '.join(trap)} returned {BOLD}{UNDER_TEST}{OFF} "
              f"— the article under test —")
        print(f"   as a top result, next to a tweet quoting it nearly verbatim. "
              f"Those are two")
        print(f"   distinct registrable domains, so jeles' independence rule "
              f"counts them as two")
        print(f"   independent sources. They are one claim, twice.")
        print(f"\n   {DIM}jeles already excludes the search engine itself from "
              f"witnessing (_NON_WITNESS,{OFF}")
        print(f"   {DIM}21 domains) because an unfiltered count read DuckDuckGo "
              f"as a source about every{OFF}")
        print(f"   {DIM}claim. This is the same defect one step out: nothing "
              f"excludes the claim's OWN{OFF}")
        print(f"   {DIM}source, or anyone repeating it. A blocklist cannot hold "
              f"this — the domain to{OFF}")
        print(f"   {DIM}exclude is different for every claim, and is only known "
              f"once you know where the{OFF}")
        print(f"   {DIM}claim came from.{OFF}")
        print(f"\n   {DIM}Which is the argument for the seal rather than against "
              f"the count: no number of{OFF}")
        print(f"   {DIM}agreeing pages distinguishes four sources from one source "
          f"quoted four times.{OFF}")

    shutil.rmtree(work, ignore_errors=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
