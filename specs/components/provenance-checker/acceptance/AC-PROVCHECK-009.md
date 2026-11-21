# AC-PROVCHECK-009

Covers: R-PROVCHECK-005
Kind: generated-test

```gherkin
Given a repo_root with `testing.md`'s key stand-ins
When current_provenance_key("comp-foo", repo_root) is called
Then spec_bundle_hash is "sha256:abc", assemble was called for
  "comp-foo" with mode "cold", gate_versions is exactly {"compiler":
  "cc@1", "generated_test": "ta@1", "verifier": "vo@1",
  "license_scanner": "ls@1", "secret_scanner": "ss@1", "generator":
  "gen@3+v11"}, and neither
  scanner's scan was called

Given the faked assemble raises ValueError
When current_provenance_key is called
Then that ValueError propagates
```
