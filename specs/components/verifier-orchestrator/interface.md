---
id: comp-verifier-orchestrator-interface
title: Verifier Orchestrator — Interface
status: draft
owners: [pipeline-team]
---

# Verifier Orchestrator — Interface

## CLI

```
hotdocs verify <component-id> [--repo-root=<dir>] [--format=json|text]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Overall verdict `pass`. |
| `1` | Overall verdict `fail`. |
| `2` | Usage error. |

## Library

```
verify(component_id: str, repo_root: Path, judge=None) -> VerificationReport
```

`judge` is the same injectable-callable pattern as `spec-linter`'s R-LINT-015
— omit it to run with every `llm-judge` criterion reporting `skipped`.

## Data: `VerificationReport`

```json
{
  "component_id": "comp-foo",
  "criteria": [
    { "id": "AC-FOO-001", "kind": "compiled", "result": "pass" },
    { "id": "AC-FOO-002", "kind": "llm-judge", "result": "skipped", "rationale": null }
  ],
  "interface_drift": false,
  "mutation_score": 0.92,
  "overall": "pass"
}
```

`result` is one of `pass` / `fail` / `skipped` — mirroring `spec-linter`'s
`severity` vocabulary (R-LINT-015's schema addition) rather than inventing a
second one for the same concept.
