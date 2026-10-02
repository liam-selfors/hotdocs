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
reference corpus; the merge-blocking decision; the separate severity-based
notification path; cache-awareness.

**Out of scope:** legal interpretation of a match (explicitly out of scope
for an engineering component — D7); maintaining the reference corpus's
content itself (treated as an external input, versioned via `gate_version`
like the signature database it is).

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

- **R-LICENSE-001** — The scanner MUST compute a similarity score between
  `gen/<component>/`'s content and the reference corpus using k-gram
  (shingle) hashing: normalize source (strip whitespace/comments), tokenize,
  hash overlapping k-token windows, and compute the Jaccard-style ratio of
  matching window-hashes against the reference corpus's precomputed hash
  sets. A score at or above the configured **block threshold** MUST cause
  the merge to be blocked, the same way a failed test does — no human
  sign-off is required or able to override this.
- **R-LICENSE-002** — Every scan result — clean or flagged, regardless of
  whether it ultimately blocks the merge — MUST be written into the
  provenance manifest's `license_scan` field. A clean result MUST be
  recorded just as faithfully as a flagged one; absence of a flag MUST NOT
  mean absence of a record.
- **R-LICENSE-003** — A match at or above a separate **severity threshold**
  MUST trigger a notification to `VAR-COMPLIANCE-WEBHOOK-URL`, independent
  of the merge outcome — including when a later retry (R-LICENSE-007)
  produces clean code, so an auto-resolved flag still gets seen by a human
  channel. When `VAR-COMPLIANCE-WEBHOOK-URL` is absent, no notification is
  sent, but the record from R-LICENSE-002 still exists regardless.
- **R-LICENSE-004** — Before scanning, the scanner MUST check
  `cache-manager` using key `(spec_bundle_hash, gen_output_hash, gate_version,
  model_pin)`; on a cache hit, the cached result MUST be reused and no
  rescan MUST occur.
- **R-LICENSE-005** — The reference corpus/signature database's own version
  MUST be part of `gate_version` (e.g. `license_scanner@3.1.0`) — reusing
  D11/D13's existing discipline that a gate's version is part of its own
  cache key, not restating it as a new mechanism. A signature-database
  update without a `gate_version` bump would let a stale cache hit mask a
  newly-added match; this requirement is what prevents that.
- **R-LICENSE-006** — The scanner MUST produce exactly one structured
  `LicenseScanResult` per component per scan, consumed by
  `provenance-writer` and `review-packet-builder`.
- **R-LICENSE-007** — When generation retries (best-of-k, owned by
  `merge-orchestrator`) and a later sample scans clean, the **original**
  flagged result MUST remain recorded — never overwritten or erased — with
  the clean result recorded alongside it as a separate entry, not a
  replacement. "Auto-resolved by retry" means the merge is no longer
  blocked; it does not mean the flag never happened.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`LicenseScanResult` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- **D7 never specified the relationship between the block threshold and the
  severity threshold** — whether they're two cutoffs on the same similarity
  score (e.g. block at 0.7, "severe" at 0.9), or orthogonal dimensions (e.g.
  severity depends on *which* license family matched — copyleft vs.
  permissive — not how similar the match was). This spec adopts the
  simpler same-scale reading (severity threshold ≥ block threshold, both
  configurable) as a concrete default, but this is a real gap in D7, not a
  judgment call this spec is positioned to close on its own — flagged for
  the main thread rather than silently assumed.
- Exact k-gram window size and the reference-corpus format are
  implementation details not pinned down here.

## Change log

- Initial draft.
