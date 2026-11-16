# Architecture

The only place the component decomposition itself is declared and changed.
Splitting or merging components is a distinct, heavier, explicitly-reviewed
operation that goes through here — never an ordinary component spec edit.

See `SPEC_GUIDELINES.md` §3.2.

- **`pipeline-decomposition.md`** — the hotdocs pipeline tool's own
  23-component decomposition and dependency graph. Documents a real,
  deliberately-explained tension (`merge-orchestrator`'s fan-out
  exceeded its own warn threshold, back when that component existed)
  rather than silently patching it — `D14` and `D76` each resolved the
  word-count half of that tension by extraction once it actually hit
  the hard-fail cap (twice), and `D87` later removed the component
  entirely once its one remaining job (a provenance check) turned out
  not to need an orchestrating component at all. See the file's own
  "finding" section for the full history.
- **`step-phrase-grammar.md`** — the fixed Given/When/Then step grammar
  every `compiled`-kind acceptance criterion is written against, and that
  `criterion-compiler` implements. A breaking change to every `compiled`
  criterion in the corpus, the same governance weight as splitting a
  component.
- **`graph-query-engine.md`** — the DuckDB-based engine (`yaml` extension
  for direct frontmatter queries, `duckpgq` available for graph traversal)
  that queries the corpus's `depends_on`/`realizes`/`uses_var`/
  `depends_on_guarantees`/`covers` graph — the decomposition rationale and
  adoption history only; the six shared views' exact definitions and
  generated SQL now live in their own component, `graph-query-engine`
  (`D13`), once the embedded SQL here turned out to be an unverified
  implementation rather than documentation (`D13` found three of
  six views broken, never having actually been run). `impact-analyzer`'s
  blast-radius computation was the first adopter, since joined by
  `spec-linter`, `corpus-graph-builder`, `capability-scenario-verifier`,
  and `review-packet-builder` (D13).
