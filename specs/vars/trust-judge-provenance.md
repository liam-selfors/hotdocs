---
id: VAR-TRUST-JUDGE-PROVENANCE
title: Trust Judge Provenance
status: draft
owners: [pipeline-team]
---

# VAR-TRUST-JUDGE-PROVENANCE

- **required:** no
- **type:** boolean
- **sensitivity:** non-secret
- **description:** Whether `provenance-checker` (`D39`) may honor a
  feature-branch-committed `.provenance.json` for a component whose
  acceptance set includes an `llm-judge`-kind criterion, trusting its
  embedded `verification_report` instead of re-dispatching to the judge
  callable at merge time. Absent means `true` — a new or early-stage
  repo leans on cheap, developer-triggered cold regen (`D1`) without
  unconditionally re-paying for a non-reproducible judge call on every
  merge. Setting this to `false` is how a maturing repo deliberately
  hardens its own governance later: every `llm-judge` criterion is then
  always re-evaluated for real at merge time, regardless of any
  feature-branch claim. This default is a deliberate exception to this
  corpus's otherwise-conservative absent-value defaults (`R-CACHE-004`,
  `R-ASSIST-007`) — those answer "what happens when something is broken
  or unavailable," this answers "what governance posture does a project
  start at before it has decided anything," which is a different
  question with a different right answer. Never affects `compiled`/
  `generated-test` criteria — those are always cheaply, deterministically
  re-verified at merge time regardless of this variable, since nothing
  about running already-authored code is ever non-reproducible.
- **example:** `false`
