#!/usr/bin/env python3
"""Import open willow-mcp SOIL gaps into Nestor as draft decision pairs.

Requires an editable willow-mcp on PYTHONPATH and WILLOW_STORE_ROOT pointing
at the SOIL tree that holds the ``gaps`` collection (charter seat:
``~/github/willow/.willow/store``).

Each gap becomes one draft pair (decision-memory shape):
  source_text = short human title (e.g. "Phase 1 gate · G3 — …")
  target_text = plain-language A/B/C commitment options (seal one line in UI)
  reason      = auditor finding + what you're deciding + file:// references
  origin      = willow:gap:<soil_id>:<dispatch_id>

Nothing is sealed. After sealing in ``nestor ui``, run ``apply_sealed_fleet_gaps.py``
(or tell willow) so SOIL gaps resolve and Hanuman dispatches fire.

Example::

  export WILLOW_STORE_ROOT=~/github/willow/.willow/store
  export WILLOW_HOME=~/github/.willow
  python scripts/import_willow_gaps.py --topic decommission/phase1-gate \\
    --keep ~/.willow/nestor-phase1-gaps --replace-drafts
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
import tempfile

from nestor import cascade, memory, portable, storage
from nestor.sqlite_store import SqliteStore

DOMAIN = "fleet-gap"

# Voice: fleet facts stay exact in SOIL + sealed lines; cards read like a human brief
# (same shape as the UTETY bulletin playground — warm, not compliance-ticket).

_PLAIN: dict[str, str] = {
    "G1 partial": (
        "When Loki opened a dispatch session, orientation did not show a project root, "
        "and PM SOIL collections came back as “not allowed.” That may be expected for a "
        "specialist scope — or it may be a bug. We need your call on whether to live with "
        "it for Phase 1 or send someone to fix orient."
    ),
    "G3": (
        "Phase 1 wanted someone to confirm the tasks table on willow_20, then watch a Kart "
        "job finish from the orchestrator seat. Loki could not run the job; willow hit "
        "unconfirmed_schema. Nothing is on fire — but the gate cannot honestly say “witnessed” "
        "until that path is green or you waive it on purpose."
    ),
    "G5": (
        "Specialists can write handoffs under handoffs/<agent>/, but session_enter still "
        "does not surface latest_handoff for them. Writes and reads are out of step — "
        "fine to document for Phase 1, or worth fixing before you sign the gate."
    ),
    "G6": (
        "The acceptance checklist mentions FRANK append/verify, but Loki’s manifest does not "
        "carry frank_* tools, and the charter seat did not have FRANK in play. Pick a policy: "
        "FRANK only on orchestrator seats, extend Loki’s manifest, or soften the gate wording."
    ),
    "G9 optional": (
        "After project sync, nobody has walked the cozy path: SessionEnd without a formal "
        "closeout, then SessionStart with stack_snapshot / [STACK] in the boot context. "
        "Optional for Phase 1 — but if you care about host continuity, witness or waive explicitly."
    ),
}

_DECISION: dict[str, str] = {
    "G1 partial": (
        "Are you comfortable that specialists see a thinner orient for Phase 1, or do you "
        "want Hanuman to make project root and SOIL scope behave before you move on?"
    ),
    "G3": (
        "Do you want to run schema confirm + Kart witness before calling Phase 1 done, "
        "waive with your eyes open, or hold the gate until it is witnessed?"
    ),
    "G5": (
        "Is it enough to note how agent handoffs work today, or should we fix the read path "
        "so latest_handoff catches up with what specialists write?"
    ),
    "G6": (
        "Where should FRANK live for gate audits — orchestrator seats only, on Loki too, "
        "or not in the specialist checklist at all?"
    ),
    "G9 optional": (
        "For the STACK snapshot story: witness it once, waive it for Phase 1, or schedule "
        "it before host cutover?"
    ),
}

_SUMMARY: dict[str, str] = {
    "G1 partial": "Can Loki find the campus on the orient map?",
    "G3": "Witness tasks schema + Kart, or say why not",
    "G5": "Handoffs write — but does anyone read them back?",
    "G6": "Where FRANK is allowed to speak",
    "G9 optional": "STACK snapshot after SessionEnd (optional)",
}

# (letter, card label, sealed line — sealed stays precise for the fleet record)
_COMMITMENT_OPTIONS: dict[str, list[tuple[str, str, str]]] = {
    "G1 partial": [
        (
            "A",
            "Live with it for Phase 1 — document the specialist orient gap; no build now.",
            "Phase 1 · G1 · Sealed: accept documented specialist orient limitation (no build).",
        ),
        (
            "B",
            "Send Hanuman — fix session_enter project root and Loki SOIL collection scope.",
            "Phase 1 · G1 · Sealed: assign Hanuman to fix specialist orient (root + SOIL scope).",
        ),
        (
            "C",
            "Not this week — note it in the gate record; revisit before Phase 2.",
            "Phase 1 · G1 · Sealed: defer orient fix to pre–Phase 2 cutover.",
        ),
    ],
    "G3": [
        (
            "A",
            "Run it — schema confirm on tasks, then witness Kart from the orchestrator seat.",
            "Phase 1 · G3 · Sealed: schema_confirm + Kart witness; close gap when green.",
        ),
        (
            "B",
            "Waive for Phase 1 — I accept unconfirmed_schema / unwatched Kart with attestation.",
            "Phase 1 · G3 · Sealed: waive schema/Kart witness for Phase 1 (operator attestation).",
        ),
        (
            "C",
            "Hold the gate — no Phase 1 sign-off until schema + Kart are witnessed.",
            "Phase 1 · G3 · Sealed: block Phase 1 sign-off until schema confirm + Kart complete.",
        ),
    ],
    "G5": [
        (
            "A",
            "Document it — known read-path gap; explain handoffs/<agent> for Phase 1.",
            "Phase 1 · G5 · Sealed: accept latest_handoff gap; document agent handoff path.",
        ),
        (
            "B",
            "Fix it — Hanuman implements read so latest_handoff works for specialists.",
            "Phase 1 · G5 · Sealed: assign Hanuman to fix latest_handoff for agent handoffs.",
        ),
        (
            "C",
            "Later — track handoff read-path as Phase 2 continuity.",
            "Phase 1 · G5 · Sealed: defer handoff read-path fix to Phase 2.",
        ),
    ],
    "G6": [
        (
            "A",
            "Orchestrator only — FRANK on willow/hanuman; Loki’s manifest stays as-is.",
            "Phase 1 · G6 · Sealed: FRANK on orchestrator seats only; loki manifest unchanged.",
        ),
        (
            "B",
            "Extend Loki — grant frank_read (or frank_*) for audit path on manifest.",
            "Phase 1 · G6 · Sealed: grant Loki FRANK tools on manifest for audits.",
        ),
        (
            "C",
            "Soften the checklist — drop FRANK from Phase 1 specialist acceptance text.",
            "Phase 1 · G6 · Sealed: narrow gate text (no FRANK requirement on loki).",
        ),
    ],
    "G9 optional": [
        (
            "A",
            "Walk it once — SessionEnd without closeout, then SessionStart shows stack_snapshot.",
            "Phase 1 · G9 · Sealed: witness STACK SessionEnd→SessionStart E2E after project sync.",
        ),
        (
            "B",
            "Waive — optional STACK E2E is out of scope for Phase 1.",
            "Phase 1 · G9 · Sealed: waive optional STACK E2E for Phase 1.",
        ),
        (
            "C",
            "Schedule — run STACK E2E before Phase 2 host cutover.",
            "Phase 1 · G9 · Sealed: defer STACK E2E to pre–Phase 2 cutover.",
        ),
    ],
}


def _commitment_block(gate_code: str, gap_id: str, dispatch_id: str) -> str:
    opts = _COMMITMENT_OPTIONS.get(gate_code)
    if not opts:
        fallback = [
            (
                "A",
                "Close gap — build or operator action complete.",
                "DECISION: Close gap — verified complete.",
            ),
            (
                "B",
                "Waive for Phase 1 with operator attestation.",
                "DECISION: Waive for Phase 1 with operator attestation.",
            ),
            (
                "C",
                "Defer — revisit before next gate.",
                "DECISION: Defer to next gate.",
            ),
        ]
        lines = [
            "Three paths — pick the one you can stand behind, then seal it:",
            "",
        ]
        for letter, label, _sealed in fallback:
            lines.append(f"{letter}) {label}")
        lines.append("")
        lines.append(f"Loki audit {dispatch_id} · willow gap {gap_id}")
        lines.append("---seal---")
        for letter, _label, sealed in fallback:
            lines.append(f"{letter}|{sealed}")
        lines.append("---end---")
        return "\n".join(lines)
    lines = [
        "Three paths — pick the one you can stand behind, then seal it:",
        "",
    ]
    for letter, label, _sealed in opts:
        lines.append(f"{letter}) {label}")
    lines.append("")
    lines.append(f"Loki audit {dispatch_id} · willow gap {gap_id}")
    lines.append("---seal---")
    for letter, _label, sealed in opts:
        lines.append(f"{letter}|{sealed}")
    lines.append("---end---")
    return "\n".join(lines)


def _load_gaps(topic: str | None, status: str | None) -> list[dict]:
    try:
        from willow_mcp.gaps import list_gaps
    except ImportError as exc:
        raise SystemExit(
            "willow_mcp not importable — pip install -e ~/github/willow-mcp "
            "and set WILLOW_STORE_ROOT to the SOIL store directory."
        ) from exc
    if not os.environ.get("WILLOW_STORE_ROOT", "").strip():
        raise SystemExit("WILLOW_STORE_ROOT must be set to the SOIL store directory.")
    return list_gaps(topic=topic or None, status=status or None)


def _parse_gate(question: str) -> tuple[str, str]:
    """Return (gate_code, dispatch_id) from a Loki gap question."""
    m = re.search(
        r"Phase 1 gate\s+(G\d+(?:\s+optional)?(?:\s+partial)?)\s*\(([A-F0-9]{8})\)",
        question,
        re.IGNORECASE,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip()), m.group(2).upper()
    dm = re.search(r"\(([A-F0-9]{8})\)", question)
    dispatch = dm.group(1).upper() if dm else "0E35F179"
    gm = re.search(r"\b(G\d+)\b", question)
    code = gm.group(1) if gm else "gap"
    return code, dispatch


def _file_uri(path: pathlib.Path) -> str:
    return path.expanduser().resolve().as_uri()


def _reference_block(
    *,
    question: str,
    gate_code: str,
    dispatch_id: str,
    gap_id: str,
    topic: str,
    asked_count: int,
    status: str,
) -> str:
    willow_home = pathlib.Path(
        os.environ.get("WILLOW_HOME", "~/github/.willow")
    ).expanduser()
    dispatch_dir = willow_home / "dispatch" / dispatch_id
    plan = pathlib.Path("~/github/willow/design/willow-2.0-decommission-plan.md").expanduser()
    plain = _PLAIN.get(
        gate_code,
        "A fleet gap is open; the technical wording from SOIL is below if you need it verbatim.",
    )
    decision = _DECISION.get(
        gate_code,
        "What do you want the fleet to do about this — close it, waive it for Phase 1, or defer?",
    )
    lines = [
        "## What happened (plain terms)",
        plain,
        "",
        "## The question we're asking you",
        decision,
        "",
        "## Loki's exact wording (for the record)",
        question.strip(),
        "",
        "## Background reading",
        _file_uri(dispatch_dir / "handoff.json"),
        _file_uri(dispatch_dir / "evidence-pack.md"),
        _file_uri(plan),
        "",
        "## For the record",
        f"gap_id={gap_id} · topic={topic} · status={status!r} · asked_count={asked_count}",
        f"dispatch_id={dispatch_id}",
    ]
    return "\n".join(lines)


def _pair_texts(g: dict) -> tuple[str, str, str, str]:
    gid = g.get("_id") or g.get("id") or "?"
    topic = g.get("topic") or ""
    question = (g.get("question") or "").strip()
    gate_code, dispatch_id = _parse_gate(question)
    summary = _SUMMARY.get(gate_code, question[:80] + ("…" if len(question) > 80 else ""))
    title = f"Phase 1 gate · {gate_code} — {summary}"
    commitment = _commitment_block(gate_code, gid, dispatch_id)
    reason = _reference_block(
        question=question,
        gate_code=gate_code,
        dispatch_id=dispatch_id,
        gap_id=gid,
        topic=topic,
        asked_count=int(g.get("asked_count") or 1),
        status=str(g.get("status") or "open"),
    )
    origin = f"willow:gap:{gid}:{dispatch_id}"
    return title, commitment, reason, origin


def _purge_fleet_gap_drafts(store: SqliteStore) -> int:
    """Script-only maintenance: remove draft fleet-gap rows before re-import."""
    with store._db() as conn:  # noqa: SLF001 — import tooling, not public API
        cur = conn.execute(
            "DELETE FROM tm_pairs WHERE status='draft' AND source_lang=? AND target_lang=?",
            (DOMAIN, DOMAIN),
        )
        return cur.rowcount


def feed(store, gaps: list[dict]) -> int:
    n = 0
    for g in gaps:
        if g.get("status") == "promoted":
            continue
        question = (g.get("question") or "").strip()
        if not question:
            continue
        title, commitment, reason, origin = _pair_texts(g)
        memory.add_pair(
            title,
            commitment,
            DOMAIN,
            DOMAIN,
            status="draft",
            reason=reason,
            origin=origin,
            store=store,
        )
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--topic", default="", help="filter gaps by topic (e.g. decommission/phase1-gate)")
    ap.add_argument("--status", default="open", help="gap status filter (default: open)")
    ap.add_argument(
        "--keep",
        metavar="DIR",
        help="persist SqliteStore + ledger here (default: temp dir, discarded)",
    )
    ap.add_argument(
        "--replace-drafts",
        action="store_true",
        help="delete existing draft fleet-gap pairs in --keep store before import",
    )
    ap.add_argument(
        "--frank",
        action="store_true",
        help="install willow_forwarder for this process (needs WILLOW_HOME / MCP env)",
    )
    ap.add_argument(
        "--export",
        metavar="PATH",
        help="write portable bundle JSON after import",
    )
    args = ap.parse_args()

    gaps = _load_gaps(args.topic or None, args.status or None)
    if not gaps:
        print("no gaps matched", file=sys.stderr)
        return 1

    if args.frank:
        from nestor import frank

        frank.set_forwarder(frank.willow_forwarder(project="willow"))

    tmp = None
    if args.keep:
        root = pathlib.Path(args.keep).expanduser()
        root.mkdir(parents=True, exist_ok=True)
    else:
        tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(tmp.name)

    try:
        cascade.set_ledger_path(root / "ledger.jsonl")
        store = SqliteStore(str(root / "nestor.db"))
        storage.set_store(store)
        store.memory_init()

        if args.replace_drafts:
            if not args.keep:
                raise SystemExit("--replace-drafts requires --keep (persistent store)")
            removed = _purge_fleet_gap_drafts(store)
            if removed:
                print(f"removed {removed} draft fleet-gap pair(s)")

        fed = feed(store, gaps)
        stats = memory.stats(store=store)
        print(f"imported {fed} gap(s) as draft pairs")
        print(f"store: {stats['total']} total, {stats['draft']} draft, {stats['sealed']} sealed")
        assert stats["sealed"] == 0

        if args.export:
            bundle = portable.export_bundle(store)
            pathlib.Path(args.export).expanduser().write_text(
                __import__("json").dumps(bundle, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"bundle written: {args.export}")

        if args.keep:
            print(f"nestor store + ledger: {root}")
            print(
                "open: nestor ui --db {db} --ledger {led} "
                "--source-lang fleet-gap --target-lang fleet-gap".format(
                    db=root / "nestor.db", led=root / "ledger.jsonl"
                )
            )
        return 0
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
