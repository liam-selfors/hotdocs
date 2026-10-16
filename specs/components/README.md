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
- **`test-author`** — the second component whose job genuinely requires a
  model call, mirroring `generator`'s split. Authors `generated-test` test
  code, dispatched to by `verifier-orchestrator` via the same
  injectable-callable pattern `llm-judge`'s `judge` already established.
  Prefers a model different from `generator`'s, for genuine independence
  (D4/D5), falling back to the canonical model alone when no second model
  exists (D10's posture, a fourth instance).
- **`verifier-orchestrator`** — all `kind: compiled`, despite sitting right
  at the judgment/model boundary: coordinating `llm-judge` and
  `test_author` dispatch is itself deterministic dispatch-and-record logic,
  even though what it dispatches to isn't. A criterion's declared `kind` is
  treated as fixed, normative input here — never re-decided at verification
  time, a boundary made explicit after a design discussion about exactly
  that temptation.
- **`cross-model-divergence-checker`** — all `kind: compiled`, for the same
  reason as `verifier-orchestrator`: comparing two already-produced,
  concrete candidates needs no judgment, even though producing them did.
- **`license-scanner`** / **`secret-scanner`** — all `kind: compiled`;
  k-gram/pattern-matching is fully deterministic, so neither needed
  `generated-test` or `llm-judge` despite sitting in the compliance/scanning
  space. Both carry a "retry doesn't erase flagged history" requirement, and
  `secret-scanner` additionally supports a cache-free pre-commit/pre-push
  invocation distinct from its full merge-gate scan.
- **`provenance-writer`** — all `kind: compiled`. Collects every other
  gate's already-produced result into one manifest; never invents a field.
  Found and fixed a real gap in `SPEC_GUIDELINES.md` §8's schema (a missing
  `secret_scan` field, even though `gate_versions` already expected a
  `secret_scanner` entry) and gave D11's "cache hit copies the prior
  manifest forward" claim its first concrete mechanism.
- **`review-packet-builder`** — all `kind: compiled`. Formats already-
  computed results; deliberately never includes the generated-code diff
  itself (principle 6).
- **`corpus-graph-builder`** — all `kind: compiled`. The single source of
  the `corpus-graph.json` manifest D8's traceability matrix and D9's
  docs-site-renderer both read — neither recomputes any part of it.
- **`docs-site-renderer`** — all `kind: compiled`. A pure function of
  `corpus-graph.json`; its output is deliberately never committed (D9).
- **`merge-orchestrator`** — all `kind: compiled`, the capstone data point
  for D5's guidance: even the component sequencing every model-calling,
  judgment-involving gate in the whole pipeline is itself fully
  deterministic. Owns the best-of-k retry loop (D3) and the real wiring of
  `test_author`/`judge` callables into `verifier-orchestrator`'s call —
  two responsibilities nothing had explicitly assigned before `generator`'s
  and `verifier-orchestrator`'s specs forced the questions. Its real,
  measured `fan_out` is 13 (12 before `test-author` was added), confirmed
  against the actual linter — exactly the warn-only finding (not a hard
  failure) `specs/architecture/pipeline-decomposition.md` predicted before
  this component existed.

**All 16 architecture components are now specced in full depth** (15
original + `test-author`, added when a design discussion surfaced that
nothing owned authoring `generated-test` code). The real linter
(`gen/spec-linter/`) validates the entire corpus clean: 0 failures, 3
warnings (two components over the spec-bundle word-count *target*, and
`merge-orchestrator`'s fan-out — none are hard-fail-severity).
