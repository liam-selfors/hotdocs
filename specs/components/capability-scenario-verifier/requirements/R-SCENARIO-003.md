# R-SCENARIO-003

**R-SCENARIO-003** — **The `bundle` passed to `judge`/`test_author`**
  (`D82`, found missing from this bundle's own visible text) MUST be
  `{capability_id, scenario_id, covers, kind, gherkin, file}` — never
  a single component's `CriterionBundle`, since no one component owns
  a cross-component capability scenario. See the glossary's "Injected
  `judge`/`test_author` callable shape" for the full convention and
  how this differs from `verifier-orchestrator`'s own (component-scoped
  `CriterionBundle`) choice.

  **`generated-test`-kind capability scenarios are ALWAYS dispatched
  fresh to `test_author`, never pre-checked against a cache file
  first** (`D84`, a deliberate choice, found previously unstated):
  unlike `verifier-orchestrator`'s `R-VERIFY-002`, there is no
  `verification/<component>/` to anchor a cache-file path to — a
  capability scenario spans the whole assembled system, not one
  component. This is not a real inefficiency: `test_author` already
  checks `cache-manager` internally before any model call
  (`R-AUTHOR-004`/`005`), so a repeated dispatch for unchanged scenario
  content is already a fast cache hit one layer down, not a redundant
  model call.
