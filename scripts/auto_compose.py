"""
Auto-composer: takes structured JSON from research agents and inserts into Nestor store.
Handles pair creation, intra-domain edges, evidence, and cross-domain edge detection.
"""
import json, uuid, sys, time
from datetime import datetime, timezone
from nestor.sqlite_store import SqliteStore

DB = 'data/nestor-demo.db'

def make_id():
    return str(uuid.uuid4())

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def compose_from_json(data, dry_run=False):
    domain = data["domain"]
    origin = f"round4:{domain}"
    ts = now_iso()

    pairs = []
    pair_id_by_source = {}

    for p in data.get("pairs", []):
        pid = make_id()
        pair_id_by_source[p["source_text"]] = pid
        pairs.append({
            "id": pid,
            "source_text": p["source_text"],
            "source_norm": p["source_text"].lower().strip(),
            "source_lang": p.get("source_lang", "en"),
            "target_text": p["target_text"],
            "target_lang": p.get("target_lang", "en"),
            "status": "draft",
            "verifier": "",
            "weight": 1.0,
            "origin": origin,
            "created_at": ts,
            "seal_sig": "",
            "reason": p.get("reason", ""),
            "superseded_by": "",
        })

    edges = []
    for e in data.get("edges", []):
        src_id = pair_id_by_source.get(e.get("from_source"))
        dst_id = pair_id_by_source.get(e.get("to_source"))
        if src_id and dst_id and e.get("kind") in ("contradicts", "refines", "supersedes"):
            edges.append({
                "id": make_id(),
                "src_id": src_id,
                "dst_id": dst_id,
                "kind": e["kind"],
                "reason": e.get("reason", ""),
                "verifier": "",
                "created_at": ts,
                "edge_sig": "",
            })

    evidence = []
    for ev in data.get("evidence", []):
        pid = pair_id_by_source.get(ev.get("pair_source"))
        if pid:
            evidence.append({
                "id": make_id(),
                "pair_id": pid,
                "kind": ev.get("kind", "url"),
                "locator": ev.get("locator", ""),
                "attaches_to": "",
                "reason": ev.get("reason", ""),
                "attached_by": origin,
                "created_at": ts,
            })

    if dry_run:
        return {"pairs": len(pairs), "edges": len(edges), "evidence": len(evidence), "domain": domain}

    s = SqliteStore(DB)
    inserted_pairs = 0
    for p in pairs:
        try:
            s.memory_insert(p)
            inserted_pairs += 1
        except Exception as ex:
            print(f"  WARN pair skip: {ex}")

    inserted_edges = 0
    for e in edges:
        try:
            s.memory_add_edge(e)
            inserted_edges += 1
        except Exception as ex:
            print(f"  WARN edge skip: {ex}")

    inserted_ev = 0
    for ev in evidence:
        try:
            s.memory_add_evidence(ev)
            inserted_ev += 1
        except Exception as ex:
            print(f"  WARN evidence skip: {ex}")

    return {"pairs": inserted_pairs, "edges": inserted_edges, "evidence": inserted_ev, "domain": domain}


def compose_all(json_files, dry_run=False):
    results = []
    for path in json_files:
        with open(path) as f:
            data = json.load(f)
        r = compose_from_json(data, dry_run=dry_run)
        results.append(r)
        action = "Would insert" if dry_run else "Inserted"
        print(f"  [{r['domain']}] {action}: {r['pairs']} pairs, {r['edges']} edges, {r['evidence']} evidence")
    return results


def wire_cross_domain_edges(domains_data, existing_pairs=None):
    """Find cross-domain connections based on shared entities/topics."""
    if existing_pairs is None:
        s = SqliteStore(DB)
        with s._db() as conn:
            existing_pairs = conn.execute(
                "SELECT id, source_text, target_text, origin FROM tm_pairs"
            ).fetchall()

    cross_edges = []
    all_new_pairs = {}
    for d in domains_data:
        origin = f"round4:{d['domain']}"
        for p in d.get("pairs", []):
            all_new_pairs[p["source_text"]] = {"origin": origin, "text": p["target_text"]}

    keywords_to_pairs = {}
    for row in existing_pairs:
        pid, src, tgt, origin = row
        for kw in _extract_keywords(src + " " + tgt):
            keywords_to_pairs.setdefault(kw, []).append((pid, src, origin))

    for src_text, info in all_new_pairs.items():
        for kw in _extract_keywords(src_text + " " + info["text"]):
            if kw in keywords_to_pairs:
                for pid, existing_src, existing_origin in keywords_to_pairs[kw]:
                    if existing_origin != info["origin"]:
                        cross_edges.append({
                            "new_source": src_text,
                            "existing_id": pid,
                            "existing_source": existing_src,
                            "existing_origin": existing_origin,
                            "keyword": kw,
                        })
    return cross_edges


def _extract_keywords(text):
    stopwords = {'the','a','an','is','are','was','were','be','been','being',
                 'have','has','had','do','does','did','will','would','shall',
                 'should','may','might','must','can','could','of','in','to',
                 'for','with','on','at','from','by','about','as','into','through',
                 'during','before','after','above','below','between','out','off',
                 'over','under','again','further','then','once','and','but','or',
                 'nor','not','no','so','than','too','very','just','that','this',
                 'these','those','it','its','all','each','every','both','few',
                 'more','most','other','some','such','only','own','same','also',
                 'how','what','which','who','whom','when','where','why','up','down'}
    words = text.lower().split()
    return {w.strip('.,;:()[]"\'') for w in words
            if len(w) > 3 and w.strip('.,;:()[]"\'') not in stopwords}


def store_totals():
    s = SqliteStore(DB)
    stats = s.memory_stats()
    with s._db() as conn:
        edges = conn.execute("SELECT kind, COUNT(*) FROM decision_edges GROUP BY kind").fetchall()
        ev_count = conn.execute("SELECT COUNT(*) FROM decision_evidence").fetchone()[0]
        origins = conn.execute(
            "SELECT origin, COUNT(*) FROM tm_pairs GROUP BY origin ORDER BY COUNT(*) DESC"
        ).fetchall()
    print(f"\n{'='*50}")
    print(f"STORE TOTALS")
    print(f"{'='*50}")
    print(f"  Pairs:    {stats.get('total', '?')} (sealed: {stats.get('sealed', '?')}, draft: {stats.get('draft', '?')})")
    print(f"  Edges:    {sum(e[1] for e in edges)} ({', '.join(f'{e[1]} {e[0]}' for e in edges)})")
    print(f"  Evidence: {ev_count}")
    print(f"\n  Origins (top 10):")
    for o, c in origins[:10]:
        print(f"    {o}: {c}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auto_compose.py <file1.json> [file2.json ...] [--dry-run]")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    files = [f for f in sys.argv[1:] if f != "--dry-run"]

    print(f"Auto-composing {len(files)} domain(s){'  [DRY RUN]' if dry_run else ''}...")
    results = compose_all(files, dry_run=dry_run)

    totals = {"pairs": 0, "edges": 0, "evidence": 0}
    for r in results:
        for k in totals:
            totals[k] += r[k]

    print(f"\nTotal: {totals['pairs']} pairs, {totals['edges']} edges, {totals['evidence']} evidence")

    if not dry_run:
        store_totals()
