# R-ASSIST-007

**R-ASSIST-007** — When no model is configured, MUST make no model
  call of any kind — no `llm-endpoint` call and no `glossary_judge`,
  so `lint` receives `judge=None` — and MUST still run R-ASSIST-001–003:
  lint findings, predicted blast radius, and criterion reviews. It MUST
  report R-ASSIST-004/005 as skipped: `degraded` true,
  `completeness_score`/`completeness_rationale` null,
  `redundancy_flags` empty.
