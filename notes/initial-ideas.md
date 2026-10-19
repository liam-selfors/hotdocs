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
      component.md     # root: frontmatter (realizes: [P-id,...] — D8) +
                       # Purpose/Scope/Definitions/Open questions/Change log
      requirements/    # one R-id per file (D15 — superseded the original
                       # single-file spec.md Behavior section)
      interface/       # cli.md / library.md / data/<Type>.md (D15 —
                       # superseded the original single-file interface.md)
      acceptance/      # one AC-id per file, agent-checkable (D5) — (D15 —
                       # superseded the original single-file acceptance.md)
      constraints.md   # non-functional: perf, security, compatibility —
                       # stays one file, see D15 for why
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

**Since D15: this frontmatter lives only on a component's root file
(`component.md`), and the body's Behavior/Interfaces/Data/Acceptance
criteria sections are pointers to `requirements/`/`interface/`/`acceptance/`
directories, not the content itself** — `SPEC_GUIDELINES.md` §2–3.4 is the
current, authoritative version; what follows is the original, pre-D15
design, kept for history.

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
   when auto-resolved), whether the merge was a cache hit (D11), and any new or
   changed `sealed` / `.overrides.json` declarations (principle 7/§8) — a
   declared exemption from the normal discipline is exactly the kind of thing a
   reviewer should see called out, not buried in a frontmatter diff. The human
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
- **Hint mode is also an input to the spec-authoring agents** — concretely,
  `spec-completeness-assistant` (`specs/components/spec-completeness-
  assistant/`), which uses the hint-mode preview to evaluate completeness
  — dependencies updated, no logical discrepancies, no redundancies —
  before a change is even submitted for merge. Advisory only; it has no
  mechanism to block anything, which is exactly what keeps the real gates
  (lint, verification, compliance scans) the sole source of merge truth.
- **Hard invariant:** 100% of the **spec-driven** generated code on `main` must
  have undergone a full **cold regen** since the last change to the underlying
  documents. Explicitly scoped to exclude both of principle 7's declared
  exemptions: `sealed` components (component granularity) and files declared in
  a `.overrides.json` pinned override (file granularity) — §8/§9. Neither is
  meant to be regenerated at all, so neither can be measured against a
  regeneration invariant; their trust model is characterization tests in
  `verification/`, not cold regen.
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
- `generated-test` — independent generation path (an author independent of
  however the code under test came to exist: a different model, when the
  code under test is itself agent-generated and the D3 toggle is enabled and
  a second model is configured; or a human author, when the code under test
  is hand-maintained — `criterion-compiler`'s own tests are exactly this
  second case, found while actually specifying a sealed component, which the
  original "different model" framing didn't account for) + mutation-score bar
  (80% / 90% for freeform-derived, per the earlier draft) + the cross-model
  divergence gate (D3) when it's on, which now explicitly
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
  gate_versions      — per-gate version map (e.g. {compiler, license_scanner,
                       cross_model_check, mutation_harness, secret_scanner}) —
                       the actual cache-key granularity D11/D13 need; a single
                       pipeline_version can't express "only the license
                       scanner's signature DB changed"
  cache_hit          — bool; if true, verification_run_id/cross_model_check/
                       license_scan below are copied from the matching prior
                       commit (D11), not freshly computed this merge
  generated_at
  verification_run_id
  cross_model_check  — divergence-gate outcome (D3/D5)
  license_scan       — result of the check below
  secret_scan        — result of D12's secret scan (added here to match
                       SPEC_GUIDELINES.md §8 — missing from this sketch
                       even though gate_versions already expected a
                       secret_scanner entry; found while specifying
                       provenance-writer)
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

**D7 addendum — block and severity are orthogonal, not two cutoffs on one
score.** Left open in the original draft ("a flag above a *severity*
threshold" never said what severity was *of*, relative to the
merge-blocking threshold); resolved while specifying `license-scanner` and
`secret-scanner`:

- **Block** is a *confidence* question — is this match certain enough to
  stop the merge? A single score/threshold, as originally designed.
- **Severity** is a *risk* question — if the match is real, how bad is it?
  Not a function of confidence at all. Each reference-corpus entry
  (license-scanner) or pattern-database rule (secret-scanner) carries its
  own **`risk_tier`** (`high`/`medium`/`low` — license family for one,
  credential-shape specificity for the other).
