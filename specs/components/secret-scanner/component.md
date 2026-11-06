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

Unconditional scan of the entire repository for committed
secrets, using `detect-secrets`. Same trust shape as `license-scanner`:
no human sign-off to clear a flag, but no result is ever silent.

## Rationale

Detection is a maintained library's: a hand-built entropy check flagged
ordinary identifiers yet could never match a random hex secret (`D168`).

**Known gaps, accepted (`D168`):** the entropy detectors read quoted
strings only, so an unquoted random token goes unseen, and
`KeywordDetector`, the only plugin catching a low-entropy password, is
off because it flags any key containing a word like `secret`.

## Scope

**In scope:** whole-repository detection; the confidence-based
blocking decision; the risk-based notification path; the sealed
allowlist (`R-SECRET-012`) and `propose`; caching; a pre-commit form.

**Out of scope:** `spec-linter`'s `R-LINT-013` (checks `specs/vars/`), and
whether a flagged scan stops a merge (`provenance-tracker` decides).

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

Every criterion is `kind: generated-test` (`D43`).

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D26`/`D53`/`D54`/`D163`/`D164`: notifications, first generation, `gate_version`, CLI.
- `D168`: `detect-secrets`, whole repository, allowlist, `propose`.
- `D195`: sealed allowlist.
