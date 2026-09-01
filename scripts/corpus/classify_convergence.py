#!/usr/bin/env python3
"""Classify the corpus's `convergence` edges — §6.126's measurement, reproducible.

    python scripts/corpus/classify_convergence.py

Reads `corpus_edges` where kind='convergence' and bins each edge by the reason it
is NOT independent arrival. Written because the MCP verb caps at 50 rows and a
15-row sample put one class at 47% that the full 389 put at 1.8%.

The LANE map is **authored, not inferred** — the same standard
`link_claims.tombstone_families` holds itself to. It records which corpus
"repositories" are extraction lanes over one project (nestor / decisions /
gh-Die-Namic-Systems are three views of one repo), which is a relation
`families` cannot express: not descent, not sibling-hood.

Findings are proposals. Every edge this bins still carries verifier='' upstream;
nothing here seals anything.
"""
import sqlite3, re, json, collections
c = sqlite3.connect(str(__import__("pathlib").Path.home() / ".nestor/keep/nestor.db")); c.row_factory = sqlite3.Row

# AUTHORED, not guessed: which corpus "repositories" are extraction lanes over one project.
LANE = {}
def lane(project, *repos):
    for r in repos: LANE[r] = project
lane("nestor",      "nestor", "decisions", "gh-Die-Namic-Systems")
lane("willow",      "willow-mcp", "gh-willow-memory", "willow-gate", "willows-grove", "willow-grove",
                    "kartikeya", "kartikeya-work", "corpus-lens", "willow-data-vault",
                    "willow-2.0", "willow-1.9", "willow-canonical", "willow", "willow-bot",
                    "willow-compose", "willow-nest", "willow-seed", "willow-tech-manual")
lane("hornbook",    "Jeles", "UTETY", "oakenscrolls-office", "gh-hornbook-knowledge", "jeles-remote")
lane("homestead",   "homestead", "homestead-law", "homestead-ledger", "homestead-health",
                    "gh-homestead-affairs", "awesome-sovereign-software")
lane("almanac",     "gh-almanac-data", *[f"{d}-almanac" for d in
     "agriculture civic climate economy education energy environment health justice science transportation".split()],
     "almanac-template")
lane("forge",       "Forge", "gh-forge-play")
lane("terpsi",      "terpsi-music", "gh-terpsi-programs")
lane("safe-store",  "safe-app-store-code", "safe-app-store-public", "app-manifests", "safe-design", "safe-app-common-package")

COPY_RE    = re.compile(r"vendor(ed|ing)\b|copied byte-for-byte|byte-for-byte|a vendored", re.I)
LINEAGE_RE = re.compile(r"\bported from\b|\boriginally\b|\bsuccessor\b|\bextracted (from|out of)\b|\bmigrated from\b|\bderived from\b", re.I)
TEMPLATE_RE= re.compile(r"pull_request_template|community health file|org default|SUPPORT\.md|CODE_OF_CONDUCT|issue template|release-please|changelog_dedup|dependabot", re.I)
REGISTRY_F = re.compile(r"human_loop|friction_floor|model_egress|mem_ratify|subject_consent|nest_pipeline", re.I)
REGISTRY_P = {("Forge","willow-mcp"),("willow-mcp","willow-gate"),("willow-mcp","UTETY")}

rows = c.execute("""SELECT e.id, a.repository ra,a.source_text sa,a.target_text ta,a.origin oa,a.source_lang la,
                           b.repository rb,b.source_text sb,b.target_text tb,b.origin ob,b.source_lang lb
                    FROM corpus_edges e JOIN corpus_claims a ON a.id=e.src_id
                    JOIN corpus_claims b ON b.id=e.dst_id WHERE e.kind='convergence'""").fetchall()

def base(o):
    m = re.search(r":([^#]*)#", o or ""); return m.group(1).rsplit("/",1)[-1] if m else ""

tal, ex = collections.Counter(), collections.defaultdict(list)
for r in rows:
    both = " ".join(str(r[k] or "") for k in ("sa","ta","oa","sb","tb","ob"))
    pa, pb = LANE.get(r["ra"]), LANE.get(r["rb"])
    pair = tuple(sorted((r["ra"], r["rb"])))
    if pa and pa == pb:
        k = "same project, different lane"          # one project talking to itself
    elif pair in {tuple(sorted(p)) for p in REGISTRY_P} and REGISTRY_F.search(both):
        k = "declared in a vendor registry"
    elif TEMPLATE_RE.search(both):
        k = "template / org-default propagation"
    elif COPY_RE.search(both):
        k = "docstring says: vendored/copied"
    elif LINEAGE_RE.search(both):
        k = "docstring says: ported/originally"
    elif base(r["oa"]) and base(r["oa"]) == base(r["ob"]):
        k = "same filename, different path, no prose"
    else:
        k = "UNCLASSIFIED"
    tal[k] += 1
    if len(ex[k]) < 3: ex[k].append(f'{r["ra"]}/{r["la"]}:{r["sa"][:52]}  <->  {r["rb"]}/{r["lb"]}:{r["sb"][:52]}')

n = len(rows); print(f"convergence rows: {n}\n")
for k, v in tal.most_common(): print(f"  {k:36s} {v:4d}  {100*v/n:5.1f}%")
print("\n--- examples ---")
for k in tal:
    print(f"\n[{k}]")
    for e in ex[k]: print("   ", e)
