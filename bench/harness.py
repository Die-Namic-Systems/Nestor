"""Shared plumbing: build a filled store, time things, record results to disk.

Every bench writes a JSON blob to ``bench/results/<name>.json`` with its
parameters, environment and measurements, so findings survive the session that
produced them. Results are append-only per run: each file carries a ``runs``
list, newest last.
"""
from __future__ import annotations

import json
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time

RESULTS = pathlib.Path(__file__).parent / "results"


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              cwd=pathlib.Path(__file__).parent.parent).stdout.strip()
    except Exception:
        return "unknown"


def environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "git_rev": _git_rev(),
    }


def record(name: str, params: dict, measurements, notes: str = "") -> pathlib.Path:
    """Append one run to ``bench/results/<name>.json`` and return the path."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    doc = {"bench": name, "runs": []}
    if path.exists():
        try:
            doc = json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    doc.setdefault("runs", []).append({
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": environment(),
        "params": params,
        "notes": notes,
        "measurements": measurements,
    })
    path.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    return path


def timed(fn, repeats: int = 1) -> dict:
    """Run ``fn`` ``repeats`` times; return ms statistics."""
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return {
        "ms_mean": round(statistics.mean(samples), 3),
        "ms_median": round(statistics.median(samples), 3),
        "ms_min": round(min(samples), 3),
        "ms_max": round(max(samples), 3),
        "repeats": repeats,
    }


def fresh_store(path: str = ":memory:"):
    """A store with the schema created once, wired as the process-wide store."""
    from nestor import storage
    from nestor.sqlite_store import SqliteStore
    store = SqliteStore(path)
    store.memory_init()
    storage.set_store(store)
    return store


def seal_all(store, phrases, domain="en", target="es", verifier="bench",
             matcher=None) -> None:
    """Seal a list of phrases as ``phrase -> BENCH:<index>``.

    The target carries the index so a served hit can be checked against the
    phrase that was actually asked for — that is how a false seal is detected.
    """
    from nestor import memory
    for i, p in enumerate(phrases):
        memory.add_pair(p, f"BENCH:{i}", domain, target, status="sealed",
                        verifier=verifier, store=store, matcher=matcher)


def quiet_ledger(tmpdir) -> None:
    """Point the ledger at a scratch file so benches never touch data/."""
    from nestor import cascade
    cascade.set_ledger_path(pathlib.Path(tmpdir) / "bench-ledger.jsonl")


def seal_key(value: str = "bench-key") -> None:
    os.environ["NESTOR_SEAL_KEY"] = value
