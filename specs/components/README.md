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
  acceptance criteria set is `kind: compiled` except one deliberate
  `llm-judge` exception (R-LINT-015), as a concrete test of D5's own
  guidance. Also the only component with a real, working bootstrap
  implementation (`gen/spec-linter/` + `verification/spec-linter/`) —
  hand-authored once, standing in for the `generator`/`criterion-compiler`
  this pipeline doesn't have yet. See `verification/spec-linter/BOOTSTRAP.md`.
  Grew well past its original scope as this corpus grew: its own graph-shaped
  rules (reference resolution, acyclicity, both traceability directions) now
  run as queries over `graph-query-engine.md`'s shared `nodes`/`edges` views
  (`R-LINT-020`/`021`, D24/D27) rather than bespoke traversal code, and it
  now also enforces `SPEC_GUIDELINES.md` §4's own decomposition-signal
  guidance as a real finding (`R-LINT-022`, D28) plus three additional
  size-cap dimensions (`R-LINT-023`, `guarantee_count`, `acceptance_count`,
  D29) — it is, by its own `R-LINT-022`, now one of the two components in
  this corpus actually crowding multiple size-cap dimensions at once.
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
  `depends_on_guarantees: [G-CACHE-001]` against it. Since D39,
  `VAR-CACHE-STORE-URL` is optional — a local `.hotdocs/cache/` fallback
  keeps this component's cost-avoidance benefit available even with no
  shared store configured — and this component no longer has any role
  in deciding whether a merge skips verification; that moved entirely
  to the new `provenance-checker`, once it was clear `cache-manager`
  was being asked a question its own data could never answer.
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
  model), one `compiled` path-safety check. Single-shot by design, called
  at most once per component per merge attempt — since `D31` retired
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
  `secret_scanner` entry) and gave D11's "provenance hit copies the prior
  manifest forward" claim its first concrete mechanism.
- **`provenance-checker`** — all `kind: compiled`. Extracted by D39 once
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
  (`R-MERGE-003`/`015`): a sealed component's hash reflects only its
  spec, never its hand-maintained `source_path`, so trusting a hit there
  would mean never re-running the one check that could catch a human's
  own edit silently breaking something.
- **`review-packet-builder`** — all `kind: compiled`. Formats already-
  computed results; deliberately never includes the generated-code diff
  itself (principle 6). Originally depended directly on
  `verifier-orchestrator`/`license-scanner`/`secret-scanner`/
  `cache-manager` for that data; since D26, reads all of it from
  `provenance-writer`'s already-written manifest via the shared
  `component_provenance` view instead — `depends_on` dropped from 5 to 1.
- **`corpus-graph-builder`** — all `kind: compiled`. The single source of
  the `corpus-graph.json` manifest D8's traceability matrix and D9's
  docs-site-renderer both read — neither recomputes any part of it.
- **`docs-site-renderer`** — all `kind: compiled`. A pure function of
  `corpus-graph.json`; its output is deliberately never committed (D9).
- **`merge-tracker`** — all `kind: compiled`. Writes one local-only,
  gitignored record per merge attempt — success or block — directly
  queryable via DuckDB's `read_json`, no bespoke query layer (D22).
  Depends only on `provenance-writer`, not `merge-orchestrator`, despite
  being called by it — reads already-written manifests from disk instead
  of depending on `merge-orchestrator`'s own `MergeResult` type, the same
  "need the caller's facts without depending on the caller" pattern
  `review-packet-builder` already established, used here specifically to
  avoid a dependency cycle. Since D32, also writes a separate,
  full-detail `AttemptRecord` per component per merge attempt to
  `.hotdocs/attempts/` — closing the gap D31's retired best-of-k loop
  opened (a blocked merge commits no provenance at all).
- **`merge-tracker-ui`** — mostly `kind: compiled` (rendering is a pure
  function of already-written `TrackingRecord` data), one `generated-test`
  criterion for the client-side DuckDB-WASM query itself actually running
  in a real browser. Local-only, like `merge-tracker`'s own data — not a
  CI artifact the way `docs-site-renderer`'s output is, a genuinely
  different lifecycle for a genuinely different kind of data. Implements
  no retry/resume action of its own: re-running `hotdocs merge` already is
  the complete recovery path (`R-MERGE-018`), so there is nothing for this
  component to wire up beyond showing status clearly.
