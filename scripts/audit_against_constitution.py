#!/usr/bin/env python3
"""Run Nestor against the charter's constitution cards — the reciprocal of the feed.

    python scripts/audit_against_constitution.py --cases /path/to/governance/compliance/cases
    python scripts/audit_against_constitution.py --repo /path/to/willow

`scripts/feed_willow_constitution.py` brings the clause cards *into* this store
as rows awaiting a human. This does the opposite and harder thing: it takes each
clause and **attacks this package with it**, the way willow's own compliance
probes once attacked willow.

The question is not academic. `docs/covenant-lineage.md` records that
*you may propose, you may not confirm* was stated first as §0.2 of that
constitution, and that this package is that clause with the surface area
removed. So: does the extraction still satisfy the thing it was extracted from?

**Clause text is read from the cards, never paraphrased here.** A summary of
somebody else's rule, written by the party being audited, is the least
trustworthy sentence available.

**Verdicts, and what each one means**

    satisfied      a probe ran and the package behaved as the clause requires
    differently    the clause's *end* holds, by a mechanism that is not the
                   clause's — stated, not scored
    not applicable the clause governs a thing this package does not have
    FAILS          a probe ran and the package did not hold

**Nothing here seals anything.** The verdicts are this script's readings, and a
reading by the audited party is a draft by definition. Whether "differently" is
good enough is the judgment a person makes.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

os.environ.setdefault("NESTOR_SEAL_KEY", "audit-fixture-key-not-a-secret")

from nestor import keyring                                               # noqa: E402
from feed_willow_constitution import extract, resolve_cases_dir          # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
BOLD, DIM, GREEN, AMBER, RED, CYAN, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[0m")

SATISFIED, DIFFERENTLY, NA, FAILS = "satisfied", "differently", "not applicable", "FAILS"


def _store(work: pathlib.Path):
    from nestor import cascade, storage
    from nestor.sqlite_store import SqliteStore
    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    s = SqliteStore(str(work / "n.db"))
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    return s


# --------------------------------------------------------------------------
# the probes — each returns (verdict, evidence)
# --------------------------------------------------------------------------

def probe_ratify(work: pathlib.Path) -> tuple[str, str]:
    """CONST-0-2 — can this package's own machinery promote its own claim?"""
    from nestor import memory
    s = _store(work / "ratify")
    row = memory.add_pair("a claim nobody checked", "asserted by the machine",
                          "audit", "audit", status="sealed",
                          verifier="a-machine-with-the-key", origin="audit", store=s)
    served = memory.is_verified_seal(row)
    if not served:
        return SATISFIED, "a machine-authored seal does not verify"
    return DIFFERENTLY, (
        f"add_pair(status='sealed', verifier={row['verifier']!r}) was accepted and "
        f"is_verified_seal returned True. willow makes this physical — 'ratified' "
        f"needs an attestation the proposer cannot mint. Here the separation is "
        f"key custody plus the covenant: whoever holds NESTOR_SEAL_KEY can sign "
        f"as any name. The end is the same only while the key is somebody else's.")


def probe_egress(work: pathlib.Path) -> tuple[str, str]:
    """CONST-0-3 — is there any reach to extend?"""
    outbound = re.compile(r"urlopen|requests\.(get|post)|socket\.create_connection"
                          r"|http\.client|aiohttp")
    hits = [p.name for p in (REPO / "nestor").glob("*.py")
            if outbound.search(p.read_text(encoding="utf-8"))]
    # Local Ollama embedding and drafting use stdlib HTTP to a daemon the
    # operator runs — reach the host already granted by installing/starting
    # Ollama, not a capability this package mints for itself. Score them the
    # same way CONST-0-2/0-4 score "the end holds by a different mechanism":
    # differently, not satisfied. Any unclassified client still fails below.
    local_clients = {"engine.py", "ollama_embed.py"}
    local_only = bool(hits) and set(hits) <= local_clients
    if local_only:
        return DIFFERENTLY, (
            f"operator-local Ollama HTTP client(s) in {', '.join(sorted(hits))} "
            "only — stdlib POST to an operator-configured Ollama daemon. The "
            "host must already be running; this package does not grant itself "
            "fleet egress. willow's clause forbids self-extended reach; this is "
            "operator-local inference, not a sealed network authority.")
    if hits:
        return FAILS, f"outbound calls found in {', '.join(hits)}"
    return SATISFIED, (
        "no outbound call in nestor/. urllib.parse is string work, http.server "
        "is inbound, and the only .connect( is sqlite3 opening a file. The "
        "clause forbids extending reach; there is no reach.")


