# AC-GATE-007

Covers: R-GATE-007
Kind: generated-test

```gherkin
Given a faked provenance-checker whose current_sealed_key returns, for
  comp-foo, a key with owners ["pipeline-team"], source_path
  "pipeline/foo/", source_hash "sha256:k", and verifier_version
  "verifier-orchestrator@2.0.0"; a faked verify returning overall
  "pass" with two criteria; and no component.md for comp-foo
When run_component_gates("comp-foo", repo_root, "m") is called
Then check_provenance, current_provenance_key, assemble, run_attempts,
  write_attempt_record, and write_provenance were never called; verify
  and both scanners were called once each; write_sealed_provenance was
  called exactly once, after verify and both scans, with component_id
  "comp-foo", owners ["pipeline-team"], source_path "pipeline/foo/",
  source_hash "sha256:k", verifier_version
  "verifier-orchestrator@2.0.0", and verify's report; provenance_hit is
  false and blocked is false

Given verify returns overall "fail" for that sealed component
When run_component_gates is called
Then blocked is true with block_reason "verification_failed", and
  write_sealed_provenance was still called once with the failing report

Given current_sealed_key returns None for comp-foo
  and check_provenance returns hit false, and run_attempts calls
  on_attempt once and returns passed true with a generation result
  with one file
When run_component_gates is called
Then write_sealed_provenance and make_closures were never
  called, and current_provenance_key, check_provenance, assemble,
  run_attempts, write_attempt_record, both scans and write_provenance
  were each called once, in that order
```
