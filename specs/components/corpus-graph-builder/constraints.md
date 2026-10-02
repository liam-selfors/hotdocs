---
id: comp-corpus-graph-builder-constraints
title: Corpus Graph Builder — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Corpus Graph Builder — Non-Functional Constraints

- **Determinism.** Same corpus/provenance/verification state MUST always
  produce a byte-identical `corpus-graph.json` — needed both for D6's
  commit discipline and for this file to participate correctly in
  cache-hit comparisons like any other gate output.
- **Single source of truth.** No other component MUST produce a competing
  view of the corpus graph — `docs-site-renderer` and D8's traceability
  matrix both read this one file; neither recomputes any part of it.
- **No network access, no model calls.** Pure graph assembly over already-
  computed data.
