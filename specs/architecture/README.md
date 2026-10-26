# Architecture

The only place the component decomposition itself is declared and changed.
Splitting or merging components is a distinct, heavier, explicitly-reviewed
operation that goes through here — never an ordinary component spec edit.

See `SPEC_GUIDELINES.md` §3.2.

- **`pipeline-decomposition.md`** — the hotdocs pipeline tool's own
  21-component decomposition and dependency graph. Documents a real,
  deliberately-explained tension (`merge-orchestrator`'s fan-out exceeds
  D2's warn threshold) rather than silently patching it — D25 resolved
  the word-count half of that tension by extraction once it actually hit
  the hard-fail cap, and the fan-out half stays accepted-not-a-defect, by
  design, as a thin coordinator's expected shape. See the file's own
  "finding" section and its `Resolved (D25)` note for the full history.
- **`step-phrase-grammar.md`** — the fixed Given/When/Then step grammar
  every `compiled`-kind acceptance criterion is written against, and that
  `criterion-compiler` implements. A breaking change to every `compiled`
  criterion in the corpus, same governance weight as splitting a
  component (D2).
- **`graph-query-engine.md`** — the DuckDB-based engine (`yaml` extension
  for direct frontmatter queries, `duckpgq` for graph traversal) that
  queries the corpus's `depends_on`/`realizes`/`uses_var`/
  `depends_on_guarantees`/`covers` graph. Its "Query surface" section
  names the shared views (`nodes`, `edges`, `component_docs`,
  `component_provenance`) every adopter queries instead of writing its
  own ingestion — `impact-analyzer`'s blast-radius computation was the
  first adopter, since joined by `spec-linter`, `corpus-graph-builder`,
  `capability-scenario-verifier`, and `review-packet-builder` (D24, D26, D27).
