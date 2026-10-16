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
verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport
```

`judge` is the same injectable-callable pattern as `spec-linter`'s
R-LINT-015 — omit it to run with every `llm-judge` criterion reporting
`skipped`. `test_author` is the equivalent for `generated-test` criteria
lacking a cached test (R-VERIFY-009) — **but omitting it degrades
differently**: a `generated-test` criterion with nothing cached and no
`test_author` configured reports `fail`, not `skipped` (R-VERIFY-010).

## Data: `VerificationReport`

```json
{
  "component_id": "comp-foo",
  "criteria": [
    { "id": "AC-FOO-001", "kind": "compiled", "result": "pass" },
    { "id": "AC-FOO-002", "kind": "llm-judge", "result": "skipped", "rationale": null },
    { "id": "AC-FOO-003", "kind": "generated-test", "result": "pass",
      "test_authoring": { "model": "gpt-5", "seed": 0, "prompt_version": "v1", "cache_hit": false } }
  ],
  "interface_drift": false,
  "mutation_score": 0.92,
  "overall": "pass"
}
```

`result` is one of `pass` / `fail` / `skipped` — mirroring `spec-linter`'s
`severity` vocabulary (R-LINT-015's schema addition) rather than inventing a
second one for the same concept. `test_authoring` is present only on
`generated-test` criteria that actually dispatched to `test_author` this
run (absent on a cache hit with no fresh authoring call, and absent on
every other `kind`) — it's how `test-author`'s own provenance (model, seed,
prompt version) reaches `provenance-writer` without that component needing
a direct dependency on `test-author`: it rides along inside this report,
the same way `llm-judge` rationale already does.
