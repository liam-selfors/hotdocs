# Trackable Metrics — Running List

_Working notes. Non-normative. Started: 2026-09-10._

A premise of spec-driven agentic development: **metrics are first-class citizens
of the spec corpus**, not an afterthought bolted on by an observability team.
Developers, stakeholders, and the system's own agents should be able to reference
high-level metrics at every phase — ideation, specification, review, generation,
verification, release, and production operation — to inform their decisions.

This file is a growing catalog. Most entries are still candidates — nothing
about *computing* them is decided (where definitions live, how agents query
them, dashboards vs. trend lines). A subset, though, are no longer speculative:
where an entry is tagged `[gate]` *and* already grounded in a concrete
mechanism described in
[`initial-ideas.md`](initial-ideas.md) (orphan rates/`D8`, license-scan flag
rate/`D7`), the gate itself is settled — only its dashboarding/trend-reporting is
still open.

Four metrics that used to live in this catalog — multi-model coverage rate,
cross-model divergence incidents, second-model verification-failure rate, and
judge disagreement rate — were removed outright rather than left as
currently-zero placeholders: each measured a mechanism this build doesn't
have (the second-model features removed in the single-model scope cut, and a
"run `llm-judge` twice and compare" check that was never actually built in
the first place). Carrying them here as inert entries risked reading as
settled tracking for gates that don't exist. The underlying ideas are kept
in [`initial-ideas.md`](initial-ideas.md) §14 ("Future enhancements"), not
lost — re-add them here if and when the mechanisms they measure return.

Consumer tags: `[dev]` developer · `[stk]` stakeholder · `[agt]` system agent ·
`[gate]` candidate hard CI gate.

---

## Corpus health (cross-cutting)

- **Requirement coverage ratio** — % of `R-id`s with ≥1 passing acceptance
  check. Target 100%. `[gate] [agt] [dev] [stk]`
- **Spec completeness** — % of `ratified` specs with zero open questions and a
  clean lint pass. `[gate] [dev]`
- **Orphan-capability rate** — product capabilities (`P-id`) with no realizing
  component. `[gate] [agt] [stk]`
- **Orphan-component rate** — components with no `realizes` entry and not
  marked `sealed` — no declared product reason to exist (per `D8`).
  `[gate] [agt] [dev]`
- **Orphan-var rate** — declared `specs/vars/` parameters with no component
  `uses_var` reference (per `D12`). Soft signal, not a gate. `[agt] [dev]`
- **Glossary conformance** — undefined-term occurrences per spec. `[agt]`
- **Glossary size** — word/entry count over time. Visibility only, not gated —
  a split is a deliberate bounded-context call, never a size response (`D14`).
  `[dev] [stk]`
- **Ambiguity density** — linter-flagged ambiguous phrases per 1000 words of
  spec. `[agt] [dev]`
- **Dependency graph health** — max fan-in, max fan-out, cycle count (must be
  0), graph diameter. `[agt] [dev]`
- **Interface-churn ratio** — interface-changing PRs vs. internal-only PRs, per
  component and overall. High ratio ⇒ component boundaries are wrong.
  `[dev] [stk]`
- **Component size distribution** — count of components over soft / hard caps
  (see [`initial-ideas.md`](initial-ideas.md)'s own size-cap discussion,
  `D2`). `[gate] [dev]`
- **Spec churn** — edits per spec per time window; surfaces unstable specs.
  `[dev] [stk]`
- **Sealed-component ratio** — % of components that are sealed (legacy
  perimeter) vs. fully spec-driven. Adoption progress. `[stk]`
- **Cold-regen freshness** — for each component, time since last underlying-doc
  change vs. time since last successful cold regen. `[gate] [agt]`

---

## Ideation phase

- **Idea → ratified-spec conversion rate** and **latency**. `[stk]`
- **Predicted blast radius** of a proposed change — components impacted, `R-id`s
  touched — computed before work starts. `[dev] [stk] [agt]`
- **Overlap / duplication score** — does this proposal restate behavior already
  specified elsewhere? `[agt] [dev]`
- **Open-question burn-down** during ideation — raised vs. resolved. `[stk]`
- **Estimated generation cost** of the proposal (tokens / $ / wall-clock) from
  predicted blast radius. `[stk]`

---

