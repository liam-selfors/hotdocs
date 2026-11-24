# R-SCENARIO-003

**R-SCENARIO-003** — **The `bundle` passed to an injected `judge` or
  `test_author`** (`D65`) MUST be `{capability_id, scenario_id, covers,
  kind, gherkin, file}`, never a single component's `CriterionBundle`,
  since no one component owns a cross-component scenario (see the
  glossary's "Injected `judge`/`test_author` callable shape").

  **A `generated-test` scenario is always dispatched to the
  `test_author` passed in** (`D68`); reusing a committed test is the
  job of the callable `R-SCENARIO-007` builds (`D370`). Omitting `test_author` makes a `generated-test`
  scenario `fail`; omitting `judge` makes an `llm-judge` scenario
  `skipped`.
