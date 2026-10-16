# Spec Linter — Non-Functional Constraints

- **Determinism, for 14 of 15 rules.** The same spec bundle, byte-for-byte,
  MUST always produce the same result for every rule except R-LINT-015.
  Required for D13's cache-key correctness — a cache hit on
  `spec_bundle_hash` is only valid if a gate is a pure function of its
  inputs, which is why R-LINT-015's result is excluded from the cache-key
  contribution other rules make (an `llm-judge` evaluation is not guaranteed
  reproducible the way a `compiled` check is).
- **Performance.** The 14 `compiled` rules, together, MUST complete in under
  2 seconds on reference hardware — this is a cheap, mechanical gate and
  must not become the merge-latency bottleneck D13 worked to avoid.
  R-LINT-015, when it runs (a model call), is allowed its own separate,
  longer budget and is not counted against the 2-second figure.
- **Mostly no network access, no model calls — one deliberate exception.**
  14 of 15 requirements are pure text/graph analysis, enforced structurally:
  `spec-linter` is close to, but not quite, the strongest trust tier
  (fully `compiled`, no model in the loop at all). R-LINT-015 is the single,
  intentional exception — consistent with D5's own guidance that `llm-judge`
  is for qualities no test could capture even in principle, which is exactly
  what "does this text conflict in meaning with the glossary" turned out to
  be once actually implemented. **When no model is configured, R-LINT-015
  degrades to `skipped`, never silently passing and never crashing** — the
  same posture D10 established for model-pin availability and
  `cache-manager` established for backing-store availability, applied here
  a third time.
- **Idempotent on unchanged input,** for every rule's non-`skipped` results.
  Running the linter twice against an unchanged spec bundle MUST produce
  byte-identical results for the 14 `compiled` rules, to support cache-hit
  comparison (D11/D13).
- **Verification against real content, not only synthetic fixtures.** The
  acceptance-criteria test suite SHOULD include checks run against actual,
  organically-authored spec content from this corpus (not only single-
  violation fixtures built to exercise one rule at a time) — a lesson from
  this component's own bootstrap (`verification/spec-linter/BOOTSTRAP.md`),
  where a complete fixture suite passed cleanly while a real bug (the
  RFC-2119 check only reading one physical line, missing wrapped
  continuations) survived undetected until real, multi-author content
  existed to run against. `SHOULD`, not `MUST`: this is a testing-practice
  recommendation about how confidence is built, not a checkable behavior of
  the linter itself.
