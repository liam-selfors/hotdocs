# R-LICENSE-007

**R-LICENSE-007** — When generation retries (best-of-k, owned by
  `merge-orchestrator`) and a later sample scans clean, the **original**
  flagged result MUST remain recorded — never overwritten or erased — with
  the clean result recorded alongside it as a separate entry, not a
  replacement. "Auto-resolved by retry" means the merge is no longer
  blocked; it does not mean the flag never happened.
