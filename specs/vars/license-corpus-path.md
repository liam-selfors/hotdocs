---
id: VAR-LICENSE-CORPUS-PATH
title: License Corpus Path
status: draft
owners: [pipeline-team]
---

# VAR-LICENSE-CORPUS-PATH

- **required:** no
- **type:** path
- **sensitivity:** non-secret
- **description:** Where `license-scanner` reads its precomputed
  k-gram reference corpus (`R-LICENSE-001`) from — a maintained,
  externally-sourced file this component treats as read-only input,
  never `.hotdocs/` (gitignored, local-only, and `SPEC_GUIDELINES.md`
  §1 forbids any gate's pass/fail decision from depending on anything
  there — a real generated candidate defaulted to exactly that path
  before this var existed to correct it, `D67`). Absent means no
  reference corpus is reachable; the scanner MUST still produce a
  real, recorded result (a clean one, per `R-LICENSE-001`'s own
  fail-to-empty posture for a missing/unavailable external input),
  never an error and never a silently-skipped scan.
- **example:** `pipeline/license-scanner/reference-corpus.json`
