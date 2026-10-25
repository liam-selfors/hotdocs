# Generator — Non-Functional Constraints

- **Not deterministic, and that's expected — but bounded.** Unlike every
  other component specced so far, a fresh model call is not required to be
  reproducible. What MUST be deterministic: a **cache hit** (R-GEN-005)
  always returns byte-identical output for the same key, and the recorded
  `seed` always matches what was actually requested (R-GEN-007) — those are
  the properties D11/D13's cache-key correctness actually depends on, not
  "the model always says the same thing."
- **Defense-in-depth on write paths.** R-GEN-009's sealed/pinned-override
  check MUST be enforced here even though `merge-orchestrator`'s own
  routing requirement (R-MERGE-015) means it should never call this
  component for a sealed component's regeneration in the first place — a
  second, independent layer, not a redundant one to remove now that the
  primary layer is a real requirement rather than an assumption.
- **No wasted model calls on a known-refused target.** R-GEN-009's
  precondition check MUST run, and MUST short-circuit, before any model
  call — paying for a call whose result can never be written is pure
  waste.
- **No silent partial output.** A model-call error MUST leave
  `gen/<component>/` untouched — never a half-written tree.
- **Credential handling.** Since `D30`, this component no longer holds
  `VAR-ANTHROPIC-API-KEY` at all — `llm-endpoint` does
  (`R-ENDPOINT-005`) — so it's structurally absent from
  `GenerationResult`, logs, and the provenance manifest, not merely
  filtered out of them. Only `model` (the identifier) is ever recorded.
