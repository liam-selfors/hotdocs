# AC-PROVCHECK-009

Covers: R-PROVCHECK-005
Kind: generated-test

```gherkin
Given a repo_root with faked dependency modules: spec-bundle-assembler
  whose assemble records its arguments and returns an object with
  spec_bundle_hash "sha256:abc"; criterion-compiler (under
  pipeline/criterion-compiler/), test-author, and verifier-orchestrator
  each defining GATE_VERSION "cc@1", "ta@1", "vo@1"; and license-scanner
  and secret-scanner each defining gate_version(repo_root) returning
  "ls@1" and "ss@1", plus a scan function that records any call
When current_provenance_key("comp-foo", repo_root) is called
Then spec_bundle_hash is "sha256:abc", assemble was called for
  "comp-foo" with mode "cold", gate_versions is exactly {"compiler":
  "cc@1", "generated_test": "ta@1", "verifier": "vo@1",
  "license_scanner": "ls@1", "secret_scanner": "ss@1"}, and neither
  scanner's scan was called

Given the faked assemble raises ValueError
When current_provenance_key is called
Then that ValueError propagates
```
