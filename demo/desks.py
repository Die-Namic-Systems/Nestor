"""Two or more Nestor desks in one process, and the globals that makes you own.

Scaffolding for fixtures that stand up more than one deployment — an intake desk
and a review desk, a client and their auditor, two people who disagree. No
persona lives here: this module knows how to stand a desk up and how to say a
claim failed, and nothing about whose desk it is.

Not a replacement for ``scripts/two_instances.py``
--------------------------------------------------
That harness runs each box in its **own subprocess** with its own environment,
and it is the one to reach for when the question is whether state crosses a
trust boundary — a seal, a key, a ledger head. It does not have to think about
any of what follows, because a process global cannot leak between processes.

This is the cheaper arrangement: several desks inside one interpreter, for
walking a story through them. It buys legibility and costs isolation, and the
cost is specific and worth stating up front.

**The package holds exactly one of each of these, per process:**

======================  ====================================  ====================
what                    set by                                read by
======================  ====================================  ====================
the ledger path         ``cascade.set_ledger_path``           every append
the store               ``storage.set_store``                 every call omitting ``store=``
the matcher             ``memory.set_matcher``                every call omitting ``matcher=``
======================  ====================================  ====================

So a fixture that stands two desks up and sets these once has not built two
desks. It has built one desk that changes its mind about which store it is,
and the failure is quiet: both desks' decisions land in whichever chain was
configured last, and any count taken afterwards is a true number about the
wrong thing. That is not hypothetical — it is what the first fixture written
against this arrangement did, and it reported one desk's total as the other's.

:meth:`Desk.activate` therefore sets all three together, and every accessor on
:class:`Desk` calls it first. Switching desks is one call you cannot half-do,
rather than three you can.

**The matcher is the one that bites hardest**, because it is the one that is
silently *correct-looking*. ``nestor.ui`` takes ``--source-lang`` and
``--target-lang`` but has no matcher of its own and no field for one, so every
write it makes normalizes with whichever matcher is installed process-wide. Aim
the surface at a domain whose matcher is not installed and the seals it writes
are keyed by something that domain will never compute: they are real, signed,
in the chain, and unreachable. Giving a :class:`Desk` its ``matcher`` and going
through :meth:`Desk.activate` is what keeps that honest here. One process still
holds one matcher, so two custom-matcher desks in one interpreter are two desks
taking turns — which is a real constraint on what a single fixture can show, and
the reason ``scripts/two_instances.py`` exists.
"""
from __future__ import annotations

import pathlib
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Any, Optional

from nestor import cascade, memory, storage, ui
from nestor.matcher import StringMatcher
from nestor.sqlite_store import SqliteStore

#: What ``activate`` installs for a desk that named no matcher. One instance,
#: because ``StringMatcher`` is stateless and a fresh one per switch would be
#: churn pretending to be caution.
DEFAULT_MATCHER = StringMatcher()

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")


# --------------------------------------------------------------------------
# Saying things, and being held to them
# --------------------------------------------------------------------------

#: Every failed :func:`claim` and :func:`gap`, in the order they failed. A
#: fixture returns ``1`` when this is non-empty — narrating something that did
#: not happen is worse than not narrating it.
FAILURES: list[str] = []


def beat(n: int, title: str) -> None:
    print(f"\n{BOLD}{n}. {title}{OFF}")


def say(text: str = "") -> None:
    print(f"   {text}" if text else "")


def note(text: str) -> None:
    say(f"{DIM}{text}{OFF}")


def claim(condition: bool, what: str) -> None:
    """Assert something the walk-through just said. Records rather than raises.

    Deliberately not an ``assert``: a fixture that dies on its first wrong claim
    shows you one problem, and a fixture that runs to the end shows you all of
    them and still exits non-zero.
    """
    if not condition:
        FAILURES.append(what)
        print(f"   {RED}DEMO CLAIM FAILED: {what}{OFF}")


def gap(condition: bool, what: str, entry: str = "") -> None:
    """Assert that a **gap is still open**, naming the entry that argues it.

    Failing here is good news — the surface grew the thing it was missing — and
    it still has to stop the build. A demo narrating a gap somebody has closed
    is the same defect as one narrating a fix that never landed, and the person
    who closes it is not going to think to grep the fixtures.
    """
    if not condition:
        FAILURES.append(f"(gap closed, update this script) {what}")
        where = f" ({entry})" if entry else ""
        print(f"   {GREEN}GAP CLOSED — update this fixture and the IDEAS entry "
              f"it names{where}: {what}{OFF}")


def verdict() -> int:
    """``0`` if every claim held, else ``1`` after listing what did not."""
    if FAILURES:
        print(f"\n{RED}{len(FAILURES)} claim(s) no longer hold:{OFF}")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print(f"\n{GREEN}Every claim above held.{OFF}\n")
    return 0


# --------------------------------------------------------------------------
# The desks
# --------------------------------------------------------------------------

