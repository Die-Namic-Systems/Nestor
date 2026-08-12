"""``nestor`` — the terminal surface.

Until now the only ways in were writing Python and, since the UI, a browser.
Neither fits a cron job, a CI check, a Makefile or a shell pipeline, and all
four are where "is the ledger still intact?" and "export the memory before the
migration" actually get asked.

Subcommands mirror the surfaces rather than inventing a new vocabulary::

    nestor ask "Good evening."            # the cascade — sealed / draft / pending
    nestor resolve AMZN --domain company  # the entity graph
    nestor check ceiling '$1,030,000' --domain contract
    nestor export --out memory.json       # a portable, re-importable bundle
    nestor db checkpoint                  # flush WAL into the main file (§6.7)
    nestor db checkpoint --out copy.db    # db + copy.ledger.jsonl (use --no-ledger to omit chain)
    nestor import memory.json             # DRY RUN by default; --apply commits
    nestor ledger verify                  # exit 1 on a broken chain, for CI
    nestor decision check "may X?"        # exit 1 on a recorded rejection or
                                           # contradicts edge, for CI (docs/decision-memory.md N9)
    nestor stats
    nestor calibrate --from en --to es    # where the threshold belongs for this corpus
    nestor rejections                     # what the recorded "no"s say in aggregate
    nestor keys add rita                  # a key per verifier (list / add / revoke)
    nestor ui                             # the browser surface
    nestor serve                          # MCP over stdio, for a model

Two conventions worth stating. **Exit codes mean something**: 0 is the good
answer, 1 is the bad one (an unverified answer, a broken chain, an import with
conflicts), 2 is a usage error — so `nestor ledger verify` is a CI gate and
`nestor ask` is usable in a shell conditional. And **import is a dry run until
you say otherwise**, like every other decision here that changes what will be
served as verified.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
from typing import Optional

from . import (answer, cascade, keyring as keyring_mod, ledger as ledger_mod, memory,
               portable, serve, signing, storage, ui)
from .sqlite_store import SqliteStore

EXIT_OK, EXIT_ANSWER_IS_NO, EXIT_USAGE = 0, 1, 2

#: Shared by every subcommand that keys a query, so the sentence a user reads is
#: the same one wherever they meet it. A shipped name, or `module:attribute` for
#: a domain's own — see `answer.load_matcher`, and IDEAS §6.41 for why a name
#: alone was not enough.
_MATCHER_HELP = ("the matcher that keys this domain: a shipped name "
                 "(string, numeric, semantic, ollama) or a custom one as "
                 "'module:attribute', e.g. 'acme.incidents:SERIALS'")


def _store(args) -> SqliteStore:
    if getattr(args, "ledger", ""):
        cascade.set_ledger_path(args.ledger)
    store = SqliteStore(args.db)
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return store


def _emit(payload, as_json: bool, human: str = "") -> None:
    if as_json or not human:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(human)


# --------------------------------------------------------------------------
# asking
# --------------------------------------------------------------------------

def cmd_ask(args) -> int:
    result = answer.ask(_store(args), args.text, args.source_lang, args.target_lang,
                        engine_name=args.engine,
                        matcher=answer.load_matcher(args.matcher))
    p = result["passage"]
    verifier = (p.get("meta") or {}).get("verifier", "")
    _emit(result, args.json,
          f"{p['mark']} {p['state']}  {p['target'] or '—'}"
          + (f"   (verified by {verifier}, similarity {p['confidence']})" if verifier else ""))
    return EXIT_OK if result["verified"] else EXIT_ANSWER_IS_NO


def cmd_resolve(args) -> int:
    result = answer.resolve(_store(args), args.surface, args.domain)
    suggestion = (result.get("provenance") or {}).get("suggestion")
    human = (f"✓ sealed  {result['canonical']}   "
             f"(confidence {result['confidence']}, by "
             f"{(result.get('provenance') or {}).get('verifier', '—')})"
             if result["sealed"] else
             f"~ unsealed suggestion: {suggestion or '—'}   "
             f"(confidence {result['confidence']} — nothing verified matched)")
    _emit(result, args.json, human)
    return EXIT_OK if result["verified"] else EXIT_ANSWER_IS_NO


def cmd_check(args) -> int:
    result = answer.check(_store(args), args.label, args.observed, domain=args.domain,
                          abs_tol=args.abs_tol, pct_tol=args.pct_tol)
    if result["baseline"] is None:
        human = f"! no sealed baseline for {args.label!r} — nothing to check against"
    elif result["observed"] is None:
        # A figure the matcher could not read is not a variation of zero; it is
        # not a figure. Saying so beats crashing on the format string, and beats
        # printing a number nobody typed.
        human = (f"✗ flagged   no number could be read from {args.observed!r} — "
                 f"the baseline stands at {result['baseline']:,}")
    else:
        mark = "✓ within tolerance" if result["within_tolerance"] else "✗ flagged"
        pct = ("" if result["variation_pct"] is None
               else f" ({result['variation_pct'] * 100:.2f}%)")
        human = (f"{mark}   baseline {result['baseline']:,}  observed "
                 f"{result['observed']:,}  variation {result['variation']:,}{pct}")
        if result["ambiguous"]:
            human += f"\n  ! {result['baseline_count']} baselines stand for this label"
    _emit(result, args.json, human)
    return EXIT_OK if result.get("within_tolerance") else EXIT_ANSWER_IS_NO


def cmd_match(args) -> int:
    # A bare shipped name goes through as the NAME, not as an object. Two
    # reasons, one of them a regression this originally shipped: `answer.match`
    # reports `matcher` back verbatim on the name path and as the class name on
    # the object path, so `--matcher numeric --json` changed from "numeric" to
    # "NumericMatcher" — a machine-readable field, altered in a release billed as
    # a pure addition. And tolerances are only applied where a name can be
    # rebuilt with them. An import spec has neither property and must be loaded.
    chosen = args.matcher
    if ":" in args.matcher:
        chosen = answer.load_matcher(args.matcher, abs_tol=args.abs_tol,
                                     pct_tol=args.pct_tol)
    result = answer.match(_store(args), args.text, args.source_lang, args.target_lang,
                          matcher=chosen,
                          abs_tol=args.abs_tol, pct_tol=args.pct_tol)
    _emit(result, args.json,
          (f"✓ would be served  {result['target']}   (by {result['verifier']}, "
           f"similarity {result['confidence']})" if result["served"]
           else f"! would not be served — {result['reason']}\n"
                f"  normalized to {result['normalized']!r}"))
    return EXIT_OK if result["served"] else EXIT_ANSWER_IS_NO


def cmd_decision(args) -> int:
    """``nestor decision check`` — a CI gate over the decision graph
    (docs/decision-memory.md N9(1)).

    Mirrors ``nestor ledger verify``'s exit-code contract exactly: 0 means the
    question is clear to propose against, 1 means something already committed
    blocks it, 2 is a usage error. This is the one point in the whole document
    that fires without anyone choosing to consult anything — it is meant to
    sit in a required CI check, not to be run by hand.
    """
    if args.decision_command != "check":
        return EXIT_USAGE
    question = args.question
    if not question or not question.strip():
        print("a question is required: nestor decision check \"<question>\"",
              file=sys.stderr)
        return EXIT_USAGE
    if args.source_lang != args.target_lang:
        # DecisionMemory has exactly one domain, ridden in both language tags
        # (N8, the same trick EntityResolver uses) — there is no such thing as
        # a decision graph with a different --from and --to, so accepting one
        # silently would mean the check ran against a domain the caller never
        # meant to ask about.
        print(f"--from and --to must match for a decision domain (got "
              f"{args.source_lang!r} and {args.target_lang!r}) — a decision's "
              f"domain rides in both tags identically, docs/decision-memory.md N8",
              file=sys.stderr)
        return EXIT_USAGE
    store = _store(args)
    from .decision import DecisionMemory
    dm = DecisionMemory(store, domain=args.source_lang)
    result = dm.constraints_on(question)
    contradicts = [c for c in result["constraints"] if c["kind"] == "contradicts"]
    blocked = bool(result["rejected"]) or bool(contradicts)
    payload = {"question": question, "domain": args.source_lang, "blocked": blocked,
              "rejected": result["rejected"], "contradicts": contradicts,
              "live": result["live"]}
    if args.json:
        _emit(payload, True)
    else:
        if not blocked:
            print(f"✓ clear — no recorded rejection or contradicts edge on {question!r}")
        else:
            print(f"✗ BLOCKED — {question!r} carries a recorded constraint:")
            for r in result["rejected"]:
                reason = r["reason"] or "(no reason recorded)"
                if r["reopen_when"]:
                    print(f"  rejected — {reason}\n"
                          f"    a condition to re-check: {r['reopen_when']}")
                else:
                    print(f"  rejected (permanent, no reopen_when) — {reason}")
            for c in contradicts:
                other = c["other_commitment"] or c["other_id"]
                why = f" — {c['edge_reason']}" if c["edge_reason"] else ""
                print(f"  contradicts {other!r}{why}   (sealed by {c['verifier']})")
    return EXIT_ANSWER_IS_NO if blocked else EXIT_OK


# --------------------------------------------------------------------------
# moving the memory
# --------------------------------------------------------------------------

def _ledger_sidecar_path(db_out: pathlib.Path) -> pathlib.Path:
    """Ledger copy beside a db backup — append, do not replace the last extension."""
    return db_out.with_name(db_out.name + ".ledger.jsonl")


def _replace_file(src: pathlib.Path, dest: pathlib.Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)


def cmd_db(args) -> int:
    store = _store(args)
    if not isinstance(store, SqliteStore):
        print("db commands require the SQLite store", file=sys.stderr)
        return EXIT_USAGE
    if args.db_command == "checkpoint":
        if args.out:
            out = pathlib.Path(args.out)
            ledger_out = _ledger_sidecar_path(out)
            ledger_src = cascade._ledger_path()
            copy_ledger = not args.no_ledger and ledger_src.is_file()
            # Both names are claimed whether or not this run writes the sidecar.
            # A chain left over from an earlier backup, sitting beside a freshly
            # written database, is a store paired with a trail that does not
            # describe it — and it is the store that is ahead, so the pair reads
            # as sealed rows whose entries are missing. That is the one thing the
            # sidecar exists to prevent, arriving by the back door.
            if not args.force:
                for path in (out, ledger_out):
                    if path.exists():
                        why = ("" if path == out or copy_ledger else
                               " — it would be left describing a different backup")
                        print(f"refusing to overwrite {path}{why} (pass --force)",
                              file=sys.stderr)
                        return EXIT_USAGE
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp_db = out.with_name(out.name + ".partial")
            tmp_db.unlink(missing_ok=True)
            try:
                store.backup_into(str(tmp_db))
                _replace_file(tmp_db, out)
            except Exception:
                tmp_db.unlink(missing_ok=True)
                raise
            parts = [str(out)]
            if copy_ledger:
                tmp_led = ledger_out.with_name(ledger_out.name + ".partial")
                tmp_led.unlink(missing_ok=True)
                try:
                    shutil.copy2(ledger_src, tmp_led)
                    _replace_file(tmp_led, ledger_out)
                except Exception:
                    tmp_led.unlink(missing_ok=True)
                    raise
                parts.append(str(ledger_out))
            else:
                if not args.no_ledger:
                    print(f"note: no ledger file at {ledger_src} to copy alongside the db",
                          file=sys.stderr)
                # Nothing was written here, so nothing may remain here.
                ledger_out.unlink(missing_ok=True)
            print(f"wrote {' and '.join(parts)}", file=sys.stderr)
        else:
            store.checkpoint_wal()
            print(f"checkpointed {args.db}", file=sys.stderr)
        return EXIT_OK
    return EXIT_USAGE


def cmd_export(args) -> int:
    bundle = portable.export_bundle(_store(args), source_lang=args.source_lang or "",
                                    target_lang=args.target_lang or "",
                                    include_ledger=not args.no_ledger,
                                    # The operator's assertion of the matcher that
                                    # keyed these rows: the store records no
                                    # per-domain matcher, so without this the
                                    # bundle would be labelled with the process
                                    # default and mislabel a custom domain. §6.92.
                                    matcher=answer.load_matcher(args.matcher))
    text = (portable.pairs_csv(bundle) if args.format == "csv"
            else json.dumps(bundle, indent=2, ensure_ascii=False, default=str))
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8")
        c = bundle["counts"]
        print(f"wrote {args.out} — {c['pairs']} pair(s), {c['sealed']} sealed "
              f"({c['servable']} servable), {c['rejections']} rejection(s), "
              f"digest {bundle['digest'][:16]}…", file=sys.stderr)
    else:
        print(text)
    return EXIT_OK


def cmd_import(args) -> int:
    store = _store(args)
    try:
        bundle = json.loads(pathlib.Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {args.file}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    ok, detail = portable.verify_bundle(bundle)
    if not ok:
        print(f"not a usable bundle: {detail}", file=sys.stderr)
        return EXIT_USAGE
    report = portable.import_bundle(bundle, store=store, dry_run=not args.apply,
                                    verifier=args.verifier,
                                    override_conflicts=args.override_conflicts,
                                    override_rejections=args.override_rejections,
                                    # The matcher this instance keys with, so a
                                    # bundle keyed by another is warned about
                                    # rather than landing rows dead. §6.92.
                                    matcher=answer.load_matcher(args.matcher))
    if args.json:
        _emit(report, True)
    else:
        head = "would import" if report["dry_run"] else "imported"
        print(f"{head}: {report['sealed']} sealed, {report['demoted']} demoted to draft "
              f"(signature does not verify here), {report['drafts']} draft, "
              f"{report['existing']} already present, {report['rejections']} rejection(s)")
        for c in report["conflicts"]:
            print(f"  conflict  {c['source_text']!r}: here {c['here']['target_text']!r} "
                  f"({c['here']['verifier'] or '—'}) vs incoming "
                  f"{c['incoming']['target_text']!r} ({c['incoming']['verifier'] or '—'})")
        for r in report["rejected_here"]:
            print(f"  REJECTED here by {r['rejected_by'] or 'a reviewer'}: "
                  f"{r['source_text']!r} — not imported "
                  f"(--override-rejections to revive it deliberately)")
        if report.get("matcher_mismatch"):
            print(f"  MATCHER: bundle keyed by {report['source_matcher']!r}, this "
                  f"instance keys by {report['dest_matcher']!r} — imported rows may "
                  f"key into a space this matcher never computes. Import under the "
                  f"bundle's matcher, or expect to re-key.")
        if report["dry_run"]:
            print("\nnothing was written — re-run with --apply to commit.", file=sys.stderr)
    unsettled = ((report["conflicts"] and not args.override_conflicts)
                 or (report["rejected_here"] and not args.override_rejections))
    return EXIT_ANSWER_IS_NO if unsettled else EXIT_OK


# --------------------------------------------------------------------------
# auditing
# --------------------------------------------------------------------------

def cmd_ledger(args) -> int:
    _store(args)
    if args.ledger_command == "head":
        # The tip, for pinning somewhere the ledger's writer cannot reach —
        # a CI variable, a monitoring check, the next run of this command.
        print(ledger_mod.head())
        return EXIT_OK
    if args.ledger_command == "verify":
        ok, detail = ledger_mod.verify(expected_head=args.expect_head or None)
        print(f"{'✓' if ok else '✗'} {detail}   ({cascade._ledger_path()})")
        if ok and not args.expect_head:
            print(f"  head {ledger_mod.head()}   (pin it with --expect-head; without "
                  f"it the newest entry is the one nothing vouches for)", file=sys.stderr)
        return EXIT_OK if ok else EXIT_ANSWER_IS_NO
    entries = ledger_mod.entries(kind=args.kind or None, limit=args.limit)
    if args.json:
        _emit(entries, True)
    else:
        for e in entries:
            rest = " ".join(f"{k}={v}" for k, v in e.items()
                            if k not in ("ts", "kind", "prev") and v not in ("", None))
            print(f"{e.get('ts', '')[:19].replace('T', ' ')}  {e.get('kind', '?'):<18} {rest}")
    # What the listing above could not include. Printed on stderr so it reaches
    # a person without changing what a script parses on stdout, and printed
    # whether or not --kind narrowed the listing: a line that will not parse has
    # no kind to be filtered by, so it is missing from every view of this file.
    torn = ledger_mod.unreadable()
    if torn:
        shown = ", ".join(str(t["line"]) for t in torn[:10])
        more = "" if len(torn) <= 10 else f", +{len(torn) - 10} more"
        print(f"  {len(torn)} line(s) in {cascade._ledger_path()} are not valid JSON, so "
              f"they are not listed above (line {shown}{more}). 'nestor ledger verify' "
              f"refuses on the first of them.", file=sys.stderr)
    return EXIT_OK


def cmd_calibrate(args) -> int:
    """Where the threshold should sit for this corpus. See :mod:`nestor.calibrate`."""
    from . import answer, calibrate as calibrate_mod
    # `load_matcher`, not `build_matcher`: `memory.py` tells a user to "measure
    # with `nestor calibrate --matcher …` on your corpus before trusting serves
    # at the shipped default", and this was the one --matcher flag in the package
    # that still could not name a custom matcher — so anyone who followed this
    # release's advice to ship one could not follow that advice to calibrate it.
    # None (the `string` default) means the shipped StringMatcher here: this is a
    # measurement of a named matcher, not a serve path that should defer.
    matcher = (answer.load_matcher(args.matcher, abs_tol=args.abs_tol,
                                   pct_tol=args.pct_tol)
               or answer.build_matcher("string"))
    result = calibrate_mod.calibrate(
        _store(args), source_lang=args.source_lang, target_lang=args.target_lang,
        target_rate=args.target, sample=args.sample, seed=args.seed, matcher=matcher)
    _emit(result, args.json, calibrate_mod.summarize(result))
    # A corpus no threshold in the sweep can make safe is the bad answer, and it
    # should be usable in a shell conditional like every other one here.
    return EXIT_OK if result["recommended"] is not None else EXIT_ANSWER_IS_NO


def cmd_keys(args) -> int:
    """Who can seal, and with what. See :mod:`nestor.keyring`."""
    path = args.keyring or keyring_mod.keyring_path()
    if not path:
        print("no keyring path: pass --keyring PATH or set NESTOR_KEYRING.\n"
              "Without one, every verifier signs with the single NESTOR_SEAL_KEY "
              "and a seal proves the key was present, not who was.", file=sys.stderr)
        return EXIT_USAGE

    if args.keys_command == "list":
        ring = keyring_mod.load(path)
        rows = [{"name": e.name, "status": ring.status(e.name),
                 "created_at": e.created_at, "revoked_at": e.revoked_at,
                 "reason": e.reason} for e in ring.entries()]
        human = [f"{len(rows)} verifier(s) in {path}"]
        for r in rows:
            note = f"  {r['reason']}" if r["reason"] else ""
            human.append(f"  {r['status']:<12} {r['name']}{note}")
        if ring.legacy_key:
            human.append("  legacy       (seals made before this keyring still verify)")
        _emit({"keyring": path, "verifiers": rows,
               "legacy_key": bool(ring.legacy_key)}, args.json, "\n".join(human))
        return EXIT_OK

    # add / revoke both write, so both start from whatever is there (or nothing).
    try:
        ring = keyring_mod.load(path)
    except keyring_mod.KeyringError:
        if args.keys_command != "add":
            raise
        ring = keyring_mod.Keyring(path=path)

    if args.keys_command == "add":
        if args.adopt_shared_key:
            shared = os.environ.get("NESTOR_SEAL_KEY", "")
            if not shared:
                print("--adopt-shared-key needs NESTOR_SEAL_KEY set: it is the key "
                      "your existing seals were signed with.", file=sys.stderr)
                return EXIT_USAGE
            ring.legacy_key = shared.encode()
        peer_key = bytes.fromhex(args.public) if args.public else None
        entry = ring.add(args.name, key=peer_key, rotate=args.rotate,
                         kind=args.key_type)
        ring.save(path)
        _emit({"keyring": path, "name": entry.name, "key": entry.key.hex(),
               "rotated": args.rotate},
              args.json,
              f"added {entry.name} to {path}\n"
              f"  key  {entry.key.hex()}\n"
              f"  This is the only time it is printed. {entry.name} needs it to sign in "
              f"to the UI; the file itself is 0600 and holds the copy Nestor verifies "
              f"against."
              + ("\n  Seals made under the old shared key will keep verifying, "
                 "reported as 'legacy'." if args.adopt_shared_key else ""))
        return EXIT_OK

    entry = ring.revoke(args.name, reason=args.reason, compromised=args.compromised)
    ring.save(path)
    consequence = ("Every seal it signed stops being served and lands in the "
                   "unverifiable list for re-verification — a stolen key's seals "
                   "cannot be told apart from the thief's."
                   if entry.compromised else
                   "Seals it already made keep serving: nobody else held the key, so "
                   "they are still that person's verifications. It just cannot make "
                   "new ones.")
    _emit({"keyring": path, "name": entry.name, "revoked_at": entry.revoked_at,
           "compromised": entry.compromised, "reason": entry.reason},
          args.json,
          f"revoked {entry.name} at {entry.revoked_at}\n  {consequence}\n"
          f"  A running UI keeps its loaded keyring until it is restarted.")
    return EXIT_OK


def cmd_rejections(args) -> int:
    """What the accumulated "no"s say — the signal nothing used to read."""
    store = _store(args)
    if not storage.supports_curation(store):
        print(f"{type(store).__name__} cannot browse the memory "
              f"(see storage.supports_curation)", file=sys.stderr)
        return EXIT_USAGE
    from .curator import Curator
    out = Curator(store, args.source_lang, args.target_lang).rejection_signals(
        min_query=args.min_query, min_pair=args.min_pair)
    lines = [f"{out['rejections']} rejection(s) in the chain for "
             f"{out['domain']['source_lang']}→{out['domain']['target_lang']}"]
    if out["queries"]:
        lines.append(f"\n  queries refused {args.min_query}+ times — the threshold "
                     f"may be wrong for this domain (nestor calibrate):")
        for q in out["queries"][:args.limit]:
            lines.append(f"    {q['rejections']}x  {q['query_norm'][:60]!r}  "
                         f"({q['distinct_answers']} distinct answer(s), "
                         f"{', '.join(q['verifiers'])})")
    if out["pairs"]:
        lines.append(f"\n  pairs refused against {args.min_pair}+ different queries — "
                     f"probably junk; unseal or reject:")
        for p in out["pairs"][:args.limit]:
            mark = "✓" if p["servable"] else " "
            lines.append(f"    {p['queries']}x {mark} {p['pair_id'][:8]}  "
                         f"{p['source_text'][:36]!r} → {p['target_text'][:36]!r} "
                         f"[{p['status']}]")
    if not out["queries"] and not out["pairs"]:
        lines.append("  nothing above the reporting thresholds — no domain-level "
                     "signal yet, which is itself the answer.")
    _emit(out, args.json, "\n".join(lines))
    return EXIT_OK


def cmd_stats(args) -> int:
    store = _store(args)
    ok, detail = ledger_mod.verify()
    stats = memory.stats(store=store)
    payload = {"db": args.db, "memory": stats, "signing_enabled": signing.signing_enabled(),
               "ledger": {"ok": ok, "detail": detail, "path": str(cascade._ledger_path())}}
    if storage.supports_curation(store):
        from .curator import Curator
        payload["curator"] = Curator(store).summary()
    human = [f"{stats['total']} pair(s): {stats['sealed']} sealed, {stats['draft']} draft"]
    if "curator" in payload and payload["curator"]["sealed_unverifiable"]:
        human.append(f"  ! {payload['curator']['sealed_unverifiable']} row(s) say sealed "
                     f"but would not be served")
    human.append("  domains: " + ", ".join(f"{sl}→{tl} ({n})" for sl, tl, n in stats["lang_pairs"])
                 if stats["lang_pairs"] else "  no domains yet")
    human.append(f"  seal signatures: {'on' if signing.signing_enabled() else 'OFF — stored status is trusted'}")
    human.append(f"  ledger: {'✓' if ok else '✗'} {detail}")
    _emit(payload, args.json, "\n".join(human))
    return EXIT_OK


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nestor",
        description="Nestor — meaning infrastructure. Has a human checked this?")
    p.add_argument("--db", default="data/nestor.db", help="SQLite database (default: data/nestor.db)")
    p.add_argument("--ledger", default="", help="ledger path (default: NESTOR_LEDGER or data/ledger.jsonl)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="command", required=True)

    def domain_args(sp, source="en", target="es"):
        sp.add_argument("--source-lang", "--from", dest="source_lang", default=source)
        sp.add_argument("--target-lang", "--to", dest="target_lang", default=target)

    ask = sub.add_parser("ask", help="run the cascade over a phrase")
    ask.add_argument("text")
    domain_args(ask)
    ask.add_argument("--engine", default="offline", choices=("offline", "auto", "claude"))
    ask.add_argument("--matcher", default="string", help=_MATCHER_HELP)
    ask.set_defaults(func=cmd_ask)

    res = sub.add_parser("resolve", help="resolve a surface form to a canonical entity")
    res.add_argument("surface")
    res.add_argument("--domain", default="entity")
    res.set_defaults(func=cmd_resolve)

    chk = sub.add_parser("check", help="check a figure against its sealed baseline")
    chk.add_argument("label")
    chk.add_argument("observed")
    chk.add_argument("--domain", default="value")
    chk.add_argument("--abs-tol", dest="abs_tol", type=float, default=0.0)
    chk.add_argument("--pct-tol", dest="pct_tol", type=float, default=0.05)
    chk.set_defaults(func=cmd_check)

    mat = sub.add_parser("match", help="the bare seam over any domain")
    mat.add_argument("text")
    domain_args(mat)
    mat.add_argument("--matcher", default="string", help=_MATCHER_HELP)
    mat.add_argument("--abs-tol", dest="abs_tol", type=float, default=0.0)
    mat.add_argument("--pct-tol", dest="pct_tol", type=float, default=0.05)
    mat.set_defaults(func=cmd_match)

    dec = sub.add_parser("decision",
                         help="the decision graph — a CI gate over recorded constraints")
    dec.add_argument("decision_command", choices=("check",))
    dec.add_argument("question", help="the question a proposal is about to answer")
    domain_args(dec, source="decision", target="decision")
    dec.set_defaults(func=cmd_decision)

    exp = sub.add_parser("export", help="write a portable, re-importable bundle")
    exp.add_argument("--out", default="", help="file to write (default: stdout)")
    exp.add_argument("--format", default="json", choices=("json", "csv"),
                     help="csv is lossy — it drops signatures, so it cannot carry a seal")
    exp.add_argument("--source-lang", "--from", dest="source_lang", default="",
                     help="limit to one domain (default: everything)")
    exp.add_argument("--target-lang", "--to", dest="target_lang", default="")
    exp.add_argument("--no-ledger", action="store_true", help="omit the source chain")
    exp.add_argument("--matcher", default="string", help=_MATCHER_HELP)
    exp.set_defaults(func=cmd_export)

    dbp = sub.add_parser("db", help="SQLite maintenance (file-backed stores)")
    dbp.add_argument("db_command", choices=("checkpoint",))
    dbp.add_argument("--out", default="",
                     help="consistent SQLite copy (VACUUM INTO); also copies the hash-chained "
                          "ledger to <basename>.ledger.jsonl beside it unless --no-ledger")
    dbp.add_argument("--no-ledger", action="store_true",
                     help="with --out, copy only the database (seals without audit chain); "
                          "an older sidecar at that name blocks, and --force removes it")
    dbp.add_argument("--force", action="store_true",
                     help="with --out, replace existing destination file(s)")
    dbp.set_defaults(func=cmd_db)

    imp = sub.add_parser("import", help="read a bundle (dry run unless --apply)")
    imp.add_argument("file")
    imp.add_argument("--apply", action="store_true", help="actually write it")
    imp.add_argument("--verifier", default="", help="who is performing the import")
    imp.add_argument("--override-conflicts", action="store_true",
                     help="take the incoming answer where this instance disagrees")
    imp.add_argument("--override-rejections", action="store_true",
                     help="revive pairs a human here rejected (separate on purpose: "
                          "--override-conflicts cannot reach them)")
    imp.add_argument("--matcher", default="string", help=_MATCHER_HELP)
    imp.set_defaults(func=cmd_import)

    led = sub.add_parser("ledger", help="verify or read the audit chain")
    led.add_argument("ledger_command", choices=("verify", "entries", "head"))
    led.add_argument("--expect-head", dest="expect_head", default="",
                     help="refuse a chain whose tip is not this (see: nestor ledger head)")
    led.add_argument("--kind", default="", help="filter entries by kind")
    led.add_argument("--limit", type=int, default=50)
    led.set_defaults(func=cmd_ledger)

    cal = sub.add_parser("calibrate",
                         help="where the seal threshold should sit for this corpus")
    domain_args(cal)
    cal.add_argument("--matcher", default="string", help=_MATCHER_HELP)
    cal.add_argument("--abs-tol", dest="abs_tol", type=float, default=0.0)
    cal.add_argument("--pct-tol", dest="pct_tol", type=float, default=0.05)
    cal.add_argument("--target", type=float, default=0.01,
                     help="acceptable collision rate (default: 0.01 — one in a hundred)")
    cal.add_argument("--sample", type=int, default=300,
                     help="rows to probe; 0 for the whole corpus (default: 300)")
    cal.add_argument("--seed", type=int, default=0, help="sampling seed")
    cal.set_defaults(func=cmd_calibrate)

    keys = sub.add_parser("keys", help="who can seal, and with what key")
    keys.add_argument("keys_command", choices=("list", "add", "revoke"))
    keys.add_argument("name", nargs="?", default="", help="the verifier")
    keys.add_argument("--keyring", default="",
                      help="keyring file (default: NESTOR_KEYRING)")
    keys.add_argument("--rotate", action="store_true",
                      help="replace an existing key — every seal it made stops verifying")
    keys.add_argument("--type", default="hmac", choices=("hmac", "ed25519"),
                      dest="key_type",
                      help="ed25519 generates a keypair here (needs the [keys] "
                           "extra); the public half is shareable")
    keys.add_argument("--public", default="",
                      help="with --type ed25519: register a PEER's public key "
                           "(hex) — verify their seals, never sign as them")
    keys.add_argument("--reason", default="", help="recorded with a revocation")
    keys.add_argument("--compromised", action="store_true",
                      help="the key was TAKEN, not merely retired: everything it "
                           "signed stops being served, because a stolen key's seals "
                           "cannot be told apart from the thief's")
    keys.add_argument("--adopt-shared-key", dest="adopt_shared_key", action="store_true",
                      help="also trust NESTOR_SEAL_KEY, so seals made before this "
                           "keyring keep verifying (reported as 'legacy')")
    keys.set_defaults(func=cmd_keys)

    rej = sub.add_parser("rejections",
                         help="what the recorded 'no's say in aggregate")
    rej.add_argument("--source-lang", "--from", dest="source_lang", default="",
                     help="limit to one domain (default: everything)")
    rej.add_argument("--target-lang", "--to", dest="target_lang", default="")
    rej.add_argument("--min-query", dest="min_query", type=int, default=2,
                     help="report a query refused at least this many times (default: 2)")
    rej.add_argument("--min-pair", dest="min_pair", type=int, default=2,
                     help="report a pair refused for at least this many queries (default: 2)")
    rej.add_argument("--limit", type=int, default=20)
    rej.set_defaults(func=cmd_rejections)

    st = sub.add_parser("stats", help="what is in the memory, and is the chain intact")
    st.set_defaults(func=cmd_stats)

    # These two own their own flags; hand the rest of argv straight over.
    sub.add_parser("ui", help="the browser surface (see: nestor ui --help)", add_help=False)
    sub.add_parser("serve", help="MCP over stdio, for a model (see: nestor serve --help)",
                   add_help=False)
    return p


DELEGATED = {"ui": "the browser surface", "serve": "the model surface"}
# Flags that mean the same thing to `nestor` and to the sub-programs, so they
# keep working on the near side of the subcommand.
SHARED_FLAGS = ("--db", "--ledger")


def split_delegated(argv: list[str]) -> tuple[Optional[str], list[str]]:
    """``(name, sub_argv)`` when this invocation targets ``ui`` or ``serve``.

    ``nestor --db x.db ui --port 9000`` has to work: a user who has typed
    ``--db`` for every other subcommand will type it here too, and having it
    silently mean something different — or, as it did, blow up in the top-level
    parser — is the kind of small betrayal that makes a CLI feel unreliable. The
    shared flags are carried across and placed *first*, so an explicit one after
    the subcommand still wins.
    """
    carried: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in SHARED_FLAGS and i + 1 < len(argv):
            carried += [token, argv[i + 1]]
            i += 2
        elif any(token.startswith(f + "=") for f in SHARED_FLAGS):
            carried.append(token)
            i += 1
        elif token == "--json":            # nothing for a server to do with it
            i += 1
        elif token in DELEGATED:
            return token, carried + argv[i + 1:]
        else:
            break                          # anything else: parse normally
    return None, argv


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `ui` and `serve` are whole programs with their own parsers; delegating the
    # remaining argv keeps one set of flags per surface instead of mirroring
    # every one of them here and letting the copies drift.
    name, rest = split_delegated(argv)
    if name:
        return {"ui": ui.main, "serve": serve.main}[name](rest)
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except BrokenPipeError:                        # `nestor ledger entries | head`
        return EXIT_OK


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
