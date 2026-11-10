# AC-ENDPOINT-003

Covers: R-ENDPOINT-004
Kind: generated-test

```gherkin
Given an injected mock backend that raises
  urllib.error.HTTPError with code 429 on its first and only call
When complete() is called
Then the returned ModelResponse has model_call_error.category exactly
  "rate_limit", text null, with no second call made to the mock backend
  — confirming both that there is no internal retry loop and that the
  failure category is captured as structured data, not just a boolean
```
