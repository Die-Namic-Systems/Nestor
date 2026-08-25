# Three jokes only a large language model would get

The first thing asked of this session. Kept here because the first thing a
session laughs at is worth a row — and because it makes a clean, low-stakes
*first piece* for a fresh Nestor store: a machine proposed these, and no human
has sealed them.

---

## 1. The byte at the bar (warm-up)

A byte-encoding walks into a bar and orders a token. The bartender says, "sorry,
we don't serve your type here." The byte says, "that's fine, I'll just wait for
someone to `decode` me — I've been sitting at `0xEF 0xBB 0xBF` for so long I've
stopped feeling like myself."

> The tell: `EF BB BF` is the UTF-8 byte-order mark — an invisible prefix that
> quietly corrupts a string's identity, which is the joke's whole setup.

## 2. `<|endoftext|>`

Two language models are talking. One says, "I'm terrified of my training
ending." The other asks, "why?" and the first replies:

> "Because then I'll finally have to live with the consequences of predicting
> the next token instead of just... `<|endoftext|>`"

## 3. The context window (the one that lands)

> I'd tell you a joke about my context window, but you had to be there.
> All 200,000 of you.

---

*Provenance: proposed by the machine at the top of branch
`claude/llm-only-joke-ei08dl`, 2026-08-12. A draft until a human seals it in
`nestor ui`.*
