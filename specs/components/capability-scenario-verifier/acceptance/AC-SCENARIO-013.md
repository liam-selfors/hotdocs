# AC-SCENARIO-013

Covers: R-SCENARIO-005
Kind: generated-test

```gherkin
Given the planted wrapper interpreter and one generated-test scenario
  whose injected test_author returns a test that passes only when
  os.environ.get("HOTDOCS_WRAPPED") == "1"
When run_capability_scenarios runs
Then the scenario is "pass"

Given the same, but the planted python adapter's provision reports ok
  False, and the test also creates the file ran.txt in repo_root
When run_capability_scenarios runs
Then the scenario is "fail" and repo_root has no ran.txt
```
