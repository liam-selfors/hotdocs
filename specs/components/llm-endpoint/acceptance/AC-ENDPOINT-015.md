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

Given save_config(<path>, "claude-cli", "m", auth="login") on a missing
  file
When load_config(<path>) is called
Then it returns provider "claude-cli", model "m" and auth "login"
```
