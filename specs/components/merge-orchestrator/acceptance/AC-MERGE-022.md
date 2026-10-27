# AC-MERGE-022

Covers: R-MERGE-021
Kind: generated-test

```gherkin
Given a cache-miss component whose generator call returns
  model_call_error (no candidate produced)
When run_merge processes that component
Then merge-tracker's write_attempt_record is called with that
  GenerationResult and a null VerificationReport, before the merge's
  block decision is evaluated, and a failure in that call does not
  change whether the merge is blocked
```