@dataclass
class Desk:
    """One deployment: its own directory, store, chain, domain and matcher.

    ``matcher`` is optional and defaults to the package default. Pass one when
    the desk's domain is not language — and then reach the desk through its own
    methods rather than calling :mod:`nestor.memory` directly, so the matcher is
    installed before anything reads it.
    """

    name: str
    root: pathlib.Path
    source_lang: str
    target_lang: str
    matcher: Any = None
    origin: str = ""
    store: Any = field(default=None, repr=False)
    app: Any = field(default=None, repr=False)

    def open(self) -> "Desk":
        """Create the directory, the store and the surface. Idempotent."""
        self.root.mkdir(parents=True, exist_ok=True)
        cascade.set_ledger_path(str(self.ledger))
        self.store = SqliteStore(str(self.db))
        self.store.init_db()
        self.store.memory_init()
        self.app = ui.App(store=self.store, source_lang=self.source_lang,
                          target_lang=self.target_lang, db_path=str(self.db))
        self.activate()
        return self

    def activate(self) -> "Desk":
        """Make this the desk the process is sitting at.

        All three globals together, because they are three ways of being at the
        wrong desk and the package will not tell you which one you got wrong.
        """
        cascade.set_ledger_path(str(self.ledger))
        storage.set_store(self.store)
        memory.set_matcher(self.matcher if self.matcher is not None
                           else DEFAULT_MATCHER)
        return self

    # -- where its things are ------------------------------------------------

    @property
    def db(self) -> pathlib.Path:
        return self.root / "nestor.db"

    @property
    def ledger(self) -> pathlib.Path:
        return self.root / "ledger.jsonl"

    def chain(self) -> list[str]:
        """This desk's ledger lines. Its own file, not the process's current one."""
        if not self.ledger.exists():
            return []
        return [ln for ln in self.ledger.read_text(encoding="utf-8").splitlines()
                if ln.strip()]

    # -- proposing, which is all a fixture may do ---------------------------

    def propose(self, source: str, target: str, reason: str = "", **kw) -> dict:
        """Queue a draft. There is no ``verifier`` and no route to ``sealed``.

        A fixture may propose and may not confirm, and a helper offering a
        shortcut past the queue would be the covenant inverted. Sealing happens
        through :meth:`seal_draft`, which goes to the human surface.
        """
        self.activate()
        return memory.add_pair(source, target, self.source_lang, self.target_lang,
                               status="draft", origin=kw.pop("origin", self.origin),
                               reason=reason, store=self.store,
                               matcher=self.matcher, **kw)

    def rows(self) -> list[dict]:
        self.activate()
        return sorted(self.store.memory_candidates(self.source_lang, self.target_lang),
                      key=lambda r: (r["status"], r["source_norm"]))

    def best_sealed(self, query: str) -> Optional[dict]:
        """What this desk would actually serve as verified, or ``None``."""
        self.activate()
        return memory.best_sealed(query, self.source_lang, self.target_lang,
                                  store=self.store, matcher=self.matcher)

    # -- the human surface --------------------------------------------------

    def ui_post(self, path: str, **payload) -> tuple:
        """POST to this desk's ``nestor.ui``, the way the browser does.

        Every human decision in a fixture should come through here rather than
        through :mod:`nestor.memory`. Reaching past the surface proves the
        library works, which was never the question.
        """
        self.activate()
        return ui.dispatch(self.app, "POST", path, {}, payload)

    def ui_get(self, path: str, **query) -> tuple:
        self.activate()
        return ui.dispatch(self.app, "GET", path, query)

    def seal_draft(self, pair_id: str, verifier: str, **payload) -> tuple:
        """A named human sealing a queued draft. Theirs, never the fixture's."""
        return self.ui_post("/api/seal-draft", pair_id=pair_id,
                            verifier=verifier, **payload)


class Workspace:
    """A temporary home for a set of desks, removed unless ``keep`` is given.

    Use as a context manager. Nothing outside it is touched, which is the whole
    reason a fixture may be run by anybody without reading it first.
    """

    def __init__(self, keep: str = "", prefix: str = "nestor-desks-"):
        self.keep = bool(keep)
        self.root = (pathlib.Path(keep) if keep
                     else pathlib.Path(tempfile.mkdtemp(prefix=prefix)))
        self.root.mkdir(parents=True, exist_ok=True)
        self.desks: list[Desk] = []

    def desk(self, name: str, source_lang: str, target_lang: str,
             matcher: Any = None, origin: str = "") -> Desk:
        d = Desk(name=name, root=self.root / name, source_lang=source_lang,
                 target_lang=target_lang, matcher=matcher, origin=origin).open()
        self.desks.append(d)
        return d

    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *exc) -> None:
        if self.keep:
            print(f"\n   {DIM}kept: {self.root}{OFF}")
        else:
            shutil.rmtree(self.root, ignore_errors=True)
