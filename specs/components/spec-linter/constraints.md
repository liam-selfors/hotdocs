---
id: comp-spec-linter-constraints
title: Spec Linter — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Spec Linter — Non-Functional Constraints

- **Determinism.** The same spec bundle, byte-for-byte, MUST always produce
  the same `LintReport`. Required for D13's cache-key correctness — a cache
  hit on `spec_bundle_hash` is only valid if the linter (and every other gate)
  is a pure function of its inputs.
- **Performance.** Linting a single component's full spec bundle MUST
  complete in under 2 seconds on reference hardware. This is a cheap,
  mechanical gate — it must not become the bottleneck in merge latency that
  D13 worked to keep the expensive gates from being.
- **No network access, no model calls.** Enforced structurally, not just by
  convention — `spec-linter` is a candidate for the strongest trust tier
  (`compiled` acceptance criteria, no model in the loop at all) specifically
  because its behavior is pure text/graph analysis.
- **Idempotent on unchanged input.** Running the linter twice against an
  unchanged spec bundle MUST produce byte-identical `LintReport` output, to
  support cache-hit comparison (D11/D13).
