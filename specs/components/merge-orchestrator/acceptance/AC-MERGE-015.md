# AC-MERGE-015

Covers: R-MERGE-015
Kind: generated-test

```gherkin
Given a sealed component with a cache miss in the blast radius
When run_merge is called
Then spec-bundle-assembler and generator are never invoked for it, and
  verifier-orchestrator is invoked directly against its existing
  source_path code
```
