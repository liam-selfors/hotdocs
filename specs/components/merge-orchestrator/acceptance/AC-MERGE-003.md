# AC-MERGE-003

Covers: R-MERGE-003
Kind: compiled

```gherkin
Given a non-sealed component provenance-checker reports a hit for
When run_merge is called
Then generator, verifier-orchestrator, license-scanner, and secret-scanner
  are never invoked for it, and MergeResult shows provenance_hit true
```
