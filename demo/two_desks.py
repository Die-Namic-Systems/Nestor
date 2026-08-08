#!/usr/bin/env python3
"""Two desks — a client's intake, and the review of the tool that records it.

    python demo/two_desks.py                 # the walk-through
    python demo/two_desks.py --keep DIR      # leave both boxes behind

**This is fiction.** Attercliffe Medical does not exist, neither does its clamp,
and no sentence in here is a decision a human made. Every row carries
``origin="fixture:attercliffe-two-desks"``, both stores and both ledgers are
temporary, and nothing outside this script's working directory is touched. A
fixture that could be mistaken for a real trail is a forged record, and this is
an audit-trail product.

Not the same exercise as ``scripts/two_instances.py``
-----------------------------------------------------
That harness asks whether *state* crosses between deployments — separate store,
ledger, keyring, seal key, process — and answers no. It is about trust.

This one asks a question that never came up while both boxes ran the shipped
translation recipe: **what happens at the human surface when a domain brings its
own matcher?** The README calls ``Matcher`` a two-method seam and ends its recipe
table with *yours / yours / whatever you can normalize and score*. Both desks
below take that row at its word, and only one of them survives it.

Why there are two desks
-----------------------
Attercliffe Medical is nineteen people in Sheffield who make one accessory for
one infusion pump. Two things land on two desks:

* **Intake.** Incident reports arrive from EU distributors in free text, naming
  the device by batch or serial and almost never the same way twice. Ines Bardhi
  runs post-market safety and has to be able to show, per report, that a named
  human adjudicated it. Her domain is not language, so it is not
  ``StringMatcher``: a report keys to the **serial it names**, and
  ``SerialMatcher`` below is the documented two-method seam and nothing else —
  ``normalize`` and ``similarity``, no optional extras.

* **The tool itself.** Their notified body takes the view that software in the
  determination path is under change control like anything else, so the thing
  that records "a human checked this" is itself a thing whose changes a human
  must have checked. Ruaridh Mackay-Osei contracts two days a month to review
  Nestor, and he does it with ``recipes/patch_review.py`` — defect in, patch
  out, sealed when he has read it. His domain is prose about code, so it is
  ``DefectMatcher``.

Two desks, one package, two custom matchers. Both people confirm the only way
anybody is allowed to: at ``nestor.ui``, because a machine may propose and may
not confirm.

What the two desks found — and what closed it
----------------------------------------------
**The surface could be aimed at a custom domain and could not be told its
matcher** (§6.40). ``nestor ui`` takes ``--source-lang`` and ``--target-lang``,
so it pointed at ``incident``/``incident`` happily. There was no ``--matcher``
and ``ui.App`` had no field for one, so every write the UI made — seal,
seal-draft, reject-match — normalized with the default ``StringMatcher``. Ines's
seal landed under a key her domain would never compute: a **second** row
appeared, the draft she was sealing stayed a draft, and the next morning the
same incident came back **pending**. Her verification was in the store, signed,
in the chain, and unreachable. Her recorded *no* went the same way and the wrong
match was served again.

**Fixed.** ``ui.App`` carries a ``matcher``, ``nestor ui`` takes ``--matcher``
for the shipped ones, and it is threaded through every decision the surface
makes — ``add_pair``, ``reject_match``, ``graduate_segment``, ``reject_segment``
and the cascade behind ``/api/ask``. ``None`` still means "defer to the
process-wide matcher", so nothing changes for a host that never had this problem.
The beats below are unchanged and their outcomes are inverted: this fixture now
runs green, and it is kept precisely because it asks the same questions it asked
when the answer was no.

**The desk next door was fine, for a reason nobody chose** (§6.41).
``DefectMatcher`` implements ``score(raw_a, raw_b)`` — documented as *optional* —
and ``best_sealed`` prefers it, comparing raw text and never consulting the
mismatched key. Ruaridh's seals worked throughout. That is the half worth
remembering: a defect that spares whoever implemented **more** than the
documentation asked, and bites whoever implemented exactly what it asked, is a
defect that stays invisible to the person who wrote the documentation. §6.41
asked whether to make ``score()`` mandatory or to stop re-keying; §6.40's fix
answers it by stopping the re-keying, which puts ``score()`` back to being the
optimisation it is described as.

**Two custom-matcher desks used to be two deployments.** ``memory.set_matcher()``
fixed the keying completely and is a module global, so one process could hold her
matcher or his, never both. Both desks now run in one interpreter, each keyed by
its own, with the global untouched — beat 7 measures exactly that.

The last beat is the one worth staying for: what this fixture found goes into the
review desk's queue **as a draft**, because this script may propose and may not
confirm — including about the surface that covenant is enforced by.
"""
from __future__ import annotations