- **Notification fires when:** `(the match blocked the merge) OR (the
  matched entry's risk_tier is "high", regardless of confidence)`. This
  captures the real asymmetry a same-scale reading misses in both
  directions: a high-confidence match to a low-risk (permissive-license,
  say) reference doesn't need to page anyone just because it's confident;
  a lower-confidence match to a high-risk reference (copyleft/unknown-
  license, or a recognizable credential shape) is worth surfacing even
  when the pipeline isn't sure enough to hard-block.

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
  scheduled job would (consistent with the D3/D7 preference for pre-merge over
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
   model_pin)`, applied to generation, D10's cross-model/judge checks, D7's
   license scan, and D12's secrets scan alike. This is the mechanism D11's rollback-as-cache-hit relies
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

### D15 — One file per addressable unit, not one file per document type

Replaces the original four-flat-files component anatomy (§5) — `spec.md` /
`interface.md` / `acceptance.md` / `constraints.md` — with:

```
components/<component>/
  component.md          # root: frontmatter + Purpose/Scope/Definitions/
                         # Open questions/Change log + pointers
  requirements/R-<comp>-NNN.md   # one Behavior requirement per file
  interface/
    cli.md
    library.md
    data/<TypeName>.md   # one schema/type per file
  acceptance/AC-<comp>-NNN.md    # one criterion per file
  constraints.md          # stays one flat file
