# Components

One subdirectory per component, flat namespace, no nesting:

```
<component>/
  component.md      # root: frontmatter + narrative + pointers
  requirements/     # one R-id per file
  interface/
    cli.md
    library.md
    data/           # one schema/type per file
  acceptance/       # one AC-id per file
  constraints.md    # non-functional requirements — stays one file (D15)
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
  only ever stated as a sizing heuristic. Since D16, also computes a
  narrowed blast radius for behavioral guarantees specifically (opt-in via
  `depends_on_guarantees`) — types stay coarse and always propagate,
  guarantees can be precisely scoped per dependent.
- **`cache-manager`** — all `kind: compiled`. Fail-closed on backing-store
  errors (the D10 "tool must keep working" posture, applied to a new
  subsystem). Since D16, exposes `interface/guarantees/G-CACHE-001.md` —
  the worked example behind the whole guarantee/narrowing mechanism, with
  `generator` as the real component declaring
  `depends_on_guarantees: [G-CACHE-001]` against it.
- **`criterion-compiler`** — the `sealed: true` component, all `kind:
  generated-test`. The one piece of this pipeline that is permanently
  hand-maintained by design, never agent-generated (D5's circularity
  argument: the compiler can't be the thing that verifies itself). Its
  parse+bind phase (grammar matching, `interface/` resolution) is formally
  target-independent (R-COMPILE-011); v1 ships one emitter (`pytest`), with
  any other `--target` rejected as a usage error rather than silently
  falling back.
- **`spec-bundle-assembler`** — all `kind: compiled`. Deliberately excludes
  `acceptance/` from what it assembles, to keep generation from
  overfitting to its own tests.
- **`generator`** — the first component whose job genuinely requires a
  model call; mostly `kind: generated-test` (tested via an injected mock
  model), one `compiled` path-safety check. Single-shot by design — the
  best-of-k retry loop lives in `merge-orchestrator`, not here. Accepts an
  optional `retry_feedback` (bare `R-id` list from the immediately
  preceding attempt), folded into its cache key so a fed-back retry can't
  collide with a blind one sharing the same seed.
- **`test-author`** — the second component whose job genuinely requires a
  model call, mirroring `generator`'s split. Authors `generated-test` test
  code, dispatched to by `verifier-orchestrator` via the same
  injectable-callable pattern `llm-judge`'s `judge` already established.
  Single-model (`R-AUTHOR-003`): independence comes from authoring the test
  from spec prose alone, with no access to the implementation under test.
- **`verifier-orchestrator`** — all `kind: compiled`, despite sitting right
  at the judgment/model boundary: coordinating `llm-judge` and
  `test_author` dispatch is itself deterministic dispatch-and-record logic,
  even though what it dispatches to isn't. A criterion's declared `kind` is
  treated as fixed, normative input here — never re-decided at verification
  time, a boundary made explicit after a design discussion about exactly
  that temptation. Also projects per-criterion results onto `requirement_
  results` (bare `R-id` pass/fail, via the existing `Covers:` graph edges)
  — the graph-topology mechanism `merge-orchestrator`'s diagnostic-guided
  retry loop feeds on, kept content-free enough that it can't reopen
  `spec-bundle-assembler`'s exclusion of `acceptance/` from generation.
- **`license-scanner`** / **`secret-scanner`** — all `kind: compiled`;
  k-gram/pattern-matching is fully deterministic, so neither needed
  `generated-test` or `llm-judge` despite sitting in the compliance/scanning
  space. Both carry a "retry doesn't erase flagged history" requirement, and
  `secret-scanner` additionally supports a cache-free pre-commit/pre-push
  invocation distinct from its full merge-gate scan.
- **`provenance-writer`** — all `kind: compiled`. Collects every other
  gate's already-produced result into one manifest; never invents a field.
  Found and fixed a real gap in `SPEC_GUIDELINES.md` §7's schema (a missing
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
  deterministic. Owns the best-of-k retry loop (D3) — now diagnostic-
  guided, extracting failing `R-id`s from the preceding attempt's
  `requirement_results` and passing them through to `generator` as
  `retry_feedback`, pure pass-through with no interpretation of its own —
  the real wiring of `test_author`/`judge` callables into
  `verifier-orchestrator`'s call, and (since D16) running golden-scenario
  verification against the real assembled system, reusing that same
  callable wiring — three responsibilities nothing had explicitly assigned
  before `generator`'s, `verifier-orchestrator`'s, and the blast-radius/D16
  threads each forced
  the question. Its real, measured `fan_out` is 14 (13 before
  `criterion-compiler` was added directly), confirmed against the actual
  linter — exactly the warn-only finding (not a hard failure)
  `specs/architecture/pipeline-decomposition.md` predicted before this
  component existed.

- **`spec-completeness-assistant`** — the assist agent D1 describes but
  never names, and that two `notes/metrics.md` metrics already assumed
  existed before this spec did. Lives outside the merge pipeline entirely —
  never in `merge-orchestrator`'s dependency list, no mechanism to gate
  anything. The one component whose core value genuinely *is* judgment
  (`llm-judge` for completeness scoring and redundancy detection), not
  dispatch around it — a deliberate contrast to every coordination
  component specced so far.

**All 17 architecture components are now specced in full depth** (15
original + `test-author`, added when a design discussion surfaced that
nothing owned authoring `generated-test` code + `spec-completeness-
assistant`, added when the same discussion surfaced it was referenced by
name in `notes/metrics.md` but never specced). The real linter
(`gen/spec-linter/`) validates the entire corpus clean: 0 failures, 3
warnings (two components over the spec-bundle word-count *target*, and
`merge-orchestrator`'s fan-out — none are hard-fail-severity).
