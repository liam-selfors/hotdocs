# Graph Query Engine — Non-Functional Constraints

- **No model calls, no network access.** Pure local file I/O via
  DuckDB table functions.
- **Determinism.** Given the same corpus content and the same
  `repo_root`, every view MUST return byte-identical results on repeat
  queries.
