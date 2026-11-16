# R-VERIFY-009

**R-VERIFY-009** — For a `generated-test`-kind criterion with no cached
  test yet, this component MUST dispatch to an injectable `test_author`
  callable, passing exactly the `CriterionBundle`
  `spec-bundle-assembler.assemble_criterion(component_id, criterion_id,
  repo_root)` returns for that criterion, and use the returned test
  code. It MUST NOT build its own `CriterionBundle`: a second producer
  with a narrower field set silently starved `test-author` of
  `dependency_interfaces` (`D119`). Its role is dispatch and recording,
  as in R-VERIFY-003; the authoring happens inside the injected
  callable, which is why this requirement is `kind: compiled` despite
  coordinating non-deterministic work.
