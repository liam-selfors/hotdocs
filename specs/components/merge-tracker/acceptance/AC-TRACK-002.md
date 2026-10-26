# AC-TRACK-002

Covers: R-TRACK-002
Kind: compiled

```gherkin
Given a merge attempt where comp-foo succeeded (provenance hit) and
  comp-bar exhausted retries after failing verification once
When write_tracking_record is called
Then the resulting TrackingRecord's components field contains comp-foo
  with provenance_hit true and comp-bar with model_call_error false and
  verification_overall "fail" — flattened summaries, not full nested
  VerificationReport objects
```
