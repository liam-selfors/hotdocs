# Spec Linter — Non-Functional Constraints

- **Determinism, for every rule except R-LINT-015.** The same spec
  bundle, byte-for-byte, MUST always produce the same result — an
  `llm-judge` evaluation isn't guaranteed reproducible the way a
  `compiled` check is, so its result is excluded from the cache-key
  contribution the other rules make.
- **Performance.** The `compiled` rules, together, MUST complete in
  under 2 seconds on reference hardware. R-LINT-015 (a model call) has
  its own separate, longer budget, uncounted against that figure.
- **Mostly no network access, no model calls.** R-LINT-015 is the
  single, intentional exception — `llm-judge` is for qualities no test
  could capture, and "conflicts in meaning with the glossary" is
  exactly that. **When no model is configured, it degrades to
  `skipped`, never silently passing and never crashing.**
- **Idempotent on unchanged input,** for every rule's non-`skipped`
  results — running the linter twice against an unchanged bundle MUST
  produce byte-identical results for every `compiled` rule.
- **Verification against real content, not only synthetic fixtures.**
  The acceptance-criteria test suite SHOULD include checks against
  actual, organically-authored spec content, not only single-violation
  fixtures. See `verification/spec-linter/BOOTSTRAP.md`.
