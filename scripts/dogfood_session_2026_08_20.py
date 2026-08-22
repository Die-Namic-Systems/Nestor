#!/usr/bin/env python3
"""Feed the 2026-08-20/21 willow-seat session's own decisions through Nestor.

    python scripts/dogfood_session_2026_08_20.py            # temp store
    python scripts/dogfood_session_2026_08_20.py --keep DIR
    python scripts/dogfood_session_2026_08_20.py --open      # print only what is OPEN

Same shape as `dogfood_session_decisions.py` (§6.14): (question, commitment,
why). Two additions this session earned:

* **`status`** — `closed`, `open`, or `corrected`. A session log that records
  only what was settled is the same defect as an audit trail that logs only
  agreement.
* **`corrected` entries carry what was believed FIRST.** Six claims in this
  session were stated confidently and were wrong. Recording only the corrected
  version would make the seat look better than it was and would lose the one
  finding worth keeping — which claims fail, and what they have in common.

**Nothing here seals.** Every pair is a draft with no verifier and no signature.
The machine may propose and may not confirm; the seal queue is a human at
`nestor.ui`. If a run ever produces a sealed row the covenant broke and the exit
code says so.
"""
from __future__ import annotations

import argparse
import sys

import dogfood_common

from nestor import memory

DOMAIN = "decision"

