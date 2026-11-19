# R-VERIFY-017

**R-VERIFY-017** — For a component whose `component.md` frontmatter has
  `sealed: true` and a single-line `source_path: <path>` (`D170`),
  `verify` MUST check the code at `<repo_root>/<source_path>`, not
  `gen/<slug>/`, for interface drift (`R-VERIFY-004`) and imports; a
  missing directory makes `overall` `fail`, never an exception. Its
  criteria are verified only by the `test_*.py` files directly in
  `verification/<slug>/`.

  A `compiled` or `generated-test` criterion `AC-X-NNN` is `pass` iff at
  least one test function named `test_ac_x_nnn` (the id lowercased,
  hyphens as underscores), exactly or followed by `_` and more text,
  exists in those files and every such test passes; otherwise `fail`,
  with `failure_detail.message` `no characterization test` when none
  matches. `test_author` and the cache are never used; `llm-judge`
  criteria follow `R-VERIFY-003`.

  No mutation testing and no asset provisioning:
  `assets` is `[]`, pytest runs under `sys.executable`, `mutation_score` is `null` and `overall` is
  `pass` iff no criterion failed and there is no drift.
  `.sealed-provenance.json` files and `__pycache__` directories under
  `source_path` are ignored.
