# R-GRAPH-003

**R-GRAPH-003** — Each component node MUST carry its verification
  report, provenance, size status, `sealed` status and pinned overrides,
  exactly as `interface/data/CorpusGraph.md` defines them. Verification
  and provenance both come from the one provenance manifest
  `provenance-writer` wrote, whose `verification_report` already embeds
  the full report, never from a second read of `verifier-orchestrator`'s
  output.
