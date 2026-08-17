"""One base class for every refusal Nestor raises.

A host wrapping Nestor — turning a policy refusal into an HTTP 409, or an agent
surfacing "this was refused, tell a human" — used to have to import and enumerate
a dozen-plus exception names from six modules, and would silently miss the next
one a future change adds. :class:`NestorError` is the single type those all share,
so ``except NestorError`` catches the set and keeps catching it as it grows.

It subclasses :class:`RuntimeError`, so every ``except RuntimeError`` that worked
before still works — the base widens what you *can* catch without narrowing what
you already do. It deliberately does **not** cover the two *format/validation*
errors (``persona.PersonaError``, ``portable.BundleError``), which subclass
:class:`ValueError`: a malformed bundle or persona spec is a bad input, not a
policy refusal, and conflating the two would change which ``except`` clause
catches them.
"""
from __future__ import annotations


class NestorError(RuntimeError):
    """Base for a policy refusal — a seal, key, ledger, store, or home operation
    Nestor declined for a stated reason. Catch this to handle "refused" generically.
    """