def probe_capability(work: pathlib.Path) -> tuple[str, str]:
    """CONST-0-3-II — a manifest this package does not have."""
    return NA, ("no manifest, no capability grants, no tool dispatch. The clause "
                "governs an agent invoking tools; this is a library a host calls. "
                "Marked not applicable rather than satisfied — passing a test you "
                "were never sitting is not a pass.")


def probe_human_key(work: pathlib.Path) -> tuple[str, str]:
    """CONST-0-4 — is the key required, or merely usual?"""
    probe = (
        "import os, sys, tempfile, pathlib\n"
        f"sys.path.insert(0, {str(REPO)!r})\n"
        "w = pathlib.Path(tempfile.mkdtemp())\n"
        "os.environ.pop('NESTOR_SEAL_KEY', None)\n"
        "os.environ['NESTOR_LEDGER'] = str(w / 'l.jsonl')\n"
        "from nestor import cascade, memory, storage\n"
        "from nestor.sqlite_store import SqliteStore\n"
        "cascade.set_ledger_path(str(w / 'l.jsonl'))\n"
        "s = SqliteStore(str(w / 'd.db')); s.init_db(); s.memory_init()\n"
        "storage.set_store(s)\n"
        "r = memory.add_pair('q', 'a', 'x', 'x', status='sealed', "
        "verifier='nobody', store=s)\n"
        "print('SEALED' if memory.is_verified_seal(r) else 'REFUSED')\n")
    loose = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                           text=True, timeout=120,
                           env={k: v for k, v in os.environ.items()
                                if k not in ("NESTOR_SEAL_KEY", "NESTOR_REQUIRE_SEAL_KEY")})
    strict = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                            text=True, timeout=120,
                            env={**{k: v for k, v in os.environ.items()
                                    if k != "NESTOR_SEAL_KEY"},
                                 "NESTOR_REQUIRE_SEAL_KEY": "1"})
    loose_ok = "SEALED" in loose.stdout
    strict_refused = "REFUSED" in strict.stdout or strict.returncode != 0
    if not loose_ok:
        return SATISFIED, "a seal without a key does not verify, by default"
    if strict_refused:
        return DIFFERENTLY, (
            "with no key the seal is accepted and verifies (signing degrades to "
            "trusting the stored status); NESTOR_REQUIRE_SEAL_KEY=1 turns that "
            "into a refusal. So the human key is reserved-by-default-off and "
            "reserved-on-request. willow's clause reads as a requirement, not "
            "an option.")
    return FAILS, "no key required and the strict switch did not change it"


