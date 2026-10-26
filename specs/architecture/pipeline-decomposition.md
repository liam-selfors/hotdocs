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
| `impact-analyzer` | From changed spec ids + the dependency graph, computes the minimal set of components to regenerate — now fully specced, including the interface-vs-internal-change distinction (`component.md`/`requirements/`/`constraints.md`/`acceptance/` changes stay local; `interface/cli.md`/`library.md`/`data/*.md`/`specs/vars/`/capability changes always propagate; `interface/guarantees/*.md` changes propagate too, but **narrowably** — opt-in per-dependent via `depends_on_guarantees`, D16) that D2 previously stated only as a sizing heuristic, never as an executable rule — and, since D15, computed as plain file-level hashing rather than needing bespoke section parsing (each `interface/` file already is its own hash boundary). | `spec-linter` |
| `spec-bundle-assembler` | Assembles a component's full generation input (`component.md` + `requirements/` + `interface/` + `constraints.md` + dependency `interface/` content + referenced vars + glossary — deliberately excluding `acceptance/`, to avoid the generation model overfitting to its own tests) into one payload. Reused by canonical generation and hint-mode previews. Fully specced. | `spec-linter` |
| `criterion-compiler` | Deterministic Gherkin → test-scaffolding compiler for `compiled`-kind acceptance criteria. Two-phase by requirement (R-COMPILE-011): parse+bind (grammar matching, `interface/` resolution — target-independent) then emit (literal source text for one `--target`). v1 ships exactly one emitter, `pytest`; any other `--target` is a usage error, never a silent fallback. | — |
| `generator` | Produces **exactly one candidate** `gen/<component>/` per call, given a `SpecBundle` and an explicit model identifier (never a hardcoded "canonical pin"). Single-shot and stateless about prior attempts, deliberately — and since `D31` retired the best-of-k retry loop that used to call it again on a verification failure, `merge-orchestrator` now never calls it more than once per component per merge at all. Since D30, dispatches its model call through `llm-endpoint` rather than holding a vendor credential itself. Fully specced. | `spec-bundle-assembler`, `cache-manager`, `llm-endpoint` |
| `test-author` | Authors the test code for one `generated-test`-kind criterion — D4/D5's "independent generation path," given a real component for the first time. Invoked by `verifier-orchestrator` via an injectable callable, not sequenced top-level by `merge-orchestrator` — same pattern `llm-judge`'s `judge` parameter already established. Single-model (`R-AUTHOR-003`): independence comes from authoring the test from spec prose alone, with no access to the implementation under test. Since D30, dispatches through `llm-endpoint`. Fully specced. | `spec-bundle-assembler`, `cache-manager`, `llm-endpoint` |
| `verifier-orchestrator` | Runs per-criterion verification (`compiled` via the compiler, `generated-test` via `test-author`, `llm-judge`) plus contract/property tests and the interface drift check. Its own coordination logic is 100% `compiled` — dispatching to judgment-involving mechanisms is itself deterministic. **Never re-decides a criterion's declared `kind`** — that stays fixed at spec-authoring time, lint-checked, normative. Fully specced. | `criterion-compiler`, `generator`, `test-author` |
| `license-scanner` | Automated, unconditional license/similarity scan (D7) — k-gram/shingle hashing against a reference corpus, fully deterministic. Fully specced. | `cache-manager` |
| `secret-scanner` | Automated, unconditional secret-pattern scan (D12), plus a distinct, cache-free pre-commit/pre-push invocation. Fully specced. | `cache-manager` |
| `cache-manager` | Content-addressed cache keyed by `(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)` (D13), avoiding redundant model calls only — since D39, no longer involved in deciding whether verification is skipped (`provenance-checker`'s job). `VAR-CACHE-STORE-URL` is optional, falling back to a local `.hotdocs/cache/` store. | — |
| `provenance-checker` | Decides whether a component's committed `.provenance.json` already proves the exact current spec state was verified (D39) — the actual mechanism behind D11's "provenance hit" rollback claim, reading committed content directly rather than asking `cache-manager` a question it could never answer. | — |
| `llm-endpoint` | The one vendor-agnostic transport every model call in this pipeline dispatches through (D30) — `complete(prompt, model) -> ModelResponse`, resolving a model identifier to a backend internally so no caller holds a vendor credential or knows how to reach one. Extracted once `generator`/`test-author` were each found independently coupled to `VAR-ANTHROPIC-API-KEY`, and `merge-orchestrator`'s `judge` wiring had no component behind it at all. v1 ships exactly one backend (Anthropic) — a second is an additive implementation, not a rework, per this project's anti-premature-abstraction stance (D18/D20). Since D32, `model_call_error` is a structured object (`category`/`message`), not a boolean, and every call writes a caller-agnostic log to `.hotdocs/calls/`. Fully specced. | — |
| `provenance-writer` | Assembles and writes `.provenance.json` (D7) from the other components' outputs — collects, never invents. Fully specced; also where D7's schema gap (missing `secret_scan` field) was found and fixed. | `generator`, `verifier-orchestrator`, `license-scanner`, `secret-scanner`, `cache-manager` |
| `review-packet-builder` | Assembles the human-readable PR summary (D11/D12/§6 step 7) — deliberately never includes the generated code diff itself. Reads every upstream result (verification, license/secret scan, provenance-hit) from `provenance-writer`'s already-written manifests via the shared `component_provenance` view (D26) — never a live call into `verifier-orchestrator`/`license-scanner`/`secret-scanner`, none of which write their own file. Fully specced. | `provenance-writer` |
| `corpus-graph-builder` | Builds `corpus-graph.json` (D8/D9) — the `P-id → component → R-id → acceptance → verification-status` walk, orphan-rate computation, including orphan-var rate (D12). Node/edge construction and per-node annotation now actually query `graph-query-engine`'s shared views (`R-GRAPH-009`, `D45`). Fully specced. | `graph-query-engine`, `spec-linter`, `provenance-writer`, `verifier-orchestrator` |
| `merge-tracker` | Writes one durable, local-only (`.hotdocs/`, gitignored, never a gate input) record per merge attempt — success or block — directly queryable via DuckDB's `read_json`, no bespoke query API (D22). Reads `provenance-writer`'s already-written manifests for per-component detail rather than depending on `merge-orchestrator`'s own `MergeResult` type, specifically to avoid a dependency cycle. Since D32, also writes a separate, full-detail `AttemptRecord` per component per merge attempt to `.hotdocs/attempts/` — the gap D31's retired best-of-k loop opened (a blocked merge commits no provenance at all, so a failed attempt's diagnostic detail would otherwise vanish with the process). Fully specced. | `provenance-writer` |
| `merge-tracker-ui` | A local, per-developer static page (DuckDB-WASM, core `read_json` only — not `duckpgq`, which this component doesn't actually need) rendering `.hotdocs/tracking/` directly in the browser, opened via a trivial local static-file server (`hotdocs track ui serve`, R-UI-006, D26) rather than `file://` — removes CORS inconsistency across browsers. The server computes nothing; DuckDB-WASM still queries entirely client-side. Not a CI artifact like `docs-site-renderer` — a different data lifecycle (local-only vs. committed) genuinely requires a different one. Implements no retry action of its own; re-running the merge command already is the complete recovery path (`R-MERGE-018`). Fully specced. | `merge-tracker` |
| `docs-site-renderer` | Pure renderer of `corpus-graph.json` into the interactive graph/docs site (D9). Not committed; CI build artifact. Fully specced. | `corpus-graph-builder` |
| `capability-scenario-verifier` | Runs the capability scenarios of every product capability whose `realizes`-set intersects a merge's blast radius, against the real assembled `gen/` output — the permanent backstop for cross-component behavioral risk `interface/guarantees/` can't fully rule out by documentation alone. Same dispatch mechanisms `verifier-orchestrator` already established (`criterion-compiler`/`test_author`/`judge`), one scope level up. Extracted from `merge-orchestrator` (D25) once that component's fan-out and word-count caps crowded simultaneously — see the finding below, now resolved rather than just flagged. Renamed from `golden-scenario-verifier` (D36) once "golden" turned out to communicate nothing about what this actually is. Fully specced. | `criterion-compiler`, `test-author` |
| `merge-orchestrator` | Sequences the above per `SPEC_GUIDELINES.md` §6, parallelizing independent gates (D13). Calls `generator` **exactly once** per cache-miss, non-sealed component per merge attempt — `D3`'s best-of-k retry loop (originally diagnostic-guided per `D17`) was retired by `D31`: a failed attempt blocks the merge for that component immediately, with no second call, no seed variation, no `retry_feedback`. Re-running the merge (`R-MERGE-018`, unaffected) is now the only path back to a fresh generation attempt, deliberately gated behind a human looking at `D32`'s per-attempt record first. Also where the real `test_author`/`judge` callables get wired into `verifier-orchestrator`'s call — nothing upstream assigned that wiring either, until this component's spec made it explicit; since D30, `judge`'s real implementation is backed by `llm-endpoint`. **Since D16, calls `capability-scenario-verifier`** once every component has passed per-component verification, wiring the same real callables into that call — the dispatch logic itself moved out (D25); this component only owns *when* and *with what* it's called now. Fully specced — its real `fan_out` is 15 as of D30 (D39 swapped `cache-manager` for `provenance-checker` without changing the count), accepted for the same reason D25's note already gives: a thin coordinator calling one more leaf component doesn't change its risk shape. `component_doc_words` is now within single digits of the hard-fail cap (`D39`) — the finding below's prediction that this dimension would eventually need relief is no longer hypothetical; see that note for the current word budget. | everything above |

## Feature-branch tooling (not part of the merge pipeline)

One component lives outside the table above by design — it never appears
in `merge-orchestrator`'s dependency list and has no mechanism to gate a
merge:

| Component | Purpose | `depends_on` |
| --- | --- | --- |
| `spec-completeness-assistant` | The assist agent D1 describes but never names, and that `notes/metrics.md`'s "Completeness-agent confidence" / "Assist-agent acceptance rate" metrics already assumed existed. Runs on a feature branch, before a merge is even attempted: lint + predicted blast radius + hint-mode preview (all `compiled`), plus a genuinely judgment-based completeness score and redundancy check (`llm-judge`, dispatched through `llm-endpoint` since D30) — the one component in this corpus whose core value *is* judgment, not dispatch around it. Fully specced. | `spec-linter`, `impact-analyzer`, `spec-bundle-assembler`, `generator`, `llm-endpoint` |

## A finding from writing this down: `merge-orchestrator`'s fan-out

`merge-orchestrator` depends on 14 components (11 at the time this was
first written, before its real spec existed; 12 once specced; 13 once
`test-author` was added and `merge-orchestrator` took on wiring its
callable into `verifier-orchestrator`'s call; 14 once `criterion-compiler`
was added directly, for the D16 capability-scenario gate reusing that same
callable-wiring pattern; 13 again once `cross-model-divergence-checker`
was removed from the dependency list, part of the second-model scope cut
for this build; 14 again once `merge-tracker` was added for D22's
merge-visibility work) — well past D2's fan-out warn threshold of 7.
This is a genuine tension
surfaced by actually doing the decomposition, not a mistake to quietly fix
by padding the dependency list down:

`merge-orchestrator` is a **thin coordinator** — its own `component.md` and
`gen/` output should be almost entirely sequencing calls to other components'
`interface/` contracts, with very little original logic or state of its own. D2's
fan-out cap exists to catch a component that is *doing too much* (real logic
coupled to many neighbors, each a real maintenance liability). A coordinator
with negligible logic of its own but a legitimately wide dependency list is a
different risk shape than that.

**Flagged, not resolved here:** this may mean D2's fan-out warning should be
weighted by the depending component's own size/complexity rather than a flat
count, or orchestrator-shaped components should get an explicit, documented
exemption class (parallel to `sealed`/pinned overrides, but for *structure*
rather than *generation*). Left as an open question against
`notes/initial-ideas.md` rather than silently patched — a real refinement
candidate for D2, discovered by using the methodology rather than just
designing it.

**Same tension, now also showing up in word count, not just fan-out:**
after D22's `merge-tracker` addition, `merge-orchestrator`'s
`component_doc_words` sits at 3964 — a trim away from D2's 4000 hard-fail
cap, not just the 2000 warn threshold every heavily-coordinating component
here already exceeds. Trimmed to fit this time; the next addition to this
component likely won't fit without either trimming again or actually
splitting something out, which is exactly the signal D2/D13 say a rising
cost like this should be treated as.

**Resolved (D25), not just predicted:** the next addition did land —
D24's `R-MERGE-020` pushed `component_doc_words` to 4074, over the hard-fail
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
lesson this produced, and `notes/initial-ideas.md`'s D25 for the full
record.

**Fan-out ticked back up to 15 under D30**, for a reason that doesn't
repeat this section's own lesson: `llm-endpoint` is a genuinely new leaf
dependency, not a word-count-pressure symptom — `merge-orchestrator`
already owned wiring the real `judge` callable (`R-MERGE-004`), and
`llm-endpoint` is simply the component that now exists behind that
wiring where none did before. `component_doc_words` is unaffected (the
wording changed, not the amount), so `R-LINT-022`'s crowding check
(`D28`) still sees exactly the two dimensions it already saw at 14 —
confirming this addition doesn't reopen the question D25 already
resolved, it's just one more call a thin coordinator makes.

**`component_doc_words` climbed back to the edge of the cap under D39**
(3991/4000) — not a crowding *signal* this time so much as the direct
cost of fixing a real correctness gap: `R-MERGE-003`/`015` needed new
language explaining why a sealed component's `spec_bundle_hash` can't
be trusted the way `provenance-checker`'s general logic trusts it
elsewhere. Trimmed repeatedly during that work to land just under the
cap rather than split anything — D25's lesson (extraction fixes a
*word-count* crowding, not a *per-requirement* one) didn't apply here,
since nothing about this addition was crowding on its own terms, just
dense. The next requirement-level addition to this component likely
won't fit without either trimming elsewhere first or finally acting on
this section's own long-flagged fan-out/word-count tension.

## Sealed component, by design rather than by legacy debt

`criterion-compiler` is the one component in this list that is **permanently
hand-maintained, not spec-generated** (`sealed: true`) — not because it's
legacy debt being wrapped (§8's original framing for `sealed`), but because
D5's trust argument requires it: the compiler is what makes `compiled`-kind
criteria trustworthy *without* a second model, and if the compiler were itself
agent-generated, that trust chain would be circular. This is a legitimate,
intentional, permanent use of the `sealed` mechanism — the mechanical
definition (`source_path`, characterization tests, exempt from the D1
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
D15 migration, which made the mismatch between "where this content lived"
and "what governance it actually needs" concrete for the first time). The
grammar itself doesn't fit any other document type — not
a component's own behavior, not a product capability — but it *is* exactly
what this document already claims to own: a cross-cutting technical decision
(`notes/initial-ideas.md` §4). Recorded here so it's unambiguous: **changing
the step-phrase grammar is an architecture-level decision**, carrying the
same governance weight as splitting a component (D2) — not something a
routine `criterion-compiler` spec edit does on its own, because it's a
breaking change to every `compiled` criterion in the corpus, not just to that
one component.
