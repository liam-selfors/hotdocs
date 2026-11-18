# AC-GQE-001

Covers: R-GQE-001
Kind: generated-test

```gherkin
Given the fixture corpus of specs/architecture/graph-query-engine-fixture.md
  written under a temporary repo_root, README.md files included
When load_views runs and nodes is queried
Then the row count per kind is component 2, capability 1, var 1,
  decision 2, guarantee 1, requirement 2, acceptance 1 and
  capability_scenario 2, and no row's id is null
```
