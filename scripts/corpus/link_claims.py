#!/usr/bin/env python3
"""Embed corpus claims, then propose the edges between them.

    python scripts/corpus/link_claims.py --embed          # embed what is new
    python scripts/corpus/link_claims.py --link           # propose edges
    python scripts/corpus/link_claims.py --embed --link   # both

**Greenfield by design.** Both halves are incremental and order-free: embedding
skips any claim whose text already has a vector under this model, and linking
skips any pair that already has an edge. Feed it the next thing; it does not
care what arrived before, how much, or in what order.

## Why this exists

The corpus keys on the SOURCE. For ``symbol -> docstring`` — most of the store —
that key is a file path, so the only convergence it can see is two repositories
sharing a filename. Measured 2026-08-30, its widest "agreement" was one almanac
template copied twelve times and ``tools/changelog_dedup.py`` propagated into
eight repos. Neither is agreement; both are copying.

Meanwhile 124 cross-family matches were sitting there unindexed — ``UTETY`` and
``willow-mcp`` on hash-chained disclosure, ``Forge`` and ``willow-mcp`` on
refusing anything that cannot positively establish loopback, ``Jeles`` and
``homestead-ledger`` on a merge that must wait for CI. The claims were in the
store. Nothing could ask the question.

## Three relations, not one

The measurement's real lesson is that "these two say the same thing" hides three
different facts, and a graph that cannot tell them apart is noise:

``copy``
    Same normalised source key. A template propagated, a file vendored. Says
    nothing about anyone's thinking.

``lineage``
    Different key, but the repositories are related by a tombstone's successor
    chain. ``willow-1.9 -> willow-2.0 -> willow-mcp`` is one idea travelling,
    not two arrivals. This is read from ``tombstones.json`` — **authored, never
    guessed** — because descent is exactly the thing a filesystem cannot tell
    you.

``convergence``
    Different key, unrelated repositories, similar meaning. The only one that is
    evidence of anything, and the one the operator was looking for.

## The covenant

Every edge is written with ``verifier = ''``. **A machine may propose an edge
and may not confirm it.** `convergence` in particular is a claim about
independent arrival, and the corpus's own decision `0227` treats that as a
construction warrant — something a human checks by reading both sides, not
something cosine similarity settles.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sqlite3
import sys
import time

import numpy

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from nestor import ollama_embed
from nestor.embedding_store import blob_to_vec, vec_to_blob

MIN_CHARS = 80
BATCH = 64


def tombstone_families(path: pathlib.Path) -> dict[str, str]:
    """Repository -> lineage root, following ``successor`` chains.

    Authored, not inferred, from two sources: a tombstone's ``successor`` chain
    (one repository became another) and the ``families`` map (they are
    siblings). Nothing about a shared word in a directory name is evidence of
    either -- ``willow-mcp`` and ``willow-2.0`` are kin, ``willow`` and
    ``willowbrook`` would not be, and only a person knows which.
    """
    import json
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    succ = {k: v.get("successor") for k, v in (data.get("tombstones") or {}).items()
            if v.get("successor")}
    declared = dict(data.get("families") or {})
    roots: dict[str, str] = {}
    for name in set(succ) | set(succ.values()):
        seen, cur = set(), name
        while cur in succ and succ[cur] not in seen:
            seen.add(cur)
            cur = succ[cur]
        roots[name] = cur
    # A declared family wins over a derived chain: siblings never appear in a
    # successor chain at all, and they are the majority of the misfiling this
    # was written to fix.
    roots.update(declared)
    return roots


def embed(db: pathlib.Path, model: str, limit: int) -> int:
    con = sqlite3.connect(str(db))
    todo = con.execute(
        "SELECT c.id, c.target_text FROM corpus_claims c "
        "LEFT JOIN corpus_embeddings e ON e.claim_id = c.id AND e.model_name = ? "
        "WHERE e.claim_id IS NULL AND length(c.target_text) >= ? "
        "LIMIT ?", (model, MIN_CHARS, limit)).fetchall()
    if not todo:
        print("  nothing to embed — every claim over "
              f"{MIN_CHARS} chars already has a vector under {model}")
        return 0
    print(f"  embedding {len(todo)} claim(s) with {model}", flush=True)
    done = t0 = 0
    t0 = time.time()
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            vecs = ollama_embed.embed_many([t for _, t in chunk], model=model)
        except Exception as e:                                     # noqa: BLE001
            print(f"    REFUSED at {done}: {type(e).__name__}: {e}")
            break
        rows = []
        for (cid, text), v in zip(chunk, vecs):
            if not v:
                continue
            rows.append((cid, model,
                         hashlib.sha256(text.encode()).hexdigest(),
                         vec_to_blob(tuple(v))))
        con.executemany("INSERT OR REPLACE INTO corpus_embeddings"
                        "(claim_id, model_name, source_sha, embedding) VALUES (?,?,?,?)", rows)
        con.commit()
        done += len(rows)
        if done and done % (BATCH * 8) == 0:
            print(f"    {done}/{len(todo)}  ({done / max(1e-9, time.time() - t0):.0f}/s)", flush=True)
    print(f"  embedded {done}")
    return done


def link(db: pathlib.Path, model: str, threshold: float, top_k: int,
         tombstones: pathlib.Path) -> dict:
    con = sqlite3.connect(str(db))
    rows = con.execute(
        "SELECT e.claim_id, c.repository, c.source_norm, c.source_lang, c.target_lang, e.embedding "
        "FROM corpus_embeddings e JOIN corpus_claims c ON c.id = e.claim_id "
        "WHERE e.model_name = ?", (model,)).fetchall()
    if not rows:
        print("  no embeddings — run --embed first", file=sys.stderr)
        return {}
    print(f"  {len(rows)} embedded claim(s)", flush=True)

    roots = tombstone_families(tombstones)
    ids, meta = [], {}
    mat = numpy.empty((len(rows), len(blob_to_vec(rows[0][5]))), dtype=numpy.float32)
    for n, (cid, repo, snorm, sl, tl, blob) in enumerate(rows):
        ids.append(cid)
        meta[cid] = (repo, snorm)
        mat[n] = blob_to_vec(blob)
    # Cosine on unit-normalised rows is a dot product, so normalise once and the
    # whole comparison is one matmul. The pure-Python version of this loop was
    # O(n^2) at 768 dimensions -- about 100 billion multiply-adds, hours of
    # wall clock for arithmetic BLAS does in minutes. Same numbers, same
    # threshold; only the arithmetic moved.
    mat /= numpy.linalg.norm(mat, axis=1, keepdims=True).clip(min=1e-9)
    repo_of = numpy.array([meta[c][0] for c in ids])
    print(f"  {mat.shape[0]} vectors at dim {mat.shape[1]} — comparing", flush=True)

    have = {(a, b) for a, b in con.execute("SELECT src_id, dst_id FROM corpus_edges")}
    counts = {"copy": 0, "lineage": 0, "convergence": 0, "skipped_existing": 0}
    new_rows = []
    #: Rows at a time. Bounded so peak memory is CHUNK x n floats rather than
    #: n x n -- 16k squared would be a gigabyte of similarity nobody needs at once.
    CHUNK = 512
    for lo in range(0, len(ids), CHUNK):
        hi = min(lo + CHUNK, len(ids))
        sims = mat[lo:hi] @ mat.T
        for r in range(hi - lo):
            i = lo + r
            row = sims[r]
            row[i] = -1.0                      # never link a claim to itself
            row[repo_of == repo_of[i]] = -1.0  # same repository is not a finding
            hits = numpy.flatnonzero(row >= threshold)
            if hits.size == 0:
                continue
            # Only the strongest few neighbours. Without this cap a dense region
            # proposes a near-infinite list, which is the failure the operator
            # named before any of this was built.
            if hits.size > top_k:
                hits = hits[numpy.argpartition(-row[hits], top_k)[:top_k]]
            for j in sorted(hits, key=lambda x: -row[x]):
                a, b = ids[i], ids[int(j)]
                if (a, b) in have or (b, a) in have:
                    counts["skipped_existing"] += 1
                    continue
                ra, sa = meta[a]
                rb, sb = meta[b]
                if sa == sb:
                    kind, why = "copy", "same normalised source key in two repositories"
                elif roots.get(ra, ra) == roots.get(rb, rb):
                    kind, why = "lineage", ("tombstone successor chain: both descend from "
                                            f"{roots.get(ra, ra)}")
                else:
                    kind, why = "convergence", ("different key, unrelated repositories, "
                                                "similar meaning")
                score = float(row[j])
                eid = hashlib.sha256(f"{a}|{b}|{kind}".encode()).hexdigest()[:32]
                new_rows.append((eid, a, b, kind, round(score, 4),
                                 f"{why}; cosine {score:.3f} under {model}"))
                counts[kind] += 1
                have.add((a, b))
        print(f"    {hi}/{len(ids)}  convergence so far: {counts['convergence']}", flush=True)

    new = new_rows
    con.executemany(
        "INSERT OR IGNORE INTO corpus_edges(id, src_id, dst_id, kind, score, reason) "
        "VALUES (?,?,?,?,?,?)", new)
    con.commit()
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=str(pathlib.Path.home() / ".nestor/keep/nestor.db"))
    ap.add_argument("--model", default=ollama_embed.DEFAULT_EMBED_MODEL)
    ap.add_argument("--embed", action="store_true")
    ap.add_argument("--link", action="store_true")
    ap.add_argument("--limit", type=int, default=100000, help="max claims to embed this run")
    #: Calibrated, not chosen. At 0.82 a first pass proposed 1,067 convergence
    #: edges from 2,548 vectors -- 42%, which is what a threshold below the
    #: model's baseline similarity for English technical prose looks like.
    #: Reading the bands: 0.95+ was the same lesson twice (a bot token silently
    #: produces no workflow runs, in kartikeya and homestead-health); 0.90-0.95
    #: held (hatch-vcs cannot version a shallow checkout, in nestor and
    #: willow-mcp); 0.87-0.90 matched PII scrubbing against extracting a class
    #: method body. The floor is where the signal actually started.
    ap.add_argument("--threshold", type=float, default=0.90)
    ap.add_argument("--top-k", type=int, default=5,
                    help="most similar neighbours kept per claim — the cap that stops "
                         "a dense region proposing a near-infinite list")
    args = ap.parse_args()

    db = pathlib.Path(args.db)
    if not db.is_file():
        print(f"error: no store at {db}", file=sys.stderr)
        return 1
    if not (args.embed or args.link):
        print("error: pass --embed, --link, or both", file=sys.stderr)
        return 2
    if args.embed:
        if not ollama_embed.available(args.model):
            print(f"error: {args.model} is not installed in ollama", file=sys.stderr)
            return 1
        embed(db, args.model, args.limit)
    if args.link:
        counts = link(db, args.model, args.threshold, args.top_k,
                      pathlib.Path(__file__).resolve().parent / "tombstones.json")
        if counts:
            print("\n  proposed edges, all unsealed (verifier is empty):")
            for k in ("convergence", "lineage", "copy"):
                print(f"    {counts[k]:6d}  {k}")
            print(f"    {counts['skipped_existing']:6d}  already had an edge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
