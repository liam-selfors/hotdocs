---
id: comp-secret-scanner
title: Secret Scanner
status: draft
owners: [pipeline-team]
depends_on: [comp-cache-manager]
realizes: [P-COMPLIANCE-GATE]
uses_var: [VAR-COMPLIANCE-WEBHOOK-URL]
model_pin: claude-opus-5-5
sealed: false
---

# Secret Scanner

## Purpose

Unconditional scan of the entire repository for committed
secrets, using `detect-secrets`. No result is ever silent.

## Rationale

See `D168`: detection is a maintained library's, and its accepted gaps.

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

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D26`, `D53`, `D54`, `D163`, `D164`, `D168`, `D195`.
