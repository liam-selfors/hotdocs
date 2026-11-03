# R-VERIFY-003

**R-VERIFY-003** — For every `llm-judge`-kind criterion, this component
  MUST invoke an injectable judge callable **exactly once**, passing
  exactly the same `CriterionBundle` `test_author` receives for that
  criterion (`R-VERIFY-009`) — never a separate, narrower payload — and
  record its pass/fail + rationale, or record `skipped` when no judge is
  configured. (`capability-scenario-verifier`'s bundle is necessarily
  narrower; see the glossary's "Injected `judge`/`test_author` callable
  shape," `D65`.) Call shape and result handling follow the
  graceful-degradation posture of `spec-linter`'s R-LINT-015. This
  component's own behavior is dispatch and recording, not judgment,
  which is why every requirement here is deterministic. Exactly once is
  deliberate: a dual-call design that compares two judges was
  considered and deferred (`notes/initial-ideas.md` §14).
