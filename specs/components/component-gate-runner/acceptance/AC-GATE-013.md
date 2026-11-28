# AC-GATE-013

Covers: R-GATE-011
Kind: generated-test

The committed manifest: `testing.md`. current_provenance_key returns
spec_bundle_hash "sha256:k" and gate_versions {"verifier": "v@2"}; verify
returns overall "pass", the scans return {"blocked": false} and
{"flagged": false}, and run_attempts returns passed true with a
generation result with one file.

```gherkin
Given check_provenance returns hit false and reason "hash formula
  differs", and separately reason "gates differ"
When run_component_gates("comp-foo", repo_root, "m") is called
Then in each case verify was called once, run_attempts and assemble
  were never called, write_provenance was called once with
  spec_bundle_hash "sha256:k" and gate_versions {"verifier": "v@2"},
  and reverified is true

Given check_provenance returns hit false and reason "gate_versions
  differ", and separately reason "spec_bundle_hash differs"
When run_component_gates is called
Then in each case verify was never called, run_attempts was called
  once and reverified is false
```
