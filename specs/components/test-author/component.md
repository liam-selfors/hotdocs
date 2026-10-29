---
id: comp-test-author
title: Test Author
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager, comp-llm-endpoint]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-sonnet-5
sealed: false
---

# Test Author

## Purpose

Authors the test code for one `generated-test`-kind acceptance
criterion: an agent authoring the test from spec prose alone, with no
access to the implementation under test. Invoked by
`verifier-orchestrator` via an injectable callable, not sequenced as a
top-level pipeline step — `verifier-orchestrator` decides *when* a test
needs authoring (a criterion's `kind` says so, already fixed at
spec-authoring time); this component decides *how* to author one.

## Rationale

The "independent generation path" a `generated-test` criterion
requires for that `kind` to be trustworthy. The injectable-callable
pattern mirrors `llm-judge`'s own `judge` parameter.

## Scope

**In scope:** producing test code from one criterion's Given/When/Then
prose plus the target component's `interface/` content; model selection
(the canonical model alone, R-AUTHOR-003); caching.

**Out of scope, deliberately:** deciding whether a criterion needs a
test at all — that is the `kind:` tag in `acceptance/`, fixed at
spec-authoring time and lint-checked (R-LINT-010), never re-decided
here or by `verifier-orchestrator` at verification time, which would
make a ratified spec's declared `kind` advisory, not normative, and
break `verifier-orchestrator`'s determinism.

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

All `kind: generated-test` (`D43`) — behavior around the external
model call is exercised via an injected mock model, same pattern
`generator`'s own suite already established; `R-AUTHOR-002`/`006`'s
pure path/data-safety checks need no model either, but none of these
criteria are actually written in the step-phrase grammar, so
`kind: compiled` would not describe how they're really verified.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

Full accounts live in `verification/test-author/BOOTSTRAP.md`.

- Initial draft; `D56`–`D58` first real implementation, 8/8
  `AC-AUTHOR-*`.
- `D94`–`D129`: `R-AUTHOR-009`–`023`, full round-by-round account in
  `BOOTSTRAP.md`. Covers: nonce-delimited output; dynamic,
  worked-example dependency resolution (`009`–`011`); lint-clean
  synthetic fixtures, never `import yaml` (`012`–`015`); missing
  `dependency_interfaces` tolerated, `seed` never forwarded,
  malformed/wrong-arity output rejected incl. alias resolution and
  string literals, dual access on the target's own return
  (`016`–`021`); never asserting fake usage via a guessed
  `sys.modules` key (`022`); write-time window truncation to the
  field's own documented precision (`023`, `D129`).
