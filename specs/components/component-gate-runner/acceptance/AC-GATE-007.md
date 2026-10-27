# AC-GATE-007

Covers: R-GATE-007
Kind: generated-test

```gherkin
Given a sealed component with a cache miss
When run_component_gates is called
Then spec-bundle-assembler and generator are never invoked for it, and
  verifier-orchestrator is invoked directly against its existing
  source_path code
```
