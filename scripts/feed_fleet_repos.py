#!/usr/bin/env python3
"""Feed a box's repo survey in — a repo, and what it does.

    python scripts/feed_fleet_repos.py --root ~/github/willow-memory
    python scripts/feed_fleet_repos.py --root /home/user --db data/nestor.db
    python scripts/feed_fleet_repos.py --root … --keep DIR

Rows are ``repo name -> one-line brief``, every one a **draft**.

**Why this corpus is unlike the others.** ``feed_willow_constitution.py`` and
``feed_jeles_sources.py`` read a declaration out of a file: the clause or the
registry entry exists in the tree, and parsing it is the whole job. There is no
file anywhere that says what a repository *does*. A brief is a reading of a
README by somebody, and here that somebody was a small model doing a
deliberately shallow pass — README plus tree shape plus a stack marker.

So the survey is a literal below rather than something extracted, and every row
carries the note that produced it: what was actually looked at, and whether the
README's claim matched the tree. That note is the row's whole value. Sealing one
means a person agreed the brief is right, which is a judgment no test in any
repository makes — the same shape as ``feed_jeles_sources.py``'s subjects field,
and the reason both corpora belong here rather than in a config file.

**Presence is derived, never asserted.** A row is written only for a repo this
script can see on disk. Repos in the survey but absent are reported; repos on
disk the survey never covered are reported *louder*, because that failure has
already happened once — the pass that produced this literal dropped a repo
silently, and the dropped one turned out to belong to a different GitHub org
than everybody assumed.

**A brief goes stale in a way a clause does not.** A constitution clause is
still the clause a year later. A repository acquires a source tree, gets
archived, or changes what it is for, and the row keeps serving the old answer
under somebody's name. This is the second corpus here to put weight on
``docs/seal-staleness-and-quorum.md``; it does not resolve it either.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from nestor import cascade, memory, storage          # noqa: E402
from nestor.sqlite_store import SqliteStore          # noqa: E402

DOMAIN = "repo"
TARGET = "brief"
ORIGIN = "fleet:repo-survey"

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

#: ``name -> (brief, stack, verification note)``. Surveyed 2026-08-12 by three
#: parallel haiku subagents over README + tree + stack marker, with two rows
#: corrected by hand afterwards (``.github`` and ``safe-app-store``, both of
#: which say so in their own note).
SURVEY: dict[str, tuple[str, str, str]] = {
    ".github": (
        "Org profile page for The Almanac — public-data catalogs mapping where authoritative "
        "datasets live and monitoring whether they stay reachable.",
        "docs",
        "CORRECTED BY HAND: the survey pass omitted this repo entirely. `git remote -v` reads "
        "almanac-data/.github, NOT the personal org's, and profile/README.md is the Almanac org "
        "page. Anyone editing this expecting a personal org profile is in the wrong clone."),
    "DispatchesFromReality": (
        "Portfolio and systems writing — case studies, essays, classroom materials and research "
        "evidence across education and governance.",
        "docs",
        "README + tree; docs/research/professional/lessons present — matches."),
    "Forge": (
        "Model-side harness for building SAFE-native apps: decision checkpoints and measurement "
        "instruments that refuse confident wrong answers. Works without live models.",
        "Python",
        "README + tree; forge/ source dir with tests — matches."),
    "Jeles": (
        "Verified-corpus organ — human-verified question/answer pairs with citations, serving as a "
        "lookup layer in front of live search. Also ships a standalone MCP server.",
        "Python",
        "README + tree; jeles/ with tests and tools — matches. Installed into Nestor's venv on "
        "2026-08-12, which un-skipped its 8 gated tests (border, bridge, verification, audits)."),
    "Nestor": (
        "The human-verification mechanic: sealed/draft/pending over a verified-match memory, with "
        "signed seals and a hash-chained ledger. Zero runtime dependencies.",
        "Python",
        "README + tree + a full suite run on 2026-08-12: 972 passed, lint and bandit clean — "
        "matches. This is the repo the store itself lives in."),
    "UTETY": (
        "On-device classroom pedagogy and trust layer — BKT mastery tracking and sourced practice "
        "items, with student data kept on-device.",
        "Python",
        "README + tree; utety/ with core/content/web split — matches."),
    "Willow": (
        "The fleet charter seat: constitution, decisions, authority envelopes and portfolio state. "
        "The code lives in the willow-mcp sibling.",
        "docs/governance",
        "AGENTS.md + CLAUDE.md + tree; governance/ present and no source tree — governance-only, "
        "as claimed. Its governance/compliance/cases feed Nestor's constitution audit."),
    "corpus-lens": (
        "Local-first process analyzer that grades your own session logs against a rubric — never "
        "another person's.",
        "Python",
        "README + tree; corpuslens/ with examples and tests — matches."),
    "cortex": (
        "Model-agnostic workflow orchestrator for coding agents — deterministic JavaScript control "
        "flow (agent/parallel/pipeline/phase) that delegates judgment to headless CLIs (Claude "
        "Code, Codex, Cursor).",
        "TypeScript / Node 22.18+ (zero deps)",
        "README + tree; package.json declares no dependencies and Node >=22.18, 16 .ts sources "
        "under src/ split into cli/runtime/adapters, a full node --test suite under test/, one "
        "example workflow — matches. Fork of upstream added 2026-08-25."),
    "homestead": (
        "Shared record, deadline and evidence core for the Homestead face — sealed logs with "
        "integrity verification and authorization gates.",
        "Python",
        "README + tree; homestead/ with tests and tools — matches."),
    "homestead-law": (
        "Embedded SQLite desktop module for legal case management, with re-identification checks "
        "and deadline tracking.",
        "Python",
        "README + tree + pyproject entry points — matches."),
    "homestead-ledger": (
        "Embedded SQLite desktop module for household financial record-keeping and categorization.",
        "Python",
        "README + tree + pyproject bindings — matches."),
    "kartikeya": (
        "Host-agnostic task queue and sandboxed worker engine, extracted from the Willow fleet and "
        "published standalone.",
        "Python",
        "README + tree; src/ layout with a full test suite. The PyPI claim was read from the "
        "README, not verified against the index."),
    "oakenscrolls-office": (
        "Local-first calibration ledger for personal predictions and confidence tracking.",
        "Python",
        "README + tree; pyproject declares TUI and web entry points — matches."),
    "openclaw-sap-gate": (
        "Python reference implementation of the SAP/1.0 MCP authorization protocol.",
        "Python",
        "README + tree; pyproject declares the sap-gate command — matches."),
    "quick-stupids": (
        "Cloud-only playground. Nothing here is canonical and nothing is a dependency; work that "
        "survives is re-landed in a compliant repo.",
        "docs",
        "README + tree; a PRIOR_ART.md survey with no active source — matches its own claim to be "
        "empty of code."),
    "quiet-corner": (
        "Local-first browser app for K-12 teachers documenting observations across expressive "
        "pathways.",
        "HTML/JS + Python server",
        "README + tree; .html/.js/.css files plus serve.sh — matches."),
    "safe-app-store": (
        "Provision-house for SAFE apps across two tiers — a shared playground under apps/, and "
        "promotion out into standing repos of their own.",
        "Python + TypeScript",
        "README + tree + catalog. NUMBERS DIFFER ON PURPOSE: catalog.json holds 41 entries while "
        "apps/ holds 38 directories. Both are correct — the catalog tracks both tiers and promoted "
        "apps have left apps/ for their own repos. Do not quote them interchangeably."),
    "safe-app-willow-grove": (
        "The unified human+agent surface for Willow — channels, agent presence, routing decisions "
        "and task queue in one dashboard. Portless by rule.",
        "Python (Textual + Postgres)",
        "README + tree; grove_db and grove modules with requirements.txt and no pyproject — "
        "matches."),
    "terpsi-music": (
        "Music-program management holding minors' education records — rosters, guardianship, "
        "medical forms, schedules, fees. Design phase: no application code yet.",
        "Python",
        "README + tree; design docs plus personas.py and voice.py, no runnable app — matches its "
        "own claim to be design-only."),
    "willow-bot": (
        "FastAPI webhook receiver for a GitHub App, taking webhooks through an ingress tunnel.",
        "Python (FastAPI)",
        "INSTALL.md + tree; bot.py and github_app.py with requirements.txt — matches. The README "
        "was uninformative, so the claim rests on INSTALL.md."),
    "willow-compose": (
        "Queryable memory corpus over the Willow constellation — code, human story and "
        "collaboration in Postgres with embeddings and MinHash dedup. Not a running service.",
        "Python (Postgres + embeddings)",
        "README + tree; engine/ pipeline scripts (extract_pieces, embed_pieces) — matches."),
    "willow-config": (
        "The canonical ~/.willow home — fleet contract, environment config, session continuity and "
        "handoff documents.",
        "config/docs",
        "README + tree; willow.md, env, settings.global.json and handoffs/ — matches."),
    "willow-data-vault": (
        "Blueprint for the persistent sovereign data box — schemas and bootstrap scripts only, "
        "never the data itself.",
        "SQL/shell/docs",
        "README + tree; bootstrap/ and schema/ with no data — matches."),
    "willow-gate": (
        "Check-in/check-out gate for agents — symmetric validation, a five-rung trust ladder, a "
        "PGP-encrypted ledger and hard stops.",
        "Python",
        "README + pyproject + tree; src/ and tests/. Installed into Nestor's venv on 2026-08-12, "
        "which un-skipped nestor.cloud_seal's test — the seam runs, not just the README."),
    "willow-mcp": (
        "Agent-neutral MCP server with persistent memory and task execution over three backends — "
        "SOIL key/value, a Postgres knowledge graph, and the Kart task queue.",
        "Python (MCP + Postgres)",
        "README + pyproject + tree; src/ present. Needs Postgres to run, so it was NOT stood up "
        "on 2026-08-12 — Nestor's FRANK mirror was proved with an injected forwarder instead."),
}


def is_checkout(path: pathlib.Path) -> bool:
    """A clone, by the only marker that does not require reading the repo."""
    return (path / ".git").is_dir()


def repo_name(path: pathlib.Path) -> str:
    """What the repository is called, which is not what the directory is called.

    ``SURVEY`` is keyed by the GitHub repository name, and presence used to be
    tested with ``is_checkout(root / name)`` — a directory-name match. A clone
    directory is whatever the person cloning it typed, and on this box that is
    routinely not the repository name: ``willow`` holds ``Willow``, ``nestor``
    holds ``Nestor``, ``dotgithub`` holds ``.github``, and ``.willow`` holds
    ``willow-config``. Six repositories across the fleet were therefore surveyed
    as absent AND reported under "on disk, not in the survey" — the branch whose
    stated job is catching a repo the survey dropped. It fired correctly and
    named the wrong cause: the survey had them, under the name they actually go
    by.

    So identity is the remote. Falls back to the directory name when there is no
    ``origin`` — a local-only clone has no better answer, and guessing a remote
    it does not have would be worse than using what is there.
    """
    try:
        url = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):        # git absent or wedged
        return path.name
    if not url:
        return path.name
    return url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True, help="directory holding the clones")
    ap.add_argument("--db", default="", help="write into this existing store instead of a temp one")
    ap.add_argument("--keep", default="", help="leave the temp store behind here")
    args = ap.parse_args()

    root = pathlib.Path(args.root).expanduser()
    if not root.is_dir():
        print(f"{RED}no directory at {root}{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting a "
              f"box with zero repositories in it. Those are different facts.{OFF}")
        return 1

    if args.db:
        store = SqliteStore(args.db)
    else:
        work = pathlib.Path(args.keep) if args.keep else pathlib.Path(
            tempfile.mkdtemp(prefix="nestor-feed-repos-"))
        work.mkdir(parents=True, exist_ok=True)
        cascade.set_ledger_path(str(work / "ledger.jsonl"))
        store = SqliteStore(str(work / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    print(f"\n{BOLD}repo survey → nestor{OFF}  "
          f"{DIM}{DOMAIN}→{TARGET}, presence read from disk{OFF}")

    # Read the disk once, keyed by what each clone actually is. A duplicate
    # remote under one root would otherwise be decided by iteration order, so
    # the first is kept and the rest fall through to `extra`, where a human sees
    # them rather than one silently shadowing the other.
    on_disk: dict[str, pathlib.Path] = {}
    duplicates: list[str] = []
    for child in sorted(root.iterdir()):
        if not is_checkout(child):
            continue
        name = repo_name(child)
        if name in on_disk:
            duplicates.append(f"{child.name} (also {name})")
            continue
        on_disk[name] = child

    written, absent = 0, []
    for name, (brief, stack, check) in sorted(SURVEY.items()):
        if name not in on_disk:
            absent.append(name)
            continue
        memory.add_pair(name, brief, DOMAIN, TARGET, status="draft",
                        origin=f"{ORIGIN}:{name}", store=store,
                        reason=f"stack: {stack}\nverification: {check}")
        written += 1

    # A clone the survey never covered. Reported louder than an absent one:
    # the pass that produced SURVEY dropped a repo silently, and a survey that
    # only reports what it remembered to look at cannot tell you what it missed.
    extra = sorted(name for name in on_disk if name not in SURVEY) + duplicates

    print(f"   {written} repo(s) written, {GREEN}all drafts{OFF}")
    print(f"   {DIM}each row carries its verification note as `reason`; nothing "
          f"is served until a person seals it{OFF}")

    if absent:
        print(f"\n{AMBER}in the survey, not on disk{OFF} ({len(absent)})")
        for name in absent:
            print(f"   {name}")
        print(f"   {DIM}No row written. A brief for a repo that is not here "
              f"would be a claim about nothing.{OFF}")
    if extra:
        print(f"\n{RED}on disk, not in the survey{OFF} ({len(extra)})")
        for name in extra:
            print(f"   {name}")
        print(f"   {DIM}The survey is incomplete and says so. This is the "
              f"branch that catches a silently dropped repo.{OFF}")
    if not absent and not extra:
        print(f"\n   {GREEN}survey and disk agree{OFF} — {written} on both "
              f"sides, none missing either way")

    if not args.db:
        print(f"\n   {DIM}store: {store.path if hasattr(store, 'path') else work}{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
