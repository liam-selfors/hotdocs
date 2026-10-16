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

- **R-LICENSE-001** — The scanner MUST compute a similarity score between
  `gen/<component>/`'s content and the reference corpus using k-gram
  (shingle) hashing: normalize source (strip whitespace/comments), tokenize,
  hash overlapping k-token windows, and compute the Jaccard-style ratio of
  matching window-hashes against the reference corpus's precomputed hash
  sets. A score at or above the configured **block threshold** MUST cause
  the merge to be blocked, the same way a failed test does — no human
  sign-off is required or able to override this. Block is a pure confidence
  determination, independent of which reference entry matched or how risky
  it is — that's R-LICENSE-003's job, not this one's.
- **R-LICENSE-002** — Every scan result — clean or flagged, regardless of
  whether it ultimately blocks the merge — MUST be written into the
  provenance manifest's `license_scan` field. A clean result MUST be
  recorded just as faithfully as a flagged one; absence of a flag MUST NOT
  mean absence of a record.
- **R-LICENSE-003** — Each reference-corpus entry MUST carry a declared
  **`risk_tier`** (`high` / `medium` / `low` — reflecting the matched
  entry's license family: e.g. `high` for strong-copyleft or
  unlicensed/proprietary sources, `medium` for weak-copyleft, `low` for
  permissive). A notification to `VAR-COMPLIANCE-WEBHOOK-URL` MUST fire
  when **either** the match blocked the merge (R-LICENSE-001) **or** the
  matched entry's `risk_tier` is `high` — regardless of confidence in the
  latter case. Severity is deliberately **not** a function of the
  similarity score: block answers "are we confident," `risk_tier` answers
  "how bad if real," and conflating the two would both over-notify on
  confident-but-low-risk matches and under-notify on uncertain-but-
  high-risk ones. Notification is independent of the merge outcome,
  including when a later retry (R-LICENSE-007) produces clean code, so an
  auto-resolved flag still gets seen. When `VAR-COMPLIANCE-WEBHOOK-URL` is
  absent, no notification is sent, but the record from R-LICENSE-002 still
  exists regardless.
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

- Exact k-gram window size and the reference-corpus format are
  implementation details not pinned down here.

## Change log

- Initial draft.
