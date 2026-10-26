# Spec Linter — Non-Functional Constraints

- **Determinism, for 26 of 27 rules.** The same spec bundle, byte-for-byte,
  MUST always produce the same result for every rule except R-LINT-015 —
  required for D13's cache-key correctness; an `llm-judge` evaluation
  isn't guaranteed reproducible the way a `compiled` check is, so its
  result is excluded from the cache-key contribution the other 26 make.
- **Performance.** The 26 `compiled` rules, together, MUST complete in
  under 2 seconds on reference hardware. R-LINT-015 (a model call) has
  its own separate, longer budget, uncounted against that figure.
- **Mostly no network access, no model calls.** R-LINT-015 is the single,
  intentional exception (rationale: D5 — `llm-judge` is for qualities no
  test could capture, and "conflicts in meaning with the glossary" is
  exactly that). **When no model is configured, it degrades to
  `skipped`, never silently passing and never crashing** — the same
  posture D10 established for model-pin availability.
- **Idempotent on unchanged input,** for every rule's non-`skipped`
  results — running the linter twice against an unchanged bundle MUST
  produce byte-identical results for the 26 `compiled` rules.
- **Verification against real content, not only synthetic fixtures.**
  The acceptance-criteria test suite SHOULD include checks against
  actual, organically-authored spec content, not only single-violation
  fixtures — a lesson from this component's own bootstrap
  (`verification/spec-linter/BOOTSTRAP.md`): a complete fixture suite
  passed cleanly while a real bug (RFC-2119 checking missed wrapped
  continuations) survived until real content existed to run against.
