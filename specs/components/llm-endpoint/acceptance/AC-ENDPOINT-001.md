# AC-ENDPOINT-001

Covers: R-ENDPOINT-002
Kind: generated-test

```gherkin
Given no hotdocs.toml and a model identifier "gpt-5" that no provider's
  naming rule matches
When complete() is called with it
Then it fails immediately with a specific usage error, before any
  call is attempted — never a silent fallback to a default provider,
  and never reported as model_call_error

Given a hotdocs.toml that names provider openai-compatible with no base_url
When complete() is called
Then the same usage error is raised, as it is for an invalid hotdocs.toml
```
