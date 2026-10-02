---
id: comp-generator-constraints
title: Generator — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Generator — Non-Functional Constraints

- **Not deterministic, and that's expected — but bounded.** Unlike every
  other component specced so far, a fresh model call is not required to be
  reproducible. What MUST be deterministic: a **cache hit** (R-GEN-005)
  always returns byte-identical output for the same key, and the recorded
  `seed` always matches what was actually requested (R-GEN-007) — those are
  the properties D11/D13's cache-key correctness actually depends on, not
  "the model always says the same thing."
- **Defense-in-depth on write paths.** R-GEN-009's sealed/pinned-override
  check MUST be enforced here even though `merge-orchestrator` should never
  call this component for a sealed component's regeneration in the first
  place — a second, independent layer, not a redundant one to remove.
- **No silent partial output.** A model-call error MUST leave
  `gen/<component>/` untouched — never a half-written tree.
- **Credential handling.** `VAR-ANTHROPIC-API-KEY` MUST never appear in
  `GenerationResult`, logs, or the provenance manifest — only `model`
  (the identifier) is recorded, never the credential used to reach it.
