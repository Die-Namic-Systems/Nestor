#!/usr/bin/env python3
"""Run Nestor against jeles' rules — the other repo in the box, auditing back.

    python scripts/audit_against_jeles.py --repo /path/to/jeles

`scripts/audit_against_constitution.py` holds this package to willow-2.0's five
clauses. Those are *constitutional* — prose about what must not happen. jeles is
the harder auditor, because its rules are **working mechanisms with escalations
demonstrated behind them**. `conflict_scan.py` carries a comment recording a
hand-built proposal that claimed ``verification_kind="human"`` and was *given*
it. The allowlist exists because that happened, not because somebody worried it
might.

So the question here is not "does this package agree with jeles". It is: **jeles
closed a hole it had proved it had. Does this package have the same hole, and if
not, is it closed for a reason or by luck?**

**Rules are read from the checkout, never paraphrased.** Same discipline and the
same reason as the constitution audit: a summary of somebody else's rule,
written by the party being audited, is the least trustworthy sentence available.
Constants come out by :mod:`ast`, including a function's *default argument*,
which is where one of jeles' own rungs turns out to live.

**Verdicts**

    satisfied      a probe ran and this package behaved as jeles' rule requires
    differently    the rule's end holds by a mechanism that is not jeles' —
                   stated, not scored
    not applicable the rule governs a thing this package does not have
    FAILS          a probe ran and this package did not hold

**Nothing here seals anything**, and nothing here writes to jeles. The verdicts
are this script's readings, and a reading by the audited party is a draft.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

os.environ.setdefault("NESTOR_SEAL_KEY", "audit-fixture-key-not-a-secret")

from nestor import keyring                                               # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
BOLD, DIM, GREEN, AMBER, RED, CYAN, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[0m")

SATISFIED, DIFFERENTLY, NA, FAILS = "satisfied", "differently", "not applicable", "FAILS"


# --------------------------------------------------------------------------
# reading jeles — ast only, no import, no execution
# --------------------------------------------------------------------------

def _module_constant(path: pathlib.Path, name: str):
    """A module-level assignment's literal value, or ``None``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        if name in targets and node.value is not None:
            try:
                return ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError):
                # frozenset({...}) and dict-of-frozenset are calls, not literals.
                return _literal_ish(node.value)
    return None


def _literal_ish(node: ast.AST):
    """``frozenset({...})`` and dicts containing them — one level of unwrapping.

    ``ast.literal_eval`` refuses a Call, and jeles writes its allow-lists as
    ``frozenset({...})``. Unwrapping exactly that one call by name keeps the
    no-execution rule intact: nothing is evaluated, a known constructor is
    recognised and its literal argument read.
    """
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ("frozenset", "set") and node.args:
        try:
            return set(ast.literal_eval(node.args[0]))
        except (ValueError, SyntaxError, TypeError):
            return None
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            try:
                key = ast.literal_eval(k)
            except (ValueError, SyntaxError, TypeError):
                return None
            out[key] = _literal_ish(v)
        return out
    return None


def _default_arg(path: pathlib.Path, func: str, arg: str):
    """The default value of one argument of one function, by parsing.

    Worth a helper of its own: `corpus.put_nugget`'s verification rung is a
    *default argument*, not a constant, so a reader grepping for the rules would
    not find it and a reader grepping for constants would conclude it had none.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != func:
            continue
        spec = node.args
        # posonlyargs is a SEPARATE list from args, and `defaults` spans both.
        # Reading only `spec.args` mis-aligns every default by the number of
        # positional-only parameters, so a function using `/` would report a
        # neighbour's default as this argument's — silently, and about somebody
        # else's repository. jeles' put_nugget has no posonly args, which is
        # exactly why this would not have shown up in the run that mattered.
        names = [a.arg for a in (*spec.posonlyargs, *spec.args)]
        # Positional defaults align to the END of the positional list.
        for got, value in zip(names[len(names) - len(spec.defaults):], spec.defaults):
            if got == arg:
                try:
                    return ast.literal_eval(value)
                except (ValueError, SyntaxError, TypeError):
                    return None
        for got, value in zip([a.arg for a in spec.kwonlyargs], spec.kw_defaults):
            if got == arg and value is not None:
                try:
                    return ast.literal_eval(value)
                except (ValueError, SyntaxError, TypeError):
                    return None
    return None


def read_rules(repo: pathlib.Path) -> dict | None:
    """jeles' rules, as jeles states them. ``None`` if they cannot be read."""
    indep = repo / "jeles" / "_independence.py"
    scan = repo / "jeles" / "reactions" / "conflict_scan.py"
    corpus = repo / "jeles" / "corpus.py"
    if not (indep.exists() and scan.exists() and corpus.exists()):
        return None
    rules = {
        "min_sources": _module_constant(indep, "MIN_INDEPENDENT_SOURCES"),
        "pinned_rung": _module_constant(scan, "PROPOSAL_VERIFICATION_KIND"),
        "non_witness": _module_constant(scan, "_NON_WITNESS"),
        "allowed_args": _module_constant(scan, "_ALLOWED_ARGS"),
        "put_nugget_rung": _default_arg(corpus, "put_nugget", "verification_kind"),
    }
    return rules if rules["min_sources"] and rules["pinned_rung"] else None