- **`merge-orchestrator`** — all `kind: compiled`, despite sequencing every
  model-calling, judgment-involving gate in the whole pipeline. Called
  `generator` up to `k` times per component via a diagnostic-guided
  best-of-k retry loop (D3/D17) until D31 retired that loop entirely —
  now calls it exactly once per component per merge attempt, blocking
  immediately on failure rather than retrying with feedback; a human
  reviewing D32's per-attempt record and re-running the merge is the
  only recovery path left. Wires the real `test_author`/`judge`
  callables into `verifier-orchestrator`'s call (since D30, `judge` is
  backed by `llm-endpoint`) — three responsibilities nothing had
  explicitly assigned before `generator`'s, `verifier-orchestrator`'s, and
  the blast-radius/D16 threads each forced the question. Since D16, also
  calls `capability-scenario-verifier` once every component has passed
  per-component verification; the capability-scenario dispatch logic itself
  (and the capability-intersection lookup) lived here only until D25,
  once both this component's fan-out and its spec-bundle word count
  crowded their caps at once — it was extracted into
  `capability-scenario-verifier` as the cross-component analog of
  `verifier-orchestrator`'s own per-component dispatch; this component now
  only owns *when* and *with what* that gets called. Its real, measured
  `fan_out` is 15 as of D30 (14 after D25's extraction, +1 for
  `llm-endpoint`; D39 swapped `cache-manager` for `provenance-checker`
  without changing the count) — confirmed against the actual linter, together with
  `component_doc_words` the one component besides `spec-linter` whose
  `R-LINT-022` crowding finding is real, accepted, and explained rather
  than resolved — see `specs/architecture/pipeline-decomposition.md`'s
  dedicated note.

- **`spec-completeness-assistant`** — the assist agent D1 describes but
  never names, and that two `notes/metrics.md` metrics already assumed
  existed before this spec did. Lives outside the merge pipeline entirely —
  never in `merge-orchestrator`'s dependency list, no mechanism to gate
  anything. The one component whose core value genuinely *is* judgment
  (`llm-judge` for completeness scoring and redundancy detection), not
  dispatch around it — a deliberate contrast to every coordination
  component specced so far. Since D30, dispatches through `llm-endpoint`
  rather than holding a model credential itself.
- **`capability-scenario-verifier`** — all `kind: compiled`. Extracted from
  `merge-orchestrator` by D25: the cross-component analog of
  `verifier-orchestrator`'s per-component dispatch, one scope level up —
  runs every product capability's capability scenarios whose `realizes`-set
  intersects a merge's blast radius, against the real assembled system.
  The permanent backstop for cross-component behavioral risk no
  `interface/`-level diffing can rule out in principle (D16).
- **`llm-endpoint`** — mostly `kind: compiled` (backend resolution,
  credential safety), one `generated-test` criterion for the actual
  dispatched call. Added by D30 once `generator` and `test-author` were
  each found independently coupled to `VAR-ANTHROPIC-API-KEY`, and
  `merge-orchestrator`'s `judge` wiring had no component behind it at
  all. The single vendor-agnostic transport every model call in the
  pipeline now dispatches through; v1 ships exactly one backend
  (Anthropic) by design, not as an unfinished gap (D18/D20's
  anti-premature-abstraction stance). Since D32, `model_call_error` is a
  structured `{category, message}` object, not a boolean, and every
  call writes a caller-agnostic record to `.hotdocs/calls/`.

**All 21 architecture components are now specced in full depth** (15
original + `test-author` + `spec-completeness-assistant`, both added
when earlier design discussions surfaced real gaps nothing owned yet,
+ `capability-scenario-verifier` (D25) + `llm-endpoint` (D30) +
`provenance-checker` (D39), each extracted from or added beneath
`merge-orchestrator` once a real coupling, crowding, or correctness
signal — not speculation — justified it). The real linter
(`gen/spec-linter/`) validates the entire corpus clean: 0 failures,
17 warnings — all `component_doc_words`/`requirement_count`/
`acceptance_count`/`generated_code_loc` near-misses, `merge-orchestrator`
and `spec-linter`'s `R-LINT-022` crowding findings (D28), and four
individual dense files caught by the per-file check (`R-LINT-023`,
D29). None are hard-fail-severity; see `SPEC_GUIDELINES.md` §4 for what
each warning dimension means and when (if ever) it calls for action.
