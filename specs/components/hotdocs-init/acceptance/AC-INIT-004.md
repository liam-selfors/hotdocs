# AC-INIT-004

Covers: R-INIT-004
Kind: generated-test

```gherkin
Given a fake detect_providers listing ollama (not available) and
  openai (available, suggested_model "gpt-x", api_key_env "OPENAI_API_KEY"),
  and no needs_base_url on either
When init runs interactively and every answer is empty
Then the questions were, in order, the provider, the model, and the API-key
  variable name (no base URL), both providers were printed, and save_config
  received provider "openai", model "gpt-x", api_key_env "OPENAI_API_KEY"

Given the same listing and the provider answers "bogus" then "2"
When init runs interactively
Then "bogus" is asked again and "2" selects the second listed provider

Given a provider "openai-compatible" with needs_base_url true, suggested_model "",
  default_base_url None, default_api_key_env None
When init runs interactively, choosing it, then answering "" (asked again), "m",
  "" (asked again), "http://h/v1", and "" for the API-key name
Then the model and base URL were each asked twice, and save_config received model "m",
  base_url "http://h/v1", and no api_key_env keyword

Given the provider "claude-cli" and env PATH holding an executable "claude" file
When init runs interactively with empty answers
Then no base URL and no API-key question was asked, and it returns 0

Given a tool root with no gen/llm-endpoint
When init runs with --yes
Then output_fn received "provider not configured: gen/llm-endpoint is missing", the exit code is 0, and no hotdocs.toml was written

Given <dir>/hotdocs.toml already exists
When init runs
Then the provider step is skipped with a message and hotdocs.toml is unchanged
```
