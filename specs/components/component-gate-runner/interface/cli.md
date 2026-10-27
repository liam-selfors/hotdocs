# CLI

```
hotdocs generate <component-id> --model=<model-id> [--seed=<n>] \
  [--retry-feedback=<R-id>,...] [--repo-root=<dir>] [--format=json|text]
```

`D91` — this verb replaces `generator`'s own, narrower former CLI:
nobody calls just the raw candidate-producing step directly anymore,
only this component's full gauntlet, via this one command. `generator`
itself is still the component owning the actual model-call mechanics
(`R-GEN-*`), now an internal library call this component makes, not a
separate thing a developer invokes.

- `<component-id>` — the component to run through its full gauntlet.
- `--model` — model identifier to call (R-GATE-002). Required — no
  implicit default.
- `--seed` — sample seed/index. Default `0`.
- `--retry-feedback` — comma-separated `R-id` list from a prior
  `generate` attempt against this same component. Optional — folds
  into `generator`'s own `gate_inputs_hash` (`R-GEN-005`), so calling
  `generate` again against an unchanged spec but with different
  `--retry-feedback` is already a cache miss, a fresh attempt, with no
  separate retry mechanism needed.
- A developer running this against more than one component in the
  same spec change MUST run it in `depends_on` order — this component
  does not sequence multiple calls itself (`R-ASSEMBLE-011`'s
  `dependency_usage` needs each dependency's `gen/` content current
  when a dependent's bundle is assembled).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | The component's gauntlet concluded — provenance written, pass or fail recorded. Check the reported `ComponentPipelineResult` for the actual outcome. |
| `1` | Model-call error (`model_call_error` populated) — distinct from "produced code that failed verification," which still exits `0`. |
| `2` | Usage error (unknown component id, missing `--model`). |