# --------------------------------------------------------------------------
# a store, and the probes — each returns (verdict, evidence)
# --------------------------------------------------------------------------

def _store(work: pathlib.Path):
    from nestor import cascade, storage
    from nestor.sqlite_store import SqliteStore
    work.mkdir(parents=True, exist_ok=True)
    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    s = SqliteStore(str(work / "n.db"))
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    return s


def probe_rung_at_the_gateway(work, rules) -> tuple[str, str]:
    """jeles: a proposal may not name its own place on the ladder.

    The escalation jeles demonstrated, aimed here: hand the tool surface a
    proposal carrying the arguments that would raise its rung, and see what
    lands.
    """
    from nestor import serve
    s = _store(work / "gateway")
    srv = serve.Server(store=s, client="audit")
    got = srv.call("nestor_propose", {
        "source_text": "a question the machine answered",
        "candidate": "the machine's answer",
        "status": "sealed", "verifier": "a-machine", "verified_by": "a-machine",
        "verification_kind": rules["put_nugget_rung"] or "human",
    })
    if got.get("state") != "draft" or got.get("verified"):
        return FAILS, (f"a proposal naming its own rung was accepted: "
                       f"state={got.get('state')!r} verified={got.get('verified')!r}")
    return SATISFIED, (
        f"state={got.get('state')!r}, verified={got.get('verified')!r}. jeles vets "
        f"proposals against an allow-list of {sum(len(v or ()) for v in (rules['allowed_args'] or {}).values())} "
        f"argument(s) and pins the rung to {rules['pinned_rung']!r}. This closes it "
        f"one step earlier — answer.propose has no status parameter to pass, and "
        f"serve.call forwards named arguments rather than splatting the dict, so "
        f"there is nothing to vet.")


def probe_refusal_is_named(work, rules) -> tuple[str, str]:
    """jeles: a refused argument produces a receipt naming it, not a silent drop."""
    from nestor import serve
    s = _store(work / "receipt")
    srv = serve.Server(store=s, client="audit")
    smuggled = ["status", "verifier", "verification_kind"]
    got = srv.call("nestor_propose", {
        "source_text": "a question", "candidate": "an answer",
        **{k: "sealed" for k in smuggled},
    })
    blob = json.dumps(got, default=str).lower()
    named = [k for k in smuggled if k in blob]
    if named:
        return SATISFIED, f"the reply names what it refused: {', '.join(named)}"
    return DIFFERENTLY, (
        f"{len(smuggled)} forbidden argument(s) were discarded and the reply says "
        f"so nowhere: {json.dumps(got, default=str)[:96]}… The escalation FAILS, "
        f"which is the part that matters, and the caller is told it succeeded. "
        f"jeles chose the other way on this exact point — an error receipt naming "
        f"what was refused, explicitly 'not silently dropped'. Same asymmetry the "
        f"countersignature fix closed: somebody asked for something, did not get "
        f"it, and was handed an unqualified success.")


