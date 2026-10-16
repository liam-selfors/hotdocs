# R-MERGE-010

**R-MERGE-010** — Once `provenance-writer` has completed for every
  impacted component **and** golden-scenario verification (R-MERGE-014)
  has completed for this merge, MUST invoke `corpus-graph-builder` and
  `review-packet-builder` — both need the golden-scenario results to
  include in their output, so neither runs before R-MERGE-014 does.
