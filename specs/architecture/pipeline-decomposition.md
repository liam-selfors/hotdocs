---
id: arch-pipeline-decomposition
title: Pipeline Decomposition
status: draft
owners: [pipeline-team]
depends_on: [P-ZERO-EDIT, P-AMBIGUITY-GATE, P-COMPLIANCE-GATE]
---

# Pipeline Decomposition

## Purpose

This repository's own pipeline — the thing that lints, generates, verifies,
and merges spec changes for *any* adopting project — is itself a spec-driven
application. This document is where its component decomposition is declared,
per `SPEC_GUIDELINES.md` §3.2: the only place that decomposition is allowed to
change.

## Components

| Component | Purpose | `depends_on` |
| --- | --- | --- |
| `spec-linter` | Structural/traceability/size-cap checks over a spec bundle. Pure, deterministic, no model calls. | — |
| `impact-analyzer` | From changed spec ids + the dependency graph, computes the minimal set of components to regenerate — now fully specced, including the interface-vs-internal-change distinction (`component.md`/`requirements/`/`constraints.md`/`acceptance/` changes stay local; `interface/cli.md`/`library.md`/`data/*.md`/`specs/vars/`/capability changes always propagate; `interface/guarantees/*.md` changes propagate too, but **narrowably** — opt-in per-dependent via `depends_on_guarantees`) that an early, informal sizing note previously stated only as a heuristic, never as an executable rule — and, since D1, computed as plain file-level hashing rather than needing bespoke section parsing (each `interface/` file already is its own hash boundary). | `spec-linter` |
| `spec-bundle-assembler` | Assembles a component's full generation input (`component.md` + `requirements/` + `interface/` + `constraints.md` + dependency `interface/` content + referenced vars + glossary — deliberately excluding `acceptance/`, to avoid the generation model overfitting to its own tests) into one payload. Reused by canonical generation and hint-mode previews. Fully specced. | `spec-linter` |
| `criterion-compiler` | Deterministic Gherkin → test-scaffolding compiler for `compiled`-kind acceptance criteria. Two-phase by requirement (R-COMPILE-011): parse+bind (grammar matching, `interface/` resolution — target-independent) then emit (literal source text for one `--target`). v1 ships exactly one emitter, `pytest`; any other `--target` is a usage error, never a silent fallback. | — |
| `generator` | Produces **exactly one candidate** `gen/<component>/` per call, given a `SpecBundle` and an explicit model identifier (never a hardcoded "canonical pin"). Single-shot and stateless about prior attempts, deliberately — and since `D3` retired the best-of-k retry loop that used to call it again on a verification failure, no caller ever calls it more than once per attempt. Since `D91`, called only internally by `component-gate-runner` (itself called by `provenance-tracker`'s `hotdocs build`, `D92`) — this component's own standalone CLI retired, since nobody had a reason to call just this narrower step directly. Since D18, dispatches its model call through `llm-endpoint` rather than holding a vendor credential itself. Fully specced. | `spec-bundle-assembler`, `cache-manager`, `llm-endpoint` |
| `test-author` | Authors the test code for one `generated-test`-kind criterion — the independent-generation-path principle, given a real component for the first time. Invoked by `verifier-orchestrator` via an injectable callable — same pattern `llm-judge`'s `judge` parameter already established. Single-model (`R-AUTHOR-003`): independence comes from authoring the test from spec prose alone, with no access to the implementation under test. Since D18, dispatches through `llm-endpoint`. Fully specced. | `spec-bundle-assembler`, `cache-manager`, `llm-endpoint` |
| `verifier-orchestrator` | Runs per-criterion verification (`compiled` via the compiler, `generated-test` via `test-author`, `llm-judge`) plus contract/property tests and the interface drift check. Its own coordination logic is 100% `compiled` — dispatching to judgment-involving mechanisms is itself deterministic. **Never re-decides a criterion's declared `kind`** — that stays fixed at spec-authoring time, lint-checked, normative. Fully specced. | `criterion-compiler`, `generator`, `test-author` |
| `license-scanner` | Automated, unconditional license/similarity scan — k-gram/shingle hashing against a reference corpus, fully deterministic. Fully specced. | `cache-manager` |
| `secret-scanner` | Automated, unconditional secret-pattern scan, plus a distinct, cache-free pre-commit/pre-push invocation. Fully specced. | `cache-manager` |
| `cache-manager` | Content-addressed cache keyed by `(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)` (old pre-baseline key-composition decision), avoiding redundant model calls only — since D29, no longer involved in deciding whether verification is skipped (`provenance-checker`'s job). `VAR-CACHE-STORE-URL` is optional, falling back to a local `.hotdocs/cache/` store. | — |
| `provenance-checker` | Decides whether a component's committed `.provenance.json` already proves the exact current spec state was verified (D29) — the actual mechanism behind the "provenance hit" rollback claim, reading committed content directly rather than asking `cache-manager` a question it could never answer. | — |
| `llm-endpoint` | The one vendor-agnostic transport every model call in this pipeline dispatches through (D18) — `complete(prompt, model) -> ModelResponse`, resolving a model identifier to a backend internally so no caller holds a vendor credential or knows how to reach one. Extracted once `generator`/`test-author` were each found independently coupled to `VAR-ANTHROPIC-API-KEY`, and `merge-orchestrator`'s `judge` wiring had no component behind it at all. v1 ships exactly one backend (Anthropic) — a second is an additive implementation, not a rework, per this project's anti-premature-abstraction stance (D4/D6). Since D20, `model_call_error` is a structured object (`category`/`message`), not a boolean, and every call writes a caller-agnostic log to `.hotdocs/calls/`. Fully specced. | — |
| `provenance-writer` | Assembles and writes `.provenance.json` from the other components' outputs — collects, never invents. Fully specced; also where a real schema gap (missing `secret_scan` field) was found and fixed. | `generator`, `verifier-orchestrator`, `license-scanner`, `secret-scanner`, `cache-manager` |
| `review-packet-builder` | Assembles the human-readable PR summary (§6 step 7) — deliberately never includes the generated code diff itself. Reads every upstream result (verification, license/secret scan, provenance-hit, capability-scenario) from `provenance-tracker`'s own `check_readiness` aggregate (`D90`) — never a live call into `verifier-orchestrator`/`license-scanner`/`secret-scanner`/`capability-scenario-verifier`. Fully specced. | `provenance-tracker` |
| `corpus-graph-builder` | Builds `corpus-graph.json` — the `P-id → component → R-id → acceptance → verification-status` walk, orphan-rate computation, including orphan-var rate. Node/edge construction and per-node annotation now actually query `graph-query-engine`'s shared views (`R-GRAPH-009`, `D13`). Fully specced. | `graph-query-engine`, `spec-linter`, `provenance-writer`, `verifier-orchestrator` |
| `provenance-tracker` | Renamed from `merge-tracker` (`D88`, once `merge-orchestrator`'s removal, `D87`, retired the per-merge-attempt log this component used to write). Owns `hotdocs build` (`D92`) — the single command replacing what were once three (`generate`/`check-capability`/`verify`): for every component and intersecting capability across a blast radius or the whole corpus, calls `component-gate-runner`'s and `capability-scenario-verifier`'s own check-then-do gauntlets (never re-deriving their hit/miss logic), sequenced in `depends_on` order, and reports one ready/not-ready verdict. Reads `.hotdocs/attempts/` (written directly by `component-gate-runner`, not through a call into this component, to avoid a dependency cycle now that this component calls it) for `last_requirement_failures`, a retry-feedback convenience. Fully specced. | `component-gate-runner`, `impact-analyzer`, `capability-scenario-verifier` |
| `provenance-tracker-ui` | Renamed from `merge-tracker-ui` (`D88`). An interactive graph view — `corpus-graph-builder`'s committed topology as the base layer (`duckpgq`, not just core `read_json` — `D88` reversed this component's prior "never reads committed corpus state" boundary once a concrete cross-referencing need actually surfaced), colored by `provenance-tracker`'s live readiness state, navigable between a blast-radius view and a whole-corpus view, with per-node drill-down into attempt history and retry-feedback suggestions. Opened via a trivial local static-file server (`hotdocs track ui serve`, R-UI-006, D16) rather than `file://`. Implements no retry/generate action of its own. Fully specced. | `provenance-tracker`, `corpus-graph-builder` |
| `docs-site-renderer` | Pure renderer of `corpus-graph.json` into the interactive graph/docs site. Not committed; CI build artifact. Fully specced. | `corpus-graph-builder` |
| `capability-scenario-verifier` | Runs the capability scenarios of every product capability whose `realizes`-set intersects a scope, against the real assembled `gen/` output — the permanent backstop for cross-component behavioral risk `interface/guarantees/` can't fully rule out by documentation alone. Same dispatch mechanisms `verifier-orchestrator` already established (`criterion-compiler`/`test_author`/`judge`), one scope level up. Extracted from `merge-orchestrator` (D14, since removed — `D87`) once that component's fan-out and word-count caps crowded simultaneously. Renamed from `golden-scenario-verifier` (D23). Since `D89`, also owns its own provenance, keyed on realizing components' actual current content (deliberately not their `spec_bundle_hash`es, to avoid the exact blind spot this component exists to close), checked/written the same way `component-gate-runner` handles component provenance — called internally by `provenance-tracker`'s `hotdocs build` (`D92`), no standalone CLI of its own. Fully specced; the `D89` addition not yet regenerated. | `criterion-compiler`, `test-author`, `llm-endpoint` |
| `component-gate-runner` | Runs one component through its full per-component gauntlet — provenance check, generation on a miss, verification dispatch, compliance scanning, provenance write — producing one `ComponentPipelineResult`. Extracted out of `merge-orchestrator` (`D76`) once that component's `fan_out` and `component_doc_words` crowded together; mirrors the same per-item-dispatcher shape `capability-scenario-verifier`'s own `D14` extraction already established. Calls `generator` **exactly once** per invocation — no automatic retry loop (`D3`). No CLI of its own (`D92`, after briefly having one, `D86`/`D91`) — called internally by `provenance-tracker`'s `hotdocs build`, once per component in scope, in `depends_on` order. Wires its own `test_author`/`judge` closures and writes its own `AttemptRecord` directly to `.hotdocs/attempts/` (`D92` — never a call into `provenance-tracker`'s own code for this, specifically to avoid the dependency cycle that would otherwise create now that `provenance-tracker` calls this component). Fully specced, not yet regenerated. | `provenance-checker`, `spec-bundle-assembler`, `generator`, `verifier-orchestrator`, `license-scanner`, `secret-scanner`, `provenance-writer`, `test-author`, `llm-endpoint` |

## Advisory tooling (not part of a merge's own provenance check)

Two components live outside the table above by design — neither
component the uniform provenance mechanism actually checks (`D87`) nor
has any mechanism to gate a merge:

| Component | Purpose | `depends_on` |
| --- | --- | --- |
| `spec-completeness-assistant` | The assist agent this methodology always assumed but never named, and that `notes/metrics.md`'s "Completeness-agent confidence" / "Assist-agent acceptance rate" metrics already assumed existed. Runs on a feature branch, before a merge is even attempted: lint + predicted blast radius + hint-mode preview (all `compiled`), plus a genuinely judgment-based completeness score and redundancy check (`llm-judge`, dispatched through `llm-endpoint` since D18) — the one component in this corpus whose core value *is* judgment, not dispatch around it. Fully specced. | `spec-linter`, `impact-analyzer`, `spec-bundle-assembler`, `generator`, `llm-endpoint` |
| `decision-drift-detector` | Corpus-wide, not feature-branch-scoped (its only real difference from the row above): for every live spec file's `D<N>` citation, flags one whose cited decision has since been superseded by a decision ratified after the citing file's own last-modified commit (`D75`) — a candidate for staleness review, never a verdict. Purely diagnostic output; no mechanism exists for it to block anything. Fully specced. | `graph-query-engine` |

## A finding from writing this down: `merge-orchestrator`'s fan-out (historical — the component itself was later removed, `D87`)

`merge-orchestrator` depends on 14 components (11 at the time this was
first written, before its real spec existed; 12 once specced; 13 once
`test-author` was added and `merge-orchestrator` took on wiring its
callable into `verifier-orchestrator`'s call; 14 once `criterion-compiler`
was added directly, for the D2 capability-scenario gate reusing that same
callable-wiring pattern; 13 again once `cross-model-divergence-checker`
was removed from the dependency list, part of the second-model scope cut
for this build; 14 again once `merge-tracker` was added for D10's
merge-visibility work) — well past the fan-out warn threshold of 7.
This is a genuine tension
surfaced by actually doing the decomposition, not a mistake to quietly fix
by padding the dependency list down:

`merge-orchestrator` is a **thin coordinator** — its own `component.md` and
`gen/` output should be almost entirely sequencing calls to other components'
`interface/` contracts, with very little original logic or state of its own. The fan-out cap
exists to catch a component that is *doing too much* (real logic
coupled to many neighbors, each a real maintenance liability). A coordinator
with negligible logic of its own but a legitimately wide dependency list is a
different risk shape than that.

**Flagged, not resolved here:** this may mean the fan-out warning should be
weighted by the depending component's own size/complexity rather than a flat
count, or orchestrator-shaped components should get an explicit, documented
exemption class (parallel to `sealed`/pinned overrides, but for *structure*
rather than *generation*). Left as an open question against
`notes/initial-ideas.md` rather than silently patched — a real refinement
candidate for this corpus's own size-cap policy, discovered by using the methodology rather than just
designing it.

**Same tension, now also showing up in word count, not just fan-out:**
after D10's `merge-tracker` addition, `merge-orchestrator`'s
`component_doc_words` sits at 3964 — a trim away from the 4000 hard-fail
cap, not just the 2000 warn threshold every heavily-coordinating component
here already exceeds. Trimmed to fit this time; the next addition to this
component likely won't fit without either trimming again or actually
splitting something out, which is exactly the signal a rising size-cap
cost like this should be treated as.

**Resolved (D14), not just predicted:** the next addition did land —
D14's `R-MERGE-020` pushed `component_doc_words` to 4074, over the hard-fail
cap, confirming the prediction rather than requiring a second trim.
Rather than trim again, the capability-scenario gate (`R-MERGE-014`/`-020`)
was extracted into `capability-scenario-verifier`: it was already the
cross-component analog of `verifier-orchestrator`'s per-component
dispatch, living in `merge-orchestrator` only because of sequencing
convenience, not conceptual fit. This is the resolution of this
section's own flagged question, not a new, unrelated one: fan-out stayed
flat (one dependency swapped for another — extraction doesn't shrink a
coordinator's *call* count, only its *owned-logic* count), but
`component_doc_words` dropped well clear of both thresholds, confirming the
two caps were measuring different things and the fix was for the
word-count one specifically — see `SPEC_GUIDELINES.md` §4 for the general
lesson this produced, and this architecture doc's own history for the full
record.

**Fan-out ticked back up to 15 under D18**, for a reason that doesn't
repeat this section's own lesson: `llm-endpoint` is a genuinely new leaf
dependency, not a word-count-pressure symptom — `merge-orchestrator`
already owned wiring the real `judge` callable (`R-MERGE-004`), and
`llm-endpoint` is simply the component that now exists behind that
wiring where none did before. `component_doc_words` is unaffected (the
wording changed, not the amount), so `R-LINT-022`'s crowding check
(`D15`) still sees exactly the two dimensions it already saw at 14 —
confirming this addition doesn't reopen the question D14 already
resolved, it's just one more call a thin coordinator makes.

**`component_doc_words` climbed back to the edge of the cap under D29**
(3991/4000) — not a crowding *signal* this time so much as the direct
cost of fixing a real correctness gap: `R-MERGE-003`/`015` needed new
language explaining why a sealed component's `spec_bundle_hash` can't
be trusted the way `provenance-checker`'s general logic trusts it
elsewhere. Trimmed repeatedly during that work to land just under the
cap rather than split anything — D14's lesson (extraction fixes a
*word-count* crowding, not a *per-requirement* one) didn't apply here,
since nothing about this addition was crowding on its own terms, just
dense. The next requirement-level addition to this component likely
won't fit without either trimming elsewhere first or finally acting on
this section's own long-flagged fan-out/word-count tension.

**Resolved a second time (D76), the same way as D14, not a new
pattern:** `component_doc_words` did cross the hard-fail cap (4014/4000)
and `fan_out` was still at 15 — both dimensions crowding at once again,
the identical signal `R-LINT-022` fired for before D14. The same
per-item-dispatcher shape was available to borrow a second time:
`R-MERGE-003/004/005/006/008/009/015` — the provenance-check through
generation/verification/scanning/provenance-write gauntlet for one
impacted component — was already self-contained, living in
`merge-orchestrator` only because nothing had extracted it yet, not
because it was conceptually a sequencing concern. Extracted as
`component-gate-runner`. Unlike D14's extraction, where fan-out stayed
flat on principle ("extraction doesn't shrink a coordinator's *call*
count"), fan-out *did* drop here in practice — from 15 to 9 — because
every one of the seven components `component-gate-runner` now calls
(`provenance-checker`, `spec-bundle-assembler`, `generator`,
`verifier-orchestrator`, `license-scanner`, `secret-scanner`,
`provenance-writer`) had been a direct `merge-orchestrator` dependency
used for nothing else; `merge-orchestrator` never needed to keep
calling any of them directly once the gauntlet moved. This doesn't
reopen this section's earlier "fan-out stays flat" observation — that
was true of D14's extraction specifically, not a general law; whether
fan-out drops after an extraction depends on whether the parent
coordinator had any *other* reason to call the extracted component's
own dependencies directly, which here it didn't.

**`D86` went further than a size-cap fix** — a deliberate product
decision, not another crowding response: generation should never
happen unattended as part of a merge at all. `component-gate-runner`
left `merge-orchestrator`'s dependency list entirely (not just its
*calls*), replaced by `provenance-checker` directly; fan-out stayed at
9 either way, a coincidence of the numbers rather than a repeat of
either prior lesson. `component-gate-runner` itself didn't shrink or
change internally — it gained its own CLI and now wires its own
`test_author`/`judge` closures, since nothing calls it on a developer's
behalf anymore.

**`D87` removed `merge-orchestrator` entirely** — a different kind of
change from everything above, worth distinguishing clearly: every
other entry in this section was a response to the size-cap signal
(`R-LINT-022`) firing, each time relieving it by extracting a cohesive
sub-responsibility into its own component. `D87` wasn't a response to
that signal at all — by the time it happened, `merge-orchestrator`'s
only remaining job (a provenance check per impacted component, `D86`)
didn't need an orchestrating component to run it, so there was nothing
left to crowd *into* anything. `provenance-tracker`'s `hotdocs build`
(`D88`/`D92`) answers the same question directly. This section's own fan-out/
word-count history remains a real, citable precedent for a future
component facing the same signal — it just no longer describes a
component that still exists.

## Sealed component, by design rather than by legacy debt

`criterion-compiler` is the one component in this list that is **permanently
hand-maintained, not spec-generated** (`sealed: true`) — not because it's
legacy debt being wrapped (§8's original framing for `sealed`), but because
the compiled-criterion trust argument requires it: the compiler is what makes `compiled`-kind
criteria trustworthy *without* a second model, and if the compiler were itself
agent-generated, that trust chain would be circular. This is a legitimate,
intentional, permanent use of the `sealed` mechanism — the mechanical
definition (`source_path`, characterization tests, exempt from the
cold-regen invariant) already covers this use case correctly; it doesn't need
a new mechanism, just a note that "sealed" isn't only for legacy debt.

Full spec bundle now at `specs/components/criterion-compiler/` — see its
`component.md` for the resolved generated-test/circularity question this
raised (its own acceptance criteria are all `kind: generated-test`, verified
by a human-authored test suite independent of the hand-maintained
implementation — verifying the compiler with the compiler would prove
nothing).

## The step-phrase grammar is a corpus-wide, architecture-level convention

`criterion-compiler` implements a fixed Given/When/Then step-phrase grammar
(the full table lives at `specs/architecture/step-phrase-grammar.md` — see
that file; relocated there from `criterion-compiler/interface/` during the
D1 migration, which made the mismatch between "where this content lived"
and "what governance it actually needs" concrete for the first time). The
grammar itself doesn't fit any other document type — not
a component's own behavior, not a product capability — but it *is* exactly
what this document already claims to own: a cross-cutting technical decision
(`notes/initial-ideas.md` §4). Recorded here so it's unambiguous: **changing
the step-phrase grammar is an architecture-level decision**, carrying the
same governance weight as splitting a component — not something a
routine `criterion-compiler` spec edit does on its own, because it's a
breaking change to every `compiled` criterion in the corpus, not just to that
one component.