## Specification / authoring phase

- **Time-in-draft** — duration a spec sits in `draft` before `ratified`.
  `[dev] [stk]`
- **Clarifying-questions count** — questions the authoring agent had to ask, or
  assumptions it surfaced, per spec revision. Trend toward zero. `[agt] [dev]`
- **First-submission lint pass rate**. `[dev]`
- **Completeness-agent confidence** — the assist agent's own score that a spec
  change is complete (deps updated, no discrepancies, no redundancy). `[agt]`
- **Hint-mode preview delta** — size of the preview change vs. expectation; large
  unexpected deltas suggest an incomplete or wrong spec edit. `[agt] [dev]`
- **Normative-statement density** — RFC-2119 keyword count per section; flags
  under-specified sections. `[agt]`
- **Mechanically-compiled vs. freeform acceptance criteria** — % of criteria
  expressible as structured Given/When/Then (deterministically compiled) vs.
  requiring freeform LLM interpretation to become executable. High
  freeform % ⇒ specs are under-formalized (per `D4`). `[agt] [dev]`
- **`llm-judge` criteria ratio** — % of acceptance criteria whose `kind` is
  `llm-judge` rather than `compiled` / `generated-test` (per `D5`). Should stay
  low for components with testable runtime behavior; high ratio there is a
  signal the spec is reaching for judgment where a real test should exist.
  `[agt] [dev]`
- **Review iterations per spec PR**. `[dev]`

---

## Review & merge phase

- **Spec-diff review time** — human minutes per changed `R-id`. `[dev] [stk]`
- **Review packet size** — components regenerated, `R-id`s changed,
  residual-risk items. `[dev]`
- **Merge-blocked rate and reasons** — lint fail, verification fail, cold-regen
  fail, unwaived assumption. `[gate] [dev]`
- **Assumption-waiver count** — assumptions explicitly waived rather than folded
  into the spec. A debt metric. `[stk] [dev]`
- **Pinned-override file count** — human-authored exemptions declared in
  `gen/<component>/.overrides.json` (per §8/principle 7). A debt metric,
  parallel to assumption-waiver count — tracks how much of `gen/` is outside
  the normal cold-regen discipline, file by file. `[stk] [dev]`

---

## Generation phase

- **Cold-regen first-pass success rate** — % of components that regenerate to
  passing verification on their one attempt. Since `D3` retired automatic
  retry, this is now simply "did the merge's one generation call for this
  component pass" — no within-merge retry exists to qualify it against.
  `[gate] [agt] [stk]`
- **Merge attempts to green** — of components that blocked at least once,
  how many separate merge attempts (not samples — `D3` retired same-merge
  retry entirely) it took before that component passed. `[agt]`
- **Generation determinism / churn** — diff size between two cold regens of the
  same unchanged spec bundle under the same model pin. Should trend to zero.
  `[agt] [dev]`
- **Cache hit rate** — model calls avoided via `cache-manager`'s
  content-addressed cache, per gate. Since `D29`, this no longer means
  a component was skipped — that's **provenance hit rate** — `gen/`
  components short-circuited entirely via `provenance-checker`'s
  committed-`.provenance.json` match, the actual instance of `D11`'s
  "restore a prior verified state" claim. `[dev] [stk]`
- **Generation cost & latency** — tokens, $, wall-clock, per component and per
  merge. `[stk]`
- **Surfaced-assumption count per generation** — gaps the agent had to fill.
  Must be 0 for `ratified` specs; nonzero ⇒ spec bug. `[gate] [agt]`
- **Hint-mode vs. cold-regen divergence** — how often the feature-branch preview
  differs materially from the final cold regen. `[agt] [dev]`
- **Correction cycles per merge** — of a blocked merge later followed by a
  passing one touching an overlapping component set, how many attempts it
  took to go green (D10, `merge-tracker`). **Computed from `.hotdocs/tracking/`
  via time-proximity + component-overlap between consecutive records, not an
  explicit link** — `TrackingRecord` doesn't mark one attempt as "the retry
  of" another (nothing at write time reliably knows that), so this is a
  heuristic query over already-written records, not a guaranteed-precise
  count. `[agt] [dev]`
