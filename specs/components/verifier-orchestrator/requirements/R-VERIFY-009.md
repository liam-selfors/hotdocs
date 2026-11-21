# R-VERIFY-009

**R-VERIFY-009** — For a `generated-test`-kind criterion with no cached
  test, this component MUST call the injectable `test_author` with
  exactly the `CriterionBundle`
  `spec-bundle-assembler.assemble_criterion(component_id, criterion_id,
  repo_root)` returns, never a bundle it builds itself (`D119`), and
  use the returned test code.
