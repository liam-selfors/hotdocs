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
3. **Every requirement has a machine-checkable acceptance criterion.** "The
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
   all hard failures.

---

## 4. Repository layout (first sketch)

```
specs/
  product/            # WHY: capabilities (P-id) + golden end-to-end scenarios
  architecture/       # HOW (system level): components, boundaries, data flow,
                      #                     cross-cutting tech decisions
  components/
    <component>/
      spec.md         # normative behavior for this unit
      interface.md    # public contract: types, endpoints, events, CLI
      acceptance.md   # machine-checkable criteria + test scenarios
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
with `sealed: true`), `supersedes`, `model_pin` (optional per-spec override),
`last_ratified_commit`.

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
   ratified specs, glossary conformance, acyclic dependency graph, every `R-id`
   covered by an acceptance criterion, no dangling `depends_on`.
2. **Impact analysis.** From the changed spec ids plus the dependency graph,
   compute the minimal set of components to regenerate.
3. **Generation.** For each impacted component, the pinned canonical model
   regenerates `gen/<component>/` from its spec bundle (`spec` + `interface` +
   `constraints` + depended-upon `interface`s + `glossary`) — cold, with no
   prior code, every time this runs at merge time (D1). Frozen prompt, best-of-k
   retry against verification (D3). Prior code as a hint is a feature-branch-only,
   preview-mode affordance (D1) — it never substitutes for the canonical,
   merge-gating cold regen.
4. **Verification.**
   - Spec-derived tests, generated by an **independent path** (different
     prompt/model) from `acceptance.md`.
   - Contract/property tests derived from `interface.md` and `Data`.
   - Drift check: generated interface must match `interface.md` exactly.
   - Non-functional gates where feasible (benchmarks, size budgets, static
     security checks).
5. **Review packet.** The pipeline emits a human-readable summary: the spec diff,
   which requirements changed, which components regenerated, verification
   results, and residual risk. The human reviews **this and the spec diff**, not
   the code.
6. **Merge.** `specs/` and `gen/` update atomically in one squashed commit.

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
| **Legacy / large code** that can't be regenerated wholesale. | Component-scoped adoption. "Sealed" components get a spec that says only "matches existing behavior; do not regenerate" plus characterization tests. |
| **Cross-component incoherence** — every local spec correct, system still wrong. | Architecture-level acceptance scenarios; contract tests at every boundary. |
| **Model drift** — the pinned model is deprecated or changes. | Per-spec model pin; bumping it is a re-ratification event gated by full regen + verification. |
| **Non-functional work** agents are weak at (perf, concurrency, security-critical). | Keep as constraints with benchmarks; allow human-authored `gen/` overrides that are explicitly pinned and carry their own mini-spec. |
| **Review burden shifts, doesn't vanish.** Reviewing a precise spec is real work. | Accept it. It's smaller, more durable, and more reusable than reviewing code. |
| **Incident debugging** — is this a spec bug or a generation bug? | The D7 provenance manifest gives a hard answer (exact spec-bundle hash, model, prompt version, sample index behind any `gen/` output); reproduce against acceptance criteria first. |
| **Concurrent spec edits / merge conflicts.** | Small spec units; treat `specs/` merges like code merges; re-run lint + impact on the merge result. |
| **Non-spec-driven change** (dependency bumps, runtime upgrades). | A separate lane that regenerates + re-verifies without a spec diff; if verification stays green, merge. |
| **Secrets, environment config, infra-as-code** — specs are plain text, committed, and constantly read/written by agents; secrets must never land in them. | *Pending — see Q11 in §12.* |
| **Pinned-model unavailability** — D1 makes cold regen mandatory at every merge; if the pinned model is deprecated or has an outage, every merge repo-wide blocks. | *Pending — see Q9 in §12.* |

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
- **Hard invariant:** 100% of the generated code on `main` must have undergone a
  full **cold regen** since the last change to the underlying documents.
- **Cold regen is part of every merge into `main`** from a feature branch, gated
  by the full verification suite.
- **Developers can run a cold regen on any part of the repo on demand** during
  development, not only at merge time.

### D2 — Component granularity

**Hard splitting trigger: verifiability.** If a component's full public behavior
cannot be captured by *complete* machine-checkable acceptance criteria, it is too
big and must be split. This is the non-negotiable rule.

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
- **Cross-model divergence check — a pre-merge gate, not a scheduled job.**
  Underspecified specs must be caught *before* they merge, not audited after.
  So on every merge, for each impacted component (already scoped by impact
  analysis — see §6 step 2), also regenerate with a second, different model. If
  that build **passes the same verification suite but is behaviorally divergent**
  from the canonical build (differential testing against the acceptance suite /
  fuzzed inputs), the merge is **blocked** as a spec defect — the acceptance
  criteria don't pin the behavior tightly enough. If the second model's build
  simply *fails* verification, that is not blocking by itself (a capability gap
  in the second model, not necessarily a spec bug) but is logged.
  Cost is bounded because it only applies to the components already in the
  blast radius of the change, not the whole repo.
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
  under test) + mutation-score bar (80% / 90% for freeform-derived, per the
  earlier draft) + the cross-model divergence gate (D3), which now explicitly
  covers divergence in generated tests, not just in `gen/` code.
- `llm-judge` — **reuse D3's divergence mechanism directly**: run the judgment
  with two independent models; disagreement blocks the merge as a signal that
  either the criterion or the artifact is ambiguous, not as a quality score to
  tune. Require structured rationale output for traceability/debugging (§8
  incident tracing), but the rationale is for audit, never a review gate.

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

This keeps the "no mandatory human review" precedent (Q5) intact for
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

---

## 12. Open questions

_Populated by the review pass below — none of these were in the original
brainstorm._

**Q9 — Pinned-model unavailability is a single point of failure.** D1 makes
cold regen mandatory at every merge. If the pinned model is deprecated or has
an outage, *every* merge across the whole repo blocks — there's no fallback.
Recommendation: allow a declared **fallback `model_pin`** that only activates
when the primary is confirmed unavailable (not a soft preference). Any merge
produced under the fallback is flagged in the D7 provenance manifest and
required to re-verify against the primary once it's restored, rather than being
silently treated as equivalent forever.

**Q10 — No incident/rollback fast path.** The per-merge gate stack is heavy:
cold regen + best-of-k + cross-model divergence + possible `llm-judge`
dual-model runs + license scan + docs rebuild. Reverting a bad production
change under incident pressure shouldn't have to pay all of that again.
Recommendation: a spec revert that returns the corpus to a byte-identical prior
state should be allowed to **restore the prior commit's already-verified
`gen/`/`verification/` artifacts directly** (matched via the D7 provenance
manifest) rather than regenerating from scratch — it's already known-good. The
full pipeline still re-validates asynchronously afterward, non-blocking, in
case something environment-dependent changed since.

**Q11 — How much of secrets/config/infra is in scope?** Specs are plain text,
committed, and constantly read/written by agents — secrets must never appear in
them. Config and infra-as-code are a gray zone. Recommendation: **out of scope
for v1.** Spec-driven generation targets application code; infra/config stays
conventionally managed. Add a hard linter rule to `SPEC_GUIDELINES.md` — scan
`specs/`, `gen/`, and `verification/` for secret-shaped strings, same mechanism
as the D7 license scanner, blocking regardless of scope questions.

**Q12 — Per-merge pipeline cost is in tension with "small, frequent changes"
(§3 principle 4).** Multiple model calls per merge (canonical gen, best-of-k,
cross-model check, possible `llm-judge` dual runs, license scan) creates
pressure to batch spec edits to amortize cost — working against the small-unit
principle the whole design leans on. Recommendation: extend the
content-addressed caching already assumed for generation (§8) to **every
gate** — cross-model divergence, `llm-judge` runs, license scan — keyed by
(spec-bundle hash, artifact hash, gate version), so an unrelated spec change
never re-pays for a gate whose inputs didn't change.

**Q13 — `glossary.md` is a single global file** — exactly the "one giant
document" shape §3 principle 4 warns specs away from. Low priority, but cheap
to decide now rather than retrofit later. Recommendation: allow sharding into
`glossary/<namespace>.md` once it crosses a D2-style size cap, with a single
generated merged view for lookups and the linter.

Also fixed in this pass (not decisions, just drift that had accumulated as D1–D9
landed): §3 principle 6, §6 step 3, and §7's double-entry/executable-criteria
bullets no longer matched D1/D3/D4/D5 — reworded to match. §8 gained the two
rows above plus a tightened incident-debugging mitigation pointing at D7. D8/D9
no longer imply two separate generated manifests.

---

## 13. Naming

Repo is `hotdocs`. The methodology needs a name — candidates: "spec-as-source",
"normative development", "documents-first". Decide later; it doesn't matter yet.
