# AC-ENDPOINT-001

Covers: R-ENDPOINT-002
Kind: generated-test

```gherkin
Given VAR_HOTDOCS_CONFIG unset, no hotdocs.toml in the current
  directory, and a model identifier "gpt-5" that no provider's
  naming rule matches
When complete() is called with it
Then it fails immediately with a specific usage error, before any
  call is attempted — never a silent fallback to a default provider,
  and never reported as model_call_error

Given a hotdocs.toml, written directly as text (save_config refuses it),
  whose [llm] table names provider openai-compatible and a model but no
  base_url
When complete() is called
Then the same usage error is raised, as it is for an invalid hotdocs.toml
```
