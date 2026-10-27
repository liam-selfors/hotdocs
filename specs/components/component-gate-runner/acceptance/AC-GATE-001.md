# AC-GATE-001

Covers: R-GATE-001
Kind: generated-test

```gherkin
Given a non-sealed component provenance-checker reports a hit for
When run_component_gates is called
Then generator, verifier-orchestrator, license-scanner, and secret-scanner
  are never invoked for it, and the result shows provenance_hit true
```
