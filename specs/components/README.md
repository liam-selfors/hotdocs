# Components

One subdirectory per component, flat namespace, no nesting:

```
<component>/
  spec.md          # normative behavior
  interface.md     # public contract
  acceptance.md    # acceptance criteria
  constraints.md   # non-functional requirements
```

See `SPEC_GUIDELINES.md` §3.4 (anatomy) and §4 (sizing / when to split).

Specced in full depth so far:

- **`spec-linter`** — the first one, deliberately: a component whose entire
  acceptance criteria set is `kind: compiled`, as a concrete test of D5's own
  guidance. Also the only component with a real, working bootstrap
  implementation (`gen/spec-linter/` + `verification/spec-linter/`) —
  hand-authored once, standing in for the `generator`/`criterion-compiler`
  this pipeline doesn't have yet. See `verification/spec-linter/BOOTSTRAP.md`.
- **`impact-analyzer`** — all `kind: compiled`. Pins down, as an executable
  rule for the first time, the interface-vs-internal-change distinction D2
  only ever stated as a sizing heuristic.
- **`cache-manager`** — all `kind: compiled`. Fail-closed on backing-store
  errors (the D10 "tool must keep working" posture, applied to a new
  subsystem).
- **`criterion-compiler`** — the `sealed: true` component, all `kind:
  generated-test`. The one piece of this pipeline that is permanently
  hand-maintained by design, never agent-generated (D5's circularity
  argument: the compiler can't be the thing that verifies itself).
- **`spec-bundle-assembler`** — all `kind: compiled`. Deliberately excludes
  `acceptance.md` from what it assembles, to keep generation from
  overfitting to its own tests.
- **`generator`** — the first component whose job genuinely requires a
  model call; mostly `kind: generated-test` (tested via an injected mock
  model), one `compiled` path-safety check. Single-shot by design — the
  best-of-k retry loop lives in `merge-orchestrator`, not here.
- **`verifier-orchestrator`** — all `kind: compiled`, despite sitting right
  at the judgment/model boundary: coordinating `llm-judge` evaluations is
  itself deterministic dispatch-and-record logic, even though what it
  dispatches to isn't.
- **`cross-model-divergence-checker`** — all `kind: compiled`, for the same
  reason as `verifier-orchestrator`: comparing two already-produced,
  concrete candidates needs no judgment, even though producing them did.
- **`license-scanner`** / **`secret-scanner`** — all `kind: compiled`;
  k-gram/pattern-matching is fully deterministic, so neither needed
  `generated-test` or `llm-judge` despite sitting in the compliance/scanning
  space. Both carry a "retry doesn't erase flagged history" requirement, and
  `secret-scanner` additionally supports a cache-free pre-commit/pre-push
  invocation distinct from its full merge-gate scan.

Everything else in the pipeline's own architecture
(`specs/architecture/pipeline-decomposition.md`) is declared but not yet
specced to this depth. `merge-orchestrator` is worth calling out specifically
— it now has a concrete, assigned responsibility (the best-of-k retry loop)
that nothing had explicitly owned before `generator`'s spec forced the
question.
