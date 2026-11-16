# AC-GATE-006

Covers: R-GATE-006
Kind: generated-test

```gherkin
Given a provenance miss whose key has gate_versions {"verifier":
  "v@1"}, one generated file, verify returning overall "pass", and a
  faked write_attempt_record that also writes one file into
  .hotdocs/attempts/foo/
When run_component_gates is called
Then write_provenance was called once, after both scans and
  write_attempt_record, with inputs whose gate_versions is
  {"verifier": "v@1"}, provenance_hit is false, attempts is 1, and
  generation_result, verification_report, license_scan_result, and
  secret_scan_result are the faked dependencies' results

Given instead a faked generator returning a model_call_error
When run_component_gates is called
Then write_provenance was never called
```
