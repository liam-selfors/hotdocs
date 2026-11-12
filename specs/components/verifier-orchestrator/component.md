---
id: comp-verifier-orchestrator
title: Verifier Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-generator, comp-test-author, comp-spec-bundle-assembler]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Verifier Orchestrator

## Purpose

Runs every applicable verification gate against one component's generated
output and produces a single, structured pass/fail verdict: `compiled`
criteria (via `criterion-compiler`), `generated-test` criteria, `llm-judge`
criteria, the contract/property tests derived from `interface/`, and the
interface drift check.

## Scope

**In scope:** dispatching each acceptance criterion to the right checking
mechanism by its declared `kind`; running the interface drift check;
aggregating mutation scores; producing one `VerificationReport`.

**Out of scope:** the license/secret scans (separate components);
*performing* an `llm-judge` evaluation or *authoring*
`generated-test` code (this component dispatches to an injectable judge and
an injectable `test_author` and records their results — it does not itself
judge or author anything, see the note below); **re-deciding a criterion's
declared `kind`** — `compiled`/`generated-test`/`llm-judge` is fixed at
spec-authoring time in `acceptance/`, lint-checked (R-LINT-010), and never
reconsidered here. Giving this component (or `test-author`) the power to
override that declaration at verification time was considered and
explicitly rejected: it would make `kind:` advisory rather than normative,
and would turn this component's own dispatch logic into a judgment call,
breaking the determinism cache-key validity and R-VERIFY-008's
idempotency claim both depend on.

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

All thirteen criteria are `kind: compiled` — this component coordinates
checking mechanisms (some of which involve judgment or external calls), but
the coordination itself is deterministic dispatch-and-record logic, testable
by mocking `criterion-compiler` and the judge callable. A fourth component
in this corpus whose entire acceptance set is `compiled`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None. The gap this spec originally surfaced — which component authors
`generated-test` code — is resolved: `test-author`, invoked via the
`test_author` injectable callable (R-VERIFY-009), the same pattern already
established for `judge`.

## Change log

- Initial draft.
- `D27`–`D124`: `failure_detail` on failing criteria (`R-VERIFY-012`);
  one-directional interface drift (`R-VERIFY-004`); the exact
  `CriterionBundle` (`R-VERIFY-009`); modules cached per `repo_root`
  (`R-VERIFY-013`); `mutation_score` a union (`R-VERIFY-006`).
- `D158`: `R-VERIFY-014` — every test run times out; a timed-out mutant
  counts as killed.
- `D163`: `R-VERIFY-015` exposes `GATE_VERSION`; `R-VERIFY-016` keeps
  a lettered criterion id (`AC-FOO-003b`) exactly as written.
- `D171`: `R-VERIFY-017` — sealed components are verified at
  `source_path` by their characterization tests; `verify` had no
  sealed support before. New `AC-VERIFY-019`.
- `D172`: `R-VERIFY-006` pins the exact operator swaps; a
  regeneration had silently changed the mutation bar.
- `D190`: CLI renamed `hotdocs verify-component` (`R-VERIFY-018`);
  `verify` returns an object, not a dict.
