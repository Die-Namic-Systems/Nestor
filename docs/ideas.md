# Nestor — the queue, as a numbered idea pile

This is `TODO.md`'s queue in the shape willow-reconciler reads: top-level
`N. ` items, optional legend tags, stable numbers. `IDEAS.md` is untouched and
stays this repo's own evidence dialect (the CI-gated Map, the five status tags,
the numbered §-sections); the longer arguments still live there and in
`QUESTIONS.md`. This file is only the index — if an item here disagrees with
one of those, they are right and this is stale.

The reconciler can be pointed at this file:

```sh
reconciler run --repo ./ --doc docs/ideas.md --validate
```

Legend: ✅ shipped · 🟡 partial · (untagged) proposed

**Numbers are permanent join keys.** `reconciler/ids.py` derives
`willow-ideas-<num>` from the number written on the line (that prefix is fixed
by willow-reconciler 0.6.0; the fleet convention names the shape
`<corpus>-ideas-<num>`), so a number is an identity, not an ordinal. Never
renumber; never write a markdown-auto-numbered list (`1.` repeated) here —
retire a number instead and leave the gap. A line may never begin with a
number and a dot unless it is an item: the parser counts such a line as
dropped rather than folding it in. A commit that lands an item carries
its id as an `Idea-Id` git trailer (`CONTRIBUTING.md`, the Idea-Id
commit-trailer convention); `.github/workflows/trailers.yml` fails a trailer
that names an item this file does not contain.

---

## A. Shipped (kept for the "why not" records)

Tagged from the tree, not from memory: each names the module, decision file or
test that carries it.

1. ✅ **shipped**: Asymmetric seal signatures — `nestor.keyring`, the `[keys]` extra, decisions `0074`/`0077`/`0078`. `QUESTIONS.md` §6; `IDEAS.md` §2.
2. ✅ **shipped**: Three deferred audit findings — decisions `0073`/`0076`, `tests/test_findings_2026_08_07_deferred.py`. `IDEAS.md` §6.92.
3. ✅ **shipped**: Hot backup while WAL is open — `nestor db checkpoint --out`. `IDEAS.md` §6.7; `docs/local-fleet.md`.
4. ✅ **shipped**: UI domain matcher — `ui.App(matcher=)`, `nestor ui --matcher`. `IDEAS.md` §6.40–§6.41.
5. ✅ **shipped**: Household trust root for dogfood seals — `~/.nestor` and `docs/local-agent-prototype.md`; `scripts/household_activate_sealed_dogfood.sh`.
6. ✅ **shipped**: Git-reviewable dogfood seals — `docs/dogfood/seals/<pair_id>.json`, folded at `dogfood_store.py --rebuild` (decision `0218`, `scripts/dogfood_seal_export.py`).

## B. Open

The queue, in priority order, exactly as `TODO.md` carried it.

7. Sync between instances. `QUESTIONS.md` §8.
8. An erasure path. `QUESTIONS.md` §10.
9. A store that takes concurrent writers. `QUESTIONS.md` §15.
10. A checkpoint somebody else holds. `IDEAS.md` §5.5.
11. Seal staleness and quorum. `IDEAS.md` §1.4.
12. Record the sixty seconds. `IDEAS.md` §4.3.

## C. Decided, not built

Untagged because the legend has no word for "refused on purpose"; the item is
kept so the number, and the reason, stay on record.

13. A terminal `nestor seal` is deliberately absent — `--verifier "$USER"` in a cron job is not a human checking anything. `IDEAS.md` §5.1. Not to be started.

## D. The evidence loop (fleet plan Wave 3)

14. ✅ **shipped**: This file — `TODO.md`'s queue as a numbered pile the reconciler reads (`reconciler run --repo ./ --doc docs/ideas.md`), with `TODO.md` reduced to a pointer plus the closing note the codebase cites. Decision `0238`.
15. ✅ **shipped**: Adopt `Idea-Id` commit trailers (fleet CONVENTION, decision-2026-09-11) — the convention section in `CONTRIBUTING.md`, the gate row in `AGENTS.md`, and `.github/workflows/trailers.yml` running `reconciler verify` on every push and PR to `master`.

## E. The CI floor (fleet plan Wave 4, decision 5)

16. ✅ **shipped**: The fleet CI floor in `tests.yml` — a Linux matrix equal to `pyproject.toml`'s Python classifiers (every declared minor, not two of them by hand), a Windows leg on the floor and ceiling Pythons running the same bash gate script, ruff pinned in exactly one place, CodeQL on python and actions (GitHub's default setup, kept), and an aggregate `test` job that runs `if: always()` and fails on any leg that is not a success. `tests/test_ci_floor.py` holds each fact to its source with a plant per rule. Decision `0239`.
17. Nestor on Windows, past the floor. The Windows leg's first run found two things the product declares POSIX and one it did not know it assumed. Declared: the hooks (`hooks/nestor-hook`, `.claude/hooks/session-start.sh`) are bash that resolve `python3` and `.venv/bin/python`, and the cross-process ledger lock is `fcntl.flock` with a one-process threading lock standing in without it — both are marked by platform on the tests that exec them (`tests/conftest.py` `runs_the_bash_hooks`, `tests/test_audit_2026_07_31.py` `posix_file_lock`). Not known: the ledger's byte-offset checkpoint assumed a one-byte newline, fixed in `cascade.py` (`newline="\n"`), and the owner-only keyring check read POSIX mode bits Windows does not carry, fixed in `keyring.py`/`ui.py`; the file-backed store opened connections with sqlite3's five-second default busy timeout, which a thread pool exceeds on a busy disk, fixed in `sqlite_store.py` (`_BUSY_TIMEOUT_SEC`). The leg runs in Python's UTF-8 mode (`PYTHONUTF8=1` in `tests.yml`): under a legacy code page a Windows pipe is cp1252 and every script that prints a check mark dies before its first line. Open here: the CLI, hooks, demos and scripts under a legacy code page (they print `✓` and `—` to whatever stdout is), hooks that self-locate an interpreter on Windows (Claude Code runs them through Git Bash), a cross-process lock where `fcntl` is absent (`msvcrt.locking` is mandatory and would fail concurrent readers, so it is not a drop-in), and the 150-odd test-side `read_text()`/`write_text()` calls with no `encoding=` (ruff `PLW1514` would name them all; four fired). Decision `0239`.
