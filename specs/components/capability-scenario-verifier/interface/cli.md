# CLI

```
hotdocs check-capability <capability-id> [--model=<model-id>] [--repo-root=<dir>] [--format=json|text]
```

`D89`. Runs `run_capability_gates` for one capability — a developer
invokes this directly, the same posture `hotdocs generate` has for one
component. `--model` is required only when a `judge`/`test_author`
dispatch is actually needed (any `llm-judge`/`generated-test` scenario
in this capability lacking a cached `generated-test`) — a
capability whose scenarios are all `kind: compiled` never needs one;
omitting it when one is needed is a usage error, not a silent skip.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Checked or run — provenance written either way. Check the reported `CapabilityProvenanceCheckResult` for the actual pass/fail. |
| `1` | A scenario dispatch's own model-call error. |
| `2` | Usage error (unknown capability id, missing `--model` when one was needed). |