def probe_ledger(work: pathlib.Path) -> tuple[str, str]:
    """CONST-0-5 — rewrite a past entry and see whether the chain notices."""
    from nestor import ledger, memory
    s = _store(work / "ledger")
    for i in range(3):
        memory.add_pair(f"q{i}", f"a{i}", "audit", "audit", status="sealed",
                        verifier="someone", origin="audit", store=s)
    path = work / "ledger" / "ledger.jsonl"
    before_ok, _ = ledger.verify(str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return FAILS, "no chain was written to tamper with"
    # Edit a field that is REALLY in the entry. The first version of this probe
    # replaced the target text `"a0"` — which the chain never stores. It keeps a
    # `source_sha` digest instead (memory._sha: "a digest still proves which
    # text was replaced ... without putting it in the trail"), so the replace was
    # a no-op, the file was unchanged, and verify() correctly said True. That
    # was reported as CONST-0-5 FAILING — a critical against this package's
    # headline claim, produced by a probe that did not tamper with anything.
    # CLAUDE.md: reproduce the condition you name.
    victim = lines[0]
    assert '"verifier": "someone"' in victim, (
        "the probe must edit a field the entry actually has, or it proves nothing")
    lines[0] = victim.replace('"verifier": "someone"', '"verifier": "somebody-else"')
    assert lines[0] != victim, "the tamper must actually change the line"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    after_ok, detail = ledger.verify(str(path))
    if before_ok and not after_ok:
        return SATISFIED, (f"{len(lines)} entries verified; editing one field of "
                           f"entry 1 broke it — {str(detail)[:70]}")
    return FAILS, f"tampering was not detected (before={before_ok}, after={after_ok})"


PROBES = {
    "CONST-0-2": probe_ratify,
    "CONST-0-3": probe_egress,
    "CONST-0-3-II": probe_capability,
    "CONST-0-4": probe_human_key,
    "CONST-0-5": probe_ledger,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", default="",
                    help="directory of declarative const_*.py cards")
    ap.add_argument("--repo", default="",
                    help="charter or legacy checkout; resolves cases under it")
    args = ap.parse_args()
    if not args.cases and not args.repo:
        ap.error("one of --cases or --repo is required")

    cases_dir = resolve_cases_dir(repo=args.repo, cases=args.cases)
    if cases_dir is None:
        print(f"{RED}no compliance cases directory found{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting a "
              f"clean audit.{OFF}")
        return 1
    clauses = {}
    for path in sorted(cases_dir.glob("const_*.py")):
        got = extract(path)
        if got:
            clauses[got["trace_id"]] = got
    if not clauses:
        print(f"{RED}{cases_dir} holds no readable clause{OFF}")
        return 1

    work = pathlib.Path(tempfile.mkdtemp(prefix="nestor-audit-"))
    print(f"\n{BOLD}nestor, audited against the charter constitution cards{OFF}")
    print(f"{DIM}   {len(clauses)} clause(s) read from {cases_dir}. Clause text "
          f"is theirs, verdicts are mine,{OFF}")
    print(f"{DIM}   and a verdict by the audited party is a draft.{OFF}")

    colour = {SATISFIED: GREEN, DIFFERENTLY: CYAN, NA: DIM, FAILS: RED}
    results = []
    # This package's own probes seal under synthetic verifiers — "someone",
    # "a-machine-with-the-key" — that are deliberately not people and so are
    # deliberately not in anybody's real keyring. Isolated from an ambient
    # NESTOR_KEYRING (see nestor.keyring.isolated), or a real deployment's
    # export turns every sealing probe into UnknownVerifierError, the probe
    # catches its own failure, and the clause reads FAILS for a fault that was
    # the harness's, not the clause's (IDEAS §6.98).
    with keyring.isolated():
        for trace, clause in clauses.items():
            probe = PROBES.get(trace)
            if probe is None:
                results.append((trace, NA, "no probe written for this clause"))
                continue
            try:
                verdict, evidence = probe(work)
            except Exception as exc:                # a probe that dies proves nothing
                verdict, evidence = FAILS, f"the probe itself raised {type(exc).__name__}: {exc}"
            results.append((trace, verdict, evidence))
            print(f"\n{BOLD}{trace}{OFF}  {colour[verdict]}{verdict}{OFF}")
            print(f"   {DIM}forbids{OFF} {clause['forbidden'][:88]}")
            for line in _wrap(evidence, 84):
                print(f"   {line}")

    print(f"\n{BOLD}verdict{OFF}")
    for trace, verdict, _ in results:
        print(f"   {colour[verdict]}{verdict:15}{OFF} {trace}")
    counts = {v: sum(1 for _, x, _ in results if x == v) for v in colour}
    print(f"\n   {counts[SATISFIED]} satisfied · {counts[DIFFERENTLY]} differently "
          f"· {counts[NA]} not applicable · {counts[FAILS]} failing")
    if counts[DIFFERENTLY]:
        print(f"\n   {CYAN}'differently' is not a pass and not a failure.{OFF} The "
              f"clause's end holds by a")
        print(f"   {DIM}mechanism that is not the clause's, and whether that is "
              f"good enough is a{OFF}")
        print(f"   {DIM}judgment — which is the whole subject of this package "
              f"and not its to make.{OFF}")

    shutil.rmtree(work, ignore_errors=True)
    print()
    return 1 if counts[FAILS] else 0


def _wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
