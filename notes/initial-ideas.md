# Spec-Driven Agentic Development — Initial Ideas

_Working notes. Non-normative. Date: 2026-09-10._

---

## 1. The core bet

Invert the dependency between specification and code.

- **Today:** code is the source of truth; docs are a lossy, out-of-date shadow of
  it. Intent lives in people's heads and in chat logs, and evaporates.
- **Here:** a corpus of specification documents is the source of truth and the
  thing humans edit and review. Code, tests, config, and infra are **build
  outputs** produced by coding agents. When code and spec disagree, the spec is
  right and the code has a bug.

The analogy is `spec : code :: source : compiled binary`. The difference — and
the entire engineering problem — is that the "compiler" is a nondeterministic
agent. Everything below is about making that compiler trustworthy enough to run
unattended in CI/CD.

### Why this is worth trying now

Coding agents are already reliable at **bounded, well-specified** implementation
tasks. They are unreliable at **holding a large system's intent coherent over
months**. So put the humans where the leverage is: specifying intent precisely
and keeping the specification corpus coherent. Let the pipeline do the typing.

---

## 2. What "vibe coding" gets wrong for long-term iteration

Vibe coding works great for the first week and rots fast. The failure modes:

1. **Intent is transient.** It lives in a chat transcript, then it's gone. The
   next change starts from the *code*, re-deriving intent by archaeology.
2. **Nothing small to review.** The only reviewable artifact is the code diff,
   which is larger and noisier than the intent behind it.
3. **Regeneration is impossible.** You cannot re-run a vibe. There is no
   deterministic-enough path from "what I wanted" to "what got built."
4. **Context compounds badly.** Every change carries the cost of understanding
   every prior undocumented change.

The fix is **not** "write more docs alongside the code" — that just adds a second
thing to keep in sync. The fix is to make the doc the thing you edit and the
code the thing you regenerate, with enough structural discipline that
regeneration is trustworthy.

---

## 3. Design principles

1. **Specs are normative; code is derived.** A spec/code disagreement is always a
   code bug.
2. **A spec is "done" only when an agent can execute it with zero clarifying
   questions.** Ambiguity is a defect the linter should catch.
3. **Every requirement has an agent-checkable acceptance criterion** (D5 —
   not necessarily a code test). "The
   pipeline is trusted" is exactly equivalent to "the acceptance criteria are
   strong." This is the load-bearing principle.
4. **Small, composable spec units with explicit dependencies** — not one giant
   document. The unit of change and the unit of regeneration should be small.
5. **Deterministic scaffolding around nondeterministic generation:** pinned model
   versions, frozen prompts, content-addressed caching, reproducible
   verification. Isolate the randomness.
6. **Humans review the spec diff; agents review the code diff.** No mandatory
   human review of generated code, of any kind (D5) — trust comes from the gate
   stack (compiler trust, independent generation paths, cross-model divergence,
   mutation testing), not from a person reading output.
7. **Drift is detectable and fails CI.** Hand-edits to `gen/`, generated
   interfaces that don't match the contract, requirements with no passing check —
   all hard failures, with exactly two declared, tracked exemptions and no
   others: `sealed` components (§8, component granularity) and pinned overrides
   (§8, file granularity) — both require characterization tests and visible
   provenance, never a silent exception.

---

## 4. Repository layout (first sketch)

```
specs/
  product/            # WHY: capabilities (P-id) + golden end-to-end scenarios
  architecture/       # HOW (system level): components, boundaries, data flow,
                      #                     cross-cutting tech decisions
  vars/               # env/config parameter declarations (VAR-id): name, type,
                      # required/optional, description, sensitivity — NEVER
                      # values (no such field exists) — see D12
  components/
    <component>/
      spec.md         # normative behavior for this unit
      interface.md    # public contract: types, endpoints, events, CLI
      acceptance.md   # agent-checkable criteria (D5) + test scenarios
                      # (realizes: [P-id, ...] in frontmatter — see D8)
      constraints.md  # non-functional: perf, security, compatibility
  decisions/          # ADR-style, append-only, immutable once ratified
  glossary.md         # canonical vocabulary; specs MUST use these terms
SPEC_GUIDELINES.md    # the rules every authoring/generating agent follows
gen/                  # generated code — regenerable, never hand-edited
pipeline/             # workflow definitions, frozen prompts, model pins
verification/         # spec-derived tests, contract checks, drift checks
                      # + corpus-graph.json (generated manifest, D8/D9)
notes/                # brainstorming; non-normative
```

`gen/` and `verification/` are committed on every branch (large binary assets go
through Git LFS) — see D6. The rendered docs/graph-explorer site built from
`corpus-graph.json` is a CI build artifact, not committed — see D9.

---

## 5. Anatomy of a spec document

**Frontmatter (YAML):** `id`, `title`, `status` (`draft` | `ratified` |
`deprecated`), `owners`, `depends_on` (list of spec ids), `realizes` (list of
product capability `P-id`s this component contributes to — see D8; omit only
with `sealed: true`), `uses_var` (list of `VAR-id`s from `specs/vars/` this
component reads — see D12), `supersedes`, `model_pin` (optional per-spec
override), `cross_model_divergence_check` / `fallback_standby_build` (optional
per-spec overrides of the repo-wide toggles — see D3/D10), `sealed` (boolean,
default `false` — legacy-perimeter escape hatch, §8/§9; exempts a component from
`realizes`, the D1 cold-regen invariant, and `gen/`-residency, see §8),
`source_path` (required when `sealed: true` — where the actual, hand-maintained
code lives; never under `gen/`), `last_ratified_commit`.

