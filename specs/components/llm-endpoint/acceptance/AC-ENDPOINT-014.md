# AC-ENDPOINT-014

Covers: R-ENDPOINT-003
Kind: generated-test

```gherkin
Given ANTHROPIC_API_KEY set to "k1", a hotdocs.toml whose [llm] table
  is provider "claude-cli", model "m" and auth "login", and the claude
  command replaced by a recorder that records its arguments and its
  ANTHROPIC_API_KEY and prints a successful stream
When complete("hi", "m") is called
Then the recorded arguments hold --safe-mode and not --bare, and the
  recorded ANTHROPIC_API_KEY is None

Given the same with auth "key"
When complete("hi", "m") is called
Then the recorded arguments hold --bare, and the recorded
  ANTHROPIC_API_KEY is "k1"

Given ANTHROPIC_API_KEY set to "k1", a hotdocs.toml with provider
  "claude-cli", model "m" and no auth, and a recorder that prints
  "Invalid API key" to stderr and exits 1
When complete("hi", "m") is called
Then model_call_error is {"category": "auth", "message": "claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it instead of your claude.ai login; unset it, or set auth = \"login\" in hotdocs.toml's [llm] table"}

Given the same recorder and auth "key"
When complete("hi", "m") is called
Then model_call_error is {"category": "auth", "message": "claude command failed (auth)"}
```
