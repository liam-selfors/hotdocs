# R-VERIFY-003

**R-VERIFY-003** — For every `llm-judge`-kind criterion, this component
  MUST invoke an injectable judge callable **exactly once**, passing
  exactly the same `CriterionBundle` `test_author` receives for that
  criterion (`R-VERIFY-009`) — never a separate, narrower payload —
  and record its pass/fail + rationale, or record `skipped` when no
  judge is configured. `CriterionBundle` is already the well-specified
  shape for "everything about this one criterion"; inventing a second,
  judge-specific shape alongside it would duplicate that without
  reason. (`capability-scenario-verifier`'s own judge/test_author
  bundle is necessarily narrower — no single component's
  `CriterionBundle` applies to a cross-component capability scenario —
  see the glossary's "Injected `judge`/`test_author` callable shape,"
  `D82`.) Call shape and result handling otherwise follow the same
  graceful-degradation posture `spec-linter`'s R-LINT-015 established,
  now a fourth instance. **This component's own behavior here is
  dispatch and recording, not judgment** — the judging happens inside
  whatever callable is injected, which is why every requirement in this
  component, including this one, is `kind: compiled`: coordinating
  non-deterministic work is itself a deterministic activity.

  **Exactly once is a deliberate simplification, not an oversight:** a
  design where two independent judge calls (e.g. two different models)
  are compared for disagreement was considered as part of
  `P-AMBIGUITY-GATE`'s judgment-ambiguity detection, but never built —
  this requirement makes the single-call behavior that's actually
  implemented explicit and normative, rather than leaving "how many judge
  calls" as an implicit property of whatever code happened to get written.
  The deferred dual-call design is recorded in `notes/initial-ideas.md`'s
  Future Enhancements section (§14), not lost.
