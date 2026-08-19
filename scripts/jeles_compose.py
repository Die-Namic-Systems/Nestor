"""
Jeles composer: takes the same structured JSON research format used by
auto_compose.py and writes nuggets into jeles corpus.

Each research pair becomes a nugget:
  question     = source_text
  answer       = target_text
  sources      = evidence URLs for that pair
  kind         = "asserted" (machine-proposed, not human-verified)
  written_by   = "nestor-composer"
  tags         = [domain, origin_prefix]

This is the dual-write path: research goes into both Nestor (for seal
verification) and jeles (for source-count corroboration). The two stores
ask different questions — jeles asks "do enough independent sources back
this?", Nestor asks "did a named human check it?"
"""
import json, sys
from jeles import corpus


def compose_to_jeles(data, dry_run=False, origin_prefix="round6"):
    domain = data["domain"]
    origin = f"{origin_prefix}:{domain}"

    evidence_by_source = {}
    for ev in data.get("evidence", []):
        src = ev.get("pair_source", "")
        evidence_by_source.setdefault(src, []).append(ev.get("locator", ""))

    results = {"created": 0, "existing": 0, "errors": 0, "domain": domain}

    for p in data.get("pairs", []):
        question = p["source_text"]
        answer = p["target_text"]
        sources = [u for u in evidence_by_source.get(question, []) if u]
        tags = [domain, origin_prefix]
        if p.get("reason"):
            tags.append("has-reason")

        if dry_run:
            results["created"] += 1
            continue

        try:
            result = corpus.put_nugget(
                question=question,
                answer=answer,
                sources=sources,
                verified_by="research-agent",
                verification_kind="asserted",
                written_by="nestor-composer",
                tags=tags,
            )
            action = result.get("action", "unknown")
            if action == "created":
                results["created"] += 1
            else:
                results["existing"] += 1
        except Exception as ex:
            print(f"  WARN nugget skip: {ex}")
            results["errors"] += 1

    return results


def compose_all_to_jeles(json_files, dry_run=False, origin_prefix="round6"):
    all_results = []
    for path in json_files:
        with open(path) as f:
            data = json.load(f)
        r = compose_to_jeles(data, dry_run=dry_run, origin_prefix=origin_prefix)
        all_results.append(r)
        action = "Would create" if dry_run else "Created"
        existing = f", {r['existing']} existing" if r['existing'] else ""
        errors = f", {r['errors']} errors" if r['errors'] else ""
        print(f"  [{r['domain']}] {action}: {r['created']} nuggets{existing}{errors}")
    return all_results


def jeles_stats():
    all_nuggets = corpus.search_nuggets("", limit=10000)
    gaps = corpus.list_gaps(limit=10000)

    by_kind = {}
    by_tag = {}
    for n in all_nuggets:
        kind = n.get("verification_kind", "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        for tag in n.get("tags", []):
            by_tag[tag] = by_tag.get(tag, 0) + 1

    print(f"\n{'='*50}")
    print(f"JELES CORPUS TOTALS")
    print(f"{'='*50}")
    print(f"  Nuggets: {len(all_nuggets)}")
    for kind, count in sorted(by_kind.items()):
        print(f"    {kind}: {count}")
    print(f"  Gaps: {len(gaps)}")
    print(f"\n  Tags (top 15):")
    for tag, count in sorted(by_tag.items(), key=lambda x: -x[1])[:15]:
        print(f"    {tag}: {count}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python jeles_compose.py <file1.json> [file2.json ...] "
              "[--dry-run] [--origin-prefix=round6]")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    origin_prefix = "round6"
    for arg in sys.argv[1:]:
        if arg.startswith("--origin-prefix="):
            origin_prefix = arg.split("=", 1)[1]
    flags = {"--dry-run", "--origin-prefix"}
    files = [f for f in sys.argv[1:]
             if not any(f == flag or f.startswith(flag + "=") for flag in flags)]

    print(f"Composing {len(files)} domain(s) to jeles "
          f"[origin: {origin_prefix}:]{'  [DRY RUN]' if dry_run else ''}...")
    results = compose_all_to_jeles(files, dry_run=dry_run,
                                    origin_prefix=origin_prefix)

    totals = {"created": 0, "existing": 0, "errors": 0}
    for r in results:
        for k in totals:
            totals[k] += r[k]

    print(f"\nTotal: {totals['created']} created, "
          f"{totals['existing']} existing, {totals['errors']} errors")

    if not dry_run:
        jeles_stats()
