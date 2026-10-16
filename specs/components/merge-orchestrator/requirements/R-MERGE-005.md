# R-MERGE-005

**R-MERGE-005** — **This is the best-of-k retry loop (D3), owned here.**
  If `verifier-orchestrator`'s verdict is `fail`, MUST call `generator`
  again with a new sample index, up to a configured `k` (default range
  2–4) total attempts, re-verifying each. The first sample whose verdict is
  `pass` MUST be kept; its sample index MUST be the one recorded for
  provenance (D3).
