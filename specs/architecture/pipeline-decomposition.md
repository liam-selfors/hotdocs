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
| `impact-analyzer` | From changed spec ids + the dependency graph, computes the minimal set of components to regenerate. | `spec-linter` |
| `spec-bundle-assembler` | Assembles a component's full generation input (spec + interface + constraints + dependency interfaces + referenced vars + glossary) into one payload. Reused by canonical generation, the cross-model check, and hint-mode previews. | `spec-linter` |
| `criterion-compiler` | Deterministic Gherkin → test-scaffolding compiler for `compiled`-kind acceptance criteria. | — |
| `generator` | Calls the pinned canonical model (cold, best-of-k retry) to produce `gen/<component>/` from a bundle. | `spec-bundle-assembler`, `cache-manager` |
| `verifier-orchestrator` | Runs per-criterion verification (`compiled` via the compiler, `generated-test`, `llm-judge`) plus contract/property tests and the interface drift check. | `criterion-compiler`, `generator` |
| `cross-model-divergence-checker` | The D3 toggleable gate: regenerates with a second model, differential-tests against the canonical build. | `generator`, `verifier-orchestrator`, `cache-manager` |
| `license-scanner` | Automated, unconditional license/similarity scan (D7). | `cache-manager` |
| `secret-scanner` | Automated, unconditional secret-pattern scan (D12). | `cache-manager` |
| `cache-manager` | Content-addressed cache keyed by `(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)` (D13); cache-hit detection feeds rollback (D11). | — |
| `provenance-writer` | Assembles and writes `.provenance.json` (D7) from the other components' outputs. | `generator`, `verifier-orchestrator`, `cross-model-divergence-checker`, `license-scanner`, `secret-scanner`, `cache-manager` |
| `review-packet-builder` | Assembles the human-readable PR summary (D11/D12/§6 step 7). | `provenance-writer`, `verifier-orchestrator`, `license-scanner`, `secret-scanner`, `cache-manager` |
| `corpus-graph-builder` | Builds `corpus-graph.json` (D8/D9) — the `P-id → component → R-id → acceptance → verification-status` walk, orphan-rate computation. | `spec-linter`, `provenance-writer`, `verifier-orchestrator` |
| `docs-site-renderer` | Pure renderer of `corpus-graph.json` into the interactive graph/docs site (D9). Not committed; CI build artifact. | `corpus-graph-builder` |
| `merge-orchestrator` | Sequences the above per `SPEC_GUIDELINES.md` §6, parallelizing independent gates (D13). | everything above |

## A finding from writing this down: `merge-orchestrator`'s fan-out

`merge-orchestrator` depends on 11 components — well past D2's fan-out warn
threshold of 7. This is a genuine tension surfaced by actually doing the
decomposition, not a mistake to quietly fix by padding the dependency list
down:

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

Its full spec bundle isn't written yet — this document records its place in
the dependency graph and its `sealed` status so the graph is honest about it;
`specs/components/criterion-compiler/` is a follow-up.
