# AC-CACHE-007

Covers: R-CACHE-007
Kind: generated-test

```gherkin
Given a put call whose payload shape does not match the schema for the
  cache_key's declared gate_version (e.g. a LintReport payload under a
  license_scanner gate_version)
When put is called
Then it is rejected with a schema-validation error and nothing is stored
```
