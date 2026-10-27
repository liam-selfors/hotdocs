# R-GRAPH-003

**R-GRAPH-003** — Each component node MUST carry its current
  verification status and provenance summary — both read from
  `provenance-writer`'s manifest, a single artifact: the manifest's
  own `verification_report` field already embeds the full
  `VerificationReport` (`interface/data/provenancemanifest.md`), never
  a second, separate read of `verifier-orchestrator`'s own output —
  plus size-vs-D2-caps status and `sealed`/pinned-override status —
  everything D9's per-node detail view needs, assembled once here
  rather than separately by the renderer.
