# R-MERGE-003

**R-MERGE-003** — For each impacted component, MUST check `cache-manager`
  for a cache hit on the full spec bundle before doing anything else; a hit
  MUST short-circuit straight to restoring the matching prior artifacts
  (D11), skipping R-MERGE-004 through R-MERGE-008 for that component
  entirely — not running them and discarding the result, actually skipping
  them.
