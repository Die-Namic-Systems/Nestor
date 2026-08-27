#!/usr/bin/env python3
"""Export sealed dogfood rows into ``docs/dogfood/seals/<pair_id>.json``.

Use after sealing decisions in a review copy or household store. The exports
are reviewable text that ``dogfood_store.py --rebuild`` folds into the
committed store when each signer's public key is in
``docs/dogfood/verifiers.json``.

    nestor --db review.db ui --verifier <you>
    python scripts/dogfood_seal_export.py --list --from-db review.db
    python scripts/dogfood_seal_export.py --decision 0218 --from-db review.db
    python scripts/dogfood_seal_export.py --all --from-db review.db
    nestor keys add <you> --type ed25519 --public <hex> \\
        --keyring docs/dogfood/verifiers.json
    python scripts/dogfood_store.py --rebuild
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import dogfood_common
import dogfood_store

from nestor.sqlite_store import SqliteStore

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEALS_DIR = ROOT / "docs" / "dogfood" / "seals"
DOMAIN = dogfood_store.DOMAIN


def _pair_ids_for_decision_ref(
    ref: str,
    decisions_dir: pathlib.Path | None = None,
) -> list[tuple[str, str]]:
    """``(pair_id, question)`` rows for ``0218`` or ``0218#1``."""
    stem, sep, rest = ref.partition("#")
    if not stem:
        raise ValueError("decision ref must look like 0218 or 0218#0")
    want_idx = int(rest) if sep else None
    if sep and not rest.isdigit():
        raise ValueError(f"decision index must be numeric, got {ref!r}")

    out: list[tuple[str, str]] = []
    for path in dogfood_common.decision_files(decisions_dir):
        file_stem = path.name.split("-")[0]
        if file_stem != stem:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        origin = f"pr:{data.get('pr', '?')}"
        date = str(data.get("date", ""))
        for i, row in enumerate(data["decisions"]):
            if want_idx is not None and i != want_idx:
                continue
            decision = dogfood_common.Decision(
                file=file_stem,
                question=row["question"],
                commitment=row["commitment"],
                why=row["why"],
                origin=origin,
                date=date,
            )
            out.append((dogfood_store._row_id(decision), row["question"]))
    return out


def _decision_rows(store) -> list[dict]:
    return [
        row for row in store.memory_list(limit=100_000)
        if row.get("source_lang") == DOMAIN and row.get("target_lang") == DOMAIN
        and not row.get("superseded_by")
    ]


def _export_row(row: dict, out_dir: pathlib.Path) -> pathlib.Path:
    if row.get("status") != "sealed":
        raise ValueError(f"row {row['id']!r} is {row.get('status')!r}, not sealed")
    if not row.get("seal_sig"):
        raise ValueError(f"row {row['id']!r} has no seal_sig")

    payload = {
        "pair_id": row["id"],
        "verifier": row.get("verifier", ""),
        "sealed_at": row.get("created_at", ""),
        "seal_sig": row["seal_sig"],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{row['id']}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return out


def _print_list(rows: list[dict]) -> None:
    if not rows:
        print("no decision-domain rows")
        return
    for row in sorted(rows, key=lambda r: (r.get("status") != "sealed", r["id"])):
        question = (row.get("source_text") or "").replace("\n", " ")
        if len(question) > 72:
            question = question[:69] + "..."
        print(f"{row['id']}  {row.get('status', '?'):7}  "
              f"{row.get('verifier') or '-':12}  {question}")


def _rows_for_export(store, args) -> list[dict]:
    if args.all:
        rows = [r for r in _decision_rows(store) if r.get("status") == "sealed"]
        if not rows:
            raise ValueError("no sealed decision rows to export")
        return rows

    if args.pair_id:
        row = store.memory_get(args.pair_id)
        if row is None:
            raise ValueError(f"no row with id {args.pair_id!r}")
        return [row]

    if args.question:
        matches = [
            r for r in _decision_rows(store)
            if args.question.casefold() in (r.get("source_text") or "").casefold()
        ]
        if not matches:
            raise ValueError(f"no row matches question {args.question!r}")
        if len(matches) > 1:
            ids = ", ".join(r["id"] for r in matches)
            raise ValueError(
                f"question {args.question!r} matches {len(matches)} rows: {ids}")
        return matches

    if args.decision:
        refs = _pair_ids_for_decision_ref(args.decision, args.decisions_dir)
        if not refs:
            raise ValueError(f"no decision file matches {args.decision!r}")
        rows = []
        for pair_id, _question in refs:
            row = store.memory_get(pair_id)
            if row is None:
                raise ValueError(
                    f"decision {args.decision!r} maps to {pair_id!r}, "
                    f"which is not in the store — rebuild or re-copy review.db?")
            rows.append(row)
        return rows

    raise ValueError("pass one of --pair-id, --decision, --question, or --all")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-db", type=pathlib.Path,
                    help="store that holds the sealed row(s)")
    ap.add_argument("--out-dir", type=pathlib.Path, default=SEALS_DIR,
                    help=f"destination directory (default: {SEALS_DIR.relative_to(ROOT)})")
    ap.add_argument("--decisions-dir", type=pathlib.Path,
                    default=dogfood_store.DECISIONS_DIR,
                    help="decision corpus for --decision lookup "
                         f"(default: {dogfood_store.DECISIONS_DIR.relative_to(ROOT)})")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true",
                      help="print decision rows and their pair ids")
    mode.add_argument("--pair-id", help="export one row by id")
    mode.add_argument("--decision", metavar="STEM[#N]",
                      help="export row(s) for a decision file, e.g. 0218 or 0218#0")
    mode.add_argument("--question", help="export the row whose question contains this text")
    mode.add_argument("--all", action="store_true",
                      help="export every sealed decision-domain row")
    args = ap.parse_args()

    if not args.from_db:
        ap.error("--from-db is required")

    db = args.from_db.expanduser().resolve()
    if not db.is_file():
        print(f"! database not found: {db}", file=sys.stderr)
        return 1

    store = SqliteStore(str(db))
    try:
        store.memory_init()
        if args.list:
            _print_list(_decision_rows(store))
            return 0

        if not any((args.pair_id, args.decision, args.question, args.all)):
            ap.error("pass one of --list, --pair-id, --decision, --question, or --all")

        rows = _rows_for_export(store, args)
        written: list[pathlib.Path] = []
        for row in rows:
            written.append(_export_row(row, args.out_dir))
    except ValueError as exc:
        print(f"! {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()

    for path in written:
        try:
            label = path.relative_to(ROOT)
        except ValueError:
            label = path
        print(f"wrote {label}")
    print("next: ensure each verifier's ed25519 public key is in "
          "docs/dogfood/verifiers.json, then run "
          "python scripts/dogfood_store.py --rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