#: (question, commitment, why, status)
DECISIONS = [
    # ── infrastructure, closed ────────────────────────────────────────────
    ("Why was the Kart worker dead for nine days?",
     "willow-mcp-worker-fast.service was DISABLED, not broken. enable --now brought it up; "
     "round-trip task 474KFY4P completed returncode 0, sandbox bwrap.",
     "The stale heartbeat named PID 3438646, which is the exact PID in the unit's last "
     "journal entry. It died with the host and never came back because nothing asked it to. "
     "kart-worker.service is a decoy: it points at ~/SAFE/.venv and ~/sean-data-vault "
     "config that do not exist, and crash-looped 1,345 times before being stopped.",
     "closed"),

    ("Can the willow seat grant itself missing manifest permissions?",
     "No. The hook refuses write-capable groups (sudo invariant, FRANK 90e52ab7), and the "
     "manifest is PGP-signed — editing it invalidated the signature and denied EVERY call "
     "until root re-signed.",
     "Two independent controls, and the signature is the one with teeth. The hook was also "
     "a false positive on gap_read, a read-only group, because it text-matches the diff "
     "rather than comparing parsed group sets.",
     "closed"),

    ("Which artifact actually governs Kart's sandbox?",
     "$WILLOW_HOME/kart-sandbox.json, verified from a Kart task's own sandbox_manifest "
     "(config_source, config_is_vendored_default: false). NOT the willow-2.0 path every "
     "pre_approved[] enforced_by still names.",
     "The law names a file that is not on disk. Separately: 31 of 68 binds in the live "
     "config are dead pre-move paths that bind_try skips SILENTLY, which is why the charter "
     "repo is not mounted and reach-github-willow-constitution-rw is not in force.",
     "closed"),

    # ── the correction that matters most ──────────────────────────────────
    ("Why does `project sync` write the wrong WILLOW_STORE_ROOT?",
     "_willow_mcp_server_block() seeds its base env from store_root(), which reads the "
     "AMBIENT PROCESS ENVIRONMENT, before any entry override is considered. The operator "
     "shell exports the project-local path, so it is baked into every .mcp.json synced.",
     "FIRST DIAGNOSIS WAS WRONG and was recorded as fact: I said load_registry() overlays "
     "the seed on every load, so the stale seed path defeated _skip_store_override. Every "
     "clause of that is false — the overlay was REMOVED upstream, and the guard returns "
     "True when executed. The diagnosis was assembled from CLAUDE.md's description plus a "
     "plausible reading, and never run. FRANK 58b6912c -> corrected by 7d9d1faf.",
     "corrected"),

    # ── governance ────────────────────────────────────────────────────────
    ("Is the sixth die face Homestead · Sovereign or Homestead · Affairs?",
     "Affairs. Ratified by root in session 2026-08-20; scribed FRANK 25f83bce; applied to "
     "10 sites in FLEET_PLACEMENT_DRAFT.md. 'Sovereign' survives as the leg's CONTENT — "
     "the five-point test — not its name.",
     "Two ratified naming decisions disagreed (2026-08-03 vs 2026-08-10). The repo settled "
     "it: homestead-law/README.md opens 'Homestead · Affairs — module one.'",
     "closed"),

    ("What should happen to a SAFE app after it is promoted to an org?",
     "The playground copy STAYS, with a PROMOTED banner naming the canonical repo and the "
     "direction of drift. Operator's decision: the copies have repeatedly been useful "
     "source for the larger builds.",
     "Promotion copies rather than moves, so three apps existed twice with nothing saying "
     "which was authoritative — and the drift was not uniform. law-gazelle's playground "
     "copy is LARGER and more recent than the org repo; oakenscrolls-office's is stale. A "
     "blanket 'this copy is behind' would have been wrong in two cases of three.",
     "closed"),

    # ── the corpus ────────────────────────────────────────────────────────
    ("Does grading your own forecasts make you better at forecasting?",
     "No. It makes you HONEST, not right. Twelve rounds of tuning a confidence scalar moved "
     "overconfidence 0.238 -> 0.231 while destroying discrimination entirely. Giving the "
     "model real features moved it to 0.044 in one round; learning the mapping from graded "
     "outcomes reached Brier 0.129.",
     "Measured across 4,200 graded predictions in an isolated box. Calibration error "
     "decomposes into miscalibration (a scalar can fix) and resolution (it cannot). A "
     "self-correcting confidence knob only ever attacks the first, and squeezing the range "
     "destroys the second. For an agent: seeing more of the world and measuring which "
     "signals carry are the only levers.",
     "closed"),

    ("Where did the 35-rung corpus exercise's output go?",
     "Nowhere — data/ is gitignored. The FINDINGS survive in docs/agent-log.md and 34 "
     "merged corpus/NN-* branches; the ~10,300 rows did not. Rebuilt today: 9,977 rows "
     "from the 24 repositories still on this box (scripts/rebuild_corpus.py, 28cb0f8).",
     "sean-data-vault reproduced at EXACTLY 155 rows, matching §6.90's recorded total two "
     "weeks later against a 2.4 GB archive under an allowlist. The extractors are "
     "deterministic; the log's numbers hold; the durable artifact was the findings.",
     "closed"),

    # ── open ──────────────────────────────────────────────────────────────
    ("How should a Nestor pair carry a warrant that is not a local seal?",
     "UNDECIDED. IDEAS §1.10 proposes evidence: dict keyed by warrant kind. The prototype "
     "rides it in `origin` as the string 'warrant:predicted', which works and is ugly.",
     "jeles already has institutional (65 sources, verified_by empty, deliberately outside "
     "_KIND_RANK) and redential-cli has construction (zero-network proven by mocking "
     "node:http, merkle bundle, npm provenance). Attestation, citation and construction "
     "COMPOSE — so a warrant cannot be an enum with a max-wins rank. But provenance.py "
     "shows `origin` already carries structured provenance (repo@commit + extractor rev), "
     "so evidence: dict must be argued against that rather than assumed better.",
     "open"),

    ("Can nestor serve be wired into every project?",
     "BLOCKED. _STATIC_SERVERS in willow-mcp knows exactly two servers and raises "
     "'unknown server' on a third. Same one-line blocker as courtlistener.",
     "nestor serve is already MCP stdio with the right shape — ask and propose, cannot "
     "seal. The prerequisite is that NESTOR_DB be HONOURED: it is set in .willow/env and "
     "ignored — from /tmp, stats reported an empty corpus rather than the pinned one. Wire "
     "it unfixed and every repo grows its own empty corpus.",
     "open"),

    ("Should decision records move from the public nestor repo to the vault?",
     "AGREED IN PRINCIPLE, not done. DECISIONS_DIR is hardcoded at dogfood_common.py:26 "
     "with no env override, and ten files reference the path.",
     "114 records have been public since 2026-08-06 in a repo with one fork; operator's "
     "decision is not to rewrite history. Blocked on the same defect as NESTOR_DB — and it "
     "wants the STRONGER fix: fail loudly when the pin is missing, never fall back to cwd.",
     "open"),

    ("Are the five willow-2.0 envelopes still in force?",
     "YES, and they should not be. Five unexpired grants in active[] name "
     "rudi193-cmd/willow-2.0, a repo that no longer exists. Retiring them is verb 12, root "
     "only.",
     "Recorded, not acted on. Alongside: heimdallr is wired as safe-app-willow-grove's "
     "agent and has NO MANIFEST at all.",
     "open"),

    ("Should the willow-memory repos be transferred to the org?",
     "UNDECIDED — held on the operator's 'not all names'. Six repos are personally owned; "
     "only two have folder/repo name mismatches (Willow, safe-app-willow-grove).",
     "Held rather than guessed. safe-app-willow-grove keeps its name per §3; the only real "
     "question is whether Willow becomes willow, which is a rename plus a transfer on the "
     "repo the seat is standing in.",
     "open"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep")
    ap.add_argument("--open", dest="only_open", action="store_true")
    a = ap.parse_args()

    if a.only_open:
        for q, c, _w, st in DECISIONS:
            if st != "closed":
                print(f"  [{st:9}] {q}\n              -> {c[:96]}")
        return

    with dogfood_common.opened(a.keep) as (root, store):
        for q, c, why, st in DECISIONS:
            memory.add_pair(q, c, DOMAIN, DOMAIN, status="draft",
                            reason=f"[{st}] {why}",
                            origin="session:willow-seat-2026-08-20",
                            store=store)

        # the covenant, asserted rather than printed — a run that seals should
        # fail the build, not report a worse number
        stats = dogfood_common.assert_nothing_sealed(store)

        by: dict[str, int] = {}
        for *_x, st in DECISIONS:
            by[st] = by.get(st, 0) + 1
        print(f"  {len(DECISIONS)} decisions fed as drafts: "
              + ", ".join(f"{k}={v}" for k, v in sorted(by.items())))
        print(f"  store says: {stats}")
        print(f"  store: {root}")
        print("  0 sealed — the machine proposed and did not confirm.")


if __name__ == "__main__":
    main()