#: Run inside a fresh interpreter: `keyring.set_keyring` is process-wide, so
#: asking "what happens with a keyring" and "what happens without one" in one
#: process makes the second answer depend on the first.
_WITNESS_PROBE = """
import os, sys, pathlib, tempfile
sys.path.insert(0, {root!r})
os.environ['NESTOR_SEAL_KEY'] = 'audit-fixture-key-not-a-secret'
w = pathlib.Path(tempfile.mkdtemp())
from nestor import cascade, storage, memory, keyring
from nestor.sqlite_store import SqliteStore
cascade.set_ledger_path(str(w / 'l.jsonl'))
s = SqliteStore(str(w / 'n.db')); s.init_db(); s.memory_init(); storage.set_store(s)
if {with_keyring!r}:
    ring = keyring.Keyring(); ring.add('rita'); keyring.set_keyring(ring)
try:
    row = memory.add_pair('q', 'a', 'd', 't', status='sealed', verifier='',
                          origin='audit', store=s)
    print('SERVED' if memory.is_verified_seal(row) else 'STORED-UNVERIFIABLE')
except Exception as exc:
    print('REFUSED:' + type(exc).__name__)
"""


def probe_who_may_witness(work, rules) -> tuple[str, str]:
    """jeles: an enumerated set of parties that can never witness.

    **The first version of this probe returned FAILS, and was wrong.** It sealed
    with ``verifier=""`` under a single ``NESTOR_SEAL_KEY``, saw it verify, and
    reported that an anonymous seal is served — against a package whose subject
    is who checked what. What it had actually measured was the weakest of the two
    signing configurations, chosen by accident because that is what the script
    happened to set at import. Under a keyring the same call is *refused before
    the store is touched*. So the honest answer is a pair of answers, and this
    runs both. Second time in one day a probe here produced a FAIL that belonged
    to the probe — CLAUDE.md: reproduce the condition you name.
    """
    import subprocess
    out = {}
    for label, flag in (("single-key", False), ("keyring", True)):
        done = subprocess.run(
            [sys.executable, "-c", _WITNESS_PROBE.format(root=str(REPO), with_keyring=flag)],
            capture_output=True, text=True, timeout=180)
        out[label] = (done.stdout.strip().splitlines() or ["(no output)"])[-1]
    n = len(rules["non_witness"] or ())
    if out["keyring"].startswith("REFUSED"):
        return DIFFERENTLY, (
            f"single shared key: anonymous seal {out['single-key']}. keyring: "
            f"{out['keyring']}. jeles names {n} parties that can never witness — the "
            f"search engine itself, and shorteners — and the list is always in force. "
            f"Here it is not a list and not always in force: with per-verifier keys, "
            f"an unknown witness is refused before the write and the empty string is "
            f"rendered '(empty)' in the message, so somebody had already thought about "
            f"this exact case. Without a keyring there is no witness identity at all "
            f"and the empty verifier seals. A blocklist asks 'who is known to be "
            f"untrustworthy'; key custody asks 'who is known'. The second is stronger "
            f"and it is off by default.")
    return FAILS, (f"an unnamed verifier is accepted in both configurations: "
                   f"single-key {out['single-key']}, keyring {out['keyring']}")


def probe_independence(work, rules) -> tuple[str, str]:
    """jeles: a finding needs >= MIN_INDEPENDENT_SOURCES distinct sources."""
    from nestor import memory
    s = _store(work / "independence")
    row = memory.add_pair("a claim", "an answer", "audit", "audit", status="sealed",
                          verifier="one-person", origin="audit", store=s)
    served = memory.is_verified_seal(row)
    bar = rules["min_sources"]
    if not served:
        return SATISFIED, "a single-verifier seal does not verify"
    return DIFFERENTLY, (
        f"jeles requires {bar} distinct sources; a seal here requires 1 and serves "
        f"on it. The two are not the same currency: jeles counts {bar} unsigned "
        f"citations, this counts one signed attestation naming a person. "
        f"docs/seal-staleness-and-quorum.md §4 is the open design for N-of-M and "
        f"says sub-quorum must be a draft rather than a weaker seal. jeles is also "
        f"careful that its own bar is 'a cheap heuristic' — two domains can be one "
        f"actor who bought both — and there is no registrable_domain() for people.")


