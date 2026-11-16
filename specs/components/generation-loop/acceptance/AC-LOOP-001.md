# AC-LOOP-001

Covers: R-LOOP-001
Kind: generated-test

```gherkin
Given stand-ins whose generate returns, in call order, results with
  model_call_error categories "truncated_response" then "rate_limit"
When run_attempts("comp-widget", bundle, repo_root, "m") is called
Then generate was called twice, attempts' outcomes are
  "generation_failed" and "generation_failed" with error_category
  "truncated_response" and "rate_limit", stop_reason is "not_retried",
  and check_surface and verify were never called

Given a generate stand-in returning refused "sealed-component"
When run_attempts is called with max_attempts=3
Then generate was called once, the only attempt's outcome is "refused",
  and stop_reason is "refused"

Given mode "turbo", or max_attempts 0
When run_attempts is called
Then it raises ValueError and no stand-in was called
```
