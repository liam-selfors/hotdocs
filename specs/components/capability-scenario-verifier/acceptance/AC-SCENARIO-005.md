# AC-SCENARIO-005

Covers: R-SCENARIO-004
Kind: generated-test

```gherkin
Given a committed record whose gate_version and content_hash both equal
  the current ones, with a passing report, and fake test-author and
  llm-endpoint modules that record every call
When check_capability_provenance("P-ZERO-EDIT", repo_root) is called
Then hit is true and capability_scenario_report is the record's report

Given the same state
When run_capability_gates("P-ZERO-EDIT", repo_root, "m") is called
Then the result equals the check result, no fake module was called, no
  file under repo_root was written or modified, and a call with model
  None behaves identically

Given no record, a record that is not valid JSON, and a record with a
  different gate_version
When check_capability_provenance is called for each
Then each gives hit false and capability_scenario_report null

Given a capability_id no specs/product file declares
When either function is called
Then UnknownCapabilityError is raised
```
