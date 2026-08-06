# A name is not a word — and "name" is not the distinction either

*Design memo for [`IDEAS.md`](../IDEAS.md) §6.22. Written 2026-08-06. Nothing
here is implemented, and per §6.22 nothing should be until somebody hits it: it
still has no reporter, no failing host, and one contrived reproduction.*

§6.22 established the collision and then declined to add a field, listing three
questions that come first and guessing that the third might dissolve the other
two. It does. This memo answers all three, and corrects one claim §6.22 makes
about the mechanism it proposed as the way out.

---

## The claim that does not hold

§6.22 says, of `glossary.locks_in_text` → `system_prompt(locks=...)`:

> **The one mechanism that could express it is outside everything.** […] an
> identity lock (`{"Nestor": "Nestor"}`) is precisely carry-through.

The second half is wrong, and it is wrong for the same reason the store cannot
hold both rows. `locks_in_text` matches case-insensitively
([`glossary.py:36`](../nestor/glossary.py)):

```python
lower = text.lower()
return {t: tr for t, tr in terms_for(source_lang, target_lang).items()
        if t.lower() in lower}
```

Measured, with `{"en->ru": {"Nestor": "Nestor"}}` installed:

```
'Nestor answers one question.'          -> locks {'Nestor': 'Nestor'}
'he was the nestor of the committee'    -> locks {'Nestor': 'Nestor'}
'NESTOR shouted'                        -> locks {'Nestor': 'Nestor'}
```

All three fire. The middle one is the common noun — the row that should become
*мудрый советник* — and the lock would put `Locked terminology — always render
these terms exactly as given: "Nestor" -> "Nestor"` into the prompt for it. An
identity lock does not express carry-through for this case; it suppresses the
only translation in the pair that is a translation.

So the glossary is not the mechanism that *could* express the distinction and
merely lacks guarantees. It is a **second** mechanism with the same blindness,
reached by a different route: the store case-folds in `StringMatcher.normalize`
deliberately, and the glossary case-folds in `locks_in_text` incidentally.
§6.22's diagnosis — "there is no field that says so" — is right, and the escape
hatch it names is not one.

That matters for what follows, because it removes the cheapest option from the
table. There is no way to say this today, in any component, with any
combination of existing parts.

---

## Q1 — proper noun, or "this string is carried, not rendered"?

**Carried, decisively.** Three reasons, in increasing order of how much they
settle.

**It needs no linguistics.** §6.22 already noted the second framing is broader.
The set it has to cover is product names, SKUs, identifiers, file paths, API
field names, legal citations, ticker symbols — a grammarian would call almost
none of those proper nouns, and every one of them has the same requirement:
survive the transform byte-for-byte.

**"Proper noun" is a property of a word; carriage is a property of an
intention.** *Nestor* is a proper noun in one segment and a common noun in the
next, which is the whole of §6.22. Any field that stores *is this a name* is
storing an answer to a question that changes per occurrence, which is how a
field ends up carrying a distinction the mechanism does not otherwise make —
the shape §6.17 keeps punishing and §6.22 explicitly refuses to repeat.

**The failing case is not about names at all.** The reason the two rows collide
is that `normalize` case-folds, and the reason that is correct is that
`Hello`/`hello` must share a row. The class where case *is* the meaning is not
the class of names; it is the class of strings whose **exact bytes are the
content**. That class is defined by what you intend to do with the string, and
"carried" says it in a word.

---

## Q2 — glossary into the store, or a policy file that is under-guarded?

**Neither, as posed — because it is not currently a policy file.** A policy file
has a location. This one does not:

```python
_PATH = pathlib.Path("data/glossary.json")
```

Relative, resolved against the process working directory, every call. Measured:
the same process, having written and read a glossary successfully, returns `{}`
for `load()` after a `chdir`. Two Nestor processes started from different
directories on one machine have different glossaries and no way to notice. A
`systemd` unit and a developer shell disagree silently.

So §6.22's framing — *correctly a policy file that happens to be under-guarded* —
understates it by one step. Before the sealing question is worth asking, the
glossary is **under-addressed**: unsigned, unledgered, unbundled *and* unlocatable.
That is worth fixing on its own account and independently of everything else in
this memo, because it is the one part with a live blast radius today. Confirmed
by grep, extending §6.22's `0, 0, 0`: `glossary` appears zero times in
`portable.py`, `cascade.py`, `sqlite_store.py`, `signing.py` and `ledger.py`.