import argparse
import difflib
import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Its own key, so the seals below are really signed and the walk-through does not
# depend on what the caller exported. Named for what it is: a fixture's key is
# not a secret, and a demo that quietly ran with signing off would be showing
# seals nobody could have made.
os.environ.setdefault("NESTOR_SEAL_KEY", "two-desks-fixture-key-not-a-secret")

# Through ui.dispatch rather than the library: the whole claim is about what
# happens at the surface a human is allowed to use, and a demo that reached past
# it to `memory.add_pair(matcher=...)` would be proving the opposite of the point.
from nestor import cascade, memory, storage, ui          # noqa: E402
from nestor.sqlite_store import SqliteStore              # noqa: E402
from recipes import patch_review                         # noqa: E402

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

ORIGIN = "fixture:attercliffe-two-desks"
INES, RUARIDH = "ines", "ruaridh"
INCIDENT = "incident"          # Ines's domain tag, both sides
DEFECT = patch_review.DOMAIN   # "defect", both sides

_FAILURES: list[str] = []


def beat(n: int, title: str) -> None:
    print(f"\n{BOLD}{n}. {title}{OFF}")


def say(text: str = "") -> None:
    print(f"   {text}" if text else "")


def note(text: str) -> None:
    say(f"{DIM}{text}{OFF}")


def claim(condition: bool, what: str) -> None:
    """A demo that narrates something that did not happen is worse than none."""
    if not condition:
        _FAILURES.append(what)
        print(f"   {RED}DEMO CLAIM FAILED: {what}{OFF}")


def gap(condition: bool, what: str) -> None:
    """A claim that a gap is still open.

    Distinguished from :func:`claim` because failing here is *good news*: the
    surface grew the thing it was missing. The exit code is the same — this
    script is now wrong, and a demo narrating a gap somebody closed is the same
    defect as one narrating a fix that never landed.
    """
    if not condition:
        _FAILURES.append(f"(gap closed, update this script) {what}")
        print(f"   {GREEN}GAP CLOSED — update demo/two_desks.py and the IDEAS "
              f"entry it names (§6.40, §6.41): {what}{OFF}")


class SerialMatcher:
    """Ines's matcher. Exactly the documented seam: ``normalize`` + ``similarity``.

    An incident report keys to the device serial it names, so "pump SN CH-4471
    over-delivered on the night run" and "CH4471 free-flow, ward 6" are one key
    and one adjudication. This is the README's *yours / yours / whatever you can
    normalize and score* row, written by somebody who read the seam's two methods
    and implemented the two methods.

    It deliberately does **not** implement the optional ``score(raw_a, raw_b)``.
    That is not an oversight in the fixture — it is the variable under test, and
    §6.41 is what the difference turns out to be worth.
    """

    def normalize(self, value) -> str:
        packed = "".join(c for c in str(value).upper() if c.isalnum())
        for i in range(len(packed) - 5):
            chunk = packed[i:i + 6]
            if chunk.startswith("CH") and chunk[2:].isdigit():
                return chunk
        return str(value).strip().lower()

    def similarity(self, a_norm: str, b_norm: str) -> float:
        return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()


