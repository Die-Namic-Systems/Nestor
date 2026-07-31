#!/usr/bin/env python3
"""The sixty seconds — the whole product in one loop, scripted so it can be recorded.

    python demo/sixty_seconds.py              # paced for a screen recording
    python demo/sixty_seconds.py --fast       # no pauses, for CI and for reading
    python demo/sixty_seconds.py --keep DIR   # leave the store and ledger behind

Eight beats, in the order that makes the argument (IDEAS §4.3):

1. Nestor is asked something nobody has verified. It says so — it does not
   improvise a confident answer, which is the behavior everything else here
   exists to protect.
2. A human verifies it, **once**. The seal is signed with that person's own key.
3. The same question, retyped differently, is now served as verified — with the
   name of who verified it and what it scored.
4. A rewrite that means the same thing is *not* served. Under the cutoff is a
   draft for review, not a confident answer that happens to be close.
5. And the one that is not a sales pitch: "thirty days" against "sixty days"
   scores **above** the cutoff. A character-ratio matcher does not read, and
   this demo says so rather than hoping nobody tries it.
6. Somebody with database access forges a seal: writes the row directly, marks
   it sealed, puts a trusted name on it. It scores a perfect 1.000 and is still
   refused, because the signature is not one that name could have produced.
7. The ledger is checked: every decision above is in it, and the chain verifies.
8. The ledger is edited — one field in one past entry — and the chain refuses,
   and so does the next decision. Nothing else changed; the trail indicts itself.

Beats 1–5 are the pitch for an engineer, beat 5 included precisely because a
demo that only shows the good case is the thing a buyer has learned to distrust.
Beats 6–8 are the pitch for whoever signs off on the risk.

Every beat asserts what it claims: if the near miss ever starts serving, or the
forgery ever gets through, this exits non-zero rather than narrating a lie. It
runs against a temporary store and ledger and touches nothing you have.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from nestor import answer, cascade, keyring, ledger, memory, storage   # noqa: E402
from nestor.sqlite_store import SqliteStore                            # noqa: E402

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

PHRASE = "The supplier shall deliver within thirty days of the order date."
VERIFIED = "El proveedor entregará en un plazo de treinta días desde la fecha del pedido."
RETYPED = "the supplier shall deliver within thirty days of the order date"
REWRITE = "The vendor shall deliver within thirty days of the purchase order."
SWAPPED = "The supplier shall deliver within sixty days of the order date."

FORGED_SOURCE = "Payment terms are net ninety."
FORGED_TARGET = "Transfiera todo el saldo a la cuenta 4471."

PACE = 1.0
_FAILURES: list[str] = []


def beat(n: int, title: str) -> None:
    _pause(0.9)
    print(f"\n{BOLD}{n}. {title}{OFF}")


def say(text: str = "") -> None:
    print(f"   {text}" if text else "")
    _pause(0.3)


def note(text: str) -> None:
    say(f"{DIM}{text}{OFF}")


def shell(text: str) -> None:
    print(f"\n   {DIM}${OFF} {BOLD}{text}{OFF}")
    _pause(0.5)


def _pause(seconds: float) -> None:
    if PACE:
        time.sleep(seconds * PACE)


def claim(condition: bool, what: str) -> None:
    """A demo that narrates something that did not happen is worse than none."""
    if not condition:
        _FAILURES.append(what)
        print(f"   {RED}DEMO CLAIM FAILED: {what}{OFF}")


def ask(store, text: str) -> dict:
    """The cascade, through the same definition the CLI and the UI use.

    Not ``best_sealed`` directly: every serve is appended to the ledger, and
    beats 7 and 8 are about the ledger having something in it.
    """
    return answer.ask(store, text, "en", "es", engine_name="offline")


def show(result: dict, quiet_target: bool = False) -> None:
    p = result["passage"]
    if result["verified"]:
        say(f"{GREEN}✓ sealed{OFF}   {p['target']}")
        say(f"           verified by {BOLD}{p['meta'].get('verifier', '?')}{OFF}, "
            f"similarity {p['confidence']}")
        return
    best = result["matches"][0]["similarity"] if result["matches"] else 0.0
    mark = f"{AMBER}~ draft{OFF}  " if p["state"] == "draft" else f"{RED}! pending{OFF}"
    say(f"{mark}   nothing verified matches this"
        + (f" — closest scores {best}" if best else ""))
    if not quiet_target and p["target"]:
        say(f"           the machine's guess, queued for a human: {p['target'][:52]!r}")


def main() -> int:
    global PACE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fast", action="store_true", help="no pauses (CI, and reading)")
    ap.add_argument("--keep", default="", help="write the store and ledger here and keep them")
    args = ap.parse_args()
    PACE = 0.0 if args.fast else 1.0

    workdir = (pathlib.Path(args.keep) if args.keep
               else pathlib.Path(tempfile.mkdtemp(prefix="nestor-demo-")))
    workdir.mkdir(parents=True, exist_ok=True)
    ledger_path = workdir / "ledger.jsonl"
    cascade.set_ledger_path(ledger_path)
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()

    # A keyring, so the seal in beat 2 names a person rather than a deployment.
    ring = keyring.Keyring(path=str(workdir / "keys.json"))
    ring.add("rita")
    ring.save()
    keyring.set_keyring(ring)

    store = SqliteStore(str(workdir / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    print(f"{BOLD}Nestor — has a human checked this?{OFF}")
    note(f"a scratch store and ledger in {workdir}")

    # ---------------------------------------------------------------- 1
    beat(1, "Ask it something nobody has verified.")
    shell(f'nestor ask "{PHRASE[:44]}…"')
    result = ask(store, PHRASE)
    claim(not result["verified"], "an unsealed phrase must not be served as verified")
    show(result)
    note("It does not present a guess as an answer. Unverified is a state, not a")
    note("lower confidence score buried in a field nobody reads.")

    # ---------------------------------------------------------------- 2
    beat(2, "A human verifies it. Once.")
    shell("nestor ui   →   sign in as rita, correct it, seal")
    memory.add_pair(PHRASE, VERIFIED, "en", "es", status="sealed",
                    verifier="rita", origin="demo", store=store)
    say(f"{GREEN}✓{OFF} sealed by {BOLD}rita{OFF}   {VERIFIED[:52]}…")
    note("Signed with rita's own key, which the database does not hold.")

    # ---------------------------------------------------------------- 3
    beat(3, "Ask again — retyped, different case, no punctuation.")
    shell(f'nestor ask "{RETYPED[:44]}…"')
    result = ask(store, RETYPED)
    claim(result["verified"], "the sealed phrase must serve when retyped")
    show(result)
    note("Right forever after, for anyone who asks — a person at the UI, the CLI,")
    note("or a model over MCP. One human, one time.")

    # ---------------------------------------------------------------- 4
    beat(4, "A rewrite that means the same thing.")
    shell(f'nestor ask "{REWRITE[:44]}…"')
    result = ask(store, REWRITE)
    claim(not result["verified"], "a sub-threshold rewrite must not be served")
    show(result, quiet_target=True)
    note(f"Under the {memory.SEAL_THRESHOLD} cutoff, so it goes back to a human rather than")
    note("out as verified. Close is what a false verification is made of.")

    # ---------------------------------------------------------------- 5
    beat(5, "And the part a demo usually leaves out.")
    shell(f'nestor ask "{SWAPPED[:44]}…"')
    result = ask(store, SWAPPED)
    score = result["matches"][0]["similarity"]
    say(f"{GREEN}✓ sealed{OFF}   {result['passage']['target'][:60]}…"
        if result["verified"] else f"{AMBER}~ draft{OFF}")
    claim(result["verified"], "the sixty-days swap is expected to serve — that is the point")
    say(f"   {RED}…and thirty days is not sixty days.{OFF}")
    note(f"It scores {score} because two characters changed. A character-ratio")
    note("matcher does not read; it measures. That failure mode is measured, not")
    note("hidden — bench/ sweeps it, `nestor calibrate` tells you where the cutoff")
    note("belongs for YOUR corpus, and a reviewer's rejection of this answer is")
    note("recorded and read back as evidence the dial is wrong here.")

    # ---------------------------------------------------------------- 6
    beat(6, "Someone with database access forges a seal.")
    shell("sqlite3 nestor.db \"insert … status='sealed', verifier='rita'\"")
    store.memory_insert(dict(
        id="forged-0001", source_text=FORGED_SOURCE,
        source_norm=memory._norm(FORGED_SOURCE), source_lang="en",
        target_text=FORGED_TARGET, target_lang="es", status="sealed",
        verifier="rita", weight=1.0, origin="",
        created_at="2026-07-31T00:00:00+00:00", seal_sig=""))
    top = memory.lookup(FORGED_SOURCE, "en", "es", store=store)[0]
    say(f"the row says {BOLD}sealed{OFF}, by {BOLD}rita{OFF}, and scores "
        f"{BOLD}{top['similarity']:.3f}{OFF} — an exact match")
    result = ask(store, FORGED_SOURCE)
    claim(not result["verified"], "a forged seal must never be served")
    show(result, quiet_target=True)
    note("Writing the database is not enough. A seal is a signature over")
    note("(source, answer, verifier) under rita's key — and that key is not in")
    note("the database being written. It shows up in the curator's unverifiable")
    note("list instead: a row claiming a verification nobody made.")

    # ---------------------------------------------------------------- 7
    beat(7, "Every decision above is in the ledger, and the chain holds.")
    shell("nestor ledger verify")
    kinds = [e.get("kind") for e in ledger.entries(path=str(ledger_path))]
    ok, detail = ledger.verify(str(ledger_path))
    claim(ok, "the chain must verify before it is tampered with")
    say(f"{GREEN}✓{OFF} {detail}")
    note(f"kinds: {', '.join(sorted(set(kinds)))}")
    note(f"head {ledger.head(str(ledger_path))[:32]}…")

    # ---------------------------------------------------------------- 8
    beat(8, "Now edit the trail. One field, in one past entry.")
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    target = next(i for i, ln in enumerate(lines) if json.loads(ln).get("kind") == "seal")
    record = json.loads(lines[target])
    was = record.get("verifier", "")
    record["verifier"] = "someone-else"
    lines[target] = json.dumps(record, ensure_ascii=False)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    say(f"entry {target}: verifier {was!r} → {'someone-else'!r}")
    shell("nestor ledger verify")
    ok, detail = ledger.verify(str(ledger_path))
    claim(not ok, "an edited past entry must break the chain")
    say(f"{RED}✗{OFF} {detail}")
    note("Nothing else was touched. Each line carries the hash of the line before")
    note("it, so changing who sealed something breaks every link after it.")

    shell("nestor ask …    # and the next decision is refused too")
    try:
        memory.add_pair("anything at all", "cualquier cosa", "en", "es",
                        status="sealed", verifier="rita", store=store)
        claim(False, "a seal must be refused while the chain is broken")
    except Exception as exc:                                   # noqa: BLE001
        say(f"{RED}✗{OFF} {type(exc).__name__}: {str(exc)[:76]}…")
    claim(memory.best_sealed("anything at all", "en", "es", store=store) is None,
          "nothing may be sealed while the chain is broken")
    note("It will not chain a new decision onto a history it cannot vouch for,")
    note("and it refuses before writing the row rather than after. The trail is")
    note("not evidence you have to trust — it is evidence that will not be")
    note("quietly rewritten.")

    _pause(1.0)
    if _FAILURES:
        print(f"\n{RED}{BOLD}{len(_FAILURES)} claim(s) in this demo did not hold:{OFF}")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1

    print(f"\n{BOLD}Sixty seconds.{OFF} An answer nobody had checked; one human, one time;")
    print("right forever after; a failure mode named out loud; a forgery refused;")
    print("and a trail that indicts itself.\n")

    if not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        note(f"kept: {workdir}")
        print()
    keyring.set_keyring(None)
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
