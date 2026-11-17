# AC-ENDPOINT-015

Covers: R-ENDPOINT-007
Kind: generated-test

```gherkin
Given a hotdocs.toml whose [llm] table is provider "claude-cli", model
  "m" and auth "login"
When load_config(<its path>) is called
Then it returns auth "login", and resolve_provider("m", that config)
  returns auth "login"

Given the same table with auth "token", and a table with provider
  "openai", model "m" and auth "login"
When load_config is called on each
Then each raises ValueError

Given the config dict {"provider": "openai", "model": "x", "base_url":
  None, "api_key_env": "MY_KEY", "timeout_seconds": 400}, which has no
  auth entry
When resolve_provider("gpt-6-astra", config) is called
Then it returns provider "openai", api_key_env "MY_KEY", timeout_seconds
  400 and auth None

Given a file holding "[llm\n", and a table with provider "openai",
  model "m", base_url "" and api_key_env ""
When load_config is called on each
Then the first raises ValueError whose message contains
  "not valid TOML", and the second returns base_url None and
  api_key_env None

Given save_config(<path>, "claude-cli", "m", auth="login") on a missing
  file
When load_config(<path>) is called
Then it returns provider "claude-cli", model "m" and auth "login"
```
