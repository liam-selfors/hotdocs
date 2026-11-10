# AC-ENDPOINT-004

Covers: R-ENDPOINT-005
Kind: generated-test

```gherkin
Given VAR_HOTDOCS_CONFIG unset, an empty current directory, and each
  provider's key variable (ANTHROPIC_API_KEY, OPENAI_API_KEY,
  GEMINI_API_KEY) set to "sk-SECRET-123", with urllib.request.urlopen
  raising HTTP 401 whose body echoes "sk-SECRET-123"
When complete() is called with "anthropic:m", "openai:m" and "gemini:m",
  and check_connection with each of those providers and "m"
Then "sk-SECRET-123" appears in no ModelResponse, no file under
  .hotdocs/calls/, and no check_connection result

Given OPENAI_API_KEY set to "sk-SECRET-123"
When save_config(<dir>/hotdocs.toml, "openai", "m",
  api_key_env="sk-SECRET-123") is called
Then it raises ValueError containing "never the key itself", and
  <dir>/hotdocs.toml does not exist
```
