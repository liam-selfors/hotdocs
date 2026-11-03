# AC-SCENARIO-001

Covers: R-SCENARIO-001
Kind: generated-test

Fixtures follow `interface/library.md`'s "Test fixtures".

```gherkin
Given a blast radius of two components, and one product capability
  whose realizes-set includes both, with exactly one generated-test
  scenario whose fake test_author returns a passing test
When run_capability_scenarios is called with that blast radius
Then the scenario's test is run, and the result is keyed by that
  capability's P-id, never by either component, with overall "pass"
```
