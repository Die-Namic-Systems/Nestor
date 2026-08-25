# A fresh Nestor, stood up with one piece

This is a fresh store standing up around a single piece: the three jokes in
[`../llm-only-jokes.md`](../llm-only-jokes.md), loaded as **one draft pair**.

```
1 pair(s): 0 sealed, 1 draft
  domains: joke→joke (1)
```

- **The piece** — source `"Tell me a joke only a large language model would
  get."` → target the jokes doc. Domain `joke→joke`.
- **Draft, not sealed.** A machine proposed it. Per the standing rule, *you may
  propose, you may not confirm* — sealing is a human sitting down in
  `nestor ui`, not a function call.
- **The store is derived.** The reviewable source is
  [`nestor.bundle.json`](nestor.bundle.json); `nestor.db` is a gitignored,
  regenerable artifact — rebuild it with `nestor import nestor.bundle.json --apply`.

To seal it (as a human), or reject it:

```bash
nestor --db demo/llm-only-joke/nestor.db ui   # the queue, where the state changes
```