```

Arose from a blast-radius question (how should `impact-analyzer` tell an
`interface.md` *contract* change from a cosmetic edit without full semantic
diffing?) that, on examination, generalized into a better answer than the
question asked: **every unit already independently addressed elsewhere in
the corpus — a requirement via `Covers:`/`realizes`, a criterion via
`Covers:`, an interface section via the drift check — should be its own
file**, so content hashing for blast-radius/cache-key purposes is *exact*
rather than approximated by parsing block boundaries inside a shared file.

- **Frontmatter lives only on `component.md`.** Every unit file carries
  none at all — its filename is its identity, nothing left to declare. This
  is simpler than the rule it replaced ("only `spec.md` has the full field
  set, the other three carry `id`/`title`/`status`/`owners`"), not just
  different.
- **`constraints.md` stays one flat file**, deliberately not split like the
  other three — nothing in the corpus addresses one individual constraint
  by id, so there's no reference-granularity reason to pay the extra-file
  cost there.
- **Readability and tooling concerns are answered by assembly, not by
  keeping one big file.** `spec-bundle-assembler` — whose whole job was
  already "assemble a component's files into one payload" for machine
  consumption — gained a human-readable flattened-view mode, the same
  operation with a different serializer. `corpus-graph-builder`/
  `docs-site-renderer` consume that flattened view and never need to know
  the split happened.
- **A real quality side effect, not just a structural one:** `spec-linter`'s
  block-boundary regex parsing (`_requirement_blocks()` and similar) —
  exactly the kind of parsing that caused a real bug during its own
  bootstrap (the RFC-2119 check missing multi-line continuations) —
  is replaced by directory listing, which can't have that class of bug by
  construction.
- **Scope decided explicitly:** extends to `spec.md`'s requirements and
  `acceptance.md`'s criteria (both independently addressed by id elsewhere,
  same reasoning as `interface.md`'s sections), but not to `constraints.md`
  (no such addressing exists for it) and not to `specs/vars/`'s declarations
  (already one file per variable, nothing further to split) or
  `specs/product/`'s golden scenarios (kept inline per capability file for
  now — fewer of them per file in practice, lower cost from leaving them
  as-is).

This is a genuine redesign, not a refinement — it touched every existing
component's file layout, `spec-linter`'s actual implementation and test
suite, and several components' specs that referenced the old file names
directly (`spec-bundle-assembler`, `impact-analyzer`, `criterion-compiler`,
`corpus-graph-builder`). See `SPEC_GUIDELINES.md` §1–§5 for the current,
authoritative rules this produced.

### D16 — Behavioral guarantees are part of the contract; golden scenarios are a permanent backstop, not a transitional one

Arose from a single thread of questions about `impact-analyzer`'s blast
radius: should `transitive-var`/`transitive-capability` inclusion cascade
beyond one hop? The answer settled on — **no, stay one-hop** — only holds
up once two real gaps it exposed are closed. Both are closed here,
together, because neither alone was sufficient.

**Gap 1: nothing ever actually ran golden scenarios.** `SPEC_GUIDELINES.md`
§3.1 and D8 both describe golden scenarios as "exercised black-box against
the whole assembled system," but no component had a requirement to
actually execute them — stated intent with nobody assigned to do it, the
same shape of gap `test-author` and `spec-completeness-assistant` each
turned out to be. **Fixed:** `merge-orchestrator` gains a new gate — once
every component in the blast radius has regenerated and passed its own
per-component verification, run every product capability's golden scenarios
whose `realizes`-set intersects the blast radius, against the real
assembled `gen/` output, blocking the merge on failure the same way a
per-component failure does (`SPEC_GUIDELINES.md` §6 step 6). This is the
backstop for cross-component behavioral risk no amount of interface-level
diffing can rule out *in principle* — permanently, not just until gap 2 is
closed, because documentation of foreseeable guarantees can never be
complete (the same irreducible-ambiguity-residual this methodology accepts
everywhere else, per principle 2).

**Gap 2: a component's real contract with its dependents isn't only
types.** Worked example: swapping `cache-manager`'s backing store from a
single-node store to a distributed one can leave every type signature
identical and every drift check green, while quietly changing a
consistency guarantee (`R-CACHE-003`'s "last-write-wins is safe because
writers are deterministic") that a dependent (`cross-model-divergence-
checker`) actually relies on — invisible to blast radius because the
guarantee lived in `requirements/`, which dependents never even receive
(`spec-bundle-assembler` only hands out `interface/`). **Fixed:** `interface/`
gains a fourth kind, `interface/guarantees/G-<comp>-NNN.md` — one
behavioral/non-functional guarantee per file, exactly the one-file-per-unit
convention D15 already established, now extended to behavioral contract
content, not just types. A change to a declared guarantee propagates via
the ordinary `interface/` file-level mechanism `impact-analyzer` already
has (generalized, per below) — no new propagation machinery needed, because
the fix is making more of the real contract *visible* to that machinery,
not making the machinery cleverer.

**The narrowing mechanism, and why it's safe.** A new optional field,
`depends_on_guarantees: [G-<comp>-NNN, ...]`, lets a dependent declare
*which specific* guarantees of a dependency it relies on — tightening its
own blast-radius inclusion to only those guarantees changing, instead of
any file under the dependency's `interface/` changing. This is **strictly
opt-in narrowing**, never the only path: a component that doesn't declare
it still gets the safe, coarse default (any `interface/` file change
propagates, same as every other interface content). The real risk this
field introduces — a component under-declaring, claiming reliance on fewer
guarantees than it actually has, producing a false-negative blast-radius
miss — is the *reason* gap 1's golden-scenario gate stays permanent rather
than being treated as superseded once guarantees are explicit: an
under-declaration is exactly the kind of wrong-but-locally-plausible spec
claim golden scenarios exist to catch when it manifests as real cross-
component breakage. This mirrors D10's precedent directly — a refinement is
safe to add precisely because it never replaces the safe default, only
sits on top of it.

- **`impact-analyzer`'s R-IMPACT-002/003 generalize** from enumerating
  `interface/cli.md`/`library.md`/`data/*.md` by name to "any file under
  `interface/`, compared independently" — not just to accommodate
  `guarantees/`, but so any *future* `interface/` file type is covered
  without another edit.
- **Reference resolution**: `depends_on_guarantees` entries must resolve to
  a real `G-id` whose owning component is already in this component's own
  `depends_on` — referencing a guarantee of something you don't depend on
  is meaningless, not just unresolved.
- `cache-manager`'s `R-CACHE-003` was retrofitted into `G-CACHE-001` as the
  worked demonstration, with `cross-model-divergence-checker` declaring
  `depends_on_guarantees: [G-CACHE-001]` as the concrete example of
  narrowing in practice.

See `SPEC_GUIDELINES.md` §1–§3.4 and §6 step 6 for the current,
authoritative rules this produced.

---

### D17 — Diagnostic-guided retry: feed best-of-k failed-requirement ids back, via graph topology, not test content

Arose from the working-queue's item 6 (best-of-k's exact value), which
turned into something more fundamental after a round of challenges to a
first, weaker proposal.

**The dead ends, in the order they were ruled out.** First framing: drop
best-of-k, treat a single generation failure as evidence of an underspecified
requirement rather than retrying. Rejected — a failure is frequently a
generation miss on an otherwise-adequate spec, and discarding retry entirely
would push real spec-authoring overhead onto every transient miss. Second
framing: let a retry see the *prior attempt's code* as hinted context, so it
edits toward the spec instead of re-rolling blind — proposed as "surely this
is just an extension of cold regen, not a cold-then-warm sequence." Challenged
and conceded: the real test for whether something is safe to feed back
isn't "within one merge vs. across merges," it's whether the fed-back
information is **derivable from the current spec bundle alone**. Prior code
fails that test — it's external, potentially-stale state, exactly
`hint_code`'s risk (D1), not a new category. Third framing, after accepting
that: feed back which specific acceptance criteria failed, including their
Gherkin text. Challenged again, more sharply: this doesn't just risk the
cold/warm line, it reopens `spec-bundle-assembler`'s R-ASSEMBLE-001 exclusion
of `acceptance/` from what a generation model ever sees — the whole reason
that exclusion exists (not overfitting generation to specific test
assertions) applies exactly as much to *retry* feedback as to a first
attempt's bundle. No clean fix was found at the AC-content level: any amount
of acceptance-criteria-adjacent detail leaking through reopens the same risk
in degree, not in kind.

**The resolution, proposed by the user: lean on graph topology.** Every
acceptance criterion already declares `Covers: R-<id>` — the same
traceability edge `R-LINT-008`/`009` enforce and `corpus-graph-builder`
already materializes, nothing new. Project each criterion's own pass/fail
result onto the `R-id`(s) it covers (AND-aggregated: any failing *or
skipped* covering criterion makes that requirement `fail` — "not yet
demonstrated" and "demonstrated wrong" both mean "not verified"), and feed
back **only that projection** — a bare `{R-id: pass|fail}` map, never
Gherkin text, `rationale`, or expected/actual values. This cleanly resolves
all three objections at once: it's derivable entirely from the current spec
bundle plus the current sequence's own output (passes the cold-mode test);
it discloses nothing beyond "your attempt didn't satisfy text you already
had" (a requirement's normative text is already in the model's bundle via
`requirements/`, regardless of which `kind` of criterion covers it), so it
can't be used to reverse-engineer a specific test assertion (passes the
overfitting test); and it's still concrete enough to turn a blind re-roll
into a targeted edit (stays useful).

**What got built:**
- `verifier-orchestrator` gains `R-VERIFY-011`: `VerificationReport`'s new
  `requirement_results` field, computed by the graph projection above.
  Deliberately a stricter rule than `overall`'s own skip-handling
  (R-VERIFY-005) — a requirement with even one skipped covering criterion
  is `fail` here, because "safe to retry against" is a higher bar than
  "safe to report as the merge verdict."
- `generator` gains `R-GEN-010`: an optional `retry_feedback` parameter
  (bare `R-id` list), explicitly not an exception to cold-mode rules
  (R-GEN-001's clarification), folded into the cache key (R-GEN-005) so a
  fed-back retry can never collide with a blind retry sharing the same
  seed. `generator` itself is purely a pass-through — it doesn't decide
  *whether* to retry, only accepts the hint when told to.
- `merge-orchestrator`'s existing best-of-k loop (R-MERGE-005) now extracts
  the immediately preceding attempt's failing `R-id`s and passes them as
  the next attempt's `retry_feedback`, unchanged and uninterpreted. Feedback
  is **not accumulated** across more than one prior attempt — only the
  immediately preceding attempt's failures count, so a requirement fixed two
  attempts ago doesn't keep steering later attempts away from content
  already corrected.
- **`k`'s default is resolved**: 2 (`R-MERGE-016`) — one blind attempt, one
  informed retry — not the wider 2–4 range D3 originally left open. Informed
  retries capture most of "try again"'s value in a single pass; a third or
  fourth attempt buys much less once the retry is no longer blind. A new
  `best_of_k` frontmatter field (mirroring `model_pin`'s pattern) lets a
  specific component opt into a higher `k` when its requirements are
  unusually numerous or interdependent.
- Provenance (`SPEC_GUIDELINES.md` §8) gains a `retry_feedback` field
  alongside `sample_index`, for the same audit reason: reconstructing why a
  winning attempt looks the way it does requires knowing whether it was
  informed by a prior failure or produced blind.

See `SPEC_GUIDELINES.md` §2 (`best_of_k` row), §8 (provenance schema), and
`specs/components/{generator,verifier-orchestrator,merge-orchestrator,
provenance-writer}/` for the current, authoritative rules this produced.

---

### D18 — `criterion-compiler`: single fixed emit target for v1, formalized as a two-phase split

Resolved item 7 (canonical target test framework for emitted scaffolding).
Single fixed target (`pytest`) for v1 is confirmed — no multi-target
machinery designed in now, consistent with this project's own
anti-premature-abstraction stance (no plugin/registry mechanism for a
second target nobody has asked for yet).

What made this safe to decide quickly: the step-phrase grammar
(`specs/architecture/step-phrase-grammar.md`) was already written in
target-independent terms before this question was ever raised — each
template's "compiles to" column describes a bound fact ("a call to the
named function," "an equality assertion on `result.<path>`"), never
literal pytest syntax. New `R-COMPILE-011` makes that separation — parse+bind
(grammar matching, `interface/` resolution) vs. emit (literal source text for
one `--target`) — a formal requirement rather than an implicit property, and
requires any `--target` other than `pytest` to fail as a specific usage
error (exit `2`), never a silent fallback. A future second target is
therefore an additive emitter function, not a grammar rework or a change to
`R-COMPILE-001`–`010`.

See `specs/components/criterion-compiler/requirements/R-COMPILE-011.md` and
`interface/cli.md` for the current, authoritative rule this produced.

---

## 12. Open questions

_None outstanding — Q9–Q13 from the review pass are now D10–D14; D15 was a
redesign triggered by resolving blast-radius item 3 from a later working
session, not an open question left over from the original brainstorm._

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
