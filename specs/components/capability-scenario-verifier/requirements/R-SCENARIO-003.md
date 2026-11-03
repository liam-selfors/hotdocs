# R-SCENARIO-003

**R-SCENARIO-003** — **The `bundle` passed to an injected `judge` or
  `test_author`** (`D65`) MUST be `{capability_id, scenario_id, covers,
  kind, gherkin, file}`, never a single component's `CriterionBundle`,
  since no one component owns a cross-component scenario (see the
  glossary's "Injected `judge`/`test_author` callable shape").

  **`generated-test` scenarios are ALWAYS dispatched fresh to
  `test_author`, never pre-checked against a cache file** (`D68`):
  unlike `verifier-orchestrator`'s `R-VERIFY-002`, there is no
  `verification/<component>/` to anchor a cache path to. This is not an
  inefficiency: `test_author` already checks `cache-manager` before any
  model call (`R-AUTHOR-004`), so an unchanged scenario is a fast cache
  hit one layer down. Omitting `test_author` makes a `generated-test`
  scenario `fail`; omitting `judge` makes an `llm-judge` scenario
  `skipped`.
