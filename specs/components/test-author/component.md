---
id: comp-test-author
title: Test Author
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
uses_var: [VAR-ANTHROPIC-API-KEY]
model_pin: claude-sonnet-5
sealed: false
---

# Test Author

## Purpose

Authors the test code for one `generated-test`-kind acceptance criterion —
the "independent generation path" D4/D5 require for that `kind` to be
trustworthy. **Currently single-model** (`R-AUTHOR-003`): independence
today means an agent authoring the test from spec prose alone, with no
access to the implementation under test — not also a different model from
the one that wrote that implementation, which was the original, stronger
design, deferred alongside the broader second-model scope reduction for
this build (see `cross-model-divergence-checker/component.md`). Invoked by
`verifier-orchestrator` via an injectable callable
(the same pattern already established for `llm-judge`'s `judge` parameter),
not sequenced as a top-level pipeline step — `verifier-orchestrator` decides
*when* a test needs authoring (a criterion's `kind` says so, already fixed
at spec-authoring time); this component decides *how* to author one.

## Scope

**In scope:** producing test code from one criterion's Given/When/Then
prose plus the target component's `interface/` content; model selection
(currently the canonical model alone — see `R-AUTHOR-003`'s deferred
second-model preference); caching.

**Out of scope, and deliberately so:** deciding whether a criterion needs a
test at all — that is the `kind:` tag in `acceptance/`, fixed at
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

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

Mixed `kind`, mirroring `generator`'s own split: behavior around the
external model call is `generated-test` (exercised via an injected mock
model, same pattern `generator`'s own suite already established);
R-AUTHOR-002 and R-AUTHOR-006 are pure path/data-safety checks, `compiled`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Whether this component should itself get a cross-model divergence check
  (two independently-authored tests for the same criterion, compared) —
  not addressed here; `cross-model-divergence-checker` as specced targets
  `generator`'s output specifically, and extending the same pattern to test
  authoring is a plausible future refinement, not assumed here. Moot for
  now regardless, alongside the broader second-model deferral below.
- ~~Second-model authoring preference~~ — deferred, not resolved as a
  question: see `R-AUTHOR-003`'s own note. `uses_var` no longer lists
  `VAR-SECOND-MODEL-API-KEY` because nothing in this component's active
  requirements references it; re-add it if the preference returns.

## Change log

- Initial draft.
