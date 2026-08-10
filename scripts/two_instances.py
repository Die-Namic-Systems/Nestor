#!/usr/bin/env python3
"""Two independent Nestor instances, and what does and does not cross between them.

    python scripts/two_instances.py            # stand both up, assert, tear down
    python scripts/two_instances.py --keep DIR # leave the two boxes behind

Nestor's export/import story is the claim that a memory can move between
deployments *without laundering trust*: a seal made over there does not become a
seal over here just because it arrived in a file. `portable.py` argues it and
`tests/test_portable.py` unit-tests it. Nothing executed it across two instances
that genuinely did not share state, and the difference is not cosmetic — the
process-wide store, ledger override, installed matcher and keyring are all
module globals, so two "instances" in one interpreter are one instance wearing
two hats.

**What isolation means here.** Separate store, separate ledger, separate
keyring, separate seal key, and every command in its own subprocess with only
its own box's environment. What it does *not* mean: separate machines, separate
filesystems, separate users. This proves independence of **state**, not a trust
boundary against a hostile operator.

**Why it is committed.** It was written once, to answer one question, and it
found `IDEAS.md` §6.36 on the way — `nestor keys add` prints the public half of
an ed25519 keypair and calls it the only copy, which is only visible when you
enrol a verifier on a second box and try to sign in. One use is a thin record.
The alternative was rebuilding it the next time somebody asks what sync would
cost (`TODO.md` §2, `QUESTIONS.md` §8), and that question is not going away.

Nothing here seals on anybody's behalf: both boxes seal as their own fictional
verifier, and the point of the exercise is watching one instance *refuse* to
inherit the other's.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]

#: Everything the package reads from the environment. A box that inherits one of
#: these from the launching shell is not isolated, so each subprocess starts from
#: a copy with all of them stripped and only its own put back.
NESTOR_ENV = ("NESTOR_KEYRING", "NESTOR_SEAL_KEY", "NESTOR_REQUIRE_SEAL_KEY",
              "NESTOR_CACHE_KEY", "NESTOR_LEDGER", "NESTOR_GLOSSARY",
              "NESTOR_LEDGER_VERIFY_INTERVAL_SEC", "NESTOR_FRANK_STRICT",
              "WILLOW_MCP_COMMAND", "WILLOW_APP_ID", "NESTOR_SEMANTIC_TEST")

BOXES = {"a": {"who": "nieves", "key": "box-a-fixture-key-not-a-secret"},
         "b": {"who": "paco", "key": "box-b-fixture-key-not-a-secret"}}

GREEN, RED, DIM, BOLD, OFF = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
_FAILURES: list[str] = []

SEED = '''
import os, sys
sys.path.insert(0, %(repo)r)
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore
cascade.set_ledger_path(os.environ["NESTOR_LEDGER"])
store = SqliteStore(sys.argv[1]); store.init_db(); store.memory_init()
storage.set_store(store)
for src, tgt, reason in %(rows)r:
    memory.add_pair(src, tgt, "es", "en", status="sealed", verifier=%(who)r,
                    origin="fixture:two-instances", reason=reason, store=store)
print(memory.stats(store=store)["sealed"])
'''

# One phrase they both hold and disagree about, and one only B has seen.
A_ROWS = [("Un abrazo muy fuerte", "A great big hug", "How every letter ends.")]
B_ROWS = [("Un abrazo muy fuerte", "With love",
           "How you close a letter in English."),
          ("la Pepa", "the 1812 Constitution",
           "She grew up here. In Cadiz this is not a woman.")]


def claim(condition: bool, what: str) -> None:
    if not condition:
        _FAILURES.append(what)
        print(f"   {RED}CLAIM FAILED: {what}{OFF}")


class Box:
    def __init__(self, root: pathlib.Path, name: str):
        self.name, self.root = name, root / name
        self.root.mkdir(parents=True, exist_ok=True)
        self.who = BOXES[name]["who"]

    @property
    def env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k not in NESTOR_ENV}
        env["PYTHONPATH"] = str(REPO)
        env["NESTOR_SEAL_KEY"] = BOXES[self.name]["key"]
        env["NESTOR_KEYRING"] = str(self.root / "keys.json")
        env["NESTOR_LEDGER"] = str(self.root / "ledger.jsonl")
        return env

    def cli(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "nestor.cli", "--db", str(self.root / "nestor.db"),
             "--ledger", str(self.root / "ledger.jsonl"), *argv],
            capture_output=True, text=True, cwd=REPO, env=self.env, timeout=120)

    def lib(self, code: str, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-c", code, str(self.root / "nestor.db"), *argv],
            capture_output=True, text=True, cwd=REPO, env=self.env, timeout=120)

    def seed(self, rows) -> None:
        # Through the library, not the CLI: there is deliberately no
        # `nestor seal` — `--verifier "$USER"` in a script is not a human
        # checking anything (TODO.md §5.1).
        done = self.lib(SEED % {"repo": str(REPO), "rows": rows, "who": self.who})
        assert done.returncode == 0, done.stdout + done.stderr

    def public_key(self, name: str) -> str:
        ring = json.loads((self.root / "keys.json").read_text(encoding="utf-8"))
        return [v for v in ring["verifiers"] if v["name"] == name][0]["key"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", default="", help="leave the two boxes behind here")
    args = ap.parse_args()
    root = (pathlib.Path(args.keep) if args.keep
            else pathlib.Path(tempfile.mkdtemp(prefix="nestor-two-")))

    print(f"\n{BOLD}Two instances{OFF} — separate store, ledger, keyring, seal key, "
          f"and process.")
    a, b = Box(root, "a"), Box(root, "b")
    for box, rows in ((a, A_ROWS), (b, B_ROWS)):
        added = box.cli("keys", "add", box.who, "--type", "ed25519")
        # The whole demo is ed25519 cross-instance verification, so a failure
        # here — usually a missing [keys] extra — has to stop at the cause. The
        # keyring never gets written, so the next line would otherwise die in
        # seed() with a bare "no keyring", three steps downstream of the reason.
        assert added.returncode == 0, added.stdout + added.stderr
        box.seed(rows)
        print(f"   box {box.name.upper()}  verifier {box.who}  "
              f"{len(rows)} sealed  {DIM}{box.root}{OFF}")

    print(f"\n{BOLD}1. They are actually independent.{OFF}")
    heads = {n: box.cli("ledger", "head").stdout.strip() for n, box in (("a", a), ("b", b))}
    claim(heads["a"] != heads["b"], "the two chains are distinct")
    print(f"   ledger head A {heads['a'][:24]}…\n   ledger head B {heads['b'][:24]}…")
    for box in (a, b):
        got = json.loads(box.cli("--json", "ask", "Un abrazo muy fuerte",
                                 "--from", "es", "--to", "en").stdout)
        print(f"   box {box.name.upper()} answers → {got['passage']['target']!r} "
              f"({got['passage']['meta'].get('verifier', '-')})")
    seen = json.loads(a.cli("--json", "ask", "la Pepa", "--from", "es",
                            "--to", "en").stdout)
    claim(not seen["verified"], "a phrase only B has sealed is unverified in A")
    print(f"   box A on 'la Pepa' → verified={seen['verified']}  "
          f"{DIM}(only B has ever seen it){OFF}")

    print(f"\n{BOLD}2. A seal does not cross just because a file did.{OFF}")
    bundle = root / "from-b.json"
    b.cli("export", "--out", str(bundle))
    first = a.cli("import", str(bundle)).stdout
    # On the COUNT, not the label: the CLI prints "N demoted to draft (...)"
    # whether N is 0 or 1, so matching the words asserts nothing. This is the
    # form that goes red when the trust check is removed.
    claim("0 sealed, 1 demoted to draft" in first,
          "B's seal arrives as a draft, not a seal")
    claim("conflict  'Un abrazo muy fuerte'" in first,
          "the phrase they disagree about is surfaced by name")
    print("   " + "\n   ".join(x for x in first.strip().splitlines() if x.strip()))

    print(f"\n{BOLD}3. With the peer's PUBLIC key, it verifies — and only that.{OFF}")
    a.cli("keys", "add", b.who, "--type", "ed25519", "--public", b.public_key(b.who))
    second = a.cli("import", str(bundle)).stdout
    claim("1 sealed, 0 demoted to draft" in second,
          "the peer's seal now verifies here")
    print("   " + "\n   ".join(x for x in second.strip().splitlines() if x.strip()))
    signable = a.lib(
        "import os,sys; sys.path.insert(0, %r)\n"
        "from nestor import keyring\n"
        "r = keyring.load(os.environ['NESTOR_KEYRING'])\n"
        "print({e.name: bool(getattr(e, 'private', '')) for e in r.entries()})"
        % str(REPO)).stdout.strip()
    claim("'paco': False" in signable, "A can verify as paco and cannot sign as paco")
    print(f"   can_sign in A's keyring: {signable}")

    if args.keep:
        print(f"\n   {DIM}kept: {root}{OFF}")
    else:
        shutil.rmtree(root, ignore_errors=True)
    if _FAILURES:
        print(f"\n{RED}{len(_FAILURES)} claim(s) no longer hold:{OFF}")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print(f"\n{GREEN}Every claim above held.{OFF}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
