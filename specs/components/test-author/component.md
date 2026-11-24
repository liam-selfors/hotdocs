---
id: comp-test-author
title: Test Author
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-llm-endpoint, comp-test-probe]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Test Author

## Purpose

Authors the test code for one `generated-test`-kind criterion, from
spec prose alone, never the implementation. `verifier-orchestrator`
calls it and decides when.

## Scope

**In scope:** test code from a criterion's Given/When/Then prose plus
the target's `interface/`; canonical-model selection (R-AUTHOR-003).

**Out of scope:** deciding whether a criterion needs a test (its
`kind`, R-LINT-010).

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

All `kind: generated-test` (`D43`), with an injected mock model.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

See the decisions, `D56` onward; `D343` specifies the CLI;
`D370` removes the cache (`R-AUTHOR-030`).
