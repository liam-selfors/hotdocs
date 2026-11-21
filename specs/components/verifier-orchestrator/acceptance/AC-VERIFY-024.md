# AC-VERIFY-024

Covers: R-VERIFY-019
Kind: generated-test

```gherkin
Given one generated-test criterion with no cached test, and a
  test_author stand-in returning model_call_error
  {"category": "network", "message": "dropped"} on its first call and a
  passing test with the correct header on its second
When verify runs with it
Then test_author was called exactly twice and the criterion's result is
  "pass"

Given a stand-in always returning model_call_error
  {"category": "network", "message": "dropped"}
When verify runs with it
Then test_author was called exactly twice, and the criterion's result
  is "fail" with failure_origin "test" and failure_detail.message
  "test authoring failed: network: dropped"

Given a stand-in always returning model_call_error
  {"category": "auth", "message": "bad key"}
When verify runs with it
Then test_author was called exactly once, and the criterion's result is
  "fail" with failure_origin "test" and failure_detail.message
  "test authoring failed: auth: bad key"
```
