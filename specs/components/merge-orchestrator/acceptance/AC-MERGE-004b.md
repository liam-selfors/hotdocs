# AC-MERGE-004b

Covers: R-MERGE-004
Kind: generated-test

```gherkin
Given a cache miss for an impacted component
When run_merge is called
Then spec-bundle-assembler, generator, and verifier-orchestrator are
  invoked in that order for it
```
