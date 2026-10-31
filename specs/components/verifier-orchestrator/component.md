---
id: comp-verifier-orchestrator
title: Verifier Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-generator, comp-test-author, comp-spec-bundle-assembler]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-sonnet-5
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
- `D27`: added `failure_detail` (`R-VERIFY-012`) to `criteria[]` for
  `compiled`/`generated-test` failures, mirroring `llm-judge`'s
  `rationale`.
- `D84`: `R-VERIFY-004` clarified as one-directional — an extra,
  undocumented public name is never drift on its own, found by a real
  candidate's false-positive set-equality implementation.
- `D85`: `R-VERIFY-012` clarified that `failure_detail.expected`/
  `.actual` must be their original Python type, not a raw string,
  found by the same real candidate leaving them as unparsed text.
- `D119`: `depends_on` gains `comp-spec-bundle-assembler` — the real
  candidate had never implemented `R-VERIFY-009`'s own existing
  "pass exactly the `CriterionBundle` spec-bundle-assembler produces"
  requirement, instead building a second, independent, narrower
  `CriterionBundle` with no `dependency_interfaces` at all. Found only
  once every dependency-shape-guessing test-authoring failure this
  session traced back to this one, silent gap. `R-VERIFY-009` now
  states the prohibition explicitly. Cold-regenerated directly,
  validated against the existing hand-maintained suite plus one new
  test proving real dependency interface text now flows through.
- `D120`: `R-VERIFY-013` — every dynamically loaded module MUST be
  cached by `(repo_root, module_name)`, never `module_name` alone —
  found once the regenerated candidate's own `load_component_module`
  cached a bare module name across two different `repo_root`s in the
  same pytest session, producing a stale-module regression on
  `AC-VERIFY-004`/`005` despite the interface-drift check's own logic
  being correct. The identical bug class `R-TRACK-011` already closed
  for `provenance-tracker`. New `AC-VERIFY-014`.
- `D124`: `R-VERIFY-006` — `mutation_score` is a union across all of a
  component's `generated-test` criteria, never a per-criterion average.
  New `AC-VERIFY-015`.
- `D158`: `R-VERIFY-014` — every test run gets a timeout; a timed-out
  mutant counts as killed. New `AC-VERIFY-016`.
