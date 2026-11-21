# AC-GATE-006

Covers: R-GATE-006
Kind: generated-test

```gherkin
Given current_sealed_key returning None, current_provenance_key
  returning a key with gate_versions {"verifier": "v@1"},
  check_provenance returning hit false, a faked run_attempts that calls
  on_attempt once per attempt entry and returns passed true with two
  attempt entries and a generation result with one file, and a faked
  write_attempt_record that writes one file into
  .hotdocs/attempts/comp-foo/ per call
When run_component_gates is called
Then write_provenance was called once, after both scans, with inputs
  whose gate_versions is {"verifier": "v@1"}, provenance_hit is false,
  attempts is 2, attempt_history is the two attempt entries, and
  generation_result, verification_report, license_scan_result and
  secret_scan_result are the faked dependencies' results

Given instead the loop returns passed false and its last generation
  result has files {} and model_call_error {"category": "network",
  "message": "down"}
When run_component_gates is called
Then write_provenance was never called
```