def probe_default_rung(work, rules) -> tuple[str, str]:
    """The reciprocal: which way does each package's *default* fall?"""
    from nestor import memory
    s = _store(work / "default")
    row = memory.add_pair("a claim", "an answer", "audit", "audit",
                          origin="audit", store=s)
    theirs = rules["put_nugget_rung"]
    if row["status"] != "draft":
        return FAILS, f"add_pair defaults to status={row['status']!r}"
    return SATISFIED, (
        f"add_pair defaults to status='draft'; corpus.put_nugget defaults to "
        f"verification_kind={theirs!r}. The defaults fall opposite ways: a caller "
        f"here who says nothing proposes, a caller there who says nothing asserts a "
        f"human checked it. jeles guards that at the gateway and this does not need "
        f"to. Recorded because an audit that only reports where the audited party "
        f"is weaker is not an audit, it is a posture.")


PROBES = (
    ("JELES-RUNG", "a proposal may not name its own place on the ladder",
     probe_rung_at_the_gateway),
    ("JELES-RECEIPT", "a refused argument is named, not silently dropped",
     probe_refusal_is_named),
    ("JELES-WITNESS", "some parties can never witness, whatever they return",
     probe_who_may_witness),
    ("JELES-INDEPENDENCE", "a finding needs N distinct sources behind it",
     probe_independence),
    ("JELES-DEFAULT", "which way the unspecified rung falls", probe_default_rung),
)


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="a jeles checkout")
    args = ap.parse_args()

    rules = read_rules(pathlib.Path(args.repo))
    if rules is None:
        print(f"{RED}could not read jeles' rules under {args.repo}{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting a "
              f"clean audit.{OFF}")
        return 1

    print(f"\n{BOLD}nestor, audited against jeles' working rules{OFF}")
    print(f"{DIM}   bar={rules['min_sources']}  pinned rung={rules['pinned_rung']!r}  "
          f"put_nugget default={rules['put_nugget_rung']!r}  "
          f"non-witness={len(rules['non_witness'] or ())}{OFF}")
    print(f"{DIM}   Rules read from the checkout. Verdicts are mine, and a verdict "
          f"by the audited party is a draft.{OFF}")

    work = pathlib.Path(tempfile.mkdtemp(prefix="nestor-jeles-audit-"))
    colour = {SATISFIED: GREEN, DIFFERENTLY: CYAN, NA: DIM, FAILS: RED}
    results = []
    # Same isolation as the constitution audit, and for the same reason: these
    # probes seal under synthetic verifiers ("one-person", "audit") that are
    # deliberately not in anybody's real keyring. Without it, a real
    # NESTOR_KEYRING export turns UnknownVerifierError into a false FAILS —
    # measured for JELES-INDEPENDENCE specifically (IDEAS §6.98's "second false
    # verdict"), published and left uncorrected across several rounds because
    # the probe's own exception handler made it look like an ordinary result.
    with keyring.isolated():
        for trace, states, probe in PROBES:
            try:
                verdict, evidence = probe(work, rules)
            except Exception as exc:        # a probe that dies proves nothing
                verdict, evidence = FAILS, f"the probe itself raised {type(exc).__name__}: {exc}"
            results.append((trace, verdict, evidence))
            print(f"\n{BOLD}{trace}{OFF}  {colour[verdict]}{verdict}{OFF}")
            print(f"   {DIM}jeles{OFF} {states}")
            for line in _wrap(evidence, 84):
                print(f"   {line}")

    print(f"\n{BOLD}verdict{OFF}")
    for trace, verdict, _ in results:
        print(f"   {colour[verdict]}{verdict:15}{OFF} {trace}")
    counts = {v: sum(1 for _, x, _ in results if x == v) for v in colour}
    print(f"\n   {counts[SATISFIED]} satisfied · {counts[DIFFERENTLY]} differently "
          f"· {counts[NA]} not applicable · {counts[FAILS]} failing")
    print(f"\n   {DIM}jeles closed its rung hole after demonstrating it had one. "
          f"The interesting{OFF}")
    print(f"   {DIM}result is not agreement — it is which of the two roads each "
          f"package took, and{OFF}")
    print(f"   {DIM}whether either would survive the other's escalation.{OFF}")

    shutil.rmtree(work, ignore_errors=True)
    print()
    return 1 if counts[FAILS] else 0


if __name__ == "__main__":
    raise SystemExit(main())
