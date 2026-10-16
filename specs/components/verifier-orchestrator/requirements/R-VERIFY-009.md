# R-VERIFY-009

**R-VERIFY-009** — For a `generated-test`-kind criterion with no cached
  test yet, this component MUST dispatch to an injectable `test_author`
  callable, passing exactly the `CriterionBundle` `spec-bundle-assembler`
  produces for that criterion, and use the returned test code. **This
  component's role here is dispatch and recording, identical in shape to
  R-VERIFY-003's handling of `llm-judge`** — the actual authoring happens
  inside whatever callable is injected, never in this component's own
  logic, which is why this requirement, like R-VERIFY-003, is `kind:
  compiled` despite coordinating non-deterministic work.
