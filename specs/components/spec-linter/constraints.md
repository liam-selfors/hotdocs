# Spec Linter — Non-Functional Constraints

- **Determinism.** The same spec bundle, byte for byte, MUST produce the
  same result for every rule but the `llm-judge` R-LINT-015, which is
  excluded from the cache-key contribution.
- **Performance.** The `compiled` rules together MUST finish in under 2
  seconds on reference hardware; R-LINT-015 has its own budget.
- **No network, no model calls,** except R-LINT-015, which with no model
  configured is `skipped`, never a silent pass or a crash.
- **Tested on real content,** not only synthetic fixtures (see
  `verification/spec-linter/BOOTSTRAP.md`).