SERIALS = SerialMatcher()

# The night-run report Ines adjudicates, and the same event as the ward sister
# writes it up a fortnight later. One serial, one adjudication — that is the
# entire reason she wrote a matcher instead of using the shipped one.
REPORT = "Pump SN CH-4471 over-delivered during the night run."
RESTATED = "CH4471 free-flow event on ward 6, no injury."
ADJUDICATION = ("Confirmed free-flow: the clamp seats proud when the giving set "
                "is loaded left-handed. Reportable, MIR filed 2026-07-02.")

# The near miss she has to be able to refuse: same batch prefix, different
# failure, and a plausible-looking answer she does not want served again.
WRONG_FOR = "CH-4471 occlusion alarm at 40 ml/h, cleared on reseat."


def at_desk(root: pathlib.Path) -> None:
    """Point the process-wide ledger at this desk's chain.

    Called at every switch between the two desks, and it is not bookkeeping.
    ``cascade`` holds one ledger path for the interpreter, so a fixture that set
    it once would write both desks' decisions into one chain and then count them
    as one desk's — which is the shape of false claim this repo keeps finding in
    its own fixtures. Two desks in one process share this global the same way
    they share the matcher in beat 7; ``scripts/two_instances.py`` is the harness
    that does not have to care, because it uses two processes.
    """
    cascade.set_ledger_path(str(root / "ledger.jsonl"))


