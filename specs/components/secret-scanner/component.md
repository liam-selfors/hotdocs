---
id: comp-secret-scanner
title: Secret Scanner
status: draft
owners: [pipeline-team]
depends_on: [comp-cache-manager]
realizes: [P-COMPLIANCE-GATE]
uses_var: [VAR-COMPLIANCE-WEBHOOK-URL]
model_pin: claude-sonnet-5
sealed: false
---

# Secret Scanner

## Purpose

Automated, unconditional scan of the entire repository for committed
secrets, using the `detect-secrets` library as its detection engine.
Same trust shape as `license-scanner`: no human sign-off required to
clear a flag, but no result is ever silent.

## Rationale

Same unconditional, no-sign-off posture as `license-scanner`. Detection
is a maintained library's, not this component's: a hand-built entropy
check flagged ordinary identifiers yet could never match a random hex
secret (`D168`).

**Known gaps, accepted (`D168`):** the entropy detectors read quoted
strings only, so an unquoted random token goes unseen; and
`KeywordDetector`, the only plugin that catches a low-entropy password,
is off because it flags any key containing a word like `secret`.

## Scope

**In scope:** whole-repository detection; the merge-blocking decision
(confidence-based); the notification path (risk-based, orthogonal to
it); the allowlist for reviewed fixtures and public constants
(`R-SECRET-012`) and the tool proposing its entries; caching; a
pre-commit form.

**Out of scope:** `spec-linter`'s `R-LINT-013` (a structural check on
`specs/vars/`; the two overlap on purpose), and whether a flagged scan
stops a merge, which `provenance-tracker` decides.

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

Every criterion is `kind: generated-test` (`D43`): the checks are deterministic
but not written in the step-phrase grammar.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D26`/`D53`/`D54`/`D163`/`D164`: notification errors, first generation, `gate_version`, CLI coverage.
- `D168`: `detect-secrets`, whole-repository scope, the allowlist and `propose`.
