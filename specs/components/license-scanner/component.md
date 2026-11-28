---
id: comp-license-scanner
title: License Scanner
status: draft
owners: [pipeline-team]
depends_on: [comp-cache-manager]
realizes: [P-COMPLIANCE-GATE]
uses_var: [VAR-COMPLIANCE-WEBHOOK-URL, VAR-LICENSE-CORPUS-PATH]
model_pin: claude-opus-5-5
sealed: false
---

# License Scanner

## Purpose

Automated, unconditional scan of `gen/<component>/` against a reference
corpus of known-licensed-code fingerprints. A match blocks the merge
with no human sign-off, and a scan that had no corpus to compare against
says it evaluated nothing rather than reporting a clean pass.

## Rationale

The original brainstorm established this scan's unconditional, no-sign-off posture.

## Scope

**In scope:** fingerprinting generated code; comparing against the
reference corpus; the merge-blocking decision (confidence-based); the
severity-based notification path; cache-awareness.

**Out of scope:** legal interpretation of a match; maintaining the
reference corpus's content itself, including its per-entry `risk_tier`
classifications.

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

`D26`, `D51`, `D52`, `D163`, `D164`, `D165`, `D193`, `D372`.
