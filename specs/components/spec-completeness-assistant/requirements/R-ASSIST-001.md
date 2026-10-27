# R-ASSIST-001

**R-ASSIST-001** — MUST run `spec-linter` against the draft spec change
  first, and surface any hard-fail finding to the developer immediately —
  before any judgment-based analysis runs. Same "cheap, deterministic gate
  first" ordering `hotdocs generate`'s own workflow already uses (a
  developer runs spec-linter before attempting generation), applied
  here on the feature-branch side.
