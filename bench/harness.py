"""Shared plumbing: build a filled store, time things, record results to disk.

Every bench writes a JSON blob to ``bench/results/<name>.json`` with its
parameters, environment and measurements, so findings survive the session that
produced them. Results are append-only per run: each file carries a ``runs``
list, newest last.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time

#: The **published** record — tracked in git, updated deliberately.
RESULTS = pathlib.Path(__file__).parent / "results"

#: Where a run lands by default. Gitignored.
#:
#: Every bench used to append straight into the tracked file, which meant simply
#: *running* one dirtied the working tree and blocked the next `git pull`. That
#: is not hypothetical: it happened to the first person to reproduce a result
#: from a clean clone, within minutes of pulling the change that documented the
#: hazard. Their runs and the published ones were the same kind of object in the
#: same file, so git had no way to merge them and neither did a person.
#:
#: Splitting them is not a storage detail, it is the difference between two
#: claims. A published run is one somebody decided was worth keeping; a local
#: run is one that happened. Only the first belongs in a record other people
#: read, and the old layout could not tell them apart — the same failure the
#: `superseded` markers exist to correct, one level up.
LOCAL = RESULTS / "local"

#: Set `NESTOR_BENCH_PUBLISH=1` to write the tracked file instead. Deliberate,
#: per-invocation, and visible in the shell history that produced it.
PUBLISH_ENV = "NESTOR_BENCH_PUBLISH"


def publishing() -> bool:
    return os.environ.get(PUBLISH_ENV, "").strip() not in ("", "0", "false", "no")


ROOT = pathlib.Path(__file__).parent.parent


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              cwd=ROOT, timeout=10).stdout.strip()
    except Exception:
        return ""


def _git_rev() -> str:
    return _git("rev-parse", "--short", "HEAD") or "unknown"


def _git_dirty() -> bool:
    """Whether the working tree differs from HEAD, including untracked files.

    ``git_rev`` alone is not provenance, and this repository has the receipts:
    every one of the first 23 runs in ``results/surfaces_human.json`` recorded
    ``111c187``, because the bench files were untracked while they were being
    edited. HEAD never moved, the code changed underneath it, and four of those
    runs were produced by a harness carrying two defects that were later fixed.
    **A revision that cannot move is not a version.**
    """
    return bool(_git("status", "--porcelain"))


def code_digest(paths) -> str:
    """Short digest over the source that actually produced a run.

    Tied to file *contents*, not to a commit, because the failure this exists to
    catch is the one a commit hash structurally misses: code that changed while
    the revision did not. Files are hashed in sorted order together with their
    repo-relative names, so moving a file changes the digest too.

    Deliberately narrow — the caller declares which files determine its numbers.
    Hashing all of ``bench/`` would move this digest whenever an unrelated bench
    was edited, and a fingerprint that cries wolf is one people learn to ignore.
    """
    h = hashlib.sha256()
    for p in sorted({pathlib.Path(x).resolve() for x in paths}):
        try:
            rel = p.relative_to(ROOT)
        except ValueError:
            rel = pathlib.Path(p.name)
        h.update(str(rel).encode("utf-8") + b"\0")
        try:
            h.update(p.read_bytes())
        except OSError:
            h.update(b"<unreadable>")
        h.update(b"\0")
    return h.hexdigest()[:12]


def environment(code_files=()) -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "git_rev": _git_rev(),
        "git_dirty": _git_dirty(),
        "code_digest": code_digest(code_files) if code_files else None,
    }


def record(name: str, params: dict, measurements, notes: str = "",
           run_id: str = "", complete: bool = True,
           code_files=()) -> pathlib.Path:
    """Append (or update) one run.

    Writes to ``bench/results/local/<name>.json`` — **gitignored** — unless
    ``NESTOR_BENCH_PUBLISH=1``, which writes the tracked
    ``bench/results/<name>.json`` instead. See :data:`LOCAL` for why the two are
    separate; the short version is that running a bench should not dirty the
    repository, and a run nobody chose to keep should not sit in a file other
    people read as a record.

    Pass a stable ``run_id`` and call this after every row to checkpoint a long
    bench as it goes: the matching run is rewritten in place rather than
    appended again. A run that dies partway then leaves its completed rows on
    disk instead of taking them with it, and progress is visible in the results
    file while the bench is still going.

    ``complete=False`` marks the run as in-flight, so a partial result can never
    be mistaken for a finished one.
    """
    target = RESULTS if publishing() else LOCAL
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{name}.json"
    # A local file starts from the published record, so `--resume` and the
    # in-place `run_id` rewrite keep working across the split, and a local file
    # is a superset rather than an orphan.
    if not path.exists() and not publishing():
        published = RESULTS / f"{name}.json"
        if published.exists():
            path.write_text(published.read_text())
    doc = {"bench": name, "runs": []}
    if path.exists():
        try:
            doc = json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    entry = {
        "run_id": run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "complete": complete,
        "environment": environment(code_files),
        "params": params,
        "notes": notes,
        "measurements": measurements,
    }
    runs = doc.setdefault("runs", [])
    for i, prior in enumerate(runs):
        if run_id and prior.get("run_id") == run_id:
            runs[i] = entry
            break
    else:
        runs.append(entry)
    # Write via a temp file in the same directory, then replace: a bench killed
    # mid-write must not leave truncated JSON where its results used to be.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    tmp.replace(path)
    return path


def new_run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def load_runs(name: str) -> list:
    """Every recorded run for a bench, oldest first. ``[]`` if none.

    Used by ``--resume``: a long bench cannot count on outliving the session
    that launched it, so completed rows from earlier attempts are reused rather
    than recomputed.

    Reads the **local** file when one exists, else the published one — never
    both concatenated. A local file is seeded from the published record on first
    write, so it is already a superset; merging the two would double every run
    that predates the split and quietly inflate any count taken over the result.
    """
    for path in (LOCAL / f"{name}.json", RESULTS / f"{name}.json"):
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text()).get("runs", [])
        except json.JSONDecodeError:
            continue
    return []


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
    """A shared signing key for benches, and isolation from any real keyring.

    Every bench that seals (``seal_all`` above, and the direct
    ``memory.add_pair(status="sealed", ...)`` calls in ``bench_surfaces.py``)
    seals under a synthetic verifier — ``"bench"`` — that is deliberately not
    a person and so is deliberately not in anybody's real keyring. Run with a
    real ``NESTOR_KEYRING`` exported (correct for a real deployment, and
    exactly what an operator standing one up plausibly has set), sealing as
    ``"bench"`` raises :class:`nestor.keyring.UnknownVerifierError`: there is
    no key for a name nobody meant to register. That is a fault in the bench
    reading the deployment's config, not in what the bench measures — the same
    shape IDEAS.md §6.98 records against the audit scripts, so a bench run
    from a shell configured for real use previously crashed rather than
    measuring anything.

    Popping ``NESTOR_KEYRING`` and clearing any injected keyring is not
    restored afterward, unlike :func:`nestor.keyring.isolated` — a bench is a
    one-shot process with no ambient keyring configuration downstream of this
    call that anything should see, so there is nothing to hand back. A test
    process is different: pytest's ``isolate_globals`` autouse fixture resets
    both between tests regardless.
    """
    os.environ["NESTOR_SEAL_KEY"] = value
    os.environ.pop("NESTOR_KEYRING", None)
    from nestor import keyring
    keyring.set_keyring(None)
