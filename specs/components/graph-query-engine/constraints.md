# Graph Query Engine — Non-Functional Constraints

- **No model calls, no network access.** Pure local file I/O via
  DuckDB table functions, same trust tier as `spec-linter`.
- **Determinism.** Given the same corpus content and the same
  `repo_root`, every view MUST return byte-identical results on repeat
  queries — required for any consumer's own cache-key correctness
  (`notes/initial-ideas.md`'s own D13) that reads through these views.
- **Never embeds `repo_root` into the generated SQL file itself.** The
  `{repo_root}` placeholder (`R-GQE-001`–`006`) MUST be substituted at
  `load_views()` call time, not baked in at generation time — the
  generated SQL is reusable across any checkout, not tied to the one
  it was generated against.
- **Hand-bootstrapped, not yet cold-regenerated** — the same honest
  exception `spec-linter` already documents (`generator`/
  `criterion-compiler` don't exist yet). See
  `verification/graph-query-engine/BOOTSTRAP.md`.
