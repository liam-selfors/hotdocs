---
id: comp-test-author
title: Test Author
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
uses_var: [VAR-ANTHROPIC-API-KEY, VAR-SECOND-MODEL-API-KEY]
model_pin: claude-sonnet-5
sealed: false
---

# Test Author

## Purpose

Authors the test code for one `generated-test`-kind acceptance criterion —
the "independent generation path" D4/D5 require for that `kind` to be
trustworthy. Invoked by `verifier-orchestrator` via an injectable callable
(the same pattern already established for `llm-judge`'s `judge` parameter),
not sequenced as a top-level pipeline step — `verifier-orchestrator` decides
*when* a test needs authoring (a criterion's `kind` says so, already fixed
at spec-authoring time); this component decides *how* to author one.

## Scope

**In scope:** producing test code from one criterion's Given/When/Then
prose plus the target component's `interface.md`; model selection for
authoring independence; caching.

**Out of scope, and deliberately so:** deciding whether a criterion needs a
test at all — that is the `kind:` tag in `acceptance.md`, fixed at
spec-authoring time and lint-checked (R-LINT-010), never re-decided here or
by `verifier-orchestrator` at verification time. This boundary was the
explicit resolution of a design discussion about this component: giving it,
or `verifier-orchestrator`, the power to override a ratified spec's declared
`kind` would make that declaration advisory rather than normative, and would
break `verifier-orchestrator`'s determinism (and therefore D13's cache-key
validity) by folding a judgment call into what must stay pure dispatch.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

- **R-AUTHOR-001** — Given a criterion's Given/When/Then text, its `Covers:
  R-id`, the covered requirement's own text from `spec.md`, the target
  component's `interface.md`, and the glossary (a `CriterionBundle`,
  assembled by `spec-bundle-assembler`), this component MUST produce test
  code that exercises the component's public interface as described,
  asserting the criterion's `Then` clause.
- **R-AUTHOR-002** — The `CriterionBundle` MUST NOT include the target
  component's actual `gen/<component>/` source code — only its
  `interface.md` contract. This is the same "write against the contract,
  not by reading the implementation" discipline `spec-bundle-assembler`
  already enforces for `generator` (R-ASSEMBLE-001), applied here to
  preserve the independence D4/D5 require of a `generated-test` check.
- **R-AUTHOR-003** — Model selection MUST prefer a model different from the
  one `generator` used for that component's current code, when a second
  model is configured — this is what makes "independent path" true in
  practice, not just in name. When no second model is configured, this
  component MUST fall back to the canonical model alone (the same
  single-model-must-keep-working posture D10 established, applied here as
  a fourth instance — authoring with the same model as the code under test
  is weaker evidence, but still produces a real, executable test, which is
  strictly better than no test at all).
- **R-AUTHOR-004** — Before calling any model, MUST check `cache-manager`
  using a key derived from `(criterion content hash, gate_inputs_hash,
  gate_version, model)` — mirrors `generator`'s R-GEN-005 exactly, at
  criterion granularity instead of component granularity.
- **R-AUTHOR-005** — On a cache miss, after a successful call, the result
  MUST be written to `cache-manager` under that key before being returned —
  mirrors R-GEN-006.
- **R-AUTHOR-006** — Output MUST be written only under
  `verification/<component>/generated-test/` — never under `gen/` (it is a
  test, not application code), and never overwriting `criterion-compiler`'s
  own output directory.
- **R-AUTHOR-007** — A model-call error MUST be reported as a distinct
  failure mode from "the authored test ran but failed" — mirrors R-GEN-008's
  classification distinction, consumed by `verifier-orchestrator` to tell
  "could not author a test" apart from "the test says the criterion isn't
  met."
- **R-AUTHOR-008** — `VAR-ANTHROPIC-API-KEY` and `VAR-SECOND-MODEL-API-KEY`
  MUST never appear in output, logs, or provenance — only the model
  identifier actually used is recorded. Mirrors `generator`'s credential
  constraint.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`TestAuthoringResult` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Whether this component should itself get a cross-model divergence check
  (two independently-authored tests for the same criterion, compared) —
  not addressed here; `cross-model-divergence-checker` as specced targets
  `generator`'s output specifically, and extending the same pattern to test
  authoring is a plausible future refinement, not assumed here.

## Change log

- Initial draft.
