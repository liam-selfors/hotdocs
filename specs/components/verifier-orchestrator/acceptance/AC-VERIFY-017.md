# AC-VERIFY-017

Covers: R-VERIFY-015
Kind: generated-test

```gherkin
Given the verifier-orchestrator module is imported
When GATE_VERSION is read, without calling verify
Then it equals "verifier-orchestrator@3.1.0"
```
