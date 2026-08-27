#!/usr/bin/env python3
"""Run the read-only meaning suite over a list of prompts, one report per run.

    python scripts/issue_probe.py \
        --db docs/dogfood/nestor.db \
        --prompts scripts/corpus/open_issues.txt \
        --out docs/archive/probes/open_issues.md

The question this exists for: *what does Nestor's own store say about a topic
when every lens gets a turn?* One lens's silence is not another's. On the open
issues snapshot, ``decision check`` reported ``match: none`` for #99 while
``match`` surfaced the recorded row at similarity 0.578 — same store, same
prompt, different lens. A one-lens sweep would have concluded "nothing there";
this runner is what makes the disagreement visible.

Lenses grouped by whether the CLI takes the prompt as an argument:

* **per-prompt** (called once per line in the prompts file):
    ``nestor ask`` (cascade, offline engine so no network),
    ``nestor resolve`` (surface → canonical),
    ``nestor match`` (bare seam, sees paraphrases below the seal bar),
    ``nestor decision check`` (recorded constraints / rejections /
    contradictions — non-zero exit is a signal, captured as ``blocked``).

* **corpus-level** (called once, up top):
    ``nestor stats`` (chain intact? corpus size?),
    ``nestor rejections`` (aggregate no's),
    ``nestor triage`` (grouping + supersession edges),
    ``nestor calibrate`` (where the bar sits — degrades gracefully on an
    unsealed corpus),
    ``nestor evidence report`` (sealed rows with no evidence attached).

What the tool cannot see, called out because silence is not evidence:

* The runner shells out to the ``nestor`` CLI on ``PATH`` — that exercises the
  code path a user runs, not the library one an import path would. If the
  wrong ``nestor`` is on ``PATH`` (a different venv, an older wheel), the
  report is about *that* Nestor and says so in the ``environment`` header, so
  a reader can catch the mismatch.
* ``resolve`` defaults its domain to ``entity``; a ``decision``-only corpus
  (the dogfood store) genuinely has no candidates. That is reported as
  ``candidates: 0`` — not as "the lens failed".
* ``decision check`` exits non-zero on a recorded rejection or contradiction
  (docs/decision-memory.md N9). That is the *design*, not a script failure:
  the runner captures it and continues.
* ``calibrate`` cannot measure a bar on a store with zero sealed rows. It
  says so in prose; the runner quotes that verbatim rather than inventing a
  number.
* Warnings printed to ``stderr`` (``NESTOR_SEAL_KEY not set`` and friends)
  are captured into a ``warnings`` list per invocation. A warning is not a
  failure but it is an answer about the seat.

Not called by this runner, and why:

* ``keys`` / ``policy`` / ``ledger`` verify — those are seat-management
  commands, not lenses over a prompt. ``ledger`` intactness is already
  summarised by ``stats``.
* ``ui`` / ``serve`` — human/model surfaces, not read-only lenses.
* ``export`` / ``import`` / ``db`` / ``prefs`` / ``completions`` / ``demo``
  / ``init`` — state changes or non-questions.
* ``warrant`` and ``evidence`` per-pair listings — need a pair id, which is
  a follow-up on a specific ``match`` hit, not a per-prompt lens.
* ``check`` — a numeric-baseline check, not a text lookup.

Read-only. Never writes to the store. Fails closed on a missing DB rather than
producing an empty report that reads identical to a store with nothing to say
(the exact failure #95 is filed for).

Record: **written on 2026-08-25 to answer "what does nestor say about the 16
open issues at that moment?".** First and only run at time of authoring; kept
because the *question* recurs (every new batch of issues, every seat startup),
not because a general "probe tool" was needed.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
from typing import Any, Iterator

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PROMPTS = ROOT / "scripts" / "corpus" / "open_issues.txt"
DEFAULT_DB = ROOT / "docs" / "dogfood" / "nestor.db"


@dataclasses.dataclass
class Invocation:
    """One CLI call, captured verbatim.

    ``exit`` is the process exit code; ``decision check`` uses non-zero to
    signal a recorded rejection or contradiction, so the runner does not treat
    non-zero as a failure — it stores it and lets the reader decide.
    """

    lens: str
    argv: list[str]
    exit: int
    stdout: str
    stderr: str
    parsed: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lens": self.lens,
            "argv": self.argv,
            "exit": self.exit,
            "stdout": self.stdout,
            "stderr_warnings": _split_warnings(self.stderr),
            "parsed": self.parsed,
        }


def _split_warnings(stderr: str) -> list[str]:
    """One warning per non-blank stderr line, stripped.

    The runner never suppresses these — a warning is captured evidence about
    the seat (e.g. ``NESTOR_SEAL_KEY not set``) and the report shows it.
    """
    return [line.rstrip() for line in stderr.splitlines() if line.strip()]


def read_prompts(path: pathlib.Path) -> list[str]:
    """Return one prompt per non-blank, non-``#`` line.

    A missing prompts file is a hard error — an empty prompt list would produce
    an empty report that reads identical to "the tool ran and found nothing".
    """
    if not path.exists():
        raise SystemExit(f"prompts file not found: {path}")
    prompts: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        prompts.append(line)
    if not prompts:
        raise SystemExit(f"prompts file contained no runnable lines: {path}")
    return prompts


def run(
    nestor_bin: str,
    db: pathlib.Path,
    lens_argv: list[str],
    lens_name: str,
    want_json: bool,
) -> Invocation:
    """Shell out to ``nestor``, capturing stdout/stderr and parsing JSON on demand.

    Uses ``check=False`` because some lenses (notably ``decision check``) use
    non-zero exit as a signal, not a failure. The exit code is preserved on
    the returned :class:`Invocation`.
    """
    argv = [nestor_bin, "--db", str(db)]
    if want_json:
        argv.append("--json")
    argv.extend(lens_argv)
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    parsed: Any = None
    if want_json and proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            parsed = None
    return Invocation(
        lens=lens_name,
        argv=argv,
        exit=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        parsed=parsed,
    )


def per_prompt_lenses(
    nestor_bin: str,
    db: pathlib.Path,
    prompt: str,
    source: str,
    target: str,
    matcher: str | None,
    resolve_domain: str,
) -> list[Invocation]:
    """The four lenses the CLI takes a prompt as argument for.

    ``ask`` runs with ``--engine offline`` so the sweep is deterministic and
    does not depend on network / LLM availability. A caller who wants the
    LLM-augmented cascade should call ``nestor ask`` themselves — the report
    is honest about which engine it used.
    """
    matcher_args = ["--matcher", matcher] if matcher else []
    return [
        run(
            nestor_bin,
            db,
            [
                "ask",
                prompt,
                "--from",
                source,
                "--to",
                target,
                "--engine",
                "offline",
                *matcher_args,
            ],
            "ask",
            want_json=True,
        ),
        run(
            nestor_bin,
            db,
            ["resolve", prompt, "--domain", resolve_domain],
            "resolve",
            want_json=True,
        ),
        run(
            nestor_bin,
            db,
            ["match", prompt, "--from", source, "--to", target, *matcher_args],
            "match",
            want_json=True,
        ),
        run(
            nestor_bin,
            db,
            [
                "decision",
                "check",
                prompt,
                "--source-lang",
                source,
                "--target-lang",
                target,
            ],
            "decision-check",
            want_json=True,
        ),
    ]


def corpus_lenses(
    nestor_bin: str,
    db: pathlib.Path,
    source: str,
    target: str,
) -> list[Invocation]:
    """The five aggregate lenses that speak about the corpus, not a prompt.

    ``stats`` has no ``--json`` mode; its stdout is captured verbatim.
    ``triage`` prints a long human-readable report; likewise captured. The
    others speak JSON.
    """
    return [
        run(nestor_bin, db, ["stats"], "stats", want_json=False),
        run(nestor_bin, db, ["rejections"], "rejections", want_json=True),
        run(nestor_bin, db, ["triage"], "triage", want_json=False),
        run(
            nestor_bin,
            db,
            [
                "calibrate",
                "--from",
                source,
                "--to",
                target,
                "--sample",
                "0",
                "--seed",
                "1",
            ],
            "calibrate",
            want_json=False,
        ),
        run(
            nestor_bin,
            db,
            ["evidence", "report", "--source-lang", source, "--target-lang", target],
            "evidence-report",
            want_json=True,
        ),
    ]


@contextlib.contextmanager
def snapshot_db(source: pathlib.Path) -> Iterator[pathlib.Path]:
    """Yield a scratch DB, produced via SQLite ``VACUUM INTO``.

    ``ask`` and ``resolve`` append audit rows to the ledger on every call —
    that is the ledger doing its job — but a *shipped* store (the dogfood one,
    in particular) is a git-tracked artifact that should not churn on every
    consultation. A plain ``cp`` of a live WAL store takes a stale file (the
    agent-guide names this in the "checked, not assumed" section), so we use
    ``VACUUM INTO`` which is safe against a concurrent writer.
    """
    with tempfile.TemporaryDirectory(prefix="nestor-probe-") as tmp:
        dst = pathlib.Path(tmp) / f"snapshot-{source.name}"
        conn = sqlite3.connect(str(source))
        try:
            conn.execute("VACUUM INTO ?", (str(dst),))
        finally:
            conn.close()
        yield dst


def resolve_nestor_bin() -> str:
    """The ``nestor`` on ``PATH``, or a hard failure.

    An absent CLI would silently make the report be about nothing; we refuse
    to produce that.
    """
    binary = shutil.which("nestor")
    if not binary:
        raise SystemExit(
            "nestor CLI not found on PATH — activate the venv or install "
            "nestor-meaning first (pip install -e . in this tree)"
        )
    return binary


def render_markdown(report: dict[str, Any]) -> str:
    """The written record, one section per prompt plus a corpus preamble.

    Only structural fields are rendered here; verbatim command output is
    embedded in fenced blocks so a reader can copy and paste to reproduce.
    """
    env = report["environment"]
    lines: list[str] = [
        "# Nestor issue-probe report",
        "",
        "*Read-only sweep of the meaning suite over a prompts file. "
        "See `docs/probing-the-store.md` for what each lens sees and does not.*",
        "",
        "## Environment",
        "",
        f"- nestor binary: `{env['nestor_bin']}`",
        f"- database: `{env['db']}`",
        f"- prompts file: `{env['prompts']}` ({env['prompt_count']} prompts)",
        f"- source→target: `{env['source']}` → `{env['target']}`",
        f"- resolve domain: `{env['resolve_domain']}`",
        f"- matcher: `{env['matcher'] or '(default)'}`",
        "",
        "## Corpus-level lenses",
        "",
    ]
    for inv in report["corpus"]:
        lines.extend(_render_invocation(inv, level=3))
    lines += ["", "## Per-prompt lenses", ""]
    for entry in report["prompts"]:
        lines += [f"### {entry['prompt']}", ""]
        for inv in entry["lenses"]:
            lines.extend(_render_invocation(inv, level=4))
    return "\n".join(lines) + "\n"


def _render_invocation(inv: dict[str, Any], level: int) -> list[str]:
    heading = "#" * level + f" `{inv['lens']}` — exit {inv['exit']}"
    out: list[str] = [heading, "", f"`$ {' '.join(inv['argv'])}`", ""]
    if inv["stderr_warnings"]:
        out.append("*stderr:*")
        out.append("")
        out.append("```")
        out.extend(inv["stderr_warnings"])
        out.append("```")
        out.append("")
    body = inv["stdout"].rstrip()
    if not body:
        out.append("*(no stdout)*")
        out.append("")
        return out
    fence = "```json" if inv["parsed"] is not None else "```"
    out.append(fence)
    out.append(body)
    out.append("```")
    out.append("")
    return out


def build_report(
    nestor_bin: str,
    db: pathlib.Path,
    prompts_path: pathlib.Path,
    source: str,
    target: str,
    matcher: str | None,
    resolve_domain: str,
    skip_corpus: bool,
) -> dict[str, Any]:
    prompts = read_prompts(prompts_path)
    corpus = (
        []
        if skip_corpus
        else [inv.to_dict() for inv in corpus_lenses(nestor_bin, db, source, target)]
    )
    per_prompt = [
        {
            "prompt": prompt,
            "lenses": [
                inv.to_dict()
                for inv in per_prompt_lenses(
                    nestor_bin,
                    db,
                    prompt,
                    source,
                    target,
                    matcher,
                    resolve_domain,
                )
            ],
        }
        for prompt in prompts
    ]
    return {
        "environment": {
            "nestor_bin": nestor_bin,
            "db": str(db),
            "prompts": str(prompts_path),
            "prompt_count": len(prompts),
            "source": source,
            "target": target,
            "resolve_domain": resolve_domain,
            "matcher": matcher,
            "skip_corpus": skip_corpus,
        },
        "corpus": corpus,
        "prompts": per_prompt,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", type=pathlib.Path, default=DEFAULT_DB)
    parser.add_argument("--prompts", type=pathlib.Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--out-json", type=pathlib.Path, default=None)
    parser.add_argument("--from", dest="source", default="decision")
    parser.add_argument("--to", dest="target", default="decision")
    parser.add_argument("--matcher", default=None)
    parser.add_argument("--resolve-domain", default="entity")
    parser.add_argument("--no-corpus", action="store_true")
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help=(
            "run against a VACUUM INTO snapshot of --db so the source store's "
            "ledger is not touched (recommended for git-tracked stores)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.db.exists():
        raise SystemExit(
            textwrap.dedent(
                f"""
                database not found: {args.db}

                A silent empty report is exactly the failure #95 is filed for.
                Stand up a store first (`nestor demo`, `python -m nestor.home_init`,
                or point --db at an existing one), then re-run.
                """
            ).strip()
        )
    nestor_bin = resolve_nestor_bin()
    cm = snapshot_db(args.db) if args.snapshot else contextlib.nullcontext(args.db)
    with cm as db_for_run:
        report = build_report(
            nestor_bin=nestor_bin,
            db=db_for_run,
            prompts_path=args.prompts,
            source=args.source,
            target=args.target,
            matcher=args.matcher,
            resolve_domain=args.resolve_domain,
            skip_corpus=args.no_corpus,
        )
    if args.snapshot:
        report["environment"]["source_db"] = str(args.db)
        report["environment"]["db"] = f"{args.db} (via VACUUM INTO snapshot)"
    md = render_markdown(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
    else:
        sys.stdout.write(md)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
