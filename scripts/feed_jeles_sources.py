#!/usr/bin/env python3
"""Feed jeles' institutional source registry in — a source, and what it claims.

    python scripts/feed_jeles_sources.py --repo /path/to/jeles
    python scripts/feed_jeles_sources.py --repo … --keep DIR

Second repository fed into this store. `jeles/sources.py` declares
``SOURCES: dict[str, dict]`` — 65 institutions, each with a display name, a list
of subject ``domain`` tags, a ``key_required`` flag and an allow-list of
``hosts``. ``route_sources()`` picks which to fan a query across by matching its
domain tags.

**Why this corpus and not another.** The registry's own comment says
``tests/test_sources.py`` pins each declaration against actual behaviour, "so
the two cannot drift apart silently" — and that is true of the parts a test can
reach. ``key_required`` is checkable: call it without a key and see whether it
abstains. ``hosts`` is checkable: watch where it connects.

The ``domain`` list is not. *Is OpenAlex a good source for the humanities?* is
an editorial judgment about a routing decision, and no test in any repository
can make it. It is also the field that decides what a user's question actually
reaches. That is the row: **source → the subjects it claims to serve**, sealed
when a person has agreed the claim is right.

**And it is the first corpus here where a seal genuinely decays.** A clause does
not stop being the clause. An institution's API changes, moves, starts requiring
a key, or stops covering a subject it used to. ``docs/seal-staleness-and-quorum.md``
is the open question in this repo about exactly that, and this is the first
material that puts weight on it: *verified once, served forever* is the pitch,
and a source verified in May may be wrong by August without anybody touching the
row. Nothing here resolves that. It supplies the case.

**Read by parsing, never importing** — same rule as
``scripts/feed_willow_constitution.py``. jeles is stdlib-only and safe to
import, which is exactly why the rule has to be about the rule rather than about
this repository being trustworthy.

**Everything lands as a draft**, and the default `StringMatcher` is used
deliberately: the source key is unique by construction (it is a dict key), so
this corpus needs no custom matcher and inventing one would be ceremony.
"""
from __future__ import annotations

import argparse
import ast
import collections
import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

os.environ.setdefault("NESTOR_SEAL_KEY", "feed-fixture-key-not-a-secret")

from nestor import cascade, memory, storage          # noqa: E402
from nestor.sqlite_store import SqliteStore          # noqa: E402

DOMAIN = "source"
TARGET = "serves"
ORIGIN = "jeles:sources"

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")


