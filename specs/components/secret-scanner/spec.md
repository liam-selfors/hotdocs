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

Automated, unconditional scan of `specs/`, `gen/`, and `verification/` for
secret-shaped strings (API-key/token patterns, high-entropy strings) per
D12. Same trust shape as `license-scanner`: no human sign-off required to
clear a flag, but no result is ever silent.

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

- **R-SECRET-001** — On a full scan, the scanner MUST check every file
  under `specs/`, `gen/`, and `verification/` against a pattern database
  (common API-key/token shapes) and a high-entropy-string heuristic. Each
  pattern-database rule MUST carry a declared **`risk_tier`** (`high` /
  `medium` / `low`) — `high` for a recognizable, provider-specific
  credential shape (e.g. an AWS access-key-ID format, a GitHub PAT prefix, a
  PEM private-key block), `low` for a generic high-entropy-string heuristic
  with no specific shape behind it (more prone to false positives; a real
  secret is possible but far less certain from the pattern alone).
- **R-SECRET-002** — A match MUST block the merge, the same way a failed
  test does — no human sign-off is required or able to override this. Block
  is a pure confidence determination (did the pattern/entropy check match
  at all), independent of which rule matched or how risky that rule's
  shape is — that's R-SECRET-004's job, not this one's.
- **R-SECRET-003** — Every scan result — clean or flagged — MUST be written
  into the provenance manifest, regardless of outcome. Absence of a flag
  MUST NOT mean absence of a record.
- **R-SECRET-004** — A notification to `VAR-COMPLIANCE-WEBHOOK-URL` MUST
  fire when **either** a match blocked the merge (R-SECRET-002) **or** the
  matched rule's `risk_tier` is `high` — mirroring `license-scanner`'s
  R-LICENSE-003 exactly, the same orthogonal block/severity split, not a
  second, independently-designed mechanism. Independent of the merge
  outcome, including when a retry later scans clean.
- **R-SECRET-005** — Before scanning, the scanner MUST check
  `cache-manager` using key `(spec_bundle_hash, gen_output_hash, gate_version,
  model_pin)`; on a cache hit, the cached result MUST be reused.
- **R-SECRET-006** — The pattern database's own version MUST be part of
  `gate_version` (e.g. `secret_scanner@2.0.0`) — reusing D11/D13's existing
  discipline, same as `license-scanner`'s R-LICENSE-005, not a new
  mechanism.
- **R-SECRET-007** — The scanner MUST produce exactly one structured
  `SecretScanResult` per scan, consumed by `provenance-writer` and
  `review-packet-builder`.
- **R-SECRET-008** — The scanner MUST support a separate, lightweight
  invocation mode — scoped only to the files touched by a pending commit or
  push, not the whole corpus — for use as a pre-commit/pre-push hook,
  distinct from the full merge-gate run (D12's "as early as pre-commit/
  pre-push where tooling allows"). This mode uses the same pattern database
  and detection logic, just a narrower file set and no cache-manager
  dependency (a pre-commit hook running before a commit even exists has
  nothing stable to key a cache entry on).
- **R-SECRET-009** — Mirroring `license-scanner`'s R-LICENSE-007: when a
  retried generation sample scans clean after an earlier flagged sample,
  the original flagged result MUST remain recorded, not overwritten.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`SecretScanResult` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Exact pattern database (which key/token shapes, entropy threshold) is an
  implementation detail not pinned down here.

## Change log

- Initial draft.
