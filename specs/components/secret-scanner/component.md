---
id: comp-secret-scanner
title: Secret Scanner
status: draft
owners: [pipeline-team]
depends_on: [comp-cache-manager]
realizes: [P-COMPLIANCE-GATE]
uses_var: [VAR-COMPLIANCE-WEBHOOK-URL, VAR-SECRET-PATTERNS-PATH]
model_pin: claude-sonnet-5
sealed: false
---

# Secret Scanner

## Purpose

Automated, unconditional scan of `specs/`, `gen/`, and `verification/`
for secret-shaped strings (API-key/token patterns, high-entropy
strings). Same trust shape as `license-scanner`: no human sign-off
required to clear a flag, but no result is ever silent.

## Rationale

D12 established this scan's unconditional, no-sign-off posture,
mirroring D7's for `license-scanner`.

## Scope

**In scope:** pattern- and entropy-based detection across all three
directories; the merge-blocking decision (confidence-based); the
severity-based notification path (risk-based, orthogonal to confidence —
see the D7 addendum in `notes/initial-ideas.md`); cache-awareness; a
lightweight pre-commit/pre-push invocation distinct from the full
merge-gate run.

**Out of scope:** `spec-linter`'s R-LINT-013 (the narrow, structural check
that a `specs/vars/` declaration with `sensitivity: secret` carries no
`example`/`default` field) — that's a schema check on one document type;
this component is a broader, textual scan across three whole directories
for secret-*shaped* strings wherever they appear, including inside prose. The
two are deliberately overlapping defense-in-depth, not redundant: R-LINT-013
closes off the structural way a secret could enter a `vars/` declaration;
this component catches the case someone pastes one into a spec's prose, a
comment, or generated code anyway.

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

Every criterion is `kind: generated-test` (`D59`) — pattern and entropy
matching are deterministic and need no model or judgment, but none are
actually written in the step-phrase grammar, so `kind: compiled` would
not describe how they're really verified.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Exact pattern database (which key/token shapes, entropy threshold) is
  an implementation detail not pinned down here~~ — resolved
  (`R-SECRET-001`): entropy threshold 4.0 bits/char; the shape database is
  sourced from a maintained external reference set, never hand-rolled and
  frozen into this spec.

## Change log

- Initial draft.
- `D38`: added `notification_delivery_error`, mirroring
  `license-scanner`'s same fix.
- `D69`/`D70`: `VAR-SECRET-PATTERNS-PATH` proactively declared before
  the first real `generate()` attempt (mirroring `license-scanner`'s
  `D67`); that attempt passed all 10 directly-testable `AC-SECRET-*`
  criteria on the first real try. `gen/secret-scanner/
  secret_scanner.py` is now that candidate.
