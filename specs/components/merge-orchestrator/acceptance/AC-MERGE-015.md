# AC-MERGE-015

Covers: R-MERGE-015
Kind: compiled

```gherkin
Given a sealed component with a cache miss in the blast radius
When run_merge is called
Then spec-bundle-assembler, generator, and cross-model-divergence-checker
  are never invoked for it, and verifier-orchestrator is invoked directly
  against its existing source_path code
```