**Body — fixed section order:**

| Section                       | Rule                                                                                          |
| ----------------------------- | ------------------------------------------------------------------------------------------- |
| Purpose                       | One paragraph. Why this unit exists.                                                        |
| Scope                         | Explicit in-scope / out-of-scope bullets.                                                   |
| Definitions                   | Only deltas from `glossary.md`.                                                             |
| Behavior                      | Normative requirements. Each has a stable ID (`R-<comp>-001`) and uses RFC 2119 keywords.  |
| Interfaces                    | Contracts with worked examples. The generated code must match this exactly.                 |
| Data                          | Schemas, invariants, migration rules.                                                       |
| Acceptance criteria           | Each maps to ≥1 requirement ID and is **agent-checkable** — confirmable by an agent, not necessarily reducible to a code test (see D5). |
| Non-functional constraints    | With measurable targets and how they're measured.                                          |
| Open questions                | MUST be empty when `status: ratified`.                                                     |
| Change log                    | Human-readable history.                                                                     |

**Traceability invariant:** every `R-id` is traceable *forward* to at least one
acceptance criterion and *backward* to a rationale or a decision record. The
linter enforces both directions.

---

## 6. The pipeline

**Trigger:** a pull request that modifies anything under `specs/`.

1. **Spec lint.** Structure, frontmatter, RFC-2119 usage, no open questions in
   ratified specs, glossary conformance, acyclic dependency graph, and full
   traceability closure — every `R-id` covered, every `realizes` / `uses_var` /
   `depends_on` reference resolves, size caps respected. This list is
   illustrative, not exhaustive: the actual, growing rule set is decided in
   D2/D4/D8/D12 and formalized in `SPEC_GUIDELINES.md` — not re-enumerated here,
   so this step doesn't drift out of sync with them again.
2. **Impact analysis.** From the changed spec ids plus the dependency graph,
   compute the minimal set of components to regenerate.
3. **Generation.** For each impacted component, the pinned canonical model
   regenerates `gen/<component>/` from its spec bundle (`spec` + `interface` +
   `constraints` + depended-upon `interface`s + referenced `specs/vars/`
   declarations (D12) + `glossary`) — cold, with no prior code, every time this
   runs at merge time (D1). Frozen prompt, best-of-k retry against verification
   (D3). Prior code as a hint is a feature-branch-only, preview-mode affordance
   (D1) — it never substitutes for the canonical, merge-gating cold regen.
4. **Verification**, per acceptance-criterion `kind` and the D3/D10 toggles:
   - `compiled` criteria run through the deterministic compiler (D4); `generated-
     test` and `llm-judge` criteria get an independent second path when the D3
     toggle is enabled and a second model is configured (D5/D10).
   - Contract/property tests derived from `interface.md` and `Data`; a drift
     check that the generated interface matches `interface.md` exactly.
   - Cross-model divergence check (D3), when enabled.
   - License scan (D7) and secrets scan (D12) — both automated and
     unconditional, strictly tracked regardless of the D3 toggle state.
   - Non-functional gates where feasible (benchmarks, size budgets).
5. **Review packet.** The pipeline emits a human-readable summary: the spec
   diff, which requirements changed, which components regenerated, verification
   results, residual risk, any license/secret-scan flags (D7/D12, surfaced even
   when auto-resolved), and whether the merge was a cache hit (D11). The human
   reviews **this and the spec diff**, not the code.
6. **Merge.** `specs/`, `gen/`, and `verification/` (including the
   `corpus-graph.json` manifest, D8/D9) update atomically in one squashed
   commit.

---

## 7. Verification is the crux

The system is only as trustworthy as the closing of the gap between "spec says X"
and "code does X." Techniques, roughly in order of value:

- **Double-entry bookkeeping, per criterion kind (D5), not a blanket rule.**
  `compiled` criteria are checked by a deterministic compiler — no second model
  needed, the compiler itself is the trusted, hand-maintained party. `generated-
  test` and `llm-judge` criteria get a genuinely independent second
  model/path (D3/D5); disagreement there blocks the merge as a spec-ambiguity
  signal, to be resolved by tightening the spec — not by picking a winner.
- **Executable acceptance criteria where possible.** Prefer `compiled`, then
  `generated-test` — code tests are strictly stronger evidence than judgment.
  Reserve `llm-judge` for qualities no test could capture even in principle
  (D5).
- **Property-based testing** from invariants in `Data` / `Interfaces`.
- **Golden end-to-end scenarios** from product specs, run against the whole
  assembled system.
