# AC-ENDPOINT-005

Covers: R-ENDPOINT-003
Kind: generated-test

```gherkin
Given llm-endpoint configured with only its v1 backend (Anthropic) and
  no other configuration
When complete() is called with model="claude-sonnet-5" and no
  backend-selection parameter of any kind
Then it dispatches successfully — confirming a caller only ever names a
  model, never a backend; which backend implements a given identifier is
  entirely this component's own internal detail
```
