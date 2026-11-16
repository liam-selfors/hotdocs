# AC-ENDPOINT-013

Covers: R-ENDPOINT-007
Kind: generated-test

```gherkin
Given VAR_HOTDOCS_CONFIG naming a file that does not exist, then a file
  that is not TOML
When load_config() runs for each
Then each raises ValueError, and for a TOML file with only an [other]
  table it returns None

Given save_config(<dir>/sub/hotdocs.toml, "openai", "gpt-6-astra",
  timeout_seconds=900) where <dir>/sub does not exist
Then the directory is created and load_config(that file) returns
  provider "openai", model "gpt-6-astra", timeout_seconds 900, and
  base_url and api_key_env None

Given that file then save_config(same path, "ollama", "llama3.2")
Then load_config returns provider "ollama" and timeout_seconds None

Given detect_providers(env={"PATH": "<dir with an executable named
  claude>", "OPENAI_API_KEY": "k"}, probe_ollama=False)
Then claude-cli and openai are available, anthropic, gemini and ollama
  are not, and openai's api_key_env is "OPENAI_API_KEY"
```
