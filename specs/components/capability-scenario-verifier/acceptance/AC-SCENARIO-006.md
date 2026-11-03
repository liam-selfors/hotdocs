# AC-SCENARIO-006

Covers: R-SCENARIO-004
Kind: generated-test

```gherkin
Given no record, one realizing component, one generated-test scenario
  whose fake author_test returns a passing test, and model "m", seed 2
When run_capability_gates("P-X", repo_root, "m", seed=2) is called
Then the scenario's test is run, hit is false, the report has overall
  "pass", and verification/capabilities/P-X/.provenance.json exists
  holding exactly capability_id, gate_version, content_hash,
  realizing_components, capability_scenario_report, model "m", and seed 2

Given that record now exists
When check_capability_provenance("P-X", repo_root) is called
Then hit is true

Given no record and model None
When run_capability_gates is called
Then ModelRequiredError is raised, no fake module was called, and no
  file was written
```
