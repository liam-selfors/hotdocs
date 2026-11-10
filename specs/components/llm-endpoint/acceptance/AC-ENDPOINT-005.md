# AC-ENDPOINT-005

Covers: R-ENDPOINT-003
Kind: generated-test

```gherkin
Given no hotdocs.toml, and the claude command replaced by a recorder
When complete() is called with model="claude-sonnet-5" and no
  provider-selection parameter of any kind
Then it dispatches through claude-cli, passing --tools "" and one of
  --bare (ANTHROPIC_API_KEY set) or --safe-mode (not set)

Given the model "anthropic:m", "openai:m", "gemini:m", "ollama:m" and
  "openai-compatible:m", with a hotdocs.toml whose [llm] table is
  provider "openai-compatible", model "m", base_url "http://h:8000/v1"
When each is called with urllib.request.urlopen replaced by a recorder,
  and ANTHROPIC_API_KEY, OPENAI_API_KEY and GEMINI_API_KEY set
Then each dispatches over HTTP through its own adapter, with no
  dependency beyond the standard library
```