- **Metamorphic checks** where a true oracle is hard (e.g. "reordering inputs
  doesn't change the result").
- **Requirement coverage, not line coverage.** Every `R-id` must have a passing
  check or CI fails.
- **Mutation testing on the generated tests** to catch vacuous / tautological
  ones.

---

## 8. Hard problems to harden against

| Problem | Sketch of mitigation |
| --- | --- |
| **Nondeterministic churn** — regen produces diffs with no spec change. | Only regenerate impacted units; content-address the generation cache by spec-bundle hash; accept code-diff noise since humans don't read it; pin models. |
| **Silent underspecification** — agent fills a gap without telling anyone. | Generation agent MUST emit a machine-readable list of assumptions it made; any assumption fails CI until it's folded into the spec or explicitly waived. |
| **Legacy / large code** that can't be regenerated wholesale. | Component-scoped adoption. "Sealed" components (`sealed: true`) get a spec that says only "matches existing behavior; do not regenerate" plus characterization tests. **Their actual code lives at `source_path`, outside `gen/` entirely** — `gen/` is reserved for cold-regen-governed output, so a sealed component's hand-maintained code is never subject to principle 7's "no hand-edits to `gen/`" rule or D1's cold-regen invariant (which excludes sealed components explicitly). Its characterization tests still live in `verification/<component>/` the normal way — wrapping legacy code in traceability/verification doesn't require rewriting it. |
| **Cross-component incoherence** — every local spec correct, system still wrong. | Architecture-level acceptance scenarios; contract tests at every boundary. |
| **Model drift** — the pinned model is deprecated or changes. | Per-spec model pin; bumping it is a re-ratification event gated by full regen + verification. |
| **Non-functional work** agents are weak at (perf, concurrency, security-critical). | Keep as constraints with benchmarks. Where a human-authored override is genuinely needed, it's a **pinned override**, not a silent exception to principle 7 or D1: declared in `gen/<component>/.overrides.json` (exempted file paths, rationale, owner), still requires characterization tests in `verification/` (the same bar `sealed` components meet), and is visible in the D9 node view and tracked as a debt metric (`metrics.md`) — the file-granularity version of the same escape hatch `sealed`/`source_path` is at component granularity, not a second, unreconciled mechanism. |
| **Review burden shifts, doesn't vanish.** Reviewing a precise spec is real work. | Accept it. It's smaller, more durable, and more reusable than reviewing code. |
| **Incident debugging** — is this a spec bug or a generation bug? | The D7 provenance manifest gives a hard answer (exact spec-bundle hash, model, prompt version, sample index behind any `gen/` output); reproduce against acceptance criteria first. |
| **Concurrent spec edits / merge conflicts.** | Small spec units; treat `specs/` merges like code merges; re-run lint + impact on the merge result. |
| **Non-spec-driven change** (dependency bumps, runtime upgrades). | A separate lane that regenerates + re-verifies without a spec diff; if verification stays green, merge. |
| **Secrets, environment config, infra-as-code** — specs are plain text, committed, and constantly read/written by agents; secrets must never land in them. | Secrets: an automated, strictly-tracked scan, same shape as the license gate (D12). Config *contracts* (not values) are spec-driven via `specs/vars/` (D12); values and infra provisioning stay out of scope. |
| **Pinned-model unavailability** — D1 makes cold regen mandatory at every merge; if the pinned model is deprecated or has an outage, every merge repo-wide blocks. | A second model, when configured, already produces a passing build every merge (D3/D10) and gets promoted to canonical on confirmed outage — no dormant fallback. With only one model available, merges halt; accepted as rare (D10). |

---

## 9. Adoption path

1. One greenfield component inside an existing repo — `specs/` + `gen/` living
   next to hand-written code.
2. Expand component by component as trust builds.
3. Wrap the legacy perimeter in sealed specs.
4. Never require a whole-repo conversion.

---

## 10. What to prototype first, in this repo

1. `SPEC_GUIDELINES.md` — the actual, enforceable rules.
2. A spec template and one small-but-real example project (candidates: a CLI
   tool, a small HTTP API, a parser/formatter).
3. The spec linter.
4. The generation + verification pipeline as local scripts first, then CI.
5. **The measurement that matters:** can we make a spec change, run the pipeline,
   and get correct code plus green verification with **zero human code edits**?
   Find where it breaks. Iterate there.

---

## 11. Decisions (resolved from open questions)

### D1 — Cold regen is the contract; hint mode is a feature-branch tool

The relationship between cold regeneration and prior-code-as-hint is governed by
the **git branching strategy**, not chosen once globally.

- **Feature branches use hint mode freely.** It is a fast, low-compute *preview*
  of how a spec change affects the product, so developers can iterate on the
  specs without paying for full regeneration each time.
- **Hint mode is also an input to the spec-authoring agents.** The assistant
  agents that help a developer land a *complete* spec change — dependencies
  updated, no logical discrepancies, no redundancies — use the hint-mode preview
  to evaluate completeness before merge.
- **Hard invariant:** 100% of the **spec-driven** generated code on `main` must
  have undergone a full **cold regen** since the last change to the underlying
  documents. Explicitly scoped to exclude `sealed` components (§8/§9) — a
  sealed component is, by definition, not meant to be regenerated at all, so it
  can't be measured against a regeneration invariant. Its trust model is
  characterization tests in `verification/`, not cold regen; see the
  `sealed`/`source_path` clarification added to §8.
- **Cold regen is part of every merge into `main`** from a feature branch, gated
  by the full verification suite.
- **Developers can run a cold regen on any part of the repo on demand** during
  development, not only at merge time.

### D2 — Component granularity

**Hard splitting trigger: verifiability.** If a component's full public behavior
cannot be captured by *complete*, agent-checkable acceptance criteria (D5 —
`compiled`, `generated-test`, and `llm-judge` all count toward completeness; a
component isn't oversized just because some of its behavior is legitimately
judgment-based rather than test-based), it is too big and must be split. This is
the non-negotiable rule.

Secondary sizing inputs, applied within what the trigger allows:

- **Cohesion** — a typical spec change stays inside the component's own bundle
  and does not force an edit to a depended-upon `interface.md`.
- **Context ceiling** — spec bundle + dependency interfaces fit inside the
  generation model's reliable-output budget with margin (empirical; loosens as
  models improve).
