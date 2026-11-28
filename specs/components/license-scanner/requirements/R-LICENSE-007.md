# R-LICENSE-007

**R-LICENSE-007** — A scan MUST never delete or overwrite an earlier
  result for different content: results are cached by content
  (`R-LICENSE-004`), so a clean scan after a flagged one adds an entry,
  and scanning the flagged content again returns the flagged result.
  Per-attempt records of flagged attempts are kept by the caller
  (`.hotdocs/attempts/`, `D19`, `D378`).
