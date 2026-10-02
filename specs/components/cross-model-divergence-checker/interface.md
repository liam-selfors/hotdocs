---
id: comp-cross-model-divergence-checker-interface
title: Cross-Model Divergence Checker — Interface
status: draft
owners: [pipeline-team]
---

# Cross-Model Divergence Checker — Interface

## CLI

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

## Library

```
cross_check(component_id: str, second_model: str, repo_root: Path, mode: str = "divergence") -> CrossCheckResult
```

## Data: `CrossCheckResult`

```json
{
  "component_id": "comp-foo",
  "second_model": "gpt-5",
  "mode": "divergence",
  "different_vendor": true,
  "second_candidate_verification": { "...": "a VerificationReport, see verifier-orchestrator/interface.md" },
  "diverged": false,
  "divergence_detail": null
}
```

`diverged` is `null` in `standby-only` mode (R-XMODEL-007 never runs the
comparison); `false`/`true` in `divergence` mode. `divergence_detail` names
the specific criterion(s) involved when `diverged` is `true` — never just a
boolean with no actionable detail (R-XMODEL-005).