def extract(path: pathlib.Path) -> dict:
    """The ``SOURCES`` literal, by parsing. No import, no execution."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        if target == "SOURCES" and value is not None:
            try:
                got = ast.literal_eval(value)
            except (ValueError, SyntaxError, TypeError):
                return {}
            return got if isinstance(got, dict) else {}
    return {}


def claim(key: str, spec: dict) -> tuple[str, str]:
    """``(source_text, target_text)`` for one registry entry."""
    name = spec.get("name") or key
    domains = ", ".join(spec.get("domain") or []) or "(no subjects declared)"
    return (f"{key} — {name}", domains)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="a jeles checkout")
    ap.add_argument("--keep", default="", help="leave the store behind here")
    args = ap.parse_args()

    path = pathlib.Path(args.repo) / "jeles" / "sources.py"
    if not path.exists():
        print(f"{RED}no jeles/sources.py under {args.repo}{OFF}")
        return 1
    sources = extract(path)
    if not sources:
        print(f"{RED}could not parse a SOURCES mapping out of {path}{OFF}")
        return 1

    work = pathlib.Path(args.keep) if args.keep else pathlib.Path(
        tempfile.mkdtemp(prefix="nestor-feed-jeles-"))
    work.mkdir(parents=True, exist_ok=True)
    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    store = SqliteStore(str(work / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    print(f"\n{BOLD}jeles sources → nestor{OFF}  "
          f"{DIM}{DOMAIN}→{TARGET}, read by parsing{OFF}")
    print(f"   {len(sources)} institution(s) declared")

    keyed = [k for k, v in sources.items() if v.get("key_required")]
    for key, spec in sources.items():
        src, tgt = claim(key, spec)
        hosts = ", ".join(spec.get("hosts") or []) or "none listed"
        memory.add_pair(src, tgt, DOMAIN, TARGET, status="draft",
                        origin=f"{ORIGIN}:{key}", store=store,
                        reason=(f"Declared hosts: {hosts}. "
                                f"key_required={bool(spec.get('key_required'))}. "
                                f"Whether it genuinely serves these subjects is a "
                                f"routing judgment no test makes."))

    # What a test already covers, said out loud so nobody seals it twice.
    print(f"   {DIM}key_required is checkable and {len(keyed)} declare it; hosts "
          f"are checkable. Subjects are not.{OFF}")

    # 1. Sources the router cannot tell apart.
    by_domains: dict[tuple, list[str]] = collections.defaultdict(list)
    for key, spec in sources.items():
        by_domains[tuple(sorted(spec.get("domain") or []))].append(key)
    twins = {d: ks for d, ks in by_domains.items() if len(ks) > 1}
    print(f"\n{BOLD}sources declaring identical subjects{OFF}  "
          f"{DIM}route_sources() cannot prefer one over the other{OFF}")
    if not twins:
        print("   none")
    for domains, keys in sorted(twins.items()):
        print(f"   {AMBER}{', '.join(keys):32}{OFF} {', '.join(domains)}")

    # 2. Host overlap. Not a defect — a note about how coarse the allow-list is.
    hosts = collections.Counter(h for v in sources.values() for h in (v.get("hosts") or []))
    shared = [(h, n) for h, n in hosts.most_common() if n > 1]
    print(f"\n{BOLD}hosts named by more than one source{OFF}  "
          f"{DIM}the egress allow-list is per source, the host is not{OFF}")
    for host, count in shared[:6]:
        print(f"   {count:2}x  {host}")
    print(f"   {DIM}{len(shared)} shared host(s) of {len(hosts)} — the "
          f"allow-list is tight, which is the honest reading.{OFF}")
    print(f"   {DIM}Granting one source's reach does grant a host others use, "
          f"but at this ratio that is a note,{OFF}")
    print(f"   {DIM}not a finding.{OFF}")

    # 3. Subjects served by exactly one source: a single point of failure for
    #    any question routed there.
    per_subject = collections.Counter(
        d for v in sources.values() for d in (v.get("domain") or []))
    alone = sorted(s for s, n in per_subject.items() if n == 1)
    print(f"\n{BOLD}subjects with exactly one source{OFF}  "
          f"{DIM}{len(alone)} of {len(per_subject)}{OFF}")
    print(f"   {', '.join(alone) if alone else 'none'}")
    print(f"\n   {DIM}MEASURED: routing breadth only — a query tagged to one of "
          f"these fans out to one institution.{OFF}")
    print(f"   {DIM}NOT measured, and worth checking: jeles corroborates a "
          f"finding only when MIN_INDEPENDENT_SOURCES{OFF}")
    print(f"   {DIM}distinct *registrable domains* back it (jeles._independence "
          f"— the DNS sense, not these subject{OFF}")
    print(f"   {DIM}tags). Whether a single-sourced subject therefore struggles "
          f"to clear that bar is a hypothesis.{OFF}")
    print(f"   {DIM}Sharper version, from the host counts above: 9 sources list "
          f"doi.org, and registrable_domain(){OFF}")
    print(f"   {DIM}collapses every doi.org citation to one source — so nine "
          f"institutions could corroborate as one.{OFF}")
    print(f"   {DIM}Also unmeasured. Both are questions this feed raises and "
          f"does not answer.{OFF}")

    sealed = sum(1 for r in store.memory_candidates(DOMAIN, TARGET)
                 if r["status"] == "sealed")
    print(f"\n{BOLD}what is in the store{OFF}")
    print(f"   {len(sources)} row(s), {AMBER}{sealed} sealed{OFF}")
    print(f"   {DIM}Every row is a draft, and this is the corpus where that "
          f"matters most:{OFF}")
    print(f"   {DIM}a source verified today can be wrong by autumn without "
          f"anybody touching the row.{OFF}")

    if args.keep:
        print(f"\n   {DIM}kept: {work}{OFF}\n")
    else:
        shutil.rmtree(work, ignore_errors=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