**On moving it into the store: the real complaint is the bundle, not the seal.**
§6.22 puts its finger on the soundness gap precisely — *a bundle that carries
every pair and rejection carries no locks, so the receiving host composes prompts
the sending host would not have.* That is a genuine defect in export/import, and
it is not fixed by sealing locks; it is fixed by **bundling** them.

But locks should not become `tm_pairs` rows, and the reason is the thing this
whole entry is about: `tm_pairs` is keyed on `(source_norm, source_lang,
target_lang)` where `source_norm` is case-folded. Putting locks in that table
reproduces the exact collision that started §6.22, one layer down. Whatever
holds carried strings must not be keyed on a case-folded normal form — that is
the one hard constraint, and it rules out the tempting shortcut.

There is also a semantic mismatch worth naming, because it decides whether
"sealed locks" even means anything. Nobody *verifies* that `Nestor` is carried.
A seal answers "has a human checked this machine output?" — and a lock is not
machine output. It is a decision somebody made, closer in kind to a rejection's
`reason` or to `reopen_when` than to a pair. It wants recording in the ledger
and travelling in the bundle. It does not want a `verifier` column, because
there is nothing for a verifier to have been right or wrong about.

---

## Q3 — does a carried string want a pair at all?

**No, and this is the question that dissolves the other two.**

§6.22 suspected it and framed it as script-versus-language: `Nestor -> Нестор`
is a fact about a script, not about a language pair, and the table is a
language-pair table. That is true, and it does not go far enough, because
`Nestor -> Нестор` is not the carried case at all — it is a *transliteration*,
which is a real transform with a real target and belongs in a pair table as much
as any other translation does.

The carried case is `Nestor -> Nestor`. And that is not a pair. It is
**membership in a set**:

> these strings are content, not language; do not transform them.

One column. No target, because the target is the source — storing it is storing
a value that can only ever equal another value in the same row, which is a table
shape asking to drift. No language pair, because carriage is not directional: a
string carried `en->ru` is carried `en->de` and carried on the way back. A
product name does not stop being a product name per corridor.

Everything reshapes once it is a set:

- **Q1 dissolves.** A set does not need a theory of what its members *are*, only
  a rule for getting in. "Proper noun" was only ever a proxy for membership, and
  a bad one.
- **Q2 shrinks.** The thing to bundle and ledger is a set of strings per domain,
  not a parallel pair table with its own key, its own uniqueness rules and its
  own collision with case folding. A set has no key to get wrong.
- **The case-folding collision goes away rather than being worked around.** The
  two rows in §6.22 stop competing because only one of them is a translation.
  `Nestor` is carried and never reaches the matcher; `nestor` is a common noun
  and takes the row. No field says which; the *set* says which, and the set is
  consulted before normalization rather than inside it.
- **The glossary's case-fold bug stops mattering for this case**, because
  membership is checked on exact bytes by construction — a set of carried
  strings that matched case-insensitively would be carrying the wrong strings,
  which is visible immediately rather than subtly.

The honest cost: a set consulted before normalization is a new step on the hot
path, and the hot path is already documented as linear and Python-bound (§2).
Whether that is acceptable is a measurement nobody has taken, and this memo does
not take it, because the feature has no reporter.

---

## What is still not proposed

No `kind` column. No `is_proper_noun`. No field on `tm_pairs` at all — the set
is beside the table, not in it.

And no implementation. §6.22's closing note holds and is worth repeating,
because it is the reason this is a memo: **nobody has hit this.** One contrived
reproduction, found while looking for somewhere to put a dozen unsigned
translations. What has changed since §6.22 was written is only that the escape
hatch it proposed has been checked and does not work, and that the shape of the
right answer is a set rather than a field.

The one item here that *is* worth doing without a reporter is the glossary's
path — see [`IDEAS.md`](../IDEAS.md) §6.27. That one is not waiting on a design
question; it is waiting on somebody noticing that their locks silently stopped
applying.
