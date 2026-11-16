# AC-ENDPOINT-006

Covers: R-ENDPOINT-006
Kind: generated-test

```gherkin
Given a mock backend that fails one call with a timeout and succeeds on
  a second, independent call
When both complete() calls finish
Then .hotdocs/calls/ contains two records, one with
  model_call_error.category "timeout" and one with no model_call_error
  — queryable via DuckDB's read_json without any bespoke parsing
```
