# R-ASSIST-007

**R-ASSIST-007** — When no model is configured, MUST make no model
  call of any kind — neither `llm-endpoint` directly nor `generator`
  (which dispatches through it) — and MUST still run R-ASSIST-001–003:
  lint findings, predicted blast radius, and hint previews, each
  preview being the hint-mode bundle alone (`R-ASSIST-003`). It MUST
  report R-ASSIST-004/005 as skipped: `degraded` true,
  `completeness_score`/`completeness_rationale` null,
  `redundancy_flags` empty. The same graceful-degradation posture
  `spec-linter`'s R-LINT-015 established, now a further instance.
