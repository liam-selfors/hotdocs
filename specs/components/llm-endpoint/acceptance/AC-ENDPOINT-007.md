# AC-ENDPOINT-007

Covers: R-ENDPOINT-007
Kind: generated-test

```gherkin
Given a hotdocs.toml with a valid [llm] table in the current directory
When load_config() is called, then again with VAR-HOTDOCS-CONFIG naming
  another valid file
Then it returns the first file's table, then the named file's, and None
  with neither; a named file that is missing raises ValueError

Given [llm] tables holding an unknown entry, an api_key entry, a
  provider outside the list, no model, a timeout_seconds of 120, or a
  claude-cli entry with a base_url
When load_config() reads each
Then each raises ValueError naming the problem, and the api_key one says
  hotdocs.toml must never hold a secret

Given a file with a valid [llm] table and a separate [other] table
When save_config() replaces the provider
Then the new [llm] is written, [other] is untouched, and the file never
  contains a secret
```