- **Blocked attempts resolved by a plain re-run vs. requiring a spec
  edit** — since `D3` retired automatic retry, every recovery from a
  blocked component is now a *separate* merge attempt, and the one
  question actually worth asking is whether the spec changed in between:
  a plain re-run with an unchanged `spec_bundle_hash` recovering means
  the failure was transient (bad luck, not a spec problem); recovery only
  after a `spec_bundle_hash` change means a human genuinely found and
  fixed something. Computed from `.hotdocs/attempts/` (`D19`) joined
  against `merge-tracker`'s cross-merge sequence — a high rate of
  unchanged-spec-hash recovery is the generation-noise baseline to
  expect; a low rate (most recoveries require a spec edit) is a signal
  this corpus's specs are frequently underspecified, not that the
  pipeline is unreliable. `[gate] [agt]`

---

## Verification phase

- **Per-run requirement coverage** — see corpus health. `[gate]`
- **Independent-path agreement rate** — how often code-from-spec and
  tests-from-spec agree without human intervention. Disagreement = spec
  ambiguity signal. `[gate] [agt]`
- **Mutation score on generated tests** — % of injected faults caught. Guards
  against vacuous / tautological tests. `[gate] [agt]`
- **Property / metamorphic check pass rate** and **flakiness**. `[agt] [dev]`
- **Contract-drift incidents** — generated interface ≠ the `interface/`
  contract (D1). `[gate] [dev]`
- **Capability-scenario pass rate** — the D2 merge-time gate's own pass/fail
  rate, per capability and over time; a sustained failure cluster on one
  capability flags a recurring cross-component composition risk that
  interface-level checks alone aren't catching. `[gate] [stk]`
- **Guarantee-narrowing adoption rate** — % of `depends_on` edges that have
  been narrowed via `depends_on_guarantees` vs. left at the coarse,
  whole-`interface/` default (D2). Low adoption isn't a problem by
  itself (the coarse default is always safe) — it's a signal of how much
  blast-radius precision is still on the table. `[dev] [stk]`
- **Non-functional gate results vs. targets** — latency, size budgets, security
  findings. `[gate] [stk]`
- **License-scan flag rate** — generated-code similarity-to-licensed-training-
  data flags, by component and over time, whether or not the flag ultimately
  blocked a merge (per `D7`). Every flag is tracked and communicated, never
  silent. `[gate] [stk]`
- **Verification runtime and cost** per merge. `[stk]`
- **Flaky-check rate** — checks with non-deterministic pass/fail. `[dev]`

---

## Release phase

- **Lead time for a spec change** — ratified spec edit → deployed. Core velocity
  metric. `[stk] [dev]`
- **Change failure rate** — % of releases that cause an incident. `[stk]`
- **Cold-regen freshness at release** — proof that 100% of `gen/` on `main` was
  cold-regenerated since the last doc change (D1 invariant, scoped to exclude
  `sealed` components and `.overrides.json`-pinned files). `[gate]`
- **Rollback rate** and **MTTR**. `[stk]`
- **Release size** — `R-id`s changed, components touched. `[dev] [stk]`

---

## Operation / production feedback phase

- **Incident cause classification** — spec bug vs. generation bug vs.
  verification gap. Tells you which layer to harden. `[stk] [agt] [dev]`
- **Symptom → `R-id` trace time** — how long to map a production symptom back to
  a requirement. `[dev]`
- **Spec-gap discovery rate** — production incidents that reveal a missing or
  ambiguous requirement, per time window. `[stk] [agt]`
- **Post-incident spec-edit latency** — how fast the fix lands as a spec change.
  `[dev] [stk]`
- **Behavioral drift** — production behavior vs. capability acceptance scenarios,
  tracked over time. `[agt] [stk]`

---

## Agent-effectiveness meta-metrics

Metrics about the system's own agents, not the product being built.

- **Per-agent success / retry / cost / latency**, by role (authoring assist,
  generation, test generation, review, impact analysis). `[stk] [agt]`
- **Human-intervention rate per phase** — where humans still have to step in.
  `[stk]`
- **Autonomy ratio** — % of spec PRs that reach `main` with zero human code
  edits. The headline claim of the whole methodology. `[stk] [dev]`
- **Assist-agent acceptance rate** — how often a developer accepts vs. overrides
  the authoring agent's completeness suggestions. `[agt] [dev]`
