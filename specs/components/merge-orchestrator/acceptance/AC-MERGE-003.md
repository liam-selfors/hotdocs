# AC-MERGE-003

Covers: R-MERGE-003
Kind: compiled

```gherkin
Given a component whose spec_bundle_hash matches a cache-manager entry
When run_merge is called
Then generator, verifier-orchestrator, license-scanner, and secret-scanner
  are never invoked for that component
```