- **Ownership** — tiebreaker: prefer the boundary that lands on a single owner.

**`architecture/` owns the decomposition.** The list of components and the
boundaries between them live in `architecture/` specs. Splitting or merging
components is a distinct, heavier, explicitly-reviewed operation — a refactor of
the spec corpus, not a normal change.

**Flat component namespace** + explicit dependency graph. No nested components
(nesting makes it ambiguous where behavior is specified). `architecture/`
expresses subsystems and grouping.

**Size caps** — educated first guesses, tunable, enforced by the linter:

| Dimension | Target (warn above) | Hard fail above |
| --- | --- | --- |
| Generated code per component | 800 LOC | 1500 LOC |
| Spec bundle (`spec` + `interface` + `acceptance` + `constraints`) | 2000 words | 4000 words |
| Requirements (`R-id`s) per component | 20 | 40 |
| Public interface surface elements (endpoints / fns / events / types) | 10 | 20 |
| `depends_on` count (fan-out) | 7 | — (warn only) |
| Dependents count (fan-in) | 10 | — (warn only) |

The interface-churn ratio that motivated these caps is tracked as a corpus-health
metric — see [`metrics.md`](metrics.md).

### D3 — Single generation model, no voting, divergence checked pre-merge

Ensembling the *generation* step can't raise the correctness ceiling —
verification already defines that (D1 + the independent-path double-entry tests
in §7). Model diversity is only worth paying for where it affects **throughput**
(first-pass success) or **spec hardening** (catching ambiguity). Three
mechanisms, judged separately:

- **Voting (majority output) — rejected.** Code isn't votable; many correct
  implementations differ textually, and majority doesn't mean correct.
- **Canonical generation = one pinned model, one frozen prompt.** Defines the
  reproducible `gen/`, cached by (spec-bundle hash, prompt version, model pin).
- **Best-of-k retry against verification** — accepted. If the first sample fails,
  draw up to k−1 more from the *same* model (varied seed) before failing the
  merge; keep the first that passes; record the winning sample index so it's
  reproducible. Small k (2–4).
- **Cross-model divergence check — a pre-merge gate, not a scheduled job, and
  toggleable, not mandatory.** Two independent preconditions, not one: a second
  model must be *configured*, **and** the check must be explicitly *enabled* —
  `cross_model_divergence_check: enabled | disabled`, set repo-wide in
  `pipeline/` with an optional per-component frontmatter override (same
  override pattern as `model_pin`). Default: enabled whenever a second model is
  configured, but a team can turn it off repo-wide or per-component — having a
  second model around for other reasons (D10's fallback, say) doesn't force
  paying for this gate everywhere. When enabled and a second model is
  configured: on every merge, for each impacted component (already scoped by
  impact analysis — §6 step 2), also regenerate with that second, different
  model. If that build **passes the same verification suite but is behaviorally
  divergent** from the canonical build (differential testing against the
  acceptance suite / fuzzed inputs), the merge is **blocked** as a spec defect —
  the acceptance criteria don't pin the behavior tightly enough. If the second
  model's build simply *fails* verification, that is not blocking by itself (a
  capability gap in the second model, not necessarily a spec bug) but is
  logged. Cost is bounded because it only applies to components already in the
  blast radius of the change. When the check is off (no second model
  configured, or explicitly disabled), this layer of defense is simply absent
  — tracked via the **multi-model coverage rate** metric (`metrics.md`), which
  now measures a *verified standby build* being available, not mere model
  configuration (see D10) — so its absence is visible, not silent. A second
  model from a **different vendor** than the canonical pin is a recommended
  best practice (reduces correlated-outage/correlated-blind-spot risk), not a
  requirement.
- This reuses directly for **model-pin migration**: "does candidate model X
  pass every component's verification?" is the readiness gate for bumping a
  pin (itself a re-ratification event, per §8).

### D4 — Acceptance criteria: constrained Given/When/Then, not prose or raw test files

Rejected the pure forms: **tagged prose** alone can't be mechanically checked for
traceability (only an LLM's judgment call, which undermines "independent path"
agreement as evidence) and **literal test files** are code — hand-authoring them
in `specs/` would blur the line that `specs/` is never executable, and couples
specs to one stack/framework.

- `acceptance.md` constrains each criterion to a **Given/When/Then block** with a
  required `Covers: <R-id>` field. This is readable as plain English in a spec
  diff *and* mechanically parseable — the linter checks "every block covers a
  real `R-id`, every `R-id` has ≥1 block" with a real parser, no LLM judgment
  needed.
