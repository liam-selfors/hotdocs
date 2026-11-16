---
id: comp-test-author
title: Test Author
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager, comp-llm-endpoint]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Test Author

## Purpose

Authors the test code for one `generated-test`-kind criterion, from
spec prose alone, with no access to the implementation under test.
Invoked by `verifier-orchestrator` via an injectable callable — it
decides *when* (a criterion's `kind`); this decides *how*.

## Rationale

The "independent generation path" a `generated-test` criterion needs
to be trustworthy. Mirrors `llm-judge`'s own `judge` parameter.

## Scope

**In scope:** test code from a criterion's Given/When/Then prose plus
the target's `interface/`; canonical-model selection (R-AUTHOR-003);
caching.

**Out of scope:** deciding if a criterion needs a test — the `kind:`
tag, lint-checked (R-LINT-010), never re-decided here.

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

All `kind: generated-test` (`D43`) — the model call uses an injected
mock, `generator`'s pattern; none fit the step-phrase grammar.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

See the decisions, `D56` onward; `D269` adds the reply format to `interface/`.
