# R-VERIFY-017

**R-VERIFY-017** — For a component whose `component.md` frontmatter has
  `sealed: true` and a single-line `source_path: <path>` (`D170`),
  `verify` MUST verify the code at `<repo_root>/<source_path>`, not
  `gen/<slug>/`: that directory is where the module is loaded from for
  interface drift (`R-VERIFY-004`) and what tests may import, and a
  missing `source_path` directory is a hard failure. Its criteria are
  verified only by the characterization tests: the `test_*.py` files
  directly in `verification/<slug>/` (hand-maintained, never authored by
  `test_author`).

  A `compiled` or `generated-test` criterion `AC-X-NNN` is `pass` iff at
  least one test function named `test_` plus the id lowercased with
  hyphens as underscores (`test_ac_x_nnn`), exactly or followed by `_`
  and more text, exists in those files and every such test passes. It is
  `fail` otherwise; with no matching test its `failure_detail.message`
  is `no characterization test`. `test_author` and the cached-test lookup
  are never used. `llm-judge` criteria follow `R-VERIFY-003`.

  Mutation testing is not run: `mutation_score` is `null` and never
  gates `overall`, which is `pass` iff no criterion failed and there is
  no interface drift. Files named `.sealed-provenance.json` and
  `__pycache__` directories under `source_path` are ignored.
