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
| `impact-analyzer` | From changed spec ids + the dependency graph, computes the minimal set of components to regenerate — now fully specced, including the interface-vs-internal-change distinction (`spec-bundle` changes stay local; `interface.md`/`specs/vars/`/capability changes propagate) that D2 previously stated only as a sizing heuristic, never as an executable rule. | `spec-linter` |
| `spec-bundle-assembler` | Assembles a component's full generation input (spec + interface + constraints + dependency interfaces + referenced vars + glossary — deliberately excluding `acceptance.md`, to avoid the generation model overfitting to its own tests) into one payload. Reused by canonical generation, the cross-model check, and hint-mode previews. Fully specced. | `spec-linter` |
| `criterion-compiler` | Deterministic Gherkin → test-scaffolding compiler for `compiled`-kind acceptance criteria. | — |
| `generator` | Produces **exactly one candidate** `gen/<component>/` per call, given a `SpecBundle` and an explicit model identifier (never a hardcoded "canonical pin" — this is what lets `cross-model-divergence-checker` reuse it with a second model). Single-shot and stateless about prior attempts, deliberately: the best-of-k *retry loop* (D3) lives in `merge-orchestrator`, not here — putting it here would require a `verifier-orchestrator` dependency this component doesn't have. Fully specced. | `spec-bundle-assembler`, `cache-manager` |
| `test-author` | Authors the test code for one `generated-test`-kind criterion — D4/D5's "independent generation path," given a real component for the first time. Invoked by `verifier-orchestrator` via an injectable callable, not sequenced top-level by `merge-orchestrator` — same pattern `llm-judge`'s `judge` parameter already established. Prefers a different model than `generator` used, when one is configured, for genuine independence. Fully specced. | `spec-bundle-assembler`, `cache-manager` |
| `verifier-orchestrator` | Runs per-criterion verification (`compiled` via the compiler, `generated-test` via `test-author`, `llm-judge`) plus contract/property tests and the interface drift check. Its own coordination logic is 100% `compiled` — dispatching to judgment-involving mechanisms is itself deterministic. **Never re-decides a criterion's declared `kind`** — that stays fixed at spec-authoring time, lint-checked, normative. Fully specced. | `criterion-compiler`, `generator`, `test-author` |
| `cross-model-divergence-checker` | The D3 toggleable gate: regenerates with a second model, differential-tests against the canonical build — or, in `standby-only` mode, just keeps a verified spare warm for D10's fallback. All `compiled`: comparing two concrete candidates needs no judgment. Fully specced. | `generator`, `verifier-orchestrator`, `cache-manager` |
| `license-scanner` | Automated, unconditional license/similarity scan (D7) — k-gram/shingle hashing against a reference corpus, fully deterministic. Fully specced. | `cache-manager` |
| `secret-scanner` | Automated, unconditional secret-pattern scan (D12), plus a distinct, cache-free pre-commit/pre-push invocation. Fully specced. | `cache-manager` |
| `cache-manager` | Content-addressed cache keyed by `(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)` (D13); cache-hit detection feeds rollback (D11). | — |
| `provenance-writer` | Assembles and writes `.provenance.json` (D7) from the other components' outputs — collects, never invents. Fully specced; also where D7's schema gap (missing `secret_scan` field) was found and fixed. | `generator`, `verifier-orchestrator`, `cross-model-divergence-checker`, `license-scanner`, `secret-scanner`, `cache-manager` |
| `review-packet-builder` | Assembles the human-readable PR summary (D11/D12/§6 step 7) — deliberately never includes the generated code diff itself. Fully specced. | `provenance-writer`, `verifier-orchestrator`, `license-scanner`, `secret-scanner`, `cache-manager` |
| `corpus-graph-builder` | Builds `corpus-graph.json` (D8/D9) — the `P-id → component → R-id → acceptance → verification-status` walk, orphan-rate computation, including orphan-var rate (D12). Fully specced. | `spec-linter`, `provenance-writer`, `verifier-orchestrator` |
| `docs-site-renderer` | Pure renderer of `corpus-graph.json` into the interactive graph/docs site (D9). Not committed; CI build artifact. Fully specced. | `corpus-graph-builder` |
| `merge-orchestrator` | Sequences the above per `SPEC_GUIDELINES.md` §6, parallelizing independent gates (D13). **Owns the best-of-k retry loop (D3)** — calls `generator` once per sample, checks the result against `verifier-orchestrator`, decides whether to call `generator` again with a different seed. Also where the real `test_author`/`judge` callables get wired into `verifier-orchestrator`'s call — nothing upstream assigned that wiring either, until this component's spec made it explicit. Fully specced — its real `fan_out` (13, after `test-author` was added) is checked against the actual linter and still triggers exactly the warn-only finding this document predicted below, confirming the prediction rather than just asserting it. | everything above |

## A finding from writing this down: `merge-orchestrator`'s fan-out

`merge-orchestrator` depends on 13 components (11 at the time this was
first written, before its real spec existed; 12 once specced; 13 once
`test-author` was added and `merge-orchestrator` took on wiring its
callable into `verifier-orchestrator`'s call) — well past D2's fan-out warn
threshold of 7. This is a genuine tension
surfaced by actually doing the decomposition, not a mistake to quietly fix
by padding the dependency list down:

`merge-orchestrator` is a **thin coordinator** — its own `spec.md` and
`gen/` output should be almost entirely sequencing calls to other components'
`interface.md`s, with very little original logic or state of its own. D2's
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
`spec.md` for the resolved generated-test/circularity question this raised
(its own acceptance criteria are all `kind: generated-test`, verified by a
human-authored test suite independent of the hand-maintained implementation —
verifying the compiler with the compiler would prove nothing).

## The step-phrase grammar is a corpus-wide, architecture-level convention

`criterion-compiler` implements a fixed Given/When/Then step-phrase grammar
(the full table lives in its `interface.md`, since that component is what
implements it). The grammar itself doesn't fit any other document type — not
a component's own behavior, not a product capability — but it *is* exactly
what this document already claims to own: a cross-cutting technical decision
(`notes/initial-ideas.md` §4). Recorded here so it's unambiguous: **changing
the step-phrase grammar is an architecture-level decision**, carrying the
same governance weight as splitting a component (D2) — not something a
routine `criterion-compiler` spec edit does on its own, because it's a
breaking change to every `compiled` criterion in the corpus, not just to that
one component.