def desk_a(workdir: pathlib.Path) -> tuple:
    """Stand up the intake desk: its own store, its own ledger, its own domain."""
    root = workdir / "intake"
    root.mkdir(parents=True, exist_ok=True)
    at_desk(root)
    store = SqliteStore(str(root / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    # `matcher=` is the field §6.40 was about not having. A domain is the tags
    # AND the matcher; handing over only the tags is what filed her seals where
    # she would never look.
    app = ui.App(store=store, source_lang=INCIDENT, target_lang=INCIDENT,
                 matcher=SERIALS, db_path=str(root / "nestor.db"))
    return store, app, root


def desk_b(workdir: pathlib.Path) -> tuple:
    """Stand up the review desk. Same package, same surface, other matcher."""
    root = workdir / "review"
    root.mkdir(parents=True, exist_ok=True)
    at_desk(root)
    store = SqliteStore(str(root / "nestor.db"))
    store.init_db()
    store.memory_init()
    app = ui.App(store=store, source_lang=DEFECT, target_lang=DEFECT,
                 matcher=patch_review.MATCHER, db_path=str(root / "nestor.db"))
    return store, app, root


def rows(store, domain) -> list:
    return sorted(store.memory_candidates(domain, domain),
                  key=lambda r: (r["status"], r["source_norm"]))


def show_rows(store, domain) -> None:
    for row in rows(store, domain):
        who = row.get("verifier") or "-"
        say(f"{row['status']:7} {who:8} key={row['source_norm'][:46]!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", default="", help="leave both boxes behind here")
    args = ap.parse_args()
    work = (pathlib.Path(args.keep) if args.keep
            else pathlib.Path(tempfile.mkdtemp(prefix="nestor-two-desks-")))
    work.mkdir(parents=True, exist_ok=True)

    print(f"\n{BOLD}Attercliffe Medical — two desks{OFF}")
    print(f"{DIM}   Fiction. Nobody here exists, no sentence below is a decision a "
          f"human made,\n   and both boxes are temporary. Every row is tagged "
          f"{ORIGIN}.{OFF}")

    store_a, app_a, root_a = desk_a(work)

    # ---------------------------------------------------------------- 1
    beat(1, "The intake desk, and a question nobody has adjudicated")
    say("Ines runs post-market safety. A report lands from the Lisbon distributor.")
    say(f"{DIM}report  {OFF}{REPORT}")
    nothing = memory.best_sealed(REPORT, INCIDENT, INCIDENT, store=store_a,
                                 matcher=SERIALS)
    claim(nothing is None, "an unadjudicated report is not served as verified")
    say(f"Nestor: {AMBER}pending{OFF} — nothing to offer, said plainly.")
    note("Which is the behaviour everything below exists to protect.")

    draft = memory.add_pair(REPORT, ADJUDICATION, INCIDENT, INCIDENT,
                            status="draft", origin=ORIGIN, store=store_a,
                            matcher=SERIALS,
                            reason="Drafted from the distributor's narrative.")
    say(f"A draft is queued for her. Its key is {BOLD}{draft['source_norm']!r}{OFF} — "
        f"the serial,")
    note("because that is what her matcher says an incident report *is*.")

    # ---------------------------------------------------------------- 2
    beat(2, "She verifies it, at the only surface she is allowed to use")
    say("A machine may propose and may not confirm, so this goes through "
        "nestor.ui —")
    note("the same dispatch the browser calls. No library shortcut.")
    status, body = ui.dispatch(app_a, "POST", "/api/seal-draft", {},
                               {"pair_id": draft["id"], "verifier": INES,
                                "reason": "Read the giving-set photos. Confirmed."})
    claim(status == 200, "the UI accepts the seal")
    sealed = body["pair"]
    say(f"HTTP {GREEN}{status}{OFF}. Sealed by {sealed.get('verifier')!r}. "
        f"It looks exactly like success.")

    claim(sealed["id"] == draft["id"],
          "sealing a draft through the UI upgrades that row rather than writing a new one")
    claim(sealed["source_norm"] == draft["source_norm"],
          "and the key her domain computed survives the seal")
    say("And the row she sealed is the row she was reading:")
    say(f"   draft  id {draft['id'][:8]}…  key {draft['source_norm']!r}")
    say(f"   sealed id {sealed['id'][:8]}…  key {sealed['source_norm']!r}")
    note("add_pair recomputes the key from source_text — with HER matcher, because")
    note("ui.App now carries one. It used to carry only the two domain tags, and")
    note("this beat is where that cost her the verification (§6.40, closed).")

    # ---------------------------------------------------------------- 3
    beat(3, "The next morning, the same event, and her verification holds")
    say(f"{DIM}ward sister{OFF} {RESTATED}")
    say(f"Her matcher keys that to {BOLD}{SERIALS.normalize(RESTATED)!r}{OFF} — "
        f"the same incident.")
    again = memory.best_sealed(RESTATED, INCIDENT, INCIDENT, store=store_a,
                               matcher=SERIALS)
    claim(again is not None,
          "a seal made through the UI is reachable to the domain that made the draft")
    say(f"Nestor: {GREEN}verified{OFF} — {again['pair']['verifier']!r}, "
        f"{again['similarity']:.3f}.")
    exact = memory.best_sealed(REPORT, INCIDENT, INCIDENT, store=store_a,
                               matcher=SERIALS)
    claim(exact is not None,
          "and so does the exact wording she sealed")
    say(f"And the exact sentence she sealed, {BOLD}word for word{OFF}, likewise.")
    say()
    say("What is actually in her store:")
    show_rows(store_a, INCIDENT)
    still = [r for r in rows(store_a, INCIDENT) if r["status"] == "draft"]
    claim(not still, "the draft she sealed is retired, not still queued")
    note("One row for one incident. This is the beat that used to show two: a")
    note("signed seal under a key her domain never computed, and the draft she")
    note("thought she had retired, still sitting in her queue.")

    # ---------------------------------------------------------------- 4
    beat(4, "She says no, durably, and it stops being served")
    memory.add_pair(REPORT, ADJUDICATION, INCIDENT, INCIDENT, status="sealed",
                    verifier=INES, origin=ORIGIN, store=store_a, matcher=SERIALS,
                    reason="Sealed through the library so there is something to refuse.")
    before = memory.best_sealed(WRONG_FOR, INCIDENT, INCIDENT, store=store_a,
                                matcher=SERIALS)
    claim(before is not None,
          "the occlusion report matches the free-flow adjudication on serial alone")
    say(f"{DIM}query {OFF}{WRONG_FOR}")
    say(f"Nestor serves the free-flow adjudication — same serial, {BOLD}wrong "
        f"event{OFF}.")
    note("Her matcher keys on the serial, so this is the near miss it was always")
    note("going to have. Rejection is the mechanism for exactly this.")

    status, said_no = ui.dispatch(
        app_a, "POST", "/api/reject-match", {},
        {"source": WRONG_FOR, "target_text": ADJUDICATION, "verifier": INES,
         "reason": "Occlusion is not free-flow. Do not serve this for that."})
    claim(status == 200, "the UI records the rejection")
    stored_key = said_no["rejection"]["query_norm"]
    say(f"HTTP {GREEN}{status}{OFF}. Recorded, signed, in the chain.")
    say(f"   filed under {stored_key[:46]!r}")
    say(f"   her domain asks under {SERIALS.normalize(WRONG_FOR)!r}")

    after = memory.best_sealed(WRONG_FOR, INCIDENT, INCIDENT, store=store_a,
                               matcher=SERIALS)
    claim(after is None,
          "a rejection recorded through the UI suppresses the match in a custom domain")
    say(f"Ask again: {GREEN}not served{OFF}.")
    mine = memory.rejected_ids(SERIALS.normalize(WRONG_FOR), INCIDENT, INCIDENT,
                               store_a)
    claim(mine != (set(), set()),
          "the recorded no is filed under the key her domain actually asks with")
    claim(stored_key == SERIALS.normalize(WRONG_FOR),
          "and reject_match keyed the query with her matcher, not the default")
    note(f"rejected_ids under her key: {len(mine[1])} target — the one she refused.")
    note("This is the promise the README leads with, and the beat where it used to")
    note("be void: the 'no' was real, signed, and filed where nobody asks.")

    # ---------------------------------------------------------------- 5
    beat(5, "The desk next door reviews the tool, and its seals work")
    store_b, app_b, root_b = desk_b(work)
    say("Ruaridh has two days a month and recipes/patch_review.py. Same package,")
    say("same surface, same seal-draft call — and a matcher of his own.")
    known = ("locks_in_text is a raw substring, so a short lock fires inside "
             "longer words")
    fix = "Wrap each term in a word-boundary regex before searching."
    prop = patch_review.propose(known, fix, reason="§6.38, open.", origin=ORIGIN,
                                store=store_b)
    status, body_b = ui.dispatch(app_b, "POST", "/api/seal-draft", {},
                                 {"pair_id": prop["id"], "verifier": RUARIDH,
                                  "reason": "Read it against the apetito case."})
    claim(status == 200, "the UI accepts his seal too")
    served = patch_review.fix_for(known, store=store_b)
    claim(served is not None,
          "the review desk CAN serve the fix a human just sealed")
    say(f"HTTP {GREEN}{status}{OFF}, and asking again returns it: "
        f"{GREEN}verified{OFF}, {served['similarity']:.3f}, by "
        f"{served['pair']['verifier']!r}.")
    say(f"   his draft key  {prop['source_norm'][:46]!r}")
    say(f"   his sealed key {body_b['pair']['source_norm'][:46]!r}")
    claim(prop["source_norm"] == body_b["pair"]["source_norm"],
          "the review desk's key is preserved too, for the same reason hers is")
    note("His row used to be re-keyed exactly like hers. The difference was that")
    note("his desk survived it, and beat 6 is why — which is the more interesting")
    note("half, because it is what kept the defect out of sight.")

    # ---------------------------------------------------------------- 6
    beat(6, "Why his desk survived it, which is why nobody found this sooner")
    say("DefectMatcher implements score(raw_a, raw_b). SerialMatcher does not.")
    say("best_sealed prefers score() when it is there, compares the raw texts,")
    say(f"and {BOLD}never consults the key at all{OFF} — so a wrong key cost him "
        f"nothing.")
    claim(hasattr(patch_review.MATCHER, "score"), "DefectMatcher offers score()")
    claim(not hasattr(SERIALS, "score"), "SerialMatcher offers only the two methods")
    claim(memory.uses_raw_score(patch_review.MATCHER)
          and not memory.uses_raw_score(SERIALS),
          "the two desks still differ on the optional third method")
    say()
    say("The seam, as the README documents it, is two methods. score() is the")
    say(f"{BOLD}optional{OFF} third. Ines implemented the documented seam and lost")
    say("her seals; Ruaridh implemented one method more and never noticed.")
    say()
    say(f"§6.41 asked which to change: make score() mandatory, or {BOLD}stop "
        f"re-keying{OFF}.")
    say("It did not pick. §6.40's fix picks: the UI keys with the domain's own")
    say("matcher, so the two methods the README promises are enough again, and")
    say("score() goes back to being what it says it is — an optimisation.")
    note("Worth keeping the beat even though the gap closed: a defect that only")
    note("bites the people who implemented exactly what was documented, and spares")
    note("the ones who did more, is a defect that stays invisible to its author.")

    # ---------------------------------------------------------------- 7
    beat(7, "Two desks, one process, and each keyed by its own matcher")
    say("The old rescue was memory.set_matcher() — a module global, so one process")
    say("could hold her matcher or his, never both. Two custom-matcher desks were")
    say("therefore two deployments, which is a sentence nobody had had to write.")
    say()
    say("The per-App matcher is what makes them one process again. Both desks are")
    say(f"live right now, in {BOLD}this{OFF} interpreter, and the global is still "
        f"the default:")
    installed = memory.get_matcher()
    claim(installed is not SERIALS and installed is not patch_review.MATCHER,
          "neither desk had to install its matcher process-wide")
    say(f"   process-wide matcher: {type(installed).__name__} — neither desk's")
    say(f"   her surface keys with {type(app_a.matcher).__name__}")
    say(f"   his surface keys with {type(app_b.matcher).__name__}")

    say()
    say("He writes up the bug she hit — quoting her serial, as anybody would:")
    at_desk(root_b)
    HIS_DEFECT = ("reject_match records query_norm with the default matcher, so "
                  "the CH4471 rejection never suppresses anything")
    d_prop = patch_review.propose(
        HIS_DEFECT, "Thread the caller's matcher through reject_match.",
        reason="Proposed by the fixture, for a human.", origin=ORIGIN, store=store_b)
    status, d_sealed = ui.dispatch(app_b, "POST", "/api/seal-draft", {},
                                   {"pair_id": d_prop["id"], "verifier": RUARIDH})
    stored = d_sealed["pair"]["source_norm"]
    say(f"{DIM}defect {OFF}{HIS_DEFECT[:60]}…")
    say(f"   his domain asks under  {patch_review.MATCHER.normalize(HIS_DEFECT)[:44]!r}")
    say(f"   it was stored under    {BOLD}{stored[:44]!r}{OFF}")
    claim(stored == patch_review.MATCHER.normalize(HIS_DEFECT),
          "his defect is filed by HIS matcher even though it names her device serial")
    claim(stored != SERIALS.normalize(HIS_DEFECT),
          "and not under the serial, which is what the global would have done")
    say(f"Filed as a defect, {BOLD}not{OFF} as a device serial. The text contains "
        f"both;")
    note("which one it *means* is the matcher's question, and each desk now gets")
    note("to answer it for itself. The global still works and is still there for a")
    note("host running one domain — it is no longer the only way, or a ceiling.")

    say()
    say("The global rescue, still measured rather than assumed:")
    at_desk(root_a)
    was_installed = memory.get_matcher()   # put back at the end of this beat
    memory.set_matcher(SERIALS)
    plain = ui.App(store=store_a, source_lang=INCIDENT, target_lang=INCIDENT,
                   db_path=str(root_a / "nestor.db"))
    probe = memory.add_pair("Pump SN CH-9002 stalled mid-infusion.",
                            "Motor stall, batch CH-9002, returned to Sheffield.",
                            INCIDENT, INCIDENT, status="draft", origin=ORIGIN,
                            store=store_a, matcher=SERIALS)
    status, fixed = ui.dispatch(plain, "POST", "/api/seal-draft", {},
                                {"pair_id": probe["id"], "verifier": INES})
    claim(fixed["pair"]["id"] == probe["id"],
          "an App with no matcher of its own still defers to the process-wide one")
    claim(fixed["pair"]["source_norm"] == probe["source_norm"],
          "and the key survives that seal too")
    say(f"   same row upgraded: {GREEN}yes{OFF}   key kept: "
        f"{fixed['pair']['source_norm']!r}")
    memory.set_matcher(was_installed)
    note("App.matcher=None means 'defer', not 'use StringMatcher' — so a host that")
    note("installed one globally before launching the surface keeps what it set.")

    # ---------------------------------------------------------------- 8
    beat(8, "What the notified body asked for, and what the chains can show")
    at_desk(root_a)
    a_entries, b_entries = len(_ledger_lines(root_a)), len(_ledger_lines(root_b))
    claim(a_entries > 0 and b_entries > 0, "each desk kept its own chain")
    say(f"Her chain holds {a_entries} entries, his {b_entries}, and they are "
        f"separate files.")
    say("Every entry in hers verifies. It records what she sealed and what she")
    say("rejected, and now the serving path agrees with it.")
    note("The chain was intact all along — that is the part worth remembering. What")
    note("was broken was the serving path it described, and a hash chain cannot")
    note("catch that: nothing had been tampered with. The record was true and the")
    note("answer was missing, which is the one failure mode this product's own")
    note("integrity guarantee is blind to by construction.")

    # ---------------------------------------------------------------- 9
    beat(9, "What this fixture is for")
    say("It is the first thing pointed at the Matcher seam from the human surface")
    say("rather than from the library, and the seam is the package's whole")
    say("extension story. Two desks because one would have hidden it: on")
    say("Ruaridh's alone the bug was invisible, and on Ines's alone it read as")
    say("her mistake.")
    say()
    say(f"It now runs {BOLD}green{OFF}, and that is the point of keeping it. The")
    say("beats did not change; the outcomes did. Every claim above is the same")
    say("question this fixture asked when the answer was no.")
    say()
    at_desk(root_b)
    say(f"The verification goes into his queue the only way this script may put it "
        f"there — {BOLD}as a draft{OFF}:")
    queued = patch_review.propose(
        "nestor ui could be aimed at a custom domain and could not be told its "
        "matcher, so seal-draft and reject-match re-keyed with StringMatcher",
        "Fixed: ui.App carries a matcher and a --matcher flag, threaded through "
        "every add_pair, reject_match and cascade call the UI makes.",
        reason="Found and closed via demo/two_desks.py. IDEAS §6.40. This fixture "
               "re-measures it on every run; a human still confirms.",
        origin=ORIGIN, store=store_b)
    claim(queued["status"] == "draft",
          "the fixture proposes the finding and does not seal it")
    say(f"   {AMBER}~{OFF} {queued['status']}  awaiting {RUARIDH}")
    note("A machine may propose. Only a human confirms. That is the covenant, and")
    note("it applies to the machine that found the defect in the covenant's own")
    note("surface.")

    if args.keep:
        print(f"\n   {DIM}kept: {work}{OFF}")
    else:
        shutil.rmtree(work, ignore_errors=True)

    if _FAILURES:
        print(f"\n{RED}{len(_FAILURES)} claim(s) no longer hold:{OFF}")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print(f"\n{GREEN}Every claim above held.{OFF}\n")
    return 0


def _ledger_lines(root: pathlib.Path) -> list:
    path = root / "ledger.jsonl"
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
