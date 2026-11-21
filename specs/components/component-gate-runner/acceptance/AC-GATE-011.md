# AC-GATE-011

Covers: R-GATE-011
Kind: generated-test

The committed manifest: `testing.md`. current_provenance_key returns
spec_bundle_hash "sha256:k" and gate_versions {"verifier": "v@1"};
check_provenance returns hit false, reason "environment differs".

```gherkin
Given verify returns overall "pass", and the scans return
  {"blocked": false} and {"flagged": false}
When run_component_gates("comp-foo", repo_root, "m") is called
Then verify was called once with ("comp-foo", repo_root) and the judge
  and test_author make_closures returned; assemble, run_attempts and
  write_attempt_record were never called
And write_provenance was called once, after both scans, with
  verification_report verify's report, those scan results, attempts 2,
  that attempt_history, provenance_hit false, gate_versions
  {"verifier": "v@1"}, and a generation_result with files {},
  spec_bundle_hash "sha256:k", model "m0", prompt_version "v9", mode
  "agentic", turns 4, tool_calls 7 and isolation "seatbelt"
And reverified is true, blocked is false, provenance_hit is false,
  attempts is [] and verification is verify's report

Given verify returns overall "fail", and separately the license scan
  returns {"blocked": true}, and separately the secret scan returns
  {"flagged": true}, and run_attempts returns passed true with a
  generation result with one file
When run_component_gates is called
Then the calls after check_provenance are, in order: verify, both scans, assemble,
  run_attempts, both scans, write_provenance, called once with the
  loop's generation result; reverified is false

Given check_provenance returns reason "assets differ"
When run_component_gates is called
Then verify was never called, run_attempts was called once and
  reverified is false
```
