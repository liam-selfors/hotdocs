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
  constraints.md    # non-functional requirements — stays one file (D1)
```

See `SPEC_GUIDELINES.md` §3.4 (anatomy) and §4 (sizing / when to split).

Specced in full depth so far:

- **`spec-linter`** — the first one, deliberately: a component whose entire
  acceptance criteria set is `kind: compiled` except one deliberate
  `llm-judge` exception (R-LINT-015), as a concrete test of the
  compiled-criterion trust argument's own guidance. One of four components
  with a real implementation
  (`gen/spec-linter/` + `verification/spec-linter/`) — this one,
  `graph-query-engine` (`D13`), and `llm-endpoint` (`D33`) hand-authored
  once each, standing in for the `generator`/`criterion-compiler` this
  pipeline didn't have yet when the first two were built (`llm-endpoint`
  is a structurally permanent exception instead, not a temporary one —
  see its own entry); `corpus-graph-builder` is the first to
  actually be produced by a real generation step instead, once a working
  stand-in for that pipeline existed. See
  `verification/spec-linter/BOOTSTRAP.md`.
  Grew well past its original scope as this corpus grew: its own graph-shaped
  rules (reference resolution, acyclicity, both traceability directions) now
  actually run as queries over `graph-query-engine`'s shared `nodes`/`edges`
  views (`R-LINT-020`/`021`, real as of `D13` — previously claimed
  but never actually implemented) rather than bespoke traversal code, and it
  now also enforces `SPEC_GUIDELINES.md` §4's own decomposition-signal
  guidance as a real finding (`R-LINT-022`, D15) plus three additional
  size-cap dimensions (`R-LINT-023`, `guarantee_count`, `acceptance_count`,
  D17) — it is, by its own `R-LINT-022`, now one of the two components in
  this corpus actually crowding multiple size-cap dimensions at once.
- **`graph-query-engine`** — all `kind: compiled`. Extracted from
  `specs/architecture/graph-query-engine.md`'s own prose (`D13`) once that
  document's embedded SQL stopped being documentation and started being an
  unverified implementation nobody had ever run — `D13` found three
  of its six views broken. Generates the six shared views
  (`nodes`/`edges`/`component_docs`/`component_context`/
  `component_provenance`/`component_size`) as a real `gen/graph-query-engine/
  views.sql` asset plus a thin loader, each view's requirement citing the
  exact `SPEC_GUIDELINES.md` section it reads under as its data contract.
  The second of three hand-bootstrapped components (after `spec-linter`,
  before `llm-endpoint`),
  the same honest exception `spec-linter` already established.
- **`impact-analyzer`** — all `kind: compiled`. Pins down, as an executable
  rule for the first time, the interface-vs-internal-change distinction
  was previously only ever stated as a sizing heuristic. Since D2, also computes a
  narrowed blast radius for behavioral guarantees specifically (opt-in via
  `depends_on_guarantees`) — types stay coarse and always propagate,
  guarantees can be precisely scoped per dependent.
- **`cache-manager`** — all `kind: compiled`. Fail-closed on backing-store
  errors (the "tool must keep working" posture, applied to a new
  subsystem). Since D2, exposes `interface/guarantees/G-CACHE-001.md` —
  the worked example behind the whole guarantee/narrowing mechanism, with
  `generator` as the real component declaring
  `depends_on_guarantees: [G-CACHE-001]` against it. Since D30,
  `VAR-CACHE-STORE-URL` is optional — a local `.hotdocs/cache/` fallback
  keeps this component's cost-avoidance benefit available even with no
  shared store configured — and this component no longer has any role
  in deciding whether a merge skips verification; that moved entirely
  to the new `provenance-checker`, once it was clear `cache-manager`
  was being asked a question its own data could never answer.
- **`criterion-compiler`** — the `sealed: true` component, all `kind:
  generated-test`. The one piece of this pipeline that is permanently
  hand-maintained by design, never agent-generated (the compiled-criterion
  trust argument's circularity point: the compiler can't be the thing that
  verifies itself). Its
  parse+bind phase (grammar matching, `interface/` resolution) is formally
  target-independent (R-COMPILE-011); v1 ships one emitter (`pytest`), with
  any other `--target` rejected as a usage error rather than silently
  falling back.
- **`spec-bundle-assembler`** — all `kind: compiled`. Deliberately excludes
  `acceptance/` from what it assembles, to keep generation from
  overfitting to its own tests.
- **`generator`** — the first component whose job genuinely requires a
  model call; mostly `kind: generated-test` (tested via an injected mock
  model), one `compiled` path-safety check. Single-shot by design, called
  at most once per component per merge attempt — since `D3` retired
  `merge-orchestrator`'s best-of-k retry loop, there is no second call to
  make within one merge at all, not just no retry loop living here.
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
  `secret_scanner` entry) and gave the "provenance hit copies the prior
  manifest forward" claim its first concrete mechanism.
- **`provenance-checker`** — all `kind: compiled`. Extracted by D29 once
  a real correctness gap surfaced: `merge-orchestrator` was treating any
  `cache-manager` hit as grounds to skip a non-sealed component's
  verification entirely, but `cache-manager` never recorded whether a
  candidate was ever actually *verified*, only that one was *produced*.
  Reads a component's already-committed `.provenance.json` directly —
  the one place a passing verdict could ever have legitimately landed,
  since a failing one never gets committed — and matches it against the
  current `spec_bundle_hash`/`gate_versions`, gated additionally by
  `VAR-TRUST-JUDGE-PROVENANCE` for any component with an `llm-judge`
  criterion. Deliberately excluded from `sealed`-component routing
  (`component-gate-runner`'s `R-GATE-001`/`007`): a sealed component's hash reflects only its
  spec, never its hand-maintained `source_path`, so trusting a hit there
  would mean never re-running the one check that could catch a human's
  own edit silently breaking something.
- **`review-packet-builder`** — all `kind: compiled`. Formats already-
  computed results; deliberately never includes the generated-code diff
  itself (principle 6). Originally depended directly on
  `verifier-orchestrator`/`license-scanner`/`secret-scanner`/
  `cache-manager` for that data; since D13, reads all of it from
  `provenance-writer`'s already-written manifest via the shared
  `component_provenance` view instead — `depends_on` dropped from 5 to 1.
- **`corpus-graph-builder`** — all `kind: compiled`. The single source of
  the `corpus-graph.json` manifest the traceability matrix and
  docs-site-renderer both read — neither recomputes any part of it.
  **The first component in this corpus whose `gen/` code was actually
  produced by a generation step**, not hand-written: a real model
  call, dispatched through a Claude Code subagent standing in for
  `llm-endpoint` (no real one existed yet at the time — `D33` built one
  shortly after, see its own entry below), constructed from exactly this
  component's assembled `SpecBundle` and nothing else — the same
  cold-mode purity `R-GEN-001` requires of the real `generator`. Verified
  independently against this repo's real corpus (node/edge counts and all
  three orphan rates cross-checked by hand) and against a synthetic
  fixture covering every `AC-GRAPH-*` criterion a real corpus can't
  currently exercise (its own orphan rates are all `0.0` today). One real
  bug found this way: `component_provenance`'s `generated_at` field
  auto-detects as `TIMESTAMP WITH TIME ZONE`, requiring `pytz` to
  materialize — invisible until a real `.provenance.json` existed to
  query (`R-GQE-005`).
- **`docs-site-renderer`** — all `kind: compiled`. A pure function of
  `corpus-graph.json`; its output is deliberately never committed.
- **`provenance-tracker`** — all `kind: compiled`. Renamed from
  `merge-tracker` (`D88`, once `merge-orchestrator`'s removal, `D87`,
  retired the per-merge-attempt log this component used to write — no
  caller of `write_tracking_record` exists anymore). Owns `hotdocs
  verify` (`D88`/`D93` — `D92` briefly combined it with `hotdocs
  generate`/`check-capability` into one `hotdocs build` command,
  reversed for the component half): for every component in scope, a
  pure, read-only check against `provenance-checker`, never triggering
  `component-gate-runner`; for every intersecting capability, calls
  `capability-scenario-verifier`'s `run_capability_gates` (check-then-run,
  unreversed by `D93` — exercising existing code, not producing new
  code), never re-deriving either component's own hit/miss logic.
  Reads `.hotdocs/attempts/` via its own `write_attempt_record`
  (`R-TRACK-007`, called by `component-gate-runner` directly — the
  dependency cycle `D92` briefly solved by having `component-gate-runner`
  write the file directly no longer exists, since this component
  doesn't call `component-gate-runner` for anything) for
  `last_requirement_failures`, a retry-feedback convenience.
- **`provenance-tracker-ui`** — all `kind: generated-test`. Renamed from
  `merge-tracker-ui` (`D88`); a build-time snapshot since `D154`: calls
  `check_readiness` once in Python, reads `corpus-graph-builder`'s
  committed `corpus-graph.json` for topology and `.hotdocs/attempts/`
  for history, and writes one self-contained page with every datum
  inlined, openable from `file://` with no server. The earlier
  DuckDB-WASM design could not render `check_readiness`'s hit/miss
  status client-side at all. Implements no generate action of its own:
  running `hotdocs generate` already is the complete recovery path, so
  there is nothing for this component to wire up beyond showing status
  clearly.
