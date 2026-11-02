# AC-ENDPOINT-004

Covers: R-ENDPOINT-005
Kind: generated-test

```gherkin
Given a credential in the environment variable a provider reads, and a
  call to each provider that fails — including a vendor error body that
  echoes the credential back
When the resulting ModelResponse, the call log, and any
  check_connection result are inspected
Then the credential value appears in none of them — only the model
  identifier actually used is present

Given save_config is called with api_key_env set to the credential's
  value instead of a variable name
Then it refuses, and no file is written
```