- **Reuse actual Gherkin syntax** for the structured subset (embedded as
  Gherkin-style blocks inside the markdown `acceptance.md`, tagged
  `@covers:R-<id>`), rather than inventing a bespoke grammar — mature parsers
  and tooling already exist for it.
- Where Given/When/Then can express the criterion (the majority), it **compiles
  deterministically** to test scaffolding — no LLM in that step, which is what
  makes the independent-generation-path agreement in §7 meaningful.
- Where it can't (fuzzy, UX, some non-functional criteria), it stays freeform
  prose and the test-generation agent fills the gap — an explicit, *tracked*
  degraded path, not treated the same as the mechanically-compiled majority.
- **Generated tests live in `verification/`, never in `specs/`.** `specs/`
  stays non-executable even for generated artifacts; `verification/` output is
  regenerable under the same cold-regen/caching discipline as `gen/`.
- New metric (added to `metrics.md`): % of acceptance criteria requiring
  freeform LLM interpretation vs. mechanically compiled — a corpus-health
  signal, not a gate.

### D5 — Acceptance has three mechanisms; code tests are one of them

Reframe: **acceptance criteria are a guide for an agent to confirm that what was
specified was achieved.** Generating a code test is one way to do that, not the
definition of "machine-checkable." Not everything worth specifying reduces to a
runtime test of generated code — e.g. "this spec is properly hardened," "this
document has no internal contradictions," are legitimate acceptance criteria
with no code to execute at all. Every criterion declares a `kind`:

| Kind | What checks it | When to use it |
| --- | --- | --- |
| `compiled` | Deterministic compiler, from structured Given/When/Then (D4) | Default for runtime behavior of generated code — strongest evidence, use whenever the criterion fits the grammar. |
| `generated-test` | Agent-written test code from freeform prose, executed thereafter like any other test | Runtime behavior that resists the Given/When/Then grammar but is still fundamentally "does the code do X." |
| `llm-judge` | An agent evaluates the criterion directly against an artifact (a spec document, a review packet, `gen/` output) — no code produced | Qualities that aren't runtime behavior at all: spec hardening/completeness, absence of contradiction, clarity, tone/style conformance. |

All three still require `Covers: <R-id>` — the traceability invariant doesn't
bend per kind.

**No mandatory human review of generated code**, for any kind. Trust instead
comes from mechanisms that were already decided and now get reused rather than
supplemented with a review gate:

- `compiled` — trust the compiler, which is hand-maintained pipeline
  infrastructure (not agent output), reviewed and versioned like any critical
  infra, never generated by the agentic pipeline itself.
- `generated-test` — independent generation path (different model than the code
  under test, when the D3 toggle is enabled and a second model is configured) +
  mutation-score bar (80% / 90% for freeform-derived, per the earlier draft) +
  the cross-model divergence gate (D3) when it's on, which now explicitly
  covers divergence in generated tests, not just in `gen/` code.
- `llm-judge` — **reuse D3's divergence mechanism when it's enabled:** run the
  judgment with two independent models; disagreement
  blocks the merge as a signal that either the criterion or the artifact is
  ambiguous, not as a quality score to tune. **In single-model mode, the single
  configured model judges alone** — no disagreement gate for that criterion.
  Always require structured rationale output for traceability/debugging (§8
  incident tracing); the rationale is for audit, never a review gate, in either
  mode.