- **`component-gate-runner`** — all `kind: compiled`. Extracted from
  `merge-orchestrator` by `D76` (the same fix `D14` applied once before
  for `capability-scenario-verifier`): runs one component through its
  provenance check, generation on a miss, verification dispatch,
  compliance scanning, and provenance write, producing one
  `ComponentPipelineResult`. Has its own CLI again (`D93`, reversing
  `D92`'s brief retirement of it): `hotdocs generate <component-id>`
  (`D86`/`D91`/`D93`), independently runnable from `hotdocs verify`.
  Wires its own `test_author`/`judge` closures and calls
  `provenance-tracker`'s `write_attempt_record` once its own attempt
  concludes (`D86`/`D93` — the dependency cycle `D92` solved by having
  this component write the file directly no longer exists, since
  `provenance-tracker` doesn't call this component for anything). Fully
  specced, not yet regenerated.

- **`spec-completeness-assistant`** — the assist agent this methodology
  always assumed but never named, and that two `notes/metrics.md` metrics
  already assumed existed before this spec did. Lives outside the merge
  workflow entirely — nothing reads this component's output as a
  readiness input, no mechanism to gate anything. The one component
  whose core value genuinely *is* judgment (`llm-judge` for
  completeness scoring and redundancy detection), not dispatch around
  it — a deliberate contrast to every coordination component specced
  so far. Since D18, dispatches through `llm-endpoint` rather than
  holding a model credential itself.
- **`capability-scenario-verifier`** — all `kind: compiled`. Extracted from
  `merge-orchestrator` by D14 (since removed, `D87`): the cross-component
  analog of `verifier-orchestrator`'s per-component dispatch, one scope
  level up — runs every product capability's capability scenarios whose
  `realizes`-set intersects a scope, against the real assembled system.
  The permanent backstop for cross-component behavioral risk no
  `interface/`-level diffing can rule out in principle (D2). Since
  `D89`, also owns its own provenance, keyed on realizing components'
  actual current content rather than their `spec_bundle_hash`es, to
  avoid reopening the exact blind spot this component exists to close;
  called internally by `provenance-tracker`'s `hotdocs verify`
  (`D92`/`D93`, no standalone CLI of its own) — the capability half of
  that check, check-then-run, unreversed when `D93` split component
  generation back out.
- **`llm-endpoint`** — mostly `kind: compiled` (backend resolution,
  credential safety), one `generated-test` criterion for the actual
  dispatched call. Added by D18 once `generator` and `test-author` were
  each found independently coupled to `VAR-ANTHROPIC-API-KEY`, and
  `merge-orchestrator`'s `judge` wiring had no component behind it at
  all. The single vendor-agnostic transport every model call in the
  pipeline now dispatches through; v1 ships exactly one backend
  (Anthropic) by design, not as an unfinished gap (D4/D6's
  anti-premature-abstraction stance). Since D20, `model_call_error` is a
  structured `{category, message}` object, not a boolean, and every
  call writes a caller-agnostic record to `.hotdocs/calls/`.
  **A real `gen/llm-endpoint/` implementation since `D33`, self-hosted
  shortly after** — the fourth component with real code, originally hand-
  bootstrapped on the theory that nothing could cold-regenerate the
  component every generation call dispatches through. Once a real
  `generator` existed, that theory was tested directly: this exact
  hand-written implementation was used to cold-regenerate itself
  from its own current spec, verified the result against every
  `AC-ENDPOINT-*` criterion, and swapped it in — the first real
  self-hosted regeneration in this corpus, resolving the generator/
  llm-endpoint chicken-and-egg problem the same way a compiler
  bootstraps by compiling itself once a first version exists by other
  means. `AnthropicBackend` dispatches via the `claude` CLI's
  non-interactive mode (`D32`) instead of a from-scratch API
  client; confirmed live exactly once per generation (real money,
  `D32`'s billing finding applies), with the full test suite otherwise
  running on an injected mock backend at zero cost.

**All 25 components are now specced in full depth** (15
original + `test-author` + `spec-completeness-assistant`, both added
when earlier design discussions surfaced real gaps nothing owned yet,
+ `capability-scenario-verifier` (D14) + `llm-endpoint` (D18) +
`provenance-checker` (D29) + `graph-query-engine` (D13) +
`component-gate-runner` (D76) + `decision-drift-detector` +
`hotdocs-cli` and `hotdocs-init` (D184, D185, the installable `hotdocs`
command and project setup), each extracted from or added beneath
`merge-orchestrator`/`spec-linter`/the architecture docs once a real
coupling, crowding, or correctness signal — not speculation —
justified it; `merge-orchestrator` itself was later removed entirely,
`D87`, once checking what the rest of the corpus already produced
turned out not to need an orchestrating component). The real linter
(`gen/spec-linter/`) validates the entire corpus clean: 0 failures,
51 warnings — all `component_doc_words`/`requirement_count`/
`acceptance_count`/`generated_code_loc` near-misses, `component-gate-runner`
and `spec-linter`'s `R-LINT-022` crowding findings (D15), and several
individual dense files caught by the per-file check (`R-LINT-023`,
D17). None are hard-fail-severity; see `SPEC_GUIDELINES.md` §4 for what
each warning dimension means and when (if ever) it calls for action.
