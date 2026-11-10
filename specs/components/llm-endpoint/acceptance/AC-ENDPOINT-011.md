# AC-ENDPOINT-011

Covers: R-ENDPOINT-002
Kind: generated-test

```gherkin
Given the identifiers "ollama:llama3.1:8b" and "llama3.1:8b"
When each is resolved
Then the first names provider ollama with model "llama3.1:8b" and the
  second names no provider, the colon being part of an Ollama tag

Given a hotdocs.toml whose [llm] table is provider "openai", model
  "gpt-6-astra", api_key_env "MY_KEY" and timeout_seconds 400, a bare
  model name, and a "gemini:..." identifier
When each is resolved
Then the bare name uses openai with the file's api_key_env and
  timeout_seconds, and the gemini one uses Gemini's defaults

Given complete("hi", "anthropic:claude-sonnet-5-5") with ANTHROPIC_API_KEY
  set and urllib.request.urlopen replaced by a recorder (an injected
  backend bypasses resolution and is passed the identifier unchanged)
Then the recorded request body's model is "claude-sonnet-5-5" but
  ModelResponse.model is "anthropic:claude-sonnet-5-5"
```
