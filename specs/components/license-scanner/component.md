---
id: comp-license-scanner
title: License Scanner
status: draft
owners: [pipeline-team]
depends_on: [comp-cache-manager]
realizes: [P-COMPLIANCE-GATE]
uses_var: [VAR-COMPLIANCE-WEBHOOK-URL, VAR-LICENSE-CORPUS-PATH]
model_pin: claude-sonnet-5
sealed: false
---

# License Scanner

## Purpose

Automated, unconditional scan of `gen/<component>/` against a reference
corpus of known-licensed-code fingerprints. No human sign-off is
required to clear a flag — a match blocks the merge the same way a
failed test does — but no result is ever silent: every scan result is
written to the provenance manifest regardless of outcome, and a scan
that had no corpus to compare against says it evaluated nothing rather
than reporting a clean pass.

## Rationale

The original brainstorm established this scan's unconditional, no-sign-off posture.

## Scope

**In scope:** fingerprinting generated code; comparing against the
reference corpus; the merge-blocking decision (confidence-based); the
severity-based notification path (risk-based, orthogonal to confidence —
see the addendum in `notes/initial-ideas.md`); cache-awareness.

**Out of scope:** legal interpretation of a match (explicitly out of scope
for an engineering component); maintaining the reference corpus's
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

Every criterion is `kind: generated-test`: fingerprint hashing and
threshold comparison are deterministic and need no model, but none is
written in the step-phrase grammar.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Exact k-gram window size and the reference-corpus format are
  implementation details not pinned down here~~ — resolved (`R-LICENSE-001`):
  9-token windows; the corpus is precomputed hashes plus metadata, sourced
  from a maintained external reference set, never raw license text and
  never a one-time list frozen into this spec.

## Change log

- Initial draft.
- `D26`: added `notification_delivery_error` to distinguish a webhook
  call that was never due from one that was due and failed to deliver.
- `D51`: new `VAR-LICENSE-CORPUS-PATH` — a real `generate()` candidate
  defaulted the reference corpus's location to `.hotdocs/`, which
  `SPEC_GUIDELINES.md` forbids any gate decision from depending on.
  `R-LICENSE-001` now names the real location explicitly.
- `D52`: a second retry, with that fix in place, passed all 8 directly
  testable `AC-LICENSE-*` criteria for real — first successful
  implementation. `gen/license-scanner/license_scanner.py` is now that
  candidate. See `verification/license-scanner/BOOTSTRAP.md`.
- `D163`/`D164`/`D165`: `gate_version`, CLI coverage, test-environment facts.
- `D193`: honest gate — `evaluated`/`reason` on every result; no corpus
  is a visible, non-blocking `not evaluated`; a configured but unusable
  corpus fails closed. `gate_version` is now `license_scanner@4.0.x`.
