# R-DOCS-002

**R-DOCS-002** — For each component node, the detail view MUST show:
  rendered `component.md`/`requirements/`/`interface/`/`acceptance/`/
  `constraints.md` content; its `R-id` list with live status; acceptance
  criteria broken out
  by `kind` with verification result; provenance (model pin, prompt
  version, last cold-regen timestamp, freshness relative to D1); size vs.
  D2 caps, color-coded; `sealed`/pinned-override exemption status; owners —
  D9's enumerated list, minus the verification-toggle item D9 originally
  specified (`cross_model_divergence_check`/`fallback_standby_build`),
  since this build has no repo-wide toggles to display (see
  `notes/initial-ideas.md`'s Future Enhancements section) — nothing else
  added, nothing else dropped.
