---
id: VAR-SECRET-PATTERNS-PATH
title: Secret Patterns Path
status: draft
owners: [pipeline-team]
---

# VAR-SECRET-PATTERNS-PATH

- **required:** no
- **type:** path
- **sensitivity:** non-secret
- **description:** Where `secret-scanner` reads its maintained,
  externally-sourced pattern database (`R-SECRET-001`) from — the
  same shape of input `license-scanner` reads from
  `VAR-LICENSE-CORPUS-PATH`, and governed by the same rule: never
  `.hotdocs/` (gitignored, local-only, and `SPEC_GUIDELINES.md` §1
  forbids any gate's pass/fail decision from depending on anything
  there — the exact mistake a real generated candidate made for
  `license-scanner` before this var pattern was established, `D51`).
  Absent means no pattern database is reachable; the scanner MUST
  still produce a real, recorded result (a clean one for the pattern-
  database-driven checks; entropy-based detection, which needs no
  external database, still runs), never an error and never a
  silently-skipped scan.
- **example:** `pipeline/secret-scanner/patterns.json`
