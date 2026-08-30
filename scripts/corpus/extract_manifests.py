#!/usr/bin/env python3
"""App manifests — what each app declares about itself, in its own words.

    python scripts/corpus/extract_manifests.py --repo /path --name safe-manifests \
        --out data/corpus/safe-manifests.db

43 ``safe-app-manifest.json`` and 11 ``mcp_apps/*/manifest.json`` sit on this
box declaring permissions, network posture, privacy tier and data streams —
machine-readable, already curated, and unreadable by the corpus.

The valuable half is ``notes``. INVARIANTS §6 says *the manifest describes code,
not aspirations*, so a note is a claim its author was willing to be held to:
playgate's ``no_score`` explains why a composite score is refused; its
``subprocess`` names ``adb install`` as the one real capability. That is design
rationale sitting in a field nothing reads.

Permissions and network are emitted as their own rows rather than folded into
the description, because "what it may do" is the question anyone actually brings
to a manifest, and burying it inside prose makes it unqueryable — the same
mistake as a percentage without a denominator.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                      # noqa: E402
import provenance                                                  # noqa: E402

from nestor.sqlite_store import SqliteStore                        # noqa: E402

PATTERNS = ("**/safe-app-manifest.json", "**/mcp_apps/*/manifest.json",
            "**/manifest.json")


def rows_for(path: pathlib.Path) -> list:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []
    if not isinstance(doc, dict):
        return []
    app = str(doc.get("app_id") or doc.get("name") or path.parent.name).strip()
    if not app:
        return []
    out = []

    def add(suffix, value, reason, anchor):
        v = str(value).strip()
        if v and v not in ("[]", "{}", "None"):
            out.append((f"{app} · {suffix}" if suffix else app, v, reason, path, anchor))

    add("", doc.get("description", ""), f"version {doc.get('version', 'unstated')}", "description")
    perms = doc.get("permissions")
    if isinstance(perms, list):
        add("permissions", ", ".join(map(str, perms)) or "none declared",
            "declared in the manifest; the gate enforces this list, not the prose", "permissions")
    for key, why in (("network", "network posture as declared"),
                     ("privacy_tier", "privacy tier"),
                     ("agent_type", "agent type"),
                     ("store_scope", "store scope"),
                     ("local_processing", "share of processing that stays local")):
        val = doc.get(key)
        if isinstance(val, list):
            val = ", ".join(map(str, val))
        add(key, val if val is not None else "", why, key)

    for stream in doc.get("data_streams") or []:
        if isinstance(stream, dict) and stream.get("id"):
            add(f"data_stream {stream['id']}", stream.get("purpose", ""),
                f"retention: {stream.get('retention', 'unstated')}", str(stream["id"]))

    notes = doc.get("notes")
    if isinstance(notes, dict):
        for key, text in notes.items():
            add(f"note {key}", text, "a manifest note — INVARIANTS §6: describes code, not aspirations", key)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    if not common.require_checkout(root):
        return 1
    seen, rows, files = set(), [], 0
    for pat in PATTERNS:
        for path in sorted(root.glob(pat)):
            if path in seen or ".venv" in path.parts or "node_modules" in path.parts:
                continue
            seen.add(path)
            got = rows_for(path)
            if got:
                files += 1
                rows.extend(got)
    print(f"  {files} manifest(s), {len(rows)} row(s)")
    if not rows:
        print("error: no manifest rows — refusing to write an empty store", file=sys.stderr)
        return 1

    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    origin = provenance.Origin(args.name, root, __file__)
    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, [("manifest", rows, "app", "declaration")], origin)
    finally:
        store.close()
    print(f"  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
