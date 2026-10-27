# AC-ENDPOINT-001

Covers: R-ENDPOINT-002
Kind: generated-test

```gherkin
Given a model identifier that matches no implemented backend's naming
  pattern
When complete() is called with it
Then it fails immediately with a specific usage error, before any
  network call is attempted — never a silent fallback to a default
  backend, and never reported as model_call_error
```
