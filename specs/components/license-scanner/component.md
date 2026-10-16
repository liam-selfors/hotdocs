---
id: comp-license-scanner
title: License Scanner
status: draft
owners: [pipeline-team]
depends_on: [comp-cache-manager]
realizes: [P-COMPLIANCE-GATE]
uses_var: [VAR-COMPLIANCE-WEBHOOK-URL]
model_pin: claude-sonnet-5
sealed: false
---

# License Scanner

## Purpose

Automated, unconditional scan of `gen/<component>/` against a reference
corpus of known-licensed-code fingerprints (D7). No human sign-off is
required to clear a flag — a match blocks the merge the same way a failed
test does — but no result, clean or flagged, is ever silent: every scan
result is written to the provenance manifest regardless of outcome.

## Scope

**In scope:** fingerprinting generated code; comparing against the
reference corpus; the merge-blocking decision (confidence-based); the
severity-based notification path (risk-based, orthogonal to confidence —
see the D7 addendum in `notes/initial-ideas.md`); cache-awareness.

**Out of scope:** legal interpretation of a match (explicitly out of scope
for an engineering component — D7); maintaining the reference corpus's
content itself, including its per-entry `risk_tier` classifications
(treated as an external input, versioned via `gate_version` like the
signature database it is — assigning a license family's risk tier is
itself a judgment call made when the reference corpus is curated, not by
this component at scan time).

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

Every criterion is `kind: compiled` — k-gram fingerprint hashing and
threshold comparison are deterministic; nothing here needs a model or
judgment.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Exact k-gram window size and the reference-corpus format are
  implementation details not pinned down here.

## Change log

- Initial draft.
