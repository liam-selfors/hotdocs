# CLI

```
hotdocs cross-check <component-id> --second-model=<model-id> [--mode=divergence|standby-only] [--repo-root=<dir>] [--format=json|text]
```

- `--second-model` — required; the model to generate the second candidate
  with (R-XMODEL-002).
- `--mode` — `divergence` (default; R-XMODEL-004/005) or `standby-only`
  (R-XMODEL-007).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | No merge-blocking divergence — includes: standby-only mode completed; the second candidate failed verification (logged, not blocking, R-XMODEL-006); or it passed and matched the canonical candidate. |
| `1` | Divergence detected (`divergence` mode only) — merge-blocking (R-XMODEL-005). |
| `2` | Usage error (missing `--second-model`, unknown component id). |
