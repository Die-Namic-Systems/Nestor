# Probe reports (moved)

Committed probe sweeps now live under [`docs/archive/probes/`](../../archive/probes/).

To generate a fresh report:

```bash
python scripts/issue_probe.py --snapshot \
  --out docs/archive/probes/$(date +%Y%m%d)-my-sweep.md \
  --out-json docs/archive/probes/$(date +%Y%m%d)-my-sweep.json
```

See [`docs/probing-the-store.md`](../../probing-the-store.md).