**Guidance on picking a kind:** prefer `compiled`, then `generated-test`,
whenever the criterion is in principle about runtime behavior — code tests are
strictly stronger evidence (deterministic, reproducible) wherever they apply.
Reach for `llm-judge` only for criteria no code test could capture even in
principle. This is also the mechanism that makes "the specs are rock solid"
(the project's founding premise) a checked property rather than an assumption —
it's recursive: `llm-judge` criteria are how agents confirm *other specs* are
hardened enough to trust for cold regen.

New metrics (added to `metrics.md`): **`llm-judge` criteria ratio** and
**judge disagreement rate**, parallel to the compiled-vs-freeform metric from
D4.

### D6 — `gen/` and `verification/` are committed, always, with an LFS exception

Settled, not a toss-up — it follows from decisions already made rather than a
fresh tradeoff:

- The usual reason to `.gitignore` build output is to avoid a second,
  potentially-stale source of truth. **D1 already makes that impossible on
  `main`**: cold regen is mandatory at every merge, so whatever's committed
  there is always fresh by construction.
- The usual cost of committing generated output is repo bloat from iterative
  regeneration churn. **§6 already neutralizes that**: merges into `main` are
  squashed, so all feature-branch hint-mode iteration collapses into one clean
  commit and never pollutes `main`'s permanent history.

So: **`gen/` and `verification/` are committed on every branch, no exceptions**
for ordinary generated source — this gets real `git bisect` / `git blame` on
`main`, self-describing commits, offline work, and simple deploys (checkout and
run, no pipeline dependency at deploy time). It also avoids depending on exact
reproducibility of generation, which D3's best-of-k retry already doesn't
guarantee unless the winning artifact itself is what's stored.

**Exception: large generated binary assets go through Git LFS**, not a plain
blob commit, to keep plain-text diffing and clone size sane for the actual
source-like output.

### D7 — Provenance manifest + automated, strictly-tracked license gate

Split into two kinds of question, resolved differently:

**Provenance (engineering — settled outright).** Every generated artifact
carries a manifest alongside it, committed under the same D6 discipline:

```
gen/<component>/.provenance.json   (and verification/<component>/)
  spec_bundle_hash   — content hash of every spec file that fed generation
  model_pin          — model id + version
  prompt_version     — id of the frozen prompt template used
  sample_index       — which best-of-k sample won (D3)
  pipeline_version   — version of the generation pipeline itself
  generated_at
  verification_run_id
  cross_model_check  — divergence-gate outcome (D3/D5)
  license_scan       — result of the check below
```

This is the hard evidence trail for incident tracing (§8) and doubles as an
SBOM/SLSA-style attestation if the code ships as a product.

**Licensing/copyright risk (a compliance question — technical control only,
legal ownership/copyrightability questions are explicitly out of scope for an
engineering doc and belong with counsel).** Decided: the license/similarity
scan is a **fully automated verification gate** — same shape as the other
gates in §7/D3/D5, no legal sign-off required to pass. A flag above the
similarity threshold blocks the merge the same way a failed test does, and the
pipeline can retry generation (same best-of-k spirit as D3) without escalating
to a person.

But — **every flag is strictly tracked and communicated, whether or not it
ends up blocking the merge:**

- Every scan result (clean or flagged) is written into `license_scan` in the
  provenance manifest — an append-only record, not just a CI log line that
  disappears.
- Flags are surfaced as an explicit line item in the review packet (§6 step 5)
  even though no human sign-off gates the merge — visibility after the fact is
  mandatory, silence is not acceptable for this category.
- A flag above a severity threshold (not just "blocked the merge") triggers an
  explicit notification to a standing compliance/legal channel — separate from
  the merge outcome, so a flag that got auto-resolved by retry still gets seen.
- Tracked as a metric with trend visibility for stakeholders (added to
  `metrics.md`): **license-scan flag rate**, by component and over time.

This keeps the "no mandatory human review" precedent (D5) intact for
*correctness* while treating *compliance* as a different category that still
must never be silent, per your instruction.

### D8 — Product/component reconciliation: linkage is lint-checked, composition is golden-scenario-verified

Two different jobs; one must not stand in for the other.

1. **The matrix is bookkeeping** — a mechanical, lint-level check that declared
   linkage is complete. It catches *missing or dangling links*, nothing more.
2. **Golden end-to-end scenarios (§7) are verification** — they prove the
   linked components actually compose correctly. Only an end-to-end run can
   catch "local specs correct, system wrong" (§8).

Mechanism:

- `specs/product/` capabilities get stable IDs (`P-<id>`) and their own
  Given/When/Then golden scenarios (D4's format, any of D5's three `kind`s),
  exercised **black-box against the whole assembled system**.
- Component specs get a new frontmatter field, **`realizes: [P-<id>, ...]`** —
  coarse (component-level, not per-`R-id`) to stay within the D2 size caps.
- **The matrix is generated, never hand-maintained** — a view over
  `verification/corpus-graph.json` (the same manifest D9 builds the docs site
  from, so this isn't a second artifact), computed by walking
  `P-id → realizing components → R-ids → acceptance criteria → verification
  status`, regenerated every merge and committed under D6.
- **New lint rules:** every `P-id` has ≥1 realizing component (no orphan
  capability); every `realizes` entry references a real `P-id` (no dangling
  link); every component has ≥1 `realizes` entry unless explicitly
  `sealed: true` (the legacy-perimeter escape hatch, §9).
- Refines the `metrics.md` orphan-rate entry into two precise, gate-able
  metrics: **orphan-capability rate** and **orphan-component rate**.

### D9 — Generated graph/documentation explorer

An interactive, auto-generated documentation site over the whole spec corpus —
never hand-authored, always a rendering of structured data the pipeline already
produces.

- **Interactive DAG** of the corpus: nodes are product capabilities and
  components (optionally clustered by `architecture/` subsystem); edges are
  `depends_on` (D2) and `realizes` (D8). Clickable, searchable.
- **Per-node detail view**, assembled entirely from existing artifacts — no new
  generation step needed, this is a pure renderer:
  - Rendered `spec.md` / `interface.md` / `acceptance.md` / `constraints.md`.
  - `R-id` list with live coverage/pass-fail status.
  - Acceptance criteria broken out by `kind` (D5) with current verification
    result.
  - Provenance (D7): model pin, prompt version, last cold-regen timestamp,
    freshness relative to the D1 invariant.
  - Size vs. the D2 caps, color-coded warn/fail.
  - Verification-toggle state (`cross_model_divergence_check`,
    `fallback_standby_build` — D3/D10) actually in effect for this component,
    so a viewer can see *why* a gate didn't run, not just that it didn't.
  - Declared exemptions from the normal cold-regen discipline: whether the
    component is `sealed` (with its `source_path`) or carries file-level
    pinned overrides (`.overrides.json`) — §8/principle 7 — each with its
    characterization-test status.
  - Owners.
- **Corpus-health dashboard** surfacing the live, computable numbers from
  `metrics.md` directly — turns that catalog from a document agents consult
  into a page people look at too.
- **Data source:** a single generated **corpus graph manifest**
  (`verification/corpus-graph.json`) — one machine-readable snapshot of the
  whole corpus (nodes, edges, statuses, provenance, metrics) that the D8
  traceability matrix is also a view over, not a second artifact.
- **Build cadence:** regenerated on every merge to `main`, same as everything
  else — it's a cheap render over data the pipeline already computed, no model
  call involved, so there's no reason for it to lag behind `main` the way a
  scheduled job would (consistent with the Q3/Q7 preference for pre-merge over
  scheduled).
- **What's committed vs. built:** the manifest JSON is committed under D6 (cheap,
  text, diffable, useful to other tooling beyond the docs site itself). The
  *rendered* static HTML/JS site is a build artifact — built in CI from the
  manifest and deployed to a docs host — not committed, the same way you
  wouldn't commit a compiled website for a typical static-site generator.

**Settled:** manifest committed, rendered site built-not-committed; rebuilt
every merge, not on a schedule.

### D10 — Single-model operation must work; the fallback is opportunistic, not guaranteed

The tool must keep functioning with only **one** model configured — D3's
cross-model check and D5's `llm-judge` disagreement check are therefore
best-effort and, as of D3's toggle, independently switchable rather than
automatic whenever a second model exists. That toggle has a direct consequence
here: "a second model is configured" no longer automatically implies "a
verified standby build exists to promote." Three regimes, not two:

- **`cross_model_divergence_check: enabled`** (D3's default when a second model
  is configured) — the divergence check already regenerates and verifies a
  second-model build every merge as a side effect of its own job. That build is
  the fallback candidate, continuously exercised, never dormant. If the primary
  pin is confirmed unavailable (N consecutive failed calls, or an explicit
  vendor status signal), the pipeline **promotes it to canonical** for the
  duration — no new config surface. Recorded in the D7 provenance manifest,
  with an explicit notification to a standing ops channel the moment it
  engages. Once the primary is restored, fallback-produced components
  re-verify against it asynchronously; a permanent deprecation promotes the
  fallback model to primary as an ordinary model-pin bump (§8).
- **`cross_model_divergence_check: disabled`, but a standing fallback is still
  wanted** — a separate, cheaper toggle, **`fallback_standby_build: enabled`**:
  the pipeline still generates and verifies (but doesn't diff or gate on) a
  second-model build every merge, purely to keep a promotable spare warm,
  without paying for the divergence comparison itself. This is the explicit way
  to buy the availability benefit without the ambiguity-detection cost.
- **Both disabled (or no second model configured at all)** — no standby build
  exists. An outage of the only configured model **halts merges** until a human
  re-ratifies a working pin. Accepted as rare, and now an explicit,
  eyes-open tradeoff a team can make for lower cost rather than a side effect of
  not having a second model lying around.
- **A second model from a different vendor is a recommended best practice**
  (reduces correlated-outage risk) in any of the three regimes — not a
  requirement.
- **Multi-model coverage rate** (`metrics.md`) is redefined to measure what
  actually matters: % of merges with a **verified, promotable standby build**
  available (regime 1 or 2) — not merely "a second model was configured," which
  the toggle means is no longer the same thing.

### D11 — Rollback is a cache-hit, not a dedicated incident feature

No special "incident mode." A spec revert that returns the corpus to a
byte-identical prior state produces the same `spec_bundle_hash` that an earlier,
already-verified commit produced — which means it's **a cache hit across the
entire gate stack** (generation, D3 cross-model, D5 `llm-judge`, D7 license
scan) under the same content-addressed caching D13 establishes generally, not a
feature built specifically for incidents. Nothing new to invoke under pressure,
nothing dormant that might be broken when it's finally needed.

- A merge whose spec bundle exactly matches a prior verified state restores the
  matching `gen/`, `verification/`, and provenance artifacts directly — no
  regeneration, no re-verification.
- **Still unconditional:** the human spec-diff review (D1/§6). A cache hit
  skips compute, never review.
- **Safety net:** even on a cache hit, the §8 "non-spec-driven change" lane
  re-runs **asynchronously, non-blocking**, afterward — the spec matching
  exactly doesn't guarantee the *environment* it runs against still does
  (dependency/infra drift since).
- **Visibility:** the review packet notes when a merge was a full cache hit.
- **Discipline this requires:** a gate's `gate_version` must bump whenever its
  underlying detection logic changes (e.g. the license-scanner's signature
  database), so a stale cache hit never papers over a genuinely changed risk —
  a rule for `SPEC_GUIDELINES.md`, already covered by `gate_version` being part
  of the cache key.

### D12 — Secrets never in scope; config *contracts* are, config *values* aren't; `specs/vars/`

Corrects an earlier over-broad answer: "config is out of scope" conflated
config *values* (rightly excluded) with config *contracts* — the name, meaning,
and required/optional-ness of a parameter — which belongs in the spec corpus
like anything else a component's behavior depends on.

- **Secrets — unconditional, not a scope question.** Never in `specs/`, `gen/`,
  or `verification/`. An automated secret-pattern scan (same shape as D7's
  license scan: no human sign-off to clear, every flag strictly tracked and
  communicated) runs pre-merge-gate and, where tooling allows, as early as
  pre-commit/pre-push.
- **New area: `specs/vars/`**, parallel to `product/`/`architecture/`/
  `components/`. Each entry declares a parameter by name — `required` /
  `optional`, a type (`string`, `url`, `connection-string`, `secret-ref`,
  `integer`, `enum`, …), a description, and a **`sensitivity: secret |
  non-secret`** classification. **There is no `value` field in the schema at
  all** — not a convention to leave it blank, it has nowhere to go.
- **Anything marked `secret` structurally forbids an `example`/`default`
  field** — closes off "someone pastes a real-looking example" at the schema
  level, with the secret scanner as the second layer underneath.
- **Components declare `uses_var: [VAR-<id>, ...]`** in frontmatter (mirrors
  `realizes`/`depends_on`) — they reference the declaration, never redefine it,
  avoiding the same variable getting inconsistently described across multiple
  components' `constraints.md`.
- **Component behavior toward configuration is ordinary spec territory**: "if
  `DATABASE_URL` is missing, fail fast with error X" is a normal `R-id` with a
  normal acceptance criterion, same as anything else.
- **Still out of scope:** the actual deployment-time values (conventional
  secrets manager / env files / CI secret store) and infra-as-code/provisioning
  itself (Terraform, K8s manifests) — this is about declaring the *shape* of
  configuration, not pulling deployment automation into the spec corpus.
- **Lint:** every `uses_var` entry must reference a real declaration (no
  dangling refs). A declared-but-unused var is a **soft metric**
  (orphan-var rate), not a hard fail — some config is legitimately
  global/infra-level without tying to one component (same posture D2 took on
  fan-in/fan-out).
- Slots into D9 for free: the graph explorer gets a new node type (vars) with
  edges to the components that use them.

### D13 — Merge cost is already bounded by D1+D2; cache, parallelize, and treat cost as a D2 signal

The premise that the full gate stack runs on every tiny edit doesn't hold: **D1**
already makes iteration cheap (hint mode on feature branches; the full stack
runs once, at merge, not per edit), and **D2** already bounds the ceiling
(impact analysis scopes a merge's cost to touched components; size caps bound
how expensive any one component's gates can get). So the real question narrows
to "is the cost of one PR's merge low enough to not pressure batching unrelated
changes into it" — answered with three additions, not a more aggressive
tiered-verification scheme:

1. **Content-addressed caching across every gate**, not just generation —
   cache key `(spec_bundle_hash, artifact/gate-inputs hash, gate_version,
   model_pin)`, applied to generation, D10's cross-model/judge checks, and D7's
   license scan alike. This is the mechanism D11's rollback-as-cache-hit relies
   on. Mainly pays off for reverts/duplicate work, a secondary win.
2. **Parallelize independent gates within a merge** — canonical generation, the
   cross-model check, and the license scan have no sequential dependency on
   each other given the same inputs. Cuts wall-clock latency (what a developer
   feels) even where it doesn't cut total spend.
3. **Rising merge cost/latency is a corpus-health signal, not a problem for more
   pipeline cleverness.** A consistently expensive or slow component is
   evidence it's oversized or over-coupled — feeds back into D2's existing
   size-cap enforcement rather than spawning new cost-cutting machinery. Cheap
   merges are a *consequence* of good component boundaries.

### D14 — `glossary.md` stays a single file; splitting is a bounded-context decision, not a size response

Reversed my own initial recommendation here (sharding by a D2-style size cap).
That was a category error: components are split *because* separability is the
goal (independent regeneration, independent ownership); a glossary's entire
purpose is the opposite — one canonical definition for terms used *across*
components. Sharding by namespace would reintroduce the scattered-definition
problem a glossary exists to prevent.

- `glossary.md` stays a single file by default, **no size-based sharding
  rule**. Glossaries grow sublinearly with corpus size (new components mostly
  reuse existing terms), and even a large one stays a small, greppable text
  file — nowhere near D2's caps, which exist for a different reason (generation
  context budget), not lookup cost. Edits are overwhelmingly additive, so
  merge-conflict risk stays low without any special handling.
- The only legitimate reason to split it is a genuinely separate bounded
  context — two subsystems that don't share vocabulary — made as a deliberate
  `architecture/`-level decomposition decision (same tier as splitting
  components, D2), never as a routine response to word count.
- Glossary size is tracked as a visibility metric (`metrics.md`) so growth
  doesn't go unnoticed, but isn't lint-gated.

---

## 12. Open questions

_None outstanding — Q9–Q13 from the review pass are now D10–D14._

Also fixed in the original review pass (not decisions, just drift that had
accumulated as D1–D9 landed): §3 principle 6, §6 step 3, and §7's
double-entry/executable-criteria bullets no longer matched D1/D3/D4/D5 —
reworded to match. §8 gained new rows for secrets/config scope (D12) and
pinned-model unavailability (D10), plus a tightened incident-debugging
mitigation pointing at D7. D8/D9 no longer imply two separate generated
manifests.

---

## 13. Naming

Repo is `hotdocs`. The methodology needs a name — candidates: "spec-as-source",
"normative development", "documents-first". Decide later; it doesn't matter yet.
