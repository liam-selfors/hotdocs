# Architecture

The only place the component decomposition itself is declared and changed.
Splitting or merging components is a distinct, heavier, explicitly-reviewed
operation that goes through here — never an ordinary component spec edit.

See `SPEC_GUIDELINES.md` §3.2.

- **`pipeline-decomposition.md`** — the hotdocs pipeline tool's own
  16-component decomposition and dependency graph. Includes a flagged,
  unresolved tension (an orchestrator component's fan-out exceeds D2's
  cap) — see the file for why it wasn't silently patched.
- **`step-phrase-grammar.md`** — the fixed Given/When/Then step grammar
  every `compiled`-kind acceptance criterion is written against, and that
  `criterion-compiler` implements. A breaking change to every `compiled`
  criterion in the corpus, same governance weight as splitting a
  component (D2).
- **`graph-query-engine.md`** — the DuckDB-based engine (`yaml` extension
  for direct frontmatter queries, `duckpgq` for graph traversal) that
  queries the corpus's `depends_on`/`realizes`/`uses_var`/
  `depends_on_guarantees` graph — `impact-analyzer`'s blast-radius
  computation is its first adopter.
