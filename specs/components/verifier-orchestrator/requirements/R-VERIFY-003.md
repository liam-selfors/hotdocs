# R-VERIFY-003

**R-VERIFY-003** — For every `llm-judge`-kind criterion, this component
  MUST invoke an injectable judge callable and record its pass/fail +
  rationale, or record `skipped` when no judge is configured — the same
  graceful-degradation posture `spec-linter`'s R-LINT-015 established, now a
  fourth instance. **This component's own behavior here is dispatch and
  recording, not judgment** — the judging happens inside whatever callable
  is injected, which is why every requirement in this component, including
  this one, is `kind: compiled`: coordinating non-deterministic work is
  itself a deterministic activity.
