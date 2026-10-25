# AC-TRACK-007

Covers: R-TRACK-007
Kind: compiled

```gherkin
Given a GenerationResult with model_call_error populated and no
  VerificationReport (generation itself failed, nothing to verify)
When write_attempt_record runs for that component
Then one AttemptRecord is written to
  .hotdocs/attempts/<component_id>/ with generation populated,
  verification null, and the file is queryable via DuckDB's read_json
  with no bespoke parsing
```
