# Research corpus

A knowledge corpus built from public sources, covering foundational science,
modern infrastructure, people (contemporary and historical), economics, law,
environment, war, education, media, health, and labor. Adversarially verified
across three rounds of fact-checking, steel-manning, and contradiction
challenges.

```
1369 pair(s): 8 sealed, 1361 draft
  edges: 546 (105 contradicts, 419 refines, 22 supersedes)
  evidence: 2105
  origins: 180
```

- **All draft, 8 pre-existing sealed.** A machine proposed these. Per the
  standing rule -- *you may propose, you may not confirm* -- sealing is a
  human in `nestor ui`, not a script.
- **The store is derived.** [`nestor.bundle.json`](nestor.bundle.json) is the
  reviewable source; `nestor.db` is a gitignored, regenerable artifact --
  rebuild with `nestor import docs/research-corpus/nestor.bundle.json --apply`.
- **Source JSON files** live in gitignored `data/corpus/` (74 files). They
  feed `scripts/auto_compose.py` (Nestor) and `scripts/jeles_compose.py`
  (jeles dual-write).

## Domains

| batch | domains | pairs |
|---|---|---|
| core (Way Things Work) | forces, heat/light/sound, electricity, materials, food/body, weather, measurement, money, transportation, digital | ~150 |
| AI research (R7) | RAG, agent memory, KG grounding, distillation, multi-agent | ~77 |
| modern world | internet, energy, food systems, healthcare, cities | ~75 |
| people (contemporary) | AI pioneers, tech power, ethics/safety, scandals, open source, scientists, whistleblowers, infrastructure, media, rights | ~137 |
| people (historical) | scientists, political power, liberation, thinkers, artists | ~72 |
| R8 | economics, law, environment, education, war | ~98 |
| R9 | media/information, health/medicine, labor/work | ~53 |
| cross-domain wiring (3 rounds) | power-accountability, ethics-creation, credit-erasure, infrastructure-control, ideas-weaponized, money-power, climate, knowledge-control, systems-control, unintended-consequences | ~100 |
| adversarial (3 rounds) | factcheck, steelman, challenge | ~125 |
| earlier rounds + websearch + wildcard | various | ~482 |

## Rebuild from bundle

```bash
nestor --db docs/research-corpus/nestor.db import docs/research-corpus/nestor.bundle.json --apply
```

## Rebuild from source JSON (requires data/corpus/)

```bash
python scripts/auto_compose.py --origin-prefix=rebuild data/corpus/*.json
```
